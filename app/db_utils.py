import sqlite3
from typing import Optional, Tuple

DB_PATH = "user_data.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    # 主业务表
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_jira_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            jira_username TEXT NOT NULL,
            jira_password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # 字段注释元数据表
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS columns_comment (
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            comment TEXT,
            PRIMARY KEY (table_name, column_name)
        )
    """
    )

    # 初始化 user_jira_account 字段注释
    _register_column_comments(
        conn,
        "user_jira_account",
        {
            "id": "主键",
            "user_id": "钉钉用户 ID",
            "jira_username": "Jira 登录名",
            "jira_password": "Jira 密码 (建议加密)",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
    )

    return conn


def _register_column_comments(conn: sqlite3.Connection, table: str, comments: dict[str, str]) -> None:
    """将列注释写入元数据表 (INSERT OR REPLACE)。"""
    for col, com in comments.items():
        conn.execute(
            "INSERT OR REPLACE INTO columns_comment (table_name, column_name, comment) VALUES (?, ?, ?)",
            (table, col, com),
        )
    conn.commit()


def get_column_comment(table: str, column: str) -> Optional[str]:
    """读取单个列注释。"""
    conn = get_conn()
    cur = conn.execute(
        "SELECT comment FROM columns_comment WHERE table_name = ? AND column_name = ?",
        (table, column),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def get_table_comments(table: str) -> dict[str, str]:
    """读取整张表的列注释。"""
    conn = get_conn()
    cur = conn.execute(
        "SELECT column_name, comment FROM columns_comment WHERE table_name = ?",
        (table,),
    )
    result = {col: com for col, com in cur.fetchall()}
    conn.close()
    return result

def get_jira_account(user_id: str) -> Optional[Tuple[str, str]]:
    conn = get_conn()
    cursor = conn.execute(
        "SELECT jira_username, jira_password FROM user_jira_account WHERE user_id = ?", (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row if row else None


def save_jira_account(user_id: str, username: str, password: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO user_jira_account (user_id, jira_username, jira_password, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (user_id, username, password),
    )
    conn.commit()
    conn.close()
