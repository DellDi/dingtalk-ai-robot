#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对话记录功能使用示例
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db_utils import (
    save_conversation_record,
    get_conversation_history,
    get_conversation_stats
)


async def simulate_conversation_flow():
    """模拟完整的对话流程"""
    print("🤖 模拟钉钉机器人对话流程")
    print("=" * 50)
    
    # 模拟用户对话
    conversations = [
        {
            "conversation_id": "dingtalk_group_001",
            "sender_id": "employee_zhang",
            "user_question": "帮我查询一下今天的天气情况",
            "ai_response": "今天北京天气：晴，温度 15-25°C，空气质量良好，适合外出活动。",
            "agent_type": "WeatherAgent",
            "response_time_ms": 1200
        },
        {
            "conversation_id": "dingtalk_group_001", 
            "sender_id": "employee_li",
            "user_question": "创建一个关于系统优化的JIRA工单",
            "ai_response": "已成功创建JIRA工单：\n- 工单号：PROJ-2024-001\n- 标题：系统性能优化\n- 状态：待处理\n- 经办人：employee_li",
            "agent_type": "JiraAgent",
            "response_time_ms": 2800
        },
        {
            "conversation_id": "dingtalk_private_002",
            "sender_id": "employee_wang",
            "user_question": "查询数据库中最近一周的用户注册数据",
            "ai_response": "查询结果：\n- 总注册用户：156人\n- 日均注册：22.3人\n- 较上周增长：12.5%",
            "agent_type": "SQLAgent", 
            "response_time_ms": 3200
        }
    ]
    
    print("📝 记录对话信息...")
    for i, conv in enumerate(conversations, 1):
        record_id = save_conversation_record(
            conversation_id=conv["conversation_id"],
            sender_id=conv["sender_id"],
            user_question=conv["user_question"],
            ai_response=conv["ai_response"],
            message_type="text",
            response_time_ms=conv["response_time_ms"],
            agent_type=conv["agent_type"]
        )
        print(f"✅ 对话 {i} 已记录，ID: {record_id}")
    
    print("\n📊 分析对话数据...")
    
    # 1. 查看群聊对话历史
    print("\n1. 群聊对话历史 (dingtalk_group_001):")
    group_history = get_conversation_history(conversation_id="dingtalk_group_001")
    for record in group_history:
        print(f"   👤 {record[2]}: {record[3][:40]}...")
        print(f"   🤖 回复: {record[4][:40]}... (耗时: {record[6]}ms)")
        print()
    
    # 2. 查看用户对话历史
    print("2. 用户对话历史 (employee_wang):")
    user_history = get_conversation_history(sender_id="employee_wang")
    for record in user_history:
        print(f"   ❓ 问题: {record[3]}")
        print(f"   ✅ 回复: {record[4]}")
        print(f"   🕒 时间: {record[8]}")
        print()
    
    # 3. 生成统计报告
    print("3. 整体统计报告:")
    stats = get_conversation_stats()
    
    print(f"   📈 总对话数: {stats['total_conversations']}")
    print(f"   👥 活跃用户: {stats['unique_users']}")
    print(f"   💬 活跃会话: {stats['unique_conversations']}")
    print(f"   ⚡ 平均响应时间: {stats['avg_response_time_ms']:.1f}ms")
    
    print("\n   🤖 智能体使用情况:")
    for agent in stats['agent_distribution']:
        print(f"      - {agent['agent_type']}: {agent['count']} 次")
    
    # 4. 性能分析
    print("\n4. 性能分析:")
    slow_responses = []
    fast_responses = []
    
    all_records = get_conversation_history(limit=100)
    for record in all_records:
        if record[6]:  # response_time_ms
            if record[6] > 2000:  # 超过2秒
                slow_responses.append(record)
            elif record[6] < 1500:  # 小于1.5秒
                fast_responses.append(record)
    
    print(f"   🐌 慢响应 (>2s): {len(slow_responses)} 次")
    print(f"   🚀 快响应 (<1.5s): {len(fast_responses)} 次")
    
    if slow_responses:
        print("   慢响应详情:")
        for record in slow_responses:
            print(f"      - {record[7]}: {record[6]}ms - {record[3][:30]}...")


