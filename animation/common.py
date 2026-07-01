"""
============================================================
MathAnimAI — 全局公共美化工具库 (common.py)
所有场景共用的动画、文本、绘图工具函数。
统一配色、字体、动画参数，禁止各场景重复实现。
============================================================
"""

from manim import *
import numpy as np

from config import (
    Colors, FONT_FAMILY, FONT_TITLE, FONT_STEP, FONT_LABEL, FONT_ANNOTATION,
    DURATION_CREATE, DURATION_SLIDE_IN, DURATION_HIGHLIGHT,
    DURATION_TRANSITION, DURATION_WRITE, DURATION_GROW, DURATION_SHIFT,
    DURATION_WAIT_LONG, DURATION_WAIT_SHORT,
    OLD_CONTENT_SCALE, OLD_CONTENT_SHIFT_UP,
    CANVAS_MAX_WIDTH, CANVAS_BOTTOM_Y, CANVAS_TOP_Y, MAX_STACK_STEPS,
    LEFT_PANEL_X, LEFT_PANEL_TOP_Y, LEFT_PANEL_SCALE, LEFT_PANEL_SPACING,
    LEFT_PANEL_MAX_ITEMS, CENTER_CONTENT_Y, CENTER_CONTENT_MAX_WIDTH,
)


# ================================================================
# 一、全局画布背景设置
# ================================================================
def set_background(scene: Scene):
    """
    设置柔和浅灰画布背景
    替换Manim默认纯黑/纯白底色
    """
    # 创建一个占满整个画面的矩形作为背景
    bg = Rectangle(
        width=config.frame_width,
        height=config.frame_height,
        fill_color=Colors.BG,
        fill_opacity=1.0,
        stroke_width=0,
    )
    bg.z_index = -100  # 放在最底层
    scene.add(bg)
    return bg


# ================================================================
# 二、文本美化工具 — 核心函数
# ================================================================
def pretty_text(
    text: str,
    font_size: int = FONT_STEP,
    color: str = Colors.STEP_TEXT,
    font_family: str = FONT_FAMILY,
    weight: str = NORMAL,
    max_width: float = None,
) -> Text:
    """
    创建美化文本对象
    - 统一圆润无衬线中文字体
    - 指定字号和颜色
    - 支持最大宽度约束（自动换行 + 缩小字号）
    - 所有文字统一由此函数生成，保证全局风格一致
    """
    if max_width is None:
        max_width = CANVAS_MAX_WIDTH

    txt = Text(
        text,
        font=font_family,
        font_size=font_size,
        color=color,
        weight=weight,
        width=max_width,  # Manim CE 支持 width 参数自动换行
    )

    # 如果换行后仍然太宽（比如连续字母），进一步缩小字号
    if txt.width > max_width * 1.05:
        scale = max_width / txt.width * 0.95
        txt.scale(scale)
        # 也缩小字体定义本身
        txt.font_size = font_size * scale

    return txt


def pretty_text_with_bg(
    text: str,
    font_size: int = FONT_STEP,
    text_color: str = Colors.STEP_TEXT,
    bg_color: str = Colors.TEXT_BG,
    font_family: str = FONT_FAMILY,
    corner_radius: float = 0.15,
    buff: float = 0.2,
    max_width: float = None,
) -> VGroup:
    """
    创建带圆角半透明白底 + 柔和模糊阴影的美化文本
    所有场景统一使用此函数生成讲解文字，区分画面层级
    支持宽度约束和自动缩放防溢出
    """
    if max_width is None:
        max_width = CANVAS_MAX_WIDTH

    txt = Text(
        text,
        font=font_family,
        font_size=font_size,
        color=text_color,
        width=max_width,
    )

    # 如果换行后仍超宽，等比例缩小
    if txt.width > max_width * 1.05:
        scale = max_width / txt.width * 0.95
        txt.scale(scale)
    # 圆角背景框
    bg = RoundedRectangle(
        corner_radius=corner_radius,
        fill_color=bg_color,
        fill_opacity=0.85,
        stroke_color=parse_color(text_color),
        stroke_width=1.5,
        stroke_opacity=0.3,
    )
    bg.stretch_to_fit_width(txt.width + buff * 2)
    bg.stretch_to_fit_height(txt.height + buff * 2)
    bg.move_to(txt.get_center())

    # 柔和阴影（下方稍微偏移的深色背景）
    shadow = RoundedRectangle(
        corner_radius=corner_radius,
        fill_color=BLACK,
        fill_opacity=0.08,
        stroke_width=0,
    )
    shadow.stretch_to_fit_width(bg.width)
    shadow.stretch_to_fit_height(bg.height)
    shadow.move_to(bg.get_center() + DOWN * 0.06 + RIGHT * 0.04)
    shadow.z_index = bg.z_index - 0.1

    return VGroup(shadow, bg, txt)


