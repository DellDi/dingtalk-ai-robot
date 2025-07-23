# 📋 /create-report 接口改造总结

## 🎯 改造目标

根据需求对 `/create-report` 接口进行以下改造：

1. **参数调整**: `template_id` → `template_name`，默认值为 "产品研发中心组长日报及周报(导入上篇)"
2. **模版获取**: 调用钉钉API获取日志模版信息
3. **内容格式化**: 根据模版字段动态格式化内容，特殊处理"上周工作"字段
4. **智能体集成**: 支持额外模版内容，调用周报智能体生成最终版本

## 🔧 具体改造内容

### 1. API模型修改 (`app/api/v1/weekly_report.py`)

**修改前:**
```python
class CreateReportRequest(BaseModel):
    summary_content: str = Field(..., description="周报总结内容")
    user_id: Optional[str] = Field(None, description="用户ID，为空则使用第一个用户")
    template_id: Optional[str] = Field(None, description="钉钉日报模版ID")
```

**修改后:**
```python
class CreateReportRequest(BaseModel):
    summary_content: str = Field(..., description="周报总结内容")
    user_id: Optional[str] = Field(None, description="用户ID，为空则使用第一个用户")
    template_name: str = Field("产品研发中心组长日报及周报(导入上篇)", description="钉钉日报模版名称")
    template_content: Optional[str] = Field(None, description="额外的模版内容，如果提供将与周报内容结合生成最终版本")
```

### 2. 钉钉服务增强 (`app/services/dingtalk/report_service.py`)

#### 新增获取模版信息方法
```python
async def get_template_by_name(self, template_name: str, user_id: str) -> Optional[Dict]:
    """根据模版名称获取日志模版信息"""
    # 调用 POST https://oapi.dingtalk.com/topapi/report/template/getbyname
```

#### 改造内容格式化方法
```python
def format_weekly_report_content(
    self,
    summary_content: str,
    template_fields: List[Dict] = None
) -> List[Dict[str, Any]]:
    """根据模版字段动态格式化内容"""
```

#### 新增辅助方法
- `_format_content_by_template_fields()`: 根据模版字段格式化
- `_convert_to_list_format()`: 转换"上周工作"为列表格式

### 3. 周报服务升级 (`app/services/weekly_report_service.py`)

**修改方法签名:**
```python
async def create_and_send_weekly_report(
    self,
    summary_content: str,
    user_id: str = None,
    template_name: str = "产品研发中心组长日报及周报(导入上篇)",
    template_content: str = None
) -> Dict[str, Any]:
```

**新增处理流程:**
1. 根据 `template_name` 获取模版信息
2. 如果提供了 `template_content`，调用AI智能体生成最终内容
3. 根据模版字段格式化内容
4. 创建钉钉日报

## 🚀 核心功能特性

### 1. 智能字段匹配
- 支持精确匹配、映射匹配、模糊匹配
- 预定义常见字段映射关系
- 自动适配不同模版结构

### 2. 上周工作列表化
- 自动检测包含"上周工作"的字段
- 将内容转换为列表格式（添加"-"前缀）
- 支持多种原始格式（普通文本、数字列表、已有列表）

### 3. AI智能体集成
- 支持额外模版内容输入
- 调用周报智能体生成最终版本
- 智能合并原始内容和模版内容

### 4. 向下兼容
- 保持原有API结构
- 支持无模版字段的默认格式化
- 错误处理和降级机制

## 📊 测试验证

### 核心逻辑测试 ✅
```bash
python3 test_core_logic.py
```
- ✅ 列表格式转换功能
- ✅ Markdown内容解析
- ✅ 字段智能匹配
- ✅ 上周工作列表化

### API接口测试
```bash
python3 test_api_request.py
```
测试场景：
- 带额外模版内容的完整流程
- 不带额外模版内容的基础流程
- 错误处理和边界情况

## 🔄 API使用示例

### 基础使用（仅模版名称）
```json
POST /api/v1/weekly-report/create-report
{
  "summary_content": "### 本周工作完成情况\n- 完成了功能开发\n### 上周工作总结\n完成了设计\n实现了核心模块",
  "user_id": "test_user",
  "template_name": "产品研发中心组长日报及周报(导入上篇)"
}
```

### 高级使用（含额外模版内容）
```json
POST /api/v1/weekly-report/create-report
{
  "summary_content": "### 本周工作完成情况\n- 完成了功能开发",
  "user_id": "test_user",
  "template_name": "产品研发中心组长日报及周报(导入上篇)",
  "template_content": "请重点突出项目进展和风险控制"
}
```

## 📈 改造效果

1. **✅ 参数优化**: 使用更直观的模版名称替代ID
2. **✅ 动态适配**: 根据实际模版字段动态生成内容
3. **✅ 智能处理**: 自动识别并格式化"上周工作"内容
4. **✅ AI增强**: 支持模版内容的智能合并
5. **✅ 向下兼容**: 保持原有功能不受影响

## 🔧 部署说明

1. 确保钉钉API配置正确
2. 验证模版名称存在于钉钉系统中
3. 测试AI智能体功能正常
4. 检查日志输出确认各步骤执行状态

## 📝 注意事项

- 模版名称必须在钉钉系统中存在
- 用户ID必须有权限访问指定模版
- AI智能体调用可能需要额外时间
- 建议在生产环境前进行充分测试
