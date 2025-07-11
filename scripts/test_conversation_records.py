#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对话记录功能测试脚本
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db_utils import (
    get_conn,
    save_conversation_record,
    get_conversation_history,
    get_conversation_stats
)


def test_conversation_records():
    """测试对话记录功能"""
    print("🧪 开始测试对话记录功能...")
    
    # 测试数据
    test_conversations = [
        {
            "conversation_id": "test_conv_001",
            "sender_id": "user_001",
            "user_question": "今天天气怎么样？",
            "ai_response": "今天天气晴朗，温度适宜，建议您外出活动。",
            "message_type": "text",
            "response_time_ms": 1200,
            "agent_type": "WeatherAgent"
        },
        {
            "conversation_id": "test_conv_001",
            "sender_id": "user_001",
            "user_question": "帮我查询数据库中的用户信息",
            "ai_response": "已为您查询到用户信息，共找到15条记录。",
            "message_type": "text",
            "response_time_ms": 2500,
            "agent_type": "SQLAgent"
        },
        {
            "conversation_id": "test_conv_002",
            "sender_id": "user_002",
            "user_question": "创建一个JIRA工单",
            "ai_response": "已成功创建JIRA工单，工单号：PROJ-123",
            "message_type": "markdown",
            "response_time_ms": 3200,
            "agent_type": "JiraAgent"
        },
        {
            "conversation_id": "test_conv_002",
            "sender_id": "user_002",
            "user_question": "查看服务器状态",
            "ai_response": "服务器运行正常，CPU使用率：15%，内存使用率：45%",
            "message_type": "text",
            "response_time_ms": 1800,
            "agent_type": "ServerAgent"
        },
        {
            "conversation_id": "test_conv_003",
            "sender_id": "user_003",
            "user_question": "搜索知识库中关于API的文档",
            "ai_response": "找到3篇相关文档：API设计规范、API测试指南、API安全最佳实践",
            "message_type": "markdown",
            "response_time_ms": 1500,
            "agent_type": "KnowledgeAgent"
        }
    ]
    
    print("📝 插入测试对话记录...")
    record_ids = []
    
    for conv in test_conversations:
        try:
            record_id = save_conversation_record(**conv)
            record_ids.append(record_id)
            print(f"✅ 成功插入记录 ID: {record_id}")
        except Exception as e:
            print(f"❌ 插入记录失败: {e}")
            return False
    
    print(f"\n📊 成功插入 {len(record_ids)} 条对话记录")
    
    # 测试查询功能
    print("\n🔍 测试查询功能...")
    
    # 1. 查询所有记录
    print("\n1. 查询所有记录:")
    all_records = get_conversation_history(limit=10)
    print(f"   总记录数: {len(all_records)}")
    for record in all_records[:3]:  # 只显示前3条
        print(f"   - ID: {record[0]}, 用户: {record[2]}, 问题: {record[3][:30]}...")
    
    # 2. 按会话ID查询
    print("\n2. 按会话ID查询 (test_conv_001):")
    conv_records = get_conversation_history(conversation_id="test_conv_001")
    print(f"   会话记录数: {len(conv_records)}")
    for record in conv_records:
        print(f"   - 问题: {record[3][:30]}..., 智能体: {record[7]}")
    
    # 3. 按用户ID查询
    print("\n3. 按用户ID查询 (user_002):")
    user_records = get_conversation_history(sender_id="user_002")
    print(f"   用户记录数: {len(user_records)}")
    for record in user_records:
        print(f"   - 问题: {record[3][:30]}..., 响应时间: {record[6]}ms")
    
    # 4. 测试统计功能
    print("\n📈 测试统计功能...")
    
    # 总体统计
    print("\n1. 总体统计:")
    stats = get_conversation_stats()
    print(f"   总对话数: {stats['total_conversations']}")
    print(f"   独立用户数: {stats['unique_users']}")
    print(f"   独立会话数: {stats['unique_conversations']}")
    print(f"   平均响应时间: {stats['avg_response_time_ms']:.1f}ms")
    
    print("\n   智能体分布:")
    for agent in stats['agent_distribution']:
        print(f"   - {agent['agent_type']}: {agent['count']} 次")
    
    print("\n   消息类型分布:")
    for msg_type in stats['message_type_distribution']:
        print(f"   - {msg_type['message_type']}: {msg_type['count']} 次")
    
    # 按用户统计
    print("\n2. 用户统计 (user_001):")
    user_stats = get_conversation_stats(sender_id="user_001")
    print(f"   用户对话数: {user_stats['total_conversations']}")
    print(f"   平均响应时间: {user_stats['avg_response_time_ms']:.1f}ms")
    
    # 按会话统计
    print("\n3. 会话统计 (test_conv_002):")
    conv_stats = get_conversation_stats(conversation_id="test_conv_002")
    print(f"   会话对话数: {conv_stats['total_conversations']}")
    print(f"   参与用户数: {conv_stats['unique_users']}")
    
    print("\n✅ 对话记录功能测试完成！")
    return True


def test_database_schema():
    """测试数据库表结构"""
    print("\n🗄️ 测试数据库表结构...")
    
    conn = get_conn()
    
    # 检查表是否存在
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_records'"
    )
    table_exists = cursor.fetchone()
    
    if table_exists:
        print("✅ conversation_records 表已存在")
        
        # 检查表结构
        cursor = conn.execute("PRAGMA table_info(conversation_records)")
        columns = cursor.fetchall()
        
        print("📋 表结构:")
        for col in columns:
            print(f"   - {col[1]} {col[2]} {'NOT NULL' if col[3] else ''} {'PRIMARY KEY' if col[5] else ''}")
        
        # 检查索引
        cursor = conn.execute("PRAGMA index_list(conversation_records)")
        indexes = cursor.fetchall()
        
        print("🔍 索引:")
        for idx in indexes:
            print(f"   - {idx[1]}")
    else:
        print("❌ conversation_records 表不存在")
        return False
    
    conn.close()
    return True


def cleanup_test_data():
    """清理测试数据"""
    print("\n🧹 清理测试数据...")
    
    conn = get_conn()
    
    # 删除测试数据
    cursor = conn.execute(
        "DELETE FROM conversation_records WHERE conversation_id LIKE 'test_conv_%'"
    )
    deleted_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"🗑️ 已删除 {deleted_count} 条测试记录")


def main():
    """主函数"""
    print("🚀 对话记录功能测试开始")
    print("=" * 50)
    
    try:
        # 测试数据库表结构
        if not test_database_schema():
            print("❌ 数据库表结构测试失败")
            return
        
        # 测试对话记录功能
        if not test_conversation_records():
            print("❌ 对话记录功能测试失败")
            return
        
        # 询问是否清理测试数据
        response = input("\n是否清理测试数据？(y/N): ").strip().lower()
        if response in ['y', 'yes']:
            cleanup_test_data()
        
        print("\n🎉 所有测试完成！")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
