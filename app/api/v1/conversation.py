#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对话记录API端点模块
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from app.db_utils import get_conversation_history, get_conversation_stats

router = APIRouter()


class ConversationRecord(BaseModel):
    """对话记录模型"""
    id: int
    conversation_id: str
    sender_id: str
    user_question: str
    ai_response: str
    message_type: str
    response_time_ms: Optional[int]
    agent_type: Optional[str]
    created_at: str
    updated_at: str


class ConversationHistoryResponse(BaseModel):
    """对话历史响应模型"""
    success: bool
    message: str
    data: List[ConversationRecord]
    total: int


class ConversationStatsResponse(BaseModel):
    """对话统计响应模型"""
    success: bool
    message: str
    data: Dict[str, Any]


@router.get("/history", response_model=ConversationHistoryResponse)
async def get_conversation_history_api(
    conversation_id: Optional[str] = Query(None, description="会话ID"),
    sender_id: Optional[str] = Query(None, description="发送者ID"),
    limit: int = Query(50, ge=1, le=1000, description="返回记录数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """
    获取对话历史记录
    """
    try:
        records = get_conversation_history(
            conversation_id=conversation_id,
            sender_id=sender_id,
            limit=limit,
            offset=offset
        )
        
        # 转换为响应模型
        conversation_records = []
        for record in records:
            conversation_records.append(ConversationRecord(
                id=record[0],
                conversation_id=record[1],
                sender_id=record[2],
                user_question=record[3],
                ai_response=record[4],
                message_type=record[5],
                response_time_ms=record[6],
                agent_type=record[7],
                created_at=record[8],
                updated_at=record[9]
            ))
        
        return ConversationHistoryResponse(
            success=True,
            message="获取对话历史成功",
            data=conversation_records,
            total=len(conversation_records)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对话历史失败: {str(e)}")


@router.get("/stats", response_model=ConversationStatsResponse)
async def get_conversation_stats_api(
    conversation_id: Optional[str] = Query(None, description="会话ID"),
    sender_id: Optional[str] = Query(None, description="发送者ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
):
    """
    获取对话统计信息
    """
    try:
        # 转换日期格式
        start_date_str = start_date.strftime("%Y-%m-%d") if start_date else None
        end_date_str = end_date.strftime("%Y-%m-%d") if end_date else None
        
        stats = get_conversation_stats(
            conversation_id=conversation_id,
            sender_id=sender_id,
            start_date=start_date_str,
            end_date=end_date_str
        )
        
        return ConversationStatsResponse(
            success=True,
            message="获取对话统计成功",
            data=stats
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对话统计失败: {str(e)}")


@router.get("/recent", response_model=ConversationHistoryResponse)
async def get_recent_conversations(
    hours: int = Query(24, ge=1, le=168, description="最近几小时内的对话，默认24小时"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数量限制"),
):
    """
    获取最近的对话记录
    """
    try:
        # 计算开始时间
        from datetime import datetime, timedelta
        start_time = datetime.now() - timedelta(hours=hours)
        start_date_str = start_time.strftime("%Y-%m-%d")
        
        records = get_conversation_history(
            limit=limit,
            offset=0
        )
        
        # 过滤最近的记录
        recent_records = []
        for record in records:
            record_time = datetime.fromisoformat(record[8])  # created_at
            if record_time >= start_time:
                recent_records.append(ConversationRecord(
                    id=record[0],
                    conversation_id=record[1],
                    sender_id=record[2],
                    user_question=record[3],
                    ai_response=record[4],
                    message_type=record[5],
                    response_time_ms=record[6],
                    agent_type=record[7],
                    created_at=record[8],
                    updated_at=record[9]
                ))
        
        return ConversationHistoryResponse(
            success=True,
            message=f"获取最近{hours}小时对话记录成功",
            data=recent_records,
            total=len(recent_records)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最近对话记录失败: {str(e)}")


@router.get("/user/{user_id}/summary")
async def get_user_conversation_summary(
    user_id: str,
    days: int = Query(7, ge=1, le=365, description="统计天数，默认7天"),
):
    """
    获取指定用户的对话摘要
    """
    try:
        from datetime import datetime, timedelta
        
        # 计算开始日期
        start_date = datetime.now() - timedelta(days=days)
        start_date_str = start_date.strftime("%Y-%m-%d")
        
        # 获取用户统计信息
        stats = get_conversation_stats(
            sender_id=user_id,
            start_date=start_date_str
        )
        
        # 获取最近的对话记录
        recent_records = get_conversation_history(
            sender_id=user_id,
            limit=10,
            offset=0
        )
        
        # 构建摘要信息
        summary = {
            "user_id": user_id,
            "period_days": days,
            "stats": stats,
            "recent_conversations": len(recent_records),
            "most_used_agent": None,
            "avg_response_time": stats.get("avg_response_time_ms"),
        }
        
        # 找出最常用的智能体
        agent_distribution = stats.get("agent_distribution", [])
        if agent_distribution:
            summary["most_used_agent"] = agent_distribution[0]["agent_type"]
        
        return {
            "success": True,
            "message": f"获取用户{user_id}的{days}天对话摘要成功",
            "data": summary
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户对话摘要失败: {str(e)}")
