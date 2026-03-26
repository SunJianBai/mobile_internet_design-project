"""Content/social tools — posts, comments, likes."""

from langchain_core.tools import tool

from app.backend_client import api_get, api_post


@tool
async def search_contents(keyword: str = "") -> str:
    """搜索校园动态/帖子。

    Args:
        keyword: 搜索关键词（可选，不填则浏览最新动态）
    """
    params = {"page": 1, "size": 10}
    if keyword:
        params["keyword"] = keyword

    path = "/api/v1/contents/search" if keyword else "/api/v1/contents"
    result = await api_get(path, user_id=0, params=params)
    data = result.get("data")
    items = data.get("content", []) if isinstance(data, dict) else (data or [])
    if not items:
        return "没有找到相关动态。"

    lines = [f"找到 {len(items)} 条动态：\n"]
    for c in items[:8]:
        cid = c.get("pid") or c.get("id")
        text = (c.get("content") or "")[:60]
        if len(c.get("content", "")) > 60:
            text += "..."
        user = c.get("user", {})
        lines.append(
            f"- **[动态#{cid}](/contents/{cid})** "
            f"by {user.get('nickname', '匿名')} — {text}"
        )
    return "\n".join(lines)


@tool
async def get_content_detail(content_id: int) -> str:
    """查看某条动态/帖子的详细内容。

    Args:
        content_id: 动态ID
    """
    result = await api_get(f"/api/v1/contents/{content_id}", user_id=0)
    c = result.get("data")
    if not c:
        return f"未找到ID为 {content_id} 的动态。"

    cid = c.get("pid") or c.get("id") or content_id
    user = c.get("user", {})
    return (
        f"**动态 #{cid}** [前往查看](/contents/{cid})\n\n"
        f"- 作者: {user.get('nickname', '匿名')}\n"
        f"- 内容: {c.get('content', '')}\n"
        f"- 发布时间: {c.get('createdAt', '')}\n"
        f"- 媒体类型: {c.get('hasMedia', 'TEXT_ONLY')}"
    )


@tool
async def create_comment(user_id: int, content_id: int, comment_text: str) -> str:
    """在某条动态下发表评论。

    Args:
        user_id: 当前用户ID（系统自动提供）
        content_id: 要评论的动态ID
        comment_text: 评论内容
    """
    body = {"content": comment_text}
    result = await api_post(f"/api/v1/contents/{content_id}/comments", user_id=user_id, json_body=body)
    if result.get("code") == 200:
        return f"✅ 评论发表成功！[查看动态](/contents/{content_id})"
    return f"评论失败: {result.get('message', '未知错误')}"


@tool
async def like_content(user_id: int, content_id: int) -> str:
    """给某条动态点赞或取消点赞。

    Args:
        user_id: 当前用户ID（系统自动提供）
        content_id: 要点赞的动态ID
    """
    result = await api_post(f"/api/v1/contents/{content_id}/like", user_id=user_id)
    if result.get("code") == 200:
        return f"✅ 操作成功！[查看动态](/contents/{content_id})"
    return f"操作失败: {result.get('message', '未知错误')}"


CONTENT_TOOLS = [search_contents, get_content_detail, create_comment, like_content]
