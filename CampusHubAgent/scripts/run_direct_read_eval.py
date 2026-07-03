"""Run deterministic checks for direct read responses.

These checks patch tool invocation, so they do not call AMap, the LLM, or the
Java backend. They verify that fast read paths and execution plans return rich
UI artifacts instead of only plain text.

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
            tool_name = getattr(tool_obj, "name", "")
            self.tool_calls.append({"name": tool_name, "args": args})
            if tool_name == "search_orders":
                if args.get("activity_type") == "RUNNING":
                    return "暂时没有找到符合条件的约伴订单。"
                return (
                    "找到 2 个约伴订单：\n\n"
                    "- **[订单#42](/orders/42)** BASKETBALL | LIANGXIANG | 良乡体育馆 | 2026-07-03 19:00:00 | 2/4人\n"
                    "- **[订单#43](/orders/43)** BADMINTON | LIANGXIANG | 羽毛球馆 | 2026-07-03 20:00:00 | 1/4人"
                )
            if tool_name == "search_contents":
                return (
                    "找到 2 条动态：\n\n"
                    "- **[动态#77](/contents/77)** by 小白 — 今晚图书馆二楼自习，有同学一起吗\n"
                    "- **[动态#78](/contents/78)** by 晚风 — 求一个自习搭子，期末周互相监督"
                )
            if tool_name == "get_user_profile":
                user_id = args.get("user_id")
                if str(user_id) == "12":
                    return (
                        "**用户资料**\n\n"
                        "- 用户ID: 12\n"
                        "- 昵称: 小白\n"
                        "- 签名: 爱自习和羽毛球\n"
                        "- 邮箱: xiaobai@example.com\n"
                        "- 加入时间: 2026-06-01T09:00:00"
                    )
                return f"未找到ID为 {user_id} 的用户。"
            if tool_name == "search_users":
                return (
                    "找到 2 个用户：\n\n"
                    "- 小白 (ID: 12)\n"
                    "- 小白同学 (ID: 15)"
                )
            if tool_name in {"maps_direction_walking", "maps_direction_driving"}:
                return json.dumps({
                    "route": {
                        "paths": [{
                            "distance": "1800",
                            "duration": "1320",
                            "steps": [
                                {"instruction": "从北京理工大学良乡校区出发，向东步行"},
                                {"instruction": "沿良乡东路继续前行"},
                                {"instruction": "到达首创奥特莱斯电影院"},
                            ],
                        }]
                    }
                }, ensure_ascii=False)
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
                if args.get("keywords") == "电影院":
                    return json.dumps({
                        "pois": [{
                            "name": "首创奥特莱斯电影院",
                            "address": "北京市房山区首创奥莱",
                            "location": "116.186600,39.722900",
                        }],
                    }, ensure_ascii=False)
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
    items = artifact.get("items") or []
    if len(items) != 2:
        failures.append(f"expected 2 structured map candidate items, got {len(items)}")
    first_item = items[0] if items else {}
    if "沐春足道" not in first_item.get("title", ""):
        failures.append(f"expected first map item title to include 沐春足道, got {first_item.get('title')!r}")
    if "116.180100,39.731200" not in first_item.get("meta", ""):
        failures.append(f"expected first map item coordinates, got {first_item.get('meta')!r}")
    if first_item.get("actionLabel") != "生成草稿":
        failures.append(f"expected first map item action label, got {first_item.get('actionLabel')!r}")
    if first_item.get("hint") != "先确认再发布":
        failures.append(f"expected first map item safety hint, got {first_item.get('hint')!r}")
    if "不要直接发布" not in first_item.get("prompt", ""):
        failures.append("map item prompt should keep the no-direct-publish guard")
    labels = [action.get("label") for action in artifact.get("actions", []) if isinstance(action, dict)]
    if "用第一家创建约伴草稿" not in labels:
        failures.append("expected an action for creating a draft from the first POI")
    prompts = [action.get("prompt", "") for action in artifact.get("actions", []) if isinstance(action, dict)]
    if not any("不要直接发布" in prompt and "沐春足道" in prompt for prompt in prompts):
        failures.append("draft action prompt should include the selected POI and no-direct-publish guard")
    return DirectReadResult("map_search_returns_followup_artifact", not failures, failures, actual)


async def scenario_english_map_restaurant_uses_precise_keyword() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="find restaurants near BIT Liangxiang for three people, show map, no order",
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
            "tool_calls": harness.tool_calls,
            "artifacts": result.get("artifacts") if result else [],
        }

    actual = await run_with_events(check)
    failures: list[str] = []
    map_calls = [
        call for call in actual.get("tool_calls", [])
        if call.get("args", {}).get("location")
    ]
    first_args = map_calls[0].get("args", {}) if map_calls else {}
    if first_args.get("keywords") != "餐厅":
        failures.append(f"expected English restaurant request to search 餐厅, got {first_args.get('keywords')!r}")
    if "餐厅" not in actual.get("reply", ""):
        failures.append("map reply should describe the restaurant category instead of generic campus surroundings")
    return DirectReadResult("english_map_restaurant_uses_precise_keyword", not failures, failures, actual)


async def scenario_noisy_english_map_restaurant_uses_precise_keyword() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="Tesfind resturants near BIT Liangxiang for three people, show map, no order",
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
            "tool_calls": harness.tool_calls,
            "artifacts": result.get("artifacts") if result else [],
        }

    actual = await run_with_events(check)
    failures: list[str] = []
    map_calls = [
        call for call in actual.get("tool_calls", [])
        if call.get("args", {}).get("location")
    ]
    first_args = map_calls[0].get("args", {}) if map_calls else {}
    if first_args.get("keywords") != "餐厅":
        failures.append(f"expected noisy English restaurant request to search 餐厅, got {first_args.get('keywords')!r}")
    if "餐厅" not in actual.get("reply", ""):
        failures.append("noisy English map reply should describe the restaurant category")
    return DirectReadResult("noisy_english_map_restaurant_uses_precise_keyword", not failures, failures, actual)


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


async def scenario_weather_direct_returns_artifact() -> DirectReadResult:
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
            "events": harness.events,
        }

    actual = await run_with_events(check)
    failures: list[str] = []
    if "北京今日天气" not in actual.get("reply", ""):
        failures.append("weather direct reply should still render weather guidance")
    artifacts = actual.get("artifacts") or []
    artifact = artifacts[0] if artifacts else {}
    artifact_events = [item for item in actual.get("events", []) if item.get("event") == "artifact"]
    if not artifacts:
        failures.append("weather direct response should return a structured weather artifact")
    if not artifact_events:
        failures.append("weather direct flow should emit an artifact event for streaming clients")
    if artifact.get("type") != "weather":
        failures.append(f"expected weather artifact, got {artifact.get('type')!r}")
    fields = {field.get("label"): field.get("value") for field in artifact.get("fields", []) if isinstance(field, dict)}
    if fields.get("白天") != "晴 · 31℃":
        failures.append(f"expected daytime weather field, got {fields.get('白天')!r}")
    labels = [action.get("label") for action in artifact.get("actions", []) if isinstance(action, dict)]
    if "找室内备选地点" not in labels:
        failures.append("expected an action for indoor backup places")
    return DirectReadResult("weather_direct_returns_artifact", not failures, failures, actual)


async def scenario_map_weather_combo_returns_two_artifacts() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="Tomorrow night I want to watch a movie with roommates, check weather, route, and nearby restaurants, no post",
            intent_analysis={
                "primary_intent": "map.search",
                "domain": "map",
                "operation_type": "read",
                "requires_confirmation": False,
                "next_action": "execute_read_tools",
                "weather_context": True,
            },
        )
        return {
            "reply": result.get("reply") if result else "",
            "artifacts": result.get("artifacts", []) if result else [],
            "tool_calls": result.get("tool_calls") if result else [],
            "events": harness.events,
        }

    actual = await run_with_events(check)
    failures: list[str] = []
    artifacts = actual.get("artifacts") or []
    artifact_types = [artifact.get("type") for artifact in artifacts if isinstance(artifact, dict)]
    tool_names = [call.get("name") for call in actual.get("tool_calls", []) if isinstance(call, dict)]
    event_artifact_types = [
        item.get("data", {}).get("type")
        for item in actual.get("events", [])
        if item.get("event") == "artifact" and isinstance(item.get("data"), dict)
    ]
    if "北京今日天气" not in actual.get("reply", ""):
        failures.append("combined map/weather reply should include weather guidance")
    if ":::map" not in actual.get("reply", ""):
        failures.append("combined map/weather reply should include map directives")
    if artifact_types[:2] != ["weather", "guide"]:
        failures.append(f"expected weather and guide artifacts, got {artifact_types!r}")
    if "maps_weather" not in tool_names:
        failures.append(f"expected maps_weather tool call, got {tool_names!r}")
    if not any(call.get("args", {}).get("location") for call in actual.get("tool_calls", []) if isinstance(call, dict)):
        failures.append("expected a map around-search tool call with location args")
    if event_artifact_types[:2] != ["weather", "guide"]:
        failures.append(f"expected streaming artifact events for weather and guide, got {event_artifact_types!r}")
    return DirectReadResult("map_weather_combo_returns_two_artifacts", not failures, failures, actual)


async def scenario_route_request_returns_route_artifact() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="从良乡校区到最近的电影院怎么走？给我地图就行",
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
            "artifacts": result.get("artifacts", []) if result else [],
            "tool_calls": result.get("tool_calls", []) if result else [],
            "events": harness.events,
        }

    actual = await run_with_events(check)
    failures: list[str] = []
    artifacts = actual.get("artifacts") or []
    artifact = artifacts[0] if artifacts else {}
    fields = {
        field.get("label"): field.get("value")
        for field in artifact.get("fields", [])
        if isinstance(field, dict)
    }
    tool_names = [call.get("name") for call in actual.get("tool_calls", []) if isinstance(call, dict)]
    artifact_events = [
        item.get("data", {})
        for item in actual.get("events", [])
        if item.get("event") == "artifact" and isinstance(item.get("data"), dict)
    ]
    if actual.get("reply", "").count(":::map") < 2:
        failures.append("route reply should render both origin and destination maps")
    if "路线要点" not in actual.get("reply", ""):
        failures.append("route reply should include route step highlights")
    if artifact.get("type") != "guide":
        failures.append(f"expected route guide artifact, got {artifact.get('type')!r}")
    if artifact.get("title") != "路线规划结果":
        failures.append(f"expected route artifact title, got {artifact.get('title')!r}")
    if fields.get("终点") != "首创奥特莱斯电影院":
        failures.append(f"expected resolved cinema destination, got {fields.get('终点')!r}")
    if fields.get("方式") != "步行":
        failures.append(f"expected walking route mode, got {fields.get('方式')!r}")
    if fields.get("距离") != "1.8 公里":
        failures.append(f"expected formatted distance, got {fields.get('距离')!r}")
    if "maps_around_search" not in tool_names or "maps_direction_walking" not in tool_names:
        failures.append(f"expected around-search then walking direction tools, got {tool_names!r}")
    labels = [action.get("label") for action in artifact.get("actions", []) if isinstance(action, dict)]
    if "用终点约伴" not in labels:
        failures.append("route artifact should offer a draft-from-destination action")
    prompts = [action.get("prompt", "") for action in artifact.get("actions", []) if isinstance(action, dict)]
    if not any("不要直接发布" in prompt and "首创奥特莱斯电影院" in prompt for prompt in prompts):
        failures.append("route follow-up prompt should preserve confirmation before publishing")
    if not artifact_events or artifact_events[0].get("title") != "路线规划结果":
        failures.append("route direct flow should emit the route artifact for streaming clients")
    return DirectReadResult("route_request_returns_route_artifact", not failures, failures, actual)


async def scenario_order_search_returns_result_artifact() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="帮我看看良乡校区今天有没有适合加入的篮球约伴活动",
            intent_analysis={
                "primary_intent": "order.search",
                "domain": "order",
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
    if "订单#42" not in actual.get("reply", ""):
        failures.append("order direct reply should include the order list")
    if not artifacts:
        failures.append("order direct response should return a structured order artifact")
    if not artifact_events:
        failures.append("order direct flow should emit an artifact event for streaming clients")
    if artifact.get("type") != "order":
        failures.append(f"expected order artifact, got {artifact.get('type')!r}")
    fields = {field.get("label"): field.get("value") for field in artifact.get("fields", []) if isinstance(field, dict)}
    if "2 个结果" != fields.get("匹配数量"):
        failures.append(f"expected order count field, got {fields.get('匹配数量')!r}")
    preview = str(fields.get("结果预览") or "")
    if "订单#42" not in preview or "订单#43" not in preview:
        failures.append(f"expected order preview to include top results, got {preview!r}")
    items = artifact.get("items") or []
    if len(items) != 2:
        failures.append(f"expected 2 structured order items, got {len(items)}")
    item_routes = [item.get("route") for item in items if isinstance(item, dict)]
    if "/orders/42" not in item_routes or "/orders/43" not in item_routes:
        failures.append(f"expected order item routes, got {item_routes!r}")
    actions = [action for action in artifact.get("actions", []) if isinstance(action, dict)]
    first_action = actions[0] if actions else {}
    if first_action.get("route") != "/orders/42":
        failures.append(f"expected first order route, got {first_action.get('route')!r}")
    if not any(action.get("label") == "申请加入第一条" and "订单#42" in action.get("prompt", "") for action in actions):
        failures.append("order result card should offer a first-result apply confirmation action")
    if not any("不要直接提交" in action.get("prompt", "") for action in actions):
        failures.append("order apply prompt should keep the no-direct-submit guard")
    if not any("不要直接发布" in action.get("prompt", "") for action in actions):
        failures.append("order follow-up prompt should keep the no-direct-publish guard")
    return DirectReadResult("order_search_returns_result_artifact", not failures, failures, actual)


async def scenario_order_search_empty_returns_action_card() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="帮我看看良乡校区今晚有没有跑步约伴活动",
            intent_analysis={
                "primary_intent": "order.search",
                "domain": "order",
                "operation_type": "read",
                "requires_confirmation": False,
                "next_action": "execute_read_tools",
            },
        )
        return {
            "reply": result.get("reply") if result else "",
            "artifacts": result.get("artifacts") if result else [],
            "events": harness.events,
        }

    actual = await run_with_events(check)
    failures: list[str] = []
    artifact = (actual.get("artifacts") or [{}])[0]
    artifact_events = [item for item in actual.get("events", []) if item.get("event") == "artifact"]
    if artifact.get("type") != "order":
        failures.append(f"expected order artifact for empty result, got {artifact.get('type')!r}")
    if "暂未找到" not in artifact.get("title", ""):
        failures.append(f"expected empty order title, got {artifact.get('title')!r}")
    if not artifact_events:
        failures.append("empty order direct flow should still emit an artifact event")
    fields = {field.get("label"): field.get("value") for field in artifact.get("fields", []) if isinstance(field, dict)}
    if fields.get("匹配数量") != "0 个结果":
        failures.append(f"expected zero-result count field, got {fields.get('匹配数量')!r}")
    labels = [action.get("label") for action in artifact.get("actions", []) if isinstance(action, dict)]
    if "发起约伴草稿" not in labels:
        failures.append("empty result card should offer a draft action")
    return DirectReadResult("order_search_empty_returns_action_card", not failures, failures, actual)


async def scenario_content_search_returns_result_artifact() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="搜索一下关于自习的校园动态",
            intent_analysis={
                "primary_intent": "content.search",
                "domain": "content",
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
    if "动态#77" not in actual.get("reply", ""):
        failures.append("content direct reply should include the content list")
    if not artifacts:
        failures.append("content direct response should return a structured content artifact")
    if not artifact_events:
        failures.append("content direct flow should emit an artifact event for streaming clients")
    if artifact.get("type") != "content":
        failures.append(f"expected content artifact, got {artifact.get('type')!r}")
    fields = {field.get("label"): field.get("value") for field in artifact.get("fields", []) if isinstance(field, dict)}
    if fields.get("搜索主题") != "自习":
        failures.append(f"expected content keyword field, got {fields.get('搜索主题')!r}")
    preview = str(fields.get("结果预览") or "")
    if "动态#77" not in preview or "动态#78" not in preview:
        failures.append(f"expected content preview to include top results, got {preview!r}")
    items = artifact.get("items") or []
    if len(items) != 2:
        failures.append(f"expected 2 structured content items, got {len(items)}")
    item_routes = [item.get("route") for item in items if isinstance(item, dict)]
    if "/contents/77" not in item_routes or "/contents/78" not in item_routes:
        failures.append(f"expected content item routes, got {item_routes!r}")
    actions = [action for action in artifact.get("actions", []) if isinstance(action, dict)]
    first_action = actions[0] if actions else {}
    if first_action.get("route") != "/contents/77":
        failures.append(f"expected first content route, got {first_action.get('route')!r}")
    if not any(action.get("label") == "评论第一条" and "动态#77" in action.get("prompt", "") for action in actions):
        failures.append("content result card should offer a first-result comment confirmation action")
    if not any("不要直接发布" in action.get("prompt", "") for action in actions):
        failures.append("content draft prompt should keep the no-direct-publish guard")
    return DirectReadResult("content_search_returns_result_artifact", not failures, failures, actual)


async def scenario_user_profile_returns_result_artifact() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="那个 12 号同学的主页给我瞅瞅，他以前发过啥",
            intent_analysis={
                "primary_intent": "user.profile",
                "domain": "user",
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
    artifact = (actual.get("artifacts") or [{}])[0]
    fields = {field.get("label"): field.get("value") for field in artifact.get("fields", []) if isinstance(field, dict)}
    actions = [action for action in artifact.get("actions", []) if isinstance(action, dict)]
    if artifact.get("type") != "user":
        failures.append(f"expected user artifact, got {artifact.get('type')!r}")
    if fields.get("用户ID") != "12":
        failures.append(f"expected user id 12, got {fields.get('用户ID')!r}")
    if fields.get("昵称") != "小白":
        failures.append(f"expected nickname 小白, got {fields.get('昵称')!r}")
    if not any((call or {}).get("name") == "get_user_profile" for call in actual.get("tool_calls", [])):
        failures.append("expected get_user_profile tool call")
    if not any(action.get("label") == "搜索 TA 的动态" and "不要评论或点赞" in action.get("prompt", "") for action in actions):
        failures.append("user profile card should offer guarded content follow-up")
    if not any(item.get("event") == "artifact" for item in actual.get("events", [])):
        failures.append("user profile direct flow should emit an artifact event")
    return DirectReadResult("user_profile_returns_result_artifact", not failures, failures, actual)


async def scenario_user_search_returns_result_artifact() -> DirectReadResult:
    async def check(harness: DirectReadHarness) -> dict[str, Any]:
        result = await harness.agent.build_direct_read_response(
            user_info={"uid": 4, "campus": "LIANGXIANG"},
            user_message="搜索小白同学的主页资料",
            intent_analysis={
                "primary_intent": "user.profile",
                "domain": "user",
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
    artifact = (actual.get("artifacts") or [{}])[0]
    items = artifact.get("items") or []
    fields = {field.get("label"): field.get("value") for field in artifact.get("fields", []) if isinstance(field, dict)}
    if artifact.get("type") != "user":
        failures.append(f"expected user search artifact, got {artifact.get('type')!r}")
    if fields.get("匹配数量") != "2 个用户":
        failures.append(f"expected 2 user matches, got {fields.get('匹配数量')!r}")
    if len(items) != 2:
        failures.append(f"expected 2 user result items, got {len(items)}")
    if not any((call or {}).get("name") == "search_users" for call in actual.get("tool_calls", [])):
        failures.append("expected search_users tool call")
    if not any("用户 12" in item.get("prompt", "") for item in items if isinstance(item, dict)):
        failures.append("user result item should offer profile lookup prompt")
    return DirectReadResult("user_search_returns_result_artifact", not failures, failures, actual)


async def scenario_execution_plan_describes_tool_path() -> DirectReadResult:
    from app import agent as agent_module

    plan = agent_module._build_execution_plan_artifact({
        "primary_intent": "order.search",
        "domain": "order",
        "operation_type": "read",
        "requires_confirmation": False,
        "suggested_agents": ["order_query"],
        "next_action": "execute_read_tools",
    })
    failures: list[str] = []
    if plan.get("type") != "plan":
        failures.append(f"expected plan artifact, got {plan.get('type')!r}")
    fields = {field.get("label"): field.get("value") for field in plan.get("fields", []) if isinstance(field, dict)}
    if fields.get("策略") != "确定性工具路径":
        failures.append(f"expected deterministic tool strategy, got {fields.get('策略')!r}")
    if fields.get("调度守卫") != "仅允许：订单专家":
        failures.append(f"expected order-only delegation guard, got {fields.get('调度守卫')!r}")
    if "确认门" not in fields:
        failures.append("plan should surface the confirmation-gate policy field")
    if "越界处理" not in fields:
        failures.append("plan should surface the delegation-boundary field")
    titles = [step.get("title") for step in plan.get("steps", []) if isinstance(step, dict)]
    if "锁定本轮专家范围" not in titles:
        failures.append("plan should include the delegation guard step")
    if "确认门策略" not in titles:
        failures.append("plan should include the confirmation-gate step")
    if "越界委派拦截" not in titles:
        failures.append("plan should include the delegation-boundary step")
    if "查询约伴活动" not in titles:
        failures.append("plan should include an order query step")
    if "生成订单结果卡" not in titles:
        failures.append("plan should include a result-card step")
    intent = plan.get("intent") if isinstance(plan.get("intent"), dict) else {}
    if intent.get("allowed_delegation_agents") != ["order"]:
        failures.append(f"expected allowed_delegation_agents ['order'], got {intent.get('allowed_delegation_agents')!r}")
    return DirectReadResult("execution_plan_describes_tool_path", not failures, failures, {"plan": plan})


async def scenario_execution_plan_surfaces_missing_slots() -> DirectReadResult:
    from app import agent as agent_module

    plan = agent_module._build_execution_plan_artifact({
        "primary_intent": "order.create",
        "domain": "order",
        "operation_type": "write",
        "requires_confirmation": True,
        "suggested_agents": ["order_draft"],
        "missing_slots": ["地点", "时间"],
        "next_action": "ask_clarification",
    })
    failures: list[str] = []
    fields = {field.get("label"): field.get("value") for field in plan.get("fields", []) if isinstance(field, dict)}
    if fields.get("待补充") != "地点、时间":
        failures.append(f"expected missing slot field, got {fields.get('待补充')!r}")
    if fields.get("确认门") != "先补齐缺失字段，再生成可确认草稿":
        failures.append(f"expected missing-slot confirmation gate, got {fields.get('确认门')!r}")
    titles = [step.get("title") for step in plan.get("steps", []) if isinstance(step, dict)]
    if "标出待补充信息" not in titles:
        failures.append("plan should include a missing-slot explanation step")
    if "确认门策略" not in titles:
        failures.append("plan should include the confirmation-gate step")
    if "越界委派拦截" not in titles:
        failures.append("plan should include the delegation-boundary step")
    intent = plan.get("intent") if isinstance(plan.get("intent"), dict) else {}
    if intent.get("missing_slots") != ["地点", "时间"]:
        failures.append(f"expected normalized missing slots in intent, got {intent.get('missing_slots')!r}")
    if intent.get("allowed_delegation_agents") != ["order"]:
        failures.append(f"expected allowed order delegation, got {intent.get('allowed_delegation_agents')!r}")
    return DirectReadResult("execution_plan_surfaces_missing_slots", not failures, failures, {"plan": plan})


async def run_all() -> list[DirectReadResult]:
    scenarios = [
        scenario_map_search_returns_followup_artifact,
        scenario_english_map_restaurant_uses_precise_keyword,
        scenario_noisy_english_map_restaurant_uses_precise_keyword,
        scenario_multi_step_marks_primary_draft_action,
        scenario_weather_direct_returns_artifact,
        scenario_map_weather_combo_returns_two_artifacts,
        scenario_route_request_returns_route_artifact,
        scenario_order_search_returns_result_artifact,
        scenario_order_search_empty_returns_action_card,
        scenario_content_search_returns_result_artifact,
        scenario_user_profile_returns_result_artifact,
        scenario_user_search_returns_result_artifact,
        scenario_execution_plan_describes_tool_path,
        scenario_execution_plan_surfaces_missing_slots,
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
