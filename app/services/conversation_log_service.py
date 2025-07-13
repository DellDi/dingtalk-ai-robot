#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对话记录服务模块，整合数据库、AI智能体和钉钉API
提供对话记录的查询、统计、清理等功能
"""


import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from loguru import logger

from app.db_utils import (
    get_conn,
    save_conversation_record,
    get_conversation_history,
    get_conversation_stats
)


class ConversationLogService:
    """对话记录服务类"""

    @staticmethod
    async def save_record(
        conversation_id: str,
        sender_id: str,
        user_question: str,
        ai_response: str,
        message_type: str = "text",
        response_time_ms: Optional[int] = None,
        agent_type: Optional[str] = None,
    ) -> int:
        """异步保存对话记录

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
        try:
            # 使用线程池执行数据库操作
            record_id = await asyncio.to_thread(
                save_conversation_record,
                conversation_id,
                sender_id,
                user_question,
                ai_response,
                message_type,
                response_time_ms,
                agent_type
            )
            logger.debug(f"对话记录保存成功: ID={record_id}")
            return record_id
        except Exception as e:
            logger.error(f"保存对话记录失败: {e}")
            return -1

    @staticmethod
    async def get_history(
        conversation_id: Optional[str] = None,
        sender_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """异步获取对话历史记录

        Args:
            conversation_id: 会话ID，可选
            sender_id: 发送者ID，可选
            limit: 返回记录数量限制
            offset: 偏移量

        Returns:
            List[Dict[str, Any]]: 对话记录列表
        """
        try:
            # 使用线程池执行数据库操作
            history = await asyncio.to_thread(
                get_conversation_history,
                conversation_id,
                sender_id,
                limit,
                offset
            )

            # 转换为字典列表格式
            result = []
            for record in history:
                result.append({
                    "id": record[0],
                    "conversation_id": record[1],
                    "sender_id": record[2],
                    "user_question": record[3],
                    "ai_response": record[4],
                    "message_type": record[5],
                    "response_time_ms": record[6],
                    "agent_type": record[7],
                    "created_at": record[8],
                    "updated_at": record[9]
                })

            return result
        except Exception as e:
            logger.error(f"获取对话历史记录失败: {e}")
            return []

    @staticmethod
    async def get_stats(
        conversation_id: Optional[str] = None,
        sender_id: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """异步获取对话统计信息

        Args:
            conversation_id: 会话ID，可选
            sender_id: 发送者ID，可选
            days: 统计天数，默认7天

        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            # 计算日期范围
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            # 使用线程池执行数据库操作
            stats = await asyncio.to_thread(
                get_conversation_stats,
                conversation_id,
                sender_id,
                start_date,
                end_date
            )

            return stats
        except Exception as e:
            logger.error(f"获取对话统计信息失败: {e}")
            return {"error": str(e)}

    @staticmethod
    async def count_old_records(days: int = 30) -> int:
        """统计指定天数前的对话记录数量

        Args:
            days: 保留天数，默认30天（统计30天前的记录）

        Returns:
            int: 记录数量
        """
        try:
            # 计算截止日期
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            # 执行查询操作
            def _count_old_records():
                conn = get_conn()
                cursor = conn.execute(
                    """SELECT COUNT(*) FROM conversation_records
                       WHERE date(created_at) < date(?)""",
                    (cutoff_date,)
                )
                count = cursor.fetchone()[0]
                conn.close()
                return count

            # 使用线程池执行数据库操作
            count = await asyncio.to_thread(_count_old_records)
            return count
        except Exception as e:
            logger.error(f"统计对话记录失败: {e}")
            return 0

    @staticmethod
    async def cleanup_old_records(days: int = 30) -> Dict[str, Any]:
        """清理指定天数前的对话记录

        Args:
            days: 保留天数，默认30天（删除30天前的记录）

        Returns:
            Dict[str, Any]: 清理结果
        """
        try:
            # 计算截止日期
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            # 执行删除操作
            def _delete_old_records():
                conn = get_conn()
                cursor = conn.execute(
                    """DELETE FROM conversation_records
                       WHERE date(created_at) < date(?)""",
                    (cutoff_date,)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                conn.close()
                return deleted_count

            # 使用线程池执行数据库操作
            deleted_count = await asyncio.to_thread(_delete_old_records)

            logger.info(f"已清理 {deleted_count} 条 {cutoff_date} 之前的对话记录")
            return {
                "success": True,
                "deleted_count": deleted_count,
                "cutoff_date": cutoff_date,
                "message": f"已清理 {deleted_count} 条 {cutoff_date} 之前的对话记录"
            }
        except Exception as e:
            logger.error(f"清理对话记录失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"清理对话记录失败: {e}"
            }

    @staticmethod
    async def export_records(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        conversation_id: Optional[str] = None,
        sender_id: Optional[str] = None,
        format: str = "json"
    ) -> Dict[str, Any]:
        """导出对话记录

        Args:
            start_date: 开始日期，格式：YYYY-MM-DD
            end_date: 结束日期，格式：YYYY-MM-DD
            conversation_id: 会话ID，可选
            sender_id: 发送者ID，可选
            format: 导出格式，支持json/csv，默认json

        Returns:
            Dict[str, Any]: 导出结果
        """
        try:
            # 默认导出最近7天的记录
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")
            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            # 构建SQL查询
            def _export_records():
                conn = get_conn()
                query = """SELECT * FROM conversation_records WHERE 1=1"""
                params = []

                if start_date:
                    query += " AND date(created_at) >= date(?)"
                    params.append(start_date)

                if end_date:
                    query += " AND date(created_at) <= date(?)"
                    params.append(end_date)

                if conversation_id:
                    query += " AND conversation_id = ?"
                    params.append(conversation_id)

                if sender_id:
                    query += " AND sender_id = ?"
                    params.append(sender_id)

                query += " ORDER BY created_at DESC"

                cursor = conn.execute(query, params)
                columns = [description[0] for description in cursor.description]
                records = cursor.fetchall()
                conn.close()

                # 转换为字典列表
                result = []
                for record in records:
                    result.append(dict(zip(columns, record)))

                return result

            # 使用线程池执行数据库操作
            records = await asyncio.to_thread(_export_records)

            # 根据格式返回结果
            if format.lower() == "csv":
                # 这里可以添加CSV格式转换逻辑
                pass

            return {
                "success": True,
                "count": len(records),
                "start_date": start_date,
                "end_date": end_date,
                "records": records,
                "format": format
            }
        except Exception as e:
            logger.error(f"导出对话记录失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"导出对话记录失败: {e}"
            }


# 创建服务实例
conversation_log_service = ConversationLogService()


async def cleanup_conversation_logs(days: int = 30) -> Dict[str, Any]:
    """清理对话记录的全局函数

    Args:
        days: 保留天数，默认30天（删除30天前的记录）

    Returns:
        Dict[str, Any]: 清理结果
    """
    return await conversation_log_service.cleanup_old_records(days)
