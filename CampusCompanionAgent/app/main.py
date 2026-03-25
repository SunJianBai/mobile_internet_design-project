"""FastAPI entry point for the Campus Companion Agent service."""

import json
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agent import chat, stream_chat, extract_memory
from app.config import AGENT_PORT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Campus Companion Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Request Models ====================


class ChatRequest(BaseModel):
    user_info: dict  # {"uid": int, "nickname": str}
    memories: list[dict] = []  # [{"category": str, "content": str}]
    history: list[dict] = []  # [{"role": str, "content": str}]
    message: str


class MemoryExtractionRequest(BaseModel):
    user_message: str
    assistant_reply: str


# ==================== Endpoints ====================


@app.get("/health")
async def health():
    return {"status": "ok", "service": "campus-companion-agent"}


@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """非流式对话"""
    try:
        result = await chat(
            user_info=req.user_info,
            memories=req.memories,
            history=req.history,
            user_message=req.message,
        )
        return {"code": 200, "data": result}
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/stream")
async def stream_endpoint(req: ChatRequest):
    """SSE 流式对话"""

    async def event_generator():
        async for event in stream_chat(
            user_info=req.user_info,
            memories=req.memories,
            history=req.history,
            user_message=req.message,
        ):
            yield {
                "event": event["event"],
                "data": event["data"],
            }

    return EventSourceResponse(event_generator())


@app.post("/extract-memory")
async def extract_memory_endpoint(req: MemoryExtractionRequest):
    """从对话提取记忆"""
    try:
        memories = await extract_memory(req.user_message, req.assistant_reply)
        return {"code": 200, "data": memories}
    except Exception as e:
        logger.error(f"Memory extraction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=AGENT_PORT, reload=True)
