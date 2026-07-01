"""
============================================================
MathAnimAI — Gradio 界面布局
功能：
  1. 左右分栏固定布局
  2. 左侧：输入区（文本框、图片上传、学段选择、生成按钮）
  3. 右侧：视频预览 + JSON脚本预览 + 历史记录
============================================================
"""

import gradio as gr

from config import GRADIO_PORT, GRADIO_SHARE, UI_BG_COLOR
from ui.components import (
    text_input_box, image_upload_box, grade_selector, type_selector,
    generate_button, clear_button,
    video_player, status_display, json_preview,
    history_table, history_reload_button,
)


# ================================================================
# 界面构建函数
# ================================================================
def create_interface(pipeline_handler, ocr_handler, history_handler):
    """
    创建Gradio Web界面

    Args:
        pipeline_handler: 全流水线处理函数
        ocr_handler: OCR图片识别处理函数
        history_handler: 历史记录加载函数

    Returns:
        gr.Blocks 实例
    """
    with gr.Blocks(
        title="MathAnimAI — 数学教育动画智能体",
    ) as demo:
        # ================================================================
        # 标题栏
        # ================================================================
        gr.Markdown(
            """
            # MathAnimAI — 中小学数学教育动画智能体
            ### 输入数学题 → AI 自动生成教学动画视频
            """
        )

        # ================================================================
        # 主体 — 左右分栏
        # ================================================================
        with gr.Row(equal_height=False):
            # ---------- 左侧：输入区域 ----------
            with gr.Column(scale=2, min_width=350):
                gr.Markdown("### 题目输入")
                problem_input = text_input_box()
                problem_image = image_upload_box()

                with gr.Row():
                    grade_dropdown = grade_selector()
                    type_dropdown = type_selector()

                with gr.Row():
                    generate_btn = generate_button()
                    clear_btn = clear_button()

                # 状态显示
                gr.Markdown("### 处理日志")
                status_box = status_display()

            # ---------- 右侧：输出区域 ----------
            with gr.Column(scale=3, min_width=500):
                gr.Markdown("### 动画视频预览")
                video_output = video_player()

                gr.Markdown("### 动画脚本")
                json_output = json_preview()

        # ================================================================
        # 底部：历史记录
        # ================================================================
        gr.Markdown("---")
        gr.Markdown("### 历史生成记录")
        with gr.Row():
            history_reload = history_reload_button()
        history_df = history_table()

        # ================================================================
        # 事件绑定
        # ================================================================
        # 1. 图片上传 → OCR识别 → 填充文本框
        problem_image.change(
            fn=ocr_handler,
            inputs=[problem_image],
            outputs=[problem_input, status_box],
        )

        # 2. 生成按钮 → 全流水线
        generate_btn.click(
            fn=pipeline_handler,
            inputs=[problem_input, problem_image, grade_dropdown, type_dropdown],
            outputs=[video_output, json_output, status_box, history_df],
            show_progress="full",
        )

        # 3. 清除按钮 → 清空输入
        clear_btn.click(
            fn=lambda: ("", None, "初中", "自动识别", "已清除"),
            inputs=[],
            outputs=[problem_input, problem_image, grade_dropdown, type_dropdown, status_box],
        )

        # 4. 刷新历史按钮
        history_reload.click(
            fn=history_handler,
            inputs=[],
            outputs=[history_df],
        )

    return demo


# ================================================================
# 启动入口
# ================================================================
def launch_app(
    pipeline_handler,
    ocr_handler,
    history_handler,
    port: int = None,
    share: bool = False,
):
    """
    启动Gradio服务

    Args:
        pipeline_handler: 全流水线处理函数
        ocr_handler: OCR识别处理函数
        history_handler: 历史记录加载函数
        port: 端口号
        share: 是否启用公网分享
    """
    port = port or GRADIO_PORT
    share = share or GRADIO_SHARE

    demo = create_interface(pipeline_handler, ocr_handler, history_handler)

    # Gradio 6.0: theme 和 css 移到 launch() 参数
    launch_theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="green",
        neutral_hue="slate",
    )
    launch_css = """
    #problem_input textarea {
        font-size: 16px;
        line-height: 1.5;
    }
    #generate_btn {
        background: #3498DB !important;
        font-size: 18px !important;
        font-weight: bold !important;
    }
    #status_display textarea {
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 13px;
    }
    .gradio-container {
        max-width: 1400px !important;
    }
    """

    demo.launch(
        server_port=port,
        share=share,
        inbrowser=True,
        theme=launch_theme,
        css=launch_css,
        show_error=True,
    )
