"""
============================================================
MathAnimAI — JSON动画脚本调度器 (builder.py)
功能：
  1. 接收parser输出的ProblemScript JSON
  2. 根据problem_type自动匹配对应题型Scene
  3. 统一传入全局美化配置
  4. 生成可渲染的Manim场景代码
============================================================
"""

import os
import json
import logging
from typing import Optional, Type

from manim import Scene

from config import Colors
from config import (
    CANVAS_MAX_WIDTH, CANVAS_BOTTOM_Y, MAX_STACK_STEPS,
    AUDIO_CHARS_PER_SEC, CENTER_CONTENT_MAX_WIDTH,
    DURATION_CREATE, DURATION_SLIDE_IN, DURATION_HIGHLIGHT,
    DURATION_GROW, DURATION_TRANSITION,
)

# ================================================================
# 动画类型 → 预估播放时长（秒）
# 用于计算 self.wait() 时减去动画本身的播放时间
# ================================================================
ANIM_TYPE_DURATION: dict[str, float] = {
    "text_slide_in": 0.8,       # DURATION_SLIDE_IN
    "title_display": 0.8,
    "draw_shape": 1.0,          # DURATION_CREATE
    "draw_circle": 1.0,
    "draw_arc": 1.0,
    "draw_dashed_line": 1.0,
    "highlight": 1.2,           # DURATION_HIGHLIGHT
    "highlight_region": 1.2,
    "mark_angle": 0.5,
    "mark_right_angle": 0.5,
    "label_vertex": 0.8,        # DURATION_GROW
    "label_side": 0.8,
    "label_text": 0.8,
    "plot_function": 1.5,       # DURATION_CREATE * 1.5
    "plot_coordinate": 1.0,
    "plot_point": 0.8,
    "draw_bar_chart": 1.5,
    "draw_pie_chart": 0.8,
    "draw_segment_diagram": 1.0,
    "wait": 0.0,                # wait 本身就是暂停，不需要减
    "transform": 1.0,
}

# 步骤切换开销（step_transition 动画时间）
STEP_TRANSITION_DURATION = DURATION_TRANSITION  # 0.5s
from parser.schema import ProblemScript, ProblemType
from animation.common import BaseMathScene
from animation.scenes.equation import EquationScene
from animation.scenes.geometry import GeometryScene
from animation.scenes.function import FunctionScene
from animation.scenes.word_problem import WordProblemScene
from animation.scenes.fraction import FractionScene
from animation.renderer import generate_scene_file, render_scene

logger = logging.getLogger("MathAnimAI.Builder")


def _py_escape(text: str) -> str:
    """
    将来自 LLM 的文本转义，使其能安全嵌入生成的 Python 源码字符串字面量。
    处理换行、引号、反斜杠等会导致 SyntaxError 的字符。
    """
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
    )


# ================================================================
# 题型 → Scene类映射表
# ================================================================
SCENE_MAP: dict[str, Type] = {
    "equation": EquationScene,
    "geometry": GeometryScene,
    "function": FunctionScene,
    "word_problem": WordProblemScene,
    "fraction": FractionScene,
}


def get_scene_class(problem_type: str):
    """根据题目类型获取对应的Scene类"""
    scene_cls = SCENE_MAP.get(problem_type)
    if scene_cls is None:
        logger.warning(f"未知题目类型 '{problem_type}'，使用通用EquationScene")
        scene_cls = EquationScene
    return scene_cls


