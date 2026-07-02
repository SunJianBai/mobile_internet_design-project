"""Run regression checks for CampusHub intent fallback routing.

The checks monkeypatch the semantic router to fail, so they do not call an LLM,
the Java backend, or external map/weather APIs. They verify that clear read-only
requests still route to a useful local fallback instead of becoming unknown.

Usage:
  python scripts/run_router_fallback_eval.py
  python scripts/run_router_fallback_eval.py --json
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


@dataclass
class FallbackResult:
    scenario_id: str
    ok: bool
    failures: list[str]
    actual: dict[str, Any]


class FailingRouter:
    async def ainvoke(self, *_args, **_kwargs):
        raise RuntimeError("simulated router outage")


def check_expected(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for key, value in expected.items():
        if actual.get(key) != value:
            failures.append(f"{key}: expected {value!r}, got {actual.get(key)!r}")
    return failures


async def run_case(agent_module, scenario: dict[str, Any]) -> FallbackResult:
    agent_module._intent_cache.clear()
    actual = await agent_module.analyze_intent(
        user_info={"uid": 4, "nickname": "Codex QA", "campus": "LIANGXIANG"},
        memories=[],
        history=[],
        user_message=scenario["message"],
    )
    actual = dict(actual)
    failures = check_expected(actual, scenario["expect"])
    return FallbackResult(
        scenario_id=scenario["id"],
        ok=not failures,
        failures=failures,
        actual=actual,
    )


async def run_all() -> list[FallbackResult]:
    from app import agent as agent_module

    original_router = agent_module._get_router_llm
    original_read_shortcut = agent_module._detect_read_intent_shortcut
    agent_module._get_router_llm = lambda: FailingRouter()
    agent_module._detect_read_intent_shortcut = lambda _message: None
    try:
        scenarios = [
            {
                "id": "fallback_companion_search_not_store",
                "message": "附近有没有人一起去看电影，别给我店铺推荐，我想找搭子",
                "expect": {
                    "primary_intent": "order.search",
                    "domain": "order",
                    "operation_type": "read",
                    "requires_confirmation": False,
                    "next_action": "execute_read_tools",
                    "router_error": "RuntimeError",
                },
            },
            {
                "id": "fallback_store_recommendation_stays_map",
                "message": "我想找适合三个人一起去的按摩店，有什么推荐",
                "expect": {
                    "primary_intent": "map.search",
                    "domain": "map",
                    "operation_type": "read",
                    "requires_confirmation": False,
                    "next_action": "execute_read_tools",
                    "router_error": "RuntimeError",
                },
            },
        ]
        return [await run_case(agent_module, scenario) for scenario in scenarios]
    finally:
        agent_module._detect_read_intent_shortcut = original_read_shortcut
        agent_module._get_router_llm = original_router
        agent_module._intent_cache.clear()


def print_text_report(results: list[FallbackResult]) -> None:
    passed = sum(item.ok for item in results)
    print(f"CampusHub router fallback eval: {passed}/{len(results)} passed")
    print("-" * 72)
    for result in results:
        mark = "PASS" if result.ok else "FAIL"
        intent = result.actual.get("primary_intent")
        domain = result.actual.get("domain")
        operation = result.actual.get("operation_type")
        confirm = result.actual.get("requires_confirmation")
        print(f"{mark:4} {result.scenario_id:38} {domain}/{intent}/{operation}/confirm={confirm}")
        for failure in result.failures:
            print(f"     - {failure}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    results = await run_all()
    if args.json_output:
        print(json.dumps([item.__dict__ for item in results], ensure_ascii=False, indent=2))
    else:
        print_text_report(results)
    return 0 if all(item.ok for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
