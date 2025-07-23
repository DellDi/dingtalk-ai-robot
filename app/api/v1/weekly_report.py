#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
周报API路由模块
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field
from loguru import logger

from app.services.weekly_report_service import WeeklyReportService
from app.core.container import get_weekly_report_service_dependency


# 创建路由器
router = APIRouter(prefix="/weekly-report", tags=["周报管理"])


# 请求模型
class GenerateSummaryRequest(BaseModel):
    """生成周报总结请求模型"""
    content: Optional[str] = Field(None, description="原始日志内容（当user_id为空时必填）")
    use_quick_mode: bool = Field(False, description="是否使用快速模式")
    user_id: Optional[str] = Field(None, description="用户ID，优先级高于content，会自动获取用户的钉钉日报记录")
    start_date: Optional[str] = Field(None, description="开始日期，格式为YYYY-MM-DD，仅在使用user_id时有效")
    end_date: Optional[str] = Field(None, description="结束日期，格式为YYYY-MM-DD，仅在使用user_id时有效")


class CreateReportRequest(BaseModel):
    """创建钉钉日报请求模型"""
    summary_content: str = Field(..., description="周报总结内容")
    user_id: Optional[str] = Field(None, description="用户ID，为空则使用第一个用户")
    template_name: str = Field("产品研发中心组长日报及周报(导入上篇)", description="钉钉日报模版名称")
    template_content: Optional[str] = Field(None, description="额外的模版内容，如果提供将与周报内容结合生成最终版本")


class SaveReportRequest(BaseModel):
    """保存钉钉日志内容请求模型"""
    summary_content: str = Field(..., description="日志内容")
    user_id: Optional[str] = Field(None, description="用户ID，为空则使用第一个用户")
    template_name: str = Field("产品研发中心组长日报及周报(导入上篇)", description="钉钉日报模版名称")
    template_content: Optional[str] = Field(None, description="额外的模版内容，如果提供将与日志内容结合生成最终版本")


