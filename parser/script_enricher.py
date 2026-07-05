"""
============================================================
MathAnimAI — LLM 脚本后处理增强器
功能：
  1. 几何题自动生成 base_figure（LLM 经常不提供）
  2. 空 config 的几何步骤自动推断坐标（label_vertex/label_side/
     mark_angle/mark_right_angle/draw_shape/draw_dashed_line）
  3. 修复 LaTeX 乱码（\rac → \frac, \t → \times 等）
  4. draw_shape 无点时自动降级为 text_slide_in
  5. 确保几何题步骤序列合理（有 base_figure 后自动补 draw_shape）

设计理念：qwen2.5:7b 等小模型能生成正确的 animation_type 名称，
但经常不提供 config 中的坐标数据。此模块在 LLM 输出后、builder 之前
自动补全缺失数据，使画面不再空白。
============================================================
"""

import re
import logging
import math
from typing import Optional

from parser.schema import (
    ProblemScript, ProblemType, Step, AnimationType,
    GeoElement, CoordinateConfig,
)

logger = logging.getLogger("MathAnimAI.Enricher")


# ================================================================
# 一、LaTeX 修复
# ================================================================
def fix_latex(text: str) -> str:
    """修复 LLM 生成的常见 LaTeX 乱码"""
    if not text:
        return text

    fixes = [
        # qwen2.5 常见错误：\rac → \frac
        (r'\\rac\b', r'\\frac'),
        # \t (tab) → \times（只在 \t 后面不是字母时才替换，避免误伤 \text 等）
        (r'\\t(?!\w)', r'\\times '),
        # \au → \tau (圆周率)
        (r'\\au\b', r'\\tau '),
        # \het → \theta
        (r'\\het\b', r'\\theta '),
        # 修复 \[ ... \] 包裹（Manim MathTex 不需要）
        (r'\\\[\s*', ''),
        (r'\s*\\\]', ''),
        # 修复 \( ... \) 包裹
        (r'\\\(\s*', ''),
        (r'\s*\\\)', ''),
        # 修复 \frac 后缺少空格
        (r'\\frac(?=\S)', r'\\frac '),
        # 修复 \times 后缺少空格（\times\tau → \times \tau）
        (r'\\times(?=\\)', r'\\times '),
        # 修复多个连续空格为单个空格
        (r'  +', ' '),
    ]

    result = text
    for pattern, replacement in fixes:
        result = re.sub(pattern, replacement, result)

    # 如果修复后和原文本不同，说明有乱码被修复了
    if result != text:
        logger.debug(f"LaTeX修复: '{text[:50]}' -> '{result[:50]}'")

    return result.strip()


# ================================================================
# 二、几何题自动生成 base_figure
# ================================================================
def _detect_geometry_shape(problem_text: str) -> Optional[GeoElement]:
    """
    从题目文本推断几何图形类型和坐标
    返回 None 表示无法推断
    """
    text = problem_text.lower()

    # 三角形
    triangle_keywords = ["三角形", "三角", "abc", "勾股", "直角三角形"]
    if any(kw in problem_text for kw in triangle_keywords):
        # 检测是否是直角三角形
        is_right = "直角" in problem_text or "勾股" in problem_text
        if is_right:
            # 直角三角形：C 为直角顶点
            return GeoElement(
                type="triangle",
                points=[[-2, -1.5, 0], [2, -1.5, 0], [-2, 1.5, 0]],
                labels=["A", "B", "C"],
                config={"color": "#4ecca3"},
            )
        else:
            # 普通三角形
            return GeoElement(
                type="triangle",
                points=[[-2, -1.5, 0], [2, -1.5, 0], [0, 2, 0]],
                labels=["A", "B", "C"],
                config={"color": "#4ecca3"},
            )

    # 圆
    circle_keywords = ["圆", "半径", "直径", "圆面积", "周长"]
    if any(kw in problem_text for kw in circle_keywords):
        return GeoElement(
            type="circle",
            points=[[0, 0, 0]],
            labels=["O"],
            radius=1.5,
            config={"color": "#4ecca3"},
        )

    # 四边形 / 正方形 / 长方形 / 矩形
    quad_keywords = ["正方形", "长方形", "矩形", "四边形", "平行四边形"]
    if any(kw in problem_text for kw in quad_keywords):
        if "正方形" in problem_text:
            return GeoElement(
                type="polygon",
                points=[[-1.5, -1.5, 0], [1.5, -1.5, 0], [1.5, 1.5, 0], [-1.5, 1.5, 0]],
                labels=["A", "B", "C", "D"],
                config={"color": "#4ecca3"},
            )
        else:
            return GeoElement(
                type="polygon",
                points=[[-2, -1.2, 0], [2, -1.2, 0], [2, 1.2, 0], [-2, 1.2, 0]],
                labels=["A", "B", "C", "D"],
                config={"color": "#4ecca3"},
            )

    return None


