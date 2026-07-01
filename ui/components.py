"""
============================================================
MathAnimAI — Gradio 组件封装
功能：
  1. 封装文本输入框、图片上传、学段下拉选择
  2. 封装视频播放器、历史记录表格
  3. 统一组件样式，方便 layout.py 调用
============================================================
"""

import gradio as gr

from config import UI_PRIMARY_COLOR, UI_BG_COLOR


# ================================================================
# 输入组件
# ================================================================
def text_input_box() -> gr.Textbox:
    """题目文本输入框 — 多行、占位提示"""
    return gr.Textbox(
        label="题目输入",
        placeholder="请在此输入数学题目，例如：\n"
                     "解方程：2x + 3 = 7\n"
                     "已知直角三角形ABC中，AB=3，BC=4，求AC\n"
                     "小明从家到学校，每分钟走60米，需要15分钟，问家到学校多远？",
        lines=5,
        max_lines=10,
        elem_id="problem_input",
    )


def image_upload_box() -> gr.Image:
    """图片上传组件"""
    return gr.Image(
        label="上传题目图片（可选）",
        type="filepath",
        elem_id="image_upload",
    )


def grade_selector() -> gr.Dropdown:
    """学段选择下拉框"""
    return gr.Dropdown(
        label="学段选择",
        choices=["小学", "初中"],
        value="初中",
        elem_id="grade_selector",
    )


def type_selector() -> gr.Dropdown:
    """题型选择下拉框"""
    return gr.Dropdown(
        label="题型（自动识别，可手动指定）",
        choices=["自动识别", "方程", "几何", "函数", "应用题", "分数"],
        value="自动识别",
        elem_id="type_selector",
    )


# ================================================================
# 按钮组件
# ================================================================
def generate_button() -> gr.Button:
    """生成按钮 — 主题色、大尺寸"""
    return gr.Button(
        value="开始生成教学动画",
        variant="primary",
        size="lg",
        elem_id="generate_btn",
    )


def clear_button() -> gr.Button:
    """清除按钮"""
    return gr.Button(
        value="清除",
        variant="secondary",
        size="sm",
        elem_id="clear_btn",
    )


# ================================================================
# 输出组件
# ================================================================
def video_player() -> gr.Video:
    """视频播放器 — 展示生成的动画视频"""
    return gr.Video(
        label="教学动画预览",
        format="mp4",
        autoplay=False,
        elem_id="video_player",
    )


def status_display() -> gr.Textbox:
    """状态/日志显示"""
    return gr.Textbox(
        label="处理状态",
        placeholder="等待生成...",
        lines=8,
        max_lines=15,
        interactive=False,
        elem_id="status_display",
    )


def json_preview() -> gr.Code:
    """JSON脚本预览"""
    return gr.Code(
        label="动画脚本 JSON",
        language="json",
        lines=10,
        interactive=False,
        elem_id="json_preview",
    )


# ================================================================
# 历史记录组件
# ================================================================
def history_table() -> gr.Dataframe:
    """历史记录表格"""
    return gr.Dataframe(
        headers=["ID", "时间", "题目", "题型", "状态", "操作"],
        datatype=["number", "str", "str", "str", "str", "str"],
        row_count=10,
        column_count=(6, "fixed"),
        interactive=False,
        elem_id="history_table",
    )


def history_reload_button() -> gr.Button:
    """刷新历史按钮"""
    return gr.Button(
        value="刷新历史记录",
        variant="secondary",
        size="sm",
        elem_id="history_reload",
    )
