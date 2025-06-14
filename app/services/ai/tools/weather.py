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
    logger.debug(f"[WeatherTool] Geocoding params: {params}")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(OWM_GEOCODE_URL, params=params)
        logger.debug(f"[WeatherTool] Geocoding response status={r.status_code}, body={r.text[:300]}")
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
    logger.debug(f"[WeatherTool] Weather params: {params}")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(OWM_ONECALL_URL, params=params)
        logger.debug(f"[WeatherTool] Weather response status={r.status_code}, body={r.text[:300]}")
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
    header = (
        "### 未来七天天气预报\n\n| 日期 | 天气 | 最高/最低 (°C) | 湿度 |\n|----|----|----|----|\n"
    )
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
    """解析用户请求，返回 (city_cn, mode)。

    解析思路：
    1. 判断查询时段关键词来决定 today / 7d
    2. 移除常见噪声词后提取城市中文名称
    """
    original = text.strip()
    # 1. 判断七天关键词
    mode = "7d" if re.search(r"7天|七天|一周|近七天|未来七天", original) else "today"

    # 2. 清理噪声词
    noise_pattern = r"(天气|查询|查看|近七天|未来七天|七天|7天|一周|的|未来)"
    cleaned = re.sub(noise_pattern, "", original)
    logger.debug(f"[WeatherTool] Cleaned request text: '{cleaned}' from original '{original}'")

    # 3. 提取连续中文字符 2~6 位作为城市名
    city_match = re.search(r"([\u4e00-\u9fa5]{2,6})", cleaned)
    city = city_match.group(1) if city_match else "上海"
    logger.debug(f"[WeatherTool] Parsed city='{city}', mode='{mode}' from text='{original}'")

    return city, mode


async def process_weather_request(*, city: str, days: int = 1) -> str:  # noqa: D401
    """查询指定城市未来 *days* 天的天气，并返回 Markdown 字符串。

    参数
    ----
    city: 中文城市名，例如 "杭州"。
    days: 可选 1 或 7，分别表示今日或 7 天预报。
    """

    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        logger.error("OpenWeather API key 未配置 (settings.OPENWEATHER_API_KEY)。")
        return "⚠️ 未配置 OpenWeather API Key，无法查询天气。"

    if days not in (1, 7):
        return "⚠️ 仅支持 1 或 7 天预报，请检查参数。"

    mode = "today" if days == 1 else "7d"
    city_cn = city.strip()
    logger.info(f"WeatherTool: city={city_cn}, days={days}, mode={mode}")

    coords = await _get_coordinates(city_cn, api_key)
    if not coords:
        return f"❌ 未找到城市 **{city_cn}** 的地理坐标，无法查询天气。"

    lat, lon = coords
    logger.debug(f"[WeatherTool] Coordinates resolved: lat={lat}, lon={lon}")
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

    logger.info(f"[WeatherTool] 完成天气查询 city={city_cn} days={days}")

    sections.append("\n*数据来源: [OpenWeather](https://openweathermap.org/)*")
    return "\n\n".join(sections)