# 响应模型
class ApiResponse(BaseModel):
    """API响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[dict] = Field(None, description="响应数据")


@router.get("/check-dingding-logs", response_model=ApiResponse, summary="查询用户钉钉日报记录")
async def check_user_logs(
    user_id: Optional[str] = Query(None, description="用户ID，为空则使用第一个用户"),
    start_date: Optional[str] = Query(None, description="开始日期，格式为YYYY-MM-DD，默认为本周一"),
    end_date: Optional[str] = Query(None, description="结束日期，格式为YYYY-MM-DD，默认为今天"),
    weekly_service: WeeklyReportService = Depends(get_weekly_report_service_dependency)
):
    """
    直接查询钉钉服务获取用户的日报记录

    - **user_id**: 用户ID，如果不提供则使用数据库中第一个用户
    - **start_date**: 开始日期，格式为YYYY-MM-DD，默认为本周一
    - **end_date**: 结束日期，格式为YYYY-MM-DD，默认为今天

    返回用户指定日期范围内的所有钉钉日报记录和整合后的内容
    """
    try:
        logger.info(f"API调用: 查询用户钉钉日报记录, user_id={user_id}, start_date={start_date}, end_date={end_date}")

        # 直接调用钉钉服务获取日报记录
        if start_date or end_date:
            # 如果指定了日期范围，直接调用fetch_user_daily_reports
            result = await weekly_service.fetch_user_daily_reports(user_id, start_date, end_date)
        else:
            # 否则使用check_user_weekly_logs（内部会调用fetch_user_daily_reports）
            result = await weekly_service.check_user_weekly_logs(user_id)

        if result["success"]:
            source = result.get("data", {}).get("source", "unknown")
            logger.info(f"用户日报记录查询成功，数据来源: {source}")
        else:
            logger.warning(f"用户日报记录查询失败: {result['message']}")

        return ApiResponse(**result)

    except Exception as e:
        logger.error(f"API错误: 查询用户钉钉日报记录失败, {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/local-reports", response_model=ApiResponse, summary="查询本地已发送的周报记录")
async def get_local_weekly_reports(
    user_id: Optional[str] = Query(None, description="用户ID，为空则使用第一个用户"),
    start_date: Optional[str] = Query(None, description="开始日期，格式为YYYY-MM-DD，默认为本周一"),
    end_date: Optional[str] = Query(None, description="结束日期，格式为YYYY-MM-DD，默认为今天"),
    weekly_service: WeeklyReportService = Depends(get_weekly_report_service_dependency)
):
    """
    从本地数据库查询已发送成功的用户周报记录

    - **user_id**: 用户ID，如果不提供则使用数据库中第一个用户
    - **start_date**: 开始日期，格式为YYYY-MM-DD，默认为本周一
    - **end_date**: 结束日期，格式为YYYY-MM-DD，默认为今天

    返回用户指定日期范围内的所有已发送到钉钉的周报记录和整合后的内容
    """
    try:
        logger.info(f"API调用: 查询本地已发送的周报记录, user_id={user_id}, start_date={start_date}, end_date={end_date}")

        # 调用服务获取本地已发送的周报记录
        result = await weekly_service.get_local_weekly_reports(user_id, start_date, end_date)

        if result["success"]:
            logs_count = result.get("data", {}).get("logs_count", 0)
            logger.info(f"本地已发送的周报记录查询成功，共 {logs_count} 条")
        else:
            logger.warning(f"本地已发送的周报记录查询失败: {result['message']}")

        return ApiResponse(**result)

    except Exception as e:
        logger.error(f"API错误: 查询本地已发送的周报记录失败, {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/generate-summary", response_model=ApiResponse, summary="生成周报总结")
async def generate_weekly_summary(
    request: GenerateSummaryRequest,
    weekly_service: WeeklyReportService = Depends(get_weekly_report_service_dependency)
):
    """
    生成周报总结 - 支持两种模式

    **模式1：基于用户ID自动获取钉钉日报（优先级高）**
    - **user_id**: 用户ID，会自动调用钉钉API获取用户的日报记录
    - **start_date**: 开始日期，格式为YYYY-MM-DD（可选）
    - **end_date**: 结束日期，格式为YYYY-MM-DD（可选）
    - **use_quick_mode**: 是否使用快速模式（单智能体）

    **模式2：基于文本内容生成总结**
    - **content**: 原始日志内容（当user_id为空时必填）
    - **use_quick_mode**: 是否使用快速模式（单智能体）

    注意：user_id的优先级高于content，如果提供了user_id，将忽略content参数
    """
    try:
        # 参数验证
        if not request.user_id and not request.content:
            raise HTTPException(
                status_code=400,
                detail="user_id和content至少需要提供一个参数"
            )

        # 模式1：基于用户ID自动获取钉钉日报（优先级高）
        if request.user_id:
            logger.info(f"API调用: 基于用户ID生成周报总结, user_id={request.user_id}, 快速模式={request.use_quick_mode}")

            # 验证日期参数
            def validate_api_date(date_str: str, param_name: str) -> str:
                """验证API传入的日期参数"""
                if not date_str:
                    return None

                # 检查是否是无效值
                if date_str.lower() in ['string', 'none', 'null', '']:
                    logger.warning(f"API接收到无效的{param_name}值: {date_str}，将忽略此参数")
                    return None

                # 验证日期格式
                try:
                    from datetime import datetime
                    datetime.strptime(date_str, "%Y-%m-%d")
                    return date_str
                except ValueError:
                    logger.warning(f"API接收到格式错误的{param_name}: {date_str}，期望格式为YYYY-MM-DD，将忽略此参数")
                    return None

            # 验证日期参数
            validated_start_date = validate_api_date(request.start_date, "start_date")
            validated_end_date = validate_api_date(request.end_date, "end_date")

            # 先调用钉钉日报获取逻辑
            try:
                if validated_start_date or validated_end_date:
                    # 如果指定了日期范围，直接调用fetch_user_daily_reports
                    daily_reports_result = await weekly_service.fetch_user_daily_reports(
                        request.user_id,
                        validated_start_date,
                        validated_end_date
                    )
                else:
                    # 否则使用check_user_weekly_logs（内部会调用fetch_user_daily_reports）
                    daily_reports_result = await weekly_service.check_user_weekly_logs(request.user_id)

                if not daily_reports_result["success"]:
                    return ApiResponse(
                        success=False,
                        message=f"获取用户日报失败: {daily_reports_result['message']}",
                        data=daily_reports_result.get("data")
                    )

                # 提取日报内容和整合内容用于AI生成
                daily_reports_data = daily_reports_result.get("data", {})
                reports_content = daily_reports_data.get("reports", [])
                combined_content = daily_reports_data.get("combined_content", "")

                if not reports_content:
                    return ApiResponse(
                        success=False,
                        message="未找到用户的日报记录，无法生成周报总结",
                        data={"user_id": request.user_id}
                    )

                # 将日报记录整合内容用于AI生成总结
                content_for_ai = combined_content

                logger.info(f"成功获取用户日报，共{len(reports_content)}条记录，开始AI生成总结")

            except Exception as e:
                logger.error(f"获取用户日报记录失败: {e}")
                return ApiResponse(
                    success=False,
                    message=f"获取用户日报记录时发生错误: {str(e)}",
                    data={"user_id": request.user_id}
                )

        # 模式2：基于文本内容生成总结
        else:
            logger.info(f"API调用: 基于文本内容生成周报总结, 快速模式={request.use_quick_mode}")
            content_for_ai = request.content

        logger.info(f"AI生成周报总结，输入内容: {(content_for_ai)}")

        # 调用AI生成周报总结
        result = await weekly_service.generate_weekly_summary(
            content_for_ai,
            request.use_quick_mode
        )

        if result["success"]:
            logger.info("周报总结生成成功")
            # 如果是基于用户ID的模式，在返回数据中添加用户信息
            if request.user_id:
                if "data" not in result:
                    result["data"] = {}
                result["data"]["user_id"] = request.user_id
                result["data"]["source"] = "dingtalk_reports"
                result["data"]["reports_count"] = len(reports_content) if 'reports_content' in locals() else 0
            else:
                if "data" not in result:
                    result["data"] = {}
                result["data"]["source"] = "text_content"
        else:
            logger.warning(f"周报总结生成失败: {result['message']}")

        return ApiResponse(**result)

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"生成周报总结API异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/create-report", response_model=ApiResponse, summary="创建并发送钉钉日报")
async def create_dingtalk_report(
    request: CreateReportRequest,
    weekly_service: WeeklyReportService = Depends(get_weekly_report_service_dependency)
):
    """
    将周报内容创建为钉钉日报并发送

    - **summary_content**: 周报总结内容
    - **user_id**: 用户ID，为空则使用第一个用户
    - **template_name**: 钉钉日报模版名称，默认为"产品研发中心组长日报及周报(导入上篇)"
    - **template_content**: 额外的模版内容，如果提供将与周报内容结合生成最终版本

    将AI生成的周报内容格式化并通过钉钉日报接口发送
    """
    try:
        logger.info(f"API调用: 创建钉钉日报, user_id={request.user_id}, template_name={request.template_name}")
        result = await weekly_service.create_and_send_weekly_report(
            request.summary_content,
            request.user_id,
            request.template_name,
            request.template_content
        )

        if result["success"]:
            logger.info("钉钉日报创建成功")
        else:
            logger.warning(f"钉钉日报创建失败: {result['message']}")

        return ApiResponse(**result)

    except Exception as e:
        logger.error(f"创建钉钉日报API异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/save-report", response_model=ApiResponse, summary="保存钉钉日报内容")
async def save_dingtalk_report(
    request: SaveReportRequest,
    weekly_service: WeeklyReportService = Depends(get_weekly_report_service_dependency)
):
    """
    将内容保存为钉钉日报（不发送到群聊）

    - **summary_content**: 日志内容
    - **user_id**: 用户ID，为空则使用第一个用户
    - **template_name**: 钉钉日报模版名称，默认为"产品研发中心组长日报及周报(导入上篇)"
    - **template_content**: 额外的模版内容，如果提供将与日志内容结合生成最终版本

    将内容格式化并通过钉钉日报接口保存（不发送到群聊）
    """
    try:
        logger.info(f"API调用: 保存钉钉日报内容, user_id={request.user_id}, template_name={request.template_name}")
        result = await weekly_service.save_weekly_report(
            request.summary_content,
            request.user_id,
            request.template_name,
            request.template_content
        )

        if result["success"]:
            logger.info("钉钉日报内容保存成功")
        else:
            logger.warning(f"钉钉日报内容保存失败: {result['message']}")

        return ApiResponse(**result)

    except Exception as e:
        logger.error(f"保存钉钉日报内容API异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/auto-task", response_model=ApiResponse, summary="执行自动周报任务")
async def run_auto_weekly_task(
    weekly_service: WeeklyReportService = Depends(get_weekly_report_service_dependency)
):
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
        result = await weekly_service.auto_weekly_report_task()

        if result["success"]:
            logger.info("自动周报任务执行成功")
        else:
            logger.warning(f"自动周报任务执行失败: {result['message']}")

        return ApiResponse(**result)

    except Exception as e:
        logger.error(f"自动周报任务API异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/health", summary="健康检查")
async def health_check(
    weekly_service: WeeklyReportService = Depends(get_weekly_report_service_dependency)
):
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
