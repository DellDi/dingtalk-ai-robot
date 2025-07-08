# openai_client.py
"""
统一封装 OpenAIChatCompletionClient，支持全局默认配置和参数覆盖。
"""
import os
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelFamily
from loguru import logger
import collections.abc

# 全局默认配置，绝大多数场景无需再传递重复参数
_DEFAULT_CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY"),
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-turbo-latest",
    "model_info": {
        "vision": True,
        "function_calling": True,
        "json_output": False,
        "multiple_system_messages": True,
        "family": ModelFamily.ANY,
        "structured_output": False,
    },
}

def deep_merge_dicts(base_dict, update_dict):
    """
    递归合并两个字典。
    update_dict 中的值会覆盖 base_dict 中的值。
    如果两个字典在同一键上的值都是字典，则递归合并它们。
    """
    merged = base_dict.copy()
    for key, value in update_dict.items():
        if isinstance(value, collections.abc.Mapping) and \
           isinstance(merged.get(key), collections.abc.Mapping):
            merged[key] = deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def get_openai_client(**overrides) -> OpenAIChatCompletionClient:
    """
    获取 OpenAIChatCompletionClient 实例，支持参数覆盖。
    优先级：调用参数 > 默认配置。
    用法：
        client = get_openai_client(api_key="xxx", model="gpt-4o")
    """
    config = deep_merge_dicts(_DEFAULT_CONFIG.copy(), overrides)
    # 过滤掉 None 的参数，防止传递无效参数
    valid_config = {k: v for k, v in config.items() if v is not None}
    return OpenAIChatCompletionClient(**valid_config)

def get_gemini_client(**overrides) -> OpenAIChatCompletionClient:
    """
    获取 GeminiChatCompletionClient 实例，支持参数覆盖。
    优先级：调用参数 > 默认配置。
    用法：
        client = get_gemini_client(api_key="xxx", model="gemini-2.5-flash")
    """
    DefaultConfig = {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "base_url": "",
        "model": ModelFamily.GEMINI_2_5_FLASH,
        "model_info": {
            "vision": True,
            "function_calling": True,
            "json_output": False,
            "multiple_system_messages": True,
            "family": ModelFamily.GEMINI_2_5_FLASH,
            "structured_output": False,
        },
    }
    config = deep_merge_dicts(DefaultConfig.copy(), overrides)
    # 过滤掉 None 的参数，防止传递无效参数
    valid_config = {k: v for k, v in config.items() if v is not None}
    return OpenAIChatCompletionClient(**valid_config)
