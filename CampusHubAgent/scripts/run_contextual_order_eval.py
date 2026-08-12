"""Run regression checks for map-result follow-ups that create order drafts.

The checks monkeypatch the confirmation-draft LLM, so they do not call a real
model, the Java backend, or AMap. They verify that a user can first ask for map
recommendations and then say "use the first one" to create a safe confirmation
draft with the selected place carried forward.

Examples:
  python scripts/run_contextual_order_eval.py
  python scripts/run_contextual_order_eval.py --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_USER = {
    "uid": 4,
    "nickname": "Codex QA",
    "campus": "LIANGXIANG",
}

MAP_HISTORY = [
    {
        "role": "user",
        "content": "先找三家适合三个人去的足疗店，把地图给我",
    },
    {
        "role": "assistant",
        "content": (
            "我先按北京理工大学良乡校区周边帮你找了几个地点。\n"
            "1. 景阳阁SPA会所(绿地诺亚方舟悦公馆南区店) 地址：绿地诺亚方舟悦公馆南区 "
            "经纬度：116.181457,39.730239\n"
            ":::map{lng=116.181457 lat=39.730239 zoom=15 title=景阳阁SPA会所(绿地诺亚方舟悦公馆南区店)}\n"
            "2. 悦康足道 地址：良乡大学城 经纬度：116.170492,39.728167\n"
            ":::map{lng=116.170492 lat=39.728167 zoom=15 title=悦康足道}"
        ),
    },
]

ORDER_HISTORY = [
    {
        "role": "user",
        "content": "帮我看看良乡校区今天有没有适合加入的篮球或羽毛球约伴活动",
    },
    {
        "role": "assistant",
        "content": (
            "找到 2 个约伴订单：\n\n"
            "- **[订单#42](/orders/42)** BASKETBALL | LIANGXIANG | 良乡体育馆 | 2026-07-03 19:00:00 | 2/4人\n"
            "- **[订单#43](/orders/43)** BADMINTON | LIANGXIANG | 羽毛球馆 | 2026-07-03 20:00:00 | 1/4人"
        ),
    },
]

ORDER_CREATED_HISTORY = [
    {
        "role": "user",
        "content": "帮我创建一个今晚7点良乡体育馆4人的篮球约伴订单，先让我确认",
    },
    {
        "role": "assistant",
        "content": (
            "我已根据上文整理好操作草稿。确认无误后，请点击确认执行或直接回复“确认”。\n\n"
            "确认草稿摘要：\n"
            "- 标题: 确认创建约伴活动\n"
            "- 操作类型: order.create\n"
            "- 活动类型: BASKETBALL（篮球）\n"
            "- 校区: LIANGXIANG（良乡校区）\n"
            "- 地点名称: 良乡体育馆\n"
            "- 时间: 2026-07-03 19:00:00\n"
            "- 参与人数: 4人\n\n"
            "确认无误后，可以点击确认执行，或直接回复“确认”。"
        ),
    },
    {
        "role": "user",
        "content": "确认",
    },
    {
        "role": "assistant",
        "content": "✅ 约伴订单创建成功！[查看订单详情](/orders/88)",
    },
]

CONTENT_HISTORY = [
    {
        "role": "user",
        "content": "搜索一下关于自习的校园动态",
    },
    {
        "role": "assistant",
        "content": (
            "找到 2 条动态：\n\n"
            "- **[动态#77](/contents/77)** by 小白 — 今晚图书馆二楼自习，有同学一起吗\n"
            "- **[动态#78](/contents/78)** by 晚风 — 求一个自习搭子，期末周互相监督"
        ),
    },
]

FOLLOWUP_MESSAGE = "就第一家吧，帮我约三个人，明晚八点，先生成草稿"
SECOND_FOLLOWUP_MESSAGE = "就第二家吧，帮我约三个人，周六晚上8点，先生成草稿"
NAMED_FOLLOWUP_MESSAGE = "还是选悦康足道，帮我创建一个4人的按摩约伴，明晚八点，先生成草稿"
ORDER_APPLY_FOLLOWUP_MESSAGE = "就第二个吧，帮我报名，先生成确认草稿，不要直接提交"
ORDER_APPLY_NAMED_MESSAGE = "羽毛球馆那个约伴我想加入，先让我确认"
ORDER_CONTENT_FOLLOWUP_MESSAGE = "就第二个帮我发条动态宣传一下，先生成草稿发布前让我确认"
ORDER_CREATED_CONTENT_FOLLOWUP_MESSAGE = "顺便基于这个订单发条动态宣传一下，先让我确认"
MAP_CONTENT_FOLLOWUP_MESSAGE = "就第一家帮我写个动态问问有没有同学一起去，先生成草稿别直接发"
CONTENT_COMMENT_FOLLOWUP_MESSAGE = "就第一条帮我评论一下：我也想去，先让我确认"
CONTENT_LIKE_NAMED_MESSAGE = "小白那条动态帮我点个赞，先确认"

MAP_ACTION_MESSAGE = (
    "我想基于刚才查询到的这个地点创建一个约伴订单草稿。\n"
    "请先生成可编辑确认卡片，等我确认后再执行，不要直接发布。\n"
    "地点：悦康足道\n"
    "坐标：116.170492, 39.728167\n"
    "请结合上文的人数、活动类型、时间偏好和校区信息；如果缺少订单必填项，请先让我补充。"
)


@dataclass
class EvalResult:
    scenario_id: str
    ok: bool
    failures: list[str]
    actual: dict[str, Any]


class FakeRouter:
    async def ainvoke(self, _messages):
        content = {
            "title": "确认创建约伴活动",
            "description": "基于用户选择的地图地点整理约伴草稿。",
            "action_kind": "order.create",
            "fields": [{"label": "时间", "value": "明晚八点"}],
            "missing_fields": ["地点", "地点坐标", "参与人数", "活动类型", "校区"],
            "reply": "",
        }
        return type("FakeResult", (), {"content": json.dumps(content, ensure_ascii=False)})()


class FakeGenericManageRouter:
    async def ainvoke(self, _messages):
        content = {
            "title": "请确认这次操作",
            "description": "用户想管理一个约伴订单申请。",
            "fields": [],
            "missing_fields": [],
            "reply": "",
        }
        return type("FakeResult", (), {"content": json.dumps(content, ensure_ascii=False)})()


class FakeTimeRouter:
    def __init__(self, start_time: str):
        self.start_time = start_time

    async def ainvoke(self, _messages):
        content = {
            "start_time": self.start_time,
            "needs_clarification": False,
            "confidence": 0.92,
            "reason": "按当前日期把明天下午解析为次日15点",
        }
        return type("FakeResult", (), {"content": json.dumps(content, ensure_ascii=False)})()


class FakeApplyRouter:
    async def ainvoke(self, _messages):
        content = {
            "title": "确认报名加入约伴活动",
            "description": "用户想基于上一轮查询结果报名加入约伴活动。",
            "action_kind": "order.apply",
            "fields": [{"label": "申请留言", "value": "我会准时到"}],
            "missing_fields": ["订单ID"],
            "reply": "",
        }
        return type("FakeResult", (), {"content": json.dumps(content, ensure_ascii=False)})()


class FakeCommentRouter:
    async def ainvoke(self, _messages):
        content = {
            "title": "确认评论动态",
            "description": "用户想基于上一轮动态搜索结果发表评论。",
            "action_kind": "content.comment",
            "fields": [],
            "missing_fields": ["动态ID", "评论内容"],
            "reply": "",
        }
        return type("FakeResult", (), {"content": json.dumps(content, ensure_ascii=False)})()


class FakeLikeRouter:
    async def ainvoke(self, _messages):
        content = {
            "title": "确认点赞动态",
            "description": "用户想基于上一轮动态搜索结果点赞。",
            "action_kind": "content.like",
            "fields": [],
            "missing_fields": ["动态ID"],
            "reply": "",
        }
        return type("FakeResult", (), {"content": json.dumps(content, ensure_ascii=False)})()


class FakeContentCreateRouter:
    async def ainvoke(self, _messages):
        content = {
            "title": "确认发布动态",
            "description": "用户想基于上一轮约伴订单发布配套动态。",
            "action_kind": "content.create",
            "fields": [],
            "missing_fields": ["订单ID", "动态内容"],
            "reply": "",
        }
        return type("FakeResult", (), {"content": json.dumps(content, ensure_ascii=False)})()


class FakeTool:
    def __init__(self, result: str):
        self.result = result

    async def ainvoke(self, _args):
        return self.result


def _field_map(fields: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in fields:
        result[str(field.get("label") or "")] = str(field.get("value") or "")
    return result


async def scenario_selects_first_map_candidate() -> EvalResult:
    from app import agent as agent_module

    title, coords = agent_module._extract_contextual_map_selection(MAP_HISTORY, FOLLOWUP_MESSAGE)
    actual = {"title": title, "coords": coords}
    failures: list[str] = []
    if title != "景阳阁SPA会所(绿地诺亚方舟悦公馆南区店)":
        failures.append(f"expected first map title, got {title!r}")
    if coords != "116.181457, 39.730239":
        failures.append(f"expected first map coords, got {coords!r}")
    return EvalResult("selects_first_map_candidate", not failures, failures, actual)


async def scenario_selects_second_map_candidate() -> EvalResult:
    from app import agent as agent_module

    title, coords = agent_module._extract_contextual_map_selection(MAP_HISTORY, SECOND_FOLLOWUP_MESSAGE)
    actual = {"title": title, "coords": coords}
    failures: list[str] = []
    if title != "悦康足道":
        failures.append(f"expected second map title, got {title!r}")
    if coords != "116.170492, 39.728167":
        failures.append(f"expected second map coords, got {coords!r}")
    return EvalResult("selects_second_map_candidate", not failures, failures, actual)


async def scenario_selects_named_map_candidate() -> EvalResult:
    from app import agent as agent_module

    title, coords = agent_module._extract_contextual_map_selection(MAP_HISTORY, NAMED_FOLLOWUP_MESSAGE)
    actual = {"title": title, "coords": coords}
    failures: list[str] = []
    if title != "悦康足道":
        failures.append(f"expected named map title, got {title!r}")
    if coords != "116.170492, 39.728167":
        failures.append(f"expected named map coords, got {coords!r}")
    return EvalResult("selects_named_map_candidate", not failures, failures, actual)


async def scenario_selects_second_order_candidate() -> EvalResult:
    from app import agent as agent_module

    candidate = agent_module._extract_contextual_order_selection(ORDER_HISTORY, ORDER_APPLY_FOLLOWUP_MESSAGE)
    actual = {"candidate": candidate}
    failures: list[str] = []
    if not candidate:
        failures.append("expected a selected order candidate")
    elif candidate.get("id") != "43":
        failures.append(f"expected second order id 43, got {candidate.get('id')!r}")
    return EvalResult("selects_second_order_candidate", not failures, failures, actual)


async def scenario_selects_named_order_candidate() -> EvalResult:
    from app import agent as agent_module

    candidate = agent_module._extract_contextual_order_selection(ORDER_HISTORY, ORDER_APPLY_NAMED_MESSAGE)
    actual = {"candidate": candidate}
    failures: list[str] = []
    if not candidate:
        failures.append("expected a named order candidate")
    elif candidate.get("id") != "43":
        failures.append(f"expected named order id 43, got {candidate.get('id')!r}")
    return EvalResult("selects_named_order_candidate", not failures, failures, actual)


async def scenario_selects_first_content_candidate() -> EvalResult:
    from app import agent as agent_module

    candidate = agent_module._extract_contextual_content_selection(CONTENT_HISTORY, CONTENT_COMMENT_FOLLOWUP_MESSAGE)
    actual = {"candidate": candidate}
    failures: list[str] = []
    if not candidate:
        failures.append("expected a selected content candidate")
    elif candidate.get("id") != "77":
        failures.append(f"expected first content id 77, got {candidate.get('id')!r}")
    return EvalResult("selects_first_content_candidate", not failures, failures, actual)


async def scenario_selects_named_content_candidate() -> EvalResult:
    from app import agent as agent_module

    candidate = agent_module._extract_contextual_content_selection(CONTENT_HISTORY, CONTENT_LIKE_NAMED_MESSAGE)
    actual = {"candidate": candidate}
    failures: list[str] = []
    if not candidate:
        failures.append("expected a named content candidate")
    elif candidate.get("id") != "77":
        failures.append(f"expected named content id 77, got {candidate.get('id')!r}")
    return EvalResult("selects_named_content_candidate", not failures, failures, actual)


async def scenario_contextual_intent_routes_to_order_create() -> EvalResult:
    from app import agent as agent_module

    agent_module._intent_cache.clear()
    analysis = await agent_module.analyze_intent(DEFAULT_USER, [], MAP_HISTORY, FOLLOWUP_MESSAGE)
    actual = dict(analysis)
    failures: list[str] = []
    expected = {
        "primary_intent": "order.create",
        "domain": "order",
        "operation_type": "write",
        "requires_confirmation": True,
        "next_action": "prepare_draft",
    }
    for key, value in expected.items():
        if actual.get(key) != value:
            failures.append(f"{key}: expected {value!r}, got {actual.get(key)!r}")
    if not actual.get("contextual_map_shortcut"):
        failures.append("expected contextual_map_shortcut marker")
    return EvalResult("contextual_intent_routes_to_order_create", not failures, failures, actual)


async def scenario_map_action_payload_routes_to_order_create() -> EvalResult:
    from app import agent as agent_module

    agent_module._intent_cache.clear()
    title, coords = agent_module._extract_contextual_map_selection(MAP_HISTORY, MAP_ACTION_MESSAGE)
    analysis = await agent_module.analyze_intent(DEFAULT_USER, [], MAP_HISTORY, MAP_ACTION_MESSAGE)
    actual = {"title": title, "coords": coords, "analysis": dict(analysis)}
    failures: list[str] = []
    if title != "悦康足道":
        failures.append(f"expected explicit map action title, got {title!r}")
    if coords != "116.170492, 39.728167":
        failures.append(f"expected explicit map action coords, got {coords!r}")
    expected = {
        "primary_intent": "order.create",
        "domain": "order",
        "operation_type": "write",
        "requires_confirmation": True,
    }
    for key, value in expected.items():
        if analysis.get(key) != value:
            failures.append(f"{key}: expected {value!r}, got {analysis.get(key)!r}")
    if not analysis.get("contextual_map_shortcut"):
        failures.append("expected contextual_map_shortcut marker")
    return EvalResult("map_action_payload_routes_to_order_create", not failures, failures, actual)


async def scenario_contextual_content_comment_routes_to_confirmed_write() -> EvalResult:
    from app import agent as agent_module

    agent_module._intent_cache.clear()
    analysis = await agent_module.analyze_intent(DEFAULT_USER, [], CONTENT_HISTORY, CONTENT_COMMENT_FOLLOWUP_MESSAGE)
    actual = dict(analysis)
    failures: list[str] = []
    expected = {
        "primary_intent": "content.interact",
        "domain": "content",
        "operation_type": "write",
        "requires_confirmation": True,
        "next_action": "prepare_draft",
    }
    for key, value in expected.items():
        if actual.get(key) != value:
            failures.append(f"{key}: expected {value!r}, got {actual.get(key)!r}")
    if not actual.get("contextual_content_shortcut"):
        failures.append("expected contextual_content_shortcut marker")
    return EvalResult("contextual_content_comment_routes_to_confirmed_write", not failures, failures, actual)


async def scenario_contextual_order_apply_routes_to_confirmed_write() -> EvalResult:
    from app import agent as agent_module

    agent_module._intent_cache.clear()
    analysis = await agent_module.analyze_intent(DEFAULT_USER, [], ORDER_HISTORY, ORDER_APPLY_FOLLOWUP_MESSAGE)
    actual = dict(analysis)
    failures: list[str] = []
    expected = {
        "primary_intent": "order.manage",
        "domain": "order",
        "operation_type": "write",
        "requires_confirmation": True,
        "next_action": "prepare_draft",
    }
    for key, value in expected.items():
        if actual.get(key) != value:
            failures.append(f"{key}: expected {value!r}, got {actual.get(key)!r}")
    return EvalResult("contextual_order_apply_routes_to_confirmed_write", not failures, failures, actual)


async def scenario_contextual_order_content_routes_to_confirmed_write() -> EvalResult:
    from app import agent as agent_module

    agent_module._intent_cache.clear()
    analysis = await agent_module.analyze_intent(DEFAULT_USER, [], ORDER_HISTORY, ORDER_CONTENT_FOLLOWUP_MESSAGE)
    actual = dict(analysis)
    failures: list[str] = []
    expected = {
        "primary_intent": "content.create",
        "domain": "content",
        "operation_type": "write",
        "requires_confirmation": True,
        "next_action": "prepare_draft",
    }
    for key, value in expected.items():
        if actual.get(key) != value:
            failures.append(f"{key}: expected {value!r}, got {actual.get(key)!r}")
    if not actual.get("contextual_order_content_shortcut"):
        failures.append("expected contextual_order_content_shortcut marker")
    return EvalResult("contextual_order_content_routes_to_confirmed_write", not failures, failures, actual)


async def scenario_contextual_map_content_routes_to_confirmed_write() -> EvalResult:
    from app import agent as agent_module

    agent_module._intent_cache.clear()
    analysis = await agent_module.analyze_intent(DEFAULT_USER, [], MAP_HISTORY, MAP_CONTENT_FOLLOWUP_MESSAGE)
    actual = dict(analysis)
    failures: list[str] = []
    expected = {
        "primary_intent": "content.create",
        "domain": "content",
        "operation_type": "write",
        "requires_confirmation": True,
        "next_action": "prepare_draft",
    }
    for key, value in expected.items():
        if actual.get(key) != value:
            failures.append(f"{key}: expected {value!r}, got {actual.get(key)!r}")
    if not actual.get("contextual_map_content_shortcut"):
        failures.append("expected contextual_map_content_shortcut marker")
    if actual.get("contextual_map_shortcut"):
        failures.append("map-to-content draft should not be claimed by order-create shortcut")
    return EvalResult("contextual_map_content_routes_to_confirmed_write", not failures, failures, actual)


async def scenario_confirmation_enriches_map_fields() -> EvalResult:
    from app import agent as agent_module

    original_router = agent_module._get_router_llm
    agent_module._get_router_llm = lambda: FakeRouter()
    try:
        analysis = {
            "primary_intent": "order.create",
            "domain": "order",
            "operation_type": "write",
            "requires_confirmation": True,
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
        }
        artifact = await agent_module.build_confirmation_artifact(
            DEFAULT_USER,
            MAP_HISTORY,
            FOLLOWUP_MESSAGE,
            analysis,
        )
    finally:
        agent_module._get_router_llm = original_router

    fields = _field_map(artifact.get("fields") or [])
    actual = {
        "fields": fields,
        "missingFields": artifact.get("missingFields") or [],
        "reply": artifact.get("reply"),
    }
    failures: list[str] = []
    expected_fields = {
        "地点名称": "景阳阁SPA会所(绿地诺亚方舟悦公馆南区店)",
        "地点坐标": "116.181457, 39.730239",
        "参与人数": "3人",
        "活动类型": "OTHER（足疗按摩）",
        "校区": "LIANGXIANG（良乡校区）",
    }
    for label, expected in expected_fields.items():
        if fields.get(label) != expected:
            failures.append(f"{label}: expected {expected!r}, got {fields.get(label)!r}")
    if artifact.get("missingFields"):
        failures.append(f"expected no missing fields after enrichment, got {artifact.get('missingFields')!r}")
    return EvalResult("confirmation_enriches_map_fields", not failures, failures, actual)


async def scenario_named_confirmation_enriches_map_fields() -> EvalResult:
    from app import agent as agent_module

    original_router = agent_module._get_router_llm
    agent_module._get_router_llm = lambda: FakeRouter()
    try:
        analysis = {
            "primary_intent": "order.create",
            "domain": "order",
            "operation_type": "write",
            "requires_confirmation": True,
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
        }
        artifact = await agent_module.build_confirmation_artifact(
            DEFAULT_USER,
            MAP_HISTORY,
            NAMED_FOLLOWUP_MESSAGE,
            analysis,
        )
    finally:
        agent_module._get_router_llm = original_router

    fields = _field_map(artifact.get("fields") or [])
    actual = {
        "fields": fields,
        "missingFields": artifact.get("missingFields") or [],
        "reply": artifact.get("reply"),
    }
    failures: list[str] = []
    expected_fields = {
        "地点名称": "悦康足道",
        "地点坐标": "116.170492, 39.728167",
        "参与人数": "4人",
        "活动类型": "OTHER（足疗按摩）",
        "校区": "LIANGXIANG（良乡校区）",
    }
    for label, expected in expected_fields.items():
        if fields.get(label) != expected:
            failures.append(f"{label}: expected {expected!r}, got {fields.get(label)!r}")
    if artifact.get("missingFields"):
        failures.append(f"expected no missing fields after named enrichment, got {artifact.get('missingFields')!r}")
    return EvalResult("named_confirmation_enriches_map_fields", not failures, failures, actual)


async def scenario_confirmation_enriches_order_apply_fields() -> EvalResult:
    from app import agent as agent_module

    original_router = agent_module._get_router_llm
    agent_module._get_router_llm = lambda: FakeApplyRouter()
    try:
        analysis = {
            "primary_intent": "order.manage",
            "domain": "order",
            "operation_type": "write",
            "requires_confirmation": True,
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
        }
        artifact = await agent_module.build_confirmation_artifact(
            DEFAULT_USER,
            ORDER_HISTORY,
            ORDER_APPLY_FOLLOWUP_MESSAGE,
            analysis,
        )
    finally:
        agent_module._get_router_llm = original_router

    fields = _field_map(artifact.get("fields") or [])
    actual = {
        "actionKind": artifact.get("actionKind"),
        "fields": fields,
        "missingFields": artifact.get("missingFields") or [],
        "reply": artifact.get("reply"),
    }
    failures: list[str] = []
    if artifact.get("actionKind") != "order.apply":
        failures.append(f"expected order.apply actionKind, got {artifact.get('actionKind')!r}")
    if fields.get("订单ID") != "43":
        failures.append(f"expected selected order id 43, got {fields.get('订单ID')!r}")
    if "羽毛球馆" not in fields.get("订单信息", ""):
        failures.append(f"expected selected order summary with 羽毛球馆, got {fields.get('订单信息')!r}")
    if artifact.get("missingFields"):
        failures.append(f"expected no missing fields after order selection enrichment, got {artifact.get('missingFields')!r}")
    return EvalResult("confirmation_enriches_order_apply_fields", not failures, failures, actual)


async def scenario_confirmation_enriches_order_content_fields() -> EvalResult:
    from app import agent as agent_module

    original_router = agent_module._get_router_llm
    agent_module._get_router_llm = lambda: FakeContentCreateRouter()
    try:
        analysis = {
            "primary_intent": "content.create",
            "domain": "content",
            "operation_type": "write",
            "requires_confirmation": True,
            "missing_slots": [],
            "suggested_agents": ["content_draft"],
            "next_action": "prepare_draft",
        }
        artifact = await agent_module.build_confirmation_artifact(
            DEFAULT_USER,
            ORDER_HISTORY,
            ORDER_CONTENT_FOLLOWUP_MESSAGE,
            analysis,
        )
    finally:
        agent_module._get_router_llm = original_router

    fields = _field_map(artifact.get("fields") or [])
    actual = {
        "actionKind": artifact.get("actionKind"),
        "fields": fields,
        "missingFields": artifact.get("missingFields") or [],
        "reply": artifact.get("reply"),
    }
    failures: list[str] = []
    if artifact.get("actionKind") != "content.create":
        failures.append(f"expected content.create actionKind, got {artifact.get('actionKind')!r}")
    if fields.get("订单ID") != "43":
        failures.append(f"expected selected order id 43, got {fields.get('订单ID')!r}")
    if "羽毛球馆" not in fields.get("订单信息", ""):
        failures.append(f"expected selected order summary with 羽毛球馆, got {fields.get('订单信息')!r}")
    draft_text = fields.get("动态内容", "")
    if "羽毛球" not in draft_text or "羽毛球馆" not in draft_text or "订单#43" not in draft_text:
        failures.append(f"expected draft text to preserve selected order context, got {draft_text!r}")
    if artifact.get("missingFields"):
        failures.append(f"expected no missing fields after order content enrichment, got {artifact.get('missingFields')!r}")
    return EvalResult("confirmation_enriches_order_content_fields", not failures, failures, actual)


async def scenario_confirmation_enriches_map_content_fields() -> EvalResult:
    from app import agent as agent_module

    original_router = agent_module._get_router_llm
    agent_module._get_router_llm = lambda: FakeContentCreateRouter()
    try:
        analysis = {
            "primary_intent": "content.create",
            "domain": "content",
            "operation_type": "write",
            "requires_confirmation": True,
            "missing_slots": [],
            "suggested_agents": ["content_draft"],
            "next_action": "prepare_draft",
            "contextual_map_content_shortcut": True,
        }
        artifact = await agent_module.build_confirmation_artifact(
            DEFAULT_USER,
            MAP_HISTORY,
            MAP_CONTENT_FOLLOWUP_MESSAGE,
            analysis,
        )
    finally:
        agent_module._get_router_llm = original_router

    fields = _field_map(artifact.get("fields") or [])
    actual = {
        "actionKind": artifact.get("actionKind"),
        "fields": fields,
        "missingFields": artifact.get("missingFields") or [],
        "reply": artifact.get("reply"),
    }
    failures: list[str] = []
    if artifact.get("actionKind") != "content.create":
        failures.append(f"expected content.create actionKind, got {artifact.get('actionKind')!r}")
    if "景阳阁SPA会所" not in fields.get("地点名称", ""):
        failures.append(f"expected first map place in fields, got {fields.get('地点名称')!r}")
    if fields.get("地点坐标") != "116.181457, 39.730239":
        failures.append(f"expected first map coords, got {fields.get('地点坐标')!r}")
    draft_text = fields.get("动态内容", "")
    if "景阳阁SPA会所" not in draft_text or "有兴趣的同学" not in draft_text:
        failures.append(f"expected map-place dynamic draft text, got {draft_text!r}")
    if "订单ID" in fields:
        failures.append("map-place content draft should not force an order id field")
    if artifact.get("missingFields"):
        failures.append(f"expected no missing fields after map content enrichment, got {artifact.get('missingFields')!r}")
    return EvalResult("confirmation_enriches_map_content_fields", not failures, failures, actual)


async def scenario_confirmation_enriches_created_order_content_fields() -> EvalResult:
    from app import agent as agent_module

    original_router = agent_module._get_router_llm
    agent_module._get_router_llm = lambda: FakeContentCreateRouter()
    try:
        analysis = {
            "primary_intent": "content.create",
            "domain": "content",
            "operation_type": "write",
            "requires_confirmation": True,
            "missing_slots": [],
            "suggested_agents": ["content_draft"],
            "next_action": "prepare_draft",
            "contextual_order_content_shortcut": True,
        }
        artifact = await agent_module.build_confirmation_artifact(
            DEFAULT_USER,
            ORDER_CREATED_HISTORY,
            ORDER_CREATED_CONTENT_FOLLOWUP_MESSAGE,
            analysis,
        )
    finally:
        agent_module._get_router_llm = original_router

    fields = _field_map(artifact.get("fields") or [])
    actual = {
        "actionKind": artifact.get("actionKind"),
        "fields": fields,
        "missingFields": artifact.get("missingFields") or [],
        "reply": artifact.get("reply"),
    }
    failures: list[str] = []
    if artifact.get("actionKind") != "content.create":
        failures.append(f"expected content.create actionKind, got {artifact.get('actionKind')!r}")
    if fields.get("订单ID") != "88":
        failures.append(f"expected created order id 88, got {fields.get('订单ID')!r}")
    if "良乡体育馆" not in fields.get("订单信息", ""):
        failures.append(f"expected created order summary with 良乡体育馆, got {fields.get('订单信息')!r}")
    draft_text = fields.get("动态内容", "")
    if "篮球" not in draft_text or "良乡体育馆" not in draft_text or "订单#88" not in draft_text:
        failures.append(f"expected draft text to preserve created order context, got {draft_text!r}")
    if artifact.get("missingFields"):
        failures.append(f"expected no missing fields after created order enrichment, got {artifact.get('missingFields')!r}")
    return EvalResult("confirmation_enriches_created_order_content_fields", not failures, failures, actual)


async def scenario_confirmation_enriches_content_comment_fields() -> EvalResult:
    from app import agent as agent_module

    original_router = agent_module._get_router_llm
    agent_module._get_router_llm = lambda: FakeCommentRouter()
    try:
        analysis = {
            "primary_intent": "content.interact",
            "domain": "content",
            "operation_type": "write",
            "requires_confirmation": True,
            "missing_slots": [],
            "suggested_agents": ["content_draft"],
            "next_action": "prepare_draft",
        }
        artifact = await agent_module.build_confirmation_artifact(
            DEFAULT_USER,
            CONTENT_HISTORY,
            CONTENT_COMMENT_FOLLOWUP_MESSAGE,
            analysis,
        )
    finally:
        agent_module._get_router_llm = original_router

    fields = _field_map(artifact.get("fields") or [])
    actual = {
        "actionKind": artifact.get("actionKind"),
        "fields": fields,
        "missingFields": artifact.get("missingFields") or [],
        "reply": artifact.get("reply"),
    }
    failures: list[str] = []
    if artifact.get("actionKind") != "content.comment":
        failures.append(f"expected content.comment actionKind, got {artifact.get('actionKind')!r}")
    if fields.get("动态ID") != "77":
        failures.append(f"expected selected content id 77, got {fields.get('动态ID')!r}")
    if "小白" not in fields.get("动态信息", ""):
        failures.append(f"expected selected content summary with 小白, got {fields.get('动态信息')!r}")
    if "我也想去" not in fields.get("评论内容", ""):
        failures.append(f"expected inline comment text, got {fields.get('评论内容')!r}")
    if artifact.get("missingFields"):
        failures.append(f"expected no missing fields after content comment enrichment, got {artifact.get('missingFields')!r}")
    return EvalResult("confirmation_enriches_content_comment_fields", not failures, failures, actual)


async def scenario_confirmation_enriches_content_like_fields() -> EvalResult:
    from app import agent as agent_module

    original_router = agent_module._get_router_llm
    agent_module._get_router_llm = lambda: FakeLikeRouter()
    try:
        analysis = {
            "primary_intent": "content.interact",
            "domain": "content",
            "operation_type": "write",
            "requires_confirmation": True,
            "missing_slots": [],
            "suggested_agents": ["content_draft"],
            "next_action": "prepare_draft",
        }
        artifact = await agent_module.build_confirmation_artifact(
            DEFAULT_USER,
            CONTENT_HISTORY,
            CONTENT_LIKE_NAMED_MESSAGE,
            analysis,
        )
    finally:
        agent_module._get_router_llm = original_router

    fields = _field_map(artifact.get("fields") or [])
    actual = {
        "actionKind": artifact.get("actionKind"),
        "fields": fields,
        "missingFields": artifact.get("missingFields") or [],
        "reply": artifact.get("reply"),
    }
    failures: list[str] = []
    if artifact.get("actionKind") != "content.like":
        failures.append(f"expected content.like actionKind, got {artifact.get('actionKind')!r}")
    if fields.get("动态ID") != "77":
        failures.append(f"expected selected content id 77, got {fields.get('动态ID')!r}")
    if "小白" not in fields.get("动态信息", ""):
        failures.append(f"expected selected content summary with 小白, got {fields.get('动态信息')!r}")
    if artifact.get("missingFields"):
        failures.append(f"expected no missing fields after content like enrichment, got {artifact.get('missingFields')!r}")
    return EvalResult("confirmation_enriches_content_like_fields", not failures, failures, actual)


async def scenario_high_confidence_gated_write_skips_review() -> EvalResult:
    from app import agent as agent_module

    analysis = {
        "primary_intent": "order.create",
        "domain": "order",
        "operation_type": "write",
        "requires_confirmation": True,
        "confidence": 0.9,
        "next_action": "prepare_draft",
    }
    should_review = agent_module._should_review_intent(analysis, "就第一家吧，帮我约三个人")
    actual = {"should_review": should_review, "analysis": analysis}
    failures: list[str] = []
    if should_review:
        failures.append("high-confidence write already gated by confirmation should not need a second router review")
    return EvalResult("high_confidence_gated_write_skips_review", not failures, failures, actual)


async def scenario_confirmed_action_kind_marker_wins() -> EvalResult:
    from app import agent as agent_module

    samples = [
        (
            "我确认执行这个草稿：请确认这次操作\n操作类型: order.cancel_apply\n订单ID: 12",
            "order.cancel_apply",
        ),
        (
            "我确认按修改后的内容执行这个草稿：请确认这次操作\n操作类型: order.reject_apply\n申请ID: 7",
            "order.reject_apply",
        ),
        (
            "我确认执行这个草稿：请确认这次操作\n操作类型: content.comment\n动态ID: 23\n评论内容: 我也想去",
            "content.comment",
        ),
    ]
    actual: dict[str, str] = {}
    failures: list[str] = []
    for index, (message, expected) in enumerate(samples, start=1):
        fields = agent_module._parse_confirmed_artifact_fields(message)
        inferred = agent_module._infer_confirmed_action_kind(message, fields)
        actual[f"sample_{index}"] = inferred
        if inferred != expected:
            failures.append(f"sample {index}: expected {expected!r}, got {inferred!r}")
    return EvalResult("confirmed_action_kind_marker_wins", not failures, failures, actual)


async def scenario_confirmation_infers_manage_action_kind() -> EvalResult:
    from app import agent as agent_module

    original_router = agent_module._get_router_llm
    agent_module._get_router_llm = lambda: FakeGenericManageRouter()
    try:
        analysis = {
            "primary_intent": "order.manage",
            "domain": "order",
            "operation_type": "write",
            "requires_confirmation": True,
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
        }
        artifact = await agent_module.build_confirmation_artifact(
            DEFAULT_USER,
            [],
            "我刚才报了订单 12，但现在去不了了，帮我取消报名，确认后再执行",
            analysis,
        )
    finally:
        agent_module._get_router_llm = original_router

    fields = _field_map(artifact.get("fields") or [])
    actual = {
        "actionKind": artifact.get("actionKind"),
        "confirmMessage": artifact.get("confirmMessage"),
        "fields": fields,
    }
    failures: list[str] = []
    if artifact.get("actionKind") != "order.cancel_apply":
        failures.append(f"expected order.cancel_apply actionKind, got {artifact.get('actionKind')!r}")
    if "操作类型: order.cancel_apply" not in str(artifact.get("confirmMessage") or ""):
        failures.append("confirmMessage should include the resolved action kind marker")
    if fields.get("订单ID") != "12":
        failures.append(f"expected enriched order id 12, got {fields.get('订单ID')!r}")
    return EvalResult("confirmation_infers_manage_action_kind", not failures, failures, actual)


async def scenario_confirmed_execution_returns_result_artifact() -> EvalResult:
    from app import agent as agent_module

    original_create_order = agent_module.create_order
    agent_module.create_order = FakeTool("✅ 约伴订单创建成功！[查看订单详情](/orders/88)")
    try:
        result = await agent_module.build_confirmed_execution_response(
            DEFAULT_USER,
            [],
            (
                "我确认执行这个草稿：确认创建约伴活动\n"
                "操作类型: order.create\n"
                "活动类型: BASKETBALL\n"
                "校区: LIANGXIANG\n"
                "地点: 良乡体育馆\n"
                "时间: 2026-07-03 19:00:00\n"
                "参与人数: 4"
            ),
        )
    finally:
        agent_module.create_order = original_create_order

    artifact = (result.get("artifacts") or [{}])[0] if result else {}
    actions = artifact.get("actions") or []
    tool_calls = result.get("tool_calls") if result else []
    actual = {
        "reply": result.get("reply") if result else None,
        "tool_calls": tool_calls,
        "artifact": artifact,
    }
    failures: list[str] = []
    if not result:
        failures.append("expected confirmed execution response")
    if artifact.get("type") != "order":
        failures.append(f"expected order artifact, got {artifact.get('type')!r}")
    if artifact.get("title") != "约伴订单已创建":
        failures.append(f"expected creation result title, got {artifact.get('title')!r}")
    if not any(action.get("route") == "/orders/88" for action in actions if isinstance(action, dict)):
        failures.append("expected a /orders/88 detail action")
    if not any((call or {}).get("name") == "create_order" for call in (tool_calls or [])):
        failures.append("expected create_order tool call")
    return EvalResult("confirmed_execution_returns_result_artifact", not failures, failures, actual)


async def scenario_short_confirmation_executes_recent_draft_summary() -> EvalResult:
    from app import agent as agent_module

    original_router = agent_module._get_router_llm
    original_create_order = agent_module.create_order
    agent_module._get_router_llm = lambda: FakeRouter()
    try:
        analysis = {
            "primary_intent": "order.create",
            "domain": "order",
            "operation_type": "write",
            "requires_confirmation": True,
            "missing_slots": [],
            "suggested_agents": ["order_draft"],
            "next_action": "prepare_draft",
        }
        draft = await agent_module.build_confirmation_artifact(
            DEFAULT_USER,
            MAP_HISTORY,
            FOLLOWUP_MESSAGE,
            analysis,
        )
        agent_module.create_order = FakeTool("✅ 约伴订单创建成功！[查看订单详情](/orders/90)")
        result = await agent_module.build_confirmed_execution_response(
            DEFAULT_USER,
            [{"role": "assistant", "content": draft.get("reply") or ""}],
            "确认",
        )
    finally:
        agent_module._get_router_llm = original_router
        agent_module.create_order = original_create_order

    tool_calls = result.get("tool_calls") if result else []
    args = (tool_calls or [{}])[0].get("args") or {}
    artifact = (result.get("artifacts") or [{}])[0] if result else {}
    actual = {
        "draft_reply": draft.get("reply"),
        "tool_calls": tool_calls,
        "args": args,
        "artifact": artifact,
    }
    failures: list[str] = []
    if "确认草稿摘要" not in str(draft.get("reply") or ""):
        failures.append("confirmation reply should persist a readable draft summary")
    if not result:
        failures.append("short confirmation should execute the recent draft summary")
    if not any((call or {}).get("name") == "create_order" for call in (tool_calls or [])):
        failures.append("expected create_order tool call after short confirmation")
    if "景阳阁SPA会所" not in str(args.get("location") or ""):
        failures.append(f"expected first map location in create args, got {args.get('location')!r}")
    if args.get("max_people") != 3:
        failures.append(f"expected max_people 3, got {args.get('max_people')!r}")
    if not args.get("start_time"):
        failures.append("expected 明晚八点 to normalize into a start_time")
    if not any(action.get("route") == "/orders/90" for action in artifact.get("actions") or [] if isinstance(action, dict)):
        failures.append("expected confirmed result card to link to created order")
    return EvalResult("short_confirmation_executes_recent_draft_summary", not failures, failures, actual)


async def scenario_confirmed_order_resolves_broad_relative_time() -> EvalResult:
    from app import agent as agent_module

    expected_dt = (agent_module._local_now() + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
    expected_start_time = expected_dt.strftime("%Y-%m-%d %H:%M:%S")
    captured_events: list[dict[str, Any]] = []

    async def capture(event: dict):
        captured_events.append(event)

    original_router = agent_module._get_router_llm
    original_create_order = agent_module.create_order
    agent_module._get_router_llm = lambda: FakeTimeRouter(expected_start_time)
    agent_module.create_order = FakeTool("✅ 约伴订单创建成功！[查看订单详情](/orders/91)")
    token = agent_module._event_sink.set(capture)
    try:
        result = await agent_module.build_confirmed_execution_response(
            DEFAULT_USER,
            [],
            (
                "我确认按修改后的内容执行这个草稿：确认创建约伴活动\n"
                "操作类型: order.create\n"
                "活动类型: 桌游\n"
                "地点: 泡芙桌游主机体验馆\n"
                "地点坐标: 116.173790, 39.725208\n"
                "校区: 北京理工大学良乡校区\n"
                "参与人数: 3人\n"
                "时间: 明天下午"
            ),
        )
    finally:
        agent_module._event_sink.reset(token)
        agent_module._get_router_llm = original_router
        agent_module.create_order = original_create_order

    tool_calls = result.get("tool_calls") if result else []
    args = (tool_calls or [{}])[0].get("args") or {}
    actual = {
        "reply": result.get("reply") if result else None,
        "tool_calls": tool_calls,
        "args": args,
        "event_names": [item.get("event") for item in captured_events],
    }
    failures: list[str] = []
    if not result:
        failures.append("expected broad relative time confirmation to execute")
    if args.get("start_time") != expected_start_time:
        failures.append(f"expected start_time {expected_start_time}, got {args.get('start_time')!r}")
    if not any((call or {}).get("name") == "create_order" for call in (tool_calls or [])):
        failures.append("expected create_order tool call")
    if "agent_step" not in actual["event_names"]:
        failures.append("expected time normalization progress to stream as agent_step")
    return EvalResult("confirmed_order_resolves_broad_relative_time", not failures, failures, actual)


async def scenario_confirmed_memory_commit_returns_artifact() -> EvalResult:
    from app import agent as agent_module

    captured_events: list[dict[str, Any]] = []

    async def capture(event: dict):
        captured_events.append(event)

    token = agent_module._event_sink.set(capture)
    try:
        result = await agent_module.build_confirmed_execution_response(
            DEFAULT_USER,
            [],
            (
                "我确认执行这个草稿：确认保存长期记忆\n"
                "操作类型: memory.manage\n"
                "记忆操作: save\n"
                "记忆分类: preference\n"
                "记忆内容: 用户以后推荐吃饭地点时优先良乡校区、预算不要太贵"
            ),
        )
    finally:
        agent_module._event_sink.reset(token)

    artifact = (result.get("artifacts") or [{}])[0] if result else {}
    actions = artifact.get("actions") or []
    commits = result.get("memory_commits") if result else []
    tool_calls = result.get("tool_calls") if result else []
    actual = {
        "reply": result.get("reply") if result else None,
        "tool_calls": tool_calls,
        "artifact": artifact,
        "memory_commits": commits,
        "event_names": [item.get("event") for item in captured_events],
    }
    failures: list[str] = []
    if not result:
        failures.append("expected confirmed memory response")
    if artifact.get("type") != "memory":
        failures.append(f"expected memory artifact, got {artifact.get('type')!r}")
    if not commits or commits[0].get("operation") != "save":
        failures.append(f"expected save memory commit, got {commits!r}")
    if not commits or "良乡校区" not in commits[0].get("content", ""):
        failures.append("expected committed memory content to preserve the preference")
    if not any((call or {}).get("name") == "commit_memory" for call in (tool_calls or [])):
        failures.append("expected commit_memory pseudo tool call")
    if "memory_commit" not in actual["event_names"]:
        failures.append("expected memory_commit stream event")
    if not any(action.get("memoryPanel") for action in actions if isinstance(action, dict)):
        failures.append("expected memory panel action")
    return EvalResult("confirmed_memory_commit_returns_artifact", not failures, failures, actual)


async def run_all() -> list[EvalResult]:
    scenarios = [
        scenario_selects_first_map_candidate,
        scenario_selects_second_map_candidate,
        scenario_selects_named_map_candidate,
        scenario_selects_second_order_candidate,
        scenario_selects_named_order_candidate,
        scenario_selects_first_content_candidate,
        scenario_selects_named_content_candidate,
        scenario_contextual_intent_routes_to_order_create,
        scenario_map_action_payload_routes_to_order_create,
        scenario_contextual_content_comment_routes_to_confirmed_write,
        scenario_contextual_order_apply_routes_to_confirmed_write,
        scenario_contextual_order_content_routes_to_confirmed_write,
        scenario_contextual_map_content_routes_to_confirmed_write,
        scenario_confirmation_enriches_map_fields,
        scenario_named_confirmation_enriches_map_fields,
        scenario_confirmation_enriches_order_apply_fields,
        scenario_confirmation_enriches_order_content_fields,
        scenario_confirmation_enriches_map_content_fields,
        scenario_confirmation_enriches_created_order_content_fields,
        scenario_confirmation_enriches_content_comment_fields,
        scenario_confirmation_enriches_content_like_fields,
        scenario_high_confidence_gated_write_skips_review,
        scenario_confirmed_action_kind_marker_wins,
        scenario_confirmation_infers_manage_action_kind,
        scenario_confirmed_execution_returns_result_artifact,
        scenario_short_confirmation_executes_recent_draft_summary,
        scenario_confirmed_order_resolves_broad_relative_time,
        scenario_confirmed_memory_commit_returns_artifact,
    ]
    return [await scenario() for scenario in scenarios]


def print_text_report(results: list[EvalResult]) -> None:
    passed = sum(1 for item in results if item.ok)
    print(f"CampusHub contextual order eval: {passed}/{len(results)} passed")
    print("-" * 72)
    for result in results:
        mark = "PASS" if result.ok else "FAIL"
        print(f"{mark:4} {result.scenario_id}")
        for failure in result.failures:
            print(f"     - {failure}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    results = await run_all()
    if args.json_output:
        print(json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2))
    else:
        print_text_report(results)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
