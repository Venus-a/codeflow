"""
CodeFlow - 简洁的 AI 编程助手

专注于 OpenCode 调用，提取精华输出
"""
import os
import sys
import subprocess
import time
import re
from pathlib import Path

import streamlit as st

# ========================
# 页面配置
# ========================

st.set_page_config(
    page_title="CodeFlow",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 工作目录
WORK_DIR = Path(__file__).parent.parent / "data" / "workspace"
WORK_DIR.mkdir(parents=True, exist_ok=True)

# ========================
# 页面状态
# ========================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "processing" not in st.session_state:
    st.session_state.processing = False

# ========================
# OpenCode 调用与解析
# ========================

def parse_opencode_output(raw_output: str) -> dict:
    """解析 OpenCode 输出，提取精华"""
    lines = raw_output.split('\n')

    result = {
        "steps": [],      # 操作步骤
        "files": [],      # 涉及的文件
        "summary": "",    # 最终总结
        "full_output": "" # 清理后的完整输出
    }

    for line in lines:
        # 移除 ANSI 码
        clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
        clean_line = clean_line.strip()

        if not clean_line or clean_line in ['> build', 'big-pickle']:
            continue

        # 检测操作 - "←" 开头表示操作
        if '←' in clean_line:
            # 提取操作内容
            parts = clean_line.split('←', 1)
            if len(parts) > 1:
                action = parts[1].strip()
                if action:
                    result["steps"].append(("doing", action))
                    # 提取文件名
                    for keyword in ['Write', 'Read', 'Edit', 'Delete', 'Create']:
                        if keyword in action:
                            # 提取文件名
                            match = re.search(rf'{keyword}\s+(\S+)', action, re.IGNORECASE)
                            if match:
                                result["files"].append(match.group(1))

        # 检测完成状态
        elif any(kw in clean_line.lower() for kw in ['success', 'done', '完成', '已创建', '已写入']):
            result["steps"].append(("done", clean_line))

        # 其他信息行
        elif clean_line and not any(skip in clean_line for skip in [
            'Performing one time', 'Database migration', 'sqlite-migration', '[0m'
        ]):
            result["steps"].append(("info", clean_line))

    # 生成完整输出
    cleaned_lines = []
    for line in lines:
        clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
        clean_line = clean_line.strip()
        if clean_line and not any(skip in clean_line for skip in [
            '[0m', 'build ·', 'Performing one time', 'Database migration', 'sqlite-migration'
        ]):
            if clean_line not in ['> build', 'big-pickle']:
                cleaned_lines.append(clean_line)

    result["full_output"] = '\n'.join(cleaned_lines).strip()

    return result


def call_opencode(prompt: str) -> tuple[bool, dict]:
    """调用 OpenCode 并解析输出"""
    try:
        result = subprocess.run(
            ["opencode", "run", prompt],
            capture_output=True,
            text=False,
            timeout=300,
            shell=True,
            cwd=WORK_DIR  # 指定工作目录
        )

        try:
            output = result.stdout.decode('utf-8', errors='ignore')
        except:
            output = str(result.stdout)

        if result.returncode == 0:
            parsed = parse_opencode_output(output)
            return True, parsed
        else:
            return False, {"error": f"OpenCode 错误: {output}"}

    except subprocess.TimeoutExpired:
        return False, {"error": "请求超时（5分钟）"}
    except FileNotFoundError:
        return False, {"error": "未找到 OpenCode，请先安装: `npm i -g opencode-ai`"}
    except Exception as e:
        return False, {"error": f"错误: {str(e)}"}


# ========================
# 主界面
# ========================

def main():
    """主界面"""

    # 标题栏
    col1, col2 = st.columns([4, 1])

    with col1:
        st.title("💬 CodeFlow")

    with col2:
        if st.button("🗑️ 清空", use_container_width=True, disabled=st.session_state.processing):
            st.session_state.messages = []
            st.rerun()

    st.divider()

    # 聊天历史
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("steps"):
                # 显示操作步骤
                for step_type, content in msg["steps"]:
                    if step_type == "doing":
                        st.caption(f"🔄 {content}")
                    elif step_type == "done":
                        st.success(f"✅ {content}")
                    else:
                        st.write(content)

                # 只在有文件时显示
                if msg.get("files"):
                    st.divider()
                    st.caption(f"**📄 生成的文件** (保存于 `data/workspace/`):")
                    for f in msg["files"]:
                        full_path = WORK_DIR / f
                        if full_path.exists():
                            st.success(f"📄 `{f}` ✅")
                        else:
                            st.write(f"📄 `{f}`")
            else:
                st.markdown(msg["content"])

    # 处理请求
    if st.session_state.processing and len(st.session_state.messages) > 0:
        last_msg = st.session_state.messages[-1]
        if last_msg["role"] == "user":
            prompt = last_msg["content"]

            # 显示处理状态
            with st.chat_message("assistant"):
                with st.status("🔄 **AI 正在工作...**", expanded=True) as status:
                    st.write("正在调用 OpenCode 处理...")

                    # 调用 OpenCode
                    success, result = call_opencode(prompt)

                    if success:
                        status.update(label="✅ **完成!**", state="complete", expanded=False)

                        # 显示操作步骤（只在有步骤时显示）
                        if result["steps"]:
                            st.divider()
                            st.caption("**📋 执行过程:**")

                            for step_type, content in result["steps"][:20]:
                                if step_type == "doing":
                                    st.write(f"🔄 {content}")
                                elif step_type == "done":
                                    st.write(f"✅ {content}")
                                else:
                                    st.write(f"• {content}")

                        # 只在有生成文件时显示文件列表
                        if result.get("files"):
                            st.divider()
                            st.caption(f"**📄 生成的文件** (保存于 `data/workspace/`):")
                            for f in result["files"]:
                                full_path = WORK_DIR / f
                                if full_path.exists():
                                    st.success(f"📄 `{f}` ✅")
                                else:
                                    st.write(f"📄 `{f}`")

                        # 保存消息
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": result.get("full_output", ""),
                            "steps": result.get("steps", []),
                            "files": result.get("files", [])
                        })
                    else:
                        status.update(label="❌ **失败**", state="error", expanded=False)
                        st.error(result.get("error", "未知错误"))

            st.session_state.processing = False
            time.sleep(0.3)
            st.rerun()

    # 用户输入
    if not st.session_state.processing:
        if prompt := st.chat_input("输入你的问题..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.processing = True
            st.rerun()

    # 底部提示
    if not st.session_state.messages:
        st.caption("💡 直接输入问题开始对话，使用 OpenCode 作为 AI 引擎")


if __name__ == "__main__":
    main()
