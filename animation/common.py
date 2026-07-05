"""
============================================================
MathAnimAI — 全局公共美化工具库 (common.py)
所有场景共用的动画、文本、绘图工具函数。
统一配色、字体、动画参数，禁止各场景重复实现。
============================================================
"""

from manim import *
import numpy as np
import os
import json
import logging

from config import (
    Colors, FONT_FAMILY, FONT_TITLE, FONT_STEP, FONT_LABEL, FONT_ANNOTATION,
    FONT_SUBTITLE, FONT_CONCLUSION,
    DURATION_CREATE, DURATION_SLIDE_IN, DURATION_HIGHLIGHT,
    DURATION_TRANSITION, DURATION_WRITE, DURATION_GROW, DURATION_SHIFT,
    DURATION_FADE, DURATION_WAIT_LONG, DURATION_WAIT_SHORT,
    OLD_CONTENT_SCALE, OLD_CONTENT_SHIFT_UP,
    CANVAS_MAX_WIDTH, CANVAS_BOTTOM_Y, CANVAS_TOP_Y, MAX_STACK_STEPS,
    LEFT_PANEL_X, LEFT_PANEL_TOP_Y, LEFT_PANEL_SCALE, LEFT_PANEL_SPACING,
    LEFT_PANEL_MAX_ITEMS, CENTER_CONTENT_Y, CENTER_CONTENT_MAX_WIDTH,
)

logger = logging.getLogger("MathAnimAI.Common")


# ================================================================
# 一、全局画布背景设置（参考模板：直接设置 camera.background_color）
# ================================================================
def set_background(scene: Scene):
    """
    设置深色画布背景（参考模板 #1a1a2e）
    深色背景下白色文字和亮色图形更清晰美观
    """
    scene.camera.background_color = Colors.BG
    return None


# ================================================================
# 二、文本美化工具 — 参考模板：深色背景下纯Text，无需背景框
# ================================================================

# Microsoft YaHei 缺少字形的数学符号集合
# 当文本包含这些字符时，不指定字体让 Pango 自动回退到有对应字形的字体
# 包含：数学运算符、希腊字母、上下标、几何符号、逻辑符号等
_MATH_SYMBOLS = set('×÷≤≥≠±≈≡∞∑∫√∠△∥⊥⌀∝∈∉∪∩⊂⊃⊆⊇∀∃∇∂δµΩρσφψχω→←↑↓↔⇒⇐⇔∴∵⟂∡∢')
# 补充：上标、下标、度数等常见数学排版字符
_MATH_SYMBOLS |= set('°²³¹⁰⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎')
# 补充：分数、百分比等
_MATH_SYMBOLS |= set('½⅓⅔¼¾‰‰')
# 补充：更多希腊大写字母
_MATH_SYMBOLS |= set('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨ')

# 尝试检测系统中是否有支持数学符号的字体
_MATH_FONT_CANDIDATES = ["Cambria Math", "Segoe UI Symbol", "DejaVu Sans", "STIX Two Math"]
_cached_math_font = None

def _get_math_font():
    """检测可用的数学符号字体"""
    global _cached_math_font
    if _cached_math_font is not None:
        return _cached_math_font
    import shutil
    fonts_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    for font_name in _MATH_FONT_CANDIDATES:
        # 简单检测：字体文件名中包含关键词
        font_file = font_name.replace(" ", "") + ".ttf"
        font_file_lower = font_file.lower()
        try:
            for f in os.listdir(fonts_dir):
                if font_file_lower in f.lower():
                    _cached_math_font = font_name
                    return font_name
        except OSError:
            pass
    _cached_math_font = ""  # 没找到
    return _cached_math_font

def _has_math_symbols(text: str) -> bool:
    """检测文本是否包含 Microsoft YaHei 无法渲染的数学符号"""
    return any(c in _MATH_SYMBOLS for c in text)

def smart_text(
    text: str,
    font_size: int = FONT_STEP,
    color: str = Colors.STEP_TEXT,
    weight: str = NORMAL,
    max_width: float = None,
) -> Text:
    """
    智能文本渲染 — 自动处理数学符号的字体回退。
    
    当文本包含数学符号（×, ÷, ≤, ∠, √等）时：
    - 不指定 font 参数，让 Pango 自动回退到系统字体
    - 这样数学符号会用 Cambria Math/Segoe UI Symbol 等渲染
    - 中文字符也会通过 Pango 字体回退正常显示
    
    当文本不含数学符号时：
    - 使用 Microsoft YaHei 字体保证中文美观
    """
    if _has_math_symbols(text):
        txt = Text(
            text,
            font_size=font_size,
            color=color,
            weight=weight,
        )
    else:
        txt = Text(
            text,
            font=FONT_FAMILY,
            font_size=font_size,
            color=color,
            weight=weight,
        )
    # 宽度安全检查
    if max_width is None:
        max_width = CANVAS_MAX_WIDTH
    if txt.width > max_width:
        txt.scale(max_width / txt.width * 0.9)
    return txt

