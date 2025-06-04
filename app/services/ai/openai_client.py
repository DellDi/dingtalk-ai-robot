# openai_client.py
"""
统一封装 OpenAIChatCompletionClient，支持全局默认配置和参数覆盖。
"""
import os
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelFamily

# 全局默认配置，绝大多数场景无需再传递重复参数
_DEFAULT_CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY"),
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-turbo-latest",
    "model_info": {
        "vision": True,
        "function_calling": True,
        "json_output": False,
        "family": ModelFamily.ANY,
        "structured_output": False,
    },
}

def get_openai_client(**overrides) -> OpenAIChatCompletionClient:
    """
    获取 OpenAIChatCompletionClient 实例，支持参数覆盖。
    优先级：调用参数 > 默认配置。
    用法：
        client = get_openai_client(api_key="xxx", model="gpt-3.5-turbo")
    """
    config = {**_DEFAULT_CONFIG, **overrides}
    # 过滤掉 None 的参数，防止传递无效参数
    valid_config = {k: v for k, v in config.items() if v is not None}
    return OpenAIChatCompletionClient(**valid_config)
