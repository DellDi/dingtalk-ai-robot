#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试改造后的 /create-report API 接口
"""

import json
import requests

def test_create_report_api():
    """测试创建日报API"""
    print("=== 测试 /create-report API ===")
    
    # API端点
    url = "http://localhost:8000/api/v1/weekly-report/create-report"
    
    # 测试数据
    test_data = {
        "summary_content": """
### 本周工作完成情况
- 完成了钉钉日报接口改造
- 实现了模版名称获取功能
- 优化了内容格式化逻辑

### 上周工作总结
完成了项目架构设计
实现了核心功能模块
进行了代码评审

### 下周工作计划
- 完善API文档
- 进行集成测试
- 准备上线部署
""",
        "user_id": "test_user_123",
        "template_name": "产品研发中心组长日报及周报(导入上篇)",
        "template_content": "额外的模版内容，用于测试AI智能体生成功能"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print(f"发送请求到: {url}")
        print(f"请求数据: {json.dumps(test_data, ensure_ascii=False, indent=2)}")
        
        response = requests.post(url, json=test_data, headers=headers, timeout=30)
        
        print(f"\n响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API调用成功:")
            print(f"   成功: {result.get('success')}")
            print(f"   消息: {result.get('message')}")
            
            data = result.get('data', {})
            if data:
                print(f"   报告ID: {data.get('report_id')}")
                print(f"   日志ID: {data.get('log_id')}")
                print(f"   用户ID: {data.get('user_id')}")
                print(f"   模版ID: {data.get('template_id')}")
                print(f"   模版名称: {data.get('template_name')}")
                print(f"   使用了模版内容: {data.get('used_template_content')}")
        else:
            print(f"❌ API调用失败:")
            print(f"   状态码: {response.status_code}")
            print(f"   响应内容: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败: 请确保服务器正在运行 (python -m uvicorn app.main:app --reload)")
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
    except Exception as e:
        print(f"❌ 请求异常: {e}")

def test_create_report_without_template_content():
    """测试不提供额外模版内容的情况"""
    print("\n=== 测试不提供额外模版内容 ===")
    
    url = "http://localhost:8000/api/v1/weekly-report/create-report"
    
    test_data = {
        "summary_content": """
### 本周工作完成情况
- 完成了基础功能开发
- 进行了代码测试

### 下周工作计划
- 继续优化功能
- 准备发布
""",
        "user_id": "test_user_456",
        "template_name": "产品研发中心组长日报及周报(导入上篇)"
        # 不提供 template_content
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=test_data, headers=headers, timeout=30)
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API调用成功 (无额外模版内容):")
            print(f"   成功: {result.get('success')}")
            print(f"   消息: {result.get('message')}")
            
            data = result.get('data', {})
            if data:
                print(f"   使用了模版内容: {data.get('used_template_content')}")
        else:
            print(f"❌ API调用失败: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败: 请确保服务器正在运行")
    except Exception as e:
        print(f"❌ 请求异常: {e}")

def main():
    """主测试函数"""
    print("🚀 开始测试改造后的 /create-report API")
    
    # 测试带额外模版内容的情况
    test_create_report_api()
    
    # 测试不带额外模版内容的情况
    test_create_report_without_template_content()
    
    print("\n✅ API测试完成")
    print("\n📝 使用说明:")
    print("1. 确保服务器正在运行: python -m uvicorn app.main:app --reload")
    print("2. 确保钉钉API配置正确")
    print("3. 检查日志输出以了解详细执行情况")

if __name__ == "__main__":
    main()
