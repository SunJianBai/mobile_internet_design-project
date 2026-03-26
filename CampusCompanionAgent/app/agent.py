"""Multi-agent architecture: 主Agent + 子Agent-as-Tool (模式B).

主Agent 通过 ReAct 循环调用 3 个子Agent（订单/社交/地图天气），
每个子Agent 内部又是一个带原子工具的 ReAct Agent。
"""

import json
import logging
from typing import AsyncIterator

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from app.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, SILICONFLOW_MODEL
from app.tools import search_orders, create_order, get_my_orders, get_order_detail
from app.tools_order import ORDER_EXTRA_TOOLS
from app.tools_content import CONTENT_TOOLS
from app.tools_user import USER_TOOLS
from app.mcp_tools import MCP_TOOLS
from app.tools_utils import UTIL_TOOLS
from app.prompts import (
    build_main_agent_prompt,
    ORDER_AGENT_PROMPT,
    SOCIAL_AGENT_PROMPT,
    MAP_AGENT_PROMPT,
    MEMORY_EXTRACTION_PROMPT,
)

logger = logging.getLogger(__name__)

# ==================== 工具分组 ====================

ORDER_TOOLS = [search_orders, create_order, get_my_orders, get_order_detail, *ORDER_EXTRA_TOOLS]
SOCIAL_TOOLS = [*CONTENT_TOOLS, *USER_TOOLS]
MAP_TOOLS = [*MCP_TOOLS, *UTIL_TOOLS]


# ==================== LLM 工厂 ====================

def _get_llm(streaming: bool = False, temperature: float = 0.7, max_tokens: int = 2048) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=SILICONFLOW_API_KEY,
        base_url=SILICONFLOW_BASE_URL,
        model=SILICONFLOW_MODEL,
        temperature=temperature,
        streaming=streaming,
        max_tokens=max_tokens,
        extra_body={"enable_thinking": False},
    )


# ==================== 子 Agent 执行器 ====================

async def _run_sub_agent(system_prompt: str, tools: list, task: str) -> str:
    """运行一个子 Agent，返回其最终回复文本。"""
    llm = _get_llm(streaming=False)
    agent = create_react_agent(llm, tools)

    try:
        result = await agent.ainvoke({
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=task),
            ],
        })

        # 提取最终 AI 回复
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                return msg.content

        return "子Agent 未返回有效结果。"
    except Exception as e:
        logger.error("Sub-agent error: %s", e, exc_info=True)
        return f"子Agent 执行出错: {str(e)}"


# ==================== 子 Agent 包装为 LangChain 工具 ====================

@tool
async def call_order_agent(task: str) -> str:
    """调用订单专家完成订单相关任务。如：搜索约伴活动、创建订单、查看订单、申请加入、接受申请等。

    Args:
        task: 具体任务描述，需包含完整的参数信息。如"搜索良乡校区的篮球约伴活动"、"为用户ID=1创建篮球订单，良乡校区体育馆，2026-03-26 15:00:00"
    """
    return await _run_sub_agent(ORDER_AGENT_PROMPT, ORDER_TOOLS, task)


@tool
async def call_social_agent(task: str) -> str:
    """调用社交专家完成校园动态相关任务。如：搜索动态、查看帖子、发评论、点赞、搜索用户等。

    Args:
        task: 具体任务描述。如"搜索关于篮球的动态"、"给动态#12点赞，用户ID=1"
    """
    return await _run_sub_agent(SOCIAL_AGENT_PROMPT, SOCIAL_TOOLS, task)


@tool
async def call_map_agent(task: str) -> str:
    """调用地图天气专家完成位置和天气相关任务。如：搜索地点、查附近、查天气、查路线等。

    Args:
        task: 具体任务描述。如"搜索北京理工大学良乡校区的位置"、"查询北京今天的天气"
    """
    return await _run_sub_agent(MAP_AGENT_PROMPT, MAP_TOOLS, task)


# 主 Agent 的工具列表（3 个子 Agent）
MAIN_AGENT_TOOLS = [call_order_agent, call_social_agent, call_map_agent]


# ==================== 消息历史构建 ====================

def _build_message_history(history: list) -> list:
    messages = []
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


# ==================== 对外接口 ====================

async def chat(
    user_info: dict,
    memories: list,
    history: list,
    user_message: str,
) -> dict:
    """非流式多 Agent 调用。"""
    system_prompt = build_main_agent_prompt(user_info, memories)
    messages = _build_message_history(history)
    messages.append(HumanMessage(content=user_message))

    llm = _get_llm(streaming=False)
    main_agent = create_react_agent(llm, MAIN_AGENT_TOOLS)

    result = await main_agent.ainvoke({
        "messages": [SystemMessage(content=system_prompt)] + messages,
    })

    tool_calls_log = []
    final_reply = ""

    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_log.append({"name": tc["name"], "args": tc["args"]})
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            final_reply = msg.content

    return {"reply": final_reply, "tool_calls": tool_calls_log}


async def stream_chat(
    user_info: dict,
    memories: list,
    history: list,
    user_message: str,
) -> AsyncIterator[dict]:
    """流式多 Agent 调用，yield SSE 事件。"""
    system_prompt = build_main_agent_prompt(user_info, memories)
    messages = _build_message_history(history)
    messages.append(HumanMessage(content=user_message))

    llm = _get_llm(streaming=True)
    main_agent = create_react_agent(llm, MAIN_AGENT_TOOLS)

    try:
        async for event in main_agent.astream_events(
            {"messages": [SystemMessage(content=system_prompt)] + messages},
            version="v2",
        ):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield {"event": "delta", "data": chunk.content}

            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                label_map = {
                    "call_order_agent": "📋 订单专家处理中...",
                    "call_social_agent": "📝 社交专家处理中...",
                    "call_map_agent": "🗺️ 地图专家处理中...",
                }
                label = label_map.get(tool_name, f"调用: {tool_name}")
                yield {"event": "tool_call", "data": label}

        yield {"event": "done", "data": ""}

    except Exception as e:
        logger.error("Stream error: %s", e, exc_info=True)
        yield {"event": "error", "data": str(e)}


async def extract_memory(user_message: str, assistant_reply: str) -> list:
    """从对话中提取用户记忆。"""
    llm = _get_llm(streaming=False)
    prompt = MEMORY_EXTRACTION_PROMPT.format(
        user_message=user_message,
        assistant_reply=assistant_reply,
    )

    try:
        result = await llm.ainvoke([HumanMessage(content=prompt)])
        text = result.content.strip()

        if text.lower() == "none" or not text:
            return []

        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [
                m for m in parsed
                if isinstance(m, dict) and "category" in m and "content" in m
            ]
    except Exception as e:
        logger.warning("Memory extraction failed: %s", e)

    return []