def _ensure_base_figure(script: ProblemScript) -> ProblemScript:
    """
    如果是几何题但 base_figure 为空，根据题目文本自动推断生成
    """
    if script.problem_type != ProblemType.GEOMETRY:
        return script

    if script.base_figure is not None:
        # 已有 base_figure，检查是否有效
        if script.base_figure.type and (
            script.base_figure.points or script.base_figure.type == "circle"
        ):
            return script

    # 自动推断
    geo = _detect_geometry_shape(script.problem_text)
    if geo:
        script.base_figure = geo
        logger.info(f"自动生成 base_figure: type={geo.type}, points={len(geo.points)}")
    else:
        logger.warning(f"无法从题目文本推断几何图形: {script.problem_text[:50]}")

    return script


# ================================================================
# 三、几何步骤 config 自动补全
# ================================================================
def _get_vertex_points(base_figure: GeoElement) -> dict[str, list[float]]:
    """从 base_figure 提取顶点名称→坐标的映射"""
    points = base_figure.points or []
    labels = base_figure.labels or []
    result = {}
    for pt, lbl in zip(points, labels):
        if len(pt) >= 2:
            result[lbl.upper()] = [pt[0], pt[1]]
    return result


def _enrich_geometry_step(
    step: Step,
    base_figure: Optional[GeoElement],
) -> Step:
    """
    为几何题步骤自动补全缺失的 config 数据
    """
    if not base_figure:
        return step

    vertices = _get_vertex_points(base_figure)
    vertex_names = list(vertices.keys())
    config = step.config or {}

    anim_type = step.animation_type.value if hasattr(step.animation_type, 'value') else str(step.animation_type)

    # --- draw_shape: 如果没有点，用 base_figure 的坐标 ---
    if anim_type == "draw_shape":
        if not config.get("points") and not config.get("shape_type"):
            config["shape_type"] = base_figure.type
            if base_figure.type in ("triangle", "polygon"):
                config["points"] = [[p[0], p[1]] for p in base_figure.points]
            elif base_figure.type == "circle":
                config["shape_type"] = "circle"
                config["radius"] = base_figure.radius or 1.5
                center = base_figure.points[0] if base_figure.points else [0, 0]
                config["center"] = [center[0], center[1]]
            config["color"] = base_figure.config.get("color", "#4ecca3") if base_figure.config else "#4ecca3"
            logger.info(f"Step {step.step_number} draw_shape 自动补全: shape={config['shape_type']}")

    # --- label_vertex: 自动推断顶点坐标 ---
    elif anim_type == "label_vertex":
        if not config.get("point"):
            label = config.get("label", "")
            # 尝试从 step.text 中提取顶点字母
            if not label:
                for vn in vertex_names:
                    if vn in step.text:
                        label = vn
                        break
            if label and label.upper() in vertices:
                config["point"] = vertices[label.upper()]
                config["label"] = label
                # 自动推断方向
                idx = vertex_names.index(label.upper()) if label.upper() in vertex_names else 0
                directions = ["DL*0.4", "DR*0.4", "UP*0.4", "UR*0.4"]
                config["direction"] = directions[idx % len(directions)]
                logger.info(f"Step {step.step_number} label_vertex 自动补全: {label} -> {config['point']}")

    # --- label_side: 自动推断边端点 ---
    elif anim_type == "label_side":
        if not config.get("start") and len(vertex_names) >= 2:
            # 尝试从 step.text 或 math_expr 中提取边名（如 AB, BC）
            text_to_check = f"{step.text} {step.math_expr}"
            # 匹配两个大写字母组成的边名
            side_match = re.findall(r'\b([A-Z])([A-Z])\b', text_to_check)
            if side_match:
                v1, v2 = side_match[0]
                if v1 in vertices and v2 in vertices:
                    config["start"] = vertices[v1]
                    config["end"] = vertices[v2]
                    # 尝试从文本提取边长标注
                    length_match = re.search(r'(\d+\.?\d*)', text_to_check)
                    if length_match:
                        config["label"] = length_match.group(1)
                    logger.info(f"Step {step.step_number} label_side 自动补全: {v1}{v2}")
            else:
                # 默认标注第一条边
                config["start"] = vertices[vertex_names[0]]
                config["end"] = vertices[vertex_names[1]]
                config["label"] = ""
                logger.info(f"Step {step.step_number} label_side 默认补全: {vertex_names[0]}{vertex_names[1]}")

    # --- mark_right_angle: 自动推断直角顶点 ---
    elif anim_type == "mark_right_angle":
        if not config.get("vertex"):
            # 直角三角形中 C 是直角顶点
            if "C" in vertices and len(vertex_names) >= 3:
                config["vertex"] = vertices["C"]
                # 找 C 的两个相邻顶点
                c_idx = vertex_names.index("C")
                # 相邻顶点
                neighbors = [vertex_names[(c_idx - 1) % len(vertex_names)],
                             vertex_names[(c_idx + 1) % len(vertex_names)]]
                config["point_a"] = vertices[neighbors[0]]
                config["point_b"] = vertices[neighbors[1]]
                logger.info(f"Step {step.step_number} mark_right_angle 自动补全: vertex=C")
            elif len(vertex_names) >= 3:
                # 默认用最后一个顶点
                vn = vertex_names[-1]
                config["vertex"] = vertices[vn]
                neighbors = [vertex_names[-2], vertex_names[0]]
                config["point_a"] = vertices[neighbors[0]]
                config["point_b"] = vertices[neighbors[1]]
                logger.info(f"Step {step.step_number} mark_right_angle 默认补全: vertex={vn}")

    # --- mark_angle: 自动推断角度顶点 ---
    elif anim_type == "mark_angle":
        if not config.get("vertex") and len(vertex_names) >= 2:
            # 默认用第一个顶点
            vn = vertex_names[0]
            config["vertex"] = vertices[vn]
            neighbors = [vertex_names[-1], vertex_names[1]]
            config["point_a"] = vertices.get(neighbors[0], vertices[vertex_names[1]])
            config["point_b"] = vertices.get(neighbors[1], vertices[vertex_names[1]])
            config["label"] = config.get("label", "")
            logger.info(f"Step {step.step_number} mark_angle 默认补全: vertex={vn}")

    # --- draw_dashed_line: 自动推断辅助线端点 ---
    elif anim_type == "draw_dashed_line":
        if not config.get("start") and len(vertex_names) >= 2:
            # 默认从第一个顶点到对边中点
            config["start"] = vertices[vertex_names[0]]
            if len(vertex_names) >= 3:
                # 对边中点
                v2 = vertices[vertex_names[1]]
                v3 = vertices[vertex_names[2]]
                mid = [(v2[0] + v3[0]) / 2, (v2[1] + v3[1]) / 2]
                config["end"] = mid
            else:
                config["end"] = vertices[vertex_names[1]]
            config["color"] = config.get("color", "#e94560")
            logger.info(f"Step {step.step_number} draw_dashed_line 默认补全")

    step.config = config
    return step


