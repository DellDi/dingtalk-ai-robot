#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
中间件模块
包含依赖注入架构的全局异常处理和其他中间件
"""

import time
import traceback
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.exceptions import ServiceException, service_exception_to_http


async def service_exception_handler(request: Request, exc: ServiceException) -> JSONResponse:
    """
    服务异常处理器
    
    统一处理所有服务层异常，提供一致的错误响应格式
    """
    logger.error(
        f"服务异常 - {exc.service_name}: {exc.message}",
        extra={
            "service": exc.service_name,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    http_exc = service_exception_to_http(exc)
    return JSONResponse(
        status_code=http_exc.status_code,
        content=http_exc.detail
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局异常处理器
    
    处理所有未被捕获的异常
    """
    logger.error(
        f"未处理异常: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc()
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "内部服务器错误",
            "message": "服务器遇到了一个意外的错误",
            "path": request.url.path
        }
    )


async def logging_middleware(request: Request, call_next: Callable) -> Response:
    """
    请求日志中间件
    
    记录所有API请求的详细信息和处理时间
    """
    start_time = time.time()
    
    # 记录请求开始
    logger.info(
        f"API请求开始: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": request.client.host if request.client else "unknown"
        }
    )
    
    # 处理请求
    response = await call_next(request)
    
    # 计算处理时间
    process_time = time.time() - start_time
    
    # 记录请求完成
    logger.info(
        f"API请求完成: {request.method} {request.url.path} - {response.status_code}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time": process_time,
            "client_ip": request.client.host if request.client else "unknown"
        }
    )
    
    # 添加处理时间到响应头
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


async def dependency_injection_middleware(request: Request, call_next: Callable) -> Response:
    """
    依赖注入中间件
    
    在请求处理过程中提供依赖注入相关的上下文信息
    """
    # 添加依赖注入上下文到请求状态
    request.state.di_context = {
        "request_id": f"{int(time.time() * 1000)}",
        "container_initialized": True,  # 可以检查容器状态
    }
    
    # 处理请求
    response = await call_next(request)
    
    # 添加依赖注入信息到响应头（用于调试）
    response.headers["X-DI-Context"] = "enabled"
    response.headers["X-Request-ID"] = request.state.di_context["request_id"]
    
    return response


def setup_middleware(app):
    """
    设置所有中间件
    
    Args:
        app: FastAPI应用实例
    """
    from app.core.exceptions import ServiceException
    
    # 添加异常处理器
    app.add_exception_handler(ServiceException, service_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    
    # 添加中间件（注意顺序：后添加的先执行）
    app.middleware("http")(dependency_injection_middleware)
    app.middleware("http")(logging_middleware)
