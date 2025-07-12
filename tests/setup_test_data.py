#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
设置测试数据脚本
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db_utils import get_conn
from loguru import logger


def setup_test_user():
    """创建测试用户数据"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # 插入测试用户数据
        cursor.execute("""
            INSERT OR REPLACE INTO user_jira_account 
            (user_id, jira_username, jira_password) 
            VALUES (?, ?, ?)
        """, ("test_user_001", "test_jira_user", "test_password"))
        
        conn.commit()
        conn.close()
        
        logger.info("✅ 测试用户数据创建成功")
        logger.info("👤 用户ID: test_user_001")
        
    except Exception as e:
        logger.error(f"❌ 创建测试用户数据失败: {e}")


def setup_test_weekly_logs():
    """创建测试周报日志数据"""
    try:
        from datetime import datetime, timedelta
        from app.db_utils import save_weekly_log
        
        # 获取本周一的日期
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        
        # 创建周一到周四的测试日志
        test_logs = [
            {
                "date_offset": 0,  # 周一
                "content": "周一：完成了钉钉AI机器人项目的需求分析，与产品经理讨论了周报功能的技术方案，开始设计数据库结构和API接口。"
            },
            {
                "date_offset": 1,  # 周二
                "content": "周二：完成了数据库设计，新增weekly_logs表，实现了周报相关的数据库操作函数，开始开发AI智能体模块。"
            },
            {
                "date_offset": 2,  # 周三
                "content": "周三：完成了WeeklyReportAgent双智能体协作模块，实现了总结智能体和检察官智能体，进行了单元测试和功能验证。"
            },
            {
                "date_offset": 3,  # 周四
                "content": "周四：完成了钉钉日报API集成，实现了DingTalkReportService服务，完成了API接口开发，准备明天的功能测试。"
            }
        ]
        
        for log_data in test_logs:
            log_date = (monday + timedelta(days=log_data["date_offset"])).strftime('%Y-%m-%d')
            
            log_id = save_weekly_log(
                user_id="test_user_001",
                week_start=log_date,
                week_end=log_date,
                log_content=log_data["content"]
            )
            
            logger.info(f"📝 创建测试日志: {log_date} (ID: {log_id})")
        
        logger.info("✅ 测试周报日志数据创建成功")
        
    except Exception as e:
        logger.error(f"❌ 创建测试周报日志数据失败: {e}")


def main():
    """主函数"""
    logger.info("🔧 开始设置测试数据")
    
    # 创建测试用户
    setup_test_user()
    
    # 创建测试周报日志
    setup_test_weekly_logs()
    
    logger.info("🎉 测试数据设置完成")


if __name__ == "__main__":
    main()
