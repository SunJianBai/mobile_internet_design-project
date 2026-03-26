"""Utility tools — local datetime, etc."""

from datetime import datetime

from langchain_core.tools import tool


@tool
def get_current_datetime() -> str:
    """获取当前的日期和时间信息，包括年月日、星期、时分秒。"""
    now = datetime.now()
    weekday_map = {
        "Monday": "星期一", "Tuesday": "星期二", "Wednesday": "星期三",
        "Thursday": "星期四", "Friday": "星期五", "Saturday": "星期六", "Sunday": "星期日",
    }
    weekday = weekday_map.get(now.strftime("%A"), now.strftime("%A"))
    return (
        f"当前时间: {now.strftime('%Y年%m月%d日')} {weekday} "
        f"{now.strftime('%H:%M:%S')}"
    )


UTIL_TOOLS = [get_current_datetime]
