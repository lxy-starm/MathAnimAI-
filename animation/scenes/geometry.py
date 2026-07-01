"""
============================================================
MathAnimAI — 平面几何教学场景 (geometry.py)
功能：
  1. 三角形、四边形、圆形绘制
  2. 辅助虚线、垂线、角平分线
  3. 直角符号、角度弧线标注
  4. 顶点字母、边长标注
  5. 全部图形元素永久保留在画布上
============================================================
"""

from manim import *
import numpy as np

from animation.common import (
    BaseMathScene, pretty_text_with_bg, step_text, title_text,
    label_text, annotation_text, math_text,
    smooth_create, smooth_create_shape, smooth_highlight,
    draw_angle_mark, draw_right_angle_mark,
    draw_vertex_label, draw_side_label,
    draw_dashed_line, draw_dot_point,
    DURATION_CREATE, DURATION_SLIDE_IN,
    DURATION_HIGHLIGHT,
)
from config import Colors, FONT_LABEL


class GeometryScene(BaseMathScene):
    """
    几何教学场景
    核心特点：
    - 基础图形首次绘制后永久固定
    - 辅助线用虚线，颜色区分
    - 标注逐层叠加在图形周围
    - 最终画面完整呈现题目+图形+标注+推导
    """

    def setup(self):
        super().setup()
        # 几何图形组
        self.main_shape: Optional[VMobject] = None
        # 顶点坐标缓存
        self.vertices: dict[str, np.ndarray] = {}

    def construct(self):
        """几何场景主流程 — 示例演示"""
        # setup() 由 Manim 在 construct() 之前自动调用
        # 演示：直角三角形勾股定理
        self._demo_pythagorean()

    def _demo_pythagorean(self):
        """演示直角三角形勾股定理"""
        # 顶点坐标：A(-2,-1.5) B(2,-1.5) C(0,2)
        A = np.array([-2.0, -1.5, 0.0])
        B = np.array([2.0, -1.5, 0.0])
        C = np.array([0.0, 2.0, 0.0])
        self.vertices = {"A": A, "B": B, "C": C}

        # 标题
        title = title_text("勾股定理：直角三角形的三边关系")
        title.to_edge(UP, buff=0.4)
        self.add_to_all(title)
        self.play(FadeIn(title, shift=DOWN * 0.5, run_time=1.0))

        # 步骤1：绘制直角三角形
        step1 = step_text("已知：直角三角形 ABC，其中 ∠C = 90°")
        step1.next_to(title, DOWN, buff=0.25)
        self.add_to_all(step1)
        self.play(FadeIn(step1, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 绘制三角形
        triangle = Polygon(A, B, C, color=Colors.PRIMARY, stroke_width=2.5)
        triangle.center()
        self.main_shape = triangle
        self.add_to_all(triangle)
        self.play(Create(triangle, run_time=DURATION_CREATE * 1.2, rate_func=linear))

        # 标注顶点
        draw_vertex_label(self, A, "A", direction=DL * 0.5)
        draw_vertex_label(self, B, "B", direction=DR * 0.5)
        draw_vertex_label(self, C, "C", direction=UP * 0.5)

        # 标注直角（在C点，AC和BC之间）
        draw_right_angle_mark(self, C, A, B, length=0.3, color=Colors.VERTEX)

        self.wait(0.5)

        # 步骤2：标注已知边长
        step2 = step_text("已知两条直角边长度：AC = 3，BC = 4")
        step2.next_to(step1, DOWN, buff=0.35)
        self.add_to_all(step2)
        self.play(FadeIn(step2, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 边长标注
        draw_side_label(self, A, C, "3", color=Colors.KNOWN, offset=0.35)
        draw_side_label(self, C, B, "4", color=Colors.KNOWN, offset=0.35)

        # 斜边变亮色提示待求
        ab_line = Line(A, B, color=Colors.RESULT, stroke_width=3.5)
        self.add_to_all(ab_line)
        self.play(Create(ab_line, run_time=0.6))
        draw_side_label(self, A, B, "?", color=Colors.RESULT, offset=0.35)

        self.wait(0.5)

        # 步骤3：应用勾股定理
        step3 = step_text("根据勾股定理：AC² + BC² = AB²")
        step3.next_to(step2, DOWN, buff=0.35)
        self.add_to_all(step3)
        self.play(FadeIn(step3, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 公式
        formula = math_text("3^2 + 4^2 = AB^2", font_size=30, color=Colors.PRIMARY)
        formula.next_to(step3, DOWN, buff=0.25)
        self.add_to_all(formula)
        self.play(FadeIn(formula, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))
        smooth_highlight(self, formula)

        # 步骤4：计算
        step4 = step_text("计算：9 + 16 = 25 = AB²")
        step4.next_to(formula, DOWN, buff=0.35)
        self.add_to_all(step4)
        self.play(FadeIn(step4, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 结果
        result = math_text("AB = \\sqrt{25} = 5", font_size=30, color=Colors.RESULT)
        result.next_to(step4, DOWN, buff=0.25)
        self.add_to_all(result)
        self.play(FadeIn(result, shift=UP * 0.3, run_time=DURATION_HIGHLIGHT))
        smooth_highlight(self, result)

        # 验证
        check = step_text("验证：3² + 4² = 9 + 16 = 25 = 5² ✓")
        check.next_to(result, DOWN, buff=0.35)
        self.add_to_all(check)
        self.play(FadeIn(check, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        self.wait(2.0)

    # ================================================================
    # 几何工具函数
    # ================================================================
    def draw_polygon(
        self,
        points: list[np.ndarray],
        labels: list[str] = None,
        color: str = Colors.PRIMARY,
        fill_opacity: float = 0.05,
    ) -> Polygon:
        """
        绘制多边形并自动标注顶点
        Args:
            points: 顶点坐标列表
            labels: 顶点字母标签列表
            color: 边框颜色
            fill_opacity: 填充透明度
        Returns:
            绘制的多边形
        """
        polygon = Polygon(
            *points,
            color=color,
            stroke_width=2.5,
            fill_color=color,
            fill_opacity=fill_opacity,
        )
        self.add_to_all(polygon)
        self.play(Create(polygon, run_time=DURATION_CREATE, rate_func=linear))

        # 自动标注顶点（向外偏移）
        if labels:
            directions = self._get_label_directions(points)
            for i, (pt, lbl) in enumerate(zip(points, labels)):
                draw_vertex_label(
                    self, pt, lbl,
                    direction=directions[i % len(directions)],
                )

        self.main_shape = polygon
        return polygon

    def draw_circle(
        self,
        center: np.ndarray,
        radius: float,
        color: str = Colors.PRIMARY,
    ) -> Circle:
        """绘制圆形"""
        circle = Circle(radius=radius, color=color, stroke_width=2.5)
        circle.move_to(center)
        self.add_to_all(circle)
        self.play(Create(circle, run_time=DURATION_CREATE, rate_func=linear))
        return circle

    def draw_auxiliary_line(
        self,
        start: np.ndarray,
        end: np.ndarray,
        label: str = "",
        color: str = Colors.DASHED,
    ) -> DashedLine:
        """绘制辅助虚线（如垂线、中线等）"""
        line = draw_dashed_line(self, start, end, color=color)
        if label:
            draw_side_label(self, start, end, label,
                           color=color, font_size=FONT_LABEL)
        return line

    def draw_perpendicular(
        self,
        foot: np.ndarray,
        point: np.ndarray,
        color: str = Colors.DASHED,
    ) -> DashedLine:
        """绘制垂线"""
        return self.draw_auxiliary_line(foot, point, label="⊥", color=color)

    def mark_angle(
        self,
        vertex: np.ndarray,
        a: np.ndarray,
        b: np.ndarray,
        label: str = "",
    ) -> None:
        """标注角度"""
        draw_angle_mark(self, vertex, a, b, label=label)

    def mark_right_angle(
        self,
        vertex: np.ndarray,
        a: np.ndarray,
        b: np.ndarray,
    ) -> None:
        """标注直角"""
        draw_right_angle_mark(self, vertex, a, b)

    def _get_label_directions(self, points: list[np.ndarray]) -> list[np.ndarray]:
        """为多边形的每个顶点计算最佳标签偏移方向（向外）"""
        if len(points) < 3:
            return [UR * 0.5] * len(points)

        center = sum(points) / len(points)
        directions = []
        for pt in points:
            # 从中心指向顶点的方向
            diff = pt - center
            norm = np.linalg.norm(diff)
            if norm > 0:
                directions.append(diff / norm * 0.5)
            else:
                directions.append(UR * 0.5)
        return directions