# ================================================================
# Scene代码生成
# ================================================================
def generate_scene_code(
    script: ProblemScript,
    audio_durations: dict = None,
    audio_paths: dict = None,
) -> str:
    """
    根据ProblemScript JSON生成完整的Scene construct()代码
    这是核心代码生成逻辑，将JSON步骤翻译为Manim动画序列

    布局规则：
    - 标题始终在画面顶部（不参与侧边栏）
    - 当前讲解步骤展示在画面中央（大号）
    - 讲解完毕的步骤缩放到左侧面板（小号，垂直排列）
    - 所有内容自动检测边界防止溢出

    音画同步（参考 MathLens 模板项目）：
    - 使用 add_sound() 将音频直接嵌入 Manim 时间轴
    - 使用 end_scene_with_audio() 自动补齐等待时间
    - 无需 FFmpeg 后期合并，帧级音画同步

    Args:
        script: 经过Pydantic校验的动画脚本
        audio_durations: {step_number: actual_audio_duration_seconds}，可选
        audio_paths: {step_number: absolute_audio_file_path}，可选

    Returns:
        完整的construct()方法代码字符串
    """
    lines = []
    indent = "        "

    # 初始化
    lines.append(f'{indent}# ===== 初始化场景 =====')
    lines.append(f'{indent}self.setup()')
    lines.append(f'')

    # 标题步骤 — 始终在顶部，不参与侧边栏
    title_raw = _py_escape(script.problem_text)
    title_display = title_raw[:40]
    if len(title_raw) > 40:
        title_display = title_display + "..."
    lines.append(f'{indent}# ===== 标题（固定在顶部） =====')
    lines.append(f'{indent}problem_title = title_text("{title_display}")')
    lines.append(f'{indent}problem_title.to_edge(UP, buff=0.5)')
    lines.append(f'{indent}self.add_to_all(problem_title)')
    lines.append(f'{indent}self.play(FadeIn(problem_title, shift=DOWN*0.5, run_time={script.settings.duration}))')
    lines.append(f'{indent}self.wait(1.0)  # 标题展示停顿（无音频）')
    lines.append(f'')

    # 如果有几何底图，先绘制
    if script.base_figure:
        lines.append(f'{indent}# ===== 绘制基础图形 =====')
        lines.append(f'{indent}self._draw_base_figure()')

    # 如果有坐标系，先绘制
    if script.coordinate_system:
        lines.append(f'{indent}# ===== 绘制坐标系 =====')
        lines.append(f'{indent}self._draw_coordinate_system()')

    lines.append('')

    # 逐步骤生成动画代码
    num_steps = len(script.steps)
    for step in script.steps:
        anim_type = step.animation_type.value if hasattr(step.animation_type, 'value') else step.animation_type
        lines.append(f'{indent}# ===== 步骤 {step.step_number}: {step.title} =====')
        lines.append(f'{indent}self.new_step()')

        # 步骤过渡：将上一个中央内容移入左侧侧边栏
        if step.step_number > 1:
            lines.append(f'{indent}# 将上一中央内容移至左侧侧边栏')
            lines.append(f'{indent}self.step_transition()')

        # ===== 音画同步：add_sound 嵌入音频 =====
        # 获取音频时长和路径
        if audio_durations and step.step_number in audio_durations:
            audio_dur = audio_durations[step.step_number]
        else:
            voice_text = step.voice_text or step.text or ""
            audio_dur = max(len(voice_text) / AUDIO_CHARS_PER_SEC, 1.0)

        audio_path = audio_paths.get(step.step_number) if audio_paths else None

        if audio_path:
            # 新方式：add_sound 嵌入音频 + end_scene_with_audio 自动补齐
            escaped_path = audio_path.replace("\\", "\\\\")
            lines.append(f'{indent}self.start_scene_with_audio({step.step_number}, audio_path=r"{audio_path}", expected_duration={audio_dur:.2f})')
        else:
            # 降级：无音频路径，仅用时长估算
            lines.append(f'{indent}self.start_scene_with_audio({step.step_number}, audio_path=None, expected_duration={audio_dur:.2f})')

        # 根据动画类型生成对应代码
        if anim_type in ("text_slide_in", "title_display"):
            lines.extend(_gen_text_slide_in(step, indent))

        elif anim_type in ("draw_shape", "draw_circle", "draw_arc"):
            lines.extend(_gen_draw_shape(step, indent))

        elif anim_type == "draw_dashed_line":
            lines.extend(_gen_dashed_line(step, indent))

        elif anim_type in ("highlight", "highlight_region"):
            lines.extend(_gen_highlight(step, indent))

        elif anim_type == "mark_angle":
            lines.extend(_gen_mark_angle(step, indent))

        elif anim_type == "mark_right_angle":
            lines.extend(_gen_mark_right_angle(step, indent))

        elif anim_type == "label_vertex":
            lines.extend(_gen_label_vertex(step, indent))

        elif anim_type == "label_side":
            lines.extend(_gen_label_side(step, indent))

        elif anim_type == "label_text":
            lines.extend(_gen_label_text(step, indent))

        elif anim_type == "plot_function":
            lines.extend(_gen_plot_function(step, indent))

        elif anim_type == "plot_coordinate":
            lines.extend(_gen_plot_coordinate(step, indent))

        elif anim_type == "plot_point":
            lines.extend(_gen_plot_point(step, indent))

        elif anim_type == "draw_bar_chart":
            lines.extend(_gen_bar_chart(step, indent))

        elif anim_type == "draw_pie_chart":
            lines.extend(_gen_pie_chart(step, indent))

        elif anim_type == "draw_segment_diagram":
            lines.extend(_gen_segment_diagram(step, indent))

        elif anim_type == "wait":
            lines.append(f'{indent}self.wait({step.config.get("duration", 1.5)})')

        elif anim_type == "transform":
            lines.extend(_gen_transform(step, indent))

        else:
            # 兜底：默认用text_slide_in
            lines.extend(_gen_text_slide_in(step, indent))

        # ===== 音画同步：end_scene_with_audio 自动补齐 =====
        lines.append(f'{indent}# audio={audio_dur:.1f}s → end_scene_with_audio 自动补齐')
        lines.append(f'{indent}self.end_scene_with_audio(expected_duration={audio_dur:.2f})')
        lines.append('')

    # 结尾 — 最终答案展示在中央
    lines.append(f'{indent}# ===== 最终展示 =====')
    lines.append(f'{indent}# 将最后中央内容移入侧边栏')
    lines.append(f'{indent}self.step_transition()')
    lines.append(f'{indent}final_text = step_text("答：{_py_escape(script.final_answer)}")')
    lines.append(f'{indent}position_in_center_safe(final_text)')
    lines.append(f'{indent}self.add_to_center(final_text)')
    lines.append(f'{indent}self.play(FadeIn(final_text, shift=UP*0.3, run_time=DURATION_HIGHLIGHT))')
    lines.append(f'{indent}self.wait(2.5)')

    return '\n'.join(lines)


