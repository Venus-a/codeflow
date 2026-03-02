# CodeFlow - 简洁的 AI 编程助手

基于 OpenCode 的简洁 AI 编程助手，专注于开发效率。

## 功能特性

- **💬 直接对话** - 无需复杂配置，输入问题即可开始
- **🔄 操作追踪** - 显示 OpenCode 的操作步骤（Write/Read/Edit 文件）
- **📄 文件管理** - 生成的文件统一保存在 `data/workspace/` 目录
- **✅ 状态反馈** - 清晰的完成状态和错误提示

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 安装 OpenCode

```bash
npm i -g opencode-ai
```

### 配置 OpenCode

OpenCode 的 Minimax API 在 OpenCode 内部配置，无需在网页端额外设置。

### 启动应用

```bash
streamlit run frontend/app.py
```

访问 http://localhost:8501 开始使用。

## 项目结构

```
codeflow/
├── frontend/
│   └── app.py          # Streamlit 前端（简洁版）
├── backend/            # 后端模块（暂未整合）
│   ├── workflow/       # 流程引擎
│   ├── prompthub/      # PromptHub 管理
│   └── executor/       # 执行器
├── prompts/            # PromptHub 提示词模板（暂未整合）
├── data/
│   └── workspace/      # 生成的文件保存目录
└── requirements.txt
```

## 使用示例

```
你: 创建一个 hello.py 文件，里面写一个打印 hello world 的函数

AI: 🔄 Write hello.py
    ✅ Wrote file successfully.

    📄 生成的文件 (保存于 data/workspace/):
    📄 hello.py ✅
```

## TODO

- [ ] 整合 PromptHub 提示词库
- [ ] 添加流程模式（TDD/传统开发）
- [ ] 支持多会话管理
- [ ] 添加代码预览功能

## 许可证

MIT
