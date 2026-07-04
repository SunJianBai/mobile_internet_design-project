"""Multi-agent architecture: 主Agent + 子Agent-as-Tool (模式B).

主Agent 通过 ReAct 循环调用 3 个子Agent（订单/社交/地图天气），
每个子Agent 内部又是一个带原子工具的 ReAct Agent。
"""

import json
import logging
import asyncio
import contextvars
import hashlib
import re
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import AsyncIterator

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from app.config import (
    SILICONFLOW_API_KEY,
    SILICONFLOW_BASE_URL,
    SILICONFLOW_MODEL,
    SILICONFLOW_ROUTER_MODEL,
)
from app.tools import search_orders, create_order, get_my_orders, get_order_detail
from app.tools_order import (
    ORDER_EXTRA_TOOLS,
    accept_applicant,
    apply_to_order,
    cancel_order_application,
    complete_order,
    reject_order_application,
)
from app.tools_content import CONTENT_TOOLS, search_contents, create_content, create_comment, like_content
from app.tools_user import USER_TOOLS, get_user_profile, search_users
from app.mcp_tools import (
    MCP_TOOLS,
    maps_around_search,
    maps_direction_driving,
    maps_direction_walking,
    maps_geo,
    maps_weather,
)
from app.tools_utils import UTIL_TOOLS
from app.prompts import (
    build_main_agent_prompt,
    ORDER_AGENT_PROMPT,
    SOCIAL_AGENT_PROMPT,
    MAP_AGENT_PROMPT,
    MEMORY_EXTRACTION_PROMPT,
)

logger = logging.getLogger(__name__)

_event_sink: contextvars.ContextVar = contextvars.ContextVar("agent_event_sink", default=None)
_delegation_state: contextvars.ContextVar = contextvars.ContextVar("agent_delegation_state", default=None)
_allowed_delegation_agents: contextvars.ContextVar = contextvars.ContextVar("agent_allowed_delegation_agents", default=None)

MAIN_AGENT_RECURSION_LIMIT = 12
SUB_AGENT_RECURSION_LIMIT = 8
MAX_MAIN_DELEGATIONS = 4
MAX_DELEGATIONS_PER_AGENT = 2
ROUTER_TIMEOUT_SECONDS = 14
INTENT_REVIEW_TIMEOUT_SECONDS = 15
INTENT_TOTAL_BUDGET_SECONDS = 29
SUB_AGENT_TIMEOUT_SECONDS = 75
INTENT_CACHE_TTL_SECONDS = 10 * 60
INTENT_CACHE_MAX_SIZE = 128

_intent_cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()

AGENT_SUGGESTION_TO_DELEGATION = {
    "order_query": "order",
    "order_draft": "order",
    "content_query": "content",
    "content_draft": "content",
    "map_weather": "map",
    "user_profile": "content",
}

INTENT_TO_DELEGATION = {
    "order.search": "order",
    "order.create": "order",
    "order.manage": "order",
    "content.search": "content",
    "content.create": "content",
    "content.interact": "content",
    "map.search": "map",
    "weather.query": "map",
    "user.profile": "content",
}

DOMAIN_TO_DELEGATION = {
    "order": "order",
    "content": "content",
    "map": "map",
    "weather": "map",
    "user": "content",
}

DELEGATION_AGENT_ORDER = ("order", "content", "map")
MAX_EXTRACTED_MEMORIES_PER_TURN = 2

MEMORY_STRICT_TRANSIENT_MARKERS = (
    "坐标", "经纬度", "地图", "导航", "路线", "草稿", "尚未提供", "工具返回", "查询结果", "搜索结果"
)
MEMORY_SOFT_TRANSIENT_MARKERS = (
    "当前", "目前", "这次", "本次", "此次", "刚才", "刚刚", "今天", "今晚", "明天", "后天",
    "正在", "查询", "搜索", "寻找", "想找", "想要找", "附近", "周边", "这家", "店铺", "会所"
)
MEMORY_DURABLE_MARKERS = (
    "喜欢", "偏好", "倾向", "习惯", "经常", "常去", "不喜欢", "讨厌", "过敏", "默认",
    "以后", "长期", "就读", "住在", "不吃", "爱吃", "常吃"
)
MEMORY_STABLE_FACT_MARKERS = (
    "专业", "年级", "学院", "学校", "校区", "来自", "手机号", "邮箱"
)
MEMORY_ONE_OFF_PREFIXES = (
    "用户想", "用户正在", "用户需要", "用户询问", "用户查找", "用户搜索", "用户提供", "用户计划", "用户准备"
)
MEMORY_NO_SIGNAL_MARKERS = (
    "none", "没有提取到", "没有值得提取", "没有可提取", "无事实", "无明确事实", "无可记忆",
    "不明确", "无法判断", "无法确定", "测试系统反应", "习惯性输入错误"
)
MEMORY_LOW_CONFIDENCE_MARKERS = (
    "可能", "疑似", "似乎", "大概", "也许", "猜测", "推测", "不确定"
)
MEMORY_COORDINATE_RE = re.compile(r"\d{2,3}\.\d{3,}\s*[,，]\s*\d{1,3}\.\d{3,}")

INTENT_ANALYSIS_PROMPT = """你是 CampusHub 的意图分析智能体。请基于用户消息、最近对话和用户信息判断请求类型。

要求：
- 不要依赖单纯关键词匹配，要理解语义。
- 只输出 JSON，不要输出 Markdown 或解释。
- 写操作包括：创建订单、发布动态、评论、点赞/取消点赞、报名、撤销报名/申请、接受/拒绝申请、完成订单、删除内容。
- 只读操作包括：搜索、查看、查询、推荐、解释、路线/天气/地点查询。
- 如果是写操作但用户还没有确认或缺少关键字段，requires_confirmation 必须为 true。

JSON 字段：
{{
  "primary_intent": "order.search|order.create|order.manage|content.search|content.create|content.interact|map.search|weather.query|user.profile|memory.manage|chat.general|multi_step|unknown",
  "domain": "order|content|map|weather|user|memory|general|multi",
  "operation_type": "read|write|mixed|unknown",
  "requires_confirmation": true,
  "confidence": 0.0,
  "summary": "一句话描述用户想做什么",
  "missing_slots": ["缺失的关键信息"],
  "suggested_agents": ["order_query|order_draft|content_query|content_draft|map_weather|user_profile|memory|general"],
  "next_action": "direct_answer|ask_clarification|prepare_draft|execute_read_tools|wait_confirmation"
}}

当前用户信息：
{user_info}

用户长期记忆：
{memories}

最近对话：
{history}

本轮用户消息：
{user_message}
"""

DEFAULT_INTENT_ANALYSIS = {
    "primary_intent": "unknown",
    "domain": "general",
    "operation_type": "unknown",
    "requires_confirmation": True,
    "confidence": 0.0,
    "summary": "",
    "missing_slots": [],
    "suggested_agents": ["general"],
    "next_action": "ask_clarification",
}

INTENT_SEMANTIC_ROUTING_GUIDE = """
Additional semantic routing guide:
- A request to find, recommend, compare, route to, or look up stores/venues/places is a map.search read task, even when the user mentions a group size, time, budget, or says they want to go together.
- If the user explicitly says they are not looking for stores/places and instead want people, partners, classmates, or "搭子", classify as order.search/read.
- If the user asks to first inspect places/options and only later invite people, organize, publish, or create an activity, classify as multi_step/mixed with next_action=execute_read_tools. Do not jump directly to a write confirmation before the read step.
- If the latest message edits a previous order/content confirmation draft, preserve the original create action from context. Editing an order draft is order.create, not order.manage.
- "主页", "个人主页", "资料", "号同学", or asking what a user has posted means user.profile/read.
- "记住", "以后推荐时记得", "以后/下次/今后 + 优先/偏好/记得", or durable preference updates mean memory.manage/write and domain=memory.
- Weather-based planning such as "如果下雨我就改室内" is still weather.query/read unless the user asks CampusHub to create, publish, update, or apply for something.
- Do not turn a recommendation/search request into content.create or order.create unless the user explicitly asks to publish, create, invite, organize, post, or place an order/activity in CampusHub.
- For "我想要找3个人一起去洗脚按摩，有什么推荐的店吗", classify as:
  {"primary_intent":"map.search","domain":"map","operation_type":"read","requires_confirmation":false,"confidence":0.9,"summary":"用户想查询并推荐适合多人前往的足疗按摩店","missing_slots":[],"suggested_agents":["map_weather"],"next_action":"execute_read_tools"}
- For "附近有没有适合三个人吃饭的店", classify as map.search/read.
- For "我不是找店，想看看今晚有没有人一起打羽毛球", classify as order.search/read.
- For "先看看附近安静咖啡馆，如果环境合适我再约几个人去自习", classify as multi_step/mixed and run read tools first.
- For "明晚操场会不会不太适合跑步，要是下雨我就改室内", classify as weather.query/read.
- For "帮我发个动态找三个人一起去按摩", classify as content.create/write and require confirmation.
- For "帮我创建一个三人按摩约伴订单", classify as order.create/write and require confirmation.
- If the latest user message is editing an existing draft, keep the domain/action of that draft from recent context and use requires_confirmation=true.
"""

INTENT_ROUTER_PROMPT_V2 = """
You are the CampusHub semantic intent router. Classify the user's latest request from meaning and recent context, not from simple keyword matching.

Return JSON only. Do not use Markdown. The JSON schema is:
{
  "primary_intent": "order.search|order.create|order.manage|content.search|content.create|content.interact|map.search|weather.query|user.profile|memory.manage|chat.general|multi_step|unknown",
  "domain": "order|content|map|weather|user|memory|general|multi",
  "operation_type": "read|write|mixed|unknown",
  "requires_confirmation": true,
  "confidence": 0.0,
  "summary": "one short Chinese sentence",
  "missing_slots": [],
  "suggested_agents": ["order_query|order_draft|content_query|content_draft|map_weather|user_profile|memory|general"],
  "next_action": "direct_answer|ask_clarification|prepare_draft|execute_read_tools|wait_confirmation"
}

Decision principles:
- Read tasks: search, browse, view, explain, recommend, compare, route planning, weather, place/store lookup. Execute read tools without confirmation.
- Write tasks: create/publish/edit/delete/comment/like/apply/cancel application/accept/reject/complete/order/sign up. They require a confirmation draft before any database write.
- A recommendation for stores, venues, routes, or nearby places is map.search/read, even if the user mentions people count, time, budget, or "一起".
- If the user says they are not looking for a store/place and wants people/classmates/partners instead, choose order.search/read.
- Only classify as content.create/order.create when the user explicitly asks CampusHub to publish/create/organize/post an activity/order/dynamic.
- If the user is editing a previous draft, preserve the draft's domain/action from context and require confirmation.
- Editing a previous order creation draft remains order.create, not order.manage.
- Asking to remember a durable preference is memory.manage/write with domain=memory.
- Asking to view a user's homepage/profile or posted content is user.profile/read.
- Weather or suitability questions remain weather.query/read when the user is only deciding their own plan, even if they mention a fallback like "改室内".

High-priority examples:
User: 我想要找3个人一起去洗脚按摩，有什么推荐的店吗
Output: {"primary_intent":"map.search","domain":"map","operation_type":"read","requires_confirmation":false,"confidence":0.92,"summary":"用户想查询并推荐适合多人前往的足疗按摩店","missing_slots":[],"suggested_agents":["map_weather"],"next_action":"execute_read_tools"}

User: 帮我看看良乡校区今天有没有篮球约伴活动
Output: {"primary_intent":"order.search","domain":"order","operation_type":"read","requires_confirmation":false,"confidence":0.92,"summary":"用户想搜索今天良乡校区的篮球约伴活动","missing_slots":[],"suggested_agents":["order_query"],"next_action":"execute_read_tools"}

User: 附近有没有适合三个人吃饭的店
Output: {"primary_intent":"map.search","domain":"map","operation_type":"read","requires_confirmation":false,"confidence":0.9,"summary":"用户想查找适合三人就餐的附近餐厅","missing_slots":[],"suggested_agents":["map_weather"],"next_action":"execute_read_tools"}

User: 帮我发个动态找三个人一起去按摩
Output: {"primary_intent":"content.create","domain":"content","operation_type":"write","requires_confirmation":true,"confidence":0.92,"summary":"用户想发布一条寻找同伴的校园动态","missing_slots":[],"suggested_agents":["content_draft"],"next_action":"prepare_draft"}

User: 帮我创建一个三人按摩约伴订单
Output: {"primary_intent":"order.create","domain":"order","operation_type":"write","requires_confirmation":true,"confidence":0.9,"summary":"用户想创建三人按摩约伴订单","missing_slots":["地点","时间"],"suggested_agents":["order_draft"],"next_action":"ask_clarification"}

User: 帮我创建一个明晚7点良乡体育馆的篮球约伴，最多4个人，男女不限
Output: {"primary_intent":"order.create","domain":"order","operation_type":"write","requires_confirmation":true,"confidence":0.92,"summary":"用户想创建一个信息较完整的篮球约伴活动草稿","missing_slots":[],"suggested_agents":["order_draft"],"next_action":"prepare_draft"}

User: 先帮我找附近适合三个人吃饭的地方，如果不错再帮我创建约饭订单
Output: {"primary_intent":"multi_step","domain":"multi","operation_type":"mixed","requires_confirmation":true,"confidence":0.9,"summary":"用户想先查询适合三人吃饭的地点，再基于结果创建约饭订单草稿","missing_slots":[],"suggested_agents":["map_weather","order_draft"],"next_action":"execute_read_tools"}

User: 我不是找店，想看看今晚有没有人一起打羽毛球
Output: {"primary_intent":"order.search","domain":"order","operation_type":"read","requires_confirmation":false,"confidence":0.9,"summary":"用户想查询今晚可一起打羽毛球的约伴机会","missing_slots":[],"suggested_agents":["order_query"],"next_action":"execute_read_tools"}

User: 先看看附近安静咖啡馆，如果环境合适我再约几个人去自习
Output: {"primary_intent":"multi_step","domain":"multi","operation_type":"mixed","requires_confirmation":true,"confidence":0.9,"summary":"用户想先查询适合自习的咖啡馆，再根据结果决定是否组织约伴","missing_slots":[],"suggested_agents":["map_weather","order_draft"],"next_action":"execute_read_tools"}

User: 那个 12 号同学的主页给我瞅瞅，他以前发过啥
Output: {"primary_intent":"user.profile","domain":"user","operation_type":"read","requires_confirmation":false,"confidence":0.88,"summary":"用户想查看指定同学主页和历史内容","missing_slots":[],"suggested_agents":["user_profile"],"next_action":"execute_read_tools"}

User: 以后推荐吃饭的地方时记得我不吃辣
Output: {"primary_intent":"memory.manage","domain":"memory","operation_type":"write","requires_confirmation":true,"confidence":0.9,"summary":"用户想让 AI 记住饮食偏好","missing_slots":[],"suggested_agents":["memory"],"next_action":"prepare_draft"}

User: 明晚操场会不会不太适合跑步，要是下雨我就改室内
Output: {"primary_intent":"weather.query","domain":"weather","operation_type":"read","requires_confirmation":false,"confidence":0.9,"summary":"用户想查询天气并判断是否适合户外跑步","missing_slots":[],"suggested_agents":["map_weather"],"next_action":"execute_read_tools"}

Previous router analysis:
{previous_analysis}

User info:
{user_info}

Long-term memories:
{memories}

Recent conversation:
{history}

Current user message:
{user_message}
"""

INTENT_REVIEW_PROMPT = """You are the senior intent-review agent for CampusHub. The fast router may miss write operations, so review the request semantically.

Rules:
- Do not rely on simple keyword matching. Infer the user's real goal from the message and recent context.
- If the user wants the system to create, publish, edit, delete, comment, like, apply, cancel/withdraw an application, accept, reject, or complete something, classify it as write or mixed.
- A write classification does not mean immediate execution. If enough information is present, use next_action=prepare_draft and requires_confirmation=true. If required fields are missing, use next_action=ask_clarification and requires_confirmation=true.
- If one request combines read-first work with a possible later create/publish/apply action, classify it as mixed and keep requires_confirmation=true.
- Read-only search, browse, explain, recommend, route, weather, and place lookup tasks are read operations.
- If the user is not looking for stores/places and instead wants people, classmates, partners, or "搭子", classify as order.search/read.
- If the user is editing a previous creation draft, preserve the original create action from context. Do not convert draft edits into order.manage.
- Durable preference updates such as "以后推荐时记得..." or "以后...优先给我推荐..." are memory.manage/write with domain=memory.
- Homepage/profile requests are user.profile/read, even when the user asks what that person has posted.
- Weather suitability and personal fallback planning are weather.query/read unless the user asks CampusHub to modify or create a platform object.
- Return JSON only. No Markdown. No explanation.

Examples:
User: 帮我发布一条动态：今天下午一起去图书馆自习，欢迎同学加入。
Output: {{"primary_intent":"content.create","domain":"content","operation_type":"write","requires_confirmation":true,"confidence":0.95,"summary":"用户想发布一条校园动态","missing_slots":[],"suggested_agents":["content_draft"],"next_action":"prepare_draft"}}

User: 帮我创建一个明天下午三点的篮球活动
Output: {{"primary_intent":"order.create","domain":"order","operation_type":"write","requires_confirmation":true,"confidence":0.9,"summary":"用户想创建约伴活动","missing_slots":["地点","参与人数"],"suggested_agents":["order_draft"],"next_action":"ask_clarification"}}

User: 帮我创建一个明晚7点良乡体育馆的篮球约伴，最多4个人，男女不限
Output: {{"primary_intent":"order.create","domain":"order","operation_type":"write","requires_confirmation":true,"confidence":0.92,"summary":"用户想创建一个信息较完整的篮球约伴活动草稿","missing_slots":[],"suggested_agents":["order_draft"],"next_action":"prepare_draft"}}

User: 先帮我找附近适合三个人吃饭的地方，如果不错再帮我创建约饭订单
Output: {{"primary_intent":"multi_step","domain":"multi","operation_type":"mixed","requires_confirmation":true,"confidence":0.9,"summary":"用户想先查询适合三人吃饭的地点，再基于结果创建约饭订单草稿","missing_slots":[],"suggested_agents":["map_weather","order_draft"],"next_action":"execute_read_tools"}}

User: 帮我找附近的篮球场
Output: {{"primary_intent":"map.search","domain":"map","operation_type":"read","requires_confirmation":false,"confidence":0.9,"summary":"用户想查询附近篮球场","missing_slots":[],"suggested_agents":["map_weather"],"next_action":"execute_read_tools"}}

User: 帮我看看良乡校区今天有没有篮球约伴活动
Output: {{"primary_intent":"order.search","domain":"order","operation_type":"read","requires_confirmation":false,"confidence":0.92,"summary":"用户想搜索今天良乡校区的篮球约伴活动","missing_slots":[],"suggested_agents":["order_query"],"next_action":"execute_read_tools"}}

User: 我想要找3个人一起去洗脚按摩，有什么推荐的店吗
Output: {{"primary_intent":"map.search","domain":"map","operation_type":"read","requires_confirmation":false,"confidence":0.92,"summary":"用户想查询并推荐适合多人前往的足疗按摩店","missing_slots":[],"suggested_agents":["map_weather"],"next_action":"execute_read_tools"}}

User: 帮我发个动态找三个人一起去按摩
Output: {{"primary_intent":"content.create","domain":"content","operation_type":"write","requires_confirmation":true,"confidence":0.92,"summary":"用户想发布一条寻找同伴的校园动态","missing_slots":[],"suggested_agents":["content_draft"],"next_action":"prepare_draft"}}

User: 我不是找店，想看看今晚有没有人一起打羽毛球
Output: {{"primary_intent":"order.search","domain":"order","operation_type":"read","requires_confirmation":false,"confidence":0.9,"summary":"用户想查询今晚可一起打羽毛球的约伴机会","missing_slots":[],"suggested_agents":["order_query"],"next_action":"execute_read_tools"}}

User: 先看看附近安静咖啡馆，如果环境合适我再约几个人去自习
Output: {{"primary_intent":"multi_step","domain":"multi","operation_type":"mixed","requires_confirmation":true,"confidence":0.9,"summary":"用户想先查询适合自习的咖啡馆，再根据结果决定是否组织约伴","missing_slots":[],"suggested_agents":["map_weather","order_draft"],"next_action":"execute_read_tools"}}

User: 那个 12 号同学的主页给我瞅瞅，他以前发过啥
Output: {{"primary_intent":"user.profile","domain":"user","operation_type":"read","requires_confirmation":false,"confidence":0.88,"summary":"用户想查看指定同学主页和历史内容","missing_slots":[],"suggested_agents":["user_profile"],"next_action":"execute_read_tools"}}

User: 以后推荐吃饭的地方时记得我不吃辣
Output: {{"primary_intent":"memory.manage","domain":"memory","operation_type":"write","requires_confirmation":true,"confidence":0.9,"summary":"用户想让 AI 记住饮食偏好","missing_slots":[],"suggested_agents":["memory"],"next_action":"prepare_draft"}}

User: 明晚操场会不会不太适合跑步，要是下雨我就改室内
Output: {{"primary_intent":"weather.query","domain":"weather","operation_type":"read","requires_confirmation":false,"confidence":0.9,"summary":"用户想查询天气并判断是否适合户外跑步","missing_slots":[],"suggested_agents":["map_weather"],"next_action":"execute_read_tools"}}

JSON fields:
{{
  "primary_intent": "order.search|order.create|order.manage|content.search|content.create|content.interact|map.search|weather.query|user.profile|memory.manage|chat.general|multi_step|unknown",
  "domain": "order|content|map|weather|user|memory|general|multi",
  "operation_type": "read|write|mixed|unknown",
  "requires_confirmation": true,
  "confidence": 0.0,
  "summary": "one-sentence summary",
  "missing_slots": ["missing fields"],
  "suggested_agents": ["order_query|order_draft|content_query|content_draft|map_weather|user_profile|memory|general"],
  "next_action": "direct_answer|ask_clarification|prepare_draft|execute_read_tools|wait_confirmation"
}}

Fast router first pass:
{previous_analysis}

User info:
{user_info}

Long-term memories:
{memories}

Recent conversation:
{history}

Current user message:
{user_message}
"""

DRAFT_CONFIRMATION_PROMPT = """你是 CampusHub 的写操作安全确认智能体。用户想执行写操作时，请把本轮请求整理成确认草稿。

要求：
- 只输出 JSON，不要输出 Markdown 或解释。
- 不要调用工具，不要假装已经创建、发布、点赞、报名或删除。
- 如果缺少必要信息，请在 missing_fields 中列出，并让 reply 询问用户补充。
- 如果信息足够，请让 reply 请求用户确认后再执行。

JSON 字段：
{{
  "title": "确认发布篮球约伴活动",
  "description": "一句话描述将要执行的操作",
  "action_kind": "order.create|content.create|content.comment|content.like|order.apply|order.cancel_apply|order.accept|order.reject_apply|order.complete|other.write",
  "fields": [
    {{"label": "字段名", "value": "字段值"}}
  ],
  "missing_fields": ["缺失字段"],
  "reply": "面向用户的确认或追问信息"
}}

意图分析：
{intent_analysis}

当前用户信息：
{user_info}

最近对话：
{history}

本轮用户消息：
{user_message}
"""

# ==================== 工具分组 ====================

DRAFT_CONFIRMATION_PROMPT = """You are CampusHub's write-operation confirmation agent. Convert the current user request into a confirmation draft card.

Rules:
- Return JSON only. No Markdown. No explanation.
- Do not call tools and do not claim that data has already been created, published, liked, applied, canceled, accepted, rejected, completed, or deleted.
- The title must match the actual action_kind and current user request. Do not copy example titles.
- For action_kind=content.create, use a title like "确认发布动态".
- For action_kind=order.create, use a title like "确认创建约伴活动".
- For action_kind=order.cancel_apply, use a title like "确认撤销报名申请" and include 订单ID.
- For action_kind=order.reject_apply, use a title like "确认拒绝订单申请" and include 申请ID.
- For action_kind=memory.manage, use a title like "确认保存长期记忆" or "确认删除长期记忆".
- For action_kind=memory.manage, include fields: 记忆操作(save/delete), 记忆分类(preference/fact/behavior), 记忆内容.
- For canceling an entire order/activity, use action_kind=other.write unless an explicit order cancellation tool is available.
- If required information is missing, list it in missing_fields and make reply ask the user to complete it.
- If enough information is present, make reply ask the user to confirm before execution.

Return this JSON shape:
{{
  "title": "确认发布动态",
  "description": "one sentence describing the pending write operation",
  "action_kind": "order.create|content.create|content.comment|content.like|order.apply|order.cancel_apply|order.accept|order.reject_apply|order.complete|memory.manage|other.write",
  "fields": [
    {{"label": "字段名", "value": "字段值"}}
  ],
  "missing_fields": ["缺失字段"],
  "reply": "message shown to the user"
}}

Intent analysis:
{intent_analysis}

User info:
{user_info}

Recent conversation:
{history}

Current user message:
{user_message}
"""

ORDER_TOOLS = [search_orders, create_order, get_my_orders, get_order_detail, *ORDER_EXTRA_TOOLS]
SOCIAL_TOOLS = [*CONTENT_TOOLS, *USER_TOOLS]
MAP_TOOLS = [*MCP_TOOLS, *UTIL_TOOLS]


# ==================== LLM 工厂 ====================

def _get_llm(streaming: bool = False, temperature: float = 0.7, max_tokens: int = 2048) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=SILICONFLOW_API_KEY,
        base_url=SILICONFLOW_BASE_URL,
        model=SILICONFLOW_MODEL,
        temperature=temperature,
        streaming=streaming,
        max_tokens=max_tokens,
        extra_body={"enable_thinking": False},
    )


def _get_router_llm() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=SILICONFLOW_API_KEY,
        base_url=SILICONFLOW_BASE_URL,
        model=SILICONFLOW_ROUTER_MODEL,
        temperature=0,
        streaming=False,
        max_tokens=700,
        extra_body={"enable_thinking": False},
    )