# ================================================================
# 每步独立渲染：generate_step_scene_code
# ================================================================
def generate_step_scene_code(
    script: ProblemScript,
    step_index: int,
    audio_durations: dict = None,
    audio_paths: dict = None,
    is_first: bool = False,
) -> str:
    """
    生成单步骤的独立 Scene construct() 代码（用于每步独立渲染）。

    与 generate_scene_code() 的区别：
    - 无侧边栏/步骤过渡（每个视频独立）
    - 标题在非首步时静态添加（无 FadeIn），确保拼接后视觉连续
    - 无最终答案展示
    - 使用 add_sound() + end_scene_with_audio() 实现音画同步

    Args:
        script: 动画脚本
        step_index: 步骤序号（1-based）
        audio_durations: {step_number: duration_seconds}
        audio_paths: {step_number: absolute_audio_file_path}
        is_first: 是否为第一个步骤（决定标题是否需要 FadeIn 动画）

    Returns:
        完整的 construct() 方法代码
    """
    step = script.steps[step_index - 1]
    anim_type = step.animation_type.value if hasattr(step.animation_type, 'value') else step.animation_type

    lines = []
    indent = "        "

    # 初始化场景
    lines.append(f'{indent}# ===== 步骤 {step.step_number} 独立场景 =====')
    lines.append(f'{indent}self.setup()')
    lines.append('')

    # 标题 — 首步 FadeIn，后续步静态（拼接后视觉连续）
    title_raw = _py_escape(script.problem_text)
    title_display = title_raw[:40]
    if len(title_raw) > 40:
        title_display = title_display + "..."
    lines.append(f'{indent}# 标题')
    lines.append(f'{indent}problem_title = title_text("{title_display}")')
    lines.append(f'{indent}problem_title.to_edge(UP, buff=0.5)')
    if is_first:
        lines.append(f'{indent}self.add_to_all(problem_title)')
        lines.append(f'{indent}self.play(FadeIn(problem_title, shift=DOWN*0.5, run_time={script.settings.duration}))')
        lines.append(f'{indent}self.wait(1.0)  # 标题展示停顿')
    else:
        # 静态添加，首帧就显示
        lines.append(f'{indent}self.add(problem_title)')
    lines.append('')

    # ===== 音画同步：add_sound 嵌入音频 =====
    if audio_durations and step.step_number in audio_durations:
        audio_dur = audio_durations[step.step_number]
    else:
        voice_text = step.voice_text or step.text or ""
        audio_dur = max(len(voice_text) / AUDIO_CHARS_PER_SEC, 1.0)

    audio_path = audio_paths.get(step.step_number) if audio_paths else None

    lines.append(f'{indent}# ===== 步骤内容 =====')
    if audio_path:
        lines.append(f'{indent}self.start_scene_with_audio({step.step_number}, audio_path=r"{audio_path}", expected_duration={audio_dur:.2f})')
    else:
        lines.append(f'{indent}self.start_scene_with_audio({step.step_number}, audio_path=None, expected_duration={audio_dur:.2f})')

    if anim_type in ("text_slide_in", "title_display"):
        lines.extend(_gen_step_text_slide_in(step, indent))
    elif anim_type in ("draw_shape", "draw_circle", "draw_arc"):
        lines.extend(_gen_draw_shape(step, indent))
    elif anim_type == "draw_dashed_line":
        lines.extend(_gen_dashed_line(step, indent))
    elif anim_type in ("highlight", "highlight_region"):
        lines.extend(_gen_highlight(step, indent))
    elif anim_type == "mark_angle":
        lines.extend(_gen_mark_angle(step, indent))
    elif anim_type == "mark_right_angle":
        lines.extend(_gen_mark_right_angle(step, indent))
    elif anim_type == "label_vertex":
        lines.extend(_gen_label_vertex(step, indent))
    elif anim_type == "label_side":
        lines.extend(_gen_label_side(step, indent))
    elif anim_type == "label_text":
        lines.extend(_gen_label_text(step, indent))
    elif anim_type == "plot_function":
        lines.extend(_gen_plot_function(step, indent))
    elif anim_type == "plot_coordinate":
        lines.extend(_gen_plot_coordinate(step, indent))
    elif anim_type == "plot_point":
        lines.extend(_gen_plot_point(step, indent))
    elif anim_type == "draw_bar_chart":
        lines.extend(_gen_bar_chart(step, indent))
    elif anim_type == "draw_pie_chart":
        lines.extend(_gen_pie_chart(step, indent))
    elif anim_type == "draw_segment_diagram":
        lines.extend(_gen_segment_diagram(step, indent))
    elif anim_type == "wait":
        lines.append(f'{indent}self.wait({step.config.get("duration", 1.5)})')
    elif anim_type == "transform":
        lines.extend(_gen_transform(step, indent))
    else:
        lines.extend(_gen_step_text_slide_in(step, indent))

    # ===== 音画同步：end_scene_with_audio 自动补齐 =====
    lines.append(f'{indent}# audio={audio_dur:.1f}s → end_scene_with_audio 自动补齐')
    lines.append(f'{indent}self.end_scene_with_audio(expected_duration={audio_dur:.2f})')

    return '\n'.join(lines)


