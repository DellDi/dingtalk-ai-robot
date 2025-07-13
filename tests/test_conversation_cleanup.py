#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试对话记录清理功能
"""

import os
import sys
import asyncio
import unittest
from datetime import datetime, timedelta
import sqlite3
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.conversation_log_service import conversation_log_service
from app.db_utils import get_conn, save_conversation_record

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestConversationCleanup(unittest.TestCase):
    """测试对话记录清理功能"""

    def setUp(self):
        """测试前准备"""
        # 使用内存数据库进行测试
        self.db_path = ":memory:"
        self.conn = sqlite3.connect(self.db_path)
        
        # 创建对话记录表
        self.conn.execute('''
        CREATE TABLE IF NOT EXISTS conversation_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            user_question TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            message_type TEXT,
            response_time_ms INTEGER,
            agent_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        self.conn.commit()
        
        # 插入测试数据
        self._insert_test_data()
    
    def _insert_test_data(self):
        """插入测试数据"""
        # 当前时间
        now = datetime.now()
        
        # 插入30条记录，其中10条是10天前的，10条是20天前的，10条是30天前的
        for i in range(30):
            days_ago = 10
            if i >= 10 and i < 20:
                days_ago = 20
            elif i >= 20:
                days_ago = 30
                
            record_time = now - timedelta(days=days_ago)
            
            self.conn.execute(
                '''
                INSERT INTO conversation_records 
                (conversation_id, sender_id, user_question, ai_response, message_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    f"conv_{i}",
                    f"user_{i % 5}",
                    f"测试问题 {i}",
                    f"测试回答 {i}",
                    "text",
                    record_time.strftime("%Y-%m-%d %H:%M:%S"),
                    record_time.strftime("%Y-%m-%d %H:%M:%S")
                )
            )
        
        self.conn.commit()
        logger.info("已插入30条测试记录")
        
        # 验证插入是否成功
        count = self.conn.execute("SELECT COUNT(*) FROM conversation_records").fetchone()[0]
        logger.info(f"当前记录总数: {count}")
    
    def tearDown(self):
        """测试后清理"""
        self.conn.close()
    
    def test_cleanup_old_records(self):
        """测试清理旧记录"""
        # 使用异步运行清理函数
        async def run_test():
            # 模拟conversation_log_service的cleanup_old_records方法
            # 由于我们使用的是内存数据库，需要模拟实际的清理逻辑
            
            # 清理15天前的记录
            cutoff_days = 15
            cutoff_date = datetime.now() - timedelta(days=cutoff_days)
            cutoff_date_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # 执行删除
            cursor = self.conn.cursor()
            cursor.execute(
                "DELETE FROM conversation_records WHERE created_at < ?",
                (cutoff_date_str,)
            )
            deleted_count = cursor.rowcount
            self.conn.commit()
            
            # 检查剩余记录数
            remaining = self.conn.execute("SELECT COUNT(*) FROM conversation_records").fetchone()[0]
            
            logger.info(f"已删除 {deleted_count} 条记录")
            logger.info(f"剩余记录数: {remaining}")
            
            # 验证删除结果
            self.assertEqual(deleted_count, 20)  # 应该删除20条记录（20天前和30天前的）
            self.assertEqual(remaining, 10)      # 应该剩下10条记录（10天前的）
            
            # 验证剩余的记录都是10天前的
            records = self.conn.execute("SELECT created_at FROM conversation_records").fetchall()
            for record in records:
                record_date = datetime.strptime(record[0], "%Y-%m-%d %H:%M:%S")
                days_diff = (datetime.now() - record_date).days
                self.assertLessEqual(days_diff, 15)  # 所有记录应该都是15天内的
        
        # 运行异步测试
        asyncio.run(run_test())
    
    def test_actual_service_cleanup(self):
        """测试实际服务的清理功能"""
        # 这个测试需要在实际环境中运行，这里只是演示
        async def run_actual_test():
            try:
                # 保存一些测试记录
                now = datetime.now()
                
                # 创建一些测试记录
                for i in range(5):
                    # 创建一条当前时间的记录
                    await conversation_log_service.save_record(
                        conversation_id=f"test_conv_{i}",
                        sender_id=f"test_user_{i}",
                        user_question=f"测试问题 {i}",
                        ai_response=f"测试回答 {i}",
                        message_type="text"
                    )
                
                logger.info("已创建5条测试记录")
                
                # 执行清理（清理7天前的记录，不应该影响我们刚创建的记录）
                result = await conversation_log_service.cleanup_old_records(days=7)
                
                logger.info(f"清理结果: {result}")
                self.assertTrue(result["success"])
                
                # 验证我们的记录仍然存在
                history = await conversation_log_service.get_history(limit=10)
                self.assertGreaterEqual(len(history), 5)
                
                logger.info("测试通过: 新创建的记录未被清理")
                
            except Exception as e:
                logger.error(f"测试失败: {str(e)}")
                self.fail(f"测试异常: {str(e)}")
        
        # 注意：这个测试在实际环境中会操作真实数据库，谨慎运行
        # 在这里我们跳过实际执行
        logger.info("跳过实际服务测试，因为它会操作真实数据库")
        # asyncio.run(run_actual_test())


if __name__ == "__main__":
    unittest.main()
