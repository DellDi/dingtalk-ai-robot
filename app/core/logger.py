#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日志配置模块
支持日志轮转和定期清理功能
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from app.core.config import settings


class LogConfig:
    """日志配置类"""

    def __init__(self):
        self.log_dir = Path("./logs")
        self.log_file = self.log_dir / "app.log"
        self.max_size = 10 * 1024 * 1024  # 10MB
        self.retention_days = 7
        self.rotation = "10 MB"
        self.compression = "zip"

    def setup_logger(self):
        """设置日志配置"""
        # 确保日志目录存在
        self.log_dir.mkdir(exist_ok=True)

        # 移除默认的控制台处理器
        logger.remove()

        # 添加控制台处理器
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
            level=settings.LOG_LEVEL,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

        # 添加文件处理器（支持轮转）
        logger.add(
            str(self.log_file),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level=settings.LOG_LEVEL,
            rotation=self.rotation,
            compression=self.compression,
            retention=f"{self.retention_days} days",
            backtrace=True,
            diagnose=True,
            encoding="utf-8",
        )

        # 添加错误日志文件处理器
        error_log_file = self.log_dir / "error.log"
        logger.add(
            str(error_log_file),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level="ERROR",
            rotation=self.rotation,
            compression=self.compression,
            retention=f"{self.retention_days} days",
            backtrace=True,
            diagnose=True,
            encoding="utf-8",
        )

        logger.info("📝 日志系统初始化完成")
        logger.info(f"📁 日志目录: {self.log_dir.absolute()}")
        logger.info(f"📄 主日志文件: {self.log_file}")
        logger.info(f"🔄 日志轮转: {self.rotation}")
        logger.info(f"🗂️ 日志保留: {self.retention_days} 天")

    def cleanup_old_logs(self):
        """清理过期日志文件"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            cleaned_count = 0

            for log_file in self.log_dir.glob("*.log*"):
                if log_file.is_file():
                    # 检查文件修改时间
                    mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if mtime < cutoff_date:
                        log_file.unlink()
                        cleaned_count += 1
                        logger.debug(f"🗑️ 删除过期日志文件: {log_file}")

            if cleaned_count > 0:
                logger.info(f"🧹 清理完成，删除了 {cleaned_count} 个过期日志文件")
            else:
                logger.debug("🧹 没有需要清理的过期日志文件")

        except Exception as e:
            logger.error(f"❌ 清理日志文件时出错: {e}")

    def get_log_stats(self) -> dict:
        """获取日志统计信息"""
        try:
            stats = {
                "log_dir": str(self.log_dir.absolute()),
                "total_files": 0,
                "total_size": 0,
                "oldest_file": None,
                "newest_file": None,
            }

            if self.log_dir.exists():
                log_files = list(self.log_dir.glob("*.log*"))
                stats["total_files"] = len(log_files)

                if log_files:
                    total_size = sum(f.stat().st_size for f in log_files)
                    stats["total_size"] = total_size

                    # 获取最旧和最新的文件
                    file_times = [(f, f.stat().st_mtime) for f in log_files]
                    file_times.sort(key=lambda x: x[1])

                    stats["oldest_file"] = {
                        "name": file_times[0][0].name,
                        "modified": datetime.fromtimestamp(file_times[0][1]).isoformat()
                    }
                    stats["newest_file"] = {
                        "name": file_times[-1][0].name,
                        "modified": datetime.fromtimestamp(file_times[-1][1]).isoformat()
                    }

            return stats

        except Exception as e:
            logger.error(f"❌ 获取日志统计信息时出错: {e}")
            return {"error": str(e)}


# 创建全局日志配置实例
log_config = LogConfig()


def setup_logging():
    """设置日志系统"""
    log_config.setup_logger()


def cleanup_logs():
    """清理过期日志"""
    log_config.cleanup_old_logs()


def get_log_stats():
    """获取日志统计信息"""
    return log_config.get_log_stats()