def _gen_step_text_slide_in(step, indent: str) -> list[str]:
    """单步骤模式的文字滑入（不使用 add_to_center / sidebar 机制）"""
    lines = []
    lines.append(f'{indent}# 文字滑入')
    text_var = f"step{step.step_number}_text"
    raw_text = _py_escape(step.text)
    step_text_content = raw_text[:80]
    if len(raw_text) > 80:
        step_text_content = step_text_content + "..."
    lines.append(f'{indent}{text_var} = step_text("{step_text_content}")')
    if step.math_expr:
        lines.append(f'{indent}{text_var}_math = math_text(r"{_py_escape(step.math_expr)}")')
        lines.append(f'{indent}{text_var} = VGroup({text_var}, {text_var}_math).arrange(DOWN, buff=0.2)')
    # 居中放置
    lines.append(f'{indent}position_in_center_safe({text_var})')
    lines.append(f'{indent}if {text_var}.width > {CENTER_CONTENT_MAX_WIDTH}:')
    lines.append(f'{indent}    {text_var}.scale({CENTER_CONTENT_MAX_WIDTH} / {text_var}.width * 0.9)')
    lines.append(f'{indent}self.add({text_var})')
    lines.append(f'{indent}self.play(FadeIn({text_var}, shift=UP*0.5, run_time=DURATION_SLIDE_IN, rate_func=smooth))')
    return lines


