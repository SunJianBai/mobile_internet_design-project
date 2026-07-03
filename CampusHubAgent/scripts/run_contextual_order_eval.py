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

FOLLOWUP_MESSAGE = "就第一家吧，帮我约三个人，明晚八点，先生成草稿"

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


async def run_all() -> list[EvalResult]:
    scenarios = [
        scenario_selects_first_map_candidate,
        scenario_contextual_intent_routes_to_order_create,
        scenario_map_action_payload_routes_to_order_create,
        scenario_confirmation_enriches_map_fields,
        scenario_high_confidence_gated_write_skips_review,
        scenario_confirmed_action_kind_marker_wins,
        scenario_confirmation_infers_manage_action_kind,
        scenario_confirmed_execution_returns_result_artifact,
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