def _json_data(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


async def _emit_event(event: str, payload: dict):
    sink = _event_sink.get()
    if sink:
        await sink({"event": event, "data": _json_data(payload)})


def _consume_background_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except BaseException:
        pass


async def _await_with_soft_timeout(coro, timeout_seconds: float):
    task = asyncio.create_task(coro)
    done, _ = await asyncio.wait({task}, timeout=timeout_seconds)
    if task in done:
        return task.result()
    task.cancel()
    task.add_done_callback(_consume_background_task_result)
    raise asyncio.TimeoutError()


def _normalize_delegation_task(task: str) -> str:
    normalized = " ".join(str(task or "").split()).lower()
    return normalized[:500]


DELEGATION_CONCEPT_ALIASES = {
    "search": ("搜索", "查找", "查询", "推荐", "找", "看看", "看下", "看一下", "search", "find", "recommend"),
    "create": ("创建", "新建", "生成", "整理", "草稿", "发起", "create", "draft"),
    "nearby": ("附近", "周边", "附近的", "周围", "周边的", "nearby", "near", "around"),
    "liangxiang": ("良乡", "良乡校区", "北理良乡", "北京理工大学良乡", "bit liangxiang"),
    "zhongguancun": ("中关村", "中关村校区"),
    "map_place": ("地图", "地点", "店", "店铺", "门店", "商家", "位置", "地址", "路线", "经纬度", "map", "place", "shop", "store"),
    "massage": ("按摩", "足疗", "洗脚", "spa", "massage"),
    "restaurant": ("餐厅", "吃饭", "约饭", "烤肉", "火锅", "咖啡", "奶茶", "restaurant", "bbq", "cafe"),
    "basketball": ("篮球", "basketball"),
    "badminton": ("羽毛球", "badminton"),
    "running": ("跑步", "操场", "running"),
    "study": ("自习", "图书馆", "教室", "study"),
    "weather": ("天气", "下雨", "温度", "weather"),
    "order": ("订单", "约伴", "活动", "报名", "加入", "order", "activity"),
    "content": ("动态", "帖子", "评论", "点赞", "发布", "content", "post"),
}


def _delegation_task_concepts(task: str) -> set[str]:
    normalized = _normalize_delegation_task(task)
    if not normalized:
        return set()

    concepts: set[str] = set()
    for concept, aliases in DELEGATION_CONCEPT_ALIASES.items():
        if any(alias.lower() in normalized for alias in aliases):
            concepts.add(concept)

    ids = re.findall(r"(?:订单|动态|内容|用户|order|content|user)[#:\s]*([0-9]+)", normalized, flags=re.IGNORECASE)
    concepts.update(f"id:{item}" for item in ids[:3])

    dates = re.findall(r"\b(?:20\d{2}[-/年])?\d{1,2}[-/月]\d{1,2}", normalized)
    concepts.update(f"date:{item}" for item in dates[:2])

    times = re.findall(r"\b\d{1,2}[:：]\d{2}\b", normalized)
    concepts.update(f"time:{item}" for item in times[:2])
    return concepts


def _build_delegation_signature(agent_key: str, task: str) -> dict | None:
    concepts = _delegation_task_concepts(task)
    if len(concepts) < 3:
        return None
    return {
        "agent": agent_key,
        "concepts": sorted(concepts),
    }


def _delegation_signature_similarity(left: dict | None, right: dict | None) -> float:
    if not left or not right or left.get("agent") != right.get("agent"):
        return 0.0
    left_concepts = set(left.get("concepts") or [])
    right_concepts = set(right.get("concepts") or [])
    if len(left_concepts) < 3 or len(right_concepts) < 3:
        return 0.0
    union = left_concepts | right_concepts
    if not union:
        return 0.0
    return len(left_concepts & right_concepts) / len(union)


def _find_semantic_delegation_reuse(state: dict, signature: dict | None) -> dict | None:
    if not signature:
        return None
    for entry in state.setdefault("semantic_results", {}).values():
        similarity = _delegation_signature_similarity(signature, entry.get("signature"))
        if similarity >= 0.72:
            return {**entry, "similarity": similarity}
    return None


def _build_allowed_delegation_agents(intent_analysis: dict) -> set[str] | None:
    if not isinstance(intent_analysis, dict):
        return None

    suggested_allowed: set[str] = set()
    suggested_agents = intent_analysis.get("suggested_agents")
    if isinstance(suggested_agents, list):
        for item in suggested_agents:
            mapped = AGENT_SUGGESTION_TO_DELEGATION.get(str(item or "").strip().lower())
            if mapped:
                suggested_allowed.add(mapped)

    base_allowed: set[str] = set()
    primary_intent = str(intent_analysis.get("primary_intent") or "").strip().lower()
    mapped = INTENT_TO_DELEGATION.get(primary_intent)
    if mapped:
        base_allowed.add(mapped)

    domain = str(intent_analysis.get("domain") or "").strip().lower()
    mapped = DOMAIN_TO_DELEGATION.get(domain)
    if mapped:
        base_allowed.add(mapped)

    operation_type = str(intent_analysis.get("operation_type") or "").strip().lower()
    is_multi_step = primary_intent == "multi_step" or domain == "multi" or operation_type == "mixed"
    if is_multi_step:
        return suggested_allowed or base_allowed or None

    # For a single-domain turn, the semantic intent/domain are the contract.
    # A noisy suggested_agents list must not let the orchestrator drift into an
    # unrelated expert and recreate the "map request becomes post/order draft"
    # failure mode.
    if base_allowed:
        return base_allowed

    return suggested_allowed or None


def _get_delegation_state() -> dict:
    state = _delegation_state.get()
    if state is None:
        state = {
            "total": 0,
            "counts": {},
            "results": {},
            "semantic_results": {},
        }
        _delegation_state.set(state)
    state.setdefault("semantic_results", {})
    return state


async def _run_guarded_sub_agent(
    agent_key: str,
    agent_name: str,
    system_prompt: str,
    tools: list,
    task: str,
) -> str:
    state = _get_delegation_state()
    fingerprint = f"{agent_key}:{_normalize_delegation_task(task)}"
    semantic_signature = _build_delegation_signature(agent_key, task)
    allowed_agents = _allowed_delegation_agents.get()

    if allowed_agents and agent_key not in allowed_agents:
        allowed_label = "、".join(sorted(allowed_agents))
        await _emit_event("agent_step", {
            "phase": "delegation_guard",
            "agent": agent_key,
            "title": f"{agent_name}不在本轮执行计划",
            "detail": f"意图分析仅允许调用：{allowed_label}。已拦截本次越界委派，避免主智能体偏离原任务。",
            "state": "failed",
        })
        return f"{agent_name}不在本轮意图分析允许的专家范围内。请改用已允许的专家，或向用户追问补充信息。"

    if fingerprint in state["results"]:
        await _emit_event("agent_step", {
            "phase": "delegation_guard",
            "agent": agent_key,
            "title": f"{agent_name}复用已有结果",
            "detail": "检测到同一轮中重复委派了相同任务，已复用上一次结果以避免循环调用",
            "state": "completed",
        })
        return state["results"][fingerprint]

    semantic_reuse = _find_semantic_delegation_reuse(state, semantic_signature)
    if semantic_reuse:
        await _emit_event("agent_step", {
            "phase": "delegation_guard",
            "agent": agent_key,
            "title": f"{agent_name}复用相近任务结果",
            "detail": f"检测到同一轮中语义相近的重复委派，已复用已有结果以避免循环调用（相似度 {semantic_reuse['similarity']:.0%}）",
            "state": "completed",
        })
        state["results"][fingerprint] = semantic_reuse["result"]
        return semantic_reuse["result"]

    agent_count = state["counts"].get(agent_key, 0)
    if state["total"] >= MAX_MAIN_DELEGATIONS:
        await _emit_event("agent_step", {
            "phase": "delegation_guard",
            "agent": agent_key,
            "title": "已达到本轮委派上限",
            "detail": "为避免智能体循环委派，本轮不再继续调用新的子智能体",
            "state": "failed",
        })
        return "已达到本轮智能体委派上限。请基于已经获得的工具结果回复用户，或说明还需要用户补充信息。"

    if agent_count >= MAX_DELEGATIONS_PER_AGENT:
        await _emit_event("agent_step", {
            "phase": "delegation_guard",
            "agent": agent_key,
            "title": f"{agent_name}调用次数受限",
            "detail": "同一轮中该专家已被多次调用，为避免循环委派，本次调用被拦截",
            "state": "failed",
        })
        return f"{agent_name}在本轮已达到调用次数上限。请不要继续重复委派该专家，改为总结已有结果或向用户追问。"

    state["total"] += 1
    state["counts"][agent_key] = agent_count + 1
    result = await _run_sub_agent(agent_key, agent_name, system_prompt, tools, task)
    state["results"][fingerprint] = result
    if semantic_signature:
        semantic_key = hashlib.sha1(
            json.dumps(semantic_signature, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        state["semantic_results"][semantic_key] = {
            "signature": semantic_signature,
            "result": result,
            "task": task,
        }
    return result


def _safe_json_loads(text: str) -> dict:
    cleaned = (text or "").strip()
    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start:end + 1]
    parsed = json.loads(cleaned)
    return parsed if isinstance(parsed, dict) else {}


def _render_intent_prompt(
    previous_analysis,
    user_info: dict,
    memories: list,
    history: list,
    user_message: str,
) -> str:
    replacements = {
        "{previous_analysis}": json.dumps(previous_analysis or {}, ensure_ascii=False)
        if previous_analysis is not None else "null",
        "{user_info}": json.dumps(user_info or {}, ensure_ascii=False),
        "{memories}": json.dumps(memories or [], ensure_ascii=False),
        "{history}": json.dumps((history or [])[-8:], ensure_ascii=False),
        "{user_message}": user_message,
    }
    prompt = INTENT_REVIEW_PROMPT if previous_analysis is not None else INTENT_ROUTER_PROMPT_V2
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)
    return prompt + "\n\n" + INTENT_SEMANTIC_ROUTING_GUIDE


def _intent_cache_key(user_info: dict, memories: list, history: list, user_message: str) -> str:
    payload = {
        "uid": (user_info or {}).get("uid"),
        "campus": (user_info or {}).get("campus"),
        "message": " ".join(str(user_message or "").split()),
        "history": (history or [])[-6:],
        "memories": [
            {
                "category": item.get("category"),
                "content": item.get("content"),
            }
            for item in (memories or [])[-8:]
            if isinstance(item, dict)
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _copy_intent(value: dict) -> dict:
    return json.loads(json.dumps(value or {}, ensure_ascii=False))


def _get_cached_intent(cache_key: str) -> dict | None:
    entry = _intent_cache.get(cache_key)
    if not entry:
        return None
    created_at, analysis = entry
    if time.time() - created_at > INTENT_CACHE_TTL_SECONDS:
        _intent_cache.pop(cache_key, None)
        return None
    _intent_cache.move_to_end(cache_key)
    cached = _copy_intent(analysis)
    cached["cache_hit"] = True
    return cached


def _store_intent(cache_key: str, analysis: dict) -> None:
    cache_value = _copy_intent(analysis)
    cache_value.pop("cache_hit", None)
    _intent_cache[cache_key] = (time.time(), cache_value)
    _intent_cache.move_to_end(cache_key)
    while len(_intent_cache) > INTENT_CACHE_MAX_SIZE:
        _intent_cache.popitem(last=False)


def _normalize_intent_analysis(value: dict) -> dict:
    result = dict(DEFAULT_INTENT_ANALYSIS)
    result.update({k: v for k, v in (value or {}).items() if v is not None})
    if not isinstance(result.get("missing_slots"), list):
        result["missing_slots"] = []
    if not isinstance(result.get("suggested_agents"), list):
        result["suggested_agents"] = ["general"]
    try:
        result["confidence"] = float(result.get("confidence", 0))
    except (TypeError, ValueError):
        result["confidence"] = 0.0
    result["requires_confirmation"] = bool(result.get("requires_confirmation", True))
    primary_intent = (result.get("primary_intent") or "").lower()
    operation_type = (result.get("operation_type") or "").lower()
    next_action = (result.get("next_action") or "").lower()
    intent_domains = {
        "order.search": "order",
        "order.create": "order",
        "order.manage": "order",
        "content.search": "content",
        "content.create": "content",
        "content.interact": "content",
        "map.search": "map",
        "weather.query": "weather",
        "user.profile": "user",
        "memory.manage": "memory",
        "multi_step": "multi",
        "chat.general": "general",
    }
    intent_agents = {
        "order.search": ["order_query"],
        "order.create": ["order_draft"],
        "order.manage": ["order_draft"],
        "content.search": ["content_query"],
        "content.create": ["content_draft"],
        "content.interact": ["content_draft"],
        "map.search": ["map_weather"],
        "weather.query": ["map_weather"],
        "user.profile": ["user_profile"],
        "memory.manage": ["memory"],
        "multi_step": ["map_weather", "order_draft"],
        "chat.general": ["general"],
    }
    if primary_intent in intent_domains:
        result["domain"] = intent_domains[primary_intent]
        if not result.get("suggested_agents") or result.get("suggested_agents") == ["general"]:
            result["suggested_agents"] = intent_agents[primary_intent]
    if operation_type in {"write", "mixed"} and next_action in {"ask_clarification", "prepare_draft", "wait_confirmation"}:
        result["requires_confirmation"] = True
    if (
        operation_type in {"write", "mixed"}
        and next_action == "ask_clarification"
        and not result.get("missing_slots")
        and primary_intent in {"order.create", "order.manage", "content.create", "content.interact", "memory.manage"}
    ):
        result["next_action"] = "prepare_draft"
    return result


def _looks_like_read_then_write_request(user_message: str, analysis: dict) -> bool:
    # This only triggers a senior-model review; it is not the final intent classifier.
    text = " ".join(str(user_message or "").split()).lower()
    if not text:
        return False
    if _has_any(text, ("如果还缺少", "如果缺少", "缺少必要信息", "请先让我补充", "先让我补充")):
        return False
    operation_type = (analysis.get("operation_type") or "").lower()
    if operation_type in {"write", "mixed"}:
        return False
    read_cues = ("先", "找", "推荐", "看看", "查询", "附近", "有没有")
    transition_cues = ("再", "然后", "之后", "如果", "合适", "不错")
    write_cues = (
        "创建",
        "新建",
        "建一个",
        "建个",
        "建活动",
        "建订单",
        "发布",
        "发个动态",
        "发一条",
        "报名",
        "申请加入",
        "下单",
        "约饭订单",
        "约伴订单",
        "发起",
        "组织",
        "约人",
        "约几个",
        "约几个人",
        "约同学",
        "拉几个人",
    )
    return (
        any(cue in text for cue in read_cues)
        and any(cue in text for cue in transition_cues)
        and any(cue in text for cue in write_cues)
    )


def _map_selection_index(text: str) -> int | None:
    text = " ".join(str(text or "").split()).lower()
    if not text:
        return None
    selection_rules = [
        (("第三家", "第三个", "第3家", "第3个", "3号", "第三"), 2),
        (("第二家", "第二个", "第2家", "第2个", "2号", "第二"), 1),
        (("第一家", "第一个", "第1家", "第1个", "1号", "第一", "首个"), 0),
        (("这家", "这个地点", "这个地方", "就这", "就它", "就这个", "刚才那个", "刚才这家"), 0),
    ]
    for cues, index in selection_rules:
        if _has_any(text, cues):
            return index
    return None


def _extract_recent_map_candidates(history: list) -> list[dict]:
    """Recover recent map candidates from assistant text so follow-up drafts keep place context."""
    candidates: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add_candidate(title: str, lng: str, lat: str) -> None:
        title = str(title or "").strip(" -:：，,。")
        coords = f"{lng}, {lat}" if lng and lat else ""
        if not title or not coords:
            return
        key = (title, coords)
        if key in seen:
            return
        seen.add(key)
        candidates.append({"title": title, "coords": coords})

    for item in reversed(history or []):
        if not isinstance(item, dict) or item.get("role") == "user":
            continue
        content = str(item.get("content") or "")
        if not content:
            continue

        for match in re.finditer(
            r":::map\{(?=[^}]*\blng=([0-9]{2,3}\.\d+))(?=[^}]*\blat=([0-9]{1,2}\.\d+))[^}]*\btitle=([^}\n\r]+)\}",
            content,
            flags=re.IGNORECASE,
        ):
            add_candidate(match.group(3), match.group(1), match.group(2))

        for match in re.finditer(
            r"(?:^|\n)\s*(?:\d{1,2}[.、]\s*)?([^\n\r:：。]{2,80}?)(?:地址[:：][^\n\r]*?)?经纬度[:：]\s*([0-9]{2,3}\.\d+)\s*[,，]\s*([0-9]{1,2}\.\d+)",
            content,
        ):
            add_candidate(match.group(1), match.group(2), match.group(3))

        if candidates:
            break
    return candidates[:5]


def _normalize_map_match_text(text: str) -> str:
    return re.sub(r"[\s\-_:：,，.。()（）【】\\[\\]「」\"'“”]+", "", str(text or "").lower())


def _map_candidate_title_aliases(title: str) -> list[str]:
    title = str(title or "").strip()
    if not title:
        return []

    aliases: list[str] = [title]
    for part in re.split(r"[()（）【】\\[\\]「」,，/／|｜\-—]+", title):
        part = part.strip()
        if len(part) >= 2:
            aliases.append(part)

    for alias in list(aliases):
        simplified = re.sub(
            r"(?:spa|会所|足道|按摩|推拿|养生|店|馆|餐厅|咖啡|影院|电影院|篮球场|体育馆)+$",
            "",
            alias,
            flags=re.IGNORECASE,
        ).strip()
        if len(simplified) >= 2:
            aliases.append(simplified)

    unique: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        normalized = _normalize_map_match_text(alias)
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(alias)
    return unique


def _match_recent_map_candidate_by_name(candidates: list[dict], user_message: str) -> dict | None:
    user_text = _normalize_map_match_text(user_message)
    if not user_text:
        return None

    scored: list[tuple[int, int, dict]] = []
    for index, candidate in enumerate(candidates or []):
        best_score = 0
        for alias in _map_candidate_title_aliases(str(candidate.get("title") or "")):
            normalized_alias = _normalize_map_match_text(alias)
            if normalized_alias and normalized_alias in user_text:
                best_score = max(best_score, len(normalized_alias))
        if best_score:
            scored.append((best_score, -index, candidate))

    if not scored:
        return None
    scored.sort(reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][2]


def _extract_contextual_map_selection(history: list, user_message: str) -> tuple[str, str]:
    title, coords = _extract_map_selection(user_message)
    if title or coords:
        return title, coords

    candidates = _extract_recent_map_candidates(history)
    selected_index = _map_selection_index(user_message)
    if selected_index is not None:
        if selected_index >= len(candidates):
            return "", ""
        candidate = candidates[selected_index]
        return candidate.get("title", ""), candidate.get("coords", "")

    candidate = _match_recent_map_candidate_by_name(candidates, user_message)
    if not candidate:
        return "", ""
    return candidate.get("title", ""), candidate.get("coords", "")


CONTENT_CREATE_CUES = (
    "发动态",
    "发条动态",
    "发布动态",
    "写动态",
    "写个动态",
    "动态草稿",
    "发帖",
    "写帖子",
    "写个帖子",
    "post",
)


def _detect_contextual_order_create_shortcut(history: list, user_message: str) -> dict | None:
    """Route follow-ups like '就第一家，帮我约三个人' to a safe order draft."""
    text = " ".join(str(user_message or "").split())
    if not text or _contains_blocking_write_negation(text):
        return None
    if _has_any(text.lower(), CONTENT_CREATE_CUES):
        return None
    title, coords = _extract_contextual_map_selection(history, text)
    has_contextual_map_selection = bool(title or coords)
    if not has_contextual_map_selection:
        return None

    write_cues = (
        "帮我约",
        "约人",
        "约几个",
        "约几个人",
        "找几个人",
        "叫几个人",
        "拉几个人",
        "创建",
        "发起",
        "组织",
        "约伴",
        "订单",
        "草稿",
    )
    if not _has_any(text, write_cues):
        return None

    missing_slots = []
    if not _looks_like_time_text(text):
        missing_slots.append("时间")
    if not _extract_group_size(text):
        missing_slots.append("参与人数")

    return {
        "primary_intent": "order.create",
        "domain": "order",
        "operation_type": "write",
        "requires_confirmation": True,
        "confidence": 0.9,
        "summary": "用户想基于上一轮地图候选创建约伴订单草稿",
        "missing_slots": missing_slots,
        "suggested_agents": ["order_draft"],
        "next_action": "ask_clarification" if missing_slots else "prepare_draft",
        "reviewed": False,
        "contextual_map_shortcut": True,
        "router_timeout": False,
    }


def _looks_like_companion_place_conflict(user_message: str, analysis: dict) -> bool:
    """Trigger model review when place routing conflicts with explicit companion intent."""
    if (analysis.get("primary_intent") or "").lower() != "map.search":
        return False
    text = " ".join(str(user_message or "").split())
    place_negation = ("不是找店", "不找店", "别给我店铺", "不是查店", "不是找地方", "不用店铺")
    people_cues = ("搭子", "有没有人", "有没有同学", "找人", "找同学", "一起打", "一起去")
    return _has_any(text, place_negation) and _has_any(text, people_cues)


def _looks_like_profile_review_needed(user_message: str, analysis: dict) -> bool:
    """Trigger model review for colloquial profile requests misrouted as content search."""
    if (analysis.get("primary_intent") or "").lower() == "user.profile":
        return False
    text = " ".join(str(user_message or "").split())
    return _has_any(text, ("主页", "个人主页", "资料", "号同学")) and _has_any(text, ("看看", "瞅瞅", "发过", "以前发"))


def _has_any(text: str, cues: tuple[str, ...]) -> bool:
    return any(cue in text for cue in cues)


def _has_negated_action(text: str, action_cues: tuple[str, ...]) -> bool:
    """Detect colloquial negation immediately before an action cue."""
    lowered = " ".join(str(text or "").split()).lower()
    if not lowered:
        return False
    negation_markers = (
        "不要",
        "别",
        "不用",
        "不必",
        "不需要",
        "无需",
        "先不",
        "暂时不",
        "no ",
        "not ",
        "don't ",
        "dont ",
        "do not ",
        "without ",
    )
    for cue in action_cues:
        cue = str(cue or "").lower()
        if not cue:
            continue
        start = lowered.find(cue)
        while start != -1:
            window = lowered[max(0, start - 12):start]
            if _has_any(window, negation_markers):
                return True
            start = lowered.find(cue, start + len(cue))
    return False


def _has_negated_write_action(text: str) -> bool:
    return _has_negated_action(
        text,
        (
            "创建",
            "发起",
            "发布",
            "发动态",
            "发订单",
            "建订单",
            "建活动",
            "报名",
            "申请",
            "申请加入",
            "加入订单",
            "加入活动",
            "评论",
            "回复",
            "留言",
            "点赞",
            "post",
            "publish",
            "apply",
            "join",
            "comment",
            "reply",
            "like",
        ),
    )


WEATHER_CONTEXT_CUES = (
    "天气",
    "下雨",
    "降雨",
    "气温",
    "温度",
    "适不适合",
    "适合不适合",
    "weather",
    "rain",
    "rains",
    "raining",
    "rainy",
    "temperature",
    "forecast",
    "sunny",
    "snow",
)


def _has_weather_context(text: str) -> bool:
    return _has_any(" ".join(str(text or "").split()).lower(), WEATHER_CONTEXT_CUES)


def _looks_like_memory_preference_update(text: str) -> bool:
    """Detect durable user preferences that should be confirmed before saving."""
    text = " ".join(str(text or "").split())
    if not text:
        return False
    if _has_any(text, ("记住", "记得我", "偏好")):
        return True
    durable_cues = ("以后", "下次", "今后", "往后", "以后如果", "以后推荐")
    preference_cues = ("优先", "尽量", "更喜欢", "不要", "避开", "推荐给我", "给我推荐")
    topic_cues = (
        "推荐",
        "安排",
        "活动",
        "地点",
        "店",
        "自习",
        "吃饭",
        "天气",
        "户外",
        "室内",
        "搭子",
    )
    return _has_any(text, durable_cues) and _has_any(text, preference_cues) and _has_any(text, topic_cues)


def _looks_like_companion_search(text: str) -> bool:
    """Detect read-only requests for people/companions rather than places."""
    text = " ".join(str(text or "").split())
    if not text:
        return False
    if _has_any(text, ("动态", "帖子", "校园圈", "评论区")):
        return False

    companion_cues = (
        "找人",
        "找几个",
        "找几个人",
        "找同学",
        "找搭子",
        "搭子",
        "同学一起",
        "有没有人",
        "有没有同学",
        "有人一起",
        "一起去",
        "一起打",
        "一起吃",
        "一起看",
        "一起玩",
        "一起自习",
        "组队",
        "约人",
        "约几个",
    )
    activity_cues = (
        "按摩",
        "洗脚",
        "足疗",
        "吃饭",
        "烤肉",
        "电影",
        "看电影",
        "羽毛球",
        "篮球",
        "跑步",
        "自习",
        "健身",
        "密室",
        "桌游",
        "唱歌",
        "ktv",
        "骑车",
        "徒步",
        "逛街",
        "咖啡",
    )
    negative_place_cues = (
        "不是找店",
        "不找店",
        "不要找店",
        "别找店",
        "不要推荐店",
        "别推荐店",
        "不用推荐店",
        "不要给我推荐店",
        "不要给我店铺推荐",
        "别给我店铺推荐",
        "不要店铺推荐",
        "别店铺推荐",
        "不是找地方",
        "不找地方",
    )
    explicit_place_cues = (
        "店",
        "推荐的店",
        "找店",
        "找个店",
        "找家店",
        "店吗",
        "店铺",
        "商家",
        "地点",
        "地方",
        "地址",
        "路线",
        "导航",
        "怎么走",
        "地图",
        "哪家",
        "哪里",
    )

    has_companion = _has_any(text, companion_cues)
    if not has_companion:
        return False
    if _has_any(text, negative_place_cues):
        return True
    return _has_any(text, activity_cues) and not _has_any(text, explicit_place_cues)


def _contains_blocking_write_negation(text: str) -> bool:
    """Return true when the user is negating the write itself, not asking for confirmation first."""
    business_cancel_cues = (
        "取消报名",
        "撤销报名",
        "取消申请",
        "撤销申请",
        "取消加入",
        "退出订单",
        "退出活动",
        "取消订单",
        "取消活动",
        "cancel my application",
        "withdraw application",
        "cancel application",
        "leave order",
        "cancel order",
    )
    if _has_any(str(text or "").lower(), business_cancel_cues):
        return False
    if _has_any(text, ("取消", "不想")):
        return True
    direct_confirmation_cues = (
        "不要直接",
        "别直接",
        "不要马上",
        "别马上",
        "先确认",
        "先让我确认",
        "先不要发布",
        "先别发布",
        "先不要发",
        "先别发",
    )
    if _has_any(text, direct_confirmation_cues):
        return False
    if _has_negated_write_action(text):
        return True
    return _has_any(
        text,
        (
            "不要创建",
            "别创建",
            "不要发起",
            "别发起",
            "不要发布",
            "别发布",
            "不要发动态",
            "别发动态",
            "不要帮我发动态",
            "别帮我发动态",
            "不用帮我发动态",
            "不要替我发动态",
            "别替我发动态",
            "不要建活动",
            "别建活动",
            "不用建活动",
            "不要发订单",
            "别发订单",
            "不要建订单",
            "别建订单",
            "不要报名",
            "别报名",
            "不用报名",
            "不要替我报名",
            "别替我报名",
            "不用帮我报名",
            "先不要报名",
            "先别报名",
            "不要申请",
            "别申请",
            "不用申请",
            "不要评论",
            "别评论",
            "不要替我评论",
            "别替我评论",
            "不要帮我评论",
            "别帮我评论",
            "不用帮我评论",
            "不用替我评论",
            "不要点赞",
            "别点赞",
            "不用点赞",
            "不要帮我点赞",
            "别帮我点赞",
            "不用帮我点赞",
        ),
    )


def _looks_like_time_text(text: str) -> bool:
    return bool(
        re.search(
            r"(今天|今晚|明天|后天|大后天|周[一二三四五六日天末]|星期[一二三四五六日天]|"
            r"[0-9一二两三四五六七八九十]{1,2}(点|:|：)|上午|中午|下午|晚上|早上|傍晚|凌晨|[0-9一二两三四五六七八九十]{1,2}号)",
            text,
        )
    )


def _detect_general_help_shortcut(user_message: str) -> dict | None:
    """Fast path for low-risk product-help or small-talk prompts.

    Business routing still goes through the semantic router. This shortcut only
    avoids spending a full router/review budget on obvious "what can you do"
    prompts that never need tools or write confirmation.
    """
    text = " ".join(str(user_message or "").split())
    if not text:
        return None

    business_cues = (
        "订单",
        "约伴",
        "活动",
        "动态",
        "地图",
        "天气",
        "附近",
        "推荐",
        "查询",
        "查一下",
        "搜索",
        "发布",
        "创建",
        "发起",
        "报名",
        "申请加入",
        "评论",
        "点赞",
        "记住",
        "偏好",
        "用户",
        "主页",
    )
    if _has_any(text, business_cues):
        return None

    help_cues = (
        "你能做什么",
        "你可以做什么",
        "你会做什么",
        "你是谁",
        "介绍你自己",
        "介绍一下你自己",
        "怎么用",
        "如何使用",
        "使用说明",
        "有什么功能",
        "功能介绍",
        "给我几个例子",
        "能帮我什么",
        "能怎么帮我",
        "怎么帮我",
        "说说能力",
        "能力",
        "hello",
        "hi",
        "你好",
        "在吗",
    )
    if not _has_any(text.lower(), help_cues):
        return None

    return {
        "primary_intent": "chat.general",
        "domain": "general",
        "operation_type": "read",
        "requires_confirmation": False,
        "confidence": 0.95,
        "summary": "用户在询问 AI 助手能力或进行普通闲聊",
        "missing_slots": [],
        "suggested_agents": ["general"],
        "next_action": "direct_answer",
        "reviewed": False,
        "general_help_shortcut": True,
        "router_timeout": False,
    }


def _detect_read_intent_shortcut(user_message: str) -> dict | None:
    """Fast path for unambiguous read-only requests that should not wait on LLM routing."""
    text = " ".join(str(user_message or "").split())
    lowered = text.lower()
    if not text:
        return None
    if _looks_like_memory_preference_update(text):
        return None

    hard_write_cues = (
        "发布动态",
        "发一条动态",
        "发个动态",
        "发动态",
        "写动态",
        "写个动态",
        "写一条动态",
        "动态草稿",
        "创建",
        "发起",
        "报名",
        "申请加入",
        "加入订单",
        "加入活动",
        "评论",
        "点赞",
        "记住",
        "接受申请",
        "完成订单",
    )
    read_only_overrides = (
        "不要创建",
        "别创建",
        "不用创建",
        "不要发布",
        "别发布",
        "不用发布",
        "不要发",
        "别发",
        "不要帮我发",
        "别帮我发",
        "不用帮我发",
        "不要替我发",
        "别替我发",
        "不要评论",
        "别评论",
        "不要替我评论",
        "别替我评论",
        "不要帮我评论",
        "别帮我评论",
        "不要点赞",
        "别点赞",
        "不要报名",
        "别报名",
        "不用报名",
        "先别报名",
        "不要申请加入",
        "别申请加入",
        "不用申请加入",
        "先别申请",
        "先不要申请",
        "先只",
        "只推荐",
        "先推荐",
        "先看看",
        "先查",
        "只是",
        "仅",
    )
    if (
        _has_any(text, hard_write_cues)
        and not _has_any(text, read_only_overrides)
        and not _has_negated_action(text, hard_write_cues)
    ):
        return None

    place_lookup_context_cues = (
        "店",
        "地方",
        "地点",
        "商家",
        "场馆",
        "附近",
        "餐厅",
        "咖啡",
        "路线",
        "地图",
        "place",
        "places",
        "shop",
        "store",
        "venue",
        "venues",
        "restaurant",
        "restaurants",
        "coffee",
        "cafe",
        "cafes",
        "cinema",
        "movie",
        "route",
        "map",
        "nearby",
    )
    weather_action_cues = (
        "查",
        "查询",
        "看看",
        "今天",
        "明天",
        "北京",
        "户外",
        "跑步",
        "check",
        "show",
        "look up",
        "weather",
        "forecast",
    )
    if (
        _has_weather_context(text)
        and _has_any(lowered, weather_action_cues)
        and not _has_any(lowered, place_lookup_context_cues)
    ):
        return {
            "primary_intent": "weather.query",
            "domain": "weather",
            "operation_type": "read",
            "requires_confirmation": False,
            "confidence": 0.86,
            "summary": "用户想查询天气并获得出行或活动建议",
            "missing_slots": [],
            "suggested_agents": ["map_weather"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "read_shortcut": True,
            "router_timeout": False,
        }

    generic_read_cues = (
        "搜",
        "搜索",
        "找",
        "看看",
        "查询",
        "查一下",
        "列出来",
        "有哪些",
        "有没有",
        "主页",
        "资料",
        "信息",
    )
    generic_read_cues = generic_read_cues + (
        "search",
        "find",
        "browse",
        "look up",
        "show me",
        "check",
        "view",
        "list",
    )
    if _looks_like_companion_search(text):
        return {
            "primary_intent": "order.search",
            "domain": "order",
            "operation_type": "read",
            "requires_confirmation": False,
            "confidence": 0.86,
            "summary": "用户想搜索可一起参加活动的人或约伴机会",
            "missing_slots": [],
            "suggested_agents": ["order_query"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "read_shortcut": True,
            "router_timeout": False,
        }

    if _has_any(text, generic_read_cues) and _has_any(text, ("用户", "主页", "资料")):
        return {
            "primary_intent": "user.profile",
            "domain": "user",
            "operation_type": "read",
            "requires_confirmation": False,
            "confidence": 0.84,
            "summary": "用户想查看用户主页或资料信息",
            "missing_slots": [],
            "suggested_agents": ["user_profile"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "read_shortcut": True,
            "router_timeout": False,
        }

    negated_content_write = _has_any(
        text,
        ("不要发布动态", "别发布动态", "不用发布动态", "不要发动态", "别发动态", "不用发动态"),
    ) or _has_any(
        lowered,
        (
            "no post",
            "no posting",
            "do not post",
            "don't post",
            "dont post",
            "without posting",
            "not post",
            "no publish",
            "do not publish",
            "don't publish",
            "dont publish",
        ),
    )
    content_negation_place_cues = place_lookup_context_cues + (
        "按摩",
        "洗脚",
        "足疗",
        "密室",
        "吃饭",
        "dinner",
        "lunch",
        "food",
        "massage",
        "board game",
        "escape room",
    )
    english_content_read = _has_any(lowered, generic_read_cues) and _has_any(
        lowered,
        (
            "post",
            "posts",
            "campus post",
            "campus posts",
            "feed",
            "campus feed",
            "timeline",
            "content",
        ),
    )
    if (
        (
            _has_any(text, generic_read_cues)
            and _has_any(text, ("动态", "帖子", "评论区", "校园圈"))
        ) or english_content_read
    ) and not (negated_content_write and _has_any(lowered, content_negation_place_cues)):
        return {
            "primary_intent": "content.search",
            "domain": "content",
            "operation_type": "read",
            "requires_confirmation": False,
            "confidence": 0.84,
            "summary": "用户想搜索或查看校园动态内容",
            "missing_slots": [],
            "suggested_agents": ["content_query"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "read_shortcut": True,
            "router_timeout": False,
        }

    negated_order_write = _has_any(text, ("不要创建订单", "别创建订单", "不用创建订单", "不要发订单", "别发订单"))
    has_positive_order_context = (
        ("订单" in text and not negated_order_write)
        or _has_any(text, ("约伴", "我发布过", "我参加过", "报名记录", "申请记录", "篮球局", "羽毛球局", "自习局"))
    )
    has_order_activity_context = (
        ("活动" in text and _has_any(text, ("约伴", "报名", "加入", "我发布过", "我参加过")))
        or (_has_any(text, ("局", "场", "名额", "空位")) and _has_any(text, ("篮球", "羽毛球", "跑步", "自习", "健身", "桌游")))
    )
    if (
        _has_any(text, generic_read_cues)
        and (has_positive_order_context or has_order_activity_context)
        and not (negated_order_write and not has_positive_order_context)
    ):
        return {
            "primary_intent": "order.search",
            "domain": "order",
            "operation_type": "read",
            "requires_confirmation": False,
            "confidence": 0.84,
            "summary": "用户想搜索或查看约伴活动订单",
            "missing_slots": [],
            "suggested_agents": ["order_query"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "read_shortcut": True,
            "router_timeout": False,
        }

    map_read_cues = (
        "找",
        "推荐",
        "看看",
        "查询",
        "查一下",
        "附近",
        "有没有",
        "哪里",
        "怎么走",
        "路线",
        "地图",
        "地址",
        "导航",
        "比较",
        "find",
        "search",
        "recommend",
        "near",
        "nearby",
        "around",
        "show map",
        "route",
        "directions",
        "where",
    )
    place_cues = (
        "店",
        "地方",
        "地点",
        "商家",
        "场",
        "馆",
        "餐厅",
        "吃饭",
        "饭",
        "按摩",
        "洗脚",
        "足疗",
        "推拿",
        "spa",
        "头疗",
        "玩",
        "电影院",
        "影院",
        "咖啡",
        "奶茶",
        "超市",
        "药店",
        "医院",
        "ktv",
        "酒吧",
        "公园",
        "密室",
        "place",
        "places",
        "shop",
        "store",
        "venue",
        "venues",
        "restaurant",
        "restaurants",
        "resturant",
        "resturants",
        "restraunt",
        "restraunts",
        "dining",
        "eatery",
        "eateries",
        "dinner",
        "lunch",
        "food",
        "massage",
        "coffee",
        "cafe",
        "cafes",
        "cinema",
        "movie",
        "theater",
        "supermarket",
        "pharmacy",
        "hospital",
        "bar",
        "park",
    )
    if _has_any(lowered, map_read_cues) and _has_any(lowered, place_cues):
        return {
            "primary_intent": "map.search",
            "domain": "map",
            "operation_type": "read",
            "requires_confirmation": False,
            "confidence": 0.86,
            "summary": "用户想查询、推荐或比较附近地点",
            "missing_slots": [],
            "suggested_agents": ["map_weather"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "read_shortcut": True,
            "router_timeout": False,
            "weather_context": _has_weather_context(text),
        }

    return None


def _recent_history_has_confirmation_draft(history: list) -> bool:
    recent = "\n".join(str(item.get("content", "")) for item in (history or [])[-6:] if isinstance(item, dict))
    if not recent:
        return False
    return _has_any(
        recent,
        (
            "草稿",
            "待确认",
            "确认草稿",
            "确认创建",
            "确认发布",
            "确认执行",
            "confirm",
            "confirmation",
            "draft",
        ),
    )


def _looks_like_new_business_request(text: str) -> bool:
    return _has_any(
        text,
        (
            "搜索",
            "搜一下",
            "查一下",
            "看看",
            "推荐",
            "找",
            "创建",
            "发布",
            "报名",
            "申请",
            "评论",
            "点赞",
            "记住",
            "地图",
            "天气",
            "订单",
            "动态",
            "search",
            "find",
            "recommend",
            "create",
            "publish",
            "apply",
            "comment",
            "like",
            "remember",
            "map",
            "weather",
            "order",
        ),
    )


def _detect_draft_cancel_shortcut(history: list, user_message: str) -> dict | None:
    """Treat draft cancellation as a safe direct answer, not as a write action."""
    text = " ".join(str(user_message or "").split())
    if not text or not _recent_history_has_confirmation_draft(history):
        return None

    lower_text = text.lower()
    cancel_cues = (
        "取消这个草稿",
        "取消草稿",
        "这个草稿取消",
        "先取消",
        "先算了",
        "算了",
        "不用了",
        "不发了",
        "不发布了",
        "不创建了",
        "别发了",
        "别发布了",
        "别创建了",
        "先不发",
        "先不发布",
        "先不创建",
        "cancel this draft",
        "cancel the draft",
        "drop this draft",
        "discard this draft",
        "never mind",
        "nevermind",
        "forget it",
        "do not publish",
        "don't publish",
        "do not create",
        "don't create",
    )
    destructive_cancel_targets = (
        "取消点赞",
        "取消报名",
        "取消申请",
        "取消订单",
        "取消活动",
        "unlike",
        "cancel my application",
        "cancel order",
    )
    if _has_any(lower_text, destructive_cancel_targets):
        return None
    if not _has_any(lower_text, cancel_cues):
        return None
    residual_text = lower_text
    for cue in cancel_cues:
        residual_text = residual_text.replace(cue, " ")
    if _looks_like_new_business_request(residual_text):
        return None

    return {
        "primary_intent": "chat.general",
        "domain": "general",
        "operation_type": "read",
        "requires_confirmation": False,
        "confidence": 0.9,
        "summary": "用户取消了上一条待确认草稿",
        "missing_slots": [],
        "suggested_agents": ["general"],
        "next_action": "direct_answer",
        "reviewed": False,
        "draft_cancel_shortcut": True,
        "router_timeout": False,
    }


def _detect_draft_edit_shortcut(history: list, user_message: str) -> dict | None:
    """Keep draft edits in the original write domain without another slow router round."""
    text = " ".join(str(user_message or "").split())
    if not text:
        return None

    edit_cues = ("改成", "改为", "改得", "修改", "调整", "换成", "补充", "加上", "加一句", "语气", "删掉", "去掉")
    if not _has_any(text, edit_cues):
        return None

    recent = "\n".join(str(item.get("content", "")) for item in (history or [])[-6:])
    if not _recent_history_has_confirmation_draft(history):
        return None

    if _has_any(recent, ("动态", "帖子", "发布")):
        return {
            "primary_intent": "content.create",
            "domain": "content",
            "operation_type": "write",
            "requires_confirmation": True,
            "confidence": 0.9,
            "summary": "用户正在修改上一条动态发布草稿",
            "missing_slots": [],
            "suggested_agents": ["content_draft"],
            "next_action": "prepare_draft",
            "reviewed": False,
            "draft_edit_shortcut": True,
            "router_timeout": False,
        }

    if _has_any(recent, ("约伴", "订单", "活动")):
        return {
            "primary_intent": "order.create",
            "domain": "order",
            "operation_type": "write",
            "requires_confirmation": True,
            "confidence": 0.9,
            "summary": "用户正在修改上一条约伴订单草稿",
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
            "reviewed": False,
            "draft_edit_shortcut": True,
            "router_timeout": False,
        }

    if _has_any(recent, ("记忆", "记住", "偏好")):
        return {
            "primary_intent": "memory.manage",
            "domain": "memory",
            "operation_type": "write",
            "requires_confirmation": True,
            "confidence": 0.88,
            "summary": "用户正在修改上一条记忆草稿",
            "missing_slots": [],
            "suggested_agents": ["memory"],
            "next_action": "prepare_draft",
            "reviewed": False,
            "draft_edit_shortcut": True,
            "router_timeout": False,
        }

    return None


def _detect_safety_intent_shortcut(user_message: str) -> dict | None:
    """Fast safety path for unmistakable write or read-then-write requests."""
    text = " ".join(str(user_message or "").split())
    if not text:
        return None
    if _contains_blocking_write_negation(text):
        return None
    if _looks_like_read_then_write_request(text, {}):
        return {
            "primary_intent": "multi_step",
            "domain": "multi",
            "operation_type": "mixed",
            "requires_confirmation": True,
            "confidence": 0.86,
            "summary": "用户想先查询推荐信息，再根据结果决定是否创建草稿",
            "missing_slots": [],
            "suggested_agents": ["map_weather", "order_draft"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "safety_shortcut": True,
            "router_timeout": False,
        }

    base = {
        "operation_type": "write",
        "requires_confirmation": True,
        "confidence": 0.88,
        "reviewed": False,
        "safety_shortcut": True,
        "router_timeout": False,
    }

    if _looks_like_memory_preference_update(text):
        return {
            **base,
            "primary_intent": "memory.manage",
            "domain": "memory",
            "summary": "用户想让 AI 记住一条偏好或事实",
            "missing_slots": [],
            "suggested_agents": ["memory"],
            "next_action": "prepare_draft",
        }

    if "动态" in text and _has_any(text, ("评论", "回复", "回一句", "回一条", "留言")):
        return {
            **base,
            "primary_intent": "content.interact",
            "domain": "content",
            "summary": "用户想对动态发表评论",
            "missing_slots": [],
            "suggested_agents": ["content_draft"],
            "next_action": "prepare_draft",
        }

    if "动态" in text and _has_any(text, ("点赞", "点个赞", "赞一下")):
        return {
            **base,
            "primary_intent": "content.interact",
            "domain": "content",
            "summary": "用户想给动态点赞",
            "missing_slots": [],
            "suggested_agents": ["content_draft"],
            "next_action": "prepare_draft",
        }

    cancel_apply_cues = (
        "取消报名",
        "撤销报名",
        "取消申请",
        "撤销申请",
        "取消加入",
        "退出订单",
        "退出活动",
        "cancel my application",
        "withdraw application",
        "cancel application",
        "leave order",
    )
    if _has_any(text.lower(), cancel_apply_cues):
        return {
            **base,
            "primary_intent": "order.manage",
            "domain": "order",
            "summary": "用户想撤销约伴订单申请或退出已申请的活动",
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
        }

    reject_apply_cues = (
        "拒绝申请",
        "驳回申请",
        "不同意申请",
        "拒绝加入",
        "reject application",
        "reject applicant",
        "deny application",
    )
    if _has_any(text.lower(), reject_apply_cues) or (_has_any(text, ("拒绝", "驳回", "不同意")) and "申请" in text):
        return {
            **base,
            "primary_intent": "order.manage",
            "domain": "order",
            "summary": "用户想拒绝约伴订单申请",
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
        }

    if _has_any(text, ("完成订单", "标记完成", "订单完成", "结束订单", "完成这个订单", "mark complete")):
        return {
            **base,
            "primary_intent": "order.manage",
            "domain": "order",
            "summary": "用户想将约伴订单标记为完成",
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
        }

    order_delete_cues = ("删除", "删掉", "删了", "下架", "撤下", "移除")
    if _has_any(
        text,
        (
            "取消订单",
            "取消活动",
            "删除订单",
            "删掉订单",
            "删了订单",
            "下架订单",
            "撤下订单",
            "移除订单",
        ),
    ) or _has_any(
        text.lower(),
        ("cancel order", "cancel activity", "delete order", "remove order", "take down order"),
    ) or ("订单" in text and _has_any(text, order_delete_cues)):
        return {
            **base,
            "primary_intent": "order.manage",
            "domain": "order",
            "summary": "用户想取消、删除或下架约伴订单/活动，需先确认并检查是否已有可执行工具",
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
        }

    if _has_any(text, ("接受申请", "同意申请", "通过申请", "同意加入", "通过一下", "同意一下")):
        return {
            **base,
            "primary_intent": "order.manage",
            "domain": "order",
            "summary": "用户想处理约伴订单申请",
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
        }

    if (
        _has_any(text, ("订单草稿", "约伴订单草稿"))
        or (_has_any(text, ("整理成", "生成", "做成")) and _has_any(text, ("约伴", "订单", "活动")))
        or (_has_any(text, ("草稿",)) and _has_any(text, ("约伴", "订单", "活动")))
    ):
        missing_slots = []
        if not _looks_like_time_text(text):
            missing_slots.append("时间")
        if not _has_any(text, ("校区", "馆", "场", "楼", "室", "地点", "地址", "店", "第一家", "刚才")):
            missing_slots.append("地点")
        if not _has_any(text, ("人", "人数", "最多", "名")):
            missing_slots.append("参与人数")
        return {
            **base,
            "primary_intent": "order.create",
            "domain": "order",
            "summary": "用户想基于已有信息整理一个约伴活动草稿",
            "missing_slots": missing_slots,
            "suggested_agents": ["order_draft"],
            "next_action": "ask_clarification" if missing_slots else "prepare_draft",
        }

    if _has_any(text, ("发布动态", "发一条动态", "发个动态", "发动态", "写动态", "写个动态", "写一条动态", "动态草稿")):
        return {
            **base,
            "primary_intent": "content.create",
            "domain": "content",
            "summary": "用户想发布一条校园动态",
            "missing_slots": [],
            "suggested_agents": ["content_draft"],
            "next_action": "prepare_draft",
        }

    if _has_any(text, ("报名", "申请加入", "加入订单", "加入活动")):
        return {
            **base,
            "primary_intent": "order.manage",
            "domain": "order",
            "summary": "用户想报名或申请加入约伴活动",
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
        }

    if _has_any(text, ("创建", "发起")) and _has_any(text, ("约伴", "订单", "活动")):
        missing_slots = []
        if not _looks_like_time_text(text):
            missing_slots.append("时间")
        if not _has_any(text, ("校区", "馆", "场", "楼", "室", "地点", "地址")):
            missing_slots.append("地点")
        if not _has_any(text, ("人", "人数", "最多", "名")):
            missing_slots.append("参与人数")
        return {
            **base,
            "primary_intent": "order.create",
            "domain": "order",
            "summary": "用户想创建一个约伴活动草稿",
            "missing_slots": missing_slots,
            "suggested_agents": ["order_draft"],
            "next_action": "ask_clarification" if missing_slots else "prepare_draft",
        }

    return None


def _detect_router_error_read_fallback(user_message: str) -> dict | None:
    """Conservative read-only fallback used when the semantic router is unavailable."""
    text = " ".join(str(user_message or "").split())
    if not text:
        return None
    if _detect_safety_intent_shortcut(text):
        return None

    read_cues = (
        "找", "看看", "查询", "查一下", "推荐", "附近", "有没有", "怎么走", "路线", "地图",
        "find", "search", "recommend", "near", "nearby", "around", "show map", "route", "directions", "where",
    )
    generic_read_cues = read_cues + ("搜索", "搜一下", "列出", "哪些", "信息", "主页", "list", "show", "check")

    if _looks_like_companion_search(text):
        return {
            "primary_intent": "order.search",
            "domain": "order",
            "operation_type": "read",
            "requires_confirmation": False,
            "confidence": 0.72,
            "summary": "用户想搜索可一起参加活动的人或约伴机会，路由模型不可用后降级为订单只读查询",
            "missing_slots": [],
            "suggested_agents": ["order_query"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "router_timeout_fallback": True,
        }

    if _has_any(text, ("天气", "气温", "下雨", "刮风", "适不适合")):
        return {
            "primary_intent": "weather.query",
            "domain": "weather",
            "operation_type": "read",
            "requires_confirmation": False,
            "confidence": 0.7,
            "summary": "用户想查询天气或户外建议，路由模型超时后降级为天气只读查询",
            "missing_slots": [],
            "suggested_agents": ["map_weather"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "router_timeout_fallback": True,
        }

    if _has_any(text, generic_read_cues) and _has_any(text, ("订单", "约伴", "活动", "我发布", "我参加", "篮球", "羽毛球")):
        return {
            "primary_intent": "order.search",
            "domain": "order",
            "operation_type": "read",
            "requires_confirmation": False,
            "confidence": 0.7,
            "summary": "用户想查询约伴活动或订单，路由模型超时后降级为订单只读查询",
            "missing_slots": [],
            "suggested_agents": ["order_query"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "router_timeout_fallback": True,
        }

    if _has_any(text, generic_read_cues) and _has_any(text, ("动态", "帖子", "评论", "自习")):
        return {
            "primary_intent": "content.search",
            "domain": "content",
            "operation_type": "read",
            "requires_confirmation": False,
            "confidence": 0.7,
            "summary": "用户想查询校园动态，路由模型超时后降级为动态只读查询",
            "missing_slots": [],
            "suggested_agents": ["content_query"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "router_timeout_fallback": True,
        }

    if _has_any(text, generic_read_cues) and _has_any(text, ("用户", "主页", "资料")):
        return {
            "primary_intent": "user.profile",
            "domain": "user",
            "operation_type": "read",
            "requires_confirmation": False,
            "confidence": 0.7,
            "summary": "用户想查看用户主页信息，路由模型超时后降级为用户资料只读查询",
            "missing_slots": [],
            "suggested_agents": ["user_profile"],
            "next_action": "execute_read_tools",
            "reviewed": False,
            "router_timeout_fallback": True,
        }

    place_cues = (
        "店",
        "地方",
        "地点",
        "商家",
        "场",
        "馆",
        "餐厅",
        "吃饭",
        "饭",
        "按摩",
        "洗脚",
        "玩",
        "电影院",
        "影院",
        "place",
        "places",
        "shop",
        "store",
        "venue",
        "restaurant",
        "restaurants",
        "resturant",
        "resturants",
        "restraunt",
        "restraunts",
        "dining",
        "eatery",
        "eateries",
        "dinner",
        "food",
        "massage",
        "coffee",
        "cafe",
        "cinema",
        "movie",
        "theater",
    )
    if not (_has_any(text, read_cues) and _has_any(text, place_cues)):
        return None

    return {
        "primary_intent": "map.search",
        "domain": "map",
        "operation_type": "read",
        "requires_confirmation": False,
        "confidence": 0.7,
        "summary": "用户想查询或推荐附近地点，路由模型超时后降级为地图只读查询",
        "missing_slots": [],
        "suggested_agents": ["map_weather"],
        "next_action": "execute_read_tools",
        "reviewed": False,
        "router_timeout_fallback": True,
    }


def _should_review_intent(analysis: dict, user_message: str = "") -> bool:
    confidence = analysis.get("confidence", 0.0)
    primary_intent = (analysis.get("primary_intent") or "").lower()
    operation_type = (analysis.get("operation_type") or "").lower()
    next_action = (analysis.get("next_action") or "").lower()
    if confidence < 0.65 or primary_intent == "unknown" or operation_type == "unknown":
        return True
    if (
        _looks_like_read_then_write_request(user_message, analysis)
        or _looks_like_companion_place_conflict(user_message, analysis)
        or _looks_like_profile_review_needed(user_message, analysis)
    ):
        return True
    if operation_type in {"write", "mixed"}:
        gated_actions = {"ask_clarification", "prepare_draft", "wait_confirmation", "execute_read_tools"}
        if bool(analysis.get("requires_confirmation")) and confidence >= 0.82 and next_action in gated_actions:
            return False
        return True
    return next_action == "direct_answer" and primary_intent != "chat.general"


async def review_intent(
    user_info: dict,
    memories: list,
    history: list,
    user_message: str,
    previous_analysis: dict,
    timeout_seconds: float = INTENT_REVIEW_TIMEOUT_SECONDS,
) -> dict:
    await _emit_event("agent_step", {
        "phase": "intent_review",
        "title": "复核低置信度意图",
        "detail": "快模型判断不够确定，正在调用主模型复核是否涉及写操作或子智能体调度",
        "state": "running",
    })
    prompt = _render_intent_prompt(previous_analysis, user_info, memories, history, user_message)
    try:
        result = await _await_with_soft_timeout(
            _get_llm(streaming=False, temperature=0, max_tokens=700).ainvoke([HumanMessage(content=prompt)]),
            timeout_seconds,
        )
        reviewed = _normalize_intent_analysis(_safe_json_loads(result.content))
        reviewed["reviewed"] = True
        reviewed["router_first_pass"] = previous_analysis
        return reviewed
    except Exception as e:
        logger.warning("Intent review failed: %s", e)
        previous_analysis["review_failed"] = True
        return previous_analysis


async def analyze_intent(user_info: dict, memories: list, history: list, user_message: str) -> dict:
    started_at = time.perf_counter()
    cache_key = _intent_cache_key(user_info, memories, history, user_message)
    cached = _get_cached_intent(cache_key)
    if cached:
        cached["router_elapsed_ms"] = 0
        await _emit_event("agent_step", {
            "phase": "intent_cache",
            "title": "复用意图分析结果",
            "detail": "检测到相同用户上下文和请求，已复用最近一次语义分析结果",
            "state": "completed",
        })
        await _emit_event("intent", {
            **cached,
            "title": "意图分析完成",
            "state": "completed",
        })
        return cached

    contextual_map_analysis = _detect_contextual_order_create_shortcut(history, user_message)
    if contextual_map_analysis:
        analysis = _normalize_intent_analysis(contextual_map_analysis)
        analysis["router_elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
        analysis["cache_hit"] = False
        _store_intent(cache_key, analysis)
        await _emit_event("agent_step", {
            "phase": "intent_contextual_map",
            "title": "沿用地图结果创建草稿",
            "detail": "识别到用户选中了上一轮地图候选，先生成约伴订单草稿并等待确认",
            "state": "completed",
        })
        await _emit_event("intent", {
            **analysis,
            "title": "意图分析完成",
            "state": "completed",
        })
        return analysis

    contextual_content_analysis = _detect_contextual_content_interact_shortcut(history, user_message)
    if contextual_content_analysis:
        analysis = _normalize_intent_analysis(contextual_content_analysis)
        analysis["router_elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
        analysis["cache_hit"] = False
        _store_intent(cache_key, analysis)
        await _emit_event("agent_step", {
            "phase": "intent_contextual_content",
            "title": "沿用动态结果生成互动草稿",
            "detail": "识别到用户选中了上一轮动态候选，先生成评论或点赞确认草稿",
            "state": "completed",
        })
        await _emit_event("intent", {
            **analysis,
            "title": "意图分析完成",
            "state": "completed",
        })
        return analysis

    contextual_order_content_analysis = _detect_contextual_order_content_create_shortcut(history, user_message)
    if contextual_order_content_analysis:
        analysis = _normalize_intent_analysis(contextual_order_content_analysis)
        analysis["router_elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
        analysis["cache_hit"] = False
        _store_intent(cache_key, analysis)
        await _emit_event("agent_step", {
            "phase": "intent_contextual_order_content",
            "title": "沿用订单生成动态草稿",
            "detail": "识别到用户想基于上一轮约伴订单发布校园动态，先生成确认草稿",
            "state": "completed",
        })
        await _emit_event("intent", {
            **analysis,
            "title": "意图分析完成",
            "state": "completed",
        })
        return analysis

    contextual_map_content_analysis = _detect_contextual_map_content_create_shortcut(history, user_message)
    if contextual_map_content_analysis:
        analysis = _normalize_intent_analysis(contextual_map_content_analysis)
        analysis["router_elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
        analysis["cache_hit"] = False
        _store_intent(cache_key, analysis)
        await _emit_event("agent_step", {
            "phase": "intent_contextual_map_content",
            "title": "沿用地图结果生成动态草稿",
            "detail": "识别到用户想基于上一轮地图地点发布校园动态，先生成确认草稿",
            "state": "completed",
        })
        await _emit_event("intent", {
            **analysis,
            "title": "意图分析完成",
            "state": "completed",
        })
        return analysis

    safety_analysis = _detect_safety_intent_shortcut(user_message)
    if safety_analysis:
        analysis = _normalize_intent_analysis(safety_analysis)
        analysis["router_elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
        analysis["cache_hit"] = False
        _store_intent(cache_key, analysis)
        detail = (
            "读优先复合请求会先执行查询，再引导确认写操作"
            if analysis.get("operation_type") == "mixed"
            else "这类请求必须先生成确认草稿，不等待模型路由后再拦截"
        )
        await _emit_event("agent_step", {
            "phase": "intent_safety",
            "title": "识别明确安全路径",
            "detail": detail,
            "state": "completed",
        })
        await _emit_event("intent", {
            **analysis,
            "title": "意图分析完成",
            "state": "completed",
        })
        return analysis

    draft_cancel_analysis = _detect_draft_cancel_shortcut(history, user_message)
    if draft_cancel_analysis:
        analysis = _normalize_intent_analysis(draft_cancel_analysis)
        analysis["router_elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
        analysis["cache_hit"] = False
        _store_intent(cache_key, analysis)
        await _emit_event("agent_step", {
            "phase": "intent_draft_cancel",
            "title": "取消待确认草稿",
            "detail": "识别到用户放弃上一条草稿，本轮不会执行创建、发布或报名等写操作",
            "state": "completed",
        })
        await _emit_event("intent", {
            **analysis,
            "title": "意图分析完成",
            "state": "completed",
        })
        return analysis

    draft_edit_analysis = _detect_draft_edit_shortcut(history, user_message)
    if draft_edit_analysis:
        analysis = _normalize_intent_analysis(draft_edit_analysis)
        analysis["router_elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
        analysis["cache_hit"] = False
        _store_intent(cache_key, analysis)
        await _emit_event("agent_step", {
            "phase": "intent_draft_edit",
            "title": "识别草稿修改",
            "detail": "已根据最近确认草稿沿用原领域，继续生成待确认修改内容",
            "state": "completed",
        })
        await _emit_event("intent", {
            **analysis,
            "title": "意图分析完成",
            "state": "completed",
        })
        return analysis

    general_help_analysis = _detect_general_help_shortcut(user_message)
    if general_help_analysis:
        analysis = _normalize_intent_analysis(general_help_analysis)
        analysis["router_elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
        analysis["cache_hit"] = False
        _store_intent(cache_key, analysis)
        await _emit_event("agent_step", {
            "phase": "intent_general_help",
            "title": "识别普通帮助请求",
            "detail": "这是低风险能力介绍或闲聊请求，无需调用业务工具或等待写操作确认",
            "state": "completed",
        })
        await _emit_event("intent", {
            **analysis,
            "title": "意图分析完成",
            "state": "completed",
        })
        return analysis

    read_shortcut_analysis = _detect_read_intent_shortcut(user_message)
    if read_shortcut_analysis:
        analysis = _normalize_intent_analysis(read_shortcut_analysis)
        analysis["router_elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
        analysis["cache_hit"] = False
        _store_intent(cache_key, analysis)
        await _emit_event("agent_step", {
            "phase": "intent_read",
            "title": "识别明确只读请求",
            "detail": "这是查询、推荐、路线或天气类请求，无需等待写操作确认",
            "state": "completed",
        })
        await _emit_event("intent", {
            **analysis,
            "title": "意图分析完成",
            "state": "completed",
        })
        return analysis

    await _emit_event("agent_step", {
        "phase": "intent",
        "title": "分析用户意图",
        "detail": "正在用轻量模型判断任务类型、风险和需要的子智能体",
        "state": "running",
    })
    prompt = _render_intent_prompt(None, user_info, memories, history, user_message)
    try:
        result = await _await_with_soft_timeout(
            _get_router_llm().ainvoke([HumanMessage(content=prompt)]),
            ROUTER_TIMEOUT_SECONDS,
        )
        analysis = _normalize_intent_analysis(_safe_json_loads(result.content))
        analysis["router_timeout"] = False
    except Exception as e:
        logger.warning("Intent analysis failed: %s", e)
        router_timeout = isinstance(e, asyncio.TimeoutError)
        timeout_fallback = _detect_router_error_read_fallback(user_message)
        if timeout_fallback:
            analysis = _normalize_intent_analysis(timeout_fallback)
            analysis["router_timeout"] = router_timeout
            analysis["router_error"] = e.__class__.__name__
            fallback_detail = (
                "轻量模型响应超时，已将明确的只读请求降级到本地安全路由"
                if router_timeout
                else "轻量模型暂时不可用，已将明确的只读请求降级到本地安全路由"
            )
            await _emit_event("agent_step", {
                "phase": "intent_fallback",
                "title": "意图路由降级",
                "detail": fallback_detail,
                "state": "completed",
            })
        else:
            analysis = _normalize_intent_analysis({
                "summary": "意图分析暂时失败，交由主智能体继续判断。",
                "next_action": "ask_clarification",
            })
            analysis["router_timeout"] = router_timeout
            analysis["router_error"] = e.__class__.__name__

    if _should_review_intent(analysis, user_message):
        elapsed_seconds = time.perf_counter() - started_at
        remaining_seconds = INTENT_TOTAL_BUDGET_SECONDS - elapsed_seconds
        if remaining_seconds >= 3:
            analysis = await review_intent(
                user_info,
                memories,
                history,
                user_message,
                analysis,
                timeout_seconds=min(INTENT_REVIEW_TIMEOUT_SECONDS, remaining_seconds),
            )
        else:
            analysis["review_skipped"] = True
            analysis["review_skip_reason"] = "intent_budget_exhausted"

    analysis["router_elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
    analysis["cache_hit"] = False
    _store_intent(cache_key, analysis)

    await _emit_event("intent", {
        **analysis,
        "title": "意图分析完成",
        "state": "completed",
    })
    return analysis


def _build_intent_system_message(intent_analysis: dict) -> SystemMessage:
    missing = ", ".join(intent_analysis.get("missing_slots") or []) or "无"
    content = f"""## 本轮意图分析
- 主要意图: {intent_analysis.get('primary_intent', 'unknown')}
- 领域: {intent_analysis.get('domain', 'unknown')}
- 操作类型: {intent_analysis.get('operation_type', 'unknown')}
- 是否需要确认: {intent_analysis.get('requires_confirmation', True)}
- 分析摘要: {intent_analysis.get('summary', '')}
- 缺失信息: {missing}
- 建议下一步: {intent_analysis.get('next_action', 'unknown')}

请严格遵守：凡是写操作，必须先确认草稿，不要因为用户语气急切就直接执行。
"""
    if (
        (intent_analysis.get("operation_type") or "").lower() == "mixed"
        and (intent_analysis.get("next_action") or "").lower() == "execute_read_tools"
    ):
        content += "\n本轮是读优先复合任务：先执行查询/推荐/路线等只读工具；最终只能给出可确认草稿或下一步建议，不要直接执行创建、发布、报名、点赞、评论等写操作。\n"
    return SystemMessage(content=content)


def _requires_confirmation_gate(intent_analysis: dict) -> bool:
    operation_type = (intent_analysis.get("operation_type") or "").lower()
    next_action = (intent_analysis.get("next_action") or "").lower()
    if operation_type not in {"write", "mixed"}:
        return False
    if operation_type == "mixed" and next_action == "execute_read_tools":
        return False
    if intent_analysis.get("requires_confirmation", True):
        return True
    return next_action in {"prepare_draft", "wait_confirmation"}


def _normalize_artifact_fields(fields: list, missing_fields: list) -> list:
    normalized = []
    for item in fields or []:
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or "").strip()
            value = item.get("value", "")
            if label:
                normalized.append({"label": label, "value": str(value)})
        elif item:
            normalized.append({"label": "信息", "value": str(item)})

    for field in missing_fields or []:
        if field:
            normalized.append({"label": str(field), "value": "待补充", "missing": True})
    return normalized


def _conversation_text(history: list, user_message: str) -> str:
    parts = []
    for item in (history or [])[-8:]:
        if isinstance(item, dict) and item.get("content"):
            parts.append(str(item.get("content")))
    if user_message:
        parts.append(str(user_message))
    return "\n".join(parts)


def _parse_small_chinese_number(token: str) -> int | None:
    numerals = {
        "零": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    token = str(token or "").strip()
    if not token:
        return None
    if token in numerals:
        return numerals[token]
    if token == "十":
        return 10
    if "十" in token:
        left, _, right = token.partition("十")
        tens = numerals.get(left, 1) if left else 1
        ones = numerals.get(right, 0) if right else 0
        return tens * 10 + ones
    return None


def _extract_group_size(text: str) -> int | None:
    text = str(text or "")
    for match in re.finditer(r"(?<!\d)(\d{1,2})\s*(?:个|名)?人", text):
        value = int(match.group(1))
        if 1 <= value <= 50:
            return value
    for match in re.finditer(r"([一二两三四五六七八九十]{1,3})\s*(?:个|名)?人", text):
        value = _parse_small_chinese_number(match.group(1))
        if value and 1 <= value <= 50:
            return value
    return None


def _extract_map_selection(text: str) -> tuple[str, str]:
    text = str(text or "")
    title = ""
    title_match = re.search(r"[「\"]([^」\"]{1,80})[」\"]", text)
    if title_match:
        title = title_match.group(1).strip()
    else:
        label_match = re.search(r"(?:地点|位置)[:：]\s*([^\n\r,，]{1,80})", text)
        if label_match:
            title = label_match.group(1).strip()

    coords = ""
    coord_match = re.search(r"坐标[:：]?\s*([0-9]{2,3}\.\d+)\s*[,，]\s*([0-9]{1,2}\.\d+)", text)
    if coord_match:
        coords = f"{coord_match.group(1)}, {coord_match.group(2)}"
    return title, coords


def _extract_order_id_reference(text: str) -> int | None:
    text = str(text or "")
    patterns = (
        r"(?:订单|约伴|活动)\s*(?:ID|id|编号|#|号)?\s*[:：#]?\s*(\d+)",
        r"\border\s*#?\s*(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_application_id_reference(text: str) -> int | None:
    text = str(text or "")
    patterns = (
        r"(?:申请记录|申请ID|申请id|申请编号|申请)\s*[:：#]?\s*(\d+)",
        r"\bapply(?:id|_id)?\s*#?\s*(\d+)\b",
        r"\bapplication\s*#?\s*(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_applicant_id_reference(text: str) -> int | None:
    text = str(text or "")
    patterns = (
        r"(?:申请者|申请用户|用户|同学)\s*(?:ID|id|编号|#|号)?\s*[:：#]?\s*(\d+)",
        r"(\d+)\s*号?(?:同学|用户|申请者)",
        r"\bapplicant\s*#?\s*(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_recent_order_candidates(history: list) -> list[dict]:
    """Recover recent order-result candidates so follow-up apply actions keep order context."""
    candidates: list[dict] = []
    seen: set[str] = set()
    by_id: dict[str, dict] = {}

    def add_candidate(
        order_id: str,
        summary: str = "",
        activity: str = "",
        location: str = "",
        time_text: str = "",
        people: str = "",
    ) -> None:
        order_id = str(order_id or "").strip()
        if not order_id:
            return
        summary = str(summary or "").strip()
        activity = str(activity or "").strip()
        location = str(location or "").strip()
        time_text = str(time_text or "").strip()
        people = str(people or "").strip()
        if order_id in seen:
            candidate = by_id.get(order_id)
            if not candidate:
                return
            for key, value in {
                "summary": summary,
                "activity": activity,
                "location": location,
                "time": time_text,
                "people": people,
            }.items():
                if value and (not candidate.get(key) or len(value) > len(str(candidate.get(key) or ""))):
                    candidate[key] = value
            return
        seen.add(order_id)
        candidate = {
            "id": order_id,
            "summary": summary,
            "activity": activity,
            "location": location,
            "time": time_text,
            "people": people,
        }
        by_id[order_id] = candidate
        candidates.append(candidate)

    def add_confirmation_order_details(content: str) -> None:
        fields = _extract_confirmation_summary_fields(content)
        action_kind = str(fields.get("操作类型") or "").strip().lower()
        if action_kind != "order.create":
            return
        order_id = _extract_order_id_reference(content)
        if not order_id and candidates:
            order_id = candidates[0].get("id")
        if not order_id:
            return
        activity = str(fields.get("活动类型") or fields.get("类型") or "").strip()
        location = _field_value(fields, ("地点名称", "活动地点", "地点", "位置"))
        time_text = _field_value(fields, ("开始时间", "时间"))
        people = _field_value(fields, ("参与人数", "人数", "上限"))
        summary = " · ".join(part for part in [activity, location, time_text, people] if part)
        add_candidate(str(order_id), summary, activity, location, time_text, people)

    for item in reversed(history or []):
        if not isinstance(item, dict) or item.get("role") == "user":
            continue
        content = str(item.get("content") or "")
        if not content:
            continue

        parsed_orders = _parse_order_result_lines(content)
        for order in parsed_orders:
            summary = " · ".join(
                part for part in [
                    order.get("activity"),
                    order.get("location"),
                    order.get("time"),
                    order.get("people"),
                ]
                if part
            )
            add_candidate(
                order.get("id"),
                summary,
                order.get("activity"),
                order.get("location"),
                order.get("time"),
                order.get("people"),
            )

        if not parsed_orders:
            for line in content.splitlines():
                match = re.search(r"(?:订单|约伴|活动)\s*#?\s*(\d+)", line, flags=re.IGNORECASE)
                if match:
                    add_candidate(match.group(1), line.strip())
                    continue
                route_match = re.search(r"/orders/(\d+)", line, flags=re.IGNORECASE)
                if route_match:
                    add_candidate(route_match.group(1), line.strip())

        add_confirmation_order_details(content)

        if candidates and any(
            candidate.get("activity") or candidate.get("location") or candidate.get("time") or candidate.get("people")
            for candidate in candidates
        ):
            break
    return candidates[:5]


def _order_candidate_aliases(candidate: dict) -> list[str]:
    order_id = str(candidate.get("id") or "").strip()
    aliases = []
    if order_id:
        aliases.extend([order_id, f"订单{order_id}", f"订单#{order_id}", f"order{order_id}", f"order#{order_id}"])
    for key in ("activity", "location", "summary"):
        value = str(candidate.get(key) or "").strip()
        if not value:
            continue
        aliases.append(value)
        for part in re.split(r"[|｜·,，:：\s]+", value):
            part = part.strip()
            if len(part) >= 2:
                aliases.append(part)

    unique: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        normalized = _normalize_map_match_text(alias)
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(alias)
    return unique


def _match_recent_order_candidate(candidates: list[dict], user_message: str) -> dict | None:
    explicit_id = _extract_order_id_reference(user_message)
    if explicit_id:
        for candidate in candidates or []:
            if str(candidate.get("id") or "") == str(explicit_id):
                return candidate
        return {"id": str(explicit_id)}

    selected_index = _map_selection_index(user_message)
    if selected_index is not None:
        if selected_index < len(candidates or []):
            return candidates[selected_index]
        return None

    user_text = _normalize_map_match_text(user_message)
    if not user_text:
        return None

    scored: list[tuple[int, int, dict]] = []
    for index, candidate in enumerate(candidates or []):
        best_score = 0
        for alias in _order_candidate_aliases(candidate):
            normalized_alias = _normalize_map_match_text(alias)
            if normalized_alias and normalized_alias in user_text:
                best_score = max(best_score, len(normalized_alias))
        if best_score:
            scored.append((best_score, -index, candidate))

    if not scored:
        return None
    scored.sort(reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][2]


def _extract_contextual_order_selection(history: list, user_message: str) -> dict | None:
    candidates = _extract_recent_order_candidates(history)
    matched = _match_recent_order_candidate(candidates, user_message)
    if matched:
        return matched
    text = str(user_message or "")
    contextual_cues = (
        "这个订单",
        "这个约伴",
        "刚才的订单",
        "刚刚的订单",
        "刚创建的订单",
        "刚才创建",
        "配套动态",
        "基于这个",
        "宣传一下",
    )
    if len(candidates) == 1 and _has_any(text, contextual_cues):
        return candidates[0]
    return None


def _extract_content_id_reference(text: str) -> int | None:
    text = str(text or "")
    patterns = (
        r"(?:动态|帖子|内容)\s*(?:ID|id|编号|#|号)?\s*[:：#]?\s*(\d+)",
        r"\bcontent\s*#?\s*(\d+)\b",
        r"/contents/(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_recent_content_candidates(history: list) -> list[dict]:
    """Recover recent content-result candidates so follow-up comments/likes keep target context."""
    candidates: list[dict] = []
    seen: set[str] = set()

    def add_candidate(content_id: str, author: str = "", text: str = "") -> None:
        content_id = str(content_id or "").strip()
        if not content_id or content_id in seen:
            return
        seen.add(content_id)
        candidates.append({
            "id": content_id,
            "author": str(author or "").strip(),
            "text": str(text or "").strip(),
        })

    for item in reversed(history or []):
        if not isinstance(item, dict) or item.get("role") == "user":
            continue
        content = str(item.get("content") or "")
        if not content:
            continue

        parsed_contents = _parse_content_result_lines(content)
        for entry in parsed_contents:
            add_candidate(entry.get("id"), entry.get("author"), entry.get("text"))

        if not parsed_contents:
            for line in content.splitlines():
                match = re.search(r"(?:动态|帖子|内容)\s*#?\s*(\d+)", line, flags=re.IGNORECASE)
                if not match:
                    continue
                add_candidate(match.group(1), text=line.strip())

        if candidates:
            break
    return candidates[:5]


def _content_candidate_aliases(candidate: dict) -> list[str]:
    content_id = str(candidate.get("id") or "").strip()
    aliases = []
    if content_id:
        aliases.extend([content_id, f"动态{content_id}", f"动态#{content_id}", f"content{content_id}", f"content#{content_id}"])
    for key in ("author", "text"):
        value = str(candidate.get(key) or "").strip()
        if not value:
            continue
        aliases.append(value)
        for part in re.split(r"[|｜·,，:：\s]+", value):
            part = part.strip()
            if len(part) >= 2:
                aliases.append(part)

    unique: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        normalized = _normalize_map_match_text(alias)
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(alias)
    return unique


def _match_recent_content_candidate(candidates: list[dict], user_message: str) -> dict | None:
    explicit_id = _extract_content_id_reference(user_message)
    if explicit_id:
        for candidate in candidates or []:
            if str(candidate.get("id") or "") == str(explicit_id):
                return candidate
        return {"id": str(explicit_id)}

    selected_index = _map_selection_index(user_message)
    if selected_index is not None:
        if selected_index < len(candidates or []):
            return candidates[selected_index]
        return None

    user_text = _normalize_map_match_text(user_message)
    if not user_text:
        return None

    scored: list[tuple[int, int, dict]] = []
    for index, candidate in enumerate(candidates or []):
        best_score = 0
        for alias in _content_candidate_aliases(candidate):
            normalized_alias = _normalize_map_match_text(alias)
            if normalized_alias and normalized_alias in user_text:
                best_score = max(best_score, len(normalized_alias))
        if best_score:
            scored.append((best_score, -index, candidate))

    if not scored:
        return None
    scored.sort(reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][2]


def _extract_contextual_content_selection(history: list, user_message: str) -> dict | None:
    candidates = _extract_recent_content_candidates(history)
    return _match_recent_content_candidate(candidates, user_message)


def _extract_inline_comment_text(text: str) -> str:
    text = str(text or "").strip()
    patterns = (
        r"(?:评论(?:一下|一条|一句)?|回复(?:一下|一条|一句)?|留言(?:一下|一条|一句)?)[：:，,]?\s*(.{2,120})$",
        r"(?:帮我|给我)?(?:回一句|回一条)[：:，,]?\s*(.{2,120})$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = re.sub(r"(?:先生成确认草稿|不要直接发布|发布前先确认|先让我确认).*$", "", match.group(1)).strip()
        value = value.strip("：:，,。.!！ ")
        if value and not _has_any(value, ("评论", "回复", "留言", "点赞", "确认草稿")):
            return value[:120]
    return ""


def _detect_contextual_content_interact_shortcut(history: list, user_message: str) -> dict | None:
    """Route follow-ups like '就第一条评论一下' to a safe content interaction draft."""
    text = " ".join(str(user_message or "").split())
    if not text or _contains_blocking_write_negation(text):
        return None
    selected_content = _extract_contextual_content_selection(history, text)
    if not selected_content:
        return None

    lowered = text.lower()
    comment_cues = ("评论", "回复", "回一句", "回一条", "留言", "comment", "reply")
    like_cues = ("点赞", "赞一下", "点个赞", "like")
    wants_comment = _has_any(lowered, comment_cues)
    wants_like = _has_any(lowered, like_cues)
    if not wants_comment and not wants_like:
        return None

    missing_slots = []
    if wants_comment and not _extract_inline_comment_text(text):
        missing_slots.append("评论内容")

    return {
        "primary_intent": "content.interact",
        "domain": "content",
        "operation_type": "write",
        "requires_confirmation": True,
        "confidence": 0.9,
        "summary": "用户想基于上一轮动态搜索结果进行评论或点赞",
        "missing_slots": missing_slots,
        "suggested_agents": ["content_draft"],
        "next_action": "prepare_draft",
        "reviewed": False,
        "contextual_content_shortcut": True,
        "router_timeout": False,
    }


def _detect_contextual_order_content_create_shortcut(history: list, user_message: str) -> dict | None:
    """Route follow-ups like '就这个订单发条动态' to a safe content draft."""
    text = " ".join(str(user_message or "").split())
    if not text or _contains_blocking_write_negation(text):
        return None
    selected_order = _extract_contextual_order_selection(history, text)
    if not selected_order:
        return None

    content_cues = (
        "发动态",
        "发条动态",
        "发布动态",
        "写动态",
        "动态草稿",
        "配套动态",
        "宣传",
        "招募",
        "推广",
        "发帖",
        "写帖子",
        "post",
    )
    if not _has_any(text.lower(), content_cues):
        return None

    return {
        "primary_intent": "content.create",
        "domain": "content",
        "operation_type": "write",
        "requires_confirmation": True,
        "confidence": 0.9,
        "summary": "用户想基于上一轮约伴订单发布配套校园动态",
        "missing_slots": [],
        "suggested_agents": ["content_draft"],
        "next_action": "prepare_draft",
        "reviewed": False,
        "contextual_order_content_shortcut": True,
        "router_timeout": False,
    }


def _detect_contextual_map_content_create_shortcut(history: list, user_message: str) -> dict | None:
    """Route follow-ups like '就第一家写动态' to a safe content draft."""
    text = " ".join(str(user_message or "").split())
    if not text or _contains_blocking_write_negation(text):
        return None

    title, coords = _extract_contextual_map_selection(history, text)
    if not title and not coords:
        return None

    if not _has_any(text.lower(), CONTENT_CREATE_CUES):
        return None

    return {
        "primary_intent": "content.create",
        "domain": "content",
        "operation_type": "write",
        "requires_confirmation": True,
        "confidence": 0.9,
        "summary": "用户想基于上一轮地图地点发布校园动态",
        "missing_slots": [],
        "suggested_agents": ["content_draft"],
        "next_action": "prepare_draft",
        "reviewed": False,
        "contextual_map_content_shortcut": True,
        "router_timeout": False,
    }


def _infer_activity_label(text: str) -> str:
    lowered = str(text or "").lower()
    activity_rules = [
        (("篮球",), "BASKETBALL（篮球）"),
        (("羽毛球",), "BADMINTON（羽毛球）"),
        (("吃饭", "约饭", "餐厅", "饭店", "美食"), "MEAL（约饭）"),
        (("自习", "图书馆", "学习"), "STUDY（自习）"),
        (("电影", "影院", "电影院"), "MOVIE（电影）"),
        (("跑步", "夜跑", "操场"), "RUNNING（跑步）"),
        (("游戏", "开黑"), "GAME（游戏）"),
        (("按摩", "足疗", "洗脚", "推拿", "spa", "头疗"), "OTHER（足疗按摩）"),
    ]
    for cues, label in activity_rules:
        if any(cue in lowered for cue in cues):
            return label
    return ""


def _infer_campus_label(user_info: dict, text: str) -> str:
    text = str(text or "")
    if "中关村" in text:
        return "ZHONGGUANCUN（中关村校区）"
    if "良乡" in text:
        return "LIANGXIANG（良乡校区）"
    campus = str((user_info or {}).get("campus") or "").upper()
    campus_labels = {
        "LIANGXIANG": "LIANGXIANG（良乡校区）",
        "ZHONGGUANCUN": "ZHONGGUANCUN（中关村校区）",
        "ZHUHAI": "ZHUHAI（珠海校区）",
        "XISHAN": "XISHAN（西山校区）",
        "OTHER_CAMPUS": "OTHER_CAMPUS（其他校区）",
    }
    return campus_labels.get(campus, "")


def _set_artifact_field(fields: list, label_keywords: tuple[str, ...], label: str, value: str) -> None:
    if not value:
        return
    for item in fields:
        if not isinstance(item, dict):
            continue
        item_label = str(item.get("label") or item.get("name") or "")
        if any(keyword in item_label for keyword in label_keywords):
            current_value = str(item.get("value") or "").strip()
            if not current_value or current_value in {"待补充", "未填写", "None", "null"}:
                item["value"] = value
            return
    fields.append({"label": label, "value": value})


def _drop_missing_fields(missing_fields: list, keywords: tuple[str, ...]) -> list:
    return [
        field for field in (missing_fields or [])
        if not any(keyword in str(field) for keyword in keywords)
    ]


def _add_missing_field(missing_fields: list, label: str) -> list:
    current = [str(item) for item in (missing_fields or [])]
    if not any(label in item for item in current):
        current.append(label)
    return current


def _enrich_order_confirmation_fields(
    fields: list,
    missing_fields: list,
    user_info: dict,
    history: list,
    user_message: str,
    intent_analysis: dict,
) -> tuple[list, list]:
    primary_intent = (intent_analysis.get("primary_intent") or "").lower()
    if primary_intent not in {"order.create", "order.manage"}:
        return fields, missing_fields

    enriched_fields = [dict(item) if isinstance(item, dict) else item for item in (fields or [])]
    enriched_missing = list(missing_fields or [])
    context_text = _conversation_text(history, user_message)
    lowered_context = context_text.lower()

    if primary_intent == "order.manage":
        selected_order = _extract_contextual_order_selection(history, user_message) or {}
        selected_order_id = str(selected_order.get("id") or "").strip()
        order_id = _extract_order_id_reference(user_message)
        if not order_id and selected_order_id.isdigit():
            order_id = int(selected_order_id)
        if not order_id:
            order_id = _extract_order_id_reference(context_text)
        apply_id = _extract_application_id_reference(context_text)
        applicant_id = _extract_applicant_id_reference(context_text)

        if order_id:
            _set_artifact_field(enriched_fields, ("订单ID", "约伴ID", "活动ID"), "订单ID", str(order_id))
            enriched_missing = _drop_missing_fields(enriched_missing, ("订单ID", "约伴ID", "活动ID"))
        if selected_order.get("summary"):
            _set_artifact_field(enriched_fields, ("订单信息", "订单摘要", "活动信息"), "订单信息", selected_order["summary"])
        if apply_id:
            _set_artifact_field(enriched_fields, ("申请ID", "申请记录ID", "申请编号"), "申请ID", str(apply_id))
            enriched_missing = _drop_missing_fields(enriched_missing, ("申请ID", "申请记录ID", "申请编号"))
        if applicant_id:
            _set_artifact_field(enriched_fields, ("申请者ID", "申请用户ID", "用户ID"), "申请者ID", str(applicant_id))
            enriched_missing = _drop_missing_fields(enriched_missing, ("申请者ID", "申请用户ID", "用户ID"))

        if _has_any(lowered_context, ("取消报名", "撤销报名", "取消申请", "撤销申请", "cancel my application", "withdraw application")):
            if not order_id:
                enriched_missing = _add_missing_field(enriched_missing, "订单ID")
        elif (
            _has_any(lowered_context, ("拒绝申请", "驳回申请", "不同意申请", "拒绝加入", "reject application", "deny application"))
            or (_has_any(lowered_context, ("拒绝", "驳回", "不同意")) and "申请" in lowered_context)
        ):
            if not apply_id:
                enriched_missing = _add_missing_field(enriched_missing, "申请ID")
        elif _has_any(context_text, ("接受申请", "同意申请", "通过申请", "同意加入", "通过一下", "同意一下")):
            if not order_id:
                enriched_missing = _add_missing_field(enriched_missing, "订单ID")
            if not applicant_id:
                enriched_missing = _add_missing_field(enriched_missing, "申请者ID")
        elif _has_any(context_text, ("完成订单", "标记完成", "订单完成", "结束订单")):
            if not order_id:
                enriched_missing = _add_missing_field(enriched_missing, "订单ID")
        return enriched_fields, enriched_missing

    location_title, coords = _extract_contextual_map_selection(history, user_message)

    if location_title:
        _set_artifact_field(enriched_fields, ("地点名称", "地点", "位置"), "地点名称", location_title)
        enriched_missing = _drop_missing_fields(enriched_missing, ("地点", "位置"))
    if coords:
        _set_artifact_field(enriched_fields, ("地点坐标", "坐标"), "地点坐标", coords)
        enriched_missing = _drop_missing_fields(enriched_missing, ("地点", "位置", "坐标"))

    activity_label = _infer_activity_label(context_text)
    if activity_label:
        _set_artifact_field(enriched_fields, ("活动类型", "类型"), "活动类型", activity_label)
        enriched_missing = _drop_missing_fields(enriched_missing, ("活动类型", "类型"))

    campus_label = _infer_campus_label(user_info, context_text)
    if campus_label:
        _set_artifact_field(enriched_fields, ("校区",), "校区", campus_label)
        enriched_missing = _drop_missing_fields(enriched_missing, ("校区",))

    group_size = _extract_group_size(context_text)
    if group_size:
        _set_artifact_field(enriched_fields, ("参与人数", "人数", "人"), "参与人数", f"{group_size}人")
        enriched_missing = _drop_missing_fields(enriched_missing, ("参与人数", "人数", "人"))

    return enriched_fields, enriched_missing


def _order_activity_display(activity: str) -> str:
    value = str(activity or "").strip()
    if not value:
        return "校园活动"
    match = re.search(r"[（(]([^）)]+)[）)]", value)
    if match:
        return match.group(1).strip() or value
    activity_map = {
        "BASKETBALL": "篮球",
        "BADMINTON": "羽毛球",
        "MEAL": "约饭",
        "STUDY": "自习",
        "MOVIE": "看电影",
        "RUNNING": "跑步",
        "GAME": "开黑",
        "OTHER": "校园活动",
    }
    return activity_map.get(value.upper(), value)


def _order_candidate_summary_text(order: dict) -> str:
    summary = str(order.get("summary") or "").strip()
    if summary:
        return summary
    return " · ".join(
        part
        for part in [
            order.get("activity"),
            order.get("location"),
            order.get("time"),
            order.get("people"),
        ]
        if part
    )


def _build_order_content_draft_text(order: dict) -> str:
    order_id = str(order.get("id") or "").strip()
    activity = _order_activity_display(order.get("activity") or "")
    location = str(order.get("location") or "").strip()
    time_text = str(order.get("time") or "").strip()
    people = str(order.get("people") or "").strip()

    opening_parts = []
    if time_text:
        opening_parts.append(time_text)
    if location:
        opening_parts.append(f"在{location}")
    opening = "".join(opening_parts)
    if opening:
        opening = f"{opening}有一场{activity}约伴"
    else:
        opening = f"这里有一场{activity}约伴"

    details = []
    if people:
        details.append(f"名额：{people}")
    if order_id:
        details.append(f"订单#{order_id}")
    detail_text = "，".join(details)
    if detail_text:
        return f"{opening}，{detail_text}。感兴趣的同学可以一起加入，确认行程前记得看看订单详情。"
    return f"{opening}。感兴趣的同学可以一起加入，确认行程前记得看看订单详情。"


def _build_map_content_draft_text(place_title: str, context_text: str) -> str:
    place = str(place_title or "").strip()
    activity = _order_activity_display(_infer_activity_label(context_text))
    group_size = _extract_group_size(context_text)

    subject = place or "这个地点"
    if activity and activity != "校园活动":
        subject = f"{subject}{activity}"

    group_prefix = f"想约{group_size}人一起去" if group_size else "想找同学一起去"
    return f"{group_prefix}{subject}，有兴趣的同学可以一起聊聊时间和人数。出发前我们再确认地点和安排。"


def _enrich_content_confirmation_fields(
    fields: list,
    missing_fields: list,
    history: list,
    user_message: str,
    intent_analysis: dict,
) -> tuple[list, list]:
    primary_intent = (intent_analysis.get("primary_intent") or "").lower()
    if primary_intent not in {"content.interact", "content.create"}:
        return fields, missing_fields

    enriched_fields = [dict(item) if isinstance(item, dict) else item for item in (fields or [])]
    enriched_missing = list(missing_fields or [])

    if primary_intent == "content.create":
        selected_order = _extract_contextual_order_selection(history, user_message) or {}
        selected_order_id = str(selected_order.get("id") or "").strip()
        if not selected_order:
            location_title, coords = _extract_contextual_map_selection(history, user_message)
            if not location_title and not coords:
                return enriched_fields, enriched_missing

            context_text = _conversation_text(history, user_message)
            if location_title:
                _set_artifact_field(enriched_fields, ("地点名称", "地点", "位置"), "地点名称", location_title)
                enriched_missing = _drop_missing_fields(enriched_missing, ("地点名称", "地点", "位置"))
            if coords:
                _set_artifact_field(enriched_fields, ("地点坐标", "坐标"), "地点坐标", coords)
                enriched_missing = _drop_missing_fields(enriched_missing, ("地点坐标", "坐标"))

            draft_text = _build_map_content_draft_text(location_title, context_text)
            if draft_text:
                _set_artifact_field(enriched_fields, ("动态内容", "正文", "内容", "文本"), "动态内容", draft_text)
                enriched_missing = _drop_missing_fields(enriched_missing, ("动态内容", "正文", "内容", "文本"))

            enriched_missing = _drop_missing_fields(enriched_missing, ("订单ID", "关联订单"))
            _set_artifact_field(enriched_fields, ("媒体类型", "mediaType"), "媒体类型", "TEXT_ONLY")
            return enriched_fields, enriched_missing

        if selected_order_id:
            _set_artifact_field(enriched_fields, ("订单ID", "关联订单"), "订单ID", selected_order_id)
            enriched_missing = _drop_missing_fields(enriched_missing, ("订单ID", "关联订单"))

        order_summary = _order_candidate_summary_text(selected_order)
        if order_summary:
            _set_artifact_field(enriched_fields, ("订单信息", "订单摘要", "活动信息"), "订单信息", order_summary)

        draft_text = _build_order_content_draft_text(selected_order)
        if draft_text:
            _set_artifact_field(enriched_fields, ("动态内容", "正文", "内容", "文本"), "动态内容", draft_text)
            enriched_missing = _drop_missing_fields(enriched_missing, ("动态内容", "正文", "内容", "文本"))

        _set_artifact_field(enriched_fields, ("媒体类型", "mediaType"), "媒体类型", "TEXT_ONLY")
        return enriched_fields, enriched_missing

    selected_content = _extract_contextual_content_selection(history, user_message) or {}
    selected_content_id = str(selected_content.get("id") or "").strip()
    content_id = _extract_content_id_reference(user_message)
    if not content_id and selected_content_id.isdigit():
        content_id = int(selected_content_id)

    if content_id:
        _set_artifact_field(enriched_fields, ("动态ID", "帖子ID", "内容ID"), "动态ID", str(content_id))
        enriched_missing = _drop_missing_fields(enriched_missing, ("动态ID", "帖子ID", "内容ID"))

    summary_parts = []
    author = str(selected_content.get("author") or "").strip()
    text = str(selected_content.get("text") or "").strip()
    if author:
        summary_parts.append(author)
    if text:
        summary_parts.append(text)
    if summary_parts:
        _set_artifact_field(enriched_fields, ("动态信息", "动态摘要", "帖子信息", "内容信息"), "动态信息", " — ".join(summary_parts))

    inline_comment = _extract_inline_comment_text(user_message)
    if inline_comment:
        _set_artifact_field(
            enriched_fields,
            ("评论内容", "评论文本", "回复内容", "留言内容"),
            "评论内容",
            inline_comment,
        )
        enriched_missing = _drop_missing_fields(enriched_missing, ("评论内容", "评论文本", "回复内容", "留言内容"))

    return enriched_fields, enriched_missing


def _is_confirmed_artifact_message(text: str) -> bool:
    text = str(text or "")
    return any(cue in text for cue in (
        "我确认执行这个草稿",
        "我确认按修改后的内容执行这个草稿",
        "确认执行这个草稿",
    ))


def _is_short_confirmation_message(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw or len(raw) > 24:
        return False
    lowered = raw.lower()
    if any(cue in lowered for cue in (
        "取消",
        "修改",
        "先别",
        "不要",
        "等等",
        "等一下",
        "再改",
        "no",
        "not",
        "cancel",
        "edit",
        "change",
    )):
        return False
    normalized = re.sub(r"[\s。.!！,，、；;:：]+", "", lowered)
    return normalized in {
        "确认",
        "确认执行",
        "可以执行",
        "执行",
        "执行吧",
        "没问题",
        "确认没问题",
        "就这样",
        "可以",
        "好的",
        "好",
        "ok",
        "okay",
        "yes",
        "y",
        "go",
        "goahead",
    }


def _parse_confirmed_artifact_fields(text: str) -> dict:
    fields = {}
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip().lstrip("-*•").strip()
        if not line or ("：" not in line and ":" not in line):
            continue
        separator = "：" if "：" in line else ":"
        label, value = line.split(separator, 1)
        label = label.strip()
        value = value.strip()
        if label and value:
            fields[label] = value
    return fields


def _build_confirmation_summary_lines(artifact: dict) -> list[str]:
    lines = []
    title = str((artifact or {}).get("title") or "").strip()
    action_kind = str((artifact or {}).get("actionKind") or (artifact or {}).get("action_kind") or "").strip()
    if title:
        lines.append(f"标题: {title}")
    if action_kind:
        lines.append(f"操作类型: {action_kind}")
    for field in (artifact or {}).get("fields") or []:
        if not isinstance(field, dict):
            continue
        label = str(field.get("label") or "").strip()
        if not label:
            continue
        value = str(field.get("value") or "").strip()
        if field.get("missing") and value in {"", "待补充", "未填写", "None", "null"}:
            value = "待补充"
        if value:
            lines.append(f"{label}: {value}")
    return lines


def _append_confirmation_summary_to_reply(reply: str, artifact: dict) -> str:
    base = str(reply or "").strip()
    if "确认草稿摘要" in base:
        return base
    summary_lines = _build_confirmation_summary_lines(artifact)
    if not summary_lines:
        return base
    missing_fields = (artifact or {}).get("missingFields") or []
    next_tip = (
        "请先补充待补充字段，再点击确认执行。"
        if missing_fields
        else "确认无误后，可以点击确认执行，或直接回复“确认”。"
    )
    summary = "\n".join(f"- {line}" for line in summary_lines)
    return f"{base}\n\n确认草稿摘要：\n{summary}\n\n{next_tip}".strip()


def _extract_confirmation_summary_fields(content: str) -> dict:
    text = str(content or "")
    if "确认草稿摘要" not in text:
        return {}
    summary_text = text.split("确认草稿摘要", 1)[1]
    lines = []
    for raw_line in summary_text.splitlines():
        line = raw_line.strip().lstrip("-*•").strip()
        if not line:
            continue
        if line.startswith(("确认无误后", "请先补充")):
            break
        if "：" in line or ":" in line:
            lines.append(line)
    return _parse_confirmed_artifact_fields("\n".join(lines)) if lines else {}


def _extract_recent_confirmation_summary(history: list) -> list[str]:
    for item in reversed(history or []):
        if not isinstance(item, dict) or item.get("role") != "assistant":
            continue
        content = str(item.get("content") or "")
        if "确认草稿摘要" not in content:
            continue
        summary_text = content.split("确认草稿摘要", 1)[1]
        lines = []
        for raw_line in summary_text.splitlines():
            line = raw_line.strip().lstrip("-*•").strip()
            if not line:
                continue
            if line.startswith(("确认无误后", "请先补充")):
                break
            if "：" in line or ":" in line:
                lines.append(line)
        if lines:
            return lines
    return []


def _build_confirmed_message_from_recent_summary(history: list, user_message: str) -> str:
    if not _is_short_confirmation_message(user_message):
        return ""
    lines = _extract_recent_confirmation_summary(history)
    if not lines:
        return ""
    fields = _parse_confirmed_artifact_fields("\n".join(lines))
    title = fields.get("标题") or "最近确认草稿"
    return f"我确认执行这个草稿：{title}\n" + "\n".join(lines)


def _field_value(fields: dict, keywords: tuple[str, ...]) -> str:
    for label, value in fields.items():
        if any(keyword in label for keyword in keywords):
            return str(value).strip()
    return ""


def _field_int(fields: dict, keywords: tuple[str, ...]) -> int | None:
    return _extract_first_int(_field_value(fields, keywords))


def _comment_text_from_fields(fields: dict) -> str:
    for label, value in fields.items():
        label_text = str(label)
        if any(keyword in label_text for keyword in ("评论内容", "评论文本", "回复内容", "留言内容")):
            return str(value).strip()
    for label, value in fields.items():
        label_text = str(label)
        if (
            any(keyword in label_text for keyword in ("评论", "回复", "留言"))
            and not any(id_key in label_text for id_key in ("ID", "编号", "申请"))
        ):
            return str(value).strip()
    return ""


def _normalize_activity_type(value: str, context: str = "") -> str:
    text = f"{value} {context}".upper()
    rules = [
        ("BASKETBALL", ("BASKETBALL", "篮球")),
        ("BADMINTON", ("BADMINTON", "羽毛球")),
        ("MEAL", ("MEAL", "吃饭", "约饭", "餐厅", "饭店", "美食")),
        ("STUDY", ("STUDY", "自习", "图书馆", "学习")),
        ("MOVIE", ("MOVIE", "电影", "影院", "电影院")),
        ("RUNNING", ("RUNNING", "跑步", "夜跑", "操场")),
        ("GAME", ("GAME", "游戏", "开黑")),
        ("OTHER", ("OTHER", "按摩", "足疗", "洗脚", "推拿", "SPA", "头疗", "约伴")),
    ]
    for normalized, cues in rules:
        if any(cue.upper() in text for cue in cues):
            return normalized
    return "OTHER"


def _normalize_campus(value: str, context: str = "") -> str:
    text = f"{value} {context}".upper()
    rules = [
        ("LIANGXIANG", ("LIANGXIANG", "良乡")),
        ("ZHONGGUANCUN", ("ZHONGGUANCUN", "中关村")),
        ("ZHUHAI", ("ZHUHAI", "珠海")),
        ("XISHAN", ("XISHAN", "西山")),
        ("OTHER_CAMPUS", ("OTHER_CAMPUS", "其他校区")),
    ]
    for normalized, cues in rules:
        if any(cue.upper() in text for cue in cues):
            return normalized
    return ""


def _normalize_gender_require(value: str) -> str:
    text = str(value or "").upper()
    if any(cue in text for cue in ("FEMALE", "女")):
        return "FEMALE"
    if any(cue in text for cue in ("MALE", "男")):
        return "MALE"
    return "ANY"


def _extract_first_int(value: str) -> int | None:
    text = str(value or "")
    match = re.search(r"\d{1,3}", text)
    if match:
        parsed = int(match.group(0))
        return parsed if parsed > 0 else None
    return _extract_group_size(text)


def _parse_hour_token(value: str) -> int | None:
    value = str(value or "").strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    return _parse_small_chinese_number(value)


def _normalize_start_time(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    normalized = text.replace("/", "-")
    match = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", normalized)
    if match:
        year, month, day, hour, minute, second = match.groups()
        dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second or 0))
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日?\s*([0-9一二两三四五六七八九十]{1,3})[点时:：](\d{1,2})?", text)
    if match:
        year, month, day, hour_token, minute = match.groups()
        hour = _parse_hour_token(hour_token)
        if hour is not None:
            if any(cue in text for cue in ("下午", "晚上", "今晚")) and hour < 12:
                hour += 12
            dt = datetime(int(year), int(month), int(day), hour, int(minute or 0), 0)
            return dt.strftime("%Y-%m-%d %H:%M:%S")

    day_offset = None
    if "后天" in text:
        day_offset = 2
    elif any(cue in text for cue in ("明天", "明晚", "明早", "明日")):
        day_offset = 1
    elif any(cue in text for cue in ("今天", "今晚")):
        day_offset = 0

    match = re.search(r"([0-9一二两三四五六七八九十]{1,3})[点时:：](\d{1,2})?", text)
    if day_offset is not None and match:
        hour = _parse_hour_token(match.group(1))
        if hour is not None:
            if any(cue in text for cue in ("下午", "晚上", "今晚", "明晚")) and hour < 12:
                hour += 12
            minute = int(match.group(2) or 0)
            dt = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=day_offset)
            return dt.strftime("%Y-%m-%d %H:%M:%S")

    return ""


def _current_user_id(user_info: dict) -> int | None:
    for key in ("uid", "id", "user_id", "userId"):
        value = (user_info or {}).get(key)
        if value is None:
            continue
        try:
            parsed = int(value)
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            continue
    return None


CONFIRMED_ACTION_KINDS = {
    "order.create",
    "content.create",
    "content.comment",
    "content.like",
    "order.apply",
    "order.cancel_apply",
    "order.accept",
    "order.reject_apply",
    "order.complete",
    "memory.manage",
    "other.write",
}


def _normalize_confirmed_action_kind(value: str) -> str:
    normalized = str(value or "").strip().strip("`").lower()
    return normalized if normalized in CONFIRMED_ACTION_KINDS else ""


def _infer_confirmed_action_kind(text: str, fields: dict) -> str:
    lowered = str(text or "").lower()
    field_labels = " ".join(fields.keys())
    explicit_action_kind = _normalize_confirmed_action_kind(
        _field_value(fields, ("操作类型", "action_kind", "actionKind", "action kind"))
    )
    if explicit_action_kind:
        return explicit_action_kind
    if any(cue in lowered for cue in (
        "取消报名",
        "撤销报名",
        "取消申请",
        "撤销申请",
        "取消加入",
        "退出订单",
        "退出活动",
        "cancel my application",
        "withdraw application",
        "cancel application",
        "leave order",
    )):
        return "order.cancel_apply"
    if (
        any(cue in lowered for cue in ("拒绝申请", "驳回申请", "不同意申请", "拒绝加入", "reject application", "deny application"))
        or (any(cue in lowered for cue in ("拒绝", "驳回", "不同意")) and "申请" in lowered)
    ):
        return "order.reject_apply"
    if any(cue in lowered for cue in ("取消订单", "取消活动", "cancel order", "cancel activity")):
        return "other.write"
    if any(cue in lowered for cue in ("申请加入", "报名", "加入订单", "加入活动")):
        return "order.apply"
    if any(cue in lowered for cue in ("评论", "回复动态", "给动态回复")) or _comment_text_from_fields(fields):
        return "content.comment"
    if any(cue in lowered for cue in ("点赞", "赞一下", "点个赞")):
        return "content.like"
    if any(cue in lowered for cue in ("接受申请", "同意加入", "通过申请")) or _field_value(fields, ("申请者ID", "申请用户ID", "accepter")):
        return "order.accept"
    if any(cue in lowered for cue in ("完成订单", "标记完成")):
        return "order.complete"
    if "memory.manage" in lowered or "记忆" in lowered or "记住" in lowered or "偏好" in field_labels:
        return "memory.manage"
    if "动态" in lowered or "动态" in field_labels or _field_value(fields, ("动态内容", "正文", "内容")):
        return "content.create"
    if "约伴" in lowered or "订单" in lowered or "活动类型" in field_labels:
        return "order.create"
    return "other.write"


def _resolve_confirmation_action_kind(draft: dict, intent_analysis: dict, user_message: str) -> str:
    explicit = _normalize_confirmed_action_kind(draft.get("action_kind") if isinstance(draft, dict) else "")
    if explicit:
        return explicit

    primary_intent = _normalize_confirmed_action_kind((intent_analysis or {}).get("primary_intent"))
    if primary_intent:
        return primary_intent

    inferred = _infer_confirmed_action_kind(user_message, {})
    if inferred != "other.write":
        return inferred

    return str((intent_analysis or {}).get("primary_intent") or "other.write")


def _intent_for_confirmed_execution(action_kind: str) -> dict:
    domain = (
        "content" if action_kind.startswith("content.")
        else "order" if action_kind.startswith("order.")
        else "memory" if action_kind == "memory.manage"
        else "other"
    )
    return {
        "primary_intent": action_kind,
        "domain": domain,
        "operation_type": "write",
        "requires_confirmation": False,
        "confidence": 1.0,
        "summary": "用户已确认执行结构化草稿",
        "missing_slots": [],
        "suggested_agents": [],
        "next_action": "execute_confirmed_write",
        "confirmation_confirmed": True,
    }


def _plain_result_text(result_text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", str(result_text or ""))
    text = text.replace("✅", "").strip()
    return text or "操作已返回结果"


def _extract_route_from_result_text(result_text: str) -> str:
    match = re.search(r"\]\((/(?:orders|contents)/\d+)\)", str(result_text or ""))
    return match.group(1) if match else ""


def _confirmed_action_title(action_kind: str, success: bool) -> str:
    if not success:
        return "操作未完成"
    titles = {
        "order.create": "约伴订单已创建",
        "content.create": "校园动态已发布",
        "content.comment": "评论已发表",
        "content.like": "动态互动已完成",
        "order.apply": "报名申请已提交",
        "order.cancel_apply": "报名申请已撤销",
        "order.accept": "申请已接受",
        "order.reject_apply": "申请已拒绝",
        "order.complete": "订单已标记完成",
        "memory.manage": "长期记忆已更新",
    }
    return titles.get(action_kind, "操作已完成")


def _confirmed_action_route(action_kind: str, args: dict, result_text: str) -> str:
    route = _extract_route_from_result_text(result_text)
    if route:
        return route
    if action_kind.startswith("content."):
        content_id = args.get("content_id")
        return f"/contents/{content_id}" if content_id else ""
    order_id = args.get("order_id")
    return f"/orders/{order_id}" if order_id else ""


def _build_confirmed_execution_artifact(action_kind: str, result_text: str, args: dict) -> dict:
    success = "失败" not in str(result_text or "") and "不能" not in str(result_text or "")
    route = _confirmed_action_route(action_kind, args, result_text)
    result_summary = _plain_result_text(result_text)
    artifact_type = (
        "content" if action_kind.startswith("content.")
        else "order" if action_kind.startswith("order.")
        else "memory" if action_kind == "memory.manage"
        else "guide"
    )
    fields = [
        {"label": "执行状态", "value": "已完成" if success else "未完成"},
        {"label": "操作类型", "value": action_kind},
        {"label": "结果摘要", "value": result_summary},
    ]

    if args.get("order_id"):
        fields.insert(2, {"label": "订单ID", "value": str(args.get("order_id"))})
    if args.get("content_id"):
        fields.insert(2, {"label": "动态ID", "value": str(args.get("content_id"))})
    if args.get("apply_id"):
        fields.insert(2, {"label": "申请ID", "value": str(args.get("apply_id"))})
    if args.get("accepter_id"):
        fields.insert(3, {"label": "申请者ID", "value": str(args.get("accepter_id"))})
    if action_kind == "memory.manage":
        operation_label = "删除" if args.get("operation") == "delete" else "保存"
        fields.insert(2, {"label": "记忆操作", "value": operation_label})
        if args.get("category"):
            fields.insert(3, {"label": "记忆分类", "value": str(args.get("category"))})
        if args.get("content"):
            fields.insert(4, {"label": "记忆内容", "value": str(args.get("content"))})

    actions = []
    if route:
        actions.append({
            "label": "查看详情",
            "route": route,
            "primary": True,
        })
    if action_kind == "order.create":
        actions.append({
            "label": "发布配套动态",
            "prompt": "基于刚才创建的约伴订单，帮我整理一条校园动态草稿，发布前先让我确认。",
        })
    elif action_kind == "content.create":
        actions.append({
            "label": "继续搜索相关动态",
            "prompt": "帮我看看最近有没有相关校园动态，先只查询不要评论或点赞。",
        })
    elif action_kind.startswith("order."):
        actions.append({
            "label": "查看我的订单",
            "prompt": "帮我看看我最近发布和参与的约伴订单，先只查询。",
        })
    elif action_kind.startswith("content."):
        actions.append({
            "label": "查看相关动态",
            "prompt": "帮我看看这条动态附近还有哪些相关评论或校园动态，先只查询。",
        })
    elif action_kind == "memory.manage":
        actions.append({
            "label": "打开 AI 记忆",
            "memoryPanel": True,
            "primary": True,
        })

    return {
        "type": artifact_type,
        "title": _confirmed_action_title(action_kind, success),
        "description": "已把确认后的执行结果整理成可操作卡片。",
        "fields": fields,
        "actions": actions,
        "state": "completed" if success else "failed",
        "intent": {
            "primary_intent": action_kind,
            "next_action": "execute_confirmed_write",
        },
    }


async def _confirmed_success_response(result_text: str, tool_name: str, args: dict, intent: dict) -> dict:
    action_kind = intent.get("primary_intent") or "other.write"
    artifact = _build_confirmed_execution_artifact(action_kind, result_text, args)
    await _emit_event("artifact", artifact)
    return {
        "reply": result_text,
        "tool_calls": [{"name": tool_name, "args": args}],
        "intent": intent,
        "artifacts": [artifact],
    }


def _normalize_memory_operation(value: str, fallback_text: str = "") -> str:
    text = f"{value or ''} {fallback_text or ''}".lower()
    if any(cue in text for cue in ("delete", "remove", "forget", "忘记", "删除", "移除", "取消记住", "别记")):
        return "delete"
    return "save"


def _normalize_memory_category(value: str, content: str = "") -> str:
    text = f"{value or ''} {content or ''}".lower()
    if any(cue in text for cue in ("behavior", "habit", "行为", "习惯", "经常", "常去")):
        return "behavior"
    if any(cue in text for cue in ("fact", "事实", "资料", "学院", "专业", "年级", "来自", "住在", "就读")):
        return "fact"
    return "preference"


def _memory_field_value(fields: dict, labels: tuple[str, ...]) -> str:
    normalized_labels = {str(label).lower() for label in labels}
    for label, value in fields.items():
        label_text = str(label or "").strip()
        label_key = label_text.lower()
        if label_key in normalized_labels:
            return str(value).strip()
    for label, value in fields.items():
        label_text = str(label or "")
        if "操作类型" in label_text or "记忆操作" in label_text or "记忆分类" in label_text:
            continue
        if any(keyword in label_text for keyword in labels):
            return str(value).strip()
    return ""


def _memory_content_from_fields(fields: dict, user_message: str) -> str:
    content = _memory_field_value(fields, ("记忆内容", "偏好内容", "长期信息", "memory_content", "content"))
    if content and content not in {"待补充", "未填写", "None", "null"}:
        return content.strip()

    cleaned = re.sub(r"^我确认执行这个草稿[:：]?.*", "", str(user_message or ""), flags=re.MULTILINE).strip()
    cleaned = re.sub(r"^操作类型[:：]\s*memory\.manage\s*$", "", cleaned, flags=re.MULTILINE).strip()
    return cleaned[:120].strip()


def _sanitize_memory_content(content: str) -> str:
    return re.sub(r"\s+", " ", str(content or "")).strip()


def _compact_memory_policy_text(value: str) -> str:
    return re.sub(r"[\s\W_，。！？；：、“”‘’（）()【】《》「」『』·]+", "", str(value or "").lower())


def _memory_contains_any(compact: str, markers: tuple[str, ...]) -> bool:
    return any(marker in compact for marker in markers)


def _normalize_extracted_memory_category(category: str, content: str = "") -> str:
    text = f"{category or ''} {content or ''}".lower()
    if any(cue in text for cue in ("preference", "偏好", "喜欢", "不吃", "爱吃")):
        return "preference"
    if any(cue in text for cue in ("behavior", "habit", "行为", "习惯", "经常", "常去")):
        return "behavior"
    if any(cue in text for cue in ("fact", "事实", "资料", "学院", "专业", "年级", "来自", "住在", "就读")):
        return "fact"
    return ""


def _is_no_signal_memory(compact: str) -> bool:
    return compact == "none" or _memory_contains_any(compact, MEMORY_NO_SIGNAL_MARKERS)


def _should_keep_extracted_memory(category: str, content: str, user_message: str = "", assistant_reply: str = "") -> bool:
    if not category or not content:
        return False
    if len(content) < 6 or len(content) > 120:
        return False
    if MEMORY_COORDINATE_RE.search(content):
        return False

    compact = _compact_memory_policy_text(content)
    if not compact:
        return False
    if _is_no_signal_memory(compact) or _memory_contains_any(compact, MEMORY_LOW_CONFIDENCE_MARKERS):
        return False
    if _memory_contains_any(compact, MEMORY_STRICT_TRANSIENT_MARKERS):
        return False
    if any(compact.startswith(prefix) for prefix in MEMORY_ONE_OFF_PREFIXES):
        return False
    if _memory_contains_any(compact, MEMORY_SOFT_TRANSIENT_MARKERS) and not _memory_contains_any(compact, MEMORY_DURABLE_MARKERS):
        return False

    user_compact = _compact_memory_policy_text(user_message)
    assistant_compact = _compact_memory_policy_text(assistant_reply)
    looks_like_tool_result = assistant_compact and compact in assistant_compact and compact not in user_compact
    if looks_like_tool_result and not _memory_contains_any(compact, MEMORY_DURABLE_MARKERS):
        return False

    return _memory_contains_any(compact, MEMORY_DURABLE_MARKERS) or (
        category == "fact" and _memory_contains_any(compact, MEMORY_STABLE_FACT_MARKERS)
    )


def filter_extracted_memories(memories: list, user_message: str = "", assistant_reply: str = "") -> list[dict]:
    """Keep only durable user memories from raw LLM extraction output."""
    filtered: list[dict] = []
    seen: set[str] = set()
    for item in memories or []:
        if len(filtered) >= MAX_EXTRACTED_MEMORIES_PER_TURN:
            break
        if not isinstance(item, dict):
            continue
        content = _sanitize_memory_content(item.get("content", ""))
        category = _normalize_extracted_memory_category(item.get("category", ""), content)
        if not _should_keep_extracted_memory(category, content, user_message, assistant_reply):
            continue
        normalized = _compact_memory_policy_text(content)
        if normalized in seen:
            continue
        seen.add(normalized)
        filtered.append({"category": category, "content": content})
    return filtered


async def _execute_confirmed_memory(user_info: dict, fields: dict, user_message: str) -> dict:
    operation = _normalize_memory_operation(
        _memory_field_value(fields, ("记忆操作", "operation", "动作")),
        user_message,
    )
    content = _memory_content_from_fields(fields, user_message)
    category = _normalize_memory_category(
        _memory_field_value(fields, ("记忆分类", "category", "分类")),
        content,
    )
    intent = _intent_for_confirmed_execution("memory.manage")

    if not content:
        return {
            "reply": "这条记忆草稿里缺少“记忆内容”，请先补充要保存或删除的长期信息。",
            "tool_calls": [],
            "intent": intent,
        }

    commit = {
        "operation": operation,
        "category": category,
        "content": content,
        "source": "confirmed-chat",
        "phase": "memory",
        "title": "提交长期记忆变更",
        "detail": ("删除匹配记忆：" if operation == "delete" else "保存长期记忆：") + content,
        "state": "completed",
    }
    await _emit_event("agent_step", {
        "phase": "memory",
        "title": "确认长期记忆",
        "detail": "正在把已确认的记忆变更交给后端持久化",
        "state": "running",
    })
    await _emit_event("memory_commit", commit)
    await _emit_event("agent_step", {
        "phase": "memory",
        "title": "长期记忆已提交",
        "detail": "后端会保存或删除匹配的长期记忆，并在 AI 记忆面板中同步",
        "state": "completed",
    })

    result_text = (
        f"✅ 已确认删除这条长期记忆：{content}"
        if operation == "delete"
        else f"✅ 已确认保存这条长期记忆：{content}"
    )
    args = {
        "operation": operation,
        "category": category,
        "content": content,
    }
    artifact = _build_confirmed_execution_artifact("memory.manage", result_text, args)
    await _emit_event("artifact", artifact)
    return {
        "reply": result_text,
        "tool_calls": [{"name": "commit_memory", "args": args}],
        "intent": intent,
        "artifacts": [artifact],
        "memory_commits": [commit],
    }


async def _execute_confirmed_order(user_info: dict, fields: dict, user_message: str) -> dict:
    user_id = _current_user_id(user_info)
    context_text = user_message
    activity_value = _field_value(fields, ("活动类型", "类型"))
    campus_value = _field_value(fields, ("校区",))
    location = _field_value(fields, ("地点名称", "活动地点", "地点", "位置"))
    start_time_value = _field_value(fields, ("开始时间", "时间"))
    people_value = _field_value(fields, ("参与人数", "人数", "上限"))
    gender_value = _field_value(fields, ("性别", "性别要求"))
    coords = _field_value(fields, ("地点坐标", "坐标"))
    note = _field_value(fields, ("备注", "说明"))

    args = {
        "user_id": user_id,
        "activity_type": _normalize_activity_type(activity_value, context_text),
        "campus": _normalize_campus(campus_value, context_text),
        "location": location,
        "start_time": _normalize_start_time(start_time_value),
        "gender_require": _normalize_gender_require(gender_value),
        "max_people": _extract_first_int(people_value),
        "note": note or (f"地点坐标：{coords}" if coords else ""),
    }
    missing = []
    if not args["user_id"]:
        missing.append("用户ID")
    if not args["campus"]:
        missing.append("校区")
    if not args["location"]:
        missing.append("地点")
    if not args["start_time"]:
        missing.append("时间（请使用 yyyy-MM-dd HH:mm:ss 或“明天晚上7点”这类格式）")
    if not args["max_people"]:
        missing.append("参与人数")

    intent = _intent_for_confirmed_execution("order.create")
    if missing:
        return {
            "reply": "我还不能执行这个订单草稿，缺少或无法解析：" + "、".join(missing) + "。请点击修改草稿补充后再确认。",
            "tool_calls": [],
            "intent": {**intent, "missing_slots": missing, "requires_confirmation": True, "next_action": "prepare_draft"},
        }

    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "执行已确认订单",
        "detail": "已收到完整确认草稿，正在调用订单创建工具",
        "state": "running",
    })
    result_text = await create_order.ainvoke(args)
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "订单执行完成",
        "detail": "订单创建工具已返回结果",
        "state": "completed",
    })
    return await _confirmed_success_response(result_text, "create_order", args, intent)


async def _execute_confirmed_content(user_info: dict, fields: dict, user_message: str) -> dict:
    user_id = _current_user_id(user_info)
    content = _field_value(fields, ("动态内容", "正文", "内容", "文本"))
    media_type = _field_value(fields, ("媒体类型", "mediaType")) or "TEXT_ONLY"
    order_id = _extract_first_int(_field_value(fields, ("订单ID", "关联订单")))

    missing = []
    if not user_id:
        missing.append("用户ID")
    if not content:
        missing.append("动态内容")

    intent = _intent_for_confirmed_execution("content.create")
    if missing:
        return {
            "reply": "我还不能发布这个动态草稿，缺少：" + "、".join(missing) + "。请点击修改草稿补充后再确认。",
            "tool_calls": [],
            "intent": {**intent, "missing_slots": missing, "requires_confirmation": True, "next_action": "prepare_draft"},
        }

    args = {
        "user_id": user_id,
        "content": content,
        "media_type": media_type,
        "order_id": order_id,
    }
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "执行已确认动态",
        "detail": "已收到完整确认草稿，正在调用动态发布工具",
        "state": "running",
    })
    result_text = await create_content.ainvoke(args)
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "动态执行完成",
        "detail": "动态发布工具已返回结果",
        "state": "completed",
    })
    return await _confirmed_success_response(result_text, "create_content", args, intent)


async def _execute_confirmed_comment(user_info: dict, fields: dict, user_message: str) -> dict:
    user_id = _current_user_id(user_info)
    content_id = _field_int(fields, ("动态ID", "帖子ID", "内容ID", "content_id", "post_id"))
    comment_text = _comment_text_from_fields(fields)

    missing = []
    if not user_id:
        missing.append("用户ID")
    if not content_id:
        missing.append("动态ID")
    if not comment_text:
        missing.append("评论内容")

    intent = _intent_for_confirmed_execution("content.comment")
    if missing:
        return {
            "reply": "我还不能发表评论，缺少：" + "、".join(missing) + "。请点击修改草稿补充后再确认。",
            "tool_calls": [],
            "intent": {**intent, "missing_slots": missing, "requires_confirmation": True, "next_action": "prepare_draft"},
        }

    args = {"user_id": user_id, "content_id": content_id, "comment_text": comment_text}
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "执行已确认评论",
        "detail": "已收到完整确认草稿，正在调用评论工具",
        "state": "running",
    })
    result_text = await create_comment.ainvoke(args)
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "评论执行完成",
        "detail": "评论工具已返回结果",
        "state": "completed",
    })
    return await _confirmed_success_response(result_text, "create_comment", args, intent)


async def _execute_confirmed_like(user_info: dict, fields: dict, user_message: str) -> dict:
    user_id = _current_user_id(user_info)
    content_id = _field_int(fields, ("动态ID", "帖子ID", "内容ID", "content_id", "post_id"))
    missing = []
    if not user_id:
        missing.append("用户ID")
    if not content_id:
        missing.append("动态ID")

    intent = _intent_for_confirmed_execution("content.like")
    if missing:
        return {
            "reply": "我还不能点赞，缺少：" + "、".join(missing) + "。请点击修改草稿补充后再确认。",
            "tool_calls": [],
            "intent": {**intent, "missing_slots": missing, "requires_confirmation": True, "next_action": "prepare_draft"},
        }

    args = {"user_id": user_id, "content_id": content_id}
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "执行已确认点赞",
        "detail": "已收到完整确认草稿，正在调用点赞工具",
        "state": "running",
    })
    result_text = await like_content.ainvoke(args)
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "点赞执行完成",
        "detail": "点赞工具已返回结果",
        "state": "completed",
    })
    return await _confirmed_success_response(result_text, "like_content", args, intent)


async def _execute_confirmed_order_apply(user_info: dict, fields: dict, user_message: str) -> dict:
    user_id = _current_user_id(user_info)
    order_id = _field_int(fields, ("订单ID", "约伴ID", "活动ID", "order_id"))
    message = _field_value(fields, ("申请留言", "留言", "备注", "说明"))
    missing = []
    if not user_id:
        missing.append("用户ID")
    if not order_id:
        missing.append("订单ID")

    intent = _intent_for_confirmed_execution("order.apply")
    if missing:
        return {
            "reply": "我还不能申请加入订单，缺少：" + "、".join(missing) + "。请点击修改草稿补充后再确认。",
            "tool_calls": [],
            "intent": {**intent, "missing_slots": missing, "requires_confirmation": True, "next_action": "prepare_draft"},
        }

    args = {"user_id": user_id, "order_id": order_id, "message": message}
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "执行已确认报名",
        "detail": "已收到完整确认草稿，正在调用申请加入工具",
        "state": "running",
    })
    result_text = await apply_to_order.ainvoke(args)
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "报名执行完成",
        "detail": "申请加入工具已返回结果",
        "state": "completed",
    })
    return await _confirmed_success_response(result_text, "apply_to_order", args, intent)


async def _execute_confirmed_order_cancel_apply(user_info: dict, fields: dict, user_message: str) -> dict:
    user_id = _current_user_id(user_info)
    order_id = _field_int(fields, ("订单ID", "约伴ID", "活动ID", "order_id"))
    missing = []
    if not user_id:
        missing.append("用户ID")
    if not order_id:
        missing.append("订单ID")

    intent = _intent_for_confirmed_execution("order.cancel_apply")
    if missing:
        return {
            "reply": "我还不能撤销订单申请，缺少：" + "、".join(missing) + "。请点击修改草稿补充后再确认。",
            "tool_calls": [],
            "intent": {**intent, "missing_slots": missing, "requires_confirmation": True, "next_action": "prepare_draft"},
        }

    args = {"user_id": user_id, "order_id": order_id}
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "执行已确认撤销申请",
        "detail": "已收到完整确认草稿，正在调用撤销申请工具",
        "state": "running",
    })
    result_text = await cancel_order_application.ainvoke(args)
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "撤销申请执行完成",
        "detail": "撤销申请工具已返回结果",
        "state": "completed",
    })
    return await _confirmed_success_response(result_text, "cancel_order_application", args, intent)


async def _execute_confirmed_order_accept(user_info: dict, fields: dict, user_message: str) -> dict:
    user_id = _current_user_id(user_info)
    order_id = _field_int(fields, ("订单ID", "约伴ID", "活动ID", "order_id"))
    accepter_id = _field_int(fields, ("申请者ID", "申请用户ID", "用户ID", "accepter_id"))
    missing = []
    if not user_id:
        missing.append("当前用户ID")
    if not order_id:
        missing.append("订单ID")
    if not accepter_id:
        missing.append("申请者ID")

    intent = _intent_for_confirmed_execution("order.accept")
    if missing:
        return {
            "reply": "我还不能接受申请，缺少：" + "、".join(missing) + "。请点击修改草稿补充后再确认。",
            "tool_calls": [],
            "intent": {**intent, "missing_slots": missing, "requires_confirmation": True, "next_action": "prepare_draft"},
        }

    args = {"user_id": user_id, "order_id": order_id, "accepter_id": accepter_id}
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "执行已确认接受申请",
        "detail": "已收到完整确认草稿，正在调用接受申请工具",
        "state": "running",
    })
    result_text = await accept_applicant.ainvoke(args)
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "接受申请执行完成",
        "detail": "接受申请工具已返回结果",
        "state": "completed",
    })
    return await _confirmed_success_response(result_text, "accept_applicant", args, intent)


async def _execute_confirmed_order_reject_apply(user_info: dict, fields: dict, user_message: str) -> dict:
    user_id = _current_user_id(user_info)
    apply_id = _field_int(fields, ("申请ID", "申请记录ID", "申请编号", "apply_id", "apid"))
    missing = []
    if not user_id:
        missing.append("当前用户ID")
    if not apply_id:
        missing.append("申请ID")

    intent = _intent_for_confirmed_execution("order.reject_apply")
    if missing:
        return {
            "reply": "我还不能拒绝申请，缺少：" + "、".join(missing) + "。请点击修改草稿补充后再确认。",
            "tool_calls": [],
            "intent": {**intent, "missing_slots": missing, "requires_confirmation": True, "next_action": "prepare_draft"},
        }

    args = {"user_id": user_id, "apply_id": apply_id}
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "执行已确认拒绝申请",
        "detail": "已收到完整确认草稿，正在调用拒绝申请工具",
        "state": "running",
    })
    result_text = await reject_order_application.ainvoke(args)
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "拒绝申请执行完成",
        "detail": "拒绝申请工具已返回结果",
        "state": "completed",
    })
    return await _confirmed_success_response(result_text, "reject_order_application", args, intent)


