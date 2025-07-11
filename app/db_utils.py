import sqlite3
from typing import Optional, Tuple, List, Dict, Any

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

    # 对话记录表
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            user_question TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            message_type TEXT DEFAULT 'text',
            response_time_ms INTEGER,
            agent_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # 为对话记录表创建索引以提高查询性能
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_conversation_records_conversation_id
        ON conversation_records(conversation_id)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_conversation_records_sender_id
        ON conversation_records(sender_id)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_conversation_records_created_at
        ON conversation_records(created_at)
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

    # 初始化 conversation_records 字段注释
    _register_column_comments(
        conn,
        "conversation_records",
        {
            "id": "主键",
            "conversation_id": "钉钉会话ID（群聊或单聊）",
            "sender_id": "发送者钉钉用户ID",
            "user_question": "用户提问内容",
            "ai_response": "智能体回复内容",
            "message_type": "消息类型（text/markdown/card等）",
            "response_time_ms": "响应时间（毫秒）",
            "agent_type": "处理的智能体类型",
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


def save_conversation_record(
    conversation_id: str,
    sender_id: str,
    user_question: str,
    ai_response: str,
    message_type: str = "text",
    response_time_ms: Optional[int] = None,
    agent_type: Optional[str] = None,
) -> int:
    """
    保存对话记录到数据库

    Args:
        conversation_id: 钉钉会话ID
        sender_id: 发送者钉钉用户ID
        user_question: 用户提问内容
        ai_response: 智能体回复内容
        message_type: 消息类型，默认为text
        response_time_ms: 响应时间（毫秒）
        agent_type: 处理的智能体类型

    Returns:
        int: 插入记录的ID
    """
    conn = get_conn()
    cursor = conn.execute(
        """
        INSERT INTO conversation_records
        (conversation_id, sender_id, user_question, ai_response, message_type, response_time_ms, agent_type, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (conversation_id, sender_id, user_question, ai_response, message_type, response_time_ms, agent_type),
    )
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id


def get_conversation_history(
    conversation_id: Optional[str] = None,
    sender_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Tuple]:
    """
    获取对话历史记录

    Args:
        conversation_id: 会话ID，可选
        sender_id: 发送者ID，可选
        limit: 返回记录数量限制
        offset: 偏移量

    Returns:
        List[Tuple]: 对话记录列表
    """
    conn = get_conn()

    # 构建查询条件
    where_conditions = []
    params = []

    if conversation_id:
        where_conditions.append("conversation_id = ?")
        params.append(conversation_id)

    if sender_id:
        where_conditions.append("sender_id = ?")
        params.append(sender_id)

    where_clause = ""
    if where_conditions:
        where_clause = "WHERE " + " AND ".join(where_conditions)

    # 添加分页参数
    params.extend([limit, offset])

    query = f"""
        SELECT id, conversation_id, sender_id, user_question, ai_response,
               message_type, response_time_ms, agent_type, created_at, updated_at
        FROM conversation_records
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_conversation_stats(
    conversation_id: Optional[str] = None,
    sender_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取对话统计信息

    Args:
        conversation_id: 会话ID，可选
        sender_id: 发送者ID，可选
        start_date: 开始日期，格式：YYYY-MM-DD
        end_date: 结束日期，格式：YYYY-MM-DD

    Returns:
        Dict[str, Any]: 统计信息
    """
    conn = get_conn()

    # 构建查询条件
    where_conditions = []
    params = []

    if conversation_id:
        where_conditions.append("conversation_id = ?")
        params.append(conversation_id)

    if sender_id:
        where_conditions.append("sender_id = ?")
        params.append(sender_id)

    if start_date:
        where_conditions.append("DATE(created_at) >= ?")
        params.append(start_date)

    if end_date:
        where_conditions.append("DATE(created_at) <= ?")
        params.append(end_date)

    where_clause = ""
    if where_conditions:
        where_clause = "WHERE " + " AND ".join(where_conditions)

    # 获取基本统计信息
    stats_query = f"""
        SELECT
            COUNT(*) as total_conversations,
            COUNT(DISTINCT sender_id) as unique_users,
            COUNT(DISTINCT conversation_id) as unique_conversations,
            AVG(response_time_ms) as avg_response_time_ms,
            MIN(created_at) as first_conversation,
            MAX(created_at) as last_conversation
        FROM conversation_records
        {where_clause}
    """

    cursor = conn.execute(stats_query, params)
    stats = cursor.fetchone()

    # 获取智能体类型分布
    agent_stats_query = f"""
        SELECT agent_type, COUNT(*) as count
        FROM conversation_records
        {where_clause}
        GROUP BY agent_type
        ORDER BY count DESC
    """

    cursor = conn.execute(agent_stats_query, params)
    agent_distribution = cursor.fetchall()

    # 获取消息类型分布
    message_type_query = f"""
        SELECT message_type, COUNT(*) as count
        FROM conversation_records
        {where_clause}
        GROUP BY message_type
        ORDER BY count DESC
    """

    cursor = conn.execute(message_type_query, params)
    message_type_distribution = cursor.fetchall()

    conn.close()

    return {
        "total_conversations": stats[0] if stats else 0,
        "unique_users": stats[1] if stats else 0,
        "unique_conversations": stats[2] if stats else 0,
        "avg_response_time_ms": stats[3] if stats else None,
        "first_conversation": stats[4] if stats else None,
        "last_conversation": stats[5] if stats else None,
        "agent_distribution": [{"agent_type": row[0], "count": row[1]} for row in agent_distribution],
        "message_type_distribution": [{"message_type": row[0], "count": row[1]} for row in message_type_distribution],
    }
