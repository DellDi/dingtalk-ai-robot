#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对话记录API端点模块
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import json
import io
import csv

from app.db_utils import get_conversation_history, get_conversation_stats
from app.services.conversation_log_service import conversation_log_service

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


class CleanupRequest(BaseModel):
    """对话记录清理请求模型"""
    days: int = Field(30, description="保留天数，默认30天（删除30天前的记录）")


class CleanupResponse(BaseModel):
    """对话记录清理响应模型"""
    success: bool
    message: str
    deleted_count: Optional[int] = None
    cutoff_date: Optional[str] = None


class ExportRequest(BaseModel):
    """对话记录导出请求模型"""
    start_date: Optional[str] = Field(None, description="开始日期，格式：YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期，格式：YYYY-MM-DD")
    conversation_id: Optional[str] = Field(None, description="会话ID")
    sender_id: Optional[str] = Field(None, description="发送者ID")
    format: str = Field("json", description="导出格式，支持json/csv")


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_conversation_records(
    request: CleanupRequest,
    background_tasks: BackgroundTasks
):
    """
    清理指定天数前的对话记录
    """
    try:
        # 对于大量数据的删除，使用后台任务处理
        if request.days < 7:
            return CleanupResponse(
                success=False,
                message="保留天数不能少于7天，请设置更大的值"
            )

        result = await conversation_log_service.cleanup_old_records(request.days)

        return CleanupResponse(
            success=result["success"],
            message=result["message"],
            deleted_count=result.get("deleted_count"),
            cutoff_date=result.get("cutoff_date")
        )
    except Exception as e:
        return CleanupResponse(
            success=False,
            message=f"清理对话记录失败: {str(e)}"
        )


@router.post("/export")
async def export_conversation_records(request: ExportRequest):
    """
    导出对话记录
    """
    try:
        result = await conversation_log_service.export_records(
            start_date=request.start_date,
            end_date=request.end_date,
            conversation_id=request.conversation_id,
            sender_id=request.sender_id,
            format=request.format
        )

        if not result["success"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": result["message"]}
            )

        # 根据请求的格式返回不同类型的响应
        if request.format.lower() == "csv":
            # 创建CSV文件
            output = io.StringIO()
            writer = csv.writer(output)

            # 写入表头
            if result["records"]:
                writer.writerow(result["records"][0].keys())

                # 写入数据行
                for record in result["records"]:
                    writer.writerow(record.values())

            # 返回CSV响应
            output.seek(0)
            filename = f"conversation_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        else:
            # 返回JSON响应
            filename = f"conversation_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            return StreamingResponse(
                io.BytesIO(json.dumps(result, ensure_ascii=False).encode()),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"导出对话记录失败: {str(e)}"
            }
        )


@router.get("/stats/summary")
async def get_conversation_summary_stats(
    days: int = Query(30, ge=7, le=365, description="统计天数，默认30天")
):
    """
    获取对话记录总体统计信息
    """
    try:
        stats = await conversation_log_service.get_stats(days=days)

        return ConversationStatsResponse(
            success=True,
            message="获取对话统计信息成功",
            data=stats
        )
    except Exception as e:
        return ConversationStatsResponse(
            success=False,
            message=f"获取对话统计信息失败: {str(e)}",
            data={}
        )
