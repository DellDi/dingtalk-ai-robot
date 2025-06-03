import sqlite3
from typing import Optional, Tuple

DB_PATH = "user_data.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_jira_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            jira_username TEXT NOT NULL,
            jira_password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn

def get_jira_account(user_id: str) -> Optional[Tuple[str, str]]:
    conn = get_conn()
    cursor = conn.execute("SELECT jira_username, jira_password FROM user_jira_account WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row if row else None

def save_jira_account(user_id: str, username: str, password: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO user_jira_account (user_id, jira_username, jira_password, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (user_id, username, password)
    )
    conn.commit()
    conn.close()