async def _execute_confirmed_order_complete(user_info: dict, fields: dict, user_message: str) -> dict:
    user_id = _current_user_id(user_info)
    order_id = _field_int(fields, ("订单ID", "约伴ID", "活动ID", "order_id"))
    missing = []
    if not user_id:
        missing.append("用户ID")
    if not order_id:
        missing.append("订单ID")

    intent = _intent_for_confirmed_execution("order.complete")
    if missing:
        return {
            "reply": "我还不能完成订单，缺少：" + "、".join(missing) + "。请点击修改草稿补充后再确认。",
            "tool_calls": [],
            "intent": {**intent, "missing_slots": missing, "requires_confirmation": True, "next_action": "prepare_draft"},
        }

    args = {"user_id": user_id, "order_id": order_id}
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "执行已确认完成订单",
        "detail": "已收到完整确认草稿，正在调用完成订单工具",
        "state": "running",
    })
    result_text = await complete_order.ainvoke(args)
    await _emit_event("agent_step", {
        "phase": "confirmed_execution",
        "title": "完成订单执行完成",
        "detail": "完成订单工具已返回结果",
        "state": "completed",
    })
    return await _confirmed_success_response(result_text, "complete_order", args, intent)


async def build_confirmed_execution_response(user_info: dict, history: list, user_message: str) -> dict | None:
    """Execute a structured draft only after the user explicitly confirms it."""
    confirmation_message = str(user_message or "")
    if not _is_confirmed_artifact_message(confirmation_message):
        confirmation_message = _build_confirmed_message_from_recent_summary(history, confirmation_message)
        if not confirmation_message:
            return None

    fields = _parse_confirmed_artifact_fields(confirmation_message)
    action_kind = _infer_confirmed_action_kind(confirmation_message, fields)
    if action_kind == "order.create":
        return await _execute_confirmed_order(user_info, fields, confirmation_message)
    if action_kind == "content.create":
        return await _execute_confirmed_content(user_info, fields, confirmation_message)
    if action_kind == "content.comment":
        return await _execute_confirmed_comment(user_info, fields, confirmation_message)
    if action_kind == "content.like":
        return await _execute_confirmed_like(user_info, fields, confirmation_message)
    if action_kind == "order.apply":
        return await _execute_confirmed_order_apply(user_info, fields, confirmation_message)
    if action_kind == "order.cancel_apply":
        return await _execute_confirmed_order_cancel_apply(user_info, fields, confirmation_message)
    if action_kind == "order.accept":
        return await _execute_confirmed_order_accept(user_info, fields, confirmation_message)
    if action_kind == "order.reject_apply":
        return await _execute_confirmed_order_reject_apply(user_info, fields, confirmation_message)
    if action_kind == "order.complete":
        return await _execute_confirmed_order_complete(user_info, fields, confirmation_message)
    if action_kind == "memory.manage":
        return await _execute_confirmed_memory(user_info, fields, confirmation_message)

    return {
        "reply": "我已收到确认，但这个草稿类型暂时还不能自动执行。请改用订单、动态、评论、点赞、报名、撤销申请、拒绝申请或记忆管理草稿，或继续手动处理。",
        "tool_calls": [],
        "intent": _intent_for_confirmed_execution(action_kind),
    }