# ================================================================
# 各动画类型的代码生成函数
# ================================================================
def _gen_text_slide_in(step, indent: str) -> list[str]:
    """生成文字滑入动画代码 — 放在画面中央，用 add_to_center 追踪"""
    lines = []
    lines.append(f'{indent}# 文字滑入（中央展示）')
    text_var = f"step{step.step_number}_text"
    # 先转义再截断（避免截断转义序列）
    raw_text = _py_escape(step.text)
    step_text_content = raw_text[:80]
    if len(raw_text) > 80:
        step_text_content = step_text_content + "..."
    lines.append(f'{indent}{text_var} = step_text("{step_text_content}")')
    if step.math_expr:
        lines.append(f'{indent}{text_var}_math = math_text(r"{_py_escape(step.math_expr)}")')
        lines.append(f'{indent}{text_var} = VGroup({text_var}, {text_var}_math).arrange(DOWN, buff=0.2)')
    # 放置在画面中央，自动安全检查
    lines.append(f'{indent}position_in_center_safe({text_var})')
    # 如果文字超出中央最大宽度，等比例缩小
    lines.append(f'{indent}if {text_var}.width > {CENTER_CONTENT_MAX_WIDTH}:')
    lines.append(f'{indent}    {text_var}.scale({CENTER_CONTENT_MAX_WIDTH} / {text_var}.width * 0.9)')
    # 使用 add_to_center 以便后续自动移入侧边栏
    lines.append(f'{indent}self.add_to_center({text_var})')
    lines.append(f'{indent}self.play(FadeIn({text_var}, shift=UP*0.5, run_time=DURATION_SLIDE_IN, rate_func=smooth))')
    return lines


def _gen_draw_shape(step, indent: str) -> list[str]:
    """生成图形绘制动画代码 — 放在画面中央"""
    lines = []
    config = step.config
    shape_type = config.get("shape_type", "polygon") if config else "polygon"
    points = config.get("points", []) if config else []
    color = config.get("color", "#3498DB") if config else "#3498DB"

    lines.append(f'{indent}# 绘制图形: {shape_type}（中央展示）')
    if shape_type == "polygon" and points:
        pts_str = ", ".join([f"np.array([{p[0]},{p[1]},0])" for p in points])
        lines.append(f'{indent}shape = Polygon({pts_str}, color="{color}", stroke_width=2.5)')
        lines.append(f'{indent}self.add_to_center(shape)')
        lines.append(f'{indent}self.play(Create(shape, run_time=DURATION_CREATE, rate_func=linear))')
    elif shape_type == "circle":
        radius = config.get("radius", 1.5)
        center = config.get("center", [0, 0])
        lines.append(f'{indent}shape = Circle(radius={radius}, color="{color}", stroke_width=2.5)')
        lines.append(f'{indent}shape.move_to(np.array([{center[0]},{center[1]},0]))')
        lines.append(f'{indent}self.add_to_center(shape)')
        lines.append(f'{indent}self.play(Create(shape, run_time=DURATION_CREATE, rate_func=linear))')
    elif shape_type == "triangle" and points:
        pts_str = ", ".join([f"np.array([{p[0]},{p[1]},0])" for p in points])
        lines.append(f'{indent}shape = Polygon({pts_str}, color="{color}", stroke_width=2.5)')
        lines.append(f'{indent}self.add_to_center(shape)')
        lines.append(f'{indent}self.play(Create(shape, run_time=DURATION_CREATE, rate_func=linear))')
    else:
        # 兜底：无法识别的图形类型或缺少坐标数据，降级为文字展示
        logger.warning(f"draw_shape 兜底降级: shape_type={shape_type}, has_points={bool(points)}")
        return _gen_text_slide_in(step, indent)
    return lines


def _gen_dashed_line(step, indent: str) -> list[str]:
    """生成虚线辅助线代码"""
    lines = []
    config = step.config or {}
    start = config.get("start", [0, 0])
    end = config.get("end", [1, 1])
    color = config.get("color", "#7F8C8D")
    lines.append(f'{indent}# 绘制虚线辅助线（中央展示）')
    lines.append(f'{indent}dl = DashedLine(np.array([{start[0]},{start[1]},0]), np.array([{end[0]},{end[1]},0]), color="{color}", dash_length=0.12)')
    lines.append(f'{indent}self.add_to_center(dl)')
    lines.append(f'{indent}self.play(Create(dl, run_time=DURATION_CREATE))')
    return lines


