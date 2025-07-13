#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对话记录清理工具

用法:
    python -m scripts.cleanup_conversation_logs --days 30
    
参数:
    --days: 保留天数，默认30天（删除30天前的记录）
    --dry-run: 仅显示将删除的记录数量，不实际删除
    --force: 跳过确认提示直接执行
"""

import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.conversation_log_service import conversation_log_service

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='清理指定天数前的对话记录')
    parser.add_argument('--days', type=int, default=30, help='保留天数，默认30天（删除30天前的记录）')
    parser.add_argument('--dry-run', action='store_true', help='仅显示将删除的记录数量，不实际删除')
    parser.add_argument('--force', action='store_true', help='跳过确认提示直接执行')
    
    args = parser.parse_args()
    
    if args.days < 7:
        logger.error("保留天数不能少于7天，请设置更大的值")
        return
    
    # 计算截止日期
    cutoff_date = datetime.now() - timedelta(days=args.days)
    cutoff_date_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
    
    logger.info(f"准备清理 {cutoff_date_str} 之前的对话记录")
    
    if args.dry_run:
        # 获取将被删除的记录数量
        count = await conversation_log_service.count_old_records(args.days)
        logger.info(f"将删除 {count} 条记录（试运行模式，不会实际删除）")
        return
    
    if not args.force:
        # 获取将被删除的记录数量
        count = await conversation_log_service.count_old_records(args.days)
        
        # 请求用户确认
        confirm = input(f"将删除 {count} 条记录，确认执行？(y/n): ")
        if confirm.lower() != 'y':
            logger.info("操作已取消")
            return
    
    # 执行清理
    result = await conversation_log_service.cleanup_old_records(args.days)
    
    if result["success"]:
        logger.info(f"清理成功! 已删除 {result.get('deleted_count', 0)} 条记录")
    else:
        logger.error(f"清理失败: {result.get('message', '未知错误')}")


if __name__ == "__main__":
    asyncio.run(main())