def pretty_text(
    text: str,
    font_size: int = FONT_STEP,
    color: str = Colors.STEP_TEXT,
    font_family: str = FONT_FAMILY,
    weight: str = NORMAL,
    max_width: float = None,
) -> Text:
    """
    创建美化文本对象（参考模板风格）
    深色背景下使用白色文字，简洁干净，无需圆角背景框
    自动处理数学符号字体回退
    """
    if _has_math_symbols(text):
        # 含数学符号，不指定字体让 Pango 回退
        txt = Text(
            text,
            font_size=font_size,
            color=color,
            weight=weight,
        )
    else:
        txt = Text(
            text,
            font=font_family,
            font_size=font_size,
            color=color,
            weight=weight,
        )
    # 宽度安全检查
    if max_width is None:
        max_width = CANVAS_MAX_WIDTH
    if txt.width > max_width:
        txt.scale(max_width / txt.width * 0.9)
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
    带半透明背景的文本（仅用于特殊强调场景，日常文字用 pretty_text）
    """
    if max_width is None:
        max_width = CANVAS_MAX_WIDTH

    if _has_math_symbols(text):
        txt = Text(text, font_size=font_size, color=text_color)
    else:
        txt = Text(text, font=font_family, font_size=font_size, color=text_color)
    if txt.width > max_width:
        txt.scale(max_width / txt.width * 0.9)
    # 半透明深色背景框
    bg = RoundedRectangle(
        corner_radius=corner_radius,
        fill_color=bg_color,
        fill_opacity=0.6,
        stroke_color=Colors.PRIMARY,
        stroke_width=1.5,
        stroke_opacity=0.3,
    )
    bg.stretch_to_fit_width(txt.width + buff * 2)
    bg.stretch_to_fit_height(txt.height + buff * 2)
    bg.move_to(txt.get_center())
    return VGroup(bg, txt)


def title_text(
    text: str,
    color: str = Colors.TITLE_TEXT,
) -> Text:
    """标题专用文本 — 大号、白色、粗体（参考模板风格）"""
    return pretty_text(
        text,
        font_size=FONT_TITLE,
        color=color,
        weight=BOLD,
    )


def step_text(
    text: str,
    color: str = Colors.STEP_TEXT,
) -> Text:
    """步骤讲解专用文本 — 白色纯文字，无背景框"""
    return pretty_text(
        text,
        font_size=FONT_STEP,
        color=color,
    )


def label_text(
    text: str,
    color: str = Colors.LABEL_TEXT,
) -> Text:
    """标注小字文本"""
    return pretty_text(
        text,
        font_size=FONT_LABEL,
        color=color,
        weight=BOLD,
    )


def annotation_text(
    text: str,
    color: str = Colors.TEXT_SECONDARY,
) -> Text:
    """注释小字"""
    return pretty_text(
        text,
        font_size=FONT_ANNOTATION,
        color=color,
    )


# ================================================================
# 二(补充)、字幕系统 — 参考模板 script_scaffold.py
# ================================================================
def create_subtitle(
    text: str,
    font_size: int = FONT_SUBTITLE,
    color: str = Colors.STEP_TEXT,
) -> Text:
    """
    创建字幕对象（参考模板 create_subtitle）
    字幕放在画面底部 to_edge(DOWN, buff=0.5)，纯文字无背景框
    """
    if _has_math_symbols(text):
        subtitle = Text(text, font_size=font_size, color=color)
    else:
        subtitle = Text(text, font=FONT_FAMILY, font_size=font_size, color=color)
    # 宽度安全检查：字幕不应超出画布
    if subtitle.width > CANVAS_MAX_WIDTH:
        subtitle.scale(CANVAS_MAX_WIDTH / subtitle.width * 0.9)
    subtitle.to_edge(DOWN, buff=0.5)
    return subtitle


def show_subtitle_timed(
    scene: Scene,
    text: str,
    duration: float,
    font_size: int = FONT_SUBTITLE,
    fade_in_time: float = DURATION_FADE,
    fade_out_time: float = DURATION_FADE,
) -> Text:
    """
    显示字幕并在指定时间后自动退场（参考模板 show_subtitle_timed）
    """
    subtitle = create_subtitle(text, font_size=font_size)
    scene.play(FadeIn(subtitle, run_time=fade_in_time))
    hold_time = max(0.0, duration - fade_in_time - fade_out_time)
    scene.wait(hold_time)
    scene.play(FadeOut(subtitle, run_time=fade_out_time))
    return subtitle


def show_subtitle_with_audio(
    scene: Scene,
    text: str,
    audio_duration: float,
    font_size: int = FONT_SUBTITLE,
) -> Text:
    """
    显示字幕并持续到音频结束（参考模板 show_subtitle_with_audio）
    """
    subtitle = create_subtitle(text, font_size=font_size)
    scene.play(FadeIn(subtitle, run_time=DURATION_FADE))
    scene.wait(max(0.0, audio_duration - 1.0))
    scene.play(FadeOut(subtitle, run_time=DURATION_FADE))
    return subtitle


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
        # 不指定字体，让 Pango 自动回退以正确显示数学符号
        return Text(
            display_text,
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
# 三、动画工具 — 参考模板：简洁明快，FadeIn/FadeOut/Create/Write
# ================================================================

def smooth_create(
    scene: Scene,
    mobject: Mobject,
    duration: float = DURATION_CREATE,
    shift_dir: np.ndarray = None,
) -> Animation:
    """
    文字淡入动画（参考模板 FadeIn run_time=0.5）
    """
    if shift_dir is None:
        shift_dir = UP * 0.3
    anim = FadeIn(
        mobject,
        shift=shift_dir,
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
    几何图形逐笔绘制（参考模板 Create run_time=1.0）
    """
    anim = Create(
        mobject,
        run_time=duration,
        rate_func=linear,
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
    文字逐字写入（参考模板 Write run_time=0.5）
    """
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
    图形从中心生长（参考模板 GrowFromCenter）
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
    高亮动画（参考模板 highlight_element: scale 1.3 + color change）
    简洁的缩放+变色，避免复杂的扫光效果
    """
    original_color = mobject.get_color() if hasattr(mobject, 'get_color') else Colors.TEXT
    # 缩放+变色
    scene.play(
        mobject.animate.scale(1.15).set_color(Colors.HIGHLIGHT),
        run_time=duration * 0.5,
        rate_func=smooth,
    )
    scene.wait(0.3)
    # 恢复
    scene.play(
        mobject.animate.scale(1/1.15).set_color(original_color),
        run_time=duration * 0.5,
        rate_func=smooth,
    )
    return None


def smooth_transition(
    scene: Scene,
    old_elements: list[Mobject],
) -> None:
    """
    步骤间过渡 — 旧内容淡出（参考模板：每幕结束 FadeOut 清理）
    """
    if not old_elements:
        return
    animations = [FadeOut(elem) for elem in old_elements]
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
    - 自动检测边界，动态调整间距防止溢出

    Args:
        scene: Manim 场景
        elements: 要移入侧边栏的元素列表
        sidebar_state: 侧边栏状态字典，跟踪已占用行数
            {"count": int, "bottom_y": float}
    """
    if not elements:
        return

    count = sidebar_state.get("count", 0)
    total_items = count + len(elements)
    animations = []

    # 动态计算缩放比例和间距
    scale = LEFT_PANEL_SCALE
    if total_items > LEFT_PANEL_MAX_ITEMS:
        # 元素过多时进一步缩小
        scale = LEFT_PANEL_SCALE * max(0.5, LEFT_PANEL_MAX_ITEMS / total_items)

    # 动态间距：根据元素数量自动调整，确保不溢出
    available_height = LEFT_PANEL_TOP_Y - (CANVAS_BOTTOM_Y + 0.5)
    if total_items > 0:
        spacing = min(LEFT_PANEL_SPACING * 3.0, available_height / total_items)
    else:
        spacing = LEFT_PANEL_SPACING * 3.0

    # 按从下到上排列：最旧的在最下面
    for i, elem in enumerate(elements):
        row = count + i
        target_y = LEFT_PANEL_TOP_Y - row * spacing

        # 硬性边界检查：确保不溢出底部
        if target_y < CANVAS_BOTTOM_Y + 0.5:
            # 压缩所有元素到更小的间距
            spacing = available_height / max(total_items, 1)
            target_y = LEFT_PANEL_TOP_Y - row * spacing

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
    sidebar_state["count"] = total_items
    sidebar_state["bottom_y"] = (
        LEFT_PANEL_TOP_Y - total_items * spacing
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

    如果中央已有内容，新元素会放在已有内容下方，避免重叠。
    """
    if y_offset is None:
        y_offset = CENTER_CONTENT_Y

    # 如果有已有中央元素，将新元素放在最下方元素下面
    if existing_center:
        try:
            lowest = existing_center[0]
            for elem in existing_center:
                if elem.get_bottom()[1] < lowest.get_bottom()[1]:
                    lowest = elem
            new_element.next_to(lowest, DOWN, buff=0.4)
        except Exception:
            new_element.move_to(np.array([0, y_offset, 0]))
    else:
        new_element.move_to(np.array([0, y_offset, 0]))

    # 宽度安全检查
    if new_element.width > CENTER_CONTENT_MAX_WIDTH:
        scale_factor = CENTER_CONTENT_MAX_WIDTH / new_element.width * 0.9
        new_element.scale(scale_factor)

    # 高度安全检查 — 底部不能超出边界
    if new_element.get_bottom()[1] < CANVAS_BOTTOM_Y + 0.5:
        overshoot = (CANVAS_BOTTOM_Y + 0.5) - new_element.get_bottom()[1]
        new_element.shift(UP * overshoot)

    # 顶部安全检查 — 不能与标题重叠
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
    color: str = Colors.HIGHLIGHT,
    label: str = "",
    duration: float = DURATION_CREATE,
) -> VGroup:
    """
    绘制角度弧线标注（参考模板：使用 Sector/Angle + 颜色标注）
    """
    line1 = Line(vertex, point_a)
    line2 = Line(vertex, point_b)
    angle = Angle(line1, line2, radius=radius, color=color)

    group = VGroup(angle)
    scene.play(Create(angle, run_time=duration, rate_func=linear))

    if label:
        # 使用 smart_text 自动处理数学符号（如 °、∠ 等）
        lbl = smart_text(label, font_size=FONT_ANNOTATION, color=color)
        lbl.next_to(angle.get_center(), UP * 0.3 + RIGHT * 0.3)
        group.add(lbl)
        scene.play(FadeIn(lbl, shift=UP * 0.2, run_time=DURATION_FADE))

    return group