def title_text(
    text: str,
    color: str = Colors.TITLE_TEXT,
) -> VGroup:
    """标题专用美化文本 — 大号、深色、居中"""
    return pretty_text_with_bg(
        text,
        font_size=FONT_TITLE,
        text_color=color,
        corner_radius=0.2,
        buff=0.3,
    )


def step_text(
    text: str,
    color: str = Colors.STEP_TEXT,
) -> VGroup:
    """步骤讲解专用美化文本"""
    return pretty_text_with_bg(
        text,
        font_size=FONT_STEP,
        text_color=color,
    )


def label_text(
    text: str,
    color: str = Colors.LABEL_TEXT,
) -> Text:
    """标注小字美化文本"""
    return pretty_text(
        text,
        font_size=FONT_LABEL,
        color=color,
    )


def annotation_text(
    text: str,
    color: str = Colors.DASHED,
) -> Text:
    """注释小字"""
    return pretty_text(
        text,
        font_size=FONT_ANNOTATION,
        color=color,
    )


def _has_latex() -> bool:
    """检测系统是否安装了LaTeX（pdflatex或xelatex）"""
    import shutil
    return shutil.which("pdflatex") is not None or shutil.which("xelatex") is not None


def math_text(
    latex: str,
    font_size: int = 32,
    color: str = Colors.STEP_TEXT,
) -> VMobject:
    """
    数学公式美化的MathTex对象
    统一字号和颜色，支持LaTeX渲染
    若LaTeX不可用，自动降级为Text渲染
    """
    if _has_latex():
        return MathTex(
            latex,
            font_size=font_size,
            color=color,
        )
    else:
        # LaTeX不可用时降级为Text渲染，做简单的Unicode映射
        display_text = _latex_to_unicode(latex)
        return Text(
            display_text,
            font=FONT_FAMILY,
            font_size=font_size,
            color=color,
        )


