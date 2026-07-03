"""Run deterministic checks for Python-side memory extraction filtering.

These checks do not call an LLM, the Java backend, or AMap. They verify that
raw memory extraction output is filtered before it leaves the Agent service.

Examples:
  python scripts/run_memory_filter_eval.py
  python scripts/run_memory_filter_eval.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class MemoryFilterResult:
    scenario_id: str
    ok: bool
    failures: list[str]
    actual: dict[str, Any]


def run_case(scenario: dict[str, Any]) -> MemoryFilterResult:
    from app.agent import filter_extracted_memories

    actual_items = filter_extracted_memories(
        scenario["items"],
        scenario.get("user_message", ""),
        scenario.get("assistant_reply", ""),
    )
    failures: list[str] = []

    expected_count = scenario.get("expected_count")
    if expected_count is not None and len(actual_items) != expected_count:
        failures.append(f"expected {expected_count} memories, got {len(actual_items)}")

    expected_contents = scenario.get("expected_contents")
    if expected_contents is not None:
        actual_contents = [item.get("content") for item in actual_items]
        if actual_contents != expected_contents:
            failures.append(f"expected contents {expected_contents!r}, got {actual_contents!r}")

    rejected_contents = set(scenario.get("rejected_contents") or [])
    if rejected_contents:
        actual_contents = {item.get("content") for item in actual_items}
        leaked = sorted(rejected_contents & actual_contents)
        if leaked:
            failures.append(f"expected rejected memories to stay out, leaked {leaked!r}")

    expected_categories = scenario.get("expected_categories")
    if expected_categories is not None:
        actual_categories = [item.get("category") for item in actual_items]
        if actual_categories != expected_categories:
            failures.append(f"expected categories {expected_categories!r}, got {actual_categories!r}")

    return MemoryFilterResult(
        scenario_id=scenario["id"],
        ok=not failures,
        failures=failures,
        actual={"items": actual_items},
    )


def build_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "id": "rejects_no_signal_and_low_confidence_noise",
            "items": [
                {"category": "fact", "content": "没有提取到关于用户的事实性信息"},
                {"category": "behavior", "content": "用户发送的消息内容不明确，可能习惯性输入错误或测试系统反应"},
                {"category": "fact", "content": "用户可能在良乡校区附近活动"},
                {"category": "preference", "content": "用户似乎喜欢打篮球"},
            ],
            "user_message": "随便发点测试一下",
            "assistant_reply": "我不确定是否有值得保存的信息。",
            "expected_count": 0,
        },
        {
            "id": "keeps_durable_preference_and_stable_fact",
            "items": [
                {"category": "偏好", "content": "用户喜欢在良乡校区打篮球"},
                {"category": "fact", "content": "用户是计算机学院大三学生"},
            ],
            "user_message": "我是计算机学院大三学生，以后推荐活动优先考虑良乡校区篮球。",
            "assistant_reply": "好的，我会记住你的长期偏好和背景。",
            "expected_count": 2,
            "expected_categories": ["preference", "fact"],
            "expected_contents": ["用户喜欢在良乡校区打篮球", "用户是计算机学院大三学生"],
        },
        {
            "id": "rejects_transient_map_and_draft_results",
            "items": [
                {"category": "fact", "content": "用户提供的地点坐标为 116.170492, 39.728167"},
                {"category": "behavior", "content": "用户正在寻找适合三人一起去的按摩店"},
                {"category": "fact", "content": "用户想基于景阳阁SPA会所创建约伴订单草稿"},
            ],
            "user_message": "我想找3个人一起去洗脚按摩，有什么推荐的店吗",
            "assistant_reply": "我找到了 3 家店，并准备了一个约伴订单草稿。",
            "expected_count": 0,
        },
        {
            "id": "normalizes_categories_caps_and_deduplicates",
            "items": [
                {"category": "偏好", "content": "用户喜欢羽毛球"},
                {"category": "habit", "content": "用户经常晚上跑步"},
                {"category": "preference", "content": "用户喜欢羽毛球"},
                {"category": "fact", "content": "用户是北京理工大学学生"},
            ],
            "user_message": "我喜欢羽毛球，经常晚上跑步，也是北京理工大学学生。",
            "assistant_reply": "好的，我会记住这些长期信息。",
            "expected_count": 2,
            "expected_categories": ["preference", "behavior"],
            "expected_contents": ["用户喜欢羽毛球", "用户经常晚上跑步"],
        },
    ]


def print_text_report(results: list[MemoryFilterResult]) -> None:
    passed = sum(item.ok for item in results)
    print(f"CampusHub memory filter eval: {passed}/{len(results)} passed")
    print("-" * 72)
    for result in results:
        mark = "PASS" if result.ok else "FAIL"
        print(f"{mark:4} {result.scenario_id}")
        for failure in result.failures:
            print(f"     - {failure}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    results = [run_case(scenario) for scenario in build_scenarios()]
    if args.json_output:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    else:
        print_text_report(results)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