def draw_right_angle_mark(
    scene: Scene,
    vertex: np.ndarray,
    point_a: np.ndarray,
    point_b: np.ndarray,
    length: float = 0.3,
    color: str = Colors.HIGHLIGHT,
    duration: float = 0.5,
) -> VMobject:
    """
    绘制直角标记（参考模板：使用 RightAngle）
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
    color: str = Colors.HIGHLIGHT,
    font_size: int = FONT_LABEL,
    direction: np.ndarray = None,
    duration: float = DURATION_FADE,
) -> Text:
    """
    绘制顶点字母标签（参考模板：Text + next_to 偏移）
    """
    if direction is None:
        direction = UR * 0.3

    txt = smart_text(label, font_size=font_size, color=color, weight=BOLD)
    txt.next_to(point, direction, buff=0.1)
    scene.play(FadeIn(txt, shift=direction * 0.5, run_time=duration))
    return txt


def draw_side_label(
    scene: Scene,
    start_point: np.ndarray,
    end_point: np.ndarray,
    label: str,
    color: str = Colors.TEXT,
    font_size: int = FONT_LABEL,
    offset: float = 0.3,
    duration: float = DURATION_FADE,
) -> Text:
    """
    绘制边长标注
    """
    mid = (start_point + end_point) / 2
    line_dir = end_point - start_point
    perp = np.array([-line_dir[1], line_dir[0], 0])
    norm = np.linalg.norm(perp) if np.linalg.norm(perp) > 0 else UP
    perp = perp / norm * offset

    txt = smart_text(label, font_size=font_size, color=color)
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
    创建等号对齐的方程列表（使用 Text 代替 MathTex，避免 LaTeX 依赖）
    """
    parts = []
    for eq in equations:
        # 使用 smart_text 自动处理数学符号字体回退
        txt = smart_text(eq, font_size=font_size, color=color)
        parts.append(txt)

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
    - 音画同步基础设施（add_sound + end_scene_with_audio）
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
        # ===== 图形偏移量跟踪 =====
        # 当 position_in_center_safe() 移动基础图形后，记录偏移量
        # 后续 mark_right_angle / label_vertex 等步骤需要用偏移修正坐标
        self._figure_offset = np.array([0.0, 0.0, 0.0])

        # ===== 音画同步基础设施 =====
        # 当前幕的起始时间戳（Manim 全局动画时钟）
        self._scene_start_time = 0.0
        # 音频安全余量（秒），确保动画不抢跑导致音频重叠
        self._audio_safety_margin = 0.3
        # 当前幕的音频时长
        self._current_audio_duration = 0.0
        # 音画同步是否已启用
        self._audio_sync_enabled = False

    # ================================================================
    # 音画同步方法（参考 MathLens 模板项目的 script_scaffold.py）
    # ================================================================
    def start_scene_with_audio(
        self,
        step_num: int,
        audio_path: str = None,
        expected_duration: float = 0.0,
    ) -> float:
        """
        开始一个步骤并播放该步骤的音频（防重叠入口）。

        核心机制：
        1. 记录当前 Manim 时间戳 self.time 作为幕起始时间
        2. 调用 self.add_sound() 将音频嵌入 Manim 时间轴
        3. 音频和动画从此刻起共享同一时间轴，实现帧级同步

        Args:
            step_num: 步骤编号
            audio_path: 音频文件绝对路径（None 则不播放音频）
            expected_duration: 该步骤音频的预期时长（秒）

        Returns:
            音频预期时长（秒）
        """
        self.current_step = step_num
        self._scene_start_time = self.time
        self._current_audio_duration = float(expected_duration)
        self._audio_sync_enabled = True

        if audio_path and os.path.exists(audio_path):
            try:
                self.add_sound(audio_path)
                logger.info(
                    f"  [同步] 步骤{step_num}: add_sound({os.path.basename(audio_path)}) "
                    f"duration={expected_duration:.2f}s t={self._scene_start_time:.2f}s"
                )
            except Exception as e:
                logger.warning(f"  [同步] 步骤{step_num} add_sound 失败: {e}")
        else:
            if audio_path:
                logger.warning(f"  [同步] 步骤{step_num} 音频文件不存在: {audio_path}")

        return float(expected_duration)

    def end_scene_with_audio(
        self,
        expected_duration: float = None,
        safety_margin: float = None,
    ) -> None:
        """
        结束一个步骤并补足等待，确保动画时长 >= 音频时长 + 安全余量。

        核心机制：
        1. 计算 elapsed = self.time - self._scene_start_time（实际已用时间）
        2. 计算 target = audio_duration + safety_margin
        3. 如果 remaining > 0，调用 self.wait(remaining) 自动补齐
        4. 这确保下一幕不会提前开始导致音频重叠

        与旧的 wait(audio_dur - anim_overhead) 方式的区别：
        - 旧方式：用硬编码估算动画时长（ANIM_TYPE_DURATION），不精确
        - 新方式：用 self.time 运行时实际测量，帧级精确
        """
        if not self._audio_sync_enabled:
            return

        if expected_duration is None:
            expected_duration = self._current_audio_duration
        if safety_margin is None:
            safety_margin = self._audio_safety_margin

        elapsed = self.time - self._scene_start_time
        target = max(0.0, float(expected_duration)) + max(0.0, float(safety_margin))
        remaining = target - elapsed

        if remaining > 1e-3:
            self.wait(remaining)
            elapsed = self.time - self._scene_start_time

        if elapsed + 1e-3 < target:
            logger.warning(
                f"  [同步] 步骤{self.current_step} 时间偏短: "
                f"elapsed={elapsed:.2f}s < target={target:.2f}s"
            )
        else:
            logger.info(
                f"  [同步] 步骤{self.current_step} 完成: "
                f"elapsed={elapsed:.2f}s / target={target:.2f}s"
            )

        self._audio_sync_enabled = False

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
        步骤过渡：将中央区域的临时内容淡出（参考模板：每幕结束 FadeOut 清理）。
        基础图形（add_to_all 添加的）保持不动，仅清除中央临时内容（add_to_center 添加的）。
        """
        if self.center_elements:
            # 淡出中央临时内容
            fade_outs = [FadeOut(elem) for elem in self.center_elements]
            self.play(*fade_outs, run_time=DURATION_TRANSITION, rate_func=smooth)
            # 从持久化缓存中也移除
            for elem in self.center_elements:
                if elem in self.all_elements:
                    self.all_elements.remove(elem)
            self.center_elements = []

    def finalize_scene(self) -> None:
        """最终画面停留，展示完整推导过程"""
        # 不需要特殊操作，所有元素已在画布上
        self.wait(DURATION_WAIT_LONG)
