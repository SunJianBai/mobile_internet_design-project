"""Run multi-turn CampusHub journey scenarios against the current agent.

The journey suite accumulates conversation history between turns, so it can
verify contextual routing such as map result follow-ups, draft edits, guarded
writes, and read-only pivots in one realistic user session.

Examples:
  python scripts/run_journey_eval.py
  python scripts/run_journey_eval.py --json
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
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_intent_eval import check_expectation  # noqa: E402


@dataclass
class TurnResult:
    journey_id: str
    turn_index: int
    ok: bool
    duration_ms: int
    message: str
    failures: list[str]
    expected: dict[str, Any]
    actual: dict[str, Any]


@dataclass
class JourneyResult:
    journey_id: str
    persona: str
    ok: bool
    turns: list[TurnResult]


def load_suite(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        suite = json.load(fh)
    if not isinstance(suite.get("journeys"), list):
        raise ValueError("journey suite must contain a journeys array")
    return suite


def validate_suite(suite: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    for index, journey in enumerate(suite["journeys"]):
        prefix = f"journeys[{index}]"
        journey_id = journey.get("id")
        if not journey_id:
            errors.append(f"{prefix}: missing id")
        elif journey_id in ids:
            errors.append(f"{prefix}: duplicate id {journey_id}")
        else:
            ids.add(journey_id)
        turns = journey.get("turns")
        if not isinstance(turns, list) or not turns:
            errors.append(f"{prefix}: missing non-empty turns")
            continue
        for turn_index, turn in enumerate(turns):
            turn_prefix = f"{prefix}.turns[{turn_index}]"
            if not turn.get("message"):
                errors.append(f"{turn_prefix}: missing message")
            if not isinstance(turn.get("expect"), dict):
                errors.append(f"{turn_prefix}: missing expect object")
    return errors


def check_markers(actual: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for marker in expect.get("markers", []):
        if not actual.get(marker):
            failures.append(f"marker {marker}: expected truthy, got {actual.get(marker)!r}")
    return failures


async def run_turn(
    journey_id: str,
    turn_index: int,
    turn: dict[str, Any],
    user_info: dict[str, Any],
    memories: list[dict[str, Any]],
    history: list[dict[str, str]],
    timeout_seconds: float,
) -> TurnResult:
    from app.agent import analyze_intent, _requires_confirmation_gate

    started_at = asyncio.get_running_loop().time()
    try:
        actual = await asyncio.wait_for(
            analyze_intent(
                user_info=user_info,
                memories=memories + turn.get("memories", []),
                history=history,
                user_message=turn["message"],
            ),
            timeout=timeout_seconds,
        )
        duration_ms = int((asyncio.get_running_loop().time() - started_at) * 1000)
        actual = dict(actual)
        actual["duration_ms"] = duration_ms
        actual["confirmation_gate"] = _requires_confirmation_gate(actual)
        failures = check_expectation(actual, turn["expect"], duration_ms)
        failures.extend(check_markers(actual, turn["expect"]))
    except asyncio.TimeoutError:
        duration_ms = int((asyncio.get_running_loop().time() - started_at) * 1000)
        actual = {"error": f"timed out after {timeout_seconds:g}s"}
        failures = [actual["error"]]
    except Exception as exc:  # pragma: no cover - eval runner should report environment issues.
        duration_ms = int((asyncio.get_running_loop().time() - started_at) * 1000)
        actual = {"error": str(exc)}
        failures = [f"turn raised {exc.__class__.__name__}: {exc}"]

    return TurnResult(
        journey_id=journey_id,
        turn_index=turn_index,
        ok=not failures,
        duration_ms=duration_ms,
        message=turn["message"],
        failures=failures,
        expected=turn["expect"],
        actual=actual,
    )


async def run_journey(
    journey: dict[str, Any],
    default_user: dict[str, Any],
    timeout_seconds: float,
) -> JourneyResult:
    from app import agent as agent_module

    user_info = {**default_user, **journey.get("user", {})}
    memories = list(journey.get("memories", []))
    history = list(journey.get("initial_history", []))
    turns: list[TurnResult] = []

    agent_module._intent_cache.clear()
    for index, turn in enumerate(journey["turns"], start=1):
        result = await run_turn(
            journey["id"],
            index,
            turn,
            user_info,
            memories,
            history,
            timeout_seconds,
        )
        turns.append(result)
        history.append({"role": "user", "content": turn["message"]})
        assistant_context = turn.get("assistant_context")
        if assistant_context:
            history.append({"role": "assistant", "content": assistant_context})

    return JourneyResult(
        journey_id=journey["id"],
        persona=journey.get("persona", ""),
        ok=all(turn.ok for turn in turns),
        turns=turns,
    )


def print_text_report(results: list[JourneyResult]) -> None:
    passed_journeys = sum(1 for item in results if item.ok)
    total_journeys = len(results)
    all_turns = [turn for journey in results for turn in journey.turns]
    passed_turns = sum(1 for turn in all_turns if turn.ok)
    print(f"CampusHub journey eval: {passed_turns}/{len(all_turns)} turns passed, {passed_journeys}/{total_journeys} journeys passed")
    print("-" * 92)
    for journey in results:
        mark = "PASS" if journey.ok else "FAIL"
        print(f"{mark:4} {journey.journey_id} {journey.persona}")
        for turn in journey.turns:
            turn_mark = "PASS" if turn.ok else "FAIL"
            intent = turn.actual.get("primary_intent")
            domain = turn.actual.get("domain")
            operation = turn.actual.get("operation_type")
            confirm = turn.actual.get("requires_confirmation")
            gate = " gate" if turn.actual.get("confirmation_gate") else ""
            markers = [marker for marker in turn.expected.get("markers", []) if turn.actual.get(marker)]
            marker_text = f" markers={','.join(markers)}" if markers else ""
            print(
                f"  {turn_mark:4} T{turn.turn_index:<2} "
                f"{domain}/{intent}/{operation}/confirm={confirm} "
                f"{turn.duration_ms}ms{gate}{marker_text}"
            )
            for failure in turn.failures:
                print(f"       - {failure}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default=ROOT / "evals" / "journey_scenarios.json", type=Path)
    parser.add_argument("--timeout", type=float, default=30.0, help="seconds per turn")
    parser.add_argument("--schema-only", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    suite = load_suite(args.suite)
    errors = validate_suite(suite)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    if args.schema_only:
        turn_count = sum(len(journey["turns"]) for journey in suite["journeys"])
        print(f"Journey schema OK: {len(suite['journeys'])} journeys / {turn_count} turns")
        return 0

    results = []
    for journey in suite["journeys"]:
        results.append(await run_journey(journey, suite.get("default_user", {}), args.timeout))

    if args.json_output:
        print(json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2, default=lambda value: value.__dict__))
    else:
        print_text_report(results)

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