# ================================================================
# 四、无效步骤降级
# ================================================================
def _degrade_invalid_steps(script: ProblemScript) -> ProblemScript:
    """
    将无法正常渲染的步骤降级为 text_slide_in
    确保每个步骤至少有文字内容显示

    规则：
    1. draw_shape 无坐标 → text_slide_in
    2. highlight/highlight_region 有 math_expr → text_slide_in（确保公式显示）
    3. label_vertex/label_side/mark_angle/mark_right_angle 无坐标且无法推断 → text_slide_in
    """
    for step in script.steps:
        anim_type = step.animation_type.value if hasattr(step.animation_type, 'value') else str(step.animation_type)
        config = step.config or {}

        # draw_shape 无坐标 → 降级
        if anim_type == "draw_shape":
            shape_type = config.get("shape_type", "")
            points = config.get("points", [])
            has_points = bool(points)
            is_circle = shape_type == "circle"
            if not shape_type and not has_points:
                step.animation_type = AnimationType.TEXT_SLIDE_IN
                logger.info(f"Step {step.step_number} draw_shape → text_slide_in (无数据)")
            elif shape_type in ("polygon", "triangle") and not has_points:
                step.animation_type = AnimationType.TEXT_SLIDE_IN
                logger.info(f"Step {step.step_number} draw_shape → text_slide_in (无坐标)")

        # highlight/highlight_region 有 math_expr → 转为 text_slide_in 确保公式显示
        elif anim_type in ("highlight", "highlight_region"):
            if step.math_expr:
                step.animation_type = AnimationType.TEXT_SLIDE_IN
                logger.info(f"Step {step.step_number} {anim_type} → text_slide_in (有公式需显示)")
            elif not step.text:
                # 没有文字也没有公式，无法显示任何内容
                step.animation_type = AnimationType.WAIT
                logger.info(f"Step {step.step_number} {anim_type} → wait (无内容)")

        # label_vertex 无坐标且无法推断 → 降级
        elif anim_type == "label_vertex" and not config.get("point"):
            step.animation_type = AnimationType.TEXT_SLIDE_IN
            logger.info(f"Step {step.step_number} label_vertex → text_slide_in (无坐标)")

        # label_side 无坐标且无法推断 → 降级
        elif anim_type == "label_side" and not config.get("start"):
            step.animation_type = AnimationType.TEXT_SLIDE_IN
            logger.info(f"Step {step.step_number} label_side → text_slide_in (无坐标)")

        # mark_right_angle 无坐标 → 降级
        elif anim_type == "mark_right_angle" and not config.get("vertex"):
            step.animation_type = AnimationType.TEXT_SLIDE_IN
            logger.info(f"Step {step.step_number} mark_right_angle → text_slide_in (无坐标)")

        # mark_angle 无坐标 → 降级
        elif anim_type == "mark_angle" and not config.get("vertex"):
            step.animation_type = AnimationType.TEXT_SLIDE_IN
            logger.info(f"Step {step.step_number} mark_angle → text_slide_in (无坐标)")

        # draw_dashed_line 无坐标 → 降级
        elif anim_type == "draw_dashed_line" and not config.get("start"):
            step.animation_type = AnimationType.TEXT_SLIDE_IN
            logger.info(f"Step {step.step_number} draw_dashed_line → text_slide_in (无坐标)")

    return script