async def build_confirmation_artifact(
    user_info: dict,
    history: list,
    user_message: str,
    intent_analysis: dict,
) -> dict:
    await _emit_event("agent_step", {
        "phase": "confirmation",
        "title": "生成确认草稿",
        "detail": "写操作需要先由你确认，当前不会执行数据库写入",
        "state": "running",
    })
    prompt = DRAFT_CONFIRMATION_PROMPT.format(
        intent_analysis=json.dumps(intent_analysis or {}, ensure_ascii=False),
        user_info=json.dumps(user_info or {}, ensure_ascii=False),
        history=json.dumps((history or [])[-8:], ensure_ascii=False),
        user_message=user_message,
    )

    try:
        result = await _get_router_llm().ainvoke([HumanMessage(content=prompt)])
        draft = _safe_json_loads(result.content)
    except Exception as e:
        logger.warning("Confirmation draft failed: %s", e)
        draft = {}

    missing_fields = draft.get("missing_fields") if isinstance(draft.get("missing_fields"), list) else []
    raw_fields = draft.get("fields") if isinstance(draft.get("fields"), list) else []
    raw_missing_fields = list(missing_fields)
    raw_fields, missing_fields = _enrich_order_confirmation_fields(
        raw_fields,
        missing_fields,
        user_info,
        history,
        user_message,
        intent_analysis,
    )
    raw_fields, missing_fields = _enrich_content_confirmation_fields(
        raw_fields,
        missing_fields,
        history,
        user_message,
        intent_analysis,
    )
    fields = _normalize_artifact_fields(raw_fields, missing_fields)
    title = draft.get("title") or "请确认这次操作"
    description = draft.get("description") or intent_analysis.get("summary") or "这是一个需要确认后才会执行的写操作。"
    reply = draft.get("reply")
    if raw_missing_fields != missing_fields:
        if missing_fields:
            reply = "我已根据上文补全部分草稿信息，还需要你补充：" + "、".join(str(item) for item in missing_fields)
        else:
            reply = "我已根据上文整理好操作草稿。确认无误后，请点击确认执行或直接回复“确认”。"
    if not reply:
        if missing_fields:
            reply = "我还需要你补充这些信息后再执行：" + "、".join(str(item) for item in missing_fields)
        else:
            reply = "我已经整理好操作草稿。确认无误后，请点击确认执行或直接回复“确认”。"

    action_kind = _resolve_confirmation_action_kind(draft, intent_analysis, user_message)
    artifact = {
        "type": "confirmation",
        "title": title,
        "description": description,
        "actionKind": action_kind,
        "fields": fields,
        "missingFields": missing_fields,
        "requiresConfirmation": True,
        "confirmMessage": f"我确认执行这个草稿：{title}\n操作类型: {action_kind}",
        "editMessage": f"我想修改这个草稿：{title}",
        "cancelMessage": f"取消这个草稿：{title}",
        "reply": reply,
    }
    artifact["reply"] = _append_confirmation_summary_to_reply(reply, artifact)
    await _emit_event("confirm_required", artifact)
    await _emit_event("agent_step", {
        "phase": "confirmation",
        "title": "等待用户确认",
        "detail": "确认后才会继续执行写操作",
        "state": "pending",
    })
    return artifact


