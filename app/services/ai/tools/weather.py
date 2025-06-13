#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""weather.py
OpenWeather One Call 3.0 查询工具。

该模块暴露 `process_weather_request` 异步函数，供智能体在运行时调用。
根据用户的请求文本自动解析地点与时间范围（今日/未来 7 天）。
返回格式化良好的 Markdown 字符串，适配 GeneralAssistant 输出需求。
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
from loguru import logger

from app.core.config import settings

OWM_GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"
OWM_ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"

# 常见中国主要城市英文名映射（补充可自行增加）
CITY_ALIAS: Dict[str, str] = {
    "北京": "Beijing",
    "上海": "Shanghai",
    "广州": "Guangzhou",
    "深圳": "Shenzhen",
    "杭州": "Hangzhou",
    "成都": "Chengdu",
    "南京": "Nanjing",
    "武汉": "Wuhan",
    "西安": "Xi'an",
}


class WeatherAPIError(Exception):
    """自定义异常：天气 API 调用失败"""


async def _get_coordinates(city_zh: str, api_key: str) -> tuple[float, float] | None:
    """根据中文城市名获取经纬度坐标。"""
    params = {
        "q": f"{CITY_ALIAS.get(city_zh, city_zh)},CN",
        "limit": 1,
        "appid": api_key,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(OWM_GEOCODE_URL, params=params)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return data[0]["lat"], data[0]["lon"]


async def _fetch_weather(lat: float, lon: float, api_key: str) -> Dict[str, Any]:
    params = {
        "lat": lat,
        "lon": lon,
        "units": "metric",
        "lang": "zh_cn",
        "appid": api_key,
        "exclude": "minutely,alerts",  # 精简不必要字段
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(OWM_ONECALL_URL, params=params)
        r.raise_for_status()
        return r.json()


def _format_current(current: Dict[str, Any]) -> str:
    dt = datetime.fromtimestamp(current["dt"], tz=timezone.utc).astimezone()
    weather = current["weather"][0]["description"].capitalize()
    temp = current["temp"]
    feels = current["feels_like"]
    humidity = current["humidity"]
    wind = current["wind_speed"]
    return (
        f"### 今日天气 ({dt:%Y-%m-%d})\n"
        f"| 指标 | 数值 |\n|----|----|\n"
        f"| 天气 | {weather} |\n| 温度 | {temp}°C (体感 {feels}°C) |\n"
        f"| 湿度 | {humidity}% |\n| 风速 | {wind} m/s |\n"
    )


def _format_daily(daily: List[Dict[str, Any]]) -> str:
    header = "### 未来七天天气预报\n\n| 日期 | 天气 | 最高/最低 (°C) | 湿度 |\n|----|----|----|----|\n"
    rows = []
    for day in daily[:7]:
        dt = datetime.fromtimestamp(day["dt"], tz=timezone.utc).astimezone()
        weather = day["weather"][0]["description"].capitalize()
        temp_max = day["temp"]["max"]
        temp_min = day["temp"]["min"]
        humidity = day["humidity"]
        rows.append(f"| {dt:%m-%d} | {weather} | {temp_max}/{temp_min} | {humidity}% |")
    return header + "\n".join(rows)


def _parse_request(text: str) -> tuple[str, str]:
    """解析用户请求，返回 (city_cn, mode)\n
    mode: "today" or "7d""".
    text = text.strip()
    # 判断七天关键词
    mode = "7d" if re.search(r"7天|七天|一周", text) else "today"
    # 简单提取城市名：假设用户输入 "上海天气" 或 "查询广州未来七天天气" 等
    city_match = re.search(r"([\u4e00-\u9fa5]{2,})", text)
    city = city_match.group(1) if city_match else "上海"
    return city, mode


async def process_weather_request(request_text: str) -> str:  # noqa: D401
    """处理天气查询请求并返回 Markdown 字符串."""

    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        logger.error("OpenWeather API key 未配置 (settings.OPENWEATHER_API_KEY)。")
        return "⚠️ 未配置 OpenWeather API Key，无法查询天气。"

    city_cn, mode = _parse_request(request_text)
    logger.info(f"WeatherTool: city={city_cn}, mode={mode}")

    coords = await _get_coordinates(city_cn, api_key)
    if not coords:
        return f"❌ 未找到城市 **{city_cn}** 的地理坐标，无法查询天气。"

    lat, lon = coords
    try:
        weather_data = await _fetch_weather(lat, lon, api_key)
    except httpx.HTTPError as exc:
        logger.error(f"Weather API 调用失败: {exc}")
        raise WeatherAPIError(str(exc)) from exc

    sections: List[str] = [f"## {city_cn} 天气概览\n"]
    if mode == "today":
        sections.append(_format_current(weather_data["current"]))
    else:
        sections.append(_format_daily(weather_data["daily"]))

    sections.append("\n*数据来源: [OpenWeather](https://openweathermap.org/)*")
    return "\n\n".join(sections)
