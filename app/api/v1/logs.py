#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日志管理API路由
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.core.logger import cleanup_logs, get_log_stats

router = APIRouter(prefix="/logs", tags=["日志管理"])


@router.get("/stats")
async def get_logs_stats():
    """
    获取日志统计信息

    Returns:
        dict: 包含日志目录、文件数量、总大小等统计信息
    """
    try:
        stats = get_log_stats()
        logger.info("📊 获取日志统计信息")
        return {
            "status": "success",
            "data": stats,
            "message": "日志统计信息获取成功"
        }
    except Exception as e:
        logger.error(f"❌ 获取日志统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取日志统计信息失败: {str(e)}")


@router.post("/cleanup")
async def cleanup_log_files():
    """
    手动清理过期日志文件

    Returns:
        dict: 清理结果
    """
    try:
        logger.info("🧹 手动触发日志清理...")
        cleanup_logs()
        return {
            "status": "success",
            "message": "日志清理完成",
            "data": {
                "action": "cleanup",
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"❌ 手动日志清理失败: {e}")
        raise HTTPException(status_code=500, detail=f"日志清理失败: {str(e)}")


@router.get("/health")
async def logs_health_check():
    """
    日志系统健康检查

    Returns:
        dict: 日志系统状态
    """
    try:
        stats = get_log_stats()
        is_healthy = "error" not in stats

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "message": "日志系统运行正常" if is_healthy else "日志系统存在问题",
            "data": {
                "healthy": is_healthy,
                "stats": stats
            }
        }
    except Exception as e:
        logger.error(f"❌ 日志系统健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "message": f"日志系统健康检查失败: {str(e)}",
            "data": {
                "healthy": False,
                "error": str(e)
            }
        }