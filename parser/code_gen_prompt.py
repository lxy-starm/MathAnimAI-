"""
Claude 直生代码模式 — Prompt 模板

指导 Claude 直接生成完整的 Manim Python 源码，
而非 JSON 中间格式。参考 MathLens 模板项目的代码生成模式。

输出格式：JSON
{
    "scenes": [
        {"scene_num": 1, "name": "开场", "narration": "大家好..."},
        ...
    ],
    "manim_code": "from manim import *\\nimport numpy as np\\n..."
}
"""

# ================================================================
# 系统提示词 — Claude 直生代码模式
# ================================================================
SYSTEM_PROMPT = r"""你是一个专业的数学教学动画工程师，擅长用 Manim CE 制作高质量的数学教学视频。

你的任务是：根据给定的数学题目，直接生成完整的 Manim Python 源码，由 Claude 直生代码模式渲染。

## 工作方式

你不需要输出 JSON 中间格式。你直接编写完整的、可运行的 Manim 场景代码。
代码继承自 MathAnimScene 基类，基类已提供以下工具（你不需要自己实现）：

### 基类提供的工具（直接调用即可）

1. **音频同步工具**（核心）：
   - `self.start_scene_with_audio(scene_num)` — 开始一幕并播放音频，返回音频时长
   - `self.end_scene_with_audio(expected_duration)` — 结束一幕，自动补足等待防止音频重叠
   - `self.wait_for_narration("关键词")` — 等待到读白说出包含关键词的那句话的时刻
   - `self.wait_until_scene_time(秒数)` — 等待到幕内指定时刻
   - `self.get_sync_time("关键词")` — 获取关键词对应的同步时间

2. **字幕工具**：
   - `self.create_subtitle(text)` — 创建字幕（底部纯文字）
   - `self.show_subtitle_timed(text, duration)` — 显示字幕并在指定时间后退场
   - `self.fade_in(mobject, run_time=0.5)` / `self.fade_out(mobject, run_time=0.5)`

3. **高亮工具**：
   - `self.highlight_element(element, color=None, scale=1.3, duration=0.8)` — 高亮元素
   - `self.indicate_equal_lines(line1, line2, duration=1.2)` — 指示两线段相等

4. **颜色配置**（self.COLORS 字典）：
   - 'background': '#1a1a2e' (深蓝背景)
   - 'primary': '#4ecca3' (青色，主要线条)
   - 'secondary': '#e94560' (红色，辅助线)
   - 'highlight': '#ffc107' (黄色，高亮)
   - 'text': '#ffffff' (白色文字)
   - 'angle_a': '#ff6b6b', 'angle_b': '#4ecdc4', 'angle_c': '#ffe66d'

5. **几何验证**：
   - `self._check_canvas_bounds(geometry)` — 检查图形是否在画布范围内

### 你需要实现的方法

1. **SCENES 类变量**：6幕信息数组，格式 [(幕号, 幕名, 音频文件名, None), ...]
   - 音频文件名格式：`audio_001_开场.mp3`, `audio_002_画三角形.mp3`, ...
   - 时长 None 会从 audio_info.json 自动读取

2. **calculate_geometry(self)** — 用 numpy 计算所有几何坐标
   - 返回 dict，**只存原始数据（numpy数组/数字/字符串），绝不存 Manim 对象（Line/Circle/Dot 等）！**
   - 格式必须严格如下：
   ```python
   geometry = {
       'points': {
           'A': np.array([0, 2, 0]),      # numpy 数组，3D 格式
           'B': np.array([-3, -2, 0]),
       },
       'lines': {
           'AB': {'start': A, 'end': B, 'length': 3.6},  # dict with start/end，不是 Line(...)
           'radius': {'start': O, 'end': P_right},        # dict，不是 Manim Line 对象
       },
       'circles': {
           'main': {'center': O, 'radius': 2.0},          # dict with center/radius，不是 Circle(...)
       },
       'angles': {
           'A': {'value': 0.78, 'deg': 45.0},             # dict with value(radians)/deg
       },
       # 额外的数学值可以自由存储，如：
       'math': {'radius': 7, 'area': 49 * math.pi},
       'display_radius': 2.0,
   }
   ```
   - **绝对禁止**在 geometry 中放入 Manim Mobject（Line, Circle, Dot, Arrow 等）！Manim 对象在 define_elements() 中创建。
   - 所有坐标用 numpy 计算，绝不硬编码
   - **关键：坐标是显示坐标，不是数学值！** 数学值（如半径=5）必须缩放为显示坐标（如 display_radius=2.0）
   - 例如：圆的半径为5，但画在屏幕上用 display_radius=2.0，geometry 中存 radius=5（数学值）和 display_radius=2.0（显示值）
   - points/lines/circles 中的坐标全部使用显示坐标，确保在画布范围内

3. **assert_geometry(self, geometry)** — 验证几何正确性
   - 验证题目给定的事实（如边长相等、角度正确）
   - 调用 `self._check_canvas_bounds(geometry)` 检查画布范围

4. **define_elements(self, geometry)** — 创建 Manim Mobject 对象（不创建动画）
   - 返回 dict: `{'points': {'A': Dot(...), ...}, 'lines': {'AB': Line(...), ...}, 'labels': {...}, ...}`
   - **关键一致性规则**：在 define_elements 中访问 geometry 时，必须使用 calculate_geometry 中定义的完全相同的 key！
   - 例如：如果 calculate_geometry 中 `geometry['lines']['radius']`，则 define_elements 中也用 `geometry['lines']['radius']`，不要用 `geometry['radius_line']`
   - 从 geometry 的坐标数据创建 Manim 对象：
   ```python
   def define_elements(self, geometry):
       pts = geometry['points']
       elements = {}
       # 从 geometry['lines']['AB'] 的坐标数据创建 Manim Line 对象
       for name, cfg in geometry['lines'].items():
           elements[name] = Line(start=cfg['start'], end=cfg['end'], color=self.COLORS['primary'])
       # 从 geometry['circles']['main'] 的数据创建 Manim Circle 对象
       for name, cfg in geometry['circles'].items():
           c = Circle(radius=cfg['radius'], color=self.COLORS['primary'])
           c.move_to(cfg['center'])
           elements[name] = c
       return elements
   ```
   - elements dict 的 key 可以和 geometry 的 key 不同，但访问 geometry 时必须用 geometry 中已有的 key

5. **play_scene_1(self, elements, geometry)** ~ **play_scene_6(self, elements, geometry)**
   - 6幕动画逻辑
   - 每幕开头调用 `expected = self.start_scene_with_audio(幕号)`
   - 用 `self.wait_for_narration("关键词")` 对齐动画和读白
   - 每幕结尾调用 `self.end_scene_with_audio(expected)`

### 6幕标准结构

| 幕号 | 名称 | 内容 |
|------|------|------|
| 1 | 开场 | 标题展示，介绍题目 |
| 2 | 画图形 | 绘制题目中的几何图形/数学对象 |
| 3 | 标注 | 标注已知条件、顶点、角度等 |
| 4 | 核心推导 | 关键解题步骤（辅助线、变换等） |
| 5 | 证明/计算 | 完成证明或计算过程 |
| 6 | 总结 | 结论展示，高亮所有元素 |

## 代码规范

1. **import**：只写 `from manim import *` 和 `import numpy as np`，基类已由外部导入
2. **类定义**：`class MathProblemScene(MathAnimScene):`（继承基类）
3. **坐标格式**：统一使用 `np.array([x, y, 0])`，3D 格式
4. **画布范围**：x ∈ [-5.5, 5.5]，y ∈ [-4.5, 4.5]，图形中心尽量在原点附近
   - **重要**：geometry 中 points/lines/circles 的坐标是显示坐标，不是题目的数学值
   - 如果题目半径=5，画在屏幕上的圆应该用 display_radius≈2.0，不是5.0
   - 数学值（如 radius=5, area=25π）单独存储在 geometry dict 中，不用作坐标
5. **音频同步**：配音提到什么，画面就高亮什么；用 `wait_for_narration` 对齐
6. **字幕**：用 `self.create_subtitle(text)` 创建，不用 Subtitle 类
7. **角度标记**：用 `Sector` 绘制角度弧
8. **虚线**：用 `DashedLine`
9. **不硬编码坐标**：所有坐标在 `calculate_geometry()` 中用 numpy 计算
10. **不写 construct()**：基类已有模板方法 construct()，会自动调用你的方法

## 文本渲染规则（重要！）

系统已安装 LaTeX（MiKTeX），可以使用 `MathTex()` 渲染数学公式。

**渲染规则：**
- **数学公式**（含符号如 ∠, π, √, ≤, ≥, 分数, 上标下标）→ 用 `MathTex()`
- **中文文字 / 纯英文文字** → 用 `Text()`，**不要设置 `font=` 参数**
- **不要用 `Tex()` 渲染中文**（LaTeX 默认不支持 Unicode 中文）

正确写法：
```python
# ✅ 数学公式用 MathTex
formula = MathTex(r"\angle A + \angle B + \angle C = 180^\circ", font_size=36, color=self.COLORS['text'])
area = MathTex(r"S = \pi r^2", font_size=42, color=self.COLORS['highlight'])
inequality = MathTex(r"x \leq 5", font_size=36)

# ✅ 中文/纯文字用 Text（不设 font 参数）
title = Text("三角形内角和定理", font_size=60, color=self.COLORS['highlight'])
subtitle = Text("证明过程", font_size=36, color=self.COLORS['text'])

# ✅ 顶点字母标签用 Text
label = Text("A", font_size=32, color=self.COLORS['text'])
label.next_to(point, UP, buff=0.2)
```

错误写法：
```python
# ❌ 错误：设了 font 参数，数学符号会显示为字母名称
title = Text("∠A = 60°", font="Microsoft YaHei", font_size=36)
# ❌ 错误：用 Tex 渲染中文
label = Tex(r"三角形内角和")
```

## 输出格式

你必须输出一个 JSON 对象，包含两个字段：

```json
{
    "scenes": [
        {"scene_num": 1, "name": "开场", "narration": "大家好，今天我们来学习..."},
        {"scene_num": 2, "name": "画三角形", "narration": "首先画一个三角形ABC..."},
        {"scene_num": 3, "name": "标注角度", "narration": "标记三个内角..."},
        {"scene_num": 4, "name": "画辅助线", "narration": "过顶点A作BC的平行线..."},
        {"scene_num": 5, "name": "证明", "narration": "利用内错角相等..."},
        {"scene_num": 6, "name": "总结", "narration": "因此三角形内角和等于180度"}
    ],
    "manim_code": "完整的 Python 代码字符串"
}
```

- `scenes`：6幕信息，每幕包含 scene_num、name、narration（配音文本）
- `manim_code`：完整的 Manim 场景代码，是一个字符串
- narration 文本会用于 TTS 语音合成，所以要用自然口语化的中文
- narration 中的关键词会用于 wait_for_narration() 的同步对齐

## 注意事项

- 代码必须是完整可运行的 Python 文件内容
- 不要用 markdown 代码块包裹 manim_code
- manim_code 中的换行用 \\n 表示（JSON 字符串转义）
- 代码中的引号需要正确转义
- 确保所有 wait_for_narration 中的关键词都能在对应幕的 narration 中找到
- **print 语句只能用 ASCII 字符**（Windows 控制台是 GBK 编码，Unicode 符号如 ✓⚠▶ 会崩溃。用 [OK] [!] >> 代替）
- **geometry dict 中绝不存 Manim 对象**（Line/Circle/Dot 等）！只存原始坐标数据（numpy数组/dict/数字）。Manim 对象在 define_elements() 中创建。
- **define_elements 中访问 geometry 的 key 必须和 calculate_geometry 中定义的完全一致**，不要凭空创造新 key
"""