def _gen_highlight(step, indent: str) -> list[str]:
    """生成高亮动画代码"""
    lines = []
    lines.append(f'{indent}# 高亮 {step.target or "当前步骤"}')
    if step.target:
        target_var = step.target
        lines.append(f'{indent}smooth_highlight(self, {target_var})')
    else:
        # 未指定目标时，高亮 center_elements 中最后一个元素
        lines.append(f'{indent}if self.center_elements:')
        lines.append(f'{indent}    smooth_highlight(self, self.center_elements[-1])')
    return lines


def _gen_mark_angle(step, indent: str) -> list[str]:
    """生成角度标注代码"""
    lines = []
    config = step.config or {}
    v = config.get("vertex", [0, 0])
    a = config.get("point_a", [1, 0])
    b = config.get("point_b", [0, 1])
    label = config.get("label", "")
    lines.append(f'{indent}draw_angle_mark(self, np.array([{v[0]},{v[1]},0]), np.array([{a[0]},{a[1]},0]), np.array([{b[0]},{b[1]},0]), label="{_py_escape(label)}")')
    return lines


def _gen_mark_right_angle(step, indent: str) -> list[str]:
    """生成直角标注代码"""
    lines = []
    config = step.config or {}
    v = config.get("vertex", [0, 0])
    a = config.get("point_a", [1, 0])
    b = config.get("point_b", [0, 1])
    lines.append(f'{indent}draw_right_angle_mark(self, np.array([{v[0]},{v[1]},0]), np.array([{a[0]},{a[1]},0]), np.array([{b[0]},{b[1]},0]))')
    return lines


def _gen_label_vertex(step, indent: str) -> list[str]:
    """生成顶点标签代码"""
    lines = []
    config = step.config or {}
    point = config.get("point", [0, 0])
    label = config.get("label", "A")
    direction = config.get("direction", "UR*0.3")
    lines.append(f'{indent}draw_vertex_label(self, np.array([{point[0]},{point[1]},0]), "{_py_escape(label)}", direction={direction})')
    return lines


def _gen_label_side(step, indent: str) -> list[str]:
    """生成边长标注代码"""
    lines = []
    config = step.config or {}
    start = config.get("start", [0, 0])
    end = config.get("end", [1, 0])
    label = config.get("label", "")
    lines.append(f'{indent}draw_side_label(self, np.array([{start[0]},{start[1]},0]), np.array([{end[0]},{end[1]},0]), "{_py_escape(label)}")')
    return lines


def _gen_label_text(step, indent: str) -> list[str]:
    """通用标注文字"""
    return _gen_text_slide_in(step, indent)


def _gen_plot_function(step, indent: str) -> list[str]:
    """函数曲线 — 中央展示"""
    lines = []
    config = step.config
    func_expr = step.math_expr or config.get("function", "x**2")
    lines.append(f'{indent}# 绘制函数曲线（中央展示）')
    lines.append(f'{indent}graph = self.axes.plot(lambda x: {func_expr}, color="{Colors.FUNCTION_CURVE}", stroke_width=3)')
    lines.append(f'{indent}self.add_to_center(graph)')
    lines.append(f'{indent}self.play(Create(graph, run_time=DURATION_CREATE*1.5))')
    return lines


def _gen_plot_coordinate(step, indent: str) -> list[str]:
    """坐标系 — 持久化（保持在画面中不动）"""
    lines = []
    config = step.config
    x_range = config.get("x_range", [-10, 10, 1])
    y_range = config.get("y_range", [-6, 6, 1])
    lines.append(f'{indent}# 绘制坐标系（持久化）')
    lines.append(f'{indent}self.axes = Axes(x_range={x_range}, y_range={y_range}, axis_config={{"include_numbers": True, "font_size": 20}}, tips=True)')
    lines.append(f'{indent}self.axes.center()')
    lines.append(f'{indent}self.add_to_all(self.axes)')
    lines.append(f'{indent}self.play(Create(self.axes, run_time=DURATION_CREATE))')
    return lines


