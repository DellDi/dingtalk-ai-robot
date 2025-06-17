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
from datetime import datetime, timezone, timedelta
import time
from typing import Any, Dict, List

import httpx
from loguru import logger

from app.core.config import settings

OWM_GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"
OWM_ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"

# 无需城市别名映射，直接支持中文或拼音城市名称

class WeatherAPIError(Exception):
    """自定义异常：天气 API 调用失败"""


async def _get_coordinates(city_zh: str, api_key: str) -> tuple[float, float] | None:
    """根据中文城市名获取经纬度坐标。"""
    params = {
        "q": f"{city_zh},CN",
        "limit": 1,
        "appid": api_key,
    }
    logger.debug(f"[WeatherTool] Geocoding params: {params}")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(OWM_GEOCODE_URL, params=params)
        logger.debug(
            f"[WeatherTool] Geocoding response status={r.status_code}, body={r.text[:300]}"
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return data[0]["lat"], data[0]["lon"]


OWM_TIMEMACHINE_URL = "https://api.openweathermap.org/data/3.0/onecall/timemachine"


async def _fetch_weather(lat: float, lon: float, api_key: str, *, dt: int | None = None) -> Dict[str, Any]:
    params = {
        "lat": lat,
        "lon": lon,
        "units": "metric",
        "lang": "zh_cn",
        "appid": api_key,
    }
    # timemachine 接口需要 dt 参数
    if dt is not None:
        params["dt"] = dt

    logger.debug(f"[WeatherTool] Weather params: {params}")
    async with httpx.AsyncClient(timeout=10) as client:
        endpoint = OWM_TIMEMACHINE_URL if dt is not None else OWM_ONECALL_URL
        r = await client.get(endpoint, params=params)
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


def _format_minutely(minutely: List[Dict[str, Any]]) -> str:
    header = "### 未来 60 分钟降水预报\n\n| 分钟 | 降水量 (mm) |\n|----|----|\n"
    rows = []
    for idx, m in enumerate(minutely[:60]):
        rows.append(f"| {idx+1} | {m.get('precipitation', 0)} |")
    return header + "\n".join(rows)


def _format_hourly(hourly: List[Dict[str, Any]], limit: int = 24) -> str:
    header = "### 小时级天气预报\n\n| 时间 | 天气 | 温度 (°C) | 湿度 |\n|----|----|----|----|\n"
    rows: List[str] = []
    for h in hourly[:limit]:
        dt = datetime.fromtimestamp(h["dt"], tz=timezone.utc).astimezone()
        weather = h["weather"][0]["description"].capitalize()
        temp = h["temp"]
        humidity = h["humidity"]
        rows.append(f"| {dt:%m-%d %H:%M} | {weather} | {temp} | {humidity}% |")
    return header + "\n".join(rows)


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


async def process_weather_request(
    *,
    city: str,
    data_type: str = "current",
    days: int | None = None,
    hours: int | None = None,
    dt: int | None = None,
    date: str | None = None,
) -> str:  # noqa: D401
    """查询指定城市天气并返回 Markdown 字符串。

    参数
    ----
    city: 中文地区名称或者拼音城市名，例如 "杭州" 或 "Hangzhou"（首字母大写）。
    data_type: 要查询的数据类型：`当前`current``|`分钟级`minutely``|`小时级`hourly``|`日级`daily``|`历史`historical``。
    days: 当 ``data_type='daily'`` 时，返回天数 (1-7)。
    hours: 当 ``data_type='hourly'`` 时，返回小时数 (1-48)。
    dt: 当 ``data_type='historical'`` 时，Unix 时间戳（秒）。若提供则优先生效。
    date: 当 ``data_type='historical'`` 时，也可直接传形如 ``YYYY-MM-DD`` 的日期字符串，工具内部转换为 00:00 (Asia/Shanghai) 对应 UTC 秒数。
         二者同时提供时以 ``dt`` 优先。若均未提供则默认回溯 24 小时。
    """

    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        logger.error("OpenWeather API key 未配置 (settings.OPENWEATHER_API_KEY)。")
        return "⚠️ 未配置 OpenWeather API Key，无法查询天气。"

    city_cn = city.strip()
    logger.info(f"WeatherTool: city={city_cn}, data_type={data_type}")

    coords = await _get_coordinates(city_cn, api_key)
    if not coords:
        return f"❌ 未找到城市 **{city_cn}** 的地理坐标，无法查询天气。"

    lat, lon = coords
    logger.debug(f"[WeatherTool] Coordinates resolved: lat={lat}, lon={lon}")

    try:
        # historical 参数处理
        if data_type == "historical":
            if dt is None:
                if date:
                    try:
                        y, m, d = map(int, date.split("-"))
                        sh_tz = timezone(timedelta(hours=8))
                        local_dt = datetime(y, m, d, tzinfo=sh_tz)
                        dt = int(local_dt.astimezone(timezone.utc).timestamp())
                    except ValueError:
                        return "⚠️ 无效的 date 参数，应为 YYYY-MM-DD"
                else:
                    dt = int(time.time()) - 86400  # 默认回溯 24 小时
            max_age = 5 * 86400  # timemachine 仅支持最近 5 天
            if abs(time.time() - dt) > max_age:
                return "⚠️ OpenWeather timemachine 仅支持过去 5 天的数据，请调整日期。"
            dt_param = dt
        else:
            dt_param = None
        weather_data = await _fetch_weather(lat, lon, api_key, dt=dt_param)
    except httpx.HTTPError as exc:
        logger.error(f"Weather API 调用失败: {exc}")
        raise WeatherAPIError(str(exc)) from exc

    sections: List[str] = [f"## {city_cn} 天气 - {data_type.capitalize()}\n"]

    if data_type == "current":
        sections.append(_format_current(weather_data["current"]))
    elif data_type == "minutely":
        if "minutely" not in weather_data:
            sections.append("⚠️ 该地区不支持分钟级预报。")
        else:
            sections.append(_format_minutely(weather_data["minutely"]))
    elif data_type == "hourly":
        sections.append(_format_hourly(weather_data["hourly"], limit=hours))
    elif data_type == "daily":
        sections.append(_format_daily(weather_data["daily"][:days]))
    elif data_type == "historical":
        # timemachine 接口返回字段可能是 'data' 或 'hourly'
        if "hourly" in weather_data:
            hist = weather_data["hourly"]
        elif "data" in weather_data:
            hist = weather_data["data"]
        else:
            hist = []
        if not hist:
            sections.append("⚠️ 历史天气数据不可用。")
        else:
            sections.append(_format_hourly(hist, limit=hours))
    else:
        sections.append("⚠️ 未知数据类型。")

    logger.info(f"[WeatherTool] 完成天气查询 city={city_cn}, data_type={data_type}")

    sections.append("\n*数据来源: [OpenWeather](https://openweathermap.org/)*")
    return "\n\n".join(sections)
