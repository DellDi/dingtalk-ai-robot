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

    # 周报日志表
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS weekly_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            week_start_date DATE NOT NULL,
            week_end_date DATE NOT NULL,
            log_content TEXT NOT NULL,
            summary_content TEXT,
            dingtalk_report_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

    # 初始化 weekly_logs 字段注释
    _register_column_comments(
        conn,
        "weekly_logs",
        {
            "id": "主键",
            "user_id": "钉钉用户 ID",
            "week_start_date": "周开始日期",
            "week_end_date": "周结束日期",
            "log_content": "原始日志内容",
            "summary_content": "AI总结后的内容",
            "dingtalk_report_id": "钉钉日报ID",
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


# ========== 周报相关数据库操作 ==========

def get_first_user_id() -> Optional[str]:
    """获取数据库中第一个用户ID"""
    conn = get_conn()
    cursor = conn.execute("SELECT user_id FROM user_jira_account ORDER BY id LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def save_weekly_log(user_id: str, week_start: str, week_end: str, log_content: str, 
                   summary_content: str = None, dingtalk_report_id: str = None) -> int:
    """保存周报日志"""
    conn = get_conn()
    cursor = conn.execute(
        """
        INSERT INTO weekly_logs 
        (user_id, week_start_date, week_end_date, log_content, summary_content, dingtalk_report_id) 
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, week_start, week_end, log_content, summary_content, dingtalk_report_id)
    )
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def update_weekly_log_summary(log_id: int, summary_content: str):
    """更新周报总结内容"""
    conn = get_conn()
    conn.execute(
        "UPDATE weekly_logs SET summary_content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (summary_content, log_id)
    )
    conn.commit()
    conn.close()


def update_weekly_log_dingtalk_id(log_id: int, dingtalk_report_id: str):
    """更新钉钉日报ID"""
    conn = get_conn()
    conn.execute(
        "UPDATE weekly_logs SET dingtalk_report_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (dingtalk_report_id, log_id)
    )
    conn.commit()
    conn.close()


def get_weekly_logs_by_date_range(user_id: str, start_date: str, end_date: str) -> list:
    """根据日期范围获取周报日志"""
    conn = get_conn()
    cursor = conn.execute(
        """
        SELECT id, user_id, week_start_date, week_end_date, log_content, 
               summary_content, dingtalk_report_id, created_at, updated_at
        FROM weekly_logs 
        WHERE user_id = ? AND week_start_date >= ? AND week_end_date <= ?
        ORDER BY week_start_date
        """,
        (user_id, start_date, end_date)
    )
    results = cursor.fetchall()
    conn.close()
    return results


def get_latest_weekly_log(user_id: str) -> Optional[Tuple]:
    """获取用户最新的周报日志"""
    conn = get_conn()
    cursor = conn.execute(
        """
        SELECT id, user_id, week_start_date, week_end_date, log_content, 
               summary_content, dingtalk_report_id, created_at, updated_at
        FROM weekly_logs 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 1
        """,
        (user_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result