def _latex_to_unicode(latex: str) -> str:
    """将简单LaTeX公式转为Unicode文本显示"""
    import re

    text = latex

    # === 第0步：修复 JSON 转义导致的控制字符 ===
    # 当 LLM 在 JSON 中输出 \frac 而未正确双转义时，
    # json.loads 会将 \f 解析为换页符(0x0C)。还原为 \frac（仅当后面紧跟 "rac"）
    text = text.replace("\x0crac", "\\frac")
    # 同理修复 \fbox, \flat 等其他以 \f 开头的 LaTeX 命令
    text = text.replace("\x0cbox", "\\fbox")
    text = text.replace("\x0clat", "\\flat")

    # === 第1步：先处理结构化 LaTeX 命令（含括号参数） ===
    # \frac{a}{b} → (a)/(b)，确保括号配对正确
    def _replace_frac(m: re.Match) -> str:
        num = _extract_braced(m.group(1))
        den = _extract_braced(m.group(2))
        return f"({num})/({den})"

    def _extract_braced(s: str) -> str:
        """提取花括号内的内容，并递归处理嵌套"""
        s = s.strip()
        if s.startswith("{") and s.endswith("}"):
            # 简单情况：单层花括号
            depth = 0
            for i, c in enumerate(s):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                if depth == 0 and i < len(s) - 1:
                    # 括号在中间就闭合了，说明不是整体包裹
                    break
            else:
                # 整个字符串被一对括号包裹
                s = s[1:-1]
        return s

    # 处理 \frac{num}{den}
    text = re.sub(r'\\frac(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',
                  _replace_frac, text)

    # \sqrt{a} → √(a), \sqrt[n]{a} → ⁿ√(a)
    text = re.sub(r'\\sqrt\[([^\]]*)\]\{([^}]*)\}',
                  lambda m: f"({m.group(1)})√({m.group(2)})", text)
    text = re.sub(r'\\sqrt\{([^}]*)\}',
                  lambda m: f"√({m.group(1)})", text)

    # \text{xxx} / \mathrm{xxx} → xxx
    text = re.sub(r'\\(?:text|mathrm)\{([^}]*)\}', r'\1', text)

    # === 第2步：去掉反斜杠 ===
    text = text.replace("\\", "")

    # === 第3步：去掉花括号（\frac 的括号已在第1步处理） ===
    text = text.replace("{", "").replace("}", "")

    # === 第4步：简单关键词替换 ===
    replacements = {
        "cdot": "·", "times": "×", "div": "÷",
        "pm": "±", "leq": "≤", "geq": "≥",
        "neq": "≠", "approx": "≈", "equiv": "≡",
        "infty": "∞", "sum": "∑",
        "int": "∫", "pi": "π", "alpha": "α",
        "beta": "β", "theta": "θ", "lambda": "λ",
        "Delta": "Δ", "rightarrow": "→", "leftarrow": "←",
        "Rightarrow": "⇒", "Leftrightarrow": "⇔",
        "angle": "∠", "triangle": "△", "parallel": "∥",
        "perp": "⊥", "circ": "°", "degree": "°",
        "quad": "  ", "qquad": "    ",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    # 清理多余空格
    text = re.sub(r'\s+', ' ', text).strip()

    return text


# ================================================================
# 三、动画工具 — 全部顺滑缓慢，禁止瞬间闪现
# ================================================================

def smooth_create(
    scene: Scene,
    mobject: Mobject,
    duration: float = DURATION_CREATE,
    shift_dir: np.ndarray = None,
) -> Animation:
    """
    顺滑创建动画 — 滑入 + 淡入组合
    禁止瞬间FadeIn/FadeOut

    Args:
        scene: Manim场景
        mobject: 要显示的对象
        duration: 动画时长
        shift_dir: 入场方向（例如 UP, RIGHT, DOWN, LEFT）
    """
    if shift_dir is None:
        shift_dir = UP * 0.5

    anim = FadeIn(
        mobject,
        shift=shift_dir,
        scale=0.95,
        run_time=duration,
        rate_func=smooth,
    )
    scene.play(anim)
    return anim


def smooth_create_shape(
    scene: Scene,
    mobject: Mobject,
    duration: float = DURATION_CREATE,
) -> Animation:
    """
    几何图形匀速逐笔绘制 — Create动画，模拟黑板手写
    """
    anim = Create(
        mobject,
        run_time=duration,
        rate_func=linear,  # 匀速，模拟手写
    )
    scene.play(anim)
    return anim


def smooth_write(
    scene: Scene,
    mobject: Mobject,
    duration: float = DURATION_WRITE,
    shift_dir: np.ndarray = None,
) -> Animation:
    """
    文字逐字写入动画
    """
    if shift_dir is None:
        shift_dir = UP * 0.3

    anim = Write(
        mobject,
        run_time=duration,
        rate_func=smooth,
    )
    scene.play(anim)
    return anim


def smooth_grow(
    scene: Scene,
    mobject: Mobject,
    duration: float = DURATION_GROW,
    direction: np.ndarray = None,
) -> Animation:
    """
    图形从中心/边缘生长动画
    """
    if direction is not None:
        anim = GrowFromEdge(mobject, direction, run_time=duration, rate_func=smooth)
    else:
        anim = GrowFromCenter(mobject, run_time=duration, rate_func=smooth)
    scene.play(anim)
    return anim


def smooth_highlight(
    scene: Scene,
    mobject: Mobject,
    duration: float = DURATION_HIGHLIGHT,
) -> Animation:
    """
    高亮渐变扫光动画 — 柔和不闪烁
    给目标添加高亮背景框，缓慢渐入渐出
    """
    # 创建比目标稍大的高亮框
    highlight_box = RoundedRectangle(
        corner_radius=0.1,
        fill_color=Colors.HIGHLIGHT_BG,
        fill_opacity=0.0,
        stroke_color=Colors.HIGHLIGHT_BORDER,
        stroke_width=3,
        stroke_opacity=0.0,
    )
    highlight_box.stretch_to_fit_width(mobject.width + 0.3)
    highlight_box.stretch_to_fit_height(mobject.height + 0.2)
    highlight_box.move_to(mobject.get_center())
    highlight_box.z_index = mobject.z_index - 0.1

    scene.add(highlight_box)

    # 渐入高亮
    anim_in = highlight_box.animate.set_style(
        fill_opacity=0.3,
        stroke_opacity=0.8,
    ).set_run_time(duration * 0.5).set_rate_func(smooth)
    scene.play(anim_in)

    # 保持高亮
    scene.wait(0.5)

    # 渐出
    anim_out = highlight_box.animate.set_style(
        fill_opacity=0.0,
        stroke_opacity=0.0,
    ).set_run_time(duration * 0.5).set_rate_func(smooth)
    scene.play(anim_out)

    scene.remove(highlight_box)
    return anim_in


def smooth_transition(
    scene: Scene,
    old_elements: list[Mobject],
) -> None:
    """
    步骤间过渡动画 — 旧内容微缩上移，为新内容腾空间
    不使用FadeOut清除，只做位置和大小调整
    """
    if not old_elements:
        return

    animations = []
    for elem in old_elements:
        # 缩小 + 上移 + 稍微降低不透明度
        animations.append(elem.animate.scale(OLD_CONTENT_SCALE).shift(
            UP * OLD_CONTENT_SHIFT_UP
        ).set_opacity(0.7))

    scene.play(
        *animations,
        run_time=DURATION_TRANSITION,
        rate_func=smooth,
    )


# ================================================================
# 3.5 侧边栏布局 — 讲解完的内容缩放到左侧
# ================================================================
def move_to_left_sidebar(
    scene: Scene,
    elements: list[Mobject],
    sidebar_state: dict,
) -> None:
    """
    将当前已展示的元素缩放到左侧面板，为新内容腾出中央空间。

    布局逻辑：
    - 所有旧元素缩放至 LEFT_PANEL_SCALE
    - 按垂直方向堆叠排列在左侧面板
    - 自动检测边界，防止溢出

    Args:
        scene: Manim 场景
        elements: 要移入侧边栏的元素列表
        sidebar_state: 侧边栏状态字典，跟踪已占用行数
            {"count": int, "bottom_y": float}
    """
    if not elements:
        return

    count = sidebar_state.get("count", 0)
    animations = []

    # 如果侧边栏元素过多，进一步缩小比例
    scale = LEFT_PANEL_SCALE
    if count >= LEFT_PANEL_MAX_ITEMS:
        scale = LEFT_PANEL_SCALE * 0.7

    # 按从下到上排列：最旧的在最下面
    for i, elem in enumerate(elements):
        # 计算目标位置
        row = count + i
        target_y = LEFT_PANEL_TOP_Y - row * LEFT_PANEL_SPACING * 3.0

        # 如果超出底部，不再添加（防止溢出）
        if target_y < CANVAS_BOTTOM_Y + 0.5:
            # 所有剩余元素一起缩小并压缩间距
            scale *= 0.75
            target_y = LEFT_PANEL_TOP_Y - (row * 0.5) * LEFT_PANEL_SPACING * 3.0

        target_pos = np.array([LEFT_PANEL_X, target_y, 0])

        # 动画：缩放到侧边栏尺寸 + 移动到左侧 + 半透明
        animations.append(
            elem.animate.scale(scale).move_to(target_pos).set_opacity(0.65)
        )

    if animations:
        scene.play(
            *animations,
            run_time=DURATION_TRANSITION * 1.2,
            rate_func=smooth,
        )

    # 更新侧边栏状态
    sidebar_state["count"] = count + len(elements)
    sidebar_state["bottom_y"] = (
        LEFT_PANEL_TOP_Y - sidebar_state["count"] * LEFT_PANEL_SPACING * 3.0
    )


def position_in_center(
    new_element: Mobject,
    y_offset: float = None,
) -> Mobject:
    """
    将新元素放置在画面中央（用于当前正在讲解的内容）。

    自动检测宽度是否超出安全区域，超出时缩小。
    """
    if y_offset is None:
        y_offset = CENTER_CONTENT_Y

    new_element.move_to(np.array([0, y_offset, 0]))

    # 宽度安全检查
    if new_element.width > CENTER_CONTENT_MAX_WIDTH:
        scale_factor = CENTER_CONTENT_MAX_WIDTH / new_element.width * 0.9
        new_element.scale(scale_factor)

    # 高度安全检查（底部不能超出边界）
    if new_element.get_bottom()[1] < CANVAS_BOTTOM_Y + 0.3:
        overshoot = (CANVAS_BOTTOM_Y + 0.3) - new_element.get_bottom()[1]
        new_element.shift(UP * overshoot)

    # 顶部安全检查
    if new_element.get_top()[1] > CANVAS_TOP_Y - 0.3:
        overshoot = new_element.get_top()[1] - (CANVAS_TOP_Y - 0.3)
        new_element.shift(DOWN * overshoot)

    return new_element


def position_in_center_safe(
    new_element: Mobject,
    existing_center: list[Mobject] = None,
    y_offset: float = None,
) -> Mobject:
    """
    将新元素放在画面中央，同时考虑当前中央是否已有元素。

    如果中央已有内容，先将其移至侧边栏，再放置新内容。
    """
    if y_offset is None:
        y_offset = CENTER_CONTENT_Y

    new_element.move_to(np.array([0, y_offset, 0]))

    # 宽度安全检查
    if new_element.width > CENTER_CONTENT_MAX_WIDTH:
        scale_factor = CENTER_CONTENT_MAX_WIDTH / new_element.width * 0.9
        new_element.scale(scale_factor)

    # 高度安全检查
    if new_element.get_bottom()[1] < CANVAS_BOTTOM_Y + 0.5:
        overshoot = (CANVAS_BOTTOM_Y + 0.5) - new_element.get_bottom()[1]
        new_element.shift(UP * overshoot)

    if new_element.get_top()[1] > CANVAS_TOP_Y - 0.5:
        overshoot = new_element.get_top()[1] - (CANVAS_TOP_Y - 0.5)
        new_element.shift(DOWN * overshoot)

    return new_element


def gentle_pause(scene: Scene, duration: float = 1.0) -> None:
    """柔和停顿"""
    scene.wait(duration)


# ================================================================
# 四、通用绘图工具 — 所有场景直接调用
# ================================================================

def draw_angle_mark(
    scene: Scene,
    vertex: np.ndarray,
    point_a: np.ndarray,
    point_b: np.ndarray,
    radius: float = 0.5,
    color: str = Colors.DASHED,
    label: str = "",
    duration: float = DURATION_CREATE,
) -> VGroup:
    """
    绘制角度弧线标注
    Args:
        vertex: 角的顶点坐标
        point_a: 角的一边上的一点
        point_b: 角的另一边上的一点
        radius: 弧线半径
        color: 弧线颜色
        label: 角度文字标签
        duration: 动画时长
    Returns:
        角度标注组（弧线 + 标签）
    """
    # 创建两条线用于Angle构造
    line1 = Line(vertex, point_a)
    line2 = Line(vertex, point_b)
    angle = Angle(line1, line2, radius=radius, color=color)

    group = VGroup(angle)
    scene.play(Create(angle, run_time=duration, rate_func=linear))

    if label:
        lbl = Tex(label, font_size=FONT_ANNOTATION, color=color)
        lbl.next_to(angle.get_center(), UP * 0.3 + RIGHT * 0.3)
        group.add(lbl)
        scene.play(FadeIn(lbl, shift=UP * 0.2, run_time=0.5))

    return group


def draw_right_angle_mark(
    scene: Scene,
    vertex: np.ndarray,
    point_a: np.ndarray,
    point_b: np.ndarray,
    length: float = 0.3,
    color: str = Colors.VERTEX,
    duration: float = DURATION_CREATE,
) -> VMobject:
    """
    绘制直角标记
    Args:
        vertex: 直角顶点
        point_a: 一条直角边上的点
        point_b: 另一条直角边上的点
        length: 直角标记边长
        color: 标记颜色
        duration: 动画时长
    """
    line1 = Line(vertex, point_a)
    line2 = Line(vertex, point_b)
    right_angle = RightAngle(line1, line2, length=length, color=color)

    scene.play(Create(right_angle, run_time=duration))
    return right_angle


def draw_vertex_label(
    scene: Scene,
    point: np.ndarray,
    label: str,
    color: str = Colors.VERTEX,
    font_size: int = FONT_LABEL,
    direction: np.ndarray = None,
    duration: float = DURATION_SLIDE_IN,
) -> Text:
    """
    绘制顶点字母标签
    Args:
        point: 顶点坐标
        label: 字母标签（如'A', 'B', 'C'）
        color: 文字颜色
        font_size: 字号
        direction: 标签偏移方向
        duration: 动画时长
    """
    if direction is None:
        direction = UR * 0.3

    txt = Text(
        label,
        font=FONT_FAMILY,
        font_size=font_size,
        color=color,
        weight=BOLD,
    )
    txt.next_to(point, direction, buff=0.1)
    scene.play(FadeIn(txt, shift=direction * 0.5, run_time=duration))
    return txt


def draw_side_label(
    scene: Scene,
    start_point: np.ndarray,
    end_point: np.ndarray,
    label: str,
    color: str = Colors.KNOWN,
    font_size: int = FONT_LABEL,
    offset: float = 0.3,
    duration: float = DURATION_SLIDE_IN,
) -> Text:
    """
    绘制边长标注
    Args:
        start_point: 线段起点
        end_point: 线段终点
        label: 标注文字
        color: 文字颜色
        font_size: 字号
        offset: 与线段的偏移距离
    """
    mid = (start_point + end_point) / 2
    line_dir = end_point - start_point
    # 垂直于线段方向
    perp = np.array([-line_dir[1], line_dir[0], 0])
    norm = np.linalg.norm(perp) if np.linalg.norm(perp) > 0 else UP
    perp = perp / norm * offset

    txt = Text(
        label,
        font=FONT_FAMILY,
        font_size=font_size,
        color=color,
    )
    txt.move_to(mid + perp)
    scene.play(FadeIn(txt, shift=perp * 0.3, run_time=duration))
    return txt


def draw_dashed_line(
    scene: Scene,
    start: np.ndarray,
    end: np.ndarray,
    color: str = Colors.DASHED,
    dash_length: float = 0.15,
    duration: float = DURATION_CREATE,
) -> DashedLine:
    """
    绘制虚线辅助线
    """
    line = DashedLine(
        start, end,
        color=color,
        dash_length=dash_length,
    )
    scene.play(Create(line, run_time=duration, rate_func=linear))
    return line


def draw_dot_point(
    scene: Scene,
    point: np.ndarray,
    color: str = Colors.VERTEX,
    radius: float = 0.06,
    duration: float = DURATION_GROW,
) -> Dot:
    """
    在指定坐标绘制圆点
    """
    dot = Dot(point=point, radius=radius, color=color)
    scene.play(GrowFromCenter(dot, run_time=duration))
    return dot


def draw_segment_highlight(
    scene: Scene,
    start: np.ndarray,
    end: np.ndarray,
    color: str = Colors.HIGHLIGHT_BORDER,
    stroke_width: float = 6,
    duration: float = DURATION_HIGHLIGHT,
) -> Line:
    """
    绘制加粗高亮线段（用于强调特定边）
    """
    line = Line(start, end, color=color, stroke_width=stroke_width)
    scene.play(Create(line, run_time=duration, rate_func=smooth))
    return line


# ================================================================
# 五、排版布局工具
# ================================================================

def position_below(
    new_element: Mobject,
    existing_elements: list[Mobject],
    buff: float = 0.5,
    bottom_limit: float = None,
) -> Mobject:
    """
    将新元素放在所有已有元素下方
    实现内容向下叠加、不重叠

    自动处理底部越界：如果新元素会超出画布底部，触发
    全局缩放旧内容以腾出空间。
    """
    if bottom_limit is None:
        bottom_limit = CANVAS_BOTTOM_Y

    if not existing_elements:
        # 无已有元素时，居中放置
        new_element.move_to(ORIGIN)
        # 检查是否超底部（理论上不应该，但防御）
        if new_element.get_bottom()[1] < bottom_limit:
            new_element.move_to(ORIGIN + UP * 1.0)
        return new_element

    # 找到最下方的元素
    lowest = existing_elements[0]
    for elem in existing_elements:
        if elem.get_bottom()[1] < lowest.get_bottom()[1]:
            lowest = elem

    # 放在最下方元素下面
    new_element.next_to(lowest, DOWN, buff=buff)

    # 检查是否超出底部边界
    if new_element.get_bottom()[1] < bottom_limit:
        # 计算需要腾出的空间
        overflow = bottom_limit - new_element.get_bottom()[1]
        # 收缩所有旧内容并上移
        shrink_scale = 0.82
        for elem in existing_elements:
            if hasattr(elem, 'animate'):
                elem.scale(shrink_scale)
                elem.shift(UP * abs(overflow) * 0.5)
        # 重新定位新元素
        lowest_after = min(existing_elements, key=lambda e: e.get_bottom()[1])
        new_element.next_to(lowest_after, DOWN, buff=buff * 0.7)

    return new_element


def position_to_right(
    new_element: Mobject,
    existing_elements: list[Mobject],
    buff: float = 0.5,
) -> Mobject:
    """将新元素放在已有元素右侧"""
    if not existing_elements:
        return new_element

    rightmost = existing_elements[0]
    for elem in existing_elements:
        if elem.get_right()[0] > rightmost.get_right()[0]:
            rightmost = elem

    new_element.next_to(rightmost, RIGHT, buff=buff)
    return new_element


# ================================================================
# 六、方程对齐辅助
# ================================================================
def create_aligned_equations(
    equations: list[str],
    font_size: int = 32,
    color: str = Colors.STEP_TEXT,
) -> VGroup:
    """
    创建等号对齐的方程列表
    每行等号在相同x坐标，方便对比变形过程
    """
    parts = []
    for eq in equations:
        if "=" in eq:
            left, right = eq.split("=", 1)
            left_tex = MathTex(left.strip(), font_size=font_size, color=color)
            eq_sign = MathTex("=", font_size=font_size, color=color)
            right_tex = MathTex(right.strip(), font_size=font_size, color=color)
            parts.append(VGroup(left_tex, eq_sign, right_tex).arrange(RIGHT, buff=0.1))
        else:
            parts.append(MathTex(eq, font_size=font_size, color=color))

    group = VGroup(*parts).arrange(DOWN, buff=0.3, aligned_edge=LEFT)
    return group


# ================================================================
# 七、Matplotlib配色转Manim颜色
# ================================================================
def parse_color(color_str: str) -> str:
    """
    将十六进制颜色（#3498DB）转换为Manim颜色表示
    Manim CE支持直接使用十六进制字符串
    """
    return color_str


# ================================================================
# 八、场景初始化基类工厂
# ================================================================
class BaseMathScene(Scene):
    """
    所有题型场景基类
    统一管理：
    - 画布背景设置
    - 元素持久化缓存 (self.all_elements)
    - 步骤过渡逻辑
    - 侧边栏布局（讲解完的内容缩放到左侧）
    - 禁止清屏约束
    """

    def setup(self):
        """场景初始化 — 在construct()之前调用"""
        # 缓存所有画面元素的列表（强制持久化）
        self.all_elements: list[Mobject] = []
        # 设置柔和背景
        self.bg = set_background(self)
        # 当前步骤计数
        self.current_step = 0
        # 侧边栏状态
        self.sidebar_state = {"count": 0, "bottom_y": LEFT_PANEL_TOP_Y}
        # 中央区域当前展示的元素（会被移入侧边栏）
        self.center_elements: list[Mobject] = []

    def add_to_all(self, *mobjects: Mobject) -> None:
        """将元素添加到画面并存入持久化缓存"""
        for mob in mobjects:
            self.add(mob)
            self.all_elements.append(mob)

    def add_to_center(self, *mobjects: Mobject) -> None:
        """将元素添加到中央展示区域（后续会被移入侧边栏）"""
        for mob in mobjects:
            self.add(mob)
            self.all_elements.append(mob)
            self.center_elements.append(mob)

    def play_and_record(self, *animations: Animation) -> None:
        """
        播放动画并记录产生的元素
        覆盖self.play以追踪所有新增元素
        """
        self.play(*animations)
        # 动画中的mobjects自动会被add，这里记录新元素
        for anim in animations:
            for mob in anim.mobjects:
                if mob not in self.all_elements:
                    self.all_elements.append(mob)

    def new_step(self) -> None:
        """开始新步骤前的准备 — 旧内容移入侧边栏"""
        self.current_step += 1

    def step_transition(self) -> None:
        """
        步骤过渡：将中央区域的内容移入左侧侧边栏。
        旧内容缩小并排列在左侧，为新的中央内容腾出空间。
        """
        if self.center_elements:
            move_to_left_sidebar(self, self.center_elements, self.sidebar_state)
            self.center_elements = []

    def finalize_scene(self) -> None:
        """最终画面停留，展示完整推导过程"""
        # 不需要特殊操作，所有元素已在画布上
        self.wait(DURATION_WAIT_LONG)
