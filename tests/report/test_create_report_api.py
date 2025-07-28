#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试改造后的 /create-report 接口
"""

import asyncio
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.dingtalk.report_service import DingTalkReportService
from app.services.weekly_report_service import WeeklyReportService

async def test_get_template_by_name():
    """测试获取模版信息"""
    print("=== 测试获取模版信息 ===")

    service = DingTalkReportService()
    template_name = "产品研发中心组长日报及周报(导入上篇)"
    user_id = "test_user"

    try:
        result = await service.get_template_by_name(template_name, user_id)
        if result:
            print(f"✅ 获取模版信息成功:")
            print(f"   模版ID: {result.get('id')}")
            print(f"   模版名称: {result.get('name')}")
            print(f"   字段数量: {len(result.get('fields', []))}")

            # 打印字段信息
            fields = result.get('fields', [])
            for field in fields:
                print(f"   - {field.get('field_name')} (sort: {field.get('sort')}, type: {field.get('type')})")
        else:
            print("❌ 获取模版信息失败")
    except Exception as e:
        print(f"❌ 测试异常: {e}")

def test_format_content_with_template():
    """测试根据模版格式化内容"""
    print("\n=== 测试内容格式化 ===")

    service = DingTalkReportService()

    # 模拟模版字段
    template_fields = [
        {"field_name": "今日完成工作", "sort": 0, "type": 1},
        {"field_name": "上周工作总结", "sort": 1, "type": 1},
        {"field_name": "本周工作计划", "sort": 2, "type": 1},
    ]

    # 模拟周报内容
    summary_content = """
### 今日完成工作
完成了API接口开发
完成了数据库设计
修复了几个重要bug

### 上周工作总结
完成了项目架构设计
实现了核心功能模块
进行了代码评审

### 本周工作计划
开始前端开发
完成单元测试
准备上线部署
"""

    try:
        result = service.format_weekly_report_content(summary_content, template_fields)
        print(f"✅ 格式化成功，生成 {len(result)} 个内容块:")

        for i, content in enumerate(result):
            print(f"   内容块 {i+1}:")
            print(f"     字段: {content.get('key')}")
            print(f"     排序: {content.get('sort')}")
            print(f"     内容: {content.get('content')[:50]}...")

            # 检查上周工作是否转换为列表格式
            if "上周工作" in content.get('key', ''):
                content_text = content.get('content', '')
                if content_text.strip().startswith('-'):
                    print(f"     ✅ 上周工作已转换为列表格式")
                else:
                    print(f"     ❌ 上周工作未转换为列表格式")

    except Exception as e:
        print(f"❌ 测试异常: {e}")

def test_convert_to_list_format():
    """测试列表格式转换"""
    print("\n=== 测试列表格式转换 ===")

    service = DingTalkReportService()

    test_cases = [
        "完成了项目架构设计\n实现了核心功能模块\n进行了代码评审",
        "1. 完成了项目架构设计\n2. 实现了核心功能模块\n3. 进行了代码评审",
        "- 已经是列表格式\n- 保持不变",
    ]

    for i, test_content in enumerate(test_cases):
        print(f"\n测试用例 {i+1}:")
        print(f"原始内容:\n{test_content}")

        result = service._convert_to_list_format(test_content)
        print(f"转换结果:\n{result}")

async def main():
    """主测试函数"""
    print("🚀 开始测试改造后的 /create-report 接口功能")

    # 测试获取模版信息（需要真实的钉钉API）
    # await test_get_template_by_name()

    # 测试内容格式化
    test_format_content_with_template()

    # 测试列表格式转换
    test_convert_to_list_format()

    print("\n✅ 所有测试完成")

if __name__ == "__main__":
    asyncio.run(main())