async def build_general_help_response(intent_analysis: dict) -> dict:
    """Return a fast, structured answer for low-risk product-help prompts."""
    await _emit_event("agent_step", {
        "phase": "general_help",
        "title": "整理助手能力",
        "detail": "这是普通帮助请求，直接展示可用能力和示例入口",
        "state": "completed",
    })

    artifact = {
        "type": "guide",
        "title": "CampusHub AI 可以帮你做什么",
        "description": "选择一个入口直接试用；涉及创建、发布、报名、评论、点赞和记忆写入时都会先生成确认草稿。",
        "fields": [
            {"label": "地图推荐", "value": "找店铺、路线、附近地点，并直接展示可操作地图"},
            {"label": "约伴活动", "value": "查询可加入活动，或整理新的约伴订单草稿"},
            {"label": "校园动态", "value": "搜索动态、整理发布草稿、评论和点赞前先确认"},
            {"label": "天气规划", "value": "查询天气并给出户外/室内备选安排"},
            {"label": "长期记忆", "value": "在你确认后记住偏好，用于后续推荐"},
        ],
        "actions": [
            {
                "label": "找三人按摩店",
                "prompt": "我想找适合三个人一起去的按摩店，请推荐附近店铺并展示地图",
                "primary": True,
            },
            {
                "label": "查可加入约伴",
                "prompt": "帮我看看良乡校区今天有没有适合加入的篮球或羽毛球约伴活动",
            },
            {
                "label": "写动态草稿",
                "prompt": "帮我发一条动态：今晚七点图书馆二楼自习，欢迎同学一起加入",
            },
            {
                "label": "查天气建议",
                "prompt": "查一下今天北京天气，适不适合晚上去操场跑步",
            },
        ],
        "state": "completed",
    }

    await _emit_event("artifact", artifact)
    reply = (
        "我可以帮你把校园里的查询、推荐和发布准备工作串起来。\n\n"
        "- **查信息**：约伴活动、校园动态、用户主页、天气和附近地点。\n"
        "- **做规划**：根据地点/天气/人数给出下一步建议。\n"
        "- **生成草稿**：订单、动态、评论、报名和记忆写入都会先让你确认，不会直接发布。\n\n"
        "下面的能力卡可以直接点一个入口开始。"
    )
    return {
        "reply": reply,
        "tool_calls": [],
        "intent": intent_analysis,
        "artifacts": [artifact],
    }


