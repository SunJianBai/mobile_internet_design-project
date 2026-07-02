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
from app.tools_order import ORDER_EXTRA_TOOLS, apply_to_order, accept_applicant, complete_order
from app.tools_content import CONTENT_TOOLS, create_content, create_comment, like_content
from app.tools_user import USER_TOOLS
from app.mcp_tools import MCP_TOOLS, maps_around_search, maps_geo, maps_weather
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

INTENT_ANALYSIS_PROMPT = """你是 CampusHub 的意图分析智能体。请基于用户消息、最近对话和用户信息判断请求类型。

要求：
- 不要依赖单纯关键词匹配，要理解语义。
- 只输出 JSON，不要输出 Markdown 或解释。
- 写操作包括：创建订单、发布动态、评论、点赞/取消点赞、报名、接受申请、完成订单、删除内容。
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
- Do not turn a recommendation/search request into content.create or order.create unless the user explicitly asks to publish, create, invite, organize, post, or place an order/activity in CampusHub.
- For "我想要找3个人一起去洗脚按摩，有什么推荐的店吗", classify as:
  {"primary_intent":"map.search","domain":"map","operation_type":"read","requires_confirmation":false,"confidence":0.9,"summary":"用户想查询并推荐适合多人前往的足疗按摩店","missing_slots":[],"suggested_agents":["map_weather"],"next_action":"execute_read_tools"}
- For "附近有没有适合三个人吃饭的店", classify as map.search/read.
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
- Write tasks: create/publish/edit/delete/comment/like/apply/accept/complete/order/sign up. They require a confirmation draft before any database write.
- A recommendation for stores, venues, routes, or nearby places is map.search/read, even if the user mentions people count, time, budget, or "一起".
- Only classify as content.create/order.create when the user explicitly asks CampusHub to publish/create/organize/post an activity/order/dynamic.
- If the user is editing a previous draft, preserve the draft's domain/action from context and require confirmation.

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
- If the user wants the system to create, publish, edit, delete, comment, like, apply, accept, or complete something, classify it as write or mixed.
- A write classification does not mean immediate execution. If enough information is present, use next_action=prepare_draft and requires_confirmation=true. If required fields are missing, use next_action=ask_clarification and requires_confirmation=true.
- If one request combines read-first work with a possible later create/publish/apply action, classify it as mixed and keep requires_confirmation=true.
- Read-only search, browse, explain, recommend, route, weather, and place lookup tasks are read operations.
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
  "action_kind": "order.create|content.create|content.comment|content.like|order.apply|order.accept|order.complete|other.write",
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
- Do not call tools and do not claim that data has already been created, published, liked, applied, accepted, completed, or deleted.
- The title must match the actual action_kind and current user request. Do not copy example titles.
- For action_kind=content.create, use a title like "确认发布动态".
- For action_kind=order.create, use a title like "确认创建约伴活动".
- If required information is missing, list it in missing_fields and make reply ask the user to complete it.
- If enough information is present, make reply ask the user to confirm before execution.

Return this JSON shape:
{{
  "title": "确认发布动态",
  "description": "one sentence describing the pending write operation",
  "action_kind": "order.create|content.create|content.comment|content.like|order.apply|order.accept|order.complete|other.write",
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


def _get_delegation_state() -> dict:
    state = _delegation_state.get()
    if state is None:
        state = {
            "total": 0,
            "counts": {},
            "results": {},
        }
        _delegation_state.set(state)
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

    if fingerprint in state["results"]:
        await _emit_event("agent_step", {
            "phase": "delegation_guard",
            "agent": agent_key,
            "title": f"{agent_name}复用已有结果",
            "detail": "检测到同一轮中重复委派了相同任务，已复用上一次结果以避免循环调用",
            "state": "completed",
        })
        return state["results"][fingerprint]

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
    write_cues = ("创建", "发布", "发个动态", "发一条", "报名", "申请加入", "下单", "约饭订单", "约伴订单")
    return (
        any(cue in text for cue in read_cues)
        and any(cue in text for cue in transition_cues)
        and any(cue in text for cue in write_cues)
    )


def _has_any(text: str, cues: tuple[str, ...]) -> bool:
    return any(cue in text for cue in cues)


def _contains_blocking_write_negation(text: str) -> bool:
    """Return true when the user is negating the write itself, not asking for confirmation first."""
    if _has_any(text, ("取消", "不想")):
        return True
    direct_confirmation_cues = ("不要直接", "别直接", "不要马上", "别马上", "先确认", "先让我确认")
    if _has_any(text, direct_confirmation_cues):
        return False
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
            "不要发订单",
            "别发订单",
            "不要报名",
            "别报名",
            "不要申请",
            "别申请",
            "不要评论",
            "别评论",
            "不要点赞",
            "别点赞",
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

    hard_write_cues = (
        "发布动态",
        "发一条动态",
        "发个动态",
        "发动态",
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
        "先只",
        "只推荐",
        "先推荐",
        "先看看",
        "先查",
        "只是",
        "仅",
    )
    if _has_any(text, hard_write_cues) and not _has_any(text, read_only_overrides):
        return None

    weather_read_cues = ("天气", "下雨", "气温", "温度", "适不适合", "适合不适合")
    if _has_any(text, weather_read_cues) and _has_any(text, ("查", "查询", "看看", "今天", "明天", "北京", "户外", "跑步")):
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

    if _has_any(text, generic_read_cues) and _has_any(text, ("动态", "帖子", "评论区", "校园圈")):
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
        or _has_any(text, ("约伴", "我发布过", "我参加过", "报名记录", "申请记录"))
    )
    has_order_activity_context = "活动" in text and _has_any(text, ("约伴", "报名", "加入", "我发布过", "我参加过"))
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
        }

    return None


def _detect_draft_edit_shortcut(history: list, user_message: str) -> dict | None:
    """Keep draft edits in the original write domain without another slow router round."""
    text = " ".join(str(user_message or "").split())
    if not text:
        return None

    edit_cues = ("改成", "改为", "修改", "调整", "换成", "补充", "加上", "删掉", "去掉")
    if not _has_any(text, edit_cues):
        return None

    recent = "\n".join(str(item.get("content", "")) for item in (history or [])[-6:])
    if not _has_any(recent, ("草稿", "待确认", "确认草稿", "确认创建", "确认发布", "确认执行")):
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

    if _has_any(text, ("记住", "以后优先", "偏好")):
        return {
            **base,
            "primary_intent": "memory.manage",
            "domain": "memory",
            "summary": "用户想让 AI 记住一条偏好或事实",
            "missing_slots": [],
            "suggested_agents": ["memory"],
            "next_action": "prepare_draft",
        }

    if "动态" in text and _has_any(text, ("评论", "回复")):
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

    if _has_any(text, ("发布动态", "发一条动态", "发个动态", "发动态")):
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


def _detect_timeout_read_fallback(user_message: str) -> dict | None:
    """Conservative read-only fallback used only when the semantic router is unavailable."""
    text = " ".join(str(user_message or "").split())
    if not text:
        return None
    if _detect_safety_intent_shortcut(text):
        return None

    read_cues = ("找", "看看", "查询", "查一下", "推荐", "附近", "有没有", "怎么走", "路线", "地图")
    generic_read_cues = read_cues + ("搜索", "搜一下", "列出", "哪些", "信息", "主页")

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
    return (
        confidence < 0.65
        or primary_intent == "unknown"
        or operation_type == "unknown"
        or operation_type in {"write", "mixed"}
        or next_action == "direct_answer"
        or _looks_like_read_then_write_request(user_message, analysis)
    )


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
        timeout_fallback = _detect_timeout_read_fallback(user_message) if router_timeout else None
        if timeout_fallback:
            analysis = _normalize_intent_analysis(timeout_fallback)
            analysis["router_timeout"] = True
            analysis["router_error"] = e.__class__.__name__
            await _emit_event("agent_step", {
                "phase": "intent_fallback",
                "title": "意图路由降级",
                "detail": "轻量模型响应超时，已将明确的地点/店铺推荐请求降级为地图只读查询",
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

    coords = ""
    coord_match = re.search(r"坐标[:：]?\s*([0-9]{2,3}\.\d+)\s*[,，]\s*([0-9]{1,2}\.\d+)", text)
    if coord_match:
        coords = f"{coord_match.group(1)}, {coord_match.group(2)}"
    return title, coords


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


def _enrich_order_confirmation_fields(
    fields: list,
    missing_fields: list,
    user_info: dict,
    history: list,
    user_message: str,
    intent_analysis: dict,
) -> tuple[list, list]:
    if (intent_analysis.get("primary_intent") or "").lower() != "order.create":
        return fields, missing_fields

    enriched_fields = [dict(item) if isinstance(item, dict) else item for item in (fields or [])]
    enriched_missing = list(missing_fields or [])
    context_text = _conversation_text(history, user_message)
    location_title, coords = _extract_map_selection(user_message)

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


def _is_confirmed_artifact_message(text: str) -> bool:
    text = str(text or "")
    return any(cue in text for cue in (
        "我确认执行这个草稿",
        "我确认按修改后的内容执行这个草稿",
        "确认执行这个草稿",
    ))


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
    elif "明天" in text:
        day_offset = 1
    elif any(cue in text for cue in ("今天", "今晚")):
        day_offset = 0

    match = re.search(r"([0-9一二两三四五六七八九十]{1,3})[点时:：](\d{1,2})?", text)
    if day_offset is not None and match:
        hour = _parse_hour_token(match.group(1))
        if hour is not None:
            if any(cue in text for cue in ("下午", "晚上", "今晚")) and hour < 12:
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


def _infer_confirmed_action_kind(text: str, fields: dict) -> str:
    lowered = str(text or "").lower()
    field_labels = " ".join(fields.keys())
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
    if "动态" in lowered or "动态" in field_labels or _field_value(fields, ("动态内容", "正文", "内容")):
        return "content.create"
    if "约伴" in lowered or "订单" in lowered or "活动类型" in field_labels:
        return "order.create"
    return "other.write"


def _intent_for_confirmed_execution(action_kind: str) -> dict:
    domain = "content" if action_kind.startswith("content.") else "order" if action_kind.startswith("order.") else "other"
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
    return {
        "reply": result_text,
        "tool_calls": [{"name": "create_order", "args": args}],
        "intent": intent,
    }


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
    return {
        "reply": result_text,
        "tool_calls": [{"name": "create_content", "args": args}],
        "intent": intent,
    }


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
    return {
        "reply": result_text,
        "tool_calls": [{"name": "create_comment", "args": args}],
        "intent": intent,
    }


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
    return {
        "reply": result_text,
        "tool_calls": [{"name": "like_content", "args": args}],
        "intent": intent,
    }


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
    return {
        "reply": result_text,
        "tool_calls": [{"name": "apply_to_order", "args": args}],
        "intent": intent,
    }


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
    return {
        "reply": result_text,
        "tool_calls": [{"name": "accept_applicant", "args": args}],
        "intent": intent,
    }


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
    return {
        "reply": result_text,
        "tool_calls": [{"name": "complete_order", "args": args}],
        "intent": intent,
    }


async def build_confirmed_execution_response(user_info: dict, history: list, user_message: str) -> dict | None:
    """Execute a structured draft only after the user explicitly confirms it."""
    if not _is_confirmed_artifact_message(user_message):
        return None

    fields = _parse_confirmed_artifact_fields(user_message)
    action_kind = _infer_confirmed_action_kind(user_message, fields)
    if action_kind == "order.create":
        return await _execute_confirmed_order(user_info, fields, user_message)
    if action_kind == "content.create":
        return await _execute_confirmed_content(user_info, fields, user_message)
    if action_kind == "content.comment":
        return await _execute_confirmed_comment(user_info, fields, user_message)
    if action_kind == "content.like":
        return await _execute_confirmed_like(user_info, fields, user_message)
    if action_kind == "order.apply":
        return await _execute_confirmed_order_apply(user_info, fields, user_message)
    if action_kind == "order.accept":
        return await _execute_confirmed_order_accept(user_info, fields, user_message)
    if action_kind == "order.complete":
        return await _execute_confirmed_order_complete(user_info, fields, user_message)

    return {
        "reply": "我已收到确认，但这个草稿类型暂时还不能自动执行。请改用订单、动态、评论、点赞或报名草稿，或继续手动处理。",
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

    artifact = {
        "type": "confirmation",
        "title": title,
        "description": description,
        "actionKind": draft.get("action_kind") or intent_analysis.get("primary_intent") or "other.write",
        "fields": fields,
        "missingFields": missing_fields,
        "requiresConfirmation": True,
        "confirmMessage": f"我确认执行这个草稿：{title}",
        "editMessage": f"我想修改这个草稿：{title}",
        "cancelMessage": f"取消这个草稿：{title}",
        "reply": reply,
    }
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
        (("按摩", "洗脚", "足疗", "推拿", "spa"), "按摩"),
        (("吃饭", "餐厅", "饭店", "美食", "约饭"), "餐厅"),
        (("咖啡", "奶茶"), "咖啡"),
        (("电影院", "影院", "电影"), "电影院"),
        (("篮球",), "篮球场"),
        (("羽毛球",), "羽毛球馆"),
        (("自习", "图书馆"), "图书馆"),
        (("超市", "便利店"), "超市"),
        (("玩", "放松", "休闲"), "休闲娱乐"),
    ]
    for cues, keyword in keyword_groups:
        if any(cue in text for cue in cues):
            return keyword
    return "校园周边"


def _extract_location_from_geo(text: str) -> str:
    data = _safe_json_object(text)
    candidates = data.get("return") or data.get("geocodes") or []
    if not isinstance(candidates, list):
        return ""
    for item in candidates:
        if isinstance(item, dict) and item.get("location"):
            return str(item["location"])
    return ""


async def _invoke_tool_text(tool_obj, args: dict) -> str:
    return await asyncio.to_thread(tool_obj.invoke, args)


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
        await _emit_event("agent_step", {
            "phase": "weather_direct",
            "title": "天气查询完成",
            "detail": "已获取天气结果并整理建议",
            "state": "completed",
        })
        return {"reply": reply, "tool_calls": [{"name": "maps_weather", "args": {"city": "北京"}}], "intent": intent_analysis}

    if primary_intent not in {"map.search", "multi_step"}:
        return None

    keyword = _extract_map_keyword(user_message)
    center, center_name = _select_campus_center(user_info, user_message)
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
    return {
        "reply": reply,
        "tool_calls": [
            {"name": "maps_around_search", "args": {"location": center, "keywords": keyword, "radius": "3000"}},
            {"name": "maps_geo", "args": {"limit": 3}},
        ],
        "intent": intent_analysis,
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
    if _requires_confirmation_gate(intent_analysis):
        artifact = await build_confirmation_artifact(user_info, history, user_message, intent_analysis)
        return {
            "reply": artifact.get("reply", ""),
            "tool_calls": [],
            "intent": intent_analysis,
            "artifacts": [artifact],
        }

    if (
        (intent_analysis.get("primary_intent") or "").lower() == "chat.general"
        and (intent_analysis.get("next_action") or "").lower() == "direct_answer"
    ):
        return await build_general_help_response(intent_analysis)

    direct_read_result = await build_direct_read_response(user_info, user_message, intent_analysis)
    if direct_read_result:
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

    delegation_token = _delegation_state.set({
        "total": 0,
        "counts": {},
        "results": {},
    })
    try:
        result = await main_agent.ainvoke(
            {
                "messages": [SystemMessage(content=system_prompt), _build_intent_system_message(intent_analysis)] + messages,
            },
            config={"recursion_limit": MAIN_AGENT_RECURSION_LIMIT},
        )
    finally:
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

    return {"reply": final_reply, "tool_calls": tool_calls_log, "intent": intent_analysis}


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
            return [
                m for m in parsed
                if isinstance(m, dict) and "category" in m and "content" in m
            ]
    except Exception as e:
        logger.warning("Memory extraction failed: %s", e)

    return []
