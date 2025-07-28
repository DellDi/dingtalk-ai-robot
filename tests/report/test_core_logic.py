#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试核心逻辑，不依赖外部模块
"""

def convert_to_list_format(content):
    """
    将内容转换为列表格式（每行前面加"-"）
    """
    if not content.strip():
        return content

    lines = content.strip().split('\n')
    formatted_lines = []

    for line in lines:
        line = line.strip()
        if line:
            # 如果行已经是列表格式，保持不变
            if line.startswith('-') or line.startswith('*') or line.startswith('+'):
                formatted_lines.append(line)
            # 如果是数字列表，转换为无序列表
            elif line.split('.')[0].strip().isdigit():
                # 移除数字前缀，添加"-"
                content_part = '.'.join(line.split('.')[1:]).strip()
                if content_part:
                    formatted_lines.append(f"- {content_part}")
            else:
                # 普通文本行，添加"-"前缀
                formatted_lines.append(f"- {line}")

    return '\n'.join(formatted_lines)

def parse_markdown_sections(content):
    """
    解析Markdown内容的不同部分
    """
    sections = {}
    current_section = None
    current_content = []

    lines = content.split("\n")

    for line in lines:
        line = line.strip()

        # 检查是否是标题行
        if line.startswith("#"):
            # 保存上一个部分
            if current_section and current_content:
                sections[current_section] = "\n".join(current_content).strip()

            # 开始新部分
            current_section = line.lstrip("#").strip()
            current_content = []
        else:
            # 添加到当前部分
            if line:  # 忽略空行
                current_content.append(line)

    # 保存最后一个部分
    if current_section and current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections

def match_content_for_field(field_name, sections):
    """
    为字段匹配对应的内容
    """
    # 定义字段名称到内容部分的映射关系
    field_mappings = {
        # 工作完成相关
        "本周工作完成情况": ["本周工作完成情况", "工作完成", "完成工作", "本周完成"],
        "今日完成工作": ["今日完成工作", "今日工作", "完成工作"],
        "本周完成工作": ["本周完成工作", "本周工作完成情况", "工作完成"],
        
        # 项目进展相关
        "重点项目进展": ["重点项目进展", "项目进展", "项目情况"],
        "项目进展": ["项目进展", "重点项目进展", "项目情况"],
        
        # 问题解决相关
        "问题及解决方案": ["问题及解决方案", "问题解决", "遇到问题", "解决方案"],
        "未完成工作": ["未完成工作", "待完成", "遗留问题"],
        
        # 计划相关
        "下周工作计划": ["下周工作计划", "下周计划", "工作计划", "下周安排"],
        "明日工作计划": ["明日工作计划", "明日计划", "明天计划"],
        
        # 上周工作相关
        "上周工作": ["上周工作", "上周完成", "上周情况"],
        "上周工作总结": ["上周工作总结", "上周工作", "上周完成"],
    }

    # 尝试精确匹配
    if field_name in sections:
        return sections[field_name]

    # 尝试通过映射关系匹配
    possible_keys = field_mappings.get(field_name, [field_name])
    for key in possible_keys:
        if key in sections:
            return sections[key]

    # 尝试模糊匹配（包含关系）
    for section_key, section_content in sections.items():
        if any(keyword in section_key for keyword in possible_keys):
            return section_content
        if any(keyword in field_name for keyword in [section_key]):
            return section_content

    return ""

def test_convert_to_list_format():
    """测试列表格式转换"""
    print("=== 测试列表格式转换 ===")
    
    test_cases = [
        "完成了项目架构设计\n实现了核心功能模块\n进行了代码评审",
        "1. 完成了项目架构设计\n2. 实现了核心功能模块\n3. 进行了代码评审",
        "- 已经是列表格式\n- 保持不变",
    ]
    
    for i, test_content in enumerate(test_cases):
        print(f"\n测试用例 {i+1}:")
        print(f"原始内容:\n{test_content}")
        
        result = convert_to_list_format(test_content)
        print(f"转换结果:\n{result}")

def test_content_matching():
    """测试内容匹配"""
    print("\n=== 测试内容匹配 ===")
    
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
    
    sections = parse_markdown_sections(summary_content)
    print(f"解析出 {len(sections)} 个部分:")
    for key, value in sections.items():
        print(f"  - {key}: {value[:30]}...")
    
    # 测试字段匹配
    test_fields = ["今日完成工作", "上周工作总结", "本周工作计划", "不存在的字段"]
    
    print(f"\n字段匹配测试:")
    for field in test_fields:
        matched_content = match_content_for_field(field, sections)
        if matched_content:
            print(f"  ✅ {field}: 匹配成功")
            # 如果是上周工作，测试列表转换
            if "上周工作" in field:
                list_format = convert_to_list_format(matched_content)
                print(f"     列表格式: {list_format[:50]}...")
        else:
            print(f"  ❌ {field}: 未匹配")

def main():
    """主测试函数"""
    print("🚀 开始测试核心逻辑")
    
    # 测试列表格式转换
    test_convert_to_list_format()
    
    # 测试内容匹配
    test_content_matching()
    
    print("\n✅ 所有测试完成")

if __name__ == "__main__":
    main()