LIANGXIANG_CENTER = "116.178000,39.729000"
ZHONGGUANCUN_CENTER = "116.326000,39.964000"


def _safe_json_object(text: str) -> dict:
    try:
        value = json.loads(text or "{}")
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _select_campus_center(user_info: dict, user_message: str) -> tuple[str, str]:
    text = str(user_message or "")
    campus = str(user_info.get("campus") or "").upper()
    if "中关村" in text or campus == "ZHONGGUANCUN":
        return ZHONGGUANCUN_CENTER, "北京理工大学中关村校区"
    return LIANGXIANG_CENTER, "北京理工大学良乡校区"


def _extract_map_keyword(user_message: str) -> str:
    text = str(user_message or "").lower()
    keyword_groups = [
        (("按摩", "洗脚", "足疗", "推拿", "spa", "massage", "foot massage", "foot bath", "relaxing massage"), "按摩"),
        (
            (
                "吃饭",
                "餐厅",
                "饭店",
                "美食",
                "约饭",
                "restaurant",
                "restaurants",
                "resturant",
                "resturants",
                "restraunt",
                "restraunts",
                "dining",
                "eatery",
                "eateries",
                "dinner",
                "lunch",
                "meal",
                "food",
                "hotpot",
                "bbq",
            ),
            "餐厅",
        ),
        (("咖啡", "奶茶", "coffee", "cafe", "cafes", "milk tea", "bubble tea"), "咖啡"),
        (("电影院", "影院", "电影", "cinema", "movie", "movies", "theater", "theatre"), "电影院"),
        (("篮球", "basketball"), "篮球场"),
        (("羽毛球", "badminton"), "羽毛球馆"),
        (("自习", "图书馆", "study", "library", "quiet place"), "图书馆"),
        (("超市", "便利店", "supermarket", "grocery", "convenience store"), "超市"),
        (("药店", "pharmacy", "drugstore"), "药店"),
        (("医院", "诊所", "hospital", "clinic"), "医院"),
        (("ktv", "karaoke"), "KTV"),
        (("酒吧", "bar", "pub"), "酒吧"),
        (("玩", "放松", "休闲", "娱乐", "fun", "hang out", "hangout", "board game", "escape room"), "休闲娱乐"),
    ]
    for cues, keyword in keyword_groups:
        if any(cue in text for cue in cues):
            return keyword
    return "校园周边"


def _is_route_request(user_message: str) -> bool:
    text = str(user_message or "").lower()
    return any(cue in text for cue in (
        "怎么走",
        "路线怎么",
        "导航到",
        "导航去",
        "带路",
        "route to",
        "directions to",
        "how do i get to",
        "how to get to",
    ))


