#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
时间工具模块，提供北京时间相关的工具函数
"""

from datetime import datetime, timedelta, timezone


def get_beijing_now() -> datetime:
    """
    获取当前北京时间（UTC+8）的datetime对象

    Returns:
        datetime: 当前北京时间
    """
    # 创建UTC+8时区对象
    beijing_tz = timezone(timedelta(hours=8))
    # 获取当前UTC时间并转换为北京时间
    return datetime.now(tz=timezone.utc).astimezone(beijing_tz)


def get_beijing_time_str(dt: datetime = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    获取北京时间的格式化字符串

    Args:
        dt: 要格式化的datetime对象，默认为当前时间
        fmt: 格式化字符串，默认为"%Y-%m-%d %H:%M:%S"

    Returns:
        str: 格式化后的北京时间字符串
    """
    if dt is None:
        dt = get_beijing_now()
    elif dt.tzinfo is None:
        # 如果传入的是无时区的datetime，假定为UTC时间，转换为北京时间
        beijing_tz = timezone(timedelta(hours=8))
        dt = dt.replace(tzinfo=timezone.utc).astimezone(beijing_tz)

    return dt.strftime(fmt)


def get_beijing_date_days_ago(days: int, fmt: str = "%Y-%m-%d") -> str:
    """
    获取指定天数前的北京日期字符串

    Args:
        days: 天数
        fmt: 格式化字符串，默认为"%Y-%m-%d"

    Returns:
        str: 指定天数前的北京日期字符串
    """
    beijing_now = get_beijing_now()
    past_date = beijing_now - timedelta(days=days)
    return past_date.strftime(fmt)


def parse_beijing_time(time_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    解析北京时间字符串为datetime对象

    Args:
        time_str: 时间字符串
        fmt: 格式化字符串，默认为"%Y-%m-%d %H:%M:%S"

    Returns:
        datetime: 解析后的datetime对象（带北京时区信息）
    """
    dt = datetime.strptime(time_str, fmt)
    beijing_tz = timezone(timedelta(hours=8))
    return dt.replace(tzinfo=beijing_tz)