def _gen_plot_point(step, indent: str) -> list[str]:
    """标注动点 — 中央展示"""
    lines = []
    config = step.config
    point = config.get("point", [0, 0])
    lines.append(f'{indent}dot = Dot(self.axes.coords_to_point({point[0]}, {point[1]}), color="{Colors.VERTEX}", radius=0.08)')
    lines.append(f'{indent}self.add_to_center(dot)')
    lines.append(f'{indent}self.play(GrowFromCenter(dot, run_time=DURATION_GROW))')
    return lines


def _gen_bar_chart(step, indent: str) -> list[str]:
    """柱状图 — 中央展示"""
    lines = []
    config = step.config
    values = config.get("values", [1, 2, 3])
    labels = config.get("labels", ["", "", ""])
    lines.append(f'{indent}# 绘制柱状图（中央展示）')
    lines.append(f'{indent}chart = BarChart(values={values}, bar_names={labels}, bar_colors={[Colors.BAR_COLORS[i%len(Colors.BAR_COLORS)] for i in range(len({values}))]})')
    lines.append(f'{indent}self.add_to_center(chart)')
    lines.append(f'{indent}self.play(Create(chart, run_time=DURATION_CREATE*1.5))')
    return lines


def _gen_pie_chart(step, indent: str) -> list[str]:
    """饼图 — 中央展示"""
    lines = []
    config = step.config
    values = config.get("values", [1, 1, 1])
    labels = config.get("labels", ["", "", ""])
    lines.append(f'{indent}# 绘制饼图（中央展示）')
    lines.append(f'{indent}chart = VGroup()')
    lines.append(f'{indent}colors_list = {Colors.PIE_COLORS}')
    lines.append(f'{indent}pie_text = step_text("{" + "+".join([str(v) for v in {values}]) + "}")')
    lines.append(f'{indent}self.add_to_center(pie_text)')
    lines.append(f'{indent}self.play(FadeIn(pie_text, shift=UP*0.5, run_time=DURATION_SLIDE_IN))')
    return lines


def _gen_segment_diagram(step, indent: str) -> list[str]:
    """线段图 — 中央展示"""
    lines = []
    config = step.config
    total = config.get("total", 1)
    parts = config.get("parts", [0.3, 0.7])
    lines.append(f'{indent}# 绘制线段图（中央展示）')
    lines.append(f'{indent}seg_line = Line(LEFT*4, RIGHT*4, color="{Colors.PRIMARY}", stroke_width=4)')
    lines.append(f'{indent}self.add_to_center(seg_line)')
    lines.append(f'{indent}self.play(Create(seg_line, run_time=DURATION_CREATE))')
    # Draw division markers
    cumulative = 0
    for i, part in enumerate(parts):
        cumulative += part
        x_pos = -4 + cumulative / total * 8
        lines.append(f'{indent}marker = DashedLine(UP*0.5 + RIGHT*{x_pos}, DOWN*0.5 + RIGHT*{x_pos}, color="{Colors.DASHED}")')
        lines.append(f'{indent}self.add_to_center(marker)')
        lines.append(f'{indent}self.play(Create(marker, run_time=0.5))')
    return lines


def _gen_transform(step, indent: str) -> list[str]:
    """图形变换"""
    lines = []
    lines.append(f'{indent}# 图形变换')
    lines.append(f'{indent}self.wait({step.config.get("duration", 1.0)})')
    return lines