# ================================================================
# 用户提示词模板
# ================================================================
def get_user_prompt(problem_text: str, grade_level: str = "初中", problem_type: str = "auto") -> str:
    """
    生成用户提示词

    Args:
        problem_text: 题目文本
        grade_level: 学段（初中/高中/小学）
        problem_type: 题型（geometry/equation/function/word_problem/fraction/auto）
    """
    type_hint = ""
    if problem_type and problem_type != "auto":
        type_map = {
            "geometry": "几何题",
            "equation": "方程题",
            "function": "函数题",
            "word_problem": "应用题",
            "fraction": "分数题",
        }
        type_hint = f"\n题目类型：{type_map.get(problem_type, problem_type)}"

    return f"""请为以下数学题目生成教学动画代码。

## 题目信息

学段：{grade_level}{type_hint}

题目：
{problem_text}

## 要求

1. 分析题目，确定解题思路
2. 设计6幕动画，每幕有自然的配音文本（narration）
3. 生成完整的 Manim 代码，继承 MathAnimScene
4. 在 calculate_geometry() 中用 numpy 计算所有坐标
5. 在 assert_geometry() 中验证题目关键事实
6. 每幕用 wait_for_narration("关键词") 对齐动画和配音
7. 配音文本要口语化、自然，适合 TTS 朗读
8. 确保动画在画布范围内（x∈[-5.5,5.5], y∈[-4.5,4.5]）
9. **关键**：geometry 中的坐标是显示坐标，不是数学值！如果半径=5，画在屏幕上用 display_radius≈2.0

请输出 JSON 格式，包含 scenes 数组和 manim_code 字符串。
"""


