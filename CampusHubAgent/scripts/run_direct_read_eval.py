"""Run deterministic checks for direct read responses.

These checks patch tool invocation, so they do not call AMap, the LLM, or the
Java backend. They verify that fast read paths return rich UI artifacts instead
of only plain text.

Examples:
  python scripts/run_direct_read_eval.py
  python scripts/run_direct_read_eval.py --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class DirectReadResult:
    scenario_id: str
    ok: bool
    failures: list[str]
    actual: dict[str, Any]


class DirectReadHarness:
    def __init__(self) -> None:
        from app import agent as agent_module

        self.agent = agent_module
        self.events: list[dict[str, Any]] = []
        self.tool_calls: list[dict[str, Any]] = []
        self._original_invoke_tool_text = agent_module._invoke_tool_text

    async def __aenter__(self) -> "DirectReadHarness":
        async def fake_invoke_tool_text(tool_obj, args: dict) -> str:
            self.tool_calls.append({"args": args})
            if "city" in args:
                return json.dumps({
                    "city": "北京",
                    "forecasts": [{
                        "dayweather": "晴",
                        "nightweather": "多云",
                        "daytemp": "31",
                        "nighttemp": "22",
                    }],
                }, ensure_ascii=False)
            if "location" in args:
                return json.dumps({
                    "pois": [
                        {
                            "name": "沐春足道",
                            "address": "北京市房山区良乡大学城附近",
                            "location": "116.180100,39.731200",
                        },
                        {
                            "name": "云庭SPA",
                            "address": "北京市房山区良乡南关附近",
                            "location": "116.171900,39.728600",
                        },
                    ],
                }, ensure_ascii=False)
            if "address" in args:
                return json.dumps({"geocodes": [{"location": "116.180100,39.731200"}]}, ensure_ascii=False)
            return "{}"

        self.agent._invoke_tool_text = fake_invoke_tool_text
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.agent._invoke_tool_text = self._original_invoke_tool_text

    async def capture_event(self, event: dict[str, Any]) -> None:
        data = event.get("data")
        try:
            parsed = json.loads(data) if isinstance(data, str) else data
        except Exception:
            parsed = data
        self.events.append({"event": event.get("event"), "data": parsed})


async def run_with_events(check: Callable[[DirectReadHarness], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
    async with DirectReadHarness() as harness:
        token = harness.agent._event_sink.set(harness.capture_event)
        try:
            return await check(harness)
        finally:
            harness.agent._event_sink.reset(token)


async def scenario_map_search_returns_followup_artifact() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="我想找适合三个人一起去的按摩店，请推荐附近店铺并展示地图",
            intent_analysis={
                "primary_intent": "map.search",
                "domain": "map",
                "operation_type": "read",
                "requires_confirmation": False,
                "next_action": "execute_read_tools",
            },
        )
        return {
            "reply": result.get("reply") if result else "",
            "artifacts": result.get("artifacts") if result else [],
            "tool_calls": result.get("tool_calls") if result else [],
            "events": harness.events,
        }

    actual = await run_with_events(check)
    failures: list[str] = []
    artifacts = actual.get("artifacts") or []
    artifact = artifacts[0] if artifacts else {}
    artifact_events = [item for item in actual.get("events", []) if item.get("event") == "artifact"]
    if not actual.get("reply") or ":::map" not in actual["reply"]:
        failures.append("map direct reply should include rendered map directives")
    if not artifacts:
        failures.append("map direct result should return a follow-up artifact")
    if not artifact_events:
        failures.append("map direct flow should emit an artifact event for streaming clients")
    if artifact.get("type") != "guide":
        failures.append(f"expected guide artifact, got {artifact.get('type')!r}")
    labels = [action.get("label") for action in artifact.get("actions", []) if isinstance(action, dict)]
    if "用第一家创建约伴草稿" not in labels:
        failures.append("expected an action for creating a draft from the first POI")
    prompts = [action.get("prompt", "") for action in artifact.get("actions", []) if isinstance(action, dict)]
    if not any("不要直接发布" in prompt and "沐春足道" in prompt for prompt in prompts):
        failures.append("draft action prompt should include the selected POI and no-direct-publish guard")
    return DirectReadResult("map_search_returns_followup_artifact", not failures, failures, actual)


async def scenario_multi_step_marks_primary_draft_action() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="先帮我找三家附近按摩店，等我选了再创建约伴订单",
            intent_analysis={
                "primary_intent": "multi_step",
                "domain": "multi",
                "operation_type": "mixed",
                "requires_confirmation": True,
                "next_action": "execute_read_tools",
            },
        )
        return {
            "artifacts": result.get("artifacts") if result else [],
            "events": harness.events,
        }

    actual = await run_with_events(check)
    failures: list[str] = []
    artifact = (actual.get("artifacts") or [{}])[0]
    actions = [action for action in artifact.get("actions", []) if isinstance(action, dict)]
    first_action = actions[0] if actions else {}
    if first_action.get("label") != "用第一家创建约伴草稿":
        failures.append("expected the first action to create a draft from the selected place")
    if first_action.get("primary") is not True:
        failures.append("multi-step read result should mark the draft action as primary")
    return DirectReadResult("multi_step_marks_primary_draft_action", not failures, failures, actual)


async def scenario_weather_direct_stays_text_only() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="查一下北京天气，晚上适不适合跑步",
            intent_analysis={
                "primary_intent": "weather.query",
                "domain": "weather",
                "operation_type": "read",
                "requires_confirmation": False,
                "next_action": "execute_read_tools",
            },
        )
        return {
            "reply": result.get("reply") if result else "",
            "artifacts": result.get("artifacts", []) if result else [],
            "tool_calls": result.get("tool_calls") if result else [],
        }

    actual = await run_with_events(check)
    failures: list[str] = []
    if "北京今日天气" not in actual.get("reply", ""):
        failures.append("weather direct reply should still render weather guidance")
    if actual.get("artifacts"):
        failures.append("weather direct response should not add map follow-up artifacts")
    return DirectReadResult("weather_direct_stays_text_only", not failures, failures, actual)


async def run_all() -> list[DirectReadResult]:
    scenarios = [
        scenario_map_search_returns_followup_artifact,
        scenario_multi_step_marks_primary_draft_action,
        scenario_weather_direct_stays_text_only,
    ]
    return [await scenario() for scenario in scenarios]


def print_text_report(results: list[DirectReadResult]) -> None:
    passed = sum(1 for item in results if item.ok)
    print(f"CampusHub direct read eval: {passed}/{len(results)} passed")
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