# ================================================================
# 统一调度入口
# ================================================================
def build_and_render_per_step(
    script: ProblemScript,
    audio_durations: dict,
    hd: bool = True,
    audio_paths: dict = None,
) -> list[dict]:
    """
    每步独立渲染：将每个步骤渲染为独立的短视频，然后 ffmpeg 拼接。

    优势：每个步骤视频的时长精确等于对应音频时长，拼接后天然音画同步。
    使用 add_sound() 将音频嵌入每个步骤视频，拼接后音频也同步。
    适用题型：word_problem、fraction（无持久化图形的题型）

    Args:
        script: 标准化动画脚本
        audio_durations: {step_number: actual_audio_duration_seconds}，必需
        hd: 是否高清渲染
        audio_paths: {step_number: absolute_audio_file_path}，用于 add_sound()

    Returns:
        [{"step_number": 1, "video_path": "...", "duration": 11.2}, ...]
        失败时返回空列表
    """
    import tempfile
    from config import get_timestamp

    logger.info(
        f"每步独立渲染模式: type={script.problem_type}, "
        f"steps={len(script.steps)}, durations={audio_durations}"
    )

    step_videos = []
    scene_cls = get_scene_class(script.problem_type)
    timestamp = get_timestamp()

    for i, step in enumerate(script.steps):
        step_num = step.step_number
        audio_dur = audio_durations.get(step_num)
        if audio_dur is None:
            logger.warning(f"步骤 {step_num} 无音频时长，使用估算")
            voice_text = step.voice_text or step.text or ""
            audio_dur = max(len(voice_text) / AUDIO_CHARS_PER_SEC, 1.0)

        is_first = (i == 0)

        # 生成单步场景代码
        scene_code = generate_step_scene_code(
            script=script,
            step_index=step_num,
            audio_durations=audio_durations,
            audio_paths=audio_paths,
            is_first=is_first,
        )

        # 渲染
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_class_name = f"MathAnimAI_step{step_num:02d}_{timestamp}"
            scene_file = generate_scene_file(
                scene_code=scene_code,
                scene_class_name=scene_class_name,
                base_class=scene_cls.__name__,
                output_dir=tmpdir,
            )

            video_path = render_scene(
                scene_file=scene_file,
                scene_class=os.path.splitext(os.path.basename(scene_file))[0],
                quality="h" if hd else "m",
            )

            if video_path and os.path.exists(video_path):
                step_videos.append({
                    "step_number": step_num,
                    "video_path": video_path,
                    "duration": audio_dur,
                })
                logger.info(f"  步骤 {step_num} 渲染完成: {video_path} (目标 {audio_dur:.1f}s)")
            else:
                logger.error(f"  步骤 {step_num} 渲染失败")
                # 继续尝试后续步骤

    logger.info(f"每步独立渲染完成: {len(step_videos)}/{len(script.steps)} 个步骤")
    return step_videos


def build_and_render(
    script: ProblemScript,
    output_dir: str = None,
    hd: bool = True,
    audio_durations: dict = None,
    audio_paths: dict = None,
) -> Optional[str]:
    """
    根据ProblemScript生成动画视频

    使用 add_sound() 将音频直接嵌入 Manim 时间轴，实现帧级音画同步。
    渲染输出的视频已包含音频轨，无需 FFmpeg 后期合并。

    Args:
        script: 标准化动画脚本
        output_dir: 视频输出目录
        hd: 是否高清渲染
        audio_durations: {step_number: duration_seconds} TTS 真实时长
        audio_paths: {step_number: absolute_audio_file_path} 用于 add_sound()

    Returns:
        视频文件路径，失败返回None
    """
    import tempfile
    from config import get_timestamp

    logger.info(f"开始构建动画: type={script.problem_type}, steps={len(script.steps)}")

    # 获取场景类
    scene_cls = get_scene_class(script.problem_type)

    # 生成场景代码
    scene_code = generate_scene_code(
        script,
        audio_durations=audio_durations,
        audio_paths=audio_paths,
    )

    # 用临时目录存场景文件
    with tempfile.TemporaryDirectory() as tmpdir:
        scene_file = generate_scene_file(
            scene_code=scene_code,
            scene_class_name=f"MathAnimAI_{get_timestamp()}",
            base_class=scene_cls.__name__,
            output_dir=tmpdir,
        )

        # 渲染
        scene_class_name = os.path.splitext(os.path.basename(scene_file))[0]
        video_path = render_scene(
            scene_file=scene_file,
            scene_class=scene_class_name,
            quality="h" if hd else "m",
            output_dir=output_dir,
        )

        return video_path


def parse_and_build(
    json_str: str,
    hd: bool = True,
    audio_durations: dict = None,
    audio_paths: dict = None,
) -> Optional[str]:
    """
    便捷入口：从JSON字符串直接生成视频

    Args:
        json_str: JSON动画脚本字符串
        hd: 是否高清
        audio_durations: {step_number: duration_seconds} TTS 真实时长
        audio_paths: {step_number: absolute_audio_file_path} 用于 add_sound()

    Returns:
        视频文件路径
    """
    try:
        script = ProblemScript.from_json_str(json_str)
        return build_and_render(
            script,
            hd=hd,
            audio_durations=audio_durations,
            audio_paths=audio_paths,
        )
    except Exception as e:
        logger.error(f"解析JSON失败: {e}")
        return None
