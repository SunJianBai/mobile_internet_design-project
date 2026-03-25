from sqlalchemy import create_engine, text
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)


def execute_query(sql: str, params: dict = None) -> list[dict]:
    """执行查询并返回字典列表"""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]


def execute_update(sql: str, params: dict = None) -> int:
    """执行更新/插入并返回影响行数"""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        conn.commit()
        return result.rowcount
