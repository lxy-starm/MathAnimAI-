"""
============================================================
MathAnimAI — 方程推导场景 (equation.py)
功能：
  1. 一元一次方程 / 一元二次方程逐步推导动画
  2. 等号强制垂直对齐，每步变形从上到下堆叠
  3. 重点步骤高亮渐变
  4. 完整保留全部推导链条（不FadeOut）
============================================================
"""

from manim import *
import numpy as np

from animation.common import (
    BaseMathScene, pretty_text_with_bg, step_text, title_text,
    math_text, smooth_create, smooth_create_shape, smooth_highlight,
    smooth_transition, DURATION_CREATE, DURATION_SLIDE_IN,
    DURATION_HIGHLIGHT, DURATION_TRANSITION,
)
from config import Colors, FONT_STEP, MATH_FONT_SIZE


class EquationScene(BaseMathScene):
    """
    方程教学场景
    核心特点：
    - 等号在垂直方向对齐
    - 每步变形从上到下堆叠
    - 上一步内容缩小上移但不消失
    - 高亮当前步骤的变形
    """

    def setup(self):
        super().setup()
        # 方程推导步骤列表
        self.equation_step_groups: list[VGroup] = []
        # 当前Y位置追踪
        self._current_y = 2.5

    def construct(self):
        """方程场景主流程 — 由builder.py生成的代码调用"""
        # setup() 由 Manim 在 construct() 之前自动调用，无需手动调用
        # 注意：此方法的具体内容由builder.py动态生成
        # 这里保留作为直接编程入参的示例模板

        # 示例：解一元二次方程 x^2 - 5x + 6 = 0
        self._demo_quadratic()

    def _demo_quadratic(self):
        """演示一元二次方程的完整求解过程"""
        # 标题
        title = title_text("解方程：x² - 5x + 6 = 0")
        title.to_edge(UP, buff=0.5)
        self.add_to_all(title)
        self.play(FadeIn(title, shift=DOWN * 0.5, run_time=1.0))
        self.wait(0.5)

        # 步骤1: 展示原方程
        eq1 = math_text("x^2 - 5x + 6 = 0", font_size=MATH_FONT_SIZE, color=Colors.KNOWN)
        eq1.move_to(UP * 1.0)
        self.add_to_all(eq1)
        self.play(FadeIn(eq1, shift=RIGHT * 0.5, run_time=DURATION_SLIDE_IN))
        self.wait(0.5)

        # 步骤2: 因式分解
        step2_text = step_text("因式分解：找两个数乘积为6，和为-5")
        step2_text.next_to(eq1, DOWN, buff=0.6)
        self.add_to_all(step2_text)
        self.play(FadeIn(step2_text, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        eq2 = math_text("(x - 2)(x - 3) = 0", font_size=MATH_FONT_SIZE, color=Colors.PRIMARY)
        eq2.next_to(step2_text, DOWN, buff=0.3)
        self.add_to_all(eq2)
        self.play(FadeIn(eq2, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))
        smooth_highlight(self, eq2)
        self.wait(0.5)

        # 步骤3: 求解
        step3_text = step_text("令每个因式等于零")
        step3_text.next_to(eq2, DOWN, buff=0.6)
        self.add_to_all(step3_text)
        self.play(FadeIn(step3_text, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        eq3 = math_text("x - 2 = 0 \\quad \\text{或} \\quad x - 3 = 0",
                        font_size=MATH_FONT_SIZE - 4, color=Colors.PRIMARY)
        eq3.next_to(step3_text, DOWN, buff=0.3)
        self.add_to_all(eq3)
        self.play(FadeIn(eq3, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))
        self.wait(0.3)

        # 步骤4: 结果
        step4_text = step_text("解得")
        step4_text.next_to(eq3, DOWN, buff=0.6)
        self.add_to_all(step4_text)
        self.play(FadeIn(step4_text, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        answer = math_text("x_1 = 2, \\quad x_2 = 3",
                           font_size=MATH_FONT_SIZE, color=Colors.RESULT)
        answer.next_to(step4_text, DOWN, buff=0.3)
        self.add_to_all(answer)
        self.play(FadeIn(answer, shift=UP * 0.3, run_time=DURATION_HIGHLIGHT))
        smooth_highlight(self, answer)

        # 验证
        check_text = step_text("验证：2²-5×2+6=4-10+6=0 ✓   3²-5×3+6=9-15+6=0 ✓")
        check_text.next_to(answer, DOWN, buff=0.5)
        self.add_to_all(check_text)
        self.play(FadeIn(check_text, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 最终画面停留
        self.wait(2.0)

    # ================================================================
    # 方程工具函数
    # ================================================================
    def draw_equation_step(
        self,
        equation_text: str,
        step_text_content: str,
        is_highlight: bool = False,
        color: str = Colors.PRIMARY,
    ) -> None:
        """
        通用的方程步骤渲染函数
        - 添加步骤说明文字
        - 添加方程数学公式
        - 自动向下堆叠
        - 可选高亮
        """
        # 找当前最底部的元素
        if self.all_elements:
            last_elem = self.all_elements[-1]
            ref_y = last_elem.get_bottom()[1]
        else:
            ref_y = 2.0

        # 步骤文字
        if step_text_content:
            text_obj = step_text(step_text_content)
            text_obj.move_to(UP * ref_y + DOWN * 0.8)
            self.add_to_all(text_obj)
            self.play(FadeIn(text_obj, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))
            ref_y = text_obj.get_bottom()[1]

        # 数学公式
        eq_obj = math_text(equation_text, font_size=MATH_FONT_SIZE, color=color)
        eq_obj.next_to(self.all_elements[-1] if self.all_elements else ORIGIN,
                       DOWN, buff=0.4)
        self.add_to_all(eq_obj)
        self.play(FadeIn(eq_obj, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 高亮
        if is_highlight:
            smooth_highlight(self, eq_obj)

    def draw_equation_chain(
        self,
        equations: list[str],
        colors: list[str] = None,
    ) -> None:
        """
        连续绘制多个等式，等号对齐
        用于展示方程的逐步变形过程
        """
        if not equations:
            return

        if colors is None:
            colors = [Colors.PRIMARY] * len(equations)

        group = VGroup()
        for i, eq in enumerate(equations):
            eq_obj = math_text(eq, font_size=MATH_FONT_SIZE,
                              color=colors[i % len(colors)])
            group.add(eq_obj)

        group.arrange(DOWN, buff=0.35, aligned_edge=LEFT)

        # 定位到当前内容下方
        if self.all_elements:
            group.next_to(self.all_elements[-1], DOWN, buff=0.5)
        else:
            group.move_to(UP)

        # 逐行播放
        for i, eq_obj in enumerate(group):
            self.add_to_all(eq_obj)
            self.play(FadeIn(eq_obj, shift=RIGHT * 0.3, run_time=DURATION_SLIDE_IN * 0.6))
            if i < len(group) - 1:
                self.wait(0.2)
