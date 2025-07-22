# 文档索引

## 🎯 核心架构文档

### **热重载解决方案**
- **`final-solution-summary.md`** - 最终完整解决方案总结
  - 问题根源分析（Mac → Windows 平台差异）
  - 依赖注入架构 + Windows 优化
  - 完整的技术细节和使用指南

- **`windows-hotreload-solution.md`** - Windows 特定技术解决方案
  - Windows 平台的线程管理差异
  - 强制退出机制的技术实现
  - 跨平台兼容性方案

### **架构设计**
- **`dependency-injection-guide.md`** - 依赖注入架构完整指南
  - 架构设计原理
  - 容器配置和使用
  - 最佳实践和示例

## 🔧 功能增强文档

### **AI 功能**
- **`GEMINI_INTEGRATION.md`** - Gemini AI 集成指南
- **`ai-agent-method-fix.md`** - AI 代理方法修复
- **`vector-memory-fix.md`** - 向量内存修复
- **`generate-summary-enhancement.md`** - 摘要生成增强

### **团队协作**
- **`autogen-team-guide.md`** - AutoGen 团队指南
- **`ssh-intelligent-command-team.md`** - SSH 智能命令团队

### **服务功能**
- **`CREATE_REPORT_REFACTOR_SUMMARY.md`** - /create-report 接口改造总结
  - 模版名称替代ID的参数优化
  - 钉钉模版信息动态获取
  - 智能内容格式化和AI增强
  - 上周工作列表化处理
- **`weekly-report-service-fix.md`** - 周报服务修复
- **`weekly_report_flow.md`** - 周报流程
- **`conversation_management.md`** - 对话管理
- **`conversation_records.md`** - 对话记录

### **系统维护**
- **`logging-system-flow.md`** - 日志系统流程
- **`ssh-tool-debug-report.md`** - SSH 工具调试报告
- **`date-format-fix.md`** - 日期格式修复

## 📚 文档说明

### **已清理的过时文档**
以下文档已被删除，因为它们已过时或被更好的解决方案替代：
- ❌ `hot-reload-fix.md` - 早期的热重载修复尝试
- ❌ `hot-reload-root-cause-analysis.md` - 错误的根因分析
- ❌ `startup-modes-guide.md` - 中间的启动模式方案
- ❌ `dependency-injection-implementation.md` - 重复的依赖注入文档

### **文档维护原则**
1. **保留最新最完整的解决方案**
2. **删除过时和重复的文档**
3. **保持技术文档的准确性**
4. **优先保留有实际价值的技术细节**

## 🎉 推荐阅读顺序

### **新开发者**
1. `dependency-injection-guide.md` - 了解架构设计
2. `final-solution-summary.md` - 了解核心问题和解决方案

### **遇到热重载问题**
1. `final-solution-summary.md` - 完整解决方案
2. `windows-hotreload-solution.md` - Windows 特定技术细节

### **功能开发**
1. 查看对应的功能增强文档
2. 参考 `dependency-injection-guide.md` 了解如何正确使用依赖注入

### **周报接口改造**
1. `CREATE_REPORT_REFACTOR_SUMMARY.md` - 了解最新的接口改造详情
2. 查看改造后的API使用示例和测试方法

---

**最后更新**: 2025-07-22
**维护者**: AI Assistant
**状态**: 已添加 /create-report 接口改造文档，保持最新状态
