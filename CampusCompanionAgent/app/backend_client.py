"""HTTP client for calling Java backend REST APIs."""

import logging
from typing import Optional

import httpx

from app.config import JAVA_BACKEND_URL

logger = logging.getLogger(__name__)

# 复用连接池的全局 client
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=JAVA_BACKEND_URL,
            timeout=30.0,
        )
    return _client


async def api_get(path: str, user_id: int, params: dict = None) -> dict:
    """GET 请求 Java 后端"""
    client = _get_client()
    try:
        resp = await client.get(
            path,
            params=params,
            headers={"X-User-Id": str(user_id)},
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Java API %s returned %s: %s", path, e.response.status_code, e.response.text[:200])
        return {"code": e.response.status_code, "message": e.response.text[:200]}
    except Exception as e:
        logger.error("Java API call failed: %s %s", path, e)
        return {"code": 500, "message": str(e)}


async def api_post(path: str, user_id: int, json_body: dict = None) -> dict:
    """POST 请求 Java 后端"""
    client = _get_client()
    try:
        resp = await client.post(
            path,
            json=json_body or {},
            headers={"X-User-Id": str(user_id)},
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Java API %s returned %s: %s", path, e.response.status_code, e.response.text[:200])
        return {"code": e.response.status_code, "message": e.response.text[:200]}
    except Exception as e:
        logger.error("Java API call failed: %s %s", path, e)
        return {"code": 500, "message": str(e)}


async def api_put(path: str, user_id: int, json_body: dict = None) -> dict:
    """PUT 请求 Java 后端"""
    client = _get_client()
    try:
        resp = await client.put(
            path,
            json=json_body or {},
            headers={"X-User-Id": str(user_id)},
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Java API %s returned %s: %s", path, e.response.status_code, e.response.text[:200])
        return {"code": e.response.status_code, "message": e.response.text[:200]}
    except Exception as e:
        logger.error("Java API call failed: %s %s", path, e)
        return {"code": 500, "message": str(e)}


async def api_delete(path: str, user_id: int) -> dict:
    """DELETE 请求 Java 后端"""
    client = _get_client()
    try:
        resp = await client.delete(
            path,
            headers={"X-User-Id": str(user_id)},
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Java API %s returned %s: %s", path, e.response.status_code, e.response.text[:200])
        return {"code": e.response.status_code, "message": e.response.text[:200]}
    except Exception as e:
        logger.error("Java API call failed: %s %s", path, e)
        return {"code": 500, "message": str(e)}
