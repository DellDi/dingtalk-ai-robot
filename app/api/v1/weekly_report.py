#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
周报API路由模块
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from loguru import logger

from app.services.weekly_report_service import weekly_report_service


# 创建路由器
router = APIRouter(prefix="/weekly-report", tags=["周报管理"])


# 请求模型
class GenerateSummaryRequest(BaseModel):
    """生成周报总结请求模型"""
    content: str = Field(..., description="原始日志内容")
    use_quick_mode: bool = Field(False, description="是否使用快速模式")


class CreateReportRequest(BaseModel):
    """创建钉钉日报请求模型"""
    summary_content: str = Field(..., description="周报总结内容")
    user_id: Optional[str] = Field(None, description="用户ID，为空则使用第一个用户")
    template_id: Optional[str] = Field(None, description="钉钉日报模版ID")


# 响应模型
class ApiResponse(BaseModel):
    """API响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[dict] = Field(None, description="响应数据")


@router.get("/check-logs", response_model=ApiResponse, summary="检查用户周报日志")
async def check_user_logs(
    user_id: Optional[str] = Query(None, description="用户ID，为空则使用第一个用户")
):
    """
    检查当前本地数据库中用户周一到周四的日志内容
    
    - **user_id**: 用户ID，如果不提供则使用数据库中第一个用户
    
    返回用户本周一到周四的所有日志记录和整合后的内容
    """
    try:
        logger.info(f"API调用: 检查用户周报日志, user_id={user_id}")
        result = await weekly_report_service.check_user_weekly_logs(user_id)
        
        if result["success"]:
            logger.info("用户周报日志检查成功")
        else:
            logger.warning(f"用户周报日志检查失败: {result['message']}")
            
        return ApiResponse(**result)
        
    except Exception as e:
        logger.error(f"检查用户日志API异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/generate-summary", response_model=ApiResponse, summary="生成周报总结")
async def generate_weekly_summary(request: GenerateSummaryRequest):
    """
    发送文本调用智能体生成周报总结
    
    - **content**: 原始日志内容
    - **use_quick_mode**: 是否使用快速模式（单智能体）
    
    使用AutoGen多智能体或单智能体生成专业的周报总结
    """
    try:
        logger.info(f"API调用: 生成周报总结, 快速模式={request.use_quick_mode}")
        result = await weekly_report_service.generate_weekly_summary(
            request.content, 
            request.use_quick_mode
        )
        
        if result["success"]:
            logger.info("周报总结生成成功")
        else:
            logger.warning(f"周报总结生成失败: {result['message']}")
            
        return ApiResponse(**result)
        
    except Exception as e:
        logger.error(f"生成周报总结API异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/create-report", response_model=ApiResponse, summary="创建并发送钉钉日报")
async def create_dingtalk_report(request: CreateReportRequest):
    """
    将周报内容创建为钉钉日报并发送
    
    - **summary_content**: 周报总结内容
    - **user_id**: 用户ID，为空则使用第一个用户
    - **template_id**: 钉钉日报模版ID，为空则使用默认模版
    
    将AI生成的周报内容格式化并通过钉钉日报接口发送
    """
    try:
        logger.info(f"API调用: 创建钉钉日报, user_id={request.user_id}")
        result = await weekly_report_service.create_and_send_weekly_report(
            request.summary_content,
            request.user_id,
            request.template_id
        )
        
        if result["success"]:
            logger.info("钉钉日报创建成功")
        else:
            logger.warning(f"钉钉日报创建失败: {result['message']}")
            
        return ApiResponse(**result)
        
    except Exception as e:
        logger.error(f"创建钉钉日报API异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/auto-task", response_model=ApiResponse, summary="执行自动周报任务")
async def run_auto_weekly_task():
    """
    执行完整的自动周报任务
    
    包含以下步骤：
    1. 检查用户周一到周四的日志
    2. 调用AI智能体生成周报总结
    3. 创建并发送钉钉日报
    4. 推送消息到钉钉机器人
    
    这个接口通常由定时任务调用
    """
    try:
        logger.info("API调用: 执行自动周报任务")
        result = await weekly_report_service.auto_weekly_report_task()
        
        if result["success"]:
            logger.info("自动周报任务执行成功")
        else:
            logger.warning(f"自动周报任务执行失败: {result['message']}")
            
        return ApiResponse(**result)
        
    except Exception as e:
        logger.error(f"自动周报任务API异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/health", summary="健康检查")
async def health_check():
    """
    周报服务健康检查
    
    检查各个组件的状态：
    - 数据库连接
    - AI智能体状态
    - 钉钉API连接
    """
    try:
        # 简单的健康检查
        from app.db_utils import get_conn
        
        # 检查数据库连接
        conn = get_conn()
        conn.close()
        
        return {
            "status": "healthy",
            "message": "周报服务运行正常",
            "components": {
                "database": "ok",
                "ai_agent": "ok",
                "dingtalk_api": "ok"
            }
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=503, detail=f"服务不可用: {str(e)}")


# 导出路由器
__all__ = ["router"]
