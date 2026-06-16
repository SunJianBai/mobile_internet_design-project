"""User tools — profile lookup, search."""

from langchain_core.tools import tool

from app.backend_client import api_get


@tool
async def get_user_profile(user_id: int) -> str:
    """查看某个用户的个人资料。

    Args:
        user_id: 要查看的用户ID
    """
    result = await api_get(f"/api/v1/users/{user_id}", user_id=user_id)
    u = result.get("data")
    if not u:
        return f"未找到ID为 {user_id} 的用户。"

    return (
        f"**用户资料** [查看主页](/user/profile)\n\n"
        f"- 昵称: {u.get('nickname', '未知')}\n"
        f"- 签名: {u.get('signature', '无')}\n"
        f"- 邮箱: {u.get('email', '未知')}"
    )


@tool
async def search_users(keyword: str) -> str:
    """搜索用户（按昵称或学号）。

    Args:
        keyword: 搜索关键词
    """
    result = await api_get("/api/v1/users/search", user_id=0, params={"keyword": keyword, "page": 1, "size": 10})
    data = result.get("data")
    users = data.get("content", []) if isinstance(data, dict) else (data or [])
    if not users:
        return f"没有找到包含「{keyword}」的用户。"

    lines = [f"找到 {len(users)} 个用户：\n"]
    for u in users[:8]:
        uid = u.get("uid") or u.get("id")
        lines.append(f"- {u.get('nickname', '未知')} (ID: {uid})")
    return "\n".join(lines)


USER_TOOLS = [get_user_profile, search_users]
