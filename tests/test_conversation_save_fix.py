#!/usr/bin/env python3
"""
测试对话记录保存功能修复
"""

import sys
import os
import asyncio
from loguru import logger

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db_utils import save_conversation_record, get_conn


def test_database_connection():
    """测试数据库连接和表结构"""
    try:
        conn = get_conn()
        logger.info("✅ 数据库连接成功")
        
        # 检查conversation_records表是否存在
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_records'"
        )
        table_exists = cursor.fetchone()
        
        if table_exists:
            logger.info("✅ conversation_records表存在")
            
            # 检查表结构
            cursor = conn.execute("PRAGMA table_info(conversation_records)")
            columns = cursor.fetchall()
            logger.info(f"📊 表结构: {[col[1] for col in columns]}")
            
        else:
            logger.error("❌ conversation_records表不存在")
            return False
            
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据库连接测试失败: {e}")
        return False


def test_save_conversation_record():
    """测试保存对话记录功能"""
    try:
        # 测试数据
        test_data = {
            "conversation_id": "test_conv_123",
            "sender_id": "test_user_456",  # 确保这是字符串类型
            "user_question": "测试问题",
            "ai_response": "测试回复",
            "message_type": "text",
            "response_time_ms": 1500,
            "agent_type": "general"
        }
        
        logger.info("🧪 开始测试保存对话记录...")
        logger.info(f"📝 测试数据: {test_data}")
        
        # 验证sender_id类型
        logger.info(f"🔍 sender_id类型: {type(test_data['sender_id'])}")
        
        record_id = save_conversation_record(**test_data)
        
        if record_id:
            logger.info(f"✅ 对话记录保存成功，记录ID: {record_id}")
            return True
        else:
            logger.error("❌ 对话记录保存失败，未返回记录ID")
            return False
            
    except Exception as e:
        logger.error(f"❌ 保存对话记录测试失败: {e}")
        return False


def cleanup_test_data():
    """清理测试数据"""
    try:
        conn = get_conn()
        conn.execute("DELETE FROM conversation_records WHERE conversation_id LIKE 'test_conv_%'")
        conn.commit()
        conn.close()
        logger.info("🧹 测试数据清理完成")
    except Exception as e:
        logger.warning(f"⚠️ 清理测试数据时出错: {e}")


def main():
    """主测试函数"""
    logger.info("🚀 开始对话记录保存功能修复测试")
    logger.info("=" * 50)
    
    # 测试数据库连接
    if not test_database_connection():
        logger.error("❌ 数据库连接测试失败，退出测试")
        return
    
    # 清理旧的测试数据
    cleanup_test_data()
    
    # 测试保存功能
    success = test_save_conversation_record()
    
    # 清理测试数据
    cleanup_test_data()
    
    # 输出测试结果
    logger.info("=" * 50)
    if success:
        logger.info("🎉 所有测试通过！对话记录保存功能修复成功")
    else:
        logger.error("❌ 测试失败，请检查修复情况")


if __name__ == "__main__":
    main()
