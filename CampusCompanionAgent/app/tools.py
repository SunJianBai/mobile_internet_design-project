"""LangChain tools for campus companion agent."""

from datetime import datetime
from typing import Optional

from langchain_core.tools import tool

from app.database import execute_query, execute_update

# ==================== 枚举映射 ====================

ACTIVITY_LABELS = {
    "BASKETBALL": "篮球", "BADMINTON": "羽毛球", "MEAL": "约饭",
    "STUDY": "自习", "MOVIE": "电影", "RUNNING": "跑步",
    "GAME": "游戏", "OTHER": "其他",
}

CAMPUS_LABELS = {
    "LIANGXIANG": "良乡校区", "ZHONGGUANCUN": "中关村校区",
    "ZHUHAI": "珠海校区", "XISHAN": "西山校区", "OTHER_CAMPUS": "其他校区",
}

GENDER_LABELS = {
    "MALE": "仅限男生", "FEMALE": "仅限女生", "ANY": "不限",
}

STATUS_LABELS = {
    "PENDING": "待匹配", "MATCHED": "已匹配", "COMPLETED": "已完成",
    "CANCELLED": "已取消",
}


def _format_order(o: dict) -> str:
    """把一条订单字典格式化为可读文本"""
    lines = [
        f"📋 订单ID: {o['oid']}",
        f"   活动类型: {ACTIVITY_LABELS.get(o.get('activity_type', ''), o.get('activity_type', ''))}",
        f"   校区: {CAMPUS_LABELS.get(o.get('campus', ''), o.get('campus', ''))}",
        f"   地点: {o.get('location', '')}",
        f"   开始时间: {o.get('start_time', '')}",
        f"   性别要求: {GENDER_LABELS.get(o.get('gender_require', ''), o.get('gender_require', ''))}",
        f"   人数: {o.get('current_people', 0)}/{o.get('max_people', 0)}",
        f"   状态: {STATUS_LABELS.get(o.get('status', ''), o.get('status', ''))}",
    ]
    if o.get("note"):
        lines.append(f"   备注: {o['note']}")
    return "\n".join(lines)


# ==================== 工具定义 ====================


@tool
def search_orders(
    activity_type: Optional[str] = None,
    campus: Optional[str] = None,
) -> str:
    """搜索当前可加入的约伴活动订单。

    Args:
        activity_type: 活动类型，可选值: BASKETBALL, BADMINTON, MEAL, STUDY, MOVIE, RUNNING, GAME, OTHER
        campus: 校区，可选值: LIANGXIANG, ZHONGGUANCUN, ZHUHAI, XISHAN, OTHER_CAMPUS
    """
    sql = "SELECT * FROM orders WHERE status = 'PENDING' AND start_time > NOW()"
    params = {}

    if activity_type:
        sql += " AND activity_type = :activity_type"
        params["activity_type"] = activity_type.upper()
    if campus:
        sql += " AND campus = :campus"
        params["campus"] = campus.upper()

    sql += " ORDER BY start_time ASC LIMIT 20"
    rows = execute_query(sql, params)

    if not rows:
        return "暂时没有找到符合条件的约伴订单。"

    result = f"找到 {len(rows)} 个约伴订单：\n\n"
    result += "\n\n".join(_format_order(r) for r in rows)
    return result


@tool
def create_order(
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
        start_time: 活动开始时间，格式 YYYY-MM-DD HH:MM:SS
        gender_require: 性别要求: MALE, FEMALE, ANY（默认ANY）
        max_people: 最大参与人数（默认2）
        note: 备注信息
    """
    sql = """
        INSERT INTO orders (uid, activity_type, campus, location, start_time,
                           gender_require, max_people, current_people, status, note,
                           created_at, updated_at)
        VALUES (:uid, :activity_type, :campus, :location, :start_time,
                :gender_require, :max_people, 1, 'PENDING', :note, NOW(), NOW())
    """
    params = {
        "uid": user_id,
        "activity_type": activity_type.upper(),
        "campus": campus.upper(),
        "location": location,
        "start_time": start_time,
        "gender_require": gender_require.upper(),
        "max_people": max_people,
        "note": note or "",
    }
    execute_update(sql, params)
    return f"✅ 约伴订单创建成功！活动类型: {ACTIVITY_LABELS.get(activity_type.upper(), activity_type)}，地点: {location}，时间: {start_time}"


@tool
def get_my_orders(user_id: int) -> str:
    """查询当前用户的所有约伴订单。

    Args:
        user_id: 当前用户ID（系统自动提供）
    """
    sql = "SELECT * FROM orders WHERE uid = :uid ORDER BY created_at DESC LIMIT 20"
    rows = execute_query(sql, {"uid": user_id})

    if not rows:
        return "你还没有发布过任何约伴订单。"

    result = f"你共有 {len(rows)} 个订单：\n\n"
    result += "\n\n".join(_format_order(r) for r in rows)
    return result


@tool
def get_order_detail(order_id: int) -> str:
    """查看某个约伴订单的详细信息。

    Args:
        order_id: 订单ID
    """
    rows = execute_query("SELECT * FROM orders WHERE oid = :oid", {"oid": order_id})
    if not rows:
        return f"未找到ID为 {order_id} 的订单。"
    return _format_order(rows[0])


# 所有可用工具列表
ALL_TOOLS = [search_orders, create_order, get_my_orders, get_order_detail]