# ================================================================
# 五、几何题步骤序列修复
# ================================================================
def _ensure_geometry_steps(script: ProblemScript) -> ProblemScript:
    """
    确保几何题有合理的步骤序列：
    - 如果有 base_figure 但第一个步骤不是 draw_shape，在开头插入一个 draw_shape 步骤
    """
    if script.problem_type != ProblemType.GEOMETRY:
        return script
    if not script.base_figure:
        return script

    # 检查是否已有 draw_shape 步骤
    has_draw_shape = any(
        (s.animation_type.value if hasattr(s.animation_type, 'value') else str(s.animation_type)) == "draw_shape"
        for s in script.steps
    )

    if not has_draw_shape:
        # 在开头插入 draw_shape 步骤
        draw_step = Step(
            step_number=1,
            title="绘制图形",
            text=f"首先画出题目中的图形",
            animation_type=AnimationType.DRAW_SHAPE,
            config={
                "shape_type": script.base_figure.type,
                "color": script.base_figure.config.get("color", "#4ecca3") if script.base_figure.config else "#4ecca3",
            },
            voice_text="首先，我们画出题目中的图形。",
        )
        # 如果是三角形/多边形，添加点坐标
        if script.base_figure.type in ("triangle", "polygon"):
            draw_step.config["points"] = [[p[0], p[1]] for p in script.base_figure.points]
        elif script.base_figure.type == "circle":
            draw_step.config["shape_type"] = "circle"
            draw_step.config["radius"] = script.base_figure.radius or 1.5
            center = script.base_figure.points[0] if script.base_figure.points else [0, 0]
            draw_step.config["center"] = [center[0], center[1]]

        # 插入到步骤列表开头
        script.steps.insert(0, draw_step)

        # 重新编号
        for i, s in enumerate(script.steps):
            s.step_number = i + 1

        logger.info(f"插入 draw_shape 步骤到几何题开头，共 {len(script.steps)} 步")

    return script


# ================================================================
# 六、主入口
# ================================================================
def enrich_script(script: ProblemScript) -> ProblemScript:
    """
    LLM 脚本后处理增强：自动补全缺失数据，修复常见错误

    处理顺序：
    1. 修复 LaTeX 乱码
    2. 几何题自动生成 base_figure
    3. 几何题步骤 config 自动补全
    4. 几何题步骤序列修复（确保有 draw_shape）
    5. 无效步骤降级为 text_slide_in

    Args:
        script: LLM 生成的原始脚本

    Returns:
        增强后的脚本（原地修改）
    """
    logger.info(f"开始脚本增强: type={script.problem_type}, steps={len(script.steps)}")

    # 1. 修复 LaTeX
    for step in script.steps:
        if step.math_expr:
            step.math_expr = fix_latex(step.math_expr)

    # 2. 几何题自动生成 base_figure
    script = _ensure_base_figure(script)

    # 3. 几何题步骤 config 自动补全
    if script.problem_type == ProblemType.GEOMETRY and script.base_figure:
        for step in script.steps:
            step = _enrich_geometry_step(step, script.base_figure)

    # 4. 几何题步骤序列修复
    script = _ensure_geometry_steps(script)

    # 5. 无效步骤降级
    script = _degrade_invalid_steps(script)

    logger.info(f"脚本增强完成: steps={len(script.steps)}, base_figure={'有' if script.base_figure else '无'}")

    return script
