import os
from dotenv import load_dotenv

load_dotenv()

# LLM
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
SILICONFLOW_MODEL = os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen3-32B")

# Java 后端
JAVA_BACKEND_URL = os.getenv("JAVA_BACKEND_URL", "http://localhost:8080")

# 高德 MCP Server
AMAP_MCP_URL = os.getenv("AMAP_MCP_URL", "https://mcp.api-inference.modelscope.net/06e5f888e0a64b/sse")

# Service
AGENT_PORT = int(os.getenv("AGENT_PORT", "5001"))
