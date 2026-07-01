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
)
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
def generate_scene_code(script: ProblemScript) -> str:
    """
    根据ProblemScript JSON生成完整的Scene construct()代码
    这是核心代码生成逻辑，将JSON步骤翻译为Manim动画序列

    布局规则：
    - 标题始终在画面顶部（不参与侧边栏）
    - 当前讲解步骤展示在画面中央（大号）
    - 讲解完毕的步骤缩放到左侧面板（小号，垂直排列）
    - 所有内容自动检测边界防止溢出

    音频同步：
    - 根据每步voice_text字数估算音频时长
    - 动画wait时间匹配音频时长，确保音画同步

    Args:
        script: 经过Pydantic校验的动画脚本

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
    # 标题演示停顿用音频估算
    title_audio_est = max(len(script.problem_text) / AUDIO_CHARS_PER_SEC * 0.6, 1.0)
    lines.append(f'{indent}self.wait({title_audio_est:.2f})')
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

        # 根据音频时长估算步骤等待时间（音画同步关键！）
        voice_text = step.voice_text or step.text or ""
        audio_est = max(len(voice_text) / AUDIO_CHARS_PER_SEC, 1.5)
        # 加上动画本身的播放时间（约1-2秒）
        total_wait = audio_est + 0.5  # 动画播放时间 + 音频时间
        lines.append(f'{indent}# 音频估算 {audio_est:.1f}s，总等待 {total_wait:.1f}s')
        lines.append(f'{indent}self.wait({total_wait:.2f})')
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
def build_and_render(
    script: ProblemScript,
    output_dir: str = None,
    hd: bool = True,
) -> Optional[str]:
    """
    根据ProblemScript生成动画视频

    Args:
        script: 标准化动画脚本
        output_dir: 视频输出目录
        hd: 是否高清渲染

    Returns:
        视频文件路径，失败返回None
    """
    import tempfile
    from config import get_timestamp

    logger.info(f"开始构建动画: type={script.problem_type}, steps={len(script.steps)}")

    # 获取场景类
    scene_cls = get_scene_class(script.problem_type)

    # 生成场景代码
    scene_code = generate_scene_code(script)

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


def parse_and_build(json_str: str, hd: bool = True) -> Optional[str]:
    """
    便捷入口：从JSON字符串直接生成视频

    Args:
        json_str: JSON动画脚本字符串
        hd: 是否高清

    Returns:
        视频文件路径
    """
    try:
        script = ProblemScript.from_json_str(json_str)
        return build_and_render(script, hd=hd)
    except Exception as e:
        logger.error(f"解析JSON失败: {e}")
        return None
