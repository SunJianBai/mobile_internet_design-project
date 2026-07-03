"""Run the CampusHub agent quality gate.

This script groups the intent, journey, direct-read, contextual-order,
delegation-guard, and fallback checks that represent the current "real user"
regression suite. Semantic-only routing is optional because it calls the LLM
router directly and is much slower than the normal guarded path.

Examples:
  python scripts/run_agent_quality_suite.py
  python scripts/run_agent_quality_suite.py --include-semantic
  python scripts/run_agent_quality_suite.py --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class SuiteStep:
    name: str
    command: list[str]
    required: bool = True


@dataclass
class StepResult:
    name: str
    ok: bool
    required: bool
    duration_ms: int
    returncode: int
    command: list[str]
    stdout: str
    stderr: str


def build_steps(args: argparse.Namespace) -> list[SuiteStep]:
    py = sys.executable
    steps = [
        SuiteStep("intent_base", [py, "scripts/run_intent_eval.py", "--timeout", str(args.timeout)]),
        SuiteStep(
            "intent_persona",
            [
                py,
                "scripts/run_intent_eval.py",
                "--suite",
                "evals/persona_scenarios.json",
                "--timeout",
                str(args.timeout),
            ],
        ),
        SuiteStep("journeys", [py, "scripts/run_journey_eval.py", "--timeout", str(args.timeout)]),
        SuiteStep("direct_read", [py, "scripts/run_direct_read_eval.py"]),
        SuiteStep("contextual_order", [py, "scripts/run_contextual_order_eval.py"]),
        SuiteStep("delegation_guard", [py, "scripts/run_delegation_guard_eval.py"]),
        SuiteStep("router_fallback", [py, "scripts/run_router_fallback_eval.py"]),
    ]
    if args.include_semantic:
        steps.append(
            SuiteStep(
                "semantic_router",
                [
                    py,
                    "scripts/run_intent_eval.py",
                    "--suite",
                    "evals/semantic_scenarios.json",
                    "--semantic-only",
                    "--timeout",
                    str(args.semantic_timeout),
                ],
            )
        )
    return steps


def run_step(step: SuiteStep) -> StepResult:
    started_at = time.perf_counter()
    completed = subprocess.run(
        step.command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    return StepResult(
        name=step.name,
        ok=completed.returncode == 0,
        required=step.required,
        duration_ms=duration_ms,
        returncode=completed.returncode,
        command=step.command,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def run_steps(steps: list[SuiteStep], jobs: int) -> list[StepResult]:
    worker_count = max(1, min(int(jobs or 1), len(steps) or 1))
    if worker_count == 1:
        return [run_step(step) for step in steps]

    results: list[StepResult | None] = [None] * len(steps)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(run_step, step): index
            for index, step in enumerate(steps)
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return [result for result in results if result is not None]


def print_step_output(result: StepResult) -> None:
    mark = "PASS" if result.ok else "FAIL"
    print(f"\n[{mark}] {result.name} ({result.duration_ms}ms)")
    print("$ " + " ".join(result.command))
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print("[stderr]")
        print(result.stderr.rstrip())


def print_summary(results: list[StepResult]) -> None:
    passed = sum(result.ok for result in results)
    total = len(results)
    required_failures = [result for result in results if result.required and not result.ok]
    print("\n" + "=" * 76)
    print(f"CampusHub agent quality suite: {passed}/{total} steps passed")
    for result in results:
        mark = "PASS" if result.ok else "FAIL"
        print(f"{mark:4} {result.name:20} {result.duration_ms:>7}ms")
    if required_failures:
        failed_names = ", ".join(result.name for result in required_failures)
        print(f"Required failures: {failed_names}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=30.0, help="seconds per regular scenario/turn")
    parser.add_argument("--jobs", type=int, default=3, help="number of suite steps to run in parallel")
    parser.add_argument(
        "--include-semantic",
        action="store_true",
        help="also run the slow semantic-only LLM router scenarios",
    )
    parser.add_argument("--semantic-timeout", type=float, default=45.0, help="seconds per semantic-only scenario")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    results = run_steps(build_steps(args), args.jobs)
    if args.json_output:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    else:
        for result in results:
            print_step_output(result)
        print_summary(results)

    return 0 if all(result.ok or not result.required for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
