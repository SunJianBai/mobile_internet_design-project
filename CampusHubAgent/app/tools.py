"""LangChain tools for order management — calls Java backend REST APIs."""

from langchain_core.tools import tool

from app.backend_client import api_get, api_post, api_put


# ==================== 订单基础工具 ====================


@tool
async def search_orders(
    activity_type: str = None,
    campus: str = None,
) -> str:
    """搜索当前可加入的约伴活动订单。

    Args:
        activity_type: 活动类型，可选值: BASKETBALL, BADMINTON, MEAL, STUDY, MOVIE, RUNNING, GAME, OTHER
        campus: 校区，可选值: LIANGXIANG, ZHONGGUANCUN, ZHUHAI, XISHAN, OTHER_CAMPUS
    """
    params = {"status": "PENDING", "page": 1, "size": 20}
    if activity_type:
        params["activityType"] = activity_type.upper()
    if campus:
        params["campus"] = campus.upper()

    result = await api_get("/api/v1/orders", user_id=0, params=params)
    data = result.get("data")
    if not data or (isinstance(data, dict) and not data.get("content")):
        return "暂时没有找到符合条件的约伴订单。"

    orders = data.get("content", []) if isinstance(data, dict) else data
    if not orders:
        return "暂时没有找到符合条件的约伴订单。"

    lines = [f"找到 {len(orders)} 个约伴订单：\n"]
    for o in orders[:10]:
        oid = o.get("oid") or o.get("id")
        lines.append(
            f"- **[订单#{oid}](/orders/{oid})** "
            f"{o.get('activityType', '')} | {o.get('campus', '')} | "
            f"{o.get('location', '')} | {o.get('startTime', '')} | "
            f"{o.get('currentPeople', 0)}/{o.get('maxPeople', 0)}人"
        )
    return "\n".join(lines)


@tool
async def create_order(
    user_id: int,
    activity_type: str,
    campus: str,
    location: str,
    start_time: str,
    gender_require: str = "ANY",
    max_people: int = 2,
    note: str = "",
) -> str:
    """创建一个新的约伴订单。调用前必须确认用户提供了所有必填信息。

    Args:
        user_id: 当前用户ID（系统自动提供）
        activity_type: 活动类型: BASKETBALL, BADMINTON, MEAL, STUDY, MOVIE, RUNNING, GAME, OTHER
        campus: 校区: LIANGXIANG, ZHONGGUANCUN, ZHUHAI, XISHAN, OTHER_CAMPUS
        location: 具体活动地点
        start_time: 活动开始时间，格式 yyyy-MM-dd HH:mm:ss
        gender_require: 性别要求: MALE, FEMALE, ANY（默认ANY）
        max_people: 最大参与人数（默认2）
        note: 备注信息
    """
    body = {
        "activityType": activity_type.upper(),
        "campus": campus.upper(),
        "location": location,
        "startTime": start_time,
        "genderRequire": gender_require.upper(),
        "maxPeople": max_people,
        "note": note or "",
    }
    result = await api_post("/api/v1/orders", user_id=user_id, json_body=body)
    if result.get("code") == 200:
        oid = result.get("data")
        return f"✅ 约伴订单创建成功！[查看订单详情](/orders/{oid})"
    return f"创建订单失败: {result.get('message', '未知错误')}"


@tool
async def get_my_orders(user_id: int) -> str:
    """查询当前用户自己发布的约伴订单。

    Args:
        user_id: 当前用户ID（系统自动提供）
    """
    result = await api_get("/api/v1/orders/my", user_id=user_id, params={"page": 1, "size": 20})
    data = result.get("data")
    orders = data.get("content", []) if isinstance(data, dict) else (data or [])
    if not orders:
        return "你还没有发布过任何约伴订单。"

    lines = [f"你共有 {len(orders)} 个订单：\n"]
    for o in orders[:10]:
        oid = o.get("oid") or o.get("id")
        lines.append(
            f"- **[订单#{oid}](/orders/{oid})** "
            f"{o.get('activityType', '')} | {o.get('status', '')} | "
            f"{o.get('startTime', '')} | {o.get('currentPeople', 0)}/{o.get('maxPeople', 0)}人"
        )
    return "\n".join(lines)


@tool
async def get_order_detail(order_id: int) -> str:
    """查看某个约伴订单的详细信息。

    Args:
        order_id: 订单ID
    """
    result = await api_get(f"/api/v1/orders/{order_id}", user_id=0)
    o = result.get("data")
    if not o:
        return f"未找到ID为 {order_id} 的订单。"

    oid = o.get("oid") or o.get("id") or order_id
    return (
        f"**订单 #{oid} 详情** [前往查看](/orders/{oid})\n\n"
        f"- 活动类型: {o.get('activityType', '')}\n"
        f"- 校区: {o.get('campus', '')}\n"
        f"- 地点: {o.get('location', '')}\n"
        f"- 时间: {o.get('startTime', '')}\n"
        f"- 性别要求: {o.get('genderRequire', '')}\n"
        f"- 人数: {o.get('currentPeople', 0)}/{o.get('maxPeople', 0)}\n"
        f"- 状态: {o.get('status', '')}\n"
        f"- 备注: {o.get('note', '无')}"
    )