async def generate_daily_report():
    """生成每日对话报告"""
    print("\n📋 生成每日对话报告")
    print("=" * 30)
    
    # 获取今天的统计数据
    today = datetime.now().strftime("%Y-%m-%d")
    stats = get_conversation_stats(start_date=today, end_date=today)
    
    print(f"📅 日期: {today}")
    print(f"💬 今日对话总数: {stats['total_conversations']}")
    print(f"👥 活跃用户数: {stats['unique_users']}")
    print(f"⚡ 平均响应时间: {stats['avg_response_time_ms']:.1f}ms" if stats['avg_response_time_ms'] else "⚡ 平均响应时间: 暂无数据")
    
    print("\n🤖 智能体使用排行:")
    for i, agent in enumerate(stats['agent_distribution'][:5], 1):
        print(f"   {i}. {agent['agent_type']}: {agent['count']} 次")
    
    print("\n📊 消息类型分布:")
    for msg_type in stats['message_type_distribution']:
        print(f"   - {msg_type['message_type']}: {msg_type['count']} 次")


async def user_behavior_analysis():
    """用户行为分析"""
    print("\n🔍 用户行为分析")
    print("=" * 20)
    
    # 获取所有用户的对话记录
    all_records = get_conversation_history(limit=1000)
    
    # 按用户分组统计
    user_stats = {}
    for record in all_records:
        user_id = record[2]
        if user_id not in user_stats:
            user_stats[user_id] = {
                'total_conversations': 0,
                'total_response_time': 0,
                'agents_used': set(),
                'last_conversation': record[8]
            }
        
        user_stats[user_id]['total_conversations'] += 1
        if record[6]:  # response_time_ms
            user_stats[user_id]['total_response_time'] += record[6]
        if record[7]:  # agent_type
            user_stats[user_id]['agents_used'].add(record[7])
    
    print("👥 用户活跃度排行:")
    sorted_users = sorted(user_stats.items(), key=lambda x: x[1]['total_conversations'], reverse=True)
    
    for i, (user_id, stats) in enumerate(sorted_users[:5], 1):
        avg_response = stats['total_response_time'] / stats['total_conversations'] if stats['total_conversations'] > 0 else 0
        print(f"   {i}. {user_id}:")
        print(f"      - 对话次数: {stats['total_conversations']}")
        print(f"      - 平均响应时间: {avg_response:.1f}ms")
        print(f"      - 使用智能体: {len(stats['agents_used'])} 种")
        print(f"      - 最后活跃: {stats['last_conversation']}")
        print()


async def cleanup_example_data():
    """清理示例数据"""
    print("\n🧹 清理示例数据...")
    
    from app.db_utils import get_conn
    conn = get_conn()
    
    # 删除示例数据
    cursor = conn.execute("""
        DELETE FROM conversation_records 
        WHERE sender_id IN ('employee_zhang', 'employee_li', 'employee_wang')
    """)
    deleted_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"🗑️ 已删除 {deleted_count} 条示例记录")


async def main():
    """主函数"""
    print("🚀 对话记录功能使用示例")
    print("=" * 60)
    
    try:
        # 1. 模拟对话流程
        await simulate_conversation_flow()
        
        # 2. 生成每日报告
        await generate_daily_report()
        
        # 3. 用户行为分析
        await user_behavior_analysis()
        
        # 4. 清理示例数据
        await cleanup_example_data()
        
        print("\n🎉 示例演示完成！")
        print("\n💡 提示：")
        print("   - 在实际使用中，对话记录会自动保存")
        print("   - 可以通过API接口查询对话历史和统计信息")
        print("   - 建议定期分析数据以优化用户体验")
        
    except Exception as e:
        print(f"❌ 示例运行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
