## 代码风格与规范

- 语言：Python 3.10+
- 使用 ruff 作为统一的格式化与静态检查工具
  - 行长度：100
  - 缩进：4 空格
  - 字符串：双引号
  - 兼容 Black 格式化原则
- Import 规范：禁止相对导入点号，如 `from .doc_updater import update_documents`，应写为 `from doc_updater import update_documents`
- 注释：代码中不允许出现中文注释（项目规约）
- 文件结构：位于 `src/mcp_pymilvus_code_generate_helper` 的模块遵循单一职责原则，按功能拆分为 *connector*、*server*、*scheduler* 等脚本。