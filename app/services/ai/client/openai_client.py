# openai_client.py
"""
统一封装 OpenAIChatCompletionClient，支持全局默认配置和参数覆盖。
同时支持 Gemini 模型客户端。
"""
import os
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelFamily
from loguru import logger
import collections.abc
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


# 全局默认配置，绝大多数场景无需再传递重复参数
_DEFAULT_CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY"),
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    # "model": "qwen-flash",
    "model": "qwen3-coder-plus",
    "model_info": {
        "vision": False,
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
    valid_config["temperature"] = 0

    # logger.info(f"OpenAIChatCompletionClient创建成功: {valid_config}")
    return OpenAIChatCompletionClient(**valid_config)

def get_kimi_k2_client(**overrides) -> OpenAIChatCompletionClient:
    """
    获取 Kimi K2 模型客户端实例，使用 OpenAI 兼容的 API。
    优先级：调用参数 > 默认配置。
    用法：
        client = get_kimi_k2_client(model="Moonshot-Kimi-K2-Instruct")
    """
    config = deep_merge_dicts(_DEFAULT_CONFIG.copy(), overrides)
    # 过滤掉 None 的参数，防止传递无效参数
    valid_config = {k: v for k, v in config.items() if v is not None}
    valid_config["model"] = "Moonshot-Kimi-K2-Instruct"
    # logger.info(f"Kimi K2 模型客户端创建成功: {valid_config}")
    return OpenAIChatCompletionClient(**valid_config)


# Gemini 模型客户端默认配置 - gemini 不需要输入base_url
_GEMINI_DEFAULT_CONFIG = {
    "api_key": os.getenv("GEMINI_API_KEY"),
    "model": "gemini-2.5-flash",
    "model_info": {
        "vision": True,
        "function_calling": True,
        "json_output": True,
        "multiple_system_messages": True,
        "family": ModelFamily.ANY,
        "structured_output": False,
    },
}


def get_gemini_client(**overrides) -> OpenAIChatCompletionClient:
    """
    获取 Gemini 模型客户端实例，使用 OpenAI 兼容的 API。
    优先级：调用参数 > 默认配置。
    用法：
        client = get_gemini_client(model="gemini-2.5-flash")
    """
    config = deep_merge_dicts(_GEMINI_DEFAULT_CONFIG.copy(), overrides)
    # 过滤掉 None 的参数，防止传递无效参数
    valid_config = {k: v for k, v in config.items() if v is not None}

    # 检查 API Key 是否存在
    if not valid_config.get("api_key"):
        logger.warning("未配置 GEMINI_API_KEY，将使用默认 OpenAI 客户端")
        return get_openai_client(**overrides)

    return OpenAIChatCompletionClient(**valid_config)
