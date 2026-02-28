# CodeFlow - 流程化 AI 编程助手

基于 OpenCode + Minimax + PromptHub 的流程化编程辅助工具。

## 功能特性

- **流程引导** - TDD、传统开发等规范化流程
- **PromptHub 集成** - Web 管理提示词模板
- **OpenCode 调用** - 可选择使用 OpenCode 或直接调用 Minimax
- **手动/自动模式** - 灵活切换执行模式
- **进度跟踪** - 实时查看开发进度

## 项目结构

```
codeflow/
├── backend/           # 后端服务
│   ├── workflow/      # 流程引擎
│   ├── prompthub/     # PromptHub 集成
│   ├── executor/      # 执行器 (OpenCode/Minimax)
│   └── api/           # FastAPI 接口
├── frontend/          # Web 管理面板 (Streamlit)
├── prompts/           # PromptHub 提示词
└── data/              # 数据存储
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env

# 启动后端
python -m backend.main

# 启动前端
streamlit run frontend/app.py
```

## 开发流程

1. 选择开发策略（TDD/传统）
2. 系统自动加载 PromptHub 对应流程
3. 逐步执行，每步可查看提示词
4. 选择使用 OpenCode 或直接 Minimax
5. 跟踪进度，完成开发
