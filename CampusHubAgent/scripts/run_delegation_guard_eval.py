"""Run regression checks for CampusHub agent delegation guards.

The checks monkeypatch sub-agent execution, so they do not call an LLM, the Java
backend, or AMap. They verify the scheduling layer that prevents repeated
delegation loops inside a single user turn.

Examples:
  python scripts/run_delegation_guard_eval.py
  python scripts/run_delegation_guard_eval.py --json
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
class GuardResult:
    scenario_id: str
    ok: bool
    failures: list[str]
    actual: dict[str, Any]


class GuardHarness:
    def __init__(self) -> None:
        from app import agent as agent_module

        self.agent = agent_module
        self.calls: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self._original_run_sub_agent = agent_module._run_sub_agent

    async def __aenter__(self) -> "GuardHarness":
        async def fake_run_sub_agent(
            agent_key: str,
            agent_name: str,
            system_prompt: str,
            tools: list,
            task: str,
        ) -> str:
            self.calls.append({
                "agent_key": agent_key,
                "agent_name": agent_name,
                "task": task,
            })
            return f"fake-result-{len(self.calls)}:{agent_key}:{task}"

        self.agent._run_sub_agent = fake_run_sub_agent
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.agent._run_sub_agent = self._original_run_sub_agent

    async def run_guarded(self, agent_key: str, task: str) -> str:
        return await self.agent._run_guarded_sub_agent(
            agent_key,
            f"{agent_key} expert",
            "system prompt",
            [],
            task,
        )

    async def capture_event(self, event: dict[str, Any]) -> None:
        payload = {
            "event": event.get("event"),
            "data": json.loads(event.get("data") or "{}"),
        }
        self.events.append(payload)


async def run_in_guard_context(
    check: Callable[[GuardHarness], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    async with GuardHarness() as harness:
        state_token = harness.agent._delegation_state.set({
            "total": 0,
            "counts": {},
            "results": {},
            "semantic_results": {},
        })
        event_token = harness.agent._event_sink.set(harness.capture_event)
        try:
            return await check(harness)
        finally:
            harness.agent._event_sink.reset(event_token)
            harness.agent._delegation_state.reset(state_token)


async def scenario_reuses_repeated_task() -> GuardResult:
    async def check(harness: GuardHarness) -> dict[str, Any]:
        first = await harness.run_guarded("map", "  Search nearby cafes  ")
        second = await harness.run_guarded("map", "search nearby   cafes")
        state = harness.agent._get_delegation_state()
        return {
            "first": first,
            "second": second,
            "call_count": len(harness.calls),
            "state_total": state["total"],
            "state_counts": dict(state["counts"]),
            "guard_events": [item for item in harness.events if item["data"].get("phase") == "delegation_guard"],
        }

    actual = await run_in_guard_context(check)
    failures: list[str] = []
    if actual["first"] != actual["second"]:
        failures.append("second repeated task should reuse the first result")
    if actual["call_count"] != 1:
        failures.append(f"expected 1 sub-agent call, got {actual['call_count']}")
    if actual["state_total"] != 1:
        failures.append(f"expected state total 1, got {actual['state_total']}")
    if actual["state_counts"].get("map") != 1:
        failures.append(f"expected map count 1, got {actual['state_counts'].get('map')}")
    if not actual["guard_events"]:
        failures.append("expected a delegation_guard event for result reuse")
    return GuardResult("reuses_repeated_task", not failures, failures, actual)


async def scenario_reuses_semantic_paraphrase() -> GuardResult:
    async def check(harness: GuardHarness) -> dict[str, Any]:
        first = await harness.run_guarded("map", "搜索北京理工大学良乡校区附近适合三个人的按摩店并展示地图")
        second = await harness.run_guarded("map", "帮我查北理良乡周边足疗店推荐，最好能看位置")
        third = await harness.run_guarded("map", "搜索北京理工大学良乡校区附近的篮球场")
        state = harness.agent._get_delegation_state()
        return {
            "first": first,
            "second": second,
            "third": third,
            "call_count": len(harness.calls),
            "calls": list(harness.calls),
            "state_total": state["total"],
            "state_counts": dict(state["counts"]),
            "guard_events": [item for item in harness.events if item["data"].get("phase") == "delegation_guard"],
        }

    actual = await run_in_guard_context(check)
    failures: list[str] = []
    if actual["first"] != actual["second"]:
        failures.append("semantic paraphrase should reuse the first map result")
    if actual["third"] == actual["first"]:
        failures.append("different place-search subject should not reuse the massage result")
    if actual["call_count"] != 2:
        failures.append(f"expected 2 sub-agent calls after semantic reuse and one distinct task, got {actual['call_count']}")
    if actual["state_total"] != 2:
        failures.append(f"expected state total 2, got {actual['state_total']}")
    if actual["state_counts"].get("map") != 2:
        failures.append(f"expected map count 2, got {actual['state_counts'].get('map')}")
    if not any("相近任务" in event["data"].get("title", "") for event in actual["guard_events"]):
        failures.append("expected a delegation_guard event for semantic result reuse")
    return GuardResult("reuses_semantic_paraphrase", not failures, failures, actual)


async def scenario_caps_single_agent() -> GuardResult:
    async def check(harness: GuardHarness) -> dict[str, Any]:
        first = await harness.run_guarded("order", "task one")
        second = await harness.run_guarded("order", "task two")
        third = await harness.run_guarded("order", "task three")
        state = harness.agent._get_delegation_state()
        return {
            "results": [first, second, third],
            "call_count": len(harness.calls),
            "state_total": state["total"],
            "state_counts": dict(state["counts"]),
            "guard_events": [item for item in harness.events if item["data"].get("phase") == "delegation_guard"],
        }

    actual = await run_in_guard_context(check)
    failures: list[str] = []
    if actual["call_count"] != 2:
        failures.append(f"expected 2 sub-agent calls before per-agent cap, got {actual['call_count']}")
    if actual["state_total"] != 2:
        failures.append(f"expected state total 2 after capped call, got {actual['state_total']}")
    if actual["state_counts"].get("order") != 2:
        failures.append(f"expected order count 2, got {actual['state_counts'].get('order')}")
    if actual["results"][2].startswith("fake-result-3"):
        failures.append("third same-agent call should be blocked instead of executed")
    if not any(event["data"].get("state") == "failed" for event in actual["guard_events"]):
        failures.append("expected failed delegation_guard event for per-agent cap")
    return GuardResult("caps_single_agent", not failures, failures, actual)


async def scenario_caps_total_delegations() -> GuardResult:
    async def check(harness: GuardHarness) -> dict[str, Any]:
        tasks = [
            ("order", "order task one"),
            ("order", "order task two"),
            ("map", "map task one"),
            ("map", "map task two"),
            ("content", "content task one"),
        ]
        results = []
        for agent_key, task in tasks:
            results.append(await harness.run_guarded(agent_key, task))
        state = harness.agent._get_delegation_state()
        return {
            "results": results,
            "call_count": len(harness.calls),
            "state_total": state["total"],
            "state_counts": dict(state["counts"]),
            "guard_events": [item for item in harness.events if item["data"].get("phase") == "delegation_guard"],
        }

    actual = await run_in_guard_context(check)
    failures: list[str] = []
    if actual["call_count"] != 4:
        failures.append(f"expected 4 sub-agent calls before total cap, got {actual['call_count']}")
    if actual["state_total"] != 4:
        failures.append(f"expected state total 4 after capped call, got {actual['state_total']}")
    if actual["results"][-1].startswith("fake-result-5"):
        failures.append("fifth total delegation should be blocked instead of executed")
    if not any(event["data"].get("state") == "failed" for event in actual["guard_events"]):
        failures.append("expected failed delegation_guard event for total cap")
    return GuardResult("caps_total_delegations", not failures, failures, actual)


async def scenario_isolates_user_turns() -> GuardResult:
    async with GuardHarness() as harness:
        event_token = harness.agent._event_sink.set(harness.capture_event)
        turn_totals = []
        try:
            for _ in range(2):
                state_token = harness.agent._delegation_state.set({
                    "total": 0,
                    "counts": {},
                    "results": {},
                    "semantic_results": {},
                })
                try:
                    await harness.run_guarded("map", "same task")
                    state = harness.agent._get_delegation_state()
                    turn_totals.append(state["total"])
                finally:
                    harness.agent._delegation_state.reset(state_token)
        finally:
            harness.agent._event_sink.reset(event_token)

        actual = {
            "call_count": len(harness.calls),
            "turn_totals": turn_totals,
            "tasks": [call["task"] for call in harness.calls],
        }

    failures: list[str] = []
    if actual["call_count"] != 2:
        failures.append(f"expected same task to execute once per user turn, got {actual['call_count']} calls")
    if actual["turn_totals"] != [1, 1]:
        failures.append("delegation state should reset between user turns")
    return GuardResult("isolates_user_turns", not failures, failures, actual)


async def run_all() -> list[GuardResult]:
    scenarios = [
        scenario_reuses_repeated_task,
        scenario_reuses_semantic_paraphrase,
        scenario_caps_single_agent,
        scenario_caps_total_delegations,
        scenario_isolates_user_turns,
    ]
    return [await scenario() for scenario in scenarios]


def print_text_report(results: list[GuardResult]) -> None:
    passed = sum(1 for item in results if item.ok)
    print(f"CampusHub delegation guard eval: {passed}/{len(results)} passed")
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
