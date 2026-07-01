"""
============================================================
MathAnimAI — 应用题教学场景 (word_problem.py)
功能：
  1. 线段图动态绘制（比例关系可视化）
  2. 柱状图动态生长
  3. 分段标注逐步叠加
  4. 原图不消失，完整呈现解题过程
============================================================
"""

from manim import *
import numpy as np

from animation.common import (
    BaseMathScene, pretty_text_with_bg, step_text, title_text,
    label_text, annotation_text,
    smooth_create, smooth_create_shape, smooth_highlight,
    draw_dashed_line,
    DURATION_CREATE, DURATION_SLIDE_IN, DURATION_HIGHLIGHT,
    DURATION_GROW,
)
from config import Colors, FONT_STEP, FONT_LABEL


class WordProblemScene(BaseMathScene):
    """
    应用题教学场景
    核心特点：
    - 示意图逐步构建，先画基础结构，再叠加标注
    - 线段图用不同颜色分段
    - 柱状图逐条生长
    - 所有图形永久保留
    """

    def setup(self):
        super().setup()
        self.diagram_elements: list[VMobject] = []

    def construct(self):
        """应用题场景主流程 — 示例演示"""
        # setup() 由 Manim 在 construct() 之前自动调用
        # 演示行程问题
        self._demo_travel_problem()

    def _demo_travel_problem(self):
        """演示行程问题：小明和小红相距120公里相向而行"""

        # 标题
        title = title_text("行程问题：相向而行")
        title.to_edge(UP, buff=0.4)
        self.add_to_all(title)
        self.play(FadeIn(title, shift=DOWN * 0.5, run_time=1.0))

        # 步骤1：审题
        step1 = step_text("小明和小红从相距120km的两地同时出发，相向而行。")
        step1.next_to(title, DOWN, buff=0.3)
        self.add_to_all(step1)
        self.play(FadeIn(step1, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        step1b = step_text("小明速度 15km/h，小红速度 10km/h，几小时后相遇？")
        step1b.next_to(step1, DOWN, buff=0.2)
        self.add_to_all(step1b)
        self.play(FadeIn(step1b, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))
        self.wait(0.5)

        # 步骤2：画线段图
        step2 = step_text("画线段图分析")
        step2.next_to(step1b, DOWN, buff=0.35)
        self.add_to_all(step2)
        self.play(FadeIn(step2, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 画总线段
        total_line = Line(LEFT * 4, RIGHT * 4, color=Colors.PRIMARY, stroke_width=4)
        total_line.shift(DOWN * 0.5)
        self.add_to_all(total_line)
        self.diagram_elements.append(total_line)
        self.play(Create(total_line, run_time=DURATION_CREATE))

        # 两端标注
        start_label = label_text("小明")
        start_label.next_to(total_line.get_start(), DOWN * 0.3)
        self.add_to_all(start_label)
        self.play(FadeIn(start_label, shift=DOWN * 0.2, run_time=0.4))

        end_label = label_text("小红")
        end_label.next_to(total_line.get_end(), DOWN * 0.3)
        self.add_to_all(end_label)
        self.play(FadeIn(end_label, shift=DOWN * 0.2, run_time=0.4))

        # 总距离标注
        dist_label = label_text("120 km", color=Colors.KNOWN)
        dist_label.next_to(total_line, UP * 0.4)
        self.add_to_all(dist_label)
        self.play(FadeIn(dist_label, shift=UP * 0.2, run_time=0.4))

        # 相遇点（约37.5%处，即 15/25 = 0.6 处，小明走了 72km = 120*15/25 = 72
        # 即总段的 72/120 = 0.6 处）
        meet_x = -4 + 0.6 * 8  # 从小明起点算起
        meet_point = np.array([meet_x, total_line.get_center()[1], 0])

        meet_dot = Dot(meet_point, color=Colors.VERTEX, radius=0.08)
        self.add_to_all(meet_dot)
        self.play(GrowFromCenter(meet_dot, run_time=0.5))

        meet_text = label_text("相遇点", color=Colors.VERTEX)
        meet_text.next_to(meet_dot, UP * 0.4)
        self.add_to_all(meet_text)
        self.play(FadeIn(meet_text, shift=UP * 0.2, run_time=0.4))
        self.wait(0.5)

        # 步骤3：标注分段
        step3 = step_text("小明路程 = 15 × t，小红路程 = 10 × t")
        step3.next_to(step2, DOWN, buff=0.35)
        self.add_to_all(step3)
        self.play(FadeIn(step3, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 用不同颜色高亮两段路程
        # 小明段（左边到相遇点）
        xm_segment = Line(
            total_line.get_start(),
            meet_point,
            color=Colors.FUNCTION_CURVE,
            stroke_width=6,
        )
        self.add_to_all(xm_segment)
        self.play(Create(xm_segment, run_time=0.8))

        xm_label = label_text("15t km", color=Colors.FUNCTION_CURVE)
        xm_label.next_to(xm_segment, DOWN * 0.5)
        self.add_to_all(xm_label)
        self.play(FadeIn(xm_label, shift=DOWN * 0.2, run_time=0.4))

        # 小红段（相遇点到右边）
        xh_segment = Line(
            meet_point,
            total_line.get_end(),
            color=Colors.FUNCTION_SECONDARY,
            stroke_width=6,
        )
        self.add_to_all(xh_segment)
        self.play(Create(xh_segment, run_time=0.8))

        xh_label = label_text("10t km", color=Colors.FUNCTION_SECONDARY)
        xh_label.next_to(xh_segment, DOWN * 0.5)
        self.add_to_all(xh_label)
        self.play(FadeIn(xh_label, shift=DOWN * 0.2, run_time=0.4))

        self.wait(0.5)

        # 步骤4：列方程
        step4 = step_text("15t + 10t = 120")
        step4.next_to(step3, DOWN, buff=0.35)
        self.add_to_all(step4)
        self.play(FadeIn(step4, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))
        smooth_highlight(self, step4)

        # 步骤5：求解
        step5 = step_text("25t = 120 → t = 120 ÷ 25 = 4.8")
        step5.next_to(step4, DOWN, buff=0.35)
        self.add_to_all(step5)
        self.play(FadeIn(step5, shift=UP * 0.3, run_time=DURATION_SLIDE_IN))

        # 答案
        answer = step_text("答：4.8小时后两人相遇。")
        answer.next_to(step5, DOWN, buff=0.35)
        answer_text = answer[2] if hasattr(answer, '__getitem__') else answer
        self.add_to_all(answer)
        self.play(FadeIn(answer, shift=UP * 0.3, run_time=DURATION_HIGHLIGHT))
        smooth_highlight(self, answer)

        self.wait(2.0)

    # ================================================================
    # 应用题目工具函数
    # ================================================================
    def draw_segment_diagram(
        self,
        total: float,
        parts: list[dict],
        labels: list[str] = None,
        colors: list[str] = None,
    ) -> VGroup:
        """
        绘制线段图
        Args:
            total: 总长度（用于计算比例）
            parts: 各部分定义 [{"value": 3, "label": "甲"}, ...]
            labels: 端点标签
            colors: 各段颜色
        Returns:
            线段图元素组
        """
        group = VGroup()
        line_length = 8.0
        start_x = -line_length / 2

        # 底线段
        base_line = Line(LEFT * line_length / 2, RIGHT * line_length / 2,
                        color=Colors.PRIMARY, stroke_width=3)
        base_line.shift(DOWN * 0.5)
        self.add_to_all(base_line)
        self.play(Create(base_line, run_time=DURATION_CREATE))
        group.add(base_line)

        # 分段
        cumulative = 0
        if colors is None:
            colors = Colors.BAR_COLORS

        for i, part in enumerate(parts):
            value = part.get("value", 1)
            label = part.get("label", "")
            section_start = start_x + cumulative / total * line_length
            cumulative += value
            section_end = start_x + cumulative / total * line_length

            y = base_line.get_center()[1]
            section = Line(
                np.array([section_start, y, 0]),
                np.array([section_end, y, 0]),
                color=colors[i % len(colors)],
                stroke_width=6,
            )
            self.add_to_all(section)
            self.play(Create(section, run_time=0.6))
            group.add(section)

            if label:
                mid = (section_start + section_end) / 2
                lbl = label_text(label)
                lbl.move_to(np.array([mid, y - 0.5, 0]))
                self.add_to_all(lbl)
                self.play(FadeIn(lbl, shift=DOWN * 0.2, run_time=0.4))
                group.add(lbl)

        return group

    def draw_bar_chart(
        self,
        values: list[float],
        labels: list[str] = None,
        title: str = "",
        colors: list[str] = None,
    ) -> VGroup:
        """
        绘制柱状图
        Args:
            values: 各柱数值
            labels: 各柱标签
            title: 图表标题
            colors: 柱子颜色
        """
        group = VGroup()

        if colors is None:
            colors = Colors.BAR_COLORS

        if title:
            ttl = label_text(title, color=Colors.TITLE_TEXT)
            ttl.to_edge(UP, buff=0.2)
            self.add_to_all(ttl)
            self.play(FadeIn(ttl, shift=DOWN * 0.3, run_time=0.5))
            group.add(ttl)

        # 计算柱子位置
        bar_width = 0.8
        spacing = 1.5
        total_width = len(values) * spacing

        for i, (val, lbl) in enumerate(zip(values, labels or [""] * len(values))):
            x = -total_width / 2 + i * spacing + spacing / 2
            height = val * 0.5  # 缩放

            # 柱子
            bar = Rectangle(
                width=bar_width,
                height=height,
                fill_color=colors[i % len(colors)],
                fill_opacity=0.8,
                stroke_width=1,
                stroke_color=colors[i % len(colors)],
            )
            bar.move_to(np.array([x, -2 + height / 2, 0]))
            self.add_to_all(bar)
            self.play(GrowFromEdge(bar, DOWN, run_time=DURATION_GROW))
            group.add(bar)

            # 标签
            if lbl:
                lb = label_text(lbl)
                lb.move_to(np.array([x, -2.3, 0]))
                self.add_to_all(lb)
                self.play(FadeIn(lb, shift=UP * 0.2, run_time=0.3))
                group.add(lb)

            # 数值
            val_lbl = label_text(str(val))
            val_lbl.move_to(np.array([x, -2 + height + 0.3, 0]))
            self.add_to_all(val_lbl)
            self.play(FadeIn(val_lbl, shift=UP * 0.15, run_time=0.3))
            group.add(val_lbl)

        return group
