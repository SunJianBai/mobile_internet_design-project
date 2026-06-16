"""Extended order tools — apply, accept, complete."""

from langchain_core.tools import tool

from app.backend_client import api_get, api_post, api_put


@tool
async def apply_to_order(user_id: int, order_id: int, message: str = "") -> str:
    """申请加入一个约伴订单。

    Args:
        user_id: 当前用户ID（系统自动提供）
        order_id: 要申请加入的订单ID
        message: 申请留言（可选）
    """
    body = {"message": message} if message else {}
    result = await api_post(f"/api/v1/orders/{order_id}/apply", user_id=user_id, json_body=body)
    if result.get("code") == 200:
        return f"✅ 已成功申请加入订单 #{order_id}，等待发布者审核。"
    return f"申请失败: {result.get('message', '未知错误')}"


@tool
async def get_order_applications(user_id: int, order_id: int) -> str:
    """查看某个订单收到的申请列表（仅订单发布者可用）。

    Args:
        user_id: 当前用户ID（系统自动提供）
        order_id: 订单ID
    """
    result = await api_get(f"/api/v1/orders/{order_id}/applications", user_id=user_id)
    data = result.get("data", [])
    if not data:
        return f"订单 #{order_id} 暂无申请。"

    apps = data if isinstance(data, list) else data.get("content", [])
    lines = [f"订单 #{order_id} 共有 {len(apps)} 个申请：\n"]
    for a in apps:
        user = a.get("user", {})
        lines.append(
            f"- 申请ID: {a.get('apid')} | "
            f"用户: {user.get('nickname', '未知')} | "
            f"状态: {a.get('status', '')}"
        )
    return "\n".join(lines)


@tool
async def accept_applicant(user_id: int, order_id: int, accepter_id: int) -> str:
    """接受某个用户的申请，让其加入订单（仅订单发布者可用）。

    Args:
        user_id: 当前用户ID（系统自动提供）
        order_id: 订单ID
        accepter_id: 要接受的申请者的用户ID
    """
    body = {"accepterId": accepter_id}
    result = await api_post(f"/api/v1/orders/{order_id}/accept", user_id=user_id, json_body=body)
    if result.get("code") == 200:
        return f"✅ 已接受用户加入订单 #{order_id}。"
    return f"接受失败: {result.get('message', '未知错误')}"


@tool
async def complete_order(user_id: int, order_id: int) -> str:
    """将订单标记为已完成。

    Args:
        user_id: 当前用户ID（系统自动提供）
        order_id: 订单ID
    """
    result = await api_put(f"/api/v1/orders/{order_id}/complete", user_id=user_id)
    if result.get("code") == 200:
        return f"✅ 订单 #{order_id} 已标记为完成。"
    return f"操作失败: {result.get('message', '未知错误')}"


ORDER_EXTRA_TOOLS = [apply_to_order, get_order_applications, accept_applicant, complete_order]
