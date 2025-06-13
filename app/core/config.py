#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
应用配置模块
"""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""

    # 钉钉开放平台配置
    DINGTALK_APP_ID: str = Field(..., description="钉钉开放平台 App ID")
    DINGTALK_CLIENT_ID: str = Field(..., description="钉钉开放平台 Client ID (AppKey)")
    DINGTALK_CLIENT_SECRET: str = Field(..., description="钉钉开放平台 Client Secret (AppSecret)")
    DINGTALK_ROBOT_CODE: str = Field(..., description="钉钉机器人编码")

    # API服务配置
    API_HOST: str = Field("0.0.0.0", description="API服务监听地址")
    API_PORT: int = Field(8000, description="API服务监听端口")
    DEBUG: bool = Field(False, description="调试模式")

    # JIRA配置
    JIRA_URL: Optional[str] = Field(None, description="JIRA服务地址")
    JIRA_USERNAME: Optional[str] = Field(None, description="JIRA用户名")
    JIRA_API_TOKEN: Optional[str] = Field(None, description="JIRA API令牌")
    JIRA_PROJECT_KEY: Optional[str] = Field(None, description="JIRA项目Key")

    # AI服务配置
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API密钥")

    # 知识库配置
    TONGYI_API_KEY: Optional[str] = Field(None, description="通义千问 API密钥")
    TONGYI_EMBEDDING_MODEL_NAME: str = Field(
        default="text-embedding-v4", description="通义千问嵌入模型名称"
    )
    TONGYI_EMBEDDING_API_ENDPOINT: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1", 
        description="通义千问OpenAI兼容模式的Base URL"
    )
    VECTOR_DB_TYPE: str = Field("chroma", description="向量数据库类型")
    VECTOR_DB_PATH: str = Field("./chroma_data/vector_db", description="向量数据库路径")
    CHROMA_DEFAULT_COLLECTION_NAME: str = Field(default="global_knowledge_base", description="ChromaDB默认集合名称")

    # 文档切片配置
    MAX_CHUNK_CHAR: int = Field(default=1500, description="最大分块字符数")
    WINDOW: int = Field(default=800, description="窗口大小")
    OVERLAP: int = Field(default=200, description="重叠大小")

    # SSH配置
    SSH_HOSTS: Optional[str] = Field(None, description="SSH主机列表，逗号分隔")
    SSH_USERNAME: Optional[str] = Field(None, description="SSH用户名")
    SSH_KEY_PATH: Optional[str] = Field(None, description="SSH密钥路径")
    SSH_PASSWORD: Optional[str] = Field(None, description="SSH密码（不推荐）")

    # 日志配置
    LOG_LEVEL: str = Field("INFO", description="日志级别")
    LOG_FILE: Optional[str] = Field("./logs/app.log", description="日志文件路径")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


# 创建全局设置实例
settings = Settings()