def _extract_route_destination_text(user_message: str) -> str:
    text = str(user_message or "").strip()
    patterns = (
        r"(?:到|去|前往|导航到|导航去)\s*([^，。,.?？!！\n]{2,40})",
        r"(?:route to|directions to|how do i get to|how to get to)\s+([^,.?!\n]{2,60})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        destination = match.group(1)
        destination = re.split(r"(?:怎么走|路线|导航|给我|展示|show|map)", destination, maxsplit=1, flags=re.IGNORECASE)[0]
        destination = destination.strip(" 的地附近周边路线导航")
        if destination:
            return destination
    return ""


def _route_mode(user_message: str) -> tuple[str, object, str]:
    text = str(user_message or "").lower()
    if any(cue in text for cue in ("开车", "驾车", "打车", "自驾", "driving", "drive", "taxi")):
        return "驾车", maps_direction_driving, "maps_direction_driving"
    return "步行", maps_direction_walking, "maps_direction_walking"


def _extract_location_from_geo(text: str) -> str:
    data = _safe_json_object(text)
    candidates = data.get("return") or data.get("geocodes") or []
    if not isinstance(candidates, list):
        return ""
    for item in candidates:
        if isinstance(item, dict) and item.get("location"):
            return str(item["location"])
    return ""


def _agent_display_name(agent_key: str) -> str:
    labels = {
        "order_query": "订单查询专家",
        "order_draft": "订单草稿专家",
        "content_query": "动态查询专家",
        "content_draft": "动态草稿专家",
        "map_weather": "地图天气专家",
        "user_profile": "用户资料专家",
        "memory": "记忆管理专家",
        "general": "通用助手",
    }
    return labels.get(str(agent_key or ""), str(agent_key or "通用助手"))


def _delegation_agent_display_name(agent_key: str) -> str:
    labels = {
        "order": "订单专家",
        "content": "动态/用户专家",
        "map": "地图天气专家",
    }
    return labels.get(str(agent_key or ""), str(agent_key or "通用助手"))


def _ordered_delegation_agents(allowed_agents: set[str] | None) -> list[str]:
    if not allowed_agents:
        return []
    ordered = [agent for agent in DELEGATION_AGENT_ORDER if agent in allowed_agents]
    ordered.extend(sorted(agent for agent in allowed_agents if agent not in DELEGATION_AGENT_ORDER))
    return ordered


def _delegation_guard_display(intent_analysis: dict) -> str:
    allowed_agents = _build_allowed_delegation_agents(intent_analysis)
    ordered = _ordered_delegation_agents(allowed_agents)
    if not ordered:
        return "无需子专家委派"
    names = "、".join(_delegation_agent_display_name(agent) for agent in ordered)
    return f"仅允许：{names}"


def _delegation_guard_detail(intent_analysis: dict) -> str:
    allowed_agents = _build_allowed_delegation_agents(intent_analysis)
    ordered = _ordered_delegation_agents(allowed_agents)
    if not ordered:
        return "本轮无需进入子专家委派，直接回答或等待确认"
    names = "、".join(_delegation_agent_display_name(agent) for agent in ordered)
    return f"如需进入专家委派，仅允许 {names}；计划外专家会被拦截"


def _intent_display_name(primary_intent: str) -> str:
    labels = {
        "order.search": "查询约伴活动",
        "order.create": "创建约伴草稿",
        "order.manage": "管理约伴活动",
        "content.search": "搜索校园动态",
        "content.create": "发布动态草稿",
        "content.interact": "动态互动",
        "map.search": "地图地点推荐",
        "weather.query": "天气建议",
        "user.profile": "查看用户资料",
        "memory.manage": "管理长期记忆",
        "multi_step": "多步骤校园任务",
        "chat.general": "普通对话",
    }
    return labels.get(str(primary_intent or ""), primary_intent or "待识别任务")


def _operation_display_name(operation_type: str) -> str:
    labels = {
        "read": "只读查询",
        "write": "写操作确认",
        "mixed": "先查后写",
        "unknown": "待确认",
    }
    return labels.get(str(operation_type or ""), operation_type or "待确认")


def _confirmation_gate_display(intent_analysis: dict) -> str:
    primary_intent = str(intent_analysis.get("primary_intent") or "").lower()
    operation_type = str(intent_analysis.get("operation_type") or "").lower()
    next_action = str(intent_analysis.get("next_action") or "").lower()
    missing_slots = _missing_slots_list(intent_analysis)
    requires_confirmation = bool(intent_analysis.get("requires_confirmation"))

    if primary_intent == "chat.general":
        return "普通问答不会触发业务写操作"
    if operation_type == "read" and not requires_confirmation:
        return "只读查询可直接调用工具，不需要发布前确认"
    if missing_slots:
        return "先补齐缺失字段，再生成可确认草稿"
    if next_action == "execute_read_tools" and operation_type == "mixed":
        return "先执行只读查询，后续创建/发布仍必须再次确认"
    if requires_confirmation:
        return "写操作只生成草稿，用户确认后才会执行"
    return "本轮不会绕过确认门"


def _delegation_boundary_display(intent_analysis: dict) -> str:
    allowed_agents = _build_allowed_delegation_agents(intent_analysis)
    if allowed_agents:
        names = "、".join(_delegation_agent_display_name(agent) for agent in _ordered_delegation_agents(allowed_agents))
        return f"仅允许 {names}；计划外专家会被拦截"
    return "未限定专家时仍受总委派次数、单专家次数和重复任务复用保护"


def _missing_slots_list(intent_analysis: dict) -> list[str]:
    slots = intent_analysis.get("missing_slots") if isinstance(intent_analysis, dict) else []
    if not isinstance(slots, list):
        return []
    return [str(item).strip() for item in slots if str(item or "").strip()]


def _missing_slots_display(intent_analysis: dict) -> str:
    slots = _missing_slots_list(intent_analysis)
    return "、".join(slots)


def _build_execution_plan_steps(intent_analysis: dict) -> list[dict]:
    primary_intent = (intent_analysis.get("primary_intent") or "").lower()
    operation_type = (intent_analysis.get("operation_type") or "").lower()
    next_action = (intent_analysis.get("next_action") or "").lower()
    has_weather_context = bool(intent_analysis.get("weather_context"))
    missing_slots = _missing_slots_display(intent_analysis)
    suggested_agents = [
        _agent_display_name(agent)
        for agent in (intent_analysis.get("suggested_agents") or [])
        if agent
    ]
    agent_text = "、".join(suggested_agents[:3]) or "通用助手"

    steps = [{
        "title": "识别意图与安全边界",
        "detail": f"{_intent_display_name(primary_intent)} · {_operation_display_name(operation_type)}",
        "state": "completed",
    }]
    steps.append({
        "title": "锁定本轮专家范围",
        "detail": _delegation_guard_detail(intent_analysis),
        "state": "completed",
    })
    steps.append({
        "title": "确认门策略",
        "detail": _confirmation_gate_display(intent_analysis),
        "state": "completed",
    })
    steps.append({
        "title": "越界委派拦截",
        "detail": _delegation_boundary_display(intent_analysis),
        "state": "completed",
    })
    if missing_slots:
        steps.append({
            "title": "标出待补充信息",
            "detail": f"还需要：{missing_slots}",
            "state": "completed",
        })

    if primary_intent == "weather.query":
        steps.extend([
            {"title": "调用天气工具", "detail": "直接查询天气数据，避免进入多轮委派", "state": "running"},
            {"title": "生成天气建议卡", "detail": "给出户外/室内备选入口", "state": "pending"},
        ])
    elif primary_intent in {"map.search", "multi_step"} and next_action == "execute_read_tools":
        if has_weather_context:
            steps.append({
                "title": "查询天气参考",
                "detail": "同一轮先获取天气数据，再继续查询附近地点",
                "state": "running",
            })
        steps.extend([
            {"title": "搜索附近地点", "detail": "调用地图工具获取候选地点", "state": "running"},
            {"title": "补全坐标并渲染地图", "detail": "前端会直接显示可交互地图卡片", "state": "pending"},
        ])
        if operation_type == "mixed" or primary_intent == "multi_step":
            steps.append({"title": "写操作前等待确认", "detail": "创建订单或动态只会先生成草稿", "state": "pending"})
    elif primary_intent in {"order.search", "order.manage"} and operation_type == "read":
        steps.extend([
            {"title": "查询约伴活动", "detail": "直接调用订单查询工具", "state": "running"},
            {"title": "生成订单结果卡", "detail": "有结果可跳转详情，空结果也给出下一步入口", "state": "pending"},
        ])
    elif primary_intent == "content.search":
        steps.extend([
            {"title": "搜索校园动态", "detail": "直接调用动态搜索工具", "state": "running"},
            {"title": "生成动态结果卡", "detail": "评论、点赞或发布前仍会先确认", "state": "pending"},
        ])
    elif primary_intent == "user.profile":
        steps.extend([
            {"title": "查询用户资料", "detail": "直接调用用户资料或搜索工具", "state": "running"},
            {"title": "生成用户资料卡", "detail": "资料查询只读，后续评论、发布或报名仍需确认", "state": "pending"},
        ])
    elif operation_type in {"write", "mixed"} or intent_analysis.get("requires_confirmation"):
        steps.extend([
            {"title": "整理待确认草稿", "detail": "提取关键字段和缺失信息", "state": "running"},
            {"title": "等待用户确认", "detail": "确认前不会创建、发布、报名、评论、点赞或写入记忆", "state": "pending"},
        ])
    elif primary_intent == "chat.general":
        steps.append({"title": "直接回答", "detail": "无需调用业务工具", "state": "running"})
    else:
        steps.extend([
            {"title": "调度领域专家", "detail": agent_text, "state": "running"},
            {"title": "汇总工具结果", "detail": "根据专家返回内容整理最终回复", "state": "pending"},
        ])

    return steps


def _build_execution_plan_artifact(intent_analysis: dict) -> dict:
    primary_intent = (intent_analysis.get("primary_intent") or "unknown").lower()
    operation_type = (intent_analysis.get("operation_type") or "unknown").lower()
    requires_confirmation = bool(intent_analysis.get("requires_confirmation"))
    suggested_agents = intent_analysis.get("suggested_agents") or []
    missing_slots = _missing_slots_list(intent_analysis)
    strategy = "确认门控" if requires_confirmation else "直接执行只读工具"
    if primary_intent == "chat.general":
        strategy = "直接回答"
    elif primary_intent in {"order.search", "content.search", "user.profile", "weather.query", "map.search", "multi_step"}:
        strategy = "确定性工具路径"
    elif suggested_agents:
        strategy = "领域专家委派"

    fields = [
        {"label": "任务", "value": _intent_display_name(primary_intent)},
        {"label": "类型", "value": _operation_display_name(operation_type)},
    ]
    if missing_slots:
        fields.append({"label": "待补充", "value": "、".join(missing_slots)})
    fields.extend([
        {"label": "策略", "value": strategy},
        {"label": "确认门", "value": _confirmation_gate_display(intent_analysis)},
        {
            "label": "专家",
            "value": "、".join(_agent_display_name(agent) for agent in suggested_agents[:3]) or "无需额外专家",
        },
        {"label": "调度守卫", "value": _delegation_guard_display(intent_analysis)},
        {"label": "越界处理", "value": _delegation_boundary_display(intent_analysis)},
    ])

    return {
        "type": "plan",
        "title": "本轮执行计划",
        "description": "根据意图分析生成的可视化调度计划；写操作仍会先等待你确认。",
        "fields": fields,
        "steps": _build_execution_plan_steps(intent_analysis),
        "state": "running",
        "intent": {
            "primary_intent": primary_intent,
            "next_action": intent_analysis.get("next_action"),
            "requires_confirmation": requires_confirmation,
            "missing_slots": missing_slots,
            "allowed_delegation_agents": _ordered_delegation_agents(_build_allowed_delegation_agents(intent_analysis)),
        },
    }


def _should_emit_execution_plan(intent_analysis: dict) -> bool:
    primary_intent = (intent_analysis.get("primary_intent") or "").lower()
    next_action = (intent_analysis.get("next_action") or "").lower()
    return not (primary_intent == "chat.general" and next_action == "direct_answer")


async def _emit_execution_plan(intent_analysis: dict) -> dict | None:
    if not _should_emit_execution_plan(intent_analysis):
        return None
    artifact = _build_execution_plan_artifact(intent_analysis)
    await _emit_event("artifact", artifact)
    return artifact


async def _invoke_tool_text(tool_obj, args: dict) -> str:
    if hasattr(tool_obj, "ainvoke"):
        return await tool_obj.ainvoke(args)
    return await asyncio.to_thread(tool_obj.invoke, args)


def _extract_order_search_args(user_info: dict, user_message: str) -> dict:
    activity_label = _infer_activity_label(user_message)
    activity_type = ""
    if activity_label:
        activity_type = activity_label.split("（", 1)[0]

    campus = _normalize_campus("", user_message)
    if not campus:
        campus = str((user_info or {}).get("campus") or "").upper()

    args = {}
    if activity_type:
        args["activity_type"] = activity_type
    if campus:
        args["campus"] = campus
    return args


def _is_my_order_query(user_message: str) -> bool:
    text = str(user_message or "")
    return _has_any(text, ("我的订单", "我发布", "我发的", "我创建", "我参加", "我报名"))


def _parse_order_result_lines(order_text: str) -> list[dict]:
    items = []
    pattern = re.compile(r"- \*\*\[订单#(?P<id>\d+)\]\(/orders/\d+\)\*\*\s*(?P<body>.+)")
    for line in str(order_text or "").splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        parts = [part.strip() for part in match.group("body").split("|")]
        item = {
            "id": match.group("id"),
            "activity": parts[0] if len(parts) > 0 else "",
            "campus_or_status": parts[1] if len(parts) > 1 else "",
            "location": parts[2] if len(parts) > 2 else "",
            "time": parts[3] if len(parts) > 3 else (parts[2] if len(parts) > 2 else ""),
            "people": parts[4] if len(parts) > 4 else (parts[3] if len(parts) > 3 else ""),
        }
        items.append(item)
    return items


def _extract_result_count(result_text: str) -> int:
    match = re.search(r"找到\s*(\d+)\s*[个条]", str(result_text or ""))
    if match:
        return int(match.group(1))
    match = re.search(r"共有\s*(\d+)\s*个", str(result_text or ""))
    if match:
        return int(match.group(1))
    return 0


def _format_order_result_preview(orders: list[dict], limit: int = 3) -> str:
    previews = []
    for item in orders[:limit]:
        summary = " · ".join(
            part for part in [item.get("activity"), item.get("location"), item.get("time"), item.get("people")]
            if part
        )
        label = f"订单#{item.get('id')}"
        previews.append(f"{label} {summary}".strip())
    return "；".join(previews)


def _build_order_result_items(orders: list[dict], limit: int = 3) -> list[dict]:
    items = []
    for order in orders[:limit]:
        order_id = order.get("id")
        title = " · ".join(part for part in [f"订单#{order_id}" if order_id else "", order.get("activity")] if part)
        subtitle = " · ".join(part for part in [order.get("location"), order.get("time")] if part)
        items.append({
            "title": title or "约伴订单",
            "subtitle": subtitle or "地点和时间待查看详情",
            "meta": order.get("people") or "人数待查看",
            "badge": order.get("campus_or_status") or "约伴",
            "actionLabel": "查看订单",
            "hint": "打开详情",
            "route": f"/orders/{order_id}" if order_id else "",
        })
    return items


def _build_order_result_artifact(order_text: str, args: dict, user_message: str, intent_analysis: dict) -> dict | None:
    orders = _parse_order_result_lines(order_text)
    if not orders:
        scope_parts = []
        if args.get("campus"):
            scope_parts.append(args["campus"])
        if args.get("activity_type"):
            scope_parts.append(args["activity_type"])
        scope = " · ".join(scope_parts) if scope_parts else "全部可加入活动"
        return {
            "type": "order",
            "title": "暂未找到可加入约伴",
            "description": "这也是有效查询结果；可以换条件继续查，或先整理一个创建草稿。",
            "fields": [
                {"label": "查询范围", "value": scope},
                {"label": "匹配数量", "value": "0 个结果"},
                {"label": "下一步", "value": "建议放宽活动类型、校区或时间条件"},
                {"label": "安全策略", "value": "创建新活动仍会先生成确认草稿"},
            ],
            "actions": [
                {
                    "label": "换个条件筛选",
                    "prompt": "帮我放宽条件重新筛选可加入约伴活动，可以先看良乡校区所有未满员活动",
                    "primary": True,
                },
                {
                    "label": "发起约伴草稿",
                    "prompt": (
                        f"没有找到合适的{scope}约伴活动，帮我整理一个新的约伴订单草稿。"
                        "如果还缺少地点、时间、人数等必要信息，请先追问；不要直接发布。"
                    ),
                },
                {
                    "label": "浏览全部活动",
                    "prompt": "帮我浏览当前所有可加入约伴活动，先不要报名或创建订单",
                },
            ],
            "state": "completed",
            "intent": {
                "primary_intent": intent_analysis.get("primary_intent"),
                "next_action": intent_analysis.get("next_action"),
            },
        }

    first = orders[0]
    count = _extract_result_count(order_text) or len(orders)
    scope_parts = []
    if args.get("campus"):
        scope_parts.append(args["campus"])
    if args.get("activity_type"):
        scope_parts.append(args["activity_type"])
    scope = " · ".join(scope_parts) if scope_parts else "全部可加入活动"
    first_summary = " · ".join(
        part for part in [first.get("activity"), first.get("location"), first.get("time"), first.get("people")]
        if part
    )
    result_preview = _format_order_result_preview(orders)
    result_items = _build_order_result_items(orders)
    draft_prompt = (
        f"参考刚才查询到的{scope}约伴活动，帮我整理一个新的约伴订单草稿。"
        "如果还缺少地点、时间、人数等必要信息，请先追问；不要直接发布。"
    )
    if first.get("location"):
        draft_prompt = (
            f"参考刚才第一条订单的地点「{first['location']}」，帮我整理一个新的约伴订单草稿。"
            "如果还缺少地点、时间、人数等必要信息，请先追问；不要直接发布。"
        )

    return {
        "type": "order",
        "title": "可加入约伴结果",
        "description": "已把订单查询结果整理成可操作卡片；报名、创建和其他写操作仍会先确认。",
        "fields": [
            {"label": "查询范围", "value": scope},
            {"label": "匹配数量", "value": f"{count} 个结果"},
            {"label": "结果预览", "value": result_preview},
            {"label": "第一条", "value": f"订单#{first.get('id')} · {first_summary}"},
            {"label": "安全策略", "value": "查看可直接跳转，报名/创建需确认"},
        ],
        "items": result_items,
        "actions": [
            {
                "label": f"打开订单#{first.get('id')}",
                "route": f"/orders/{first.get('id')}",
                "primary": True,
            },
            {
                "label": "申请加入第一条",
                "prompt": f"我想申请加入订单#{first.get('id')}，请先整理报名确认草稿，不要直接提交。",
            },
            {
                "label": "基于结果建草稿",
                "prompt": draft_prompt,
            },
            {
                "label": "换个条件筛选",
                "prompt": "帮我换一个条件筛选可加入约伴活动，比如时间更近、人数未满、地点更近。",
            },
        ],
        "state": "completed",
        "intent": {
            "primary_intent": intent_analysis.get("primary_intent"),
            "next_action": intent_analysis.get("next_action"),
        },
    }


def _extract_content_keyword(user_message: str) -> str:
    text = str(user_message or "").strip()
    patterns = [
        r"关于(.+?)的(?:校园)?(?:动态|帖子)",
        r"搜索(?:一下)?(?:关于)?(.+?)的?(?:校园)?(?:动态|帖子)",
        r"查(?:一下|找)?(?:关于)?(.+?)的?(?:校园)?(?:动态|帖子)",
        r"看看(?:关于)?(.+?)的?(?:校园)?(?:动态|帖子)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            keyword = re.sub(r"[，。,.!?！？\s]+$", "", match.group(1).strip())
            keyword = re.sub(r"^(一下|有关|关于)", "", keyword).strip()
            return keyword[:24]

    for keyword in ("自习", "篮球", "羽毛球", "跑步", "电影", "约饭", "考试", "社团", "活动"):
        if keyword in text:
            return keyword
    return ""


def _parse_content_result_lines(content_text: str) -> list[dict]:
    items = []
    pattern = re.compile(r"- \*\*\[动态#(?P<id>\d+)\]\(/contents/\d+\)\*\*\s*by\s*(?P<author>.*?)\s*—\s*(?P<text>.*)")
    for line in str(content_text or "").splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        items.append({
            "id": match.group("id"),
            "author": match.group("author") or "匿名",
            "text": match.group("text") or "",
        })
    return items


def _format_content_result_preview(contents: list[dict], limit: int = 3) -> str:
    previews = []
    for item in contents[:limit]:
        text = item.get("text") or "无正文预览"
        if len(text) > 28:
            text = f"{text[:28]}..."
        previews.append(f"动态#{item.get('id')} · {item.get('author')}: {text}")
    return "；".join(previews)


def _build_content_result_items(contents: list[dict], limit: int = 3) -> list[dict]:
    items = []
    for content in contents[:limit]:
        content_id = content.get("id")
        text = content.get("text") or "无正文预览"
        if len(text) > 42:
            text = f"{text[:42]}..."
        items.append({
            "title": " · ".join(part for part in [f"动态#{content_id}" if content_id else "", content.get("author") or "匿名"] if part),
            "subtitle": text,
            "meta": "查看详情",
            "badge": "动态",
            "actionLabel": "查看动态",
            "hint": "打开详情",
            "route": f"/contents/{content_id}" if content_id else "",
        })
    return items


def _build_content_result_artifact(content_text: str, keyword: str, intent_analysis: dict) -> dict | None:
    contents = _parse_content_result_lines(content_text)
    if not contents:
        scope = keyword or "最新动态"
        return {
            "type": "content",
            "title": "暂未找到相关动态",
            "description": "这也是有效搜索结果；可以换主题继续查，或整理一条新的动态草稿。",
            "fields": [
                {"label": "搜索主题", "value": scope},
                {"label": "匹配数量", "value": "0 条动态"},
                {"label": "下一步", "value": "建议换关键词、看最新动态，或发布一条新的动态草稿"},
                {"label": "安全策略", "value": "发布、评论、点赞都会先确认"},
            ],
            "actions": [
                {
                    "label": "换主题搜索",
                    "prompt": "帮我换一个相关主题继续搜索校园动态",
                    "primary": True,
                },
                {
                    "label": "看最新动态",
                    "prompt": "帮我浏览最新校园动态，先不要评论、点赞或发布",
                },
                {
                    "label": "写动态草稿",
                    "prompt": f"没有搜到关于「{scope}」的动态，帮我整理一条新的校园动态草稿。不要直接发布，先让我确认。",
                },
            ],
            "state": "completed",
            "intent": {
                "primary_intent": intent_analysis.get("primary_intent"),
                "next_action": intent_analysis.get("next_action"),
            },
        }

    first = contents[0]
    count = _extract_result_count(content_text) or len(contents)
    scope = keyword or "最新动态"
    first_text = first.get("text") or "无正文预览"
    if len(first_text) > 48:
        first_text = f"{first_text[:48]}..."
    result_preview = _format_content_result_preview(contents)
    result_items = _build_content_result_items(contents)

    return {
        "type": "content",
        "title": "校园动态结果",
        "description": "已把动态搜索整理成可继续操作的卡片；评论、点赞和发布都会先确认。",
        "fields": [
            {"label": "搜索主题", "value": scope},
            {"label": "匹配数量", "value": f"{count} 条动态"},
            {"label": "结果预览", "value": result_preview},
            {"label": "第一条", "value": f"动态#{first.get('id')} · {first.get('author')}"},
            {"label": "摘要", "value": first_text},
        ],
        "items": result_items,
        "actions": [
            {
                "label": f"打开动态#{first.get('id')}",
                "route": f"/contents/{first.get('id')}",
                "primary": True,
            },
            {
                "label": "评论第一条",
                "prompt": f"我想评论动态#{first.get('id')}，请先整理评论确认草稿，不要直接发布。",
            },
            {
                "label": "写类似动态草稿",
                "prompt": f"参考刚才关于「{scope}」的动态，帮我整理一条新的校园动态草稿。不要直接发布，先让我确认。",
            },
            {
                "label": "只看约伴相关",
                "prompt": f"继续搜索和「{scope}」相关、适合约伴或一起参加的校园动态",
            },
        ],
        "state": "completed",
        "intent": {
            "primary_intent": intent_analysis.get("primary_intent"),
            "next_action": intent_analysis.get("next_action"),
        },
    }


def _extract_user_profile_id(user_message: str) -> int | None:
    text = str(user_message or "")
    patterns = (
        r"(?:用户|同学|主页|个人主页|资料)\s*(?:ID|id|编号|#|号)?\s*[:：#]?\s*(\d+)",
        r"(\d+)\s*号?(?:同学|用户)",
        r"\b(?:user|uid)\s*#?\s*(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_user_search_keyword(user_message: str) -> str:
    text = str(user_message or "").strip()
    patterns = (
        r"(?:搜索|查找|找|看看|查看|瞅瞅)\s*([A-Za-z0-9_\-\u4e00-\u9fff]{2,20})\s*(?:同学|用户)?(?:的)?(?:主页|资料|个人主页)",
        r"([A-Za-z0-9_\-\u4e00-\u9fff]{2,20})\s*(?:同学|用户)(?:的)?(?:主页|资料|个人主页)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            keyword = match.group(1).strip()
            if keyword not in {"用户", "同学", "主页", "资料", "个人主页"}:
                return keyword[:20]
    return ""


def _parse_user_profile_text(profile_text: str) -> dict:
    user = {}
    for raw_line in str(profile_text or "").splitlines():
        line = raw_line.strip().lstrip("-*•").strip()
        if not line or ("：" not in line and ":" not in line):
            continue
        separator = "：" if "：" in line else ":"
        label, value = line.split(separator, 1)
        label = label.strip()
        value = value.strip()
        if "用户ID" in label or label.lower() in {"id", "uid", "user id"}:
            user["id"] = value
        elif "昵称" in label or "nickname" in label.lower():
            user["nickname"] = value
        elif "签名" in label or "signature" in label.lower():
            user["signature"] = value
        elif "邮箱" in label or "email" in label.lower():
            user["email"] = value
        elif "加入时间" in label or "created" in label.lower():
            user["created_at"] = value
    return user


def _parse_user_search_lines(search_text: str) -> list[dict]:
    users = []
    pattern = re.compile(r"-\s*(?P<nickname>.+?)\s*\(ID:\s*(?P<id>\d+)\)")
    for line in str(search_text or "").splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        users.append({
            "id": match.group("id"),
            "nickname": match.group("nickname").strip(),
        })
    return users


def _build_user_profile_artifact(profile_text: str, user_id: int | None, intent_analysis: dict) -> dict | None:
    user = _parse_user_profile_text(profile_text)
    if not user and "未找到" in str(profile_text or ""):
        return {
            "type": "user",
            "title": "未找到用户资料",
            "description": "没有匹配到这个用户 ID，可以换一个 ID 或昵称继续查。",
            "fields": [
                {"label": "用户ID", "value": str(user_id or "未识别")},
                {"label": "查询结果", "value": "未找到"},
            ],
            "actions": [
                {
                    "label": "换昵称搜索",
                    "prompt": "帮我按昵称搜索用户主页，先只查询资料不要发布或评论。",
                    "primary": True,
                }
            ],
            "state": "completed",
        }
    if not user:
        return None

    uid = user.get("id") or str(user_id or "")
    nickname = user.get("nickname") or "用户"
    signature = user.get("signature") or "无"
    email = user.get("email") or "未知"
    created_at = user.get("created_at") or "未知"
    return {
        "type": "user",
        "title": f"{nickname} 的用户资料",
        "description": "已把用户资料整理成可继续查询的卡片；查看资料不会触发写操作。",
        "fields": [
            {"label": "用户ID", "value": uid},
            {"label": "昵称", "value": nickname},
            {"label": "签名", "value": signature},
            {"label": "邮箱", "value": email},
            {"label": "加入时间", "value": created_at},
        ],
        "actions": [
            {
                "label": "搜索 TA 的动态",
                "prompt": f"帮我搜索用户 {uid} 或昵称「{nickname}」相关的校园动态，先只查询不要评论或点赞。",
                "primary": True,
            },
            {
                "label": "看 TA 的约伴",
                "prompt": f"帮我看看用户 {uid} 最近发布过哪些约伴活动，先只查询不要报名。",
            },
            {
                "label": "基于资料写动态草稿",
                "prompt": f"参考「{nickname}」的资料，帮我整理一条友好的校园动态草稿，发布前先让我确认。",
            },
        ],
        "state": "completed",
        "intent": {
            "primary_intent": intent_analysis.get("primary_intent"),
            "next_action": intent_analysis.get("next_action"),
        },
    }


def _build_user_search_artifact(search_text: str, keyword: str, intent_analysis: dict) -> dict | None:
    users = _parse_user_search_lines(search_text)
    if not users:
        return {
            "type": "user",
            "title": "暂未找到相关用户",
            "description": "可以换昵称、邮箱或用户 ID 继续查。",
            "fields": [
                {"label": "搜索关键词", "value": keyword or "未识别"},
                {"label": "匹配数量", "value": "0 个用户"},
            ],
            "actions": [
                {
                    "label": "换关键词搜索",
                    "prompt": "帮我换一个关键词继续搜索用户资料。",
                    "primary": True,
                }
            ],
            "state": "completed",
        }

    first = users[0]
    return {
        "type": "user",
        "title": "用户搜索结果",
        "description": "已把匹配用户整理成可继续查询的卡片。",
        "fields": [
            {"label": "搜索关键词", "value": keyword},
            {"label": "匹配数量", "value": f"{len(users)} 个用户"},
            {"label": "第一条", "value": f"{first.get('nickname')} · 用户ID {first.get('id')}"},
        ],
        "items": [
            {
                "title": user.get("nickname") or "用户",
                "subtitle": f"用户ID {user.get('id')}",
                "meta": "资料",
                "badge": "用户",
                "actionLabel": "查看资料",
                "hint": "只读查询",
                "prompt": f"帮我查看用户 {user.get('id')} 的主页资料，先只查询。",
            }
            for user in users[:5]
        ],
        "actions": [
            {
                "label": f"查看 {first.get('nickname')}",
                "prompt": f"帮我查看用户 {first.get('id')} 的主页资料，先只查询。",
                "primary": True,
            },
            {
                "label": "换关键词搜索",
                "prompt": "帮我换一个关键词继续搜索用户资料。",
            },
        ],
        "state": "completed",
        "intent": {
            "primary_intent": intent_analysis.get("primary_intent"),
            "next_action": intent_analysis.get("next_action"),
        },
    }


async def _resolve_poi_locations(pois: list[dict], limit: int = 3) -> list[dict]:
    resolved = []
    for poi in pois[:limit]:
        if not isinstance(poi, dict):
            continue
        item = {
            "name": str(poi.get("name") or "未命名地点"),
            "address": str(poi.get("address") or "地址暂缺"),
            "location": str(poi.get("location") or ""),
        }
        if not item["location"]:
            query = item["address"] if item["address"] != "地址暂缺" else item["name"]
            geo_text = await _invoke_tool_text(maps_geo, {"address": query, "city": "北京"})
            item["location"] = _extract_location_from_geo(geo_text)
        if item["location"]:
            resolved.append(item)
    return resolved


def _format_map_direct_reply(keyword: str, center_name: str, pois: list[dict]) -> str:
    if not pois:
        return ""
    lines = [
        f"我先按 **{center_name}** 周边帮你找了几个“{keyword}”相关地点，下面这些结果可以直接在页面里看地图。",
        "",
    ]
    for index, poi in enumerate(pois, start=1):
        lng_lat = [part.strip() for part in str(poi["location"]).split(",", 1)]
        if len(lng_lat) != 2:
            continue
        lng, lat = lng_lat
        title = poi["name"].replace("{", "").replace("}", "")
        lines.extend([
            f"{index}. **{poi['name']}**",
            f"   地址：{poi['address']}",
            f"   经纬度：{lng},{lat}",
            f":::map{{lng={lng} lat={lat} zoom=15 title={title}}}",
            "",
        ])
    lines.append("如果你选中其中一个地点，可以点地图卡里的“用此地点约伴”，我会先整理订单草稿并等你确认。")
    return "\n".join(lines).strip()


def _map_followup_draft_mode(intent_analysis: dict) -> str:
    suggested_agents = {
        str(agent or "").strip().lower()
        for agent in (intent_analysis.get("suggested_agents") or [])
    }
    primary_intent = str(intent_analysis.get("primary_intent") or "").lower()
    domain = str(intent_analysis.get("domain") or "").lower()
    if "content_draft" in suggested_agents or primary_intent == "content.create" or domain == "content":
        return "content"
    return "order"


def _build_map_place_draft_prompt(name: str, location: str, draft_mode: str) -> str:
    if draft_mode == "content":
        prompt = f"基于地图里的「{name}」写一条校园动态草稿，邀请同学一起去这个地点"
    else:
        prompt = f"基于地图里的「{name}」创建一个约伴订单草稿"
    if location:
        prompt += f"，地点坐标：{location}"
    prompt += "。如果还缺少必要信息，请先让我补充；不要直接发布，先让我确认。"
    return prompt


def _build_map_candidate_items(pois: list[dict], draft_mode: str = "order", limit: int = 3) -> list[dict]:
    items = []
    for index, poi in enumerate(pois[:limit], start=1):
        name = str(poi.get("name") or f"地点{index}")
        address = str(poi.get("address") or "地址暂缺")
        location = str(poi.get("location") or "")
        prompt = _build_map_place_draft_prompt(name, location, draft_mode)
        items.append({
            "title": f"{index}. {name}",
            "subtitle": address,
            "meta": location or "坐标待补全",
            "badge": "地点",
            "actionLabel": "写动态" if draft_mode == "content" else "生成草稿",
            "hint": "先确认再发布",
            "prompt": prompt,
        })
    return items


def _build_map_followup_artifact(keyword: str, center_name: str, pois: list[dict], intent_analysis: dict) -> dict:
    first = pois[0] if pois else {}
    first_name = str(first.get("name") or "第一个地点")
    first_location = str(first.get("location") or "")
    draft_mode = _map_followup_draft_mode(intent_analysis)
    first_prompt = _build_map_place_draft_prompt(first_name, first_location, draft_mode)
    first_order_prompt = _build_map_place_draft_prompt(first_name, first_location, "order")
    is_multi_step = (intent_analysis.get("primary_intent") or "").lower() == "multi_step"
    primary_action = {
        "label": "用第一家写动态草稿" if draft_mode == "content" else "用第一家创建约伴草稿",
        "prompt": first_prompt,
        "primary": is_multi_step,
    }
    actions = [primary_action]
    if draft_mode == "content":
        actions.append({
            "label": "改为创建约伴草稿",
            "prompt": first_order_prompt,
        })
    actions.extend([
        {
            "label": "换一批附近推荐",
            "prompt": f"换一批{center_name}附近的{keyword}推荐，并继续展示地图",
        },
        {
            "label": "先查天气再决定",
            "prompt": "查一下北京天气，并告诉我是否适合安排这个活动",
        },
    ])

    return {
        "type": "guide",
        "title": "接下来可以怎么做",
        "description": "这些都是下一步入口；涉及创建订单或发布动态时只会先生成确认草稿，不会直接发布。",
        "fields": [
            {"label": "当前搜索", "value": f"{center_name}周边 · {keyword}"},
            {"label": "可选地点", "value": f"{len(pois)} 个可渲染地图结果"},
            {"label": "写操作保护", "value": "创建、发布、报名等操作都会先确认"},
        ],
        "items": _build_map_candidate_items(pois, draft_mode=draft_mode),
        "actions": actions,
        "state": "completed",
    }


def _extract_route_path(route_text: str) -> dict:
    data = _safe_json_object(route_text)
    route = data.get("route") if isinstance(data.get("route"), dict) else data
    paths = route.get("paths") if isinstance(route, dict) else None
    if isinstance(paths, list) and paths:
        path = paths[0] if isinstance(paths[0], dict) else {}
    else:
        path = route if isinstance(route, dict) else {}
    steps = path.get("steps") if isinstance(path.get("steps"), list) else []
    return {
        "distance": str(path.get("distance") or ""),
        "duration": str(path.get("duration") or ""),
        "steps": [
            str(step.get("instruction") or step.get("road") or "").strip()
            for step in steps
            if isinstance(step, dict) and str(step.get("instruction") or step.get("road") or "").strip()
        ],
    }


def _format_route_metric(value: str, unit: str) -> str:
    try:
        number = float(str(value or "").strip())
    except ValueError:
        return ""
    if unit == "m":
        return f"{number / 1000:.1f} 公里" if number >= 1000 else f"{int(number)} 米"
    if unit == "s":
        minutes = max(1, round(number / 60))
        return f"{minutes} 分钟"
    return str(value)


def _format_route_direct_reply(
    origin_name: str,
    origin_location: str,
    destination_name: str,
    destination_location: str,
    mode_label: str,
    route_info: dict,
) -> str:
    origin_lng, origin_lat = [part.strip() for part in origin_location.split(",", 1)]
    dest_lng, dest_lat = [part.strip() for part in destination_location.split(",", 1)]
    distance = _format_route_metric(route_info.get("distance", ""), "m") or "路线距离待确认"
    duration = _format_route_metric(route_info.get("duration", ""), "s") or "耗时待确认"
    steps = route_info.get("steps") or []
    lines = [
        f"我按 **{mode_label}** 帮你规划了从 **{origin_name}** 到 **{destination_name}** 的路线。",
        "",
        f"- 预计距离：{distance}",
        f"- 预计耗时：{duration}",
        "",
        f":::map{{lng={origin_lng} lat={origin_lat} zoom=15 title={origin_name}}}",
        f":::map{{lng={dest_lng} lat={dest_lat} zoom=15 title={destination_name}}}",
    ]
    if steps:
        lines.extend(["", "路线要点："])
        lines.extend(f"{index}. {step}" for index, step in enumerate(steps[:4], start=1))
    lines.append("")
    lines.append("页面里会直接显示起点和终点地图；如果要基于这个地点发起约伴，我会先生成确认草稿。")
    return "\n".join(lines).strip()


def _build_route_artifact(
    origin_name: str,
    destination_name: str,
    destination_location: str,
    mode_label: str,
    route_info: dict,
    intent_analysis: dict,
) -> dict:
    distance = _format_route_metric(route_info.get("distance", ""), "m") or "待确认"
    duration = _format_route_metric(route_info.get("duration", ""), "s") or "待确认"
    steps = route_info.get("steps") or []
    return {
        "type": "guide",
        "title": "路线规划结果",
        "description": "已整理成可继续操作的路线卡片；创建活动或发布动态仍会先确认。",
        "fields": [
            {"label": "起点", "value": origin_name},
            {"label": "终点", "value": destination_name},
            {"label": "方式", "value": mode_label},
            {"label": "距离", "value": distance},
            {"label": "耗时", "value": duration},
        ],
        "items": [
            {
                "title": f"{index}. {step}",
                "subtitle": destination_name if index == 1 else "",
                "meta": mode_label,
                "badge": "路线",
                "hint": "只读规划",
            }
            for index, step in enumerate(steps[:5], start=1)
        ],
        "actions": [
            {
                "label": "用终点约伴",
                "prompt": f"基于路线终点「{destination_name}」创建一个约伴订单草稿，地点坐标：{destination_location}。不要直接发布，先让我确认。",
                "primary": False,
            },
            {
                "label": "查终点附近餐厅",
                "prompt": f"帮我查「{destination_name}」附近的餐厅，并展示地图，先只查询。",
            },
            {
                "label": "换个目的地",
                "prompt": "帮我重新规划到另一个目的地的路线，并展示地图。",
            },
        ],
        "state": "completed",
        "intent": {
            "primary_intent": intent_analysis.get("primary_intent"),
            "next_action": intent_analysis.get("next_action"),
        },
    }


def _format_weather_direct_reply(weather_text: str) -> str:
    data = _safe_json_object(weather_text)
    forecasts = data.get("forecasts") if isinstance(data.get("forecasts"), list) else []
    if not forecasts:
        return ""
    city = data.get("city") or "北京"
    today = forecasts[0]
    day_weather = today.get("dayweather") or "未知"
    night_weather = today.get("nightweather") or "未知"
    day_temp = today.get("daytemp") or "-"
    night_temp = today.get("nighttemp") or "-"
    advice = "天气有降雨或强对流迹象，户外活动建议带伞并准备室内备选。"
    weather_text_joined = f"{day_weather}{night_weather}"
    if not any(cue in weather_text_joined for cue in ("雨", "雪", "雷", "沙尘")):
        advice = "天气风险不高，可以安排户外活动，但仍建议出门前再确认实时天气。"
    return (
        f"**{city}今日天气**\n\n"
        f"- 白天：{day_weather}，约 {day_temp}℃\n"
        f"- 夜间：{night_weather}，约 {night_temp}℃\n"
        f"- 建议：{advice}\n\n"
        "需要的话，我也可以继续帮你找附近的室内备选地点。"
    )


def _build_weather_artifact(weather_text: str, reply: str, intent_analysis: dict) -> dict | None:
    data = _safe_json_object(weather_text)
    forecasts = data.get("forecasts") if isinstance(data.get("forecasts"), list) else []
    if not forecasts:
        return None

    city = data.get("city") or "北京"
    today = forecasts[0]
    day_weather = today.get("dayweather") or "未知"
    night_weather = today.get("nightweather") or "未知"
    day_temp = today.get("daytemp") or "-"
    night_temp = today.get("nighttemp") or "-"
    advice = ""
    for line in str(reply or "").splitlines():
        if "建议：" in line:
            advice = line.split("建议：", 1)[-1].strip()
            break
    if not advice:
        advice = "建议出门前再确认实时天气。"

    return {
        "type": "weather",
        "title": f"{city}今日天气建议",
        "description": "已整理成可继续操作的天气卡片；后续如需创建活动，仍会先生成确认草稿。",
        "fields": [
            {"label": "城市", "value": city},
            {"label": "白天", "value": f"{day_weather} · {day_temp}℃"},
            {"label": "夜间", "value": f"{night_weather} · {night_temp}℃"},
            {"label": "建议", "value": advice},
        ],
        "actions": [
            {
                "label": "找室内备选地点",
                "prompt": f"根据{city}今天的天气，帮我找附近适合临时改去的室内地点，并展示地图",
                "primary": True,
            },
            {
                "label": "生成备选安排",
                "prompt": f"根据{city}今天的天气，帮我整理一个户外和室内两套备选安排，先不要发布或创建订单",
            },
            {
                "label": "只看可加入活动",
                "prompt": "帮我筛选今天适合室内进行、现在还能加入的约伴活动",
            },
        ],
        "state": "completed",
        "intent": {
            "primary_intent": intent_analysis.get("primary_intent"),
            "next_action": intent_analysis.get("next_action"),
        },
    }


async def build_direct_read_response(user_info: dict, user_message: str, intent_analysis: dict) -> dict | None:
    """Fast deterministic read path for simple map/weather tasks."""
    primary_intent = (intent_analysis.get("primary_intent") or "").lower()
    next_action = (intent_analysis.get("next_action") or "").lower()
    if intent_analysis.get("requires_confirmation") and primary_intent != "multi_step":
        return None
    if primary_intent == "multi_step" and next_action != "execute_read_tools":
        return None

    if primary_intent == "weather.query":
        await _emit_event("agent_step", {
            "phase": "weather_direct",
            "title": "查询天气",
            "detail": "正在直接调用天气工具，避免普通天气问题进入多轮智能体循环",
            "state": "running",
        })
        weather_text = await _invoke_tool_text(maps_weather, {"city": "北京"})
        reply = _format_weather_direct_reply(weather_text)
        if not reply:
            return None
        weather_artifact = _build_weather_artifact(weather_text, reply, intent_analysis)
        if weather_artifact:
            await _emit_event("artifact", weather_artifact)
        await _emit_event("agent_step", {
            "phase": "weather_direct",
            "title": "天气查询完成",
            "detail": "已获取天气结果并整理建议",
            "state": "completed",
        })
        return {
            "reply": reply,
            "tool_calls": [{"name": "maps_weather", "args": {"city": "北京"}}],
            "intent": intent_analysis,
            "artifacts": [weather_artifact] if weather_artifact else [],
        }

    if primary_intent in {"order.search", "order.manage"}:
        await _emit_event("agent_step", {
            "phase": "order_direct",
            "title": "查询约伴活动",
            "detail": "正在直接调用订单查询工具，优先返回可操作结果卡片",
            "state": "running",
        })
        uid = int((user_info or {}).get("uid") or (user_info or {}).get("id") or (user_info or {}).get("userId") or 0)
        if uid and _is_my_order_query(user_message):
            order_args = {"user_id": uid}
            order_text = await _invoke_tool_text(get_my_orders, order_args)
            tool_name = "get_my_orders"
        else:
            order_args = _extract_order_search_args(user_info, user_message)
            order_text = await _invoke_tool_text(search_orders, order_args)
            tool_name = "search_orders"

        order_has_results = bool(_parse_order_result_lines(order_text))
        order_artifact = _build_order_result_artifact(order_text, order_args, user_message, intent_analysis)
        if not order_artifact:
            return None
        await _emit_event("artifact", order_artifact)
        await _emit_event("agent_step", {
            "phase": "order_direct",
            "title": "订单查询完成",
            "detail": "已把可加入活动整理成结果卡片",
            "state": "completed",
        })
        order_tail = (
            "可以直接打开结果卡里的订单详情；如果要报名或创建新活动，我会先生成确认草稿。"
            if order_has_results
            else "我把空结果也整理成了下一步卡片；可以换条件继续查，或先创建一个需要你确认的约伴草稿。"
        )
        return {
            "reply": order_text + f"\n\n{order_tail}",
            "tool_calls": [{"name": tool_name, "args": order_args}],
            "intent": intent_analysis,
            "artifacts": [order_artifact],
        }

    if primary_intent == "content.search":
        await _emit_event("agent_step", {
            "phase": "content_direct",
            "title": "搜索校园动态",
            "detail": "正在直接调用动态搜索工具，优先返回可操作结果卡片",
            "state": "running",
        })
        keyword = _extract_content_keyword(user_message)
        content_args = {"keyword": keyword} if keyword else {}
        content_text = await _invoke_tool_text(search_contents, content_args)
        content_has_results = bool(_parse_content_result_lines(content_text))
        content_artifact = _build_content_result_artifact(content_text, keyword, intent_analysis)
        if not content_artifact:
            return None
        await _emit_event("artifact", content_artifact)
        await _emit_event("agent_step", {
            "phase": "content_direct",
            "title": "动态搜索完成",
            "detail": "已把校园动态整理成结果卡片",
            "state": "completed",
        })
        content_tail = (
            "可以直接打开结果卡里的动态详情；如果要评论、点赞或发布，我会先生成确认草稿。"
            if content_has_results
            else "我把空结果也整理成了下一步卡片；可以换主题继续查，或先生成一条需要你确认的动态草稿。"
        )
        return {
            "reply": content_text + f"\n\n{content_tail}",
            "tool_calls": [{"name": "search_contents", "args": content_args}],
            "intent": intent_analysis,
            "artifacts": [content_artifact],
        }

    if primary_intent == "user.profile":
        await _emit_event("agent_step", {
            "phase": "user_direct",
            "title": "查询用户资料",
            "detail": "正在直接调用用户资料工具，整理成可继续操作的资料卡片",
            "state": "running",
        })
        profile_user_id = _extract_user_profile_id(user_message)
        if profile_user_id:
            profile_text = await _invoke_tool_text(get_user_profile, {"user_id": profile_user_id})
            profile_artifact = _build_user_profile_artifact(profile_text, profile_user_id, intent_analysis)
            if not profile_artifact:
                return None
            await _emit_event("artifact", profile_artifact)
            await _emit_event("agent_step", {
                "phase": "user_direct",
                "title": "用户资料查询完成",
                "detail": "已把用户资料整理成结果卡片",
                "state": "completed",
            })
            return {
                "reply": profile_text + "\n\n我把资料整理成了用户卡片；后续如果要评论、发布或报名，我仍会先生成确认草稿。",
                "tool_calls": [{"name": "get_user_profile", "args": {"user_id": profile_user_id}}],
                "intent": intent_analysis,
                "artifacts": [profile_artifact],
            }

        keyword = _extract_user_search_keyword(user_message)
        if not keyword:
            return {
                "reply": "我需要一个用户 ID 或昵称才能查看主页资料。你可以直接说“查看用户 12 的主页”或“搜索小白的用户资料”。",
                "tool_calls": [],
                "intent": intent_analysis,
                "artifacts": [],
            }

        search_text = await _invoke_tool_text(search_users, {"keyword": keyword})
        search_artifact = _build_user_search_artifact(search_text, keyword, intent_analysis)
        if not search_artifact:
            return None
        await _emit_event("artifact", search_artifact)
        await _emit_event("agent_step", {
            "phase": "user_direct",
            "title": "用户搜索完成",
            "detail": "已把匹配用户整理成结果卡片",
            "state": "completed",
        })
        return {
            "reply": search_text + "\n\n可以从结果卡继续查看某个用户资料；所有后续写操作都会先确认。",
            "tool_calls": [{"name": "search_users", "args": {"keyword": keyword}}],
            "intent": intent_analysis,
            "artifacts": [search_artifact],
        }

    if primary_intent not in {"map.search", "multi_step"}:
        return None

    keyword = _extract_map_keyword(user_message)
    center, center_name = _select_campus_center(user_info, user_message)
    if _is_route_request(user_message):
        await _emit_event("agent_step", {
            "phase": "route_direct",
            "title": "解析路线请求",
            "detail": "正在确定起点、终点和路线方式",
            "state": "running",
        })
        destination_query = _extract_route_destination_text(user_message)
        destination_keyword = _extract_map_keyword(destination_query or user_message)
        destination_name = destination_query or destination_keyword
        destination_location = ""
        tool_calls = []

        use_nearby_destination = (
            not destination_query
            or "最近" in destination_query
            or "附近" in destination_query
            or destination_query in {destination_keyword, f"最近的{destination_keyword}", f"附近的{destination_keyword}"}
        )
        if use_nearby_destination and destination_keyword != "校园周边":
            search_text = await _invoke_tool_text(
                maps_around_search,
                {"location": center, "keywords": destination_keyword, "radius": "3000"},
            )
            tool_calls.append({"name": "maps_around_search", "args": {"location": center, "keywords": destination_keyword, "radius": "3000"}})
            data = _safe_json_object(search_text)
            pois = data.get("pois") if isinstance(data.get("pois"), list) else []
            resolved = await _resolve_poi_locations(pois, limit=1)
            if resolved:
                destination = resolved[0]
                destination_name = destination.get("name") or destination_keyword
                destination_location = destination.get("location") or ""
        else:
            geo_text = await _invoke_tool_text(maps_geo, {"address": destination_query, "city": "北京"})
            tool_calls.append({"name": "maps_geo", "args": {"address": destination_query, "city": "北京"}})
            destination_location = _extract_location_from_geo(geo_text)

        if not destination_location or "," not in destination_location:
            return None

        mode_label, direction_tool, direction_tool_name = _route_mode(user_message)
        await _emit_event("agent_step", {
            "phase": "route_direct",
            "title": "调用路线规划",
            "detail": f"正在规划从{center_name}到{destination_name}的{mode_label}路线",
            "state": "running",
        })
        route_text = await _invoke_tool_text(direction_tool, {"origin": center, "destination": destination_location})
        tool_calls.append({"name": direction_tool_name, "args": {"origin": center, "destination": destination_location}})
        route_info = _extract_route_path(route_text)
        reply = _format_route_direct_reply(
            center_name,
            center,
            destination_name,
            destination_location,
            mode_label,
            route_info,
        )
        route_artifact = _build_route_artifact(
            center_name,
            destination_name,
            destination_location,
            mode_label,
            route_info,
            intent_analysis,
        )
        await _emit_event("artifact", route_artifact)
        await _emit_event("agent_step", {
            "phase": "route_direct",
            "title": "路线规划完成",
            "detail": "已把路线、起终点地图和后续动作整理成卡片",
            "state": "completed",
        })
        return {
            "reply": reply,
            "tool_calls": tool_calls,
            "intent": intent_analysis,
            "artifacts": [route_artifact],
        }

    include_weather_context = bool(intent_analysis.get("weather_context")) or _has_weather_context(user_message)
    weather_reply = ""
    weather_artifact = None
    weather_tool_calls = []
    if include_weather_context:
        await _emit_event("agent_step", {
            "phase": "weather_direct",
            "title": "查询天气参考",
            "detail": "这轮请求同时提到天气和地点，先直接查询天气数据",
            "state": "running",
        })
        weather_text = await _invoke_tool_text(maps_weather, {"city": "北京"})
        weather_reply = _format_weather_direct_reply(weather_text)
        weather_artifact = _build_weather_artifact(weather_text, weather_reply, intent_analysis) if weather_reply else None
        weather_tool_calls.append({"name": "maps_weather", "args": {"city": "北京"}})
        if weather_artifact:
            await _emit_event("artifact", weather_artifact)
        await _emit_event("agent_step", {
            "phase": "weather_direct",
            "title": "天气参考完成",
            "detail": "已把天气结果整理成卡片，并继续查询地点",
            "state": "completed",
        })
    await _emit_event("agent_step", {
        "phase": "map_direct",
        "title": "查询附近地点",
        "detail": f"正在以{center_name}为中心搜索：{keyword}",
        "state": "running",
    })
    search_text = await _invoke_tool_text(
        maps_around_search,
        {"location": center, "keywords": keyword, "radius": "3000"},
    )
    data = _safe_json_object(search_text)
    pois = data.get("pois") if isinstance(data.get("pois"), list) else []
    if not pois:
        return None

    await _emit_event("agent_step", {
        "phase": "map_geocode",
        "title": "补全地图坐标",
        "detail": "正在为推荐地点补全经纬度，方便前端直接渲染地图",
        "state": "running",
    })
    resolved = await _resolve_poi_locations(pois, limit=3)
    await _emit_event("agent_step", {
        "phase": "map_geocode",
        "title": "地图坐标已补全",
        "detail": f"已为 {len(resolved)} 个地点解析经纬度",
        "state": "completed",
    })
    reply = _format_map_direct_reply(keyword, center_name, resolved)
    if not reply:
        return None
    followup_artifact = _build_map_followup_artifact(keyword, center_name, resolved, intent_analysis)
    await _emit_event("artifact", followup_artifact)
    await _emit_event("agent_step", {
        "phase": "map_direct",
        "title": "地图推荐完成",
        "detail": f"已整理 {len(resolved)} 个可渲染地图的地点",
        "state": "completed",
    })
    await _emit_event("agent_step", {
        "phase": "response",
        "title": "整理回复",
        "detail": "正在把地点结果整理成可交互地图卡片",
        "state": "completed",
    })
    artifacts = [artifact for artifact in (weather_artifact, followup_artifact) if artifact]
    if weather_reply:
        reply = f"{weather_reply}\n\n---\n\n{reply}"
    return {
        "reply": reply,
        "tool_calls": weather_tool_calls + [
            {"name": "maps_around_search", "args": {"location": center, "keywords": keyword, "radius": "3000"}},
            {"name": "maps_geo", "args": {"limit": 3}},
        ],
        "intent": intent_analysis,
        "artifacts": artifacts,
    }


# ==================== 子 Agent 执行器 ====================

async def _run_sub_agent(agent_key: str, agent_name: str, system_prompt: str, tools: list, task: str) -> str:
    """运行一个子 Agent，返回其最终回复文本。"""
    llm = _get_llm(streaming=False)
    agent = create_react_agent(llm, tools)

    try:
        await _emit_event("agent_step", {
            "phase": agent_key,
            "agent": agent_key,
            "title": f"{agent_name}开始处理",
            "detail": task[:180],
            "state": "running",
        })
        result = await _await_with_soft_timeout(
            agent.ainvoke(
                {
                    "messages": [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=task),
                    ],
                },
                config={"recursion_limit": SUB_AGENT_RECURSION_LIMIT},
            ),
            SUB_AGENT_TIMEOUT_SECONDS,
        )

        # 提取最终 AI 回复
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                await _emit_event("agent_step", {
                    "phase": agent_key,
                    "agent": agent_key,
                    "title": f"{agent_name}完成",
                    "detail": "已返回处理结果",
                    "state": "completed",
                })
                return msg.content

        return "子Agent 未返回有效结果。"
    except asyncio.TimeoutError:
        await _emit_event("agent_step", {
            "phase": agent_key,
            "agent": agent_key,
            "title": f"{agent_name}执行超时",
            "detail": f"超过 {SUB_AGENT_TIMEOUT_SECONDS} 秒仍未返回，已停止本次子智能体调用以避免界面长时间等待",
            "state": "failed",
        })
        return f"{agent_name}执行超时。请基于已经获得的信息回复用户，或建议用户稍后重试/缩小查询范围。"
    except Exception as e:
        logger.error("Sub-agent error: %s", e, exc_info=True)
        await _emit_event("agent_step", {
            "phase": agent_key,
            "agent": agent_key,
            "title": f"{agent_name}执行失败",
            "detail": str(e),
            "state": "failed",
        })
        return f"子Agent 执行出错: {str(e)}"


# ==================== 子 Agent 包装为 LangChain 工具 ====================

@tool
async def call_order_agent(task: str) -> str:
    """调用订单专家完成订单相关任务。如：搜索约伴活动、创建订单、查看订单、申请加入、接受申请等。

    Args:
        task: 具体任务描述，需包含完整的参数信息。如"搜索良乡校区的篮球约伴活动"、"为用户ID=1创建篮球订单，良乡校区体育馆，2026-03-26 15:00:00"
    """
    return await _run_guarded_sub_agent("order", "订单专家", ORDER_AGENT_PROMPT, ORDER_TOOLS, task)


@tool
async def call_social_agent(task: str) -> str:
    """调用社交专家完成校园动态相关任务。如：搜索动态、查看帖子、发评论、点赞、搜索用户等。

    Args:
        task: 具体任务描述。如"搜索关于篮球的动态"、"给动态#12点赞，用户ID=1"
    """
    return await _run_guarded_sub_agent("content", "动态专家", SOCIAL_AGENT_PROMPT, SOCIAL_TOOLS, task)


@tool
async def call_map_agent(task: str) -> str:
    """调用地图天气专家完成位置和天气相关任务。如：搜索地点、查附近、查天气、查路线等。

    Args:
        task: 具体任务描述。如"搜索北京理工大学良乡校区的位置"、"查询北京今天的天气"
    """
    return await _run_guarded_sub_agent("map", "地图天气专家", MAP_AGENT_PROMPT, MAP_TOOLS, task)


# 主 Agent 的工具列表（3 个子 Agent）
MAIN_AGENT_TOOLS = [call_order_agent, call_social_agent, call_map_agent]


# ==================== 消息历史构建 ====================

def _build_message_history(history: list) -> list:
    messages = []
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


# ==================== 对外接口 ====================

async def chat(
    user_info: dict,
    memories: list,
    history: list,
    user_message: str,
) -> dict:
    """非流式多 Agent 调用。"""
    confirmed_execution = await build_confirmed_execution_response(user_info, history, user_message)
    if confirmed_execution:
        return confirmed_execution

    intent_analysis = await analyze_intent(user_info, memories, history, user_message)
    plan_artifact = await _emit_execution_plan(intent_analysis)
    if _requires_confirmation_gate(intent_analysis):
        artifact = await build_confirmation_artifact(user_info, history, user_message, intent_analysis)
        return {
            "reply": artifact.get("reply", ""),
            "tool_calls": [],
            "intent": intent_analysis,
            "artifacts": [item for item in (plan_artifact, artifact) if item],
        }

    if (
        (intent_analysis.get("primary_intent") or "").lower() == "chat.general"
        and (intent_analysis.get("next_action") or "").lower() == "direct_answer"
    ):
        return await build_general_help_response(intent_analysis)

    direct_read_result = await build_direct_read_response(user_info, user_message, intent_analysis)
    if direct_read_result:
        if plan_artifact:
            direct_read_result["artifacts"] = [plan_artifact] + list(direct_read_result.get("artifacts") or [])
        return direct_read_result

    await _emit_event("agent_step", {
        "phase": "planning",
        "title": "规划执行步骤",
        "detail": "正在根据意图分析结果调度校园服务智能体",
        "state": "running",
    })
    system_prompt = build_main_agent_prompt(user_info, memories)
    messages = _build_message_history(history)
    messages.append(HumanMessage(content=user_message))

    llm = _get_llm(streaming=False)
    main_agent = create_react_agent(llm, MAIN_AGENT_TOOLS)
    allowed_delegation_agents = _build_allowed_delegation_agents(intent_analysis)

    delegation_token = _delegation_state.set({
        "total": 0,
        "counts": {},
        "results": {},
    })
    allowed_token = _allowed_delegation_agents.set(allowed_delegation_agents)
    try:
        result = await main_agent.ainvoke(
            {
                "messages": [SystemMessage(content=system_prompt), _build_intent_system_message(intent_analysis)] + messages,
            },
            config={"recursion_limit": MAIN_AGENT_RECURSION_LIMIT},
        )
    finally:
        _allowed_delegation_agents.reset(allowed_token)
        _delegation_state.reset(delegation_token)

    tool_calls_log = []
    final_reply = ""

    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_log.append({"name": tc["name"], "args": tc["args"]})
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            final_reply = msg.content

    await _emit_event("agent_step", {
        "phase": "response",
        "title": "整理回复",
        "detail": "正在把工具结果整理为可阅读的回答",
        "state": "completed",
    })

    return {
        "reply": final_reply,
        "tool_calls": tool_calls_log,
        "intent": intent_analysis,
        "artifacts": [plan_artifact] if plan_artifact else [],
    }


async def stream_chat(
    user_info: dict,
    memories: list,
    history: list,
    user_message: str,
) -> AsyncIterator[dict]:
    """流式多 Agent 调用，实时输出结构化进度事件和最终文本。"""
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event: dict):
        await queue.put(event)

    async def run_agent():
        token = _event_sink.set(emit)
        try:
            result = await chat(user_info, memories, history, user_message)
            await queue.put({"event": "__result__", "data": result})
        except Exception as e:
            logger.error("Stream error: %s", e, exc_info=True)
            await queue.put({"event": "error", "data": str(e)})
        finally:
            _event_sink.reset(token)
            await queue.put({"event": "__complete__", "data": ""})

    task = asyncio.create_task(run_agent())
    reply_sent = False

    while True:
        event = await queue.get()
        event_name = event.get("event")

        if event_name == "__result__":
            result = event.get("data") or {}
            reply = result.get("reply") or "抱歉，AI 未返回有效内容。"
            chunk_size = 4
            for i in range(0, len(reply), chunk_size):
                yield {"event": "delta", "data": reply[i:i + chunk_size]}
            reply_sent = True
            continue

        if event_name == "__complete__":
            if not task.done():
                await task
            if reply_sent:
                yield {"event": "done", "data": ""}
            break

        yield event


async def extract_memory(user_message: str, assistant_reply: str) -> list:
    """从对话中提取用户记忆。"""
    llm = _get_llm(streaming=False)
    prompt = MEMORY_EXTRACTION_PROMPT.format(
        user_message=user_message,
        assistant_reply=assistant_reply,
    )

    try:
        result = await llm.ainvoke([HumanMessage(content=prompt)])
        text = result.content.strip()

        if text.lower() == "none" or not text:
            return []

        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        parsed = json.loads(text)
        if isinstance(parsed, list):
            return filter_extracted_memories(parsed, user_message, assistant_reply)
    except Exception as e:
        logger.warning("Memory extraction failed: %s", e)

    return []
