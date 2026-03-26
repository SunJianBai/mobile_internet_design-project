"""MCP client for Amap (高德地图) — ModelScope MCP SSE server.

MCP over SSE 协议需要完整握手:
1. GET /sse → 获取 messages endpoint + session_id
2. POST initialize → 握手
3. POST notifications/initialized → 确认
4. POST tools/call → 调用工具（通过 SSE 读取响应）

SSE 连接必须在整个会话期间保持打开。
"""

import json
import logging
import threading
import time
from typing import Optional

import httpx
from langchain_core.tools import tool

from app.config import AMAP_MCP_URL

logger = logging.getLogger(__name__)


class MCPSession:
    """管理与 MCP Server 的 SSE 会话。"""

    def __init__(self):
        self.messages_url: Optional[str] = None
        self._responses: dict = {}  # id -> response
        self._thread: Optional[threading.Thread] = None
        self._initialized = False
        self._post_client: Optional[httpx.Client] = None
        self._lock = threading.Lock()
        self._req_counter = 0  # 递增计数器，避免 ID 冲突
        self._reader_alive = False  # 标记 SSE reader 是否存活

    def _derive_base_url(self) -> str:
        """从 AMAP_MCP_URL 推导 server root URL。"""
        from urllib.parse import urlparse
        parsed = urlparse(AMAP_MCP_URL)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _ensure_connected(self):
        """确保 SSE 连接已建立并完成初始化握手。"""
        if self._initialized and self.messages_url and self._reader_alive:
            return

        with self._lock:
            if self._initialized and self.messages_url and self._reader_alive:
                return

            # 清理旧状态
            self._responses = {}
            self._initialized = False
            self._reader_alive = False
            if self._post_client:
                try:
                    self._post_client.close()
                except Exception:
                    pass

            # 启动新的 SSE 读取线程
            self.messages_url = None
            self._thread = threading.Thread(target=self._sse_reader, daemon=True)
            self._thread.start()

            # 等待 messages URL
            for _ in range(30):
                if self.messages_url:
                    break
                time.sleep(0.3)

            if not self.messages_url:
                raise RuntimeError("无法连接到地图 MCP Server")

            # 初始化握手
            self._post_client = httpx.Client(timeout=10)
            init_req = {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "campus-companion", "version": "1.0"},
                },
            }
            self._post_client.post(self.messages_url, json=init_req)

            # 等待 initialize 响应
            for _ in range(20):
                if 0 in self._responses:
                    break
                time.sleep(0.3)

            # 发送 initialized 通知
            self._post_client.post(
                self.messages_url,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            )
            time.sleep(0.5)
            self._initialized = True
            logger.info("MCP Session initialized: %s", self.messages_url)

    def _sse_reader(self):
        """后台线程：保持 SSE 连接，读取响应。"""
        self._reader_alive = True
        base_url = self._derive_base_url()
        try:
            with httpx.Client(timeout=300) as client:
                with client.stream("GET", AMAP_MCP_URL) as resp:
                    for line in resp.iter_lines():
                        if line.startswith("data:") and "/messages" in line:
                            rel_path = line[5:].strip()
                            self.messages_url = base_url + rel_path
                        elif line.startswith("data:") and "{" in line:
                            try:
                                obj = json.loads(line[5:].strip())
                                req_id = obj.get("id")
                                if req_id is not None:
                                    self._responses[req_id] = obj
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            logger.error("MCP SSE reader error: %s", e)
        finally:
            self._reader_alive = False
            self._initialized = False
            self.messages_url = None

    def _next_id(self) -> int:
        """生成唯一递增请求 ID。"""
        self._req_counter += 1
        return self._req_counter

    def call_tool(self, tool_name: str, arguments: dict, timeout: float = 15) -> str:
        """调用 MCP 工具并等待响应。"""
        try:
            self._ensure_connected()
        except Exception as e:
            return f"地图服务连接失败: {e}"

        req_id = self._next_id()
        rpc_request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        try:
            self._post_client.post(self.messages_url, json=rpc_request)
        except Exception as e:
            # session 过期，重置（下次调用自动重连）
            self._initialized = False
            self.messages_url = None
            return f"地图服务请求失败: {e}"

        # 等待响应
        start = time.time()
        while time.time() - start < timeout:
            if req_id in self._responses:
                resp = self._responses.pop(req_id)
                if "result" in resp:
                    content = resp["result"].get("content", [])
                    texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                    return "\n".join(texts) if texts else json.dumps(resp["result"], ensure_ascii=False)
                if "error" in resp:
                    return f"地图服务错误: {resp['error'].get('message', str(resp['error']))}"
            time.sleep(0.3)

        return "地图服务响应超时"


# 全局 MCP 会话
_mcp_session = MCPSession()


# ==================== LangChain 工具（对齐 MCP Server 工具名） ====================


@tool
def maps_text_search(keywords: str, city: str = "") -> str:
    """关键词搜索地点（POI），搜索相关的地点信息，返回地点名称、地址、经纬度坐标。

    Args:
        keywords: 搜索关键词，如"北京理工大学"、"星巴克"、"篮球场"
        city: 城市名称（可选），如"北京"
    """
    args = {"keywords": keywords}
    if city:
        args["city"] = city
    return _mcp_session.call_tool("maps_text_search", args)


@tool
def maps_around_search(location: str, keywords: str = "", radius: str = "1000") -> str:
    """周边搜索，根据坐标搜索半径范围内的地点。

    Args:
        location: 中心点经纬度，格式"经度,纬度"如"116.397,39.908"
        keywords: 搜索关键词（可选），如"餐厅"、"超市"
        radius: 搜索半径（米），默认1000
    """
    args = {"location": location}
    if keywords:
        args["keywords"] = keywords
    if radius:
        args["radius"] = radius
    return _mcp_session.call_tool("maps_around_search", args)


@tool
def maps_weather(city: str) -> str:
    """查询城市天气信息。

    Args:
        city: 城市名称或 adcode，如"北京"、"110000"
    """
    return _mcp_session.call_tool("maps_weather", {"city": city})


@tool
def maps_geo(address: str, city: str = "") -> str:
    """地理编码：将地址转换为经纬度坐标。

    Args:
        address: 结构化地址，如"北京市房山区良乡东路"
        city: 城市名称（可选）
    """
    args = {"address": address}
    if city:
        args["city"] = city
    return _mcp_session.call_tool("maps_geo", args)


@tool
def maps_direction_walking(origin: str, destination: str) -> str:
    """步行路线规划（100km以内）。

    Args:
        origin: 起点经纬度，格式"经度,纬度"
        destination: 终点经纬度，格式"经度,纬度"
    """
    return _mcp_session.call_tool("maps_direction_walking", {"origin": origin, "destination": destination})


@tool
def maps_direction_driving(origin: str, destination: str) -> str:
    """驾车路线规划。

    Args:
        origin: 起点经纬度，格式"经度,纬度"
        destination: 终点经纬度，格式"经度,纬度"
    """
    return _mcp_session.call_tool("maps_direction_driving", {"origin": origin, "destination": destination})


MCP_TOOLS = [
    maps_text_search,
    maps_around_search,
    maps_weather,
    maps_geo,
    maps_direction_walking,
    maps_direction_driving,
]
