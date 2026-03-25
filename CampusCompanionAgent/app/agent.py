"""LangChain Agent core - campus companion agent with tool calling."""

import json
import logging
from typing import AsyncIterator

from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langgraph.prebuilt import create_react_agent

from app.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, SILICONFLOW_MODEL
from app.tools import ALL_TOOLS
from app.prompts import build_system_prompt, MEMORY_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


def _get_llm(streaming: bool = False) -> ChatOpenAI:
    """创建 SiliconFlow LLM 实例（OpenAI 兼容接口）"""
    return ChatOpenAI(
        api_key=SILICONFLOW_API_KEY,
        base_url=SILICONFLOW_BASE_URL,
        model=SILICONFLOW_MODEL,
        temperature=0.7,
        streaming=streaming,
        max_tokens=2048,
        extra_body={"enable_thinking": False},  # 禁用 thinking 模式（Qwen3 系列）
    )


def _build_message_history(history: list[dict]) -> list:
    """将前端传来的历史消息转为 LangChain 消息对象"""
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


def create_agent():
    """创建 LangGraph ReAct Agent"""
    llm = _get_llm(streaming=False)
    agent = create_react_agent(llm, ALL_TOOLS)
    return agent


def create_streaming_agent():
    """创建支持流式输出的 Agent"""
    llm = _get_llm(streaming=True)
    agent = create_react_agent(llm, ALL_TOOLS)
    return agent


async def chat(
    user_info: dict,
    memories: list[dict],
    history: list[dict],
    user_message: str,
) -> dict:
    """非流式 Agent 调用。

    Returns:
        {"reply": str, "tool_calls": list[dict]}
    """
    system_prompt = build_system_prompt(user_info, memories)
    messages = _build_message_history(history)
    messages.append(HumanMessage(content=user_message))

    agent = create_agent()

    result = await agent.ainvoke({
        "messages": [SystemMessage(content=system_prompt)] + messages,
    })

    # 提取最终回复和工具调用记录
    tool_calls_log = []
    final_reply = ""

    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_log.append({
                    "name": tc["name"],
                    "args": tc["args"],
                })
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            final_reply = msg.content

    return {"reply": final_reply, "tool_calls": tool_calls_log}


async def stream_chat(
    user_info: dict,
    memories: list[dict],
    history: list[dict],
    user_message: str,
) -> AsyncIterator[dict]:
    """流式 Agent 调用，yield SSE 事件。

    Yields:
        {"event": "delta"|"tool_call"|"done"|"error", "data": str}
    """
    system_prompt = build_system_prompt(user_info, memories)
    messages = _build_message_history(history)
    messages.append(HumanMessage(content=user_message))

    agent = create_streaming_agent()

    try:
        async for event in agent.astream_events(
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
                yield {"event": "tool_call", "data": f"正在调用工具: {tool_name}"}

            elif kind == "on_tool_end":
                pass  # 工具结果由 agent 内部处理

        yield {"event": "done", "data": ""}

    except Exception as e:
        logger.error(f"Stream error: {e}", exc_info=True)
        yield {"event": "error", "data": str(e)}


async def extract_memory(user_message: str, assistant_reply: str) -> list[dict]:
    """从对话中提取用户记忆。

    Returns:
        [{"category": str, "content": str}, ...]
    """
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

        # 尝试从回复中提取 JSON
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
        logger.warning(f"Memory extraction failed: {e}")

    return []