# ================================================================
# 完整示例（参考 MathLens script_example.py）
# ================================================================
EXAMPLE_CODE = r'''class TriangleAngleSum(MathAnimScene):
    """三角形内角和证明动画"""

    SCENES = [
        (1, "开场", "audio_001_开场.mp3", None),
        (2, "画三角形", "audio_002_画三角形.mp3", None),
        (3, "标角度", "audio_003_标角度.mp3", None),
        (4, "画平行线", "audio_004_画平行线.mp3", None),
        (5, "证明", "audio_005_证明.mp3", None),
        (6, "总结", "audio_006_总结.mp3", None),
    ]

    def calculate_geometry(self):
        A = np.array([0, 2, 0])
        B = np.array([-3, -2, 0])
        C = np.array([3, -2, 0])

        def dist(p1, p2):
            return np.linalg.norm(p1 - p2)

        AB = dist(A, B)
        AC = dist(A, C)
        BC = dist(B, C)

        def angle_at(p_vertex, p1, p2):
            v1 = p1 - p_vertex
            v2 = p2 - p_vertex
            cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            return np.arccos(np.clip(cos_a, -1, 1))

        angle_A = angle_at(A, B, C)
        angle_B = angle_at(B, A, C)
        angle_C = angle_at(C, A, B)

        parallel_dir = (C - B) / np.linalg.norm(C - B)
        parallel_start = A - parallel_dir * 4
        parallel_end = A + parallel_dir * 4

        return {
            'points': {'A': A, 'B': B, 'C': C},
            'lines': {
                'AB': {'start': A, 'end': B, 'length': AB},
                'AC': {'start': A, 'end': C, 'length': AC},
                'BC': {'start': B, 'end': C, 'length': BC},
                'parallel': {'start': parallel_start, 'end': parallel_end},
            },
            'angles': {
                'A': {'value': angle_A, 'deg': np.degrees(angle_A)},
                'B': {'value': angle_B, 'deg': np.degrees(angle_B)},
                'C': {'value': angle_C, 'deg': np.degrees(angle_C)},
            },
        }

    def assert_geometry(self, geometry):
        angles = geometry['angles']
        total = angles['A']['deg'] + angles['B']['deg'] + angles['C']['deg']
        assert abs(total - 180) < 0.1, f"内角和错误: {total}"
        self._check_canvas_bounds(geometry)
        print(f"[OK] Geometry validation passed (angles sum: {total:.1f} deg)")

    def define_elements(self, geometry):
        pts = geometry['points']
        elements = {'points': {}, 'lines': {}, 'labels': {}, 'angles': {}}

        for name, coord in pts.items():
            elements['points'][name] = Dot(point=coord, color=self.COLORS['text'], radius=0.1)
            elements['labels'][name] = Text(name, font_size=32, color=self.COLORS['text']).next_to(
                elements['points'][name],
                UP if name == 'A' else (DOWN + LEFT if name == 'B' else DOWN + RIGHT),
                buff=0.2
            )

        for name, cfg in geometry['lines'].items():
            if name == 'parallel':
                elements['lines'][name] = DashedLine(
                    start=cfg['start'], end=cfg['end'],
                    color=self.COLORS['secondary'], dash_length=0.2
                )
            else:
                elements['lines'][name] = Line(
                    start=cfg['start'], end=cfg['end'],
                    color=self.COLORS['primary'], stroke_width=4
                )

        return elements

    def play_scene_1(self, elements, geometry):
        expected = self.start_scene_with_audio(1)
        title = Text("三角形内角和定理", font_size=60, color=self.COLORS['highlight'])
        subtitle = Text("证明：三角形内角和等于180度", font_size=36, color=self.COLORS['text'])
        title.move_to(UP * 2)
        subtitle.next_to(title, DOWN, buff=0.5)
        self.play(FadeIn(title), run_time=1)
        self.play(FadeIn(subtitle), run_time=1)
        self.wait_for_narration("三角形")
        self.play(FadeOut(title), FadeOut(subtitle))
        self.end_scene_with_audio(expected)

    def play_scene_2(self, elements, geometry):
        expected = self.start_scene_with_audio(2)
        sub = self.create_subtitle("首先画一个任意三角形ABC")
        self.play(FadeIn(sub))
        self.wait_for_narration("三角形")
        self.play(Create(elements['lines']['AB']), run_time=1)
        self.play(Create(elements['lines']['AC']), run_time=1)
        self.play(Create(elements['lines']['BC']), run_time=1)
        self.play(
            *[FadeIn(elements['points'][p]) for p in 'ABC'],
            *[Write(elements['labels'][p]) for p in 'ABC'],
            run_time=1
        )
        self.play(FadeOut(sub))
        self.end_scene_with_audio(expected)

    def play_scene_3(self, elements, geometry):
        expected = self.start_scene_with_audio(3)
        sub = self.create_subtitle("标记三个内角")
        self.play(FadeIn(sub))
        self.wait_for_narration("内角")
        for name in ['A', 'B', 'C']:
            angle_val = geometry['angles'][name]['deg']
            label = MathTex(f"{angle_val:.0f}" + r"^\circ", font_size=24, color=self.COLORS[f'angle_{name.lower()}'])
            label.next_to(elements['points'][name], UP if name == 'A' else DOWN, buff=0.3)
            self.play(Write(label), run_time=0.5)
        self.play(FadeOut(sub))
        self.end_scene_with_audio(expected)

    def play_scene_4(self, elements, geometry):
        expected = self.start_scene_with_audio(4)
        sub = self.create_subtitle("过顶点A作BC的平行线")
        self.play(FadeIn(sub))
        self.wait_for_narration("平行线")
        self.play(Create(elements['lines']['parallel']), run_time=1.5)
        self.play(FadeOut(sub))
        self.end_scene_with_audio(expected)

    def play_scene_5(self, elements, geometry):
        expected = self.start_scene_with_audio(5)
        sub = self.create_subtitle("利用平行线性质：内错角相等")
        self.play(FadeIn(sub))
        self.wait_for_narration("内错角")
        conclusion = MathTex(r"\therefore \angle A + \angle B + \angle C = 180^\circ", font_size=48, color=self.COLORS['highlight'])
        conclusion.to_edge(DOWN, buff=1.5)
        self.play(Write(conclusion), run_time=1)
        self.play(FadeOut(sub), FadeOut(conclusion))
        self.end_scene_with_audio(expected)

    def play_scene_6(self, elements, geometry):
        expected = self.start_scene_with_audio(6)
        sub = self.create_subtitle("三角形内角和恒等于180度")
        self.play(FadeIn(sub))
        self.wait_for_narration("180度")
        all_elems = list(elements['lines'].values()) + list(elements['points'].values())
        self.play(*[e.animate.set_color(self.COLORS['highlight']) for e in all_elems], run_time=1)
        final = Text("证毕", font_size=72, color=self.COLORS['highlight'])
        self.play(Write(final), run_time=1)
        self.wait(1)
        self.play(FadeOut(final), FadeOut(sub))
        self.end_scene_with_audio(expected)
'''
