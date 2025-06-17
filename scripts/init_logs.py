#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日志目录初始化脚本
"""

import os
from pathlib import Path


def init_logs_directory():
    """初始化日志目录"""
    log_dir = Path("./logs")

    # 创建日志目录
    log_dir.mkdir(exist_ok=True)

    # 创建 .gitkeep 文件以保持目录结构
    gitkeep_file = log_dir / ".gitkeep"
    if not gitkeep_file.exists():
        gitkeep_file.touch()

    # 创建 .gitignore 文件
    gitignore_file = log_dir / ".gitignore"
    if not gitignore_file.exists():
        gitignore_content = """# 忽略所有日志文件
*.log
*.log.*
*.zip

# 但保留 .gitkeep 文件
!.gitkeep
"""
        gitignore_file.write_text(gitignore_content, encoding="utf-8")

    print(f"✅ 日志目录初始化完成: {log_dir.absolute()}")
    print(f"📁 目录结构:")
    print(f"   {log_dir}/")
    print(f"   ├── .gitkeep")
    print(f"   └── .gitignore")


if __name__ == "__main__":
    init_logs_directory()