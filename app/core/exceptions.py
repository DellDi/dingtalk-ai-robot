#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
自定义异常类模块
配合依赖注入架构使用的统一异常处理
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException


class ServiceException(Exception):
    """服务层基础异常"""
    
    def __init__(self, message: str, service_name: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.service_name = service_name
        self.details = details or {}
        super().__init__(self.message)


class ServiceUnavailableException(ServiceException):
    """服务不可用异常"""
    
    def __init__(self, service_name: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"服务 {service_name} 当前不可用",
            service_name=service_name,
            details=details
        )


class ServiceInitializationException(ServiceException):
    """服务初始化异常"""
    
    def __init__(self, service_name: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"服务 {service_name} 初始化失败",
            service_name=service_name,
            details=details
        )


class KnowledgeBaseException(ServiceException):
    """知识库服务异常"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            service_name="KnowledgeRetriever",
            details=details
        )


class AIServiceException(ServiceException):
    """AI服务异常"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            service_name="AIMessageHandler",
            details=details
        )


class SSHServiceException(ServiceException):
    """SSH服务异常"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            service_name="SSHClient",
            details=details
        )


# HTTP异常转换器
def service_exception_to_http(exc: ServiceException) -> HTTPException:
    """将服务异常转换为HTTP异常"""
    
    status_code = 500  # 默认内部服务器错误
    
    if isinstance(exc, ServiceUnavailableException):
        status_code = 503
    elif isinstance(exc, ServiceInitializationException):
        status_code = 503
    
    return HTTPException(
        status_code=status_code,
        detail={
            "error": exc.message,
            "service": exc.service_name,
            "details": exc.details
        }
    )
