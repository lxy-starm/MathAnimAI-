"""
============================================================
MathAnimAI — 函数图像教学场景 (function.py)
功能：
  1. 一次 / 二次函数图像绘制
  2. 坐标轴常驻画面
  3. 函数曲线逐段绘制
  4. 动点缓慢移动演示
  5. 坐标标注、关键点标注
============================================================
"""

from manim import *
import numpy as np

from animation.common import (
    BaseMathScene, pretty_text_with_bg, step_text, title_text,
    label_text, math_text,
    smooth_create, smooth_create_shape, smooth_highlight,
    draw_dot_point, draw_vertex_label,
    DURATION_CREATE, DURATION_SLIDE_IN, DURATION_HIGHLIGHT, DURATION_GROW,
)
from config import Colors, FONT_STEP


class FunctionScene(BaseMathScene):
    """
    函数图像教学场景
    核心特点：
    - 坐标系永久固定
    - 曲线缓慢绘制
    - 关键点动态标注
    """

    def setup(self):
        super().setup()
        self.axes: Optional[Axes] = None
        self.graphs: list[VMobject] = []

    def construct(self):
        """函数场景主流程 — 示例演示"""
        # setup() 由 Manim 在 construct() 之前自动调用
        # 演示二次函数图像
        self._demo_quadratic_function()

    def _demo_quadratic_function(self):
        """演示二次函数 y = x² - 4x + 3 的图像和性质"""

        # 标题
        title = title_text("二次函数：y = x² - 4x + 3")
        title.to_edge(UP, buff=0.4)
        self.add_to_all(title)
        self.play(FadeIn(title, shift=DOWN * 0.5, run_time=1.0))
        self.wait(0.3)

        # 步骤1：绘制坐标系
        step1 = step_text("第一步：建立平面直角坐标系")
        step1.to_edge(LEFT, buff=0.5).shift(DOWN * 0.5)
        self.add_to_all(step1)
        self.play(FadeIn(step1, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 创建坐标轴
        axes = Axes(
            x_range=[-2, 6, 1],
            y_range=[-3, 8, 1],
            x_length=9,
            y_length=6,
            axis_config={"include_numbers": True, "font_size": 18,
                         "color": Colors.STEP_TEXT},
            tips=True,
        )
        axes.center().shift(DOWN * 0.3)
        self.axes = axes
        self.add_to_all(axes)
        self.play(Create(axes, run_time=DURATION_CREATE * 1.5, rate_func=linear))

        # 坐标轴标签
        x_label = axes.get_x_axis_label("x", edge=RIGHT, direction=RIGHT, buff=0.2)
        y_label = axes.get_y_axis_label("y", edge=UP, direction=UP, buff=0.2)
        self.add_to_all(x_label, y_label)
        self.play(FadeIn(x_label), FadeIn(y_label))
        self.wait(0.5)

        # 步骤2：求顶点坐标
        step2 = step_text("第二步：求顶点坐标")
        step2.next_to(step1, DOWN, buff=0.25)
        self.add_to_all(step2)
        self.play(FadeIn(step2, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 配方法
        formula = math_text(
            r"y = x^2 - 4x + 3 = (x-2)^2 - 1",
            font_size=28, color=Colors.PRIMARY
        )
        formula.next_to(step2, DOWN, buff=0.2)
        self.add_to_all(formula)
        self.play(FadeIn(formula, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        vertex_text = step_text("顶点坐标：(2, -1)，开口向上")
        vertex_text.next_to(formula, DOWN, buff=0.2)
        self.add_to_all(vertex_text)
        self.play(FadeIn(vertex_text, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 标注顶点
        vertex_point = axes.coords_to_point(2, -1)
        dot = Dot(vertex_point, color=Colors.VERTEX, radius=0.08)
        self.add_to_all(dot)
        self.play(GrowFromCenter(dot, run_time=DURATION_GROW))
        v_label = label_text("(2, -1)")
        v_label.next_to(dot, DR * 0.4, buff=0.05)
        self.add_to_all(v_label)
        self.play(FadeIn(v_label, shift=DR * 0.2, run_time=0.5))
        self.wait(0.5)

        # 步骤3：绘制函数曲线（逐段）
        step3 = step_text("第三步：绘制抛物线图像")
        step3.next_to(vertex_text, DOWN, buff=0.3)
        self.add_to_all(step3)
        self.play(FadeIn(step3, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 绘制抛物线
        graph = axes.plot(
            lambda x: x**2 - 4*x + 3,
            x_range=[-0.5, 5.5],
            color=Colors.FUNCTION_CURVE,
            stroke_width=3,
        )
        self.add_to_all(graph)
        self.play(Create(graph, run_time=DURATION_CREATE * 2.0, rate_func=linear))
        self.graphs.append(graph)
        self.wait(0.5)

        # 标注与x轴交点
        for x_val in [1, 3]:
            pt = axes.coords_to_point(x_val, 0)
            dot_x = Dot(pt, color=Colors.KNOWN, radius=0.06)
            self.add_to_all(dot_x)
            self.play(GrowFromCenter(dot_x, run_time=0.4))
            lbl = label_text(f"({x_val}, 0)")
            lbl.next_to(dot_x, DOWN * 0.3, buff=0.05)
            self.add_to_all(lbl)
            self.play(FadeIn(lbl, shift=DOWN * 0.15, run_time=0.3))

        self.wait(0.3)

        # 标注与y轴交点
        pt_y = axes.coords_to_point(0, 3)
        dot_y = Dot(pt_y, color=Colors.KNOWN, radius=0.06)
        self.add_to_all(dot_y)
        self.play(GrowFromCenter(dot_y, run_time=0.4))
        lbl_y = label_text("(0, 3)")
        lbl_y.next_to(dot_y, LEFT * 0.5, buff=0.05)
        self.add_to_all(lbl_y)
        self.play(FadeIn(lbl_y, shift=LEFT * 0.15, run_time=0.3))

        # 步骤4：分析性质
        step4 = step_text("当x<2时，y随x增大而减小；当x>2时，y随x增大而增大；当x=2时取最小值-1")
        step4.next_to(step3, DOWN, buff=0.3)
        self.add_to_all(step4)
        self.play(FadeIn(step4, shift=UP * 0.3, run_time=DURATION_HIGHLIGHT))

        smooth_highlight(self, vertex_text)

        self.wait(2.0)

    # ================================================================
    # 函数工具函数
    # ================================================================
    def setup_axes(
        self,
        x_range: list,
        y_range: list,
        x_length: float = 9,
        y_length: float = 6,
    ) -> Axes:
        """
        创建并渲染坐标轴
        Returns:
            Axes 对象
        """
        axes = Axes(
            x_range=x_range,
            y_range=y_range,
            x_length=x_length,
            y_length=y_length,
            axis_config={
                "include_numbers": True,
                "font_size": 18,
                "color": Colors.STEP_TEXT,
            },
            tips=True,
        )
        axes.center()
        self.axes = axes
        self.add_to_all(axes)
        self.play(Create(axes, run_time=DURATION_CREATE * 1.2, rate_func=linear))
        return axes

    def plot_curve(
        self,
        func,
        x_range: list,
        color: str = Colors.FUNCTION_CURVE,
        label: str = "",
    ) -> ParametricFunction:
        """
        绘制函数曲线
        Args:
            func: 函数 lambda x: ...
            x_range: x范围 [x_min, x_max]
            color: 曲线颜色
            label: 曲线标签
        Returns:
            绘制的曲线对象
        """
        if self.axes is None:
            raise ValueError("请先调用 setup_axes() 创建坐标系")

        graph = self.axes.plot(
            func,
            x_range=x_range,
            color=color,
            stroke_width=3,
        )
        self.add_to_all(graph)
        self.graphs.append(graph)
        # 逐段绘制，模拟手写
        self.play(Create(graph, run_time=DURATION_CREATE * 1.5, rate_func=linear))

        if label:
            lbl = label_text(label, color=color)
            # 将标签放在曲线末端
            end_x = x_range[1]
            end_y = func(end_x)
            end_point = self.axes.coords_to_point(end_x, end_y)
            lbl.next_to(end_point, UR * 0.2, buff=0.1)
            self.add_to_all(lbl)
            self.play(FadeIn(lbl, shift=UR * 0.15, run_time=0.4))

        return graph

    def mark_point(
        self,
        x: float,
        y: float,
        label: str = "",
        color: str = Colors.VERTEX,
    ) -> Dot:
        """
        在坐标系上标注关键点
        """
        if self.axes is None:
            raise ValueError("请先调用 setup_axes() 创建坐标系")

        point = self.axes.coords_to_point(x, y)
        dot = Dot(point, color=color, radius=0.08)
        self.add_to_all(dot)
        self.play(GrowFromCenter(dot, run_time=DURATION_GROW))

        if label:
            lbl = label_text(label)
            lbl.next_to(dot, UR * 0.3, buff=0.05)
            self.add_to_all(lbl)
            self.play(FadeIn(lbl, shift=UR * 0.15, run_time=0.3))

        return dot
