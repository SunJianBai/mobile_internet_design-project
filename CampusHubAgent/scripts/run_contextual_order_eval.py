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


async def run_all() -> list[EvalResult]:
    scenarios = [
        scenario_selects_first_map_candidate,
        scenario_contextual_intent_routes_to_order_create,
        scenario_confirmation_enriches_map_fields,
        scenario_high_confidence_gated_write_skips_review,
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
