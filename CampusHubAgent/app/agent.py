"""Multi-agent architecture: 主Agent + 子Agent-as-Tool (模式B).

主Agent 通过 ReAct 循环调用 3 个子Agent（订单/社交/地图天气），
每个子Agent 内部又是一个带原子工具的 ReAct Agent。
"""

import json
import logging
import asyncio
import contextvars
import hashlib
import time
from collections import OrderedDict
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
from app.tools_order import ORDER_EXTRA_TOOLS
from app.tools_content import CONTENT_TOOLS
from app.tools_user import USER_TOOLS
from app.mcp_tools import MCP_TOOLS
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
ROUTER_TIMEOUT_SECONDS = 18
INTENT_REVIEW_TIMEOUT_SECONDS = 25
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

User: 附近有没有适合三个人吃饭的店
Output: {"primary_intent":"map.search","domain":"map","operation_type":"read","requires_confirmation":false,"confidence":0.9,"summary":"用户想查找适合三人就餐的附近餐厅","missing_slots":[],"suggested_agents":["map_weather"],"next_action":"execute_read_tools"}

User: 帮我发个动态找三个人一起去按摩
Output: {"primary_intent":"content.create","domain":"content","operation_type":"write","requires_confirmation":true,"confidence":0.92,"summary":"用户想发布一条寻找同伴的校园动态","missing_slots":[],"suggested_agents":["content_draft"],"next_action":"prepare_draft"}

User: 帮我创建一个三人按摩约伴订单
Output: {"primary_intent":"order.create","domain":"order","operation_type":"write","requires_confirmation":true,"confidence":0.9,"summary":"用户想创建三人按摩约伴订单","missing_slots":["地点","时间"],"suggested_agents":["order_draft"],"next_action":"ask_clarification"}

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
- Read-only search, browse, explain, recommend, route, weather, and place lookup tasks are read operations.
- Return JSON only. No Markdown. No explanation.

Examples:
User: 帮我发布一条动态：今天下午一起去图书馆自习，欢迎同学加入。
Output: {{"primary_intent":"content.create","domain":"content","operation_type":"write","requires_confirmation":true,"confidence":0.95,"summary":"用户想发布一条校园动态","missing_slots":[],"suggested_agents":["content_draft"],"next_action":"prepare_draft"}}

User: 帮我创建一个明天下午三点的篮球活动
Output: {{"primary_intent":"order.create","domain":"order","operation_type":"write","requires_confirmation":true,"confidence":0.9,"summary":"用户想创建约伴活动","missing_slots":["地点","参与人数"],"suggested_agents":["order_draft"],"next_action":"ask_clarification"}}

User: 帮我找附近的篮球场
Output: {{"primary_intent":"map.search","domain":"map","operation_type":"read","requires_confirmation":false,"confidence":0.9,"summary":"用户想查询附近篮球场","missing_slots":[],"suggested_agents":["map_weather"],"next_action":"execute_read_tools"}}

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
    operation_type = (result.get("operation_type") or "").lower()
    next_action = (result.get("next_action") or "").lower()
    if operation_type in {"write", "mixed"} and next_action in {"ask_clarification", "prepare_draft", "wait_confirmation"}:
        result["requires_confirmation"] = True
    return result


def _should_review_intent(analysis: dict) -> bool:
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
    )


async def review_intent(
    user_info: dict,
    memories: list,
    history: list,
    user_message: str,
    previous_analysis: dict,
) -> dict:
    await _emit_event("agent_step", {
        "phase": "intent_review",
        "title": "复核低置信度意图",
        "detail": "快模型判断不够确定，正在调用主模型复核是否涉及写操作或子智能体调度",
        "state": "running",
    })
    prompt = _render_intent_prompt(previous_analysis, user_info, memories, history, user_message)
    try:
        result = await asyncio.wait_for(
            _get_llm(streaming=False, temperature=0, max_tokens=700).ainvoke([HumanMessage(content=prompt)]),
            timeout=INTENT_REVIEW_TIMEOUT_SECONDS,
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

    await _emit_event("agent_step", {
        "phase": "intent",
        "title": "分析用户意图",
        "detail": "正在用轻量模型判断任务类型、风险和需要的子智能体",
        "state": "running",
    })
    prompt = _render_intent_prompt(None, user_info, memories, history, user_message)
    try:
        result = await asyncio.wait_for(
            _get_router_llm().ainvoke([HumanMessage(content=prompt)]),
            timeout=ROUTER_TIMEOUT_SECONDS,
        )
        analysis = _normalize_intent_analysis(_safe_json_loads(result.content))
        analysis["router_timeout"] = False
    except Exception as e:
        logger.warning("Intent analysis failed: %s", e)
        analysis = _normalize_intent_analysis({
            "summary": "意图分析暂时失败，交由主智能体继续判断。",
            "next_action": "ask_clarification",
        })
        analysis["router_timeout"] = isinstance(e, asyncio.TimeoutError)
        analysis["router_error"] = e.__class__.__name__

    if _should_review_intent(analysis):
        analysis = await review_intent(user_info, memories, history, user_message, analysis)

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
    return SystemMessage(content=content)


def _requires_confirmation_gate(intent_analysis: dict) -> bool:
    operation_type = (intent_analysis.get("operation_type") or "").lower()
    next_action = (intent_analysis.get("next_action") or "").lower()
    if operation_type not in {"write", "mixed"}:
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
    fields = _normalize_artifact_fields(draft.get("fields") if isinstance(draft.get("fields"), list) else [], missing_fields)
    title = draft.get("title") or "请确认这次操作"
    description = draft.get("description") or intent_analysis.get("summary") or "这是一个需要确认后才会执行的写操作。"
    reply = draft.get("reply")
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
        result = await agent.ainvoke(
            {
                "messages": [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=task),
                ],
            },
            config={"recursion_limit": SUB_AGENT_RECURSION_LIMIT},
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
    intent_analysis = await analyze_intent(user_info, memories, history, user_message)
    if _requires_confirmation_gate(intent_analysis):
        artifact = await build_confirmation_artifact(user_info, history, user_message, intent_analysis)
        return {
            "reply": artifact.get("reply", ""),
            "tool_calls": [],
            "intent": intent_analysis,
            "artifacts": [artifact],
        }

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
