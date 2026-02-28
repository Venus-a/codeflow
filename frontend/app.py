"""
CodeFlow - 流程化 AI 编程助手

Web 管理面板
"""
import os
import sys
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
import json

import streamlit as st
from datetime import datetime

# 添加后端模块路径
# 支持多种运行环境（streamlit、python 直接运行等）
try:
    backend_path = Path(__file__).resolve().parent.parent / "backend"
except NameError:
    # __file__ 未定义（如某些交互环境）
    backend_path = Path("../backend").resolve()

if not backend_path.exists():
    # 尝试当前目录
    backend_path = Path("./backend").resolve()

sys.path.insert(0, str(backend_path))

# 直接导入模块
from prompthub import PromptHubManager
from workflow import WorkflowEngine, ExecutionMode
from executor import ExecutorManager, MinimaxExecutor, OpenCodeExecutor


# ========================
# 配置
# ========================

st.set_page_config(
    page_title="CodeFlow",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================
# 配置管理
# ========================

CONFIG_FILE = Path(__file__).parent.parent / ".env"


def load_config():
    """加载配置"""
    config = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    return config


def save_config(config):
    """保存配置"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        for key, value in config.items():
            f.write(f"{key}={value}\n")


def get_config(key, default=""):
    """获取配置项"""
    config = load_config()
    return config.get(key, os.getenv(key, default))


@st.cache_data(ttl=60)  # 缓存60秒，可以通过重新加载刷新
def check_opencode():
    """检查 OpenCode 是否安装"""
    try:
        result = subprocess.run(
            ["opencode", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


# ========================
# 初始化
# ========================

@st.cache_resource
def init_prompthub():
    """初始化 PromptHub"""
    prompts_dir = get_config("PROMPTS_DIR", "./prompts")
    return PromptHubManager(prompts_dir)


@st.cache_resource
def init_executor_manager():
    """初始化执行器管理器"""
    manager = ExecutorManager()

    # 从配置文件读取 Minimax 配置
    minimax_config = {
        "api_key": get_config("MINIMAX_API_KEY", ""),
        "group_id": get_config("MINIMAX_GROUP_ID", ""),
        "model": "abab6.5s-chat",
        "enabled": True
    }
    manager.register("minimax", MinimaxExecutor(minimax_config))

    # 从配置文件读取 OpenCode 配置
    opencode_config = {
        "path": get_config("OPENCODE_PATH", "opencode"),
        "enabled": get_config("OPENCODE_ENABLED", "true").lower() == "true"
    }
    manager.register("opencode", OpenCodeExecutor(opencode_config))

    return manager


@st.cache_resource
def init_workflow_engine():
    """初始化流程引擎"""
    prompthub = init_prompthub()
    executor = init_executor_manager()
    sessions_dir = get_config("SESSIONS_DIR", "./data/sessions")
    return WorkflowEngine(prompthub, executor, sessions_dir)


prompthub = init_prompthub()
executor_manager = init_executor_manager()
workflow_engine = init_workflow_engine()

# 初始化页面状态
if "page" not in st.session_state:
    st.session_state.page = "home"
if "opencode_checked" not in st.session_state:
    st.session_state.opencode_checked = False


# ========================
# UI 组件
# ========================

def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.title("🚀 CodeFlow")
        st.caption("流程化 AI 编程助手")

        st.divider()

        # 导航菜单
        st.subheader("📍 导航")
        if st.button("🏠 首页", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
        if st.button("⚙️ 配置", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()

        st.divider()

        # 执行器状态
        st.subheader("⚡ 执行器状态")

        # 检查 OpenCode
        opencode_installed = check_opencode()
        if not opencode_installed and not st.session_state.opencode_checked:
            st.warning("❌ OpenCode 未安装")
            if st.button("📥 安装 OpenCode", key="install_opencode", use_container_width=True):
                st.session_state.page = "settings"
                st.session_state.show_opencode_install = True
                st.rerun()
            st.session_state.opencode_checked = True
        elif not opencode_installed:
            st.caption("❌ OpenCode 不可用")
        else:
            st.caption("✅ OpenCode 已安装")

        executors = executor_manager.list_executors()
        for exec_info in executors:
            status = "✅" if exec_info["available"] else "❌"
            st.write(f"{status} {exec_info['name'].title()}")

        # Minimax 配置状态
        minimax_key = get_config("MINIMAX_API_KEY", "")
        if minimax_key:
            st.caption("🔑 Minimax 已配置")
        else:
            st.warning("⚠️ Minimax 未配置")

        st.divider()

        # 配置快捷操作
        st.subheader("⚙️ 快捷操作")
        if st.button("🔄 重新加载提示词", use_container_width=True):
            prompthub.reload()
            check_opencode.clear()  # 清除 OpenCode 检测缓存
            st.success("提示词已重新加载")
            st.rerun()

        # 快速创建会话
        st.divider()
        st.subheader("🆕 快速开始")
        workflows = prompthub.list_workflows()
        for workflow in workflows:
            if st.button(f"📋 {workflow.name}", key=f"quick_{workflow.id}", use_container_width=True):
                st.session_state.selected_workflow = workflow.id
                st.session_state.selected_mode = "manual"
                st.session_state.page = "create_session"
                st.rerun()


def render_home():
    """渲染首页"""
    st.title("🚀 CodeFlow")
    st.caption("流程化 AI 编程助手 - 让开发更规范")

    # 工作流程列表
    workflows = prompthub.list_workflows()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📋 可用工作流程")

        for workflow in workflows:
            with st.expander(f"📁 {workflow.name}", expanded=False):
                st.write(f"**描述**: {workflow.description}")
                st.write(f"**步骤数**: {len(workflow.steps)}")

                # 显示步骤
                for step in workflow.steps[:5]:  # 只显示前5步
                    status_icon = "⏸️"
                    st.write(f"  {status_icon} Step {step.order}: {step.description}")

                if len(workflow.steps) > 5:
                    st.write(f"  ... 还有 {len(workflow.steps) - 5} 步")

                # 创建会话按钮
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button("🚀 手动模式", key=f"manual_{workflow.id}"):
                        st.session_state.selected_workflow = workflow.id
                        st.session_state.selected_mode = "manual"
                        st.session_state.page = "create_session"
                        st.rerun()
                with col_b:
                    if st.button("⚡ 自动模式", key=f"auto_{workflow.id}"):
                        st.session_state.selected_workflow = workflow.id
                        st.session_state.selected_mode = "auto"
                        st.session_state.page = "create_session"
                        st.rerun()
                with col_c:
                    if st.button("🔀 混合模式", key=f"hybrid_{workflow.id}"):
                        st.session_state.selected_workflow = workflow.id
                        st.session_state.selected_mode = "hybrid"
                        st.session_state.page = "create_session"
                        st.rerun()

    with col2:
        st.subheader("📝 会话历史")

        sessions = workflow_engine.list_sessions()[:10]

        if sessions:
            for session in sessions:
                with st.expander(f"💬 {session.workflow_name}", expanded=False):
                    st.write(f"**ID**: {session.id}")
                    st.write(f"**模式**: {session.mode.value}")
                    st.write(f"**状态**: {session.status}")
                    st.write(f"**当前步骤**: {session.current_step}")

                    if st.button("继续", key=f"resume_{session.id}"):
                        st.session_state.session_id = session.id
                        st.session_state.page = "session"
                        st.rerun()
        else:
            st.info("暂无会话历史")


def render_create_session():
    """渲染创建会话页面"""
    workflow_id = st.session_state.get("selected_workflow")
    mode = st.session_state.get("selected_mode", "manual")

    workflow = prompthub.get_workflow(workflow_id)
    if not workflow:
        st.error("工作流程不存在")
        return

    st.title(f"📋 创建会话: {workflow.name}")
    st.caption(workflow.description)

    st.divider()

    # 配置表单
    with st.form("create_session"):
        st.subheader("⚙️ 会话配置")

        col1, col2 = st.columns(2)
        with col1:
            new_mode = st.selectbox(
                "执行模式",
                options=["manual", "auto", "hybrid"],
                index=["manual", "auto", "hybrid"].index(mode),
                format_func=lambda x: {"manual": "手动", "auto": "自动", "hybrid": "混合"}[x]
            )

        with col2:
            project_path = st.text_input("项目路径", value=".")
            language = st.text_input("编程语言", value="python")

        st.divider()

        # 步骤预览
        st.subheader("📝 流程步骤预览")
        for step in workflow.steps:
            with st.expander(f"Step {step.order}: {step.description}", expanded=False):
                st.text_area(
                    "提示词内容",
                    value=step.template_content[:500] + "..." if len(step.template_content) > 500 else step.template_content,
                    height=150,
                    key=f"preview_{step.order}",
                    disabled=True
                )

        submitted = st.form_submit_button("🚀 创建会话", use_container_width=True)

        if submitted:
            context = {
                "project_path": project_path,
                "language": language
            }

            session = workflow_engine.create_session(
                workflow_id=workflow_id,
                mode=ExecutionMode(new_mode),
                context=context
            )

            if session:
                st.success(f"会话已创建: {session.id}")
                st.session_state.session_id = session.id
                st.session_state.page = "session"
                st.rerun()
            else:
                st.error("创建会话失败")

    if st.button("← 返回首页"):
        st.session_state.page = "home"
        st.rerun()


def render_session():
    """渲染会话执行页面"""
    session_id = st.session_state.get("session_id")

    if not session_id:
        st.error("未选择会话")
        st.session_state.page = "home"
        st.rerun()
        return

    session = workflow_engine.get_session(session_id)
    if not session:
        st.error("会话不存在")
        st.session_state.page = "home"
        st.rerun()
        return

    workflow = prompthub.get_workflow(session.workflow_id)

    # 顶部信息栏
    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

    with col1:
        st.title(f"📋 {session.workflow_name}")

    with col2:
        progress = workflow_engine.get_progress(session_id)
        st.metric("进度", f"{progress.get('completed', 0)}/{progress.get('total', 0)}")

    with col3:
        st.write(f"**模式**: {session.mode.value}")

    with col4:
        if st.button("← 返回"):
            st.session_state.page = "home"
            st.rerun()

    st.divider()

    # 主内容区
    col1, col2 = st.columns([2, 1])

    with col1:
        # 当前步骤
        current_step = workflow.get_step(session.current_step)
        if current_step:
            st.subheader(f"📍 当前步骤: Step {current_step.order} - {current_step.description}")

            # 显示提示词
            prompt = workflow_engine.get_current_prompt(session_id)
            if prompt:
                st.text_area("提示词内容", prompt, height=200, disabled=True, key="current_prompt")

            # 用户输入
            user_input = st.text_area("💬 你的输入（可选）", key="user_input", placeholder="补充说明...")

            # 执行器选择
            col_a, col_b = st.columns(2)
            with col_a:
                executor_choice = st.selectbox(
                    "选择执行器",
                    options=["minimax", "opencode"],
                    format_func=lambda x: {"minimax": "Minimax", "opencode": "OpenCode"}[x]
                )
            with col_b:
                st.write("")  # 占位
                if st.button("⏸️ 暂停", use_container_width=True):
                    workflow_engine.pause_session(session_id)
                    st.success("会话已暂停")
                    st.rerun()

        # 执行和操作按钮
        col_a, col_b, col_c, col_d = st.columns(4)

        with col_a:
            if st.button("▶️ 执行", use_container_width=True, type="primary"):
                with st.spinner("执行中..."):
                    # 使用 asyncio.run 调用异步函数
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                    except:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    result = loop.run_until_complete(
                        workflow_engine.execute_step(session_id, executor_choice, user_input)
                    )
                    if result.success:
                        st.success("执行成功")
                        st.session_state.last_result = result
                    else:
                        st.error(f"执行失败: {result.error}")
                    st.rerun()

        with col_b:
            if st.button("⏭️ 下一步", use_container_width=True):
                if workflow_engine.advance_step(session_id):
                    st.success("已进入下一步")
                    st.rerun()
                else:
                    st.info("已是最后一步")

        with col_c:
            if st.button("⏭️ 跳过", use_container_width=True):
                if workflow_engine.skip_step(session_id):
                    st.success("已跳过当前步骤")
                    st.rerun()

        with col_d:
            if st.button("🗑️ 删除", use_container_width=True):
                if workflow_engine.delete_session(session_id):
                    st.success("会话已删除")
                    st.session_state.page = "home"
                    st.rerun()

        # 显示执行结果
        if "last_result" in st.session_state:
            result = st.session_state.last_result
            st.divider()
            st.subheader("📤 执行结果")
            if result.success:
                st.info(result.content)
            else:
                st.error(result.error)

    with col2:
        # 流程进度
        st.subheader("📊 流程进度")

        progress = workflow_engine.get_progress(session_id)

        # 进度条
        st.progress(progress.get("percentage", 0) / 100)

        # 步骤列表
        for step in workflow.steps:
            step_status = session.steps_status.get(step.order, "pending")
            status_icon = {
                "pending": "⏸️",
                "in_progress": "▶️",
                "completed": "✅",
                "skipped": "⏭️"
            }.get(step_status, "⏸️")

            is_current = step.order == session.current_step
            if is_current:
                st.markdown(f"**{status_icon} Step {step.order}: {step.description}** ← 当前")
            else:
                st.write(f"{status_icon} Step {step.order}: {step.description}")

        # 笔记
        st.divider()
        st.subheader("📝 笔记")

        note = st.text_area("添加笔记", key="note_input")
        if st.button("添加", use_container_width=True):
            if workflow_engine.add_note(session_id, note):
                st.success("笔记已添加")
                st.rerun()

        for note_text in session.notes:
            st.caption(f"• {note_text}")


def render_settings():
    """渲染配置页面"""
    st.title("⚙️ 配置")
    st.caption("配置 API Key 和其他设置")

    st.divider()

    # OpenCode 安装
    st.subheader("📦 OpenCode 安装")
    opencode_installed = check_opencode()

    if opencode_installed:
        st.success("✅ OpenCode 已安装")
        try:
            result = subprocess.run(["opencode", "--version"], capture_output=True, text=True)
            st.caption(f"版本: {result.stdout.strip()}")
        except:
            st.caption("版本: 未知")
    else:
        st.warning("❌ OpenCode 未安装")

        with st.expander("📖 如何安装 OpenCode", expanded=True):
            st.markdown("""
            ### 方法 1: 使用 npm (推荐)
            ```bash
            npm i -g opencode-ai@latest
            ```

            ### 方法 2: 使用 curl
            ```bash
            curl -fsSL https://opencode.ai/install | bash
            ```

            ### 方法 3: 使用 Homebrew (macOS)
            ```bash
            brew install opencode
            ```

            ### 方法 4: 使用 Scoop (Windows)
            ```bash
            scoop bucket add extras
            scoop install extras/opencode
            ```

            安装完成后，点击下方按钮刷新检测。
            """)

        if st.button("🔄 刷新检测", use_container_width=True):
            st.session_state.opencode_checked = False
            check_opencode.clear()  # 清除缓存
            st.rerun()

    # 显示安装提示
    if st.session_state.get("show_opencode_install", False):
        st.info("💡 请按照上方说明安装 OpenCode，然后刷新检测")

    st.divider()

    # Minimax 配置
    st.subheader("🔑 Minimax API 配置")

    current_key = get_config("MINIMAX_API_KEY", "")
    current_group_id = get_config("MINIMAX_GROUP_ID", "")

    col1, col2 = st.columns(2)

    with col1:
        new_api_key = st.text_input(
            "API Key",
            value=current_key,
            type="password",
            help="从 https://www.minimaxi.com 获取"
        )

    with col2:
        new_group_id = st.text_input(
            "Group ID",
            value=current_group_id,
            help="你的 Minimax Group ID"
        )

    if st.button("💾 保存配置", use_container_width=True):
        config = load_config()
        config["MINIMAX_API_KEY"] = new_api_key
        config["MINIMAX_GROUP_ID"] = new_group_id
        save_config(config)
        st.success("配置已保存！请刷新页面使配置生效")
        st.info("💡 提示：保存后需要重新加载执行器才能生效")

    st.divider()

    # 其他配置
    st.subheader("🔧 其他配置")

    current_project_path = get_config("DEFAULT_PROJECT_PATH", ".")
    new_project_path = st.text_input("默认项目路径", value=current_project_path)

    current_language = get_config("DEFAULT_LANGUAGE", "python")
    new_language = st.text_input("默认编程语言", value=current_language)

    opencode_path = get_config("OPENCODE_PATH", "opencode")
    new_opencode_path = st.text_input("OpenCode 路径", value=opencode_path)

    if st.button("💾 保存其他配置", use_container_width=True):
        config = load_config()
        config["DEFAULT_PROJECT_PATH"] = new_project_path
        config["DEFAULT_LANGUAGE"] = new_language
        config["OPENCODE_PATH"] = new_opencode_path
        save_config(config)
        st.success("配置已保存！")

    st.divider()

    # 当前配置预览
    st.subheader("📋 当前配置")
    config_data = load_config()
    if config_data:
        st.json(config_data)
    else:
        st.info("暂无配置，请添加配置")


# ========================
# 页面路由
# ========================

def main():
    """主页面"""
    # 初始化页面状态
    if "page" not in st.session_state:
        st.session_state.page = "home"

    # 渲染侧边栏
    render_sidebar()

    # 页面路由
    page = st.session_state.page

    if page == "home":
        render_home()
    elif page == "create_session":
        render_create_session()
    elif page == "session":
        render_session()
    elif page == "settings":
        render_settings()
    else:
        render_home()

    # 底部状态栏
    st.divider()
    st.caption(f"CodeFlow v0.1.0 | 已加载 {len(prompthub.workflows)} 个工作流程")


if __name__ == "__main__":
    main()
