"""
============================================================
MathAnimAI — 分数教学场景 (fraction.py)
功能：
  1. 饼图动态分割
  2. 数轴分数标记
  3. 分层色块区分分子分母
  4. 通分/约分过程逐步展示
============================================================
"""

from manim import *
import numpy as np

from animation.common import (
    BaseMathScene, pretty_text_with_bg, step_text, title_text,
    label_text, math_text,
    smooth_create, smooth_create_shape, smooth_highlight,
    DURATION_CREATE, DURATION_SLIDE_IN, DURATION_HIGHLIGHT,
    DURATION_GROW,
)
from config import Colors, FONT_STEP


class FractionScene(BaseMathScene):
    """
    分数教学场景
    核心特点：
    - 饼图分块动画平滑
    - 色块区分不同部分
    - 数轴标注精确
    - 每一步的内容叠加保留
    """

    def setup(self):
        super().setup()
        self.pie_charts: list[VGroup] = []

    def construct(self):
        """分数场景主流程 — 示例演示"""
        # setup() 由 Manim 在 construct() 之前自动调用
        # 演示分数加法：1/2 + 1/3
        self._demo_fraction_add()

    def _demo_fraction_add(self):
        """演示分数通分加法：1/2 + 1/3"""

        # 标题
        title = title_text("分数加法：1/2 + 1/3 = ?")
        title.to_edge(UP, buff=0.4)
        self.add_to_all(title)
        self.play(FadeIn(title, shift=DOWN * 0.5, run_time=1.0))
        self.wait(0.3)

        # 步骤1：展示题目
        step1 = step_text("计算：1/2 + 1/3")
        step1.next_to(title, DOWN, buff=0.3)
        self.add_to_all(step1)
        self.play(FadeIn(step1, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 画两个饼图
        left_pie = self._draw_single_pie(LEFT * 3 + DOWN * 1.5, 2, 1, label="1/2")
        right_pie = self._draw_single_pie(RIGHT * 1 + DOWN * 1.5, 3, 1, label="1/3")

        self.wait(0.5)

        # 步骤2：通分
        step2 = step_text("通分：找分母2和3的最小公倍数 → 6")
        step2.next_to(step1, DOWN, buff=0.3)
        self.add_to_all(step2)
        self.play(FadeIn(step2, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 通分公式
        formula = math_text(
            r"\frac{1}{2} = \frac{1 \times 3}{2 \times 3} = \frac{3}{6}",
            font_size=28, color=Colors.PRIMARY
        )
        formula.next_to(step2, DOWN, buff=0.2)
        self.add_to_all(formula)
        self.play(FadeIn(formula, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        formula2 = math_text(
            r"\frac{1}{3} = \frac{1 \times 2}{3 \times 2} = \frac{2}{6}",
            font_size=28, color=Colors.PRIMARY
        )
        formula2.next_to(formula, DOWN, buff=0.2)
        self.add_to_all(formula2)
        self.play(FadeIn(formula2, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        self.wait(0.3)

        # 步骤3：同分母相加
        step3 = step_text("同分母相加：分子相加，分母不变")
        step3.next_to(formula2, DOWN, buff=0.35)
        self.add_to_all(step3)
        self.play(FadeIn(step3, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        formula3 = math_text(
            r"\frac{3}{6} + \frac{2}{6} = \frac{3+2}{6} = \frac{5}{6}",
            font_size=28, color=Colors.RESULT
        )
        formula3.next_to(step3, DOWN, buff=0.2)
        self.add_to_all(formula3)
        self.play(FadeIn(formula3, shift=UP * 0.3, run_time=DURATION_HIGHLIGHT))
        smooth_highlight(self, formula3)

        # 步骤4：画结果饼图
        step4 = step_text("用饼图表示结果：5/6")
        step4.next_to(formula3, DOWN, buff=0.35)
        self.add_to_all(step4)
        self.play(FadeIn(step4, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 结果饼图（6份中取5份）
        self._draw_single_pie(DOWN * 3.5, 6, 5, label="5/6")

        self.wait(2.0)

    def _draw_single_pie(
        self,
        position: np.ndarray,
        total: int,
        filled: int,
        label: str = "",
    ) -> VGroup:
        """
        绘制单个饼图
        Args:
            position: 饼图中心位置
            total: 总份数
            filled: 已填充份数
            label: 标签文字
        Returns:
            饼图元素组
        """
        group = VGroup()
        radius = 0.8

        # 绘制圆形
        circle = Circle(radius=radius, color=Colors.PRIMARY, stroke_width=2)
        circle.move_to(position)
        self.add_to_all(circle)
        self.play(Create(circle, run_time=0.6))

        # 分段填充
        angle_per_part = 2 * PI / total
        colors_list = Colors.PIE_COLORS

        for i in range(total):
            start_angle = i * angle_per_part - PI / 2  # 从顶部开始
            if i < filled:
                # 创建扇形（填充）
                arc = Arc(
                    radius=radius,
                    start_angle=start_angle,
                    angle=angle_per_part,
                    color=colors_list[i % len(colors_list)],
                    stroke_width=2,
                )
                arc.move_arc_center_to(position)

                # 用AnnularSector做填充
                sector = AnnularSector(
                    inner_radius=0,
                    outer_radius=radius,
                    start_angle=start_angle,
                    angle=angle_per_part,
                    fill_color=colors_list[i % len(colors_list)],
                    fill_opacity=0.6,
                    stroke_color=Colors.PRIMARY,
                    stroke_width=1,
                )
                sector.move_arc_center_to(position)
                self.add_to_all(sector)
                self.play(GrowFromCenter(sector, run_time=0.3))
                group.add(sector)
            else:
                # 空白扇形（只在边界画线）
                arc = Arc(
                    radius=radius,
                    start_angle=start_angle,
                    angle=angle_per_part,
                    color=Colors.DASHED,
                    stroke_width=1,
                    stroke_opacity=0.3,
                )
                arc.move_arc_center_to(position)
                self.add_to_all(arc)
                self.play(Create(arc, run_time=0.2))
                group.add(arc)

        # 标签
        if label:
            lbl = label_text(label, color=Colors.STEP_TEXT)
            lbl.next_to(circle, DOWN * 0.3)
            self.add_to_all(lbl)
            self.play(FadeIn(lbl, shift=UP * 0.2, run_time=0.4))
            group.add(lbl)

        self.pie_charts.append(group)
        return group

    # ================================================================
    # 分数工具函数
    # ================================================================
    def draw_number_line_fraction(
        self,
        start: float,
        end: float,
        denominator: int,
        marked_positions: list[int],
        color: str = Colors.PRIMARY,
    ) -> VGroup:
        """
        在数轴上标注分数
        Args:
            start: 数轴起点
            end: 数轴终点
            denominator: 分母（等分数）
            marked_positions: 要标注的分子位置列表
            color: 数轴颜色
        Returns:
            数轴+标注组
        """
        group = VGroup()

        # 数轴
        line = Line(LEFT * 4, RIGHT * 4, color=color, stroke_width=2)
        self.add_to_all(line)
        self.play(Create(line, run_time=DURATION_CREATE))
        group.add(line)

        # 区间长度
        total_length = 8.0
        segment_length = total_length / denominator

        # 刻度标记
        for i in range(denominator + 1):
            x = -4 + i * segment_length
            tick = Line(UP * 0.15, DOWN * 0.15, color=color)
            tick.move_to(np.array([x, 0, 0]))
            self.add_to_all(tick)
            self.play(Create(tick, run_time=0.15))
            group.add(tick)

            # 标注
            if i in marked_positions or i == 0 or i == denominator:
                fraction_str = f"{i}/{denominator}"
                lbl = label_text(fraction_str, font_size=16)
                lbl.next_to(tick, DOWN * 0.2)
                self.add_to_all(lbl)
                self.play(FadeIn(lbl, shift=DOWN * 0.1, run_time=0.2))
                group.add(lbl)

        # 高亮标记的位置
        for pos in marked_positions:
            x = -4 + pos * segment_length
            mark = Dot(np.array([x, 0, 0]), color=Colors.VERTEX, radius=0.06)
            self.add_to_all(mark)
            self.play(GrowFromCenter(mark, run_time=0.3))
            group.add(mark)

        return group
