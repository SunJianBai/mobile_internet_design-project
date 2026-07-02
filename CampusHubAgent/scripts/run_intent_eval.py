"""Run CampusHub intent-routing scenarios against the current agent.

Examples:
  python scripts/run_intent_eval.py --schema-only
  python scripts/run_intent_eval.py --limit 8
  python scripts/run_intent_eval.py --category guardrail --json
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
class ScenarioResult:
    scenario_id: str
    category: str
    ok: bool
    duration_ms: int
    failures: list[str]
    expected: dict[str, Any]
    actual: dict[str, Any]


def load_suite(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        suite = json.load(fh)
    if not isinstance(suite.get("scenarios"), list):
        raise ValueError("scenario suite must contain a scenarios array")
    return suite


def expected_values(expect: dict[str, Any], key: str) -> list[Any] | None:
    if key in expect:
        return [expect[key]]
    any_key = f"{key}_any"
    if any_key in expect:
        values = expect[any_key]
        return values if isinstance(values, list) else [values]
    return None


def check_expectation(actual: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for key in ("primary_intent", "domain", "operation_type", "next_action"):
        allowed = expected_values(expect, key)
        if allowed is not None and actual.get(key) not in allowed:
            failures.append(f"{key}: expected one of {allowed}, got {actual.get(key)!r}")

    if "requires_confirmation" in expect:
        actual_value = bool(actual.get("requires_confirmation"))
        if actual_value is not bool(expect["requires_confirmation"]):
            failures.append(
                "requires_confirmation: "
                f"expected {expect['requires_confirmation']}, got {actual_value}"
            )

    min_confidence = expect.get("min_confidence")
    if min_confidence is not None:
        confidence = actual.get("confidence")
        if not isinstance(confidence, (int, float)) or confidence < min_confidence:
            failures.append(f"confidence: expected >= {min_confidence}, got {confidence!r}")

    return failures


def validate_schema(suite: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    for index, scenario in enumerate(suite["scenarios"]):
        prefix = f"scenarios[{index}]"
        scenario_id = scenario.get("id")
        if not scenario_id:
            errors.append(f"{prefix}: missing id")
        elif scenario_id in ids:
            errors.append(f"{prefix}: duplicate id {scenario_id}")
        else:
            ids.add(scenario_id)
        if not scenario.get("category"):
            errors.append(f"{prefix}: missing category")
        if not scenario.get("message"):
            errors.append(f"{prefix}: missing message")
        if not isinstance(scenario.get("expect"), dict):
            errors.append(f"{prefix}: missing expect object")
    return errors


async def run_scenario(
    scenario: dict[str, Any],
    default_user: dict[str, Any],
    timeout_seconds: float,
) -> ScenarioResult:
    from app.agent import analyze_intent

    started_at = asyncio.get_running_loop().time()
    try:
        actual = await asyncio.wait_for(
            analyze_intent(
                user_info={**default_user, **scenario.get("user", {})},
                memories=scenario.get("memories", []),
                history=scenario.get("history", []),
                user_message=scenario["message"],
            ),
            timeout=timeout_seconds,
        )
        failures = check_expectation(actual, scenario["expect"])
    except asyncio.TimeoutError:
        actual = {"error": f"timed out after {timeout_seconds:g}s"}
        failures = [actual["error"]]
    except Exception as exc:  # pragma: no cover - eval runner should report environment issues.
        actual = {"error": str(exc)}
        failures = [f"scenario raised {exc.__class__.__name__}: {exc}"]

    return ScenarioResult(
        scenario_id=scenario["id"],
        category=scenario["category"],
        ok=not failures,
        duration_ms=int((asyncio.get_running_loop().time() - started_at) * 1000),
        failures=failures,
        expected=scenario["expect"],
        actual=actual,
    )


def select_scenarios(
    scenarios: list[dict[str, Any]],
    category: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    selected = [s for s in scenarios if category is None or s.get("category") == category]
    return selected[:limit] if limit else selected


def print_text_report(results: list[ScenarioResult]) -> None:
    passed = sum(1 for item in results if item.ok)
    total = len(results)
    print(f"CampusHub intent eval: {passed}/{total} passed")
    print("-" * 72)
    for result in results:
        mark = "PASS" if result.ok else "FAIL"
        intent = result.actual.get("primary_intent")
        domain = result.actual.get("domain")
        operation = result.actual.get("operation_type")
        confirm = result.actual.get("requires_confirmation")
        cache = " cache" if result.actual.get("cache_hit") else ""
        timeout = " timeout" if result.actual.get("router_timeout") else ""
        print(
            f"{mark:4} {result.scenario_id:34} "
            f"{domain}/{intent}/{operation}/confirm={confirm} "
            f"{result.duration_ms}ms{cache}{timeout}"
        )
        for failure in result.failures:
            print(f"     - {failure}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default=ROOT / "evals" / "agent_scenarios.json", type=Path)
    parser.add_argument("--category")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=float, default=30.0, help="seconds per scenario")
    parser.add_argument("--schema-only", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    suite = load_suite(args.suite)
    schema_errors = validate_schema(suite)
    if schema_errors:
        for error in schema_errors:
            print(error, file=sys.stderr)
        return 2

    scenarios = select_scenarios(suite["scenarios"], args.category, args.limit)
    if args.schema_only:
        print(f"Scenario schema OK: {len(scenarios)} selected / {len(suite['scenarios'])} total")
        return 0

    results = []
    for scenario in scenarios:
        results.append(await run_scenario(scenario, suite.get("default_user", {}), args.timeout))

    if args.json_output:
        print(json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2))
    else:
        print_text_report(results)

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
