"""
MathAnimScene — Claude 直生代码的脚手架基类

参考 MathLens 模板项目的 script_scaffold.py 设计：
- 6幕持久化结构：calculate_geometry → assert_geometry → define_elements → play_scene_1~6
- 音画同步：wait_for_narration(keyword) + sync_points 精确对齐
- 统一收口：start_scene_with_audio / end_scene_with_audio 防止音频重叠
- 字幕 & 高亮工具

Claude 生成的代码继承此类，只需实现：
  - calculate_geometry()    → 几何计算（numpy 算坐标，不靠 LLM 硬编码）
  - assert_geometry()       → 验证关键事实 + 画布范围
  - define_elements()       → 创建 Manim Mobject 对象
  - play_scene_1~6()        → 6 幕动画逻辑
  - SCENES 类变量            → 幕信息数组
"""

from manim import *
import json
import os
import sys as _sys
import numpy as np

# Windows GBK 控制台兼容：将 stdout/stderr 切到 UTF-8，避免 print Unicode 字符崩溃
try:
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    _sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


class MathAnimScene(Scene):
    """
    数学教学动画基类（Claude 直生代码的脚手架）

    核心原则：
    1. 数学先行 — 先用 numpy 建立正确的几何模型，坐标不靠 LLM 硬编码
    2. 音画同步 — 用 wait_for_narration("关键词") 对齐高亮与读白
    3. 高亮对应 — 配音提到什么，画面高亮什么
    4. 最小验证 — assert_geometry 只验证关键事实和画布范围
    5. 统一收口 — 每幕通过 start/end_scene_with_audio 防止音频重叠
    """

    # ========== 颜色配置（参考 MathLens 模板，深色背景 + 亮色配色） ==========
    COLORS = {
        'background': '#1a1a2e',
        'primary': '#4ecca3',       # 青色 — 主要线条
        'secondary': '#e94560',     # 红色 — 辅助线
        'highlight': '#ffc107',     # 黄色 — 高亮
        'text': '#ffffff',
        'text_secondary': '#aaaaaa',
        'grid': '#2a2a4e',
        'axis': '#444466',
        # 角度配色
        'angle_a': '#ff6b6b',
        'angle_b': '#4ecdc4',
        'angle_c': '#ffe66d',
    }

    # ========== 幕信息数组（子类必须覆写） ==========
    SCENES = [
        # (幕号, 幕名, 音频文件名, 时长秒数)
        # 时长从 audio_info.json 自动读取
        # TODO: 子类覆写
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 音频目录：优先使用环境变量，回退到项目输出目录
        self.audio_dir = os.environ.get("MATHANIM_AUDIO_DIR", "audio")
        self.audio_info_file = os.path.join(self.audio_dir, "audio_info.json")
        self._current_scene_num = None
        self._current_scene_name = ""
        self._scene_start_time = 0.0
        self._audio_safety_margin = 0.2
        self._sync_points = {}  # {scene_num: [{idx, text, time}, ...]}
        self._audio_data = self._load_audio_data()

    # ========== 音频管理 ==========

    def _load_audio_data(self):
        """从 audio_info.json 加载音频时长和同步点"""
        if not os.path.exists(self.audio_info_file):
            print(f"Warning: audio_info.json not found at {self.audio_info_file}")
            return {}

        try:
            with open(self.audio_info_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load audio info: {e}")
            return {}

        timings = {}
        self._audio_file_paths = {}  # {scene_num: absolute_path}

        for item in data.get('files', []):
            scene_num = item.get('scene')
            duration = item.get('duration')
            file_path = item.get("path", "")
            filename = item.get("file", "")

            if scene_num and duration:
                timings[scene_num] = duration

            if scene_num and file_path and os.path.exists(file_path):
                self._audio_file_paths[scene_num] = file_path
            elif scene_num and filename:
                full_path = os.path.join(self.audio_dir, filename)
                if os.path.exists(full_path):
                    self._audio_file_paths[scene_num] = full_path

            sp = item.get('sync_points', [])
            if scene_num and sp:
                self._sync_points[scene_num] = sp

        # 更新 SCENES 中的时长
        for i, (scene_num, name, audio_file, _) in enumerate(self.SCENES):
            if scene_num in timings:
                self.SCENES[i] = (scene_num, name, audio_file, timings[scene_num])

        return timings

    def add_scene_audio(self, scene_num, play_audio=True):
        """添加指定幕的音频（通过 add_sound 嵌入到视频）"""
        # 策略1：通过 audio_info.json 中的绝对路径查找
        if hasattr(self, '_audio_file_paths') and scene_num in self._audio_file_paths:
            audio_path = self._audio_file_paths[scene_num]
            if os.path.exists(audio_path):
                if play_audio:
                    self.add_sound(audio_path)
                # 返回时长
                for sn, name, audio_file, duration in self.SCENES:
                    if sn == scene_num:
                        return duration
                return 0

        # 策略2：通过 SCENES 中的文件名在 audio_dir 中查找
        for sn, name, audio_file, duration in self.SCENES:
            if sn == scene_num:
                audio_path = os.path.join(self.audio_dir, audio_file)
                if os.path.exists(audio_path):
                    if play_audio:
                        self.add_sound(audio_path)
                    return duration
                else:
                    print(f"Warning: Audio file not found: {audio_path}")
                    return 0
        return 0

    def start_scene_with_audio(self, scene_num):
        """
        开始一幕并播放该幕音频（防重叠入口）

        返回：float — 该幕音频时长（秒）
        """
        self._current_scene_num = scene_num
        self._scene_start_time = self.time

        expected = 0.0
        for sn, name, _, duration in self.SCENES:
            if sn == scene_num:
                self._current_scene_name = name
                expected = float(duration or 0)
                break
        else:
            self._current_scene_name = f"Scene {scene_num}"

        self.add_scene_audio(scene_num, play_audio=True)
        print(
            f"\n>> Scene {scene_num}: {self._current_scene_name} | "
            f"audio={expected:.2f}s | t={self._scene_start_time:.2f}s"
        )
        return expected

    def end_scene_with_audio(self, expected_duration=None, safety_margin=None):
        """
        结束一幕并补足等待，确保不抢跑到下一幕导致音频重叠。

        每幕的 play_scene_N() 结束后必须调用此方法。
        """
        if expected_duration is None:
            expected_duration = 0.0
        if safety_margin is None:
            safety_margin = self._audio_safety_margin

        elapsed = self.time - self._scene_start_time
        target = max(0.0, float(expected_duration)) + max(0.0, float(safety_margin))
        remaining = target - elapsed

        if remaining > 1e-3:
            self.wait(remaining)
            elapsed = self.time - self._scene_start_time

        if elapsed + 1e-3 < target:
            print(
                f"[!] Scene {self._current_scene_num} timeline short: "
                f"elapsed={elapsed:.2f}s < target={target:.2f}s"
            )
        else:
            print(
                f"[OK] Scene {self._current_scene_num} done: "
                f"elapsed={elapsed:.2f}s / target={target:.2f}s"
            )

    # ========== 幕内同步工具（核心） ==========

    def wait_until_scene_time(self, target_time):
        """
        等待到当前幕内的指定时刻（相对于幕开始的秒数）。

        如果动画已超过目标时刻，打印警告但不回退。
        用法：self.wait_until_scene_time(3.7)  # 等到幕开始后 3.7s
        """
        elapsed = self.time - self._scene_start_time
        remaining = target_time - elapsed
        if remaining > 0.05:
            self.wait(remaining)
        elif remaining < -0.3:
            print(
                f"  [!] 幕{self._current_scene_num} 动画超时 {abs(remaining):.2f}s"
                f"（目标 {target_time:.1f}s，实际已 {elapsed:.1f}s）"
            )

    def wait_for_narration(self, keyword):
        """
        等待到读白说出包含 keyword 的那句话的起始时刻。

        从当前幕的 sync_points 中查找第一个 text 包含 keyword 的条目，
        然后调用 wait_until_scene_time() 对齐。

        用法：
            self.wait_for_narration("内切圆")
            self.play(FadeIn(incircle))
        """
        target = self.get_sync_time(keyword)
        if target is not None:
            self.wait_until_scene_time(target)
        else:
            print(
                f"  [!] 幕{self._current_scene_num} 未找到同步点 '{keyword}'，"
                f"跳过等待（检查 audio_info.json 的 sync_points）"
            )

    def get_sync_time(self, keyword):
        """
        查找当前幕中包含 keyword 的同步点时间。

        返回：float 秒数，未找到返回 None
        """
        points = self._sync_points.get(self._current_scene_num, [])
        for sp in points:
            if keyword in sp.get("text", ""):
                return sp["time"]
        return None

    def get_sync_time_by_index(self, sentence_idx):
        """
        按句子序号获取同步点时间（第 0 句、第 1 句...）。

        返回：float 秒数，未找到返回 None
        """
        points = self._sync_points.get(self._current_scene_num, [])
        for sp in points:
            if sp.get("idx") == sentence_idx:
                return sp["time"]
        return None

    # ========== 几何计算（子类必须实现） ==========

    def calculate_geometry(self):
        """
        计算所有几何元素的位置和属性（子类必须覆写）。

        坐标系说明：
        - 所有点的格式：np.array([x, y, 0])
        - 建议将几何图形放在 (-5, 5) x (-3, 3) 区域内
        - 使用 numpy 计算坐标，不要硬编码

        返回：dict 包含所有几何对象的数据
        """
        return {
            'points': {},
            'lines': {},
            'circles': {},
            'arcs': {},
            'polygons': {},
            'angles': {},
        }

    # ========== 几何验证（子类必须实现） ==========

    def assert_geometry(self, geometry):
        """
        验证几何计算的正确性（子类必须覆写）。

        验证内容：
        1. 题目给定的事实（如：两条边相等）
        2. 精度问题：使用相对误差比较
        3. 画布范围检查：确保图形在可视区域内
        """
        self._check_canvas_bounds(geometry)
        print("Geometry validation passed!")

    def _check_canvas_bounds(self, geometry):
        """检查所有几何元素是否在画布可视范围内

        兼容多种数据格式：
        - points: list/tuple/np.ndarray，如 [x, y] 或 [x, y, 0]
        - circles: dict {'center': (cx,cy), 'radius': r} 或 tuple ((cx,cy), r)
        - lines: dict {'start': (x,y), 'end': (x,y)} 或 tuple ((x1,y1), (x2,y2))
        """
        all_points = []

        def _extract_xy(p):
            """从各种格式中提取 (x, y) 坐标"""
            if isinstance(p, np.ndarray):
                return (float(p[0]), float(p[1]))
            elif isinstance(p, (list, tuple)):
                return (float(p[0]), float(p[1]))
            return None

        for p in geometry.get('points', {}).values():
            xy = _extract_xy(p)
            if xy:
                all_points.append(xy)

        for circle in geometry.get('circles', {}).values():
            if isinstance(circle, dict):
                center = circle.get('center', (0, 0))
                r = circle.get('radius', 0)
            elif isinstance(circle, (list, tuple)) and len(circle) >= 2:
                center, r = circle[0], circle[1]
            else:
                continue
            cx, cy = _extract_xy(center) or (0, 0)
            r = float(r) if not isinstance(r, np.ndarray) else float(r.item())
            all_points.extend([(cx+r, cy), (cx-r, cy), (cx, cy+r), (cx, cy-r)])

        for line in geometry.get('lines', {}).values():
            if isinstance(line, dict):
                s, e = line.get('start'), line.get('end')
            elif isinstance(line, (list, tuple)) and len(line) >= 2:
                s, e = line[0], line[1]
            else:
                continue
            xy_s = _extract_xy(s)
            xy_e = _extract_xy(e)
            if xy_s:
                all_points.append(xy_s)
            if xy_e:
                all_points.append(xy_e)

        if not all_points:
            return True

        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # 与 MathLens 模板保持一致：x∈[-6,6], y∈[-5,5], 留 0.5 边距
        CANVAS_MIN_X, CANVAS_MAX_X = -6, 6
        CANVAS_MIN_Y, CANVAS_MAX_Y = -5, 5
        MARGIN = 0.5

        # 使用警告而非 assert，避免画布范围问题导致整个渲染失败
        warnings = []
        if min_x < CANVAS_MIN_X + MARGIN:
            warnings.append(f"图形超出左边界：{min_x:.1f} < {CANVAS_MIN_X + MARGIN}")
        if max_x > CANVAS_MAX_X - MARGIN:
            warnings.append(f"图形超出右边界：{max_x:.1f} > {CANVAS_MAX_X - MARGIN}")
        if min_y < CANVAS_MIN_Y + MARGIN:
            warnings.append(f"图形超出下边界：{min_y:.1f} < {CANVAS_MIN_Y + MARGIN}")
        if max_y > CANVAS_MAX_Y - MARGIN:
            warnings.append(f"图形超出上边界：{max_y:.1f} > {CANVAS_MAX_Y - MARGIN}")

        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        if abs(center_x) > 2.0:
            warnings.append(f"图形中心偏离 x 轴：{center_x:.1f}")
        if abs(center_y) > 2.0:
            warnings.append(f"图形中心偏离 y 轴：{center_y:.1f}")

        if warnings:
            print("[Canvas Bounds Warning] " + "; ".join(warnings))

        return True

    # ========== 图形元素定义（子类必须实现） ==========

    def define_elements(self, geometry):
        """
        定义 Manim 图形对象（子类必须覆写）。

        在此处创建 Dot、Line、Sector、Text 等 Mobject，
        但不要创建动画（动画在 play_scene_N 中）。

        返回：dict 包含所有 Mobject 元素
        """
        return {
            'points': {},
            'lines': {},
            'circles': {},
            'labels': {},
            'angles': {},
        }

    # ========== 字幕工具 ==========

    def create_subtitle(self, text, position=None):
        """
        创建字幕对象（底部纯文字，无背景框）。
        自动检测数学符号：含数学符号时不设font让Pango回退，纯中文时用雅黑。

        Args:
            text: 字幕文本
            position: 位置向量，默认底部
        """
        # 检测是否包含数学符号
        _math_syms = set('×÷≤≥≠±≈≡∞∑∫√∠△∥⊥°²³∴∵→←↑↓⇒⇐⇔')
        _math_syms |= set('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨαβγδεζηθικλμνξοπρστυφχψω')
        has_math = any(c in _math_syms for c in text)

        if has_math:
            sub = Text(text, font_size=36, color=self.COLORS['text'])
        else:
            sub = Text(text, font_size=36, color=self.COLORS['text'], font="Microsoft YaHei")
        sub.to_edge(DOWN, buff=0.5)
        if position is not None:
            sub.move_to(position)
        return sub

    def fade_in(self, mobject, run_time=0.5):
        """便捷 FadeIn 包装"""
        return FadeIn(mobject, run_time=run_time)

    def fade_out(self, mobject, run_time=0.5):
        """便捷 FadeOut 包装"""
        return FadeOut(mobject, run_time=run_time)

    def show_subtitle_timed(self, text, duration, position=None,
                            fade_in_time=0.5, fade_out_time=0.5):
        """
        显示字幕并在指定时间后自动退场。

        Args:
            text: 字幕文本
            duration: 总显示时长（秒）
            position: 位置（默认底部）
            fade_in_time: 淡入时长
            fade_out_time: 淡出时长
        """
        subtitle = self.create_subtitle(text, position)
        self.play(self.fade_in(subtitle), run_time=fade_in_time)
        hold_time = max(0.0, duration - fade_in_time - fade_out_time)
        self.wait(hold_time)
        self.play(self.fade_out(subtitle), run_time=fade_out_time)
        return subtitle

    # ========== 高亮工具 ==========

    def highlight_element(self, element, color=None, scale=1.3, duration=0.8):
        """
        高亮指定元素（放大 + 变色 → 停留 → 恢复）。

        Args:
            element: Manim Mobject
            color: 高亮颜色，默认使用 COLORS['highlight']
            scale: 放大倍数
            duration: 总高亮时长
        """
        color = color or self.COLORS['highlight']
        original_color = element.get_color()
        self.play(
            element.animate.scale(scale).set_color(color),
            run_time=0.4
        )
        self.wait(max(0.0, duration - 0.4))
        self.play(
            element.animate.scale(1/scale).set_color(original_color),
            run_time=0.4
        )

    def indicate_equal_lines(self, line1, line2, duration=1.2):
        """指示两条线段相等（同时高亮）"""
        self.play(
            line1.animate.set_color(self.COLORS['highlight']).set_stroke(width=6),
            line2.animate.set_color(self.COLORS['highlight']).set_stroke(width=6),
            run_time=0.5
        )
        self.wait(max(0.0, duration - 0.8))
        self.play(
            line1.animate.set_color(self.COLORS['primary']).set_stroke(width=3),
            line2.animate.set_color(self.COLORS['primary']).set_stroke(width=3),
            run_time=0.5
        )

    # ========== 主流程（模板方法，子类不需要覆写） ==========

    def construct(self):
        """
        主构造流程（模板方法）：
        1. 设置背景色
        2. 计算几何 → 验证 → 定义元素
        3. 依次执行 play_scene_1 ~ play_scene_6
        """
        self.camera.background_color = self.COLORS['background']

        geometry = self.calculate_geometry()
        self.assert_geometry(geometry)

        try:
            elements = self.define_elements(geometry)
        except KeyError as e:
            raise KeyError(
                f"define_elements() KeyError: key {e} not found in geometry. "
                f"Available geometry keys: {list(geometry.keys())}. "
                f"Make sure define_elements uses the same keys as calculate_geometry."
            ) from e

        for scene_num, scene_name, audio_file, duration in self.SCENES:
            method_name = f"play_scene_{scene_num}"
            if hasattr(self, method_name):
                expected_duration = self.start_scene_with_audio(scene_num)
                try:
                    getattr(self, method_name)(elements, geometry)
                except KeyError as e:
                    raise KeyError(
                        f"play_scene_{scene_num}() KeyError: key {e} not found. "
                        f"Available geometry keys: {list(geometry.keys())}, "
                        f"elements keys: {list(elements.keys())}. "
                        f"Make sure you use the same keys as defined in calculate_geometry/define_elements."
                    ) from e
                self.end_scene_with_audio(expected_duration)
            else:
                print(f"Warning: play_scene_{scene_num} not implemented")
        # 视频拷贝由 main.py 在 subprocess 完成后处理，此处不再调用

    def _copy_video_to_output(self):
        """渲染完成后拷贝视频到指定输出目录"""
        import shutil
        from pathlib import Path

        scene_name = self.__class__.__name__
        # 尝试多个可能的输出路径
        possible_paths = [
            Path(f"media/videos/script/1920p60/{scene_name}.mp4"),
            Path(f"media/videos/script/1080p60/{scene_name}.mp4"),
            Path(f"media/videos/script/720p30/{scene_name}.mp4"),
            Path(f"media/videos/{scene_name}.py/1080p60/{scene_name}.mp4"),
            Path(f"media/videos/{scene_name}.py/720p30/{scene_name}.mp4"),
        ]

        video_src = None
        for path in possible_paths:
            if path.exists():
                video_src = path
                break

        # 递归搜索 media 目录
        if not video_src:
            media_dir = Path("media/videos")
            if media_dir.exists():
                for mp4 in media_dir.rglob(f"{scene_name}.mp4"):
                    video_src = mp4
                    break

        if video_src:
            output_dir = os.environ.get("MATHANIM_VIDEO_OUTPUT", "")
            if output_dir:
                video_dst = Path(output_dir) / f"{scene_name}.mp4"
            else:
                video_dst = Path(f"{scene_name}.mp4")
            try:
                shutil.copy2(video_src, video_dst)
                print(f"\n[OK] 视频已拷贝到：{video_dst.absolute()}")
            except Exception as e:
                print(f"\n[!] 视频拷贝失败：{e}")
        else:
            print(f"\n[!] 未找到视频文件，搜索路径: {possible_paths}")


# ========== 使用说明 ==========
"""
关键提醒（Claude 生成代码时必须遵守）：

1. 所有几何计算必须在 calculate_geometry() 中用 numpy 完成，不要硬编码坐标
2. assert_geometry() 必须检查画布范围（调用 self._check_canvas_bounds）
3. 每幕必须通过 start_scene_with_audio()/end_scene_with_audio() 统一收口
4. 配音提到什么，画面就高亮什么
5. 使用 wait_for_narration("关键词") 对齐读白和高亮时机
6. 使用 wait_until_scene_time(秒数) 精确定位幕内时间点
7. 使用 create_subtitle() 创建字幕
8. 幕末收尾统一由 end_scene_with_audio() 自动补足，play_scene_N() 内不需要手动兜底
9. 所有点坐标使用 np.array([x, y, 0])，3D 格式
10. 字幕退场：使用 show_subtitle_timed() 确保文字退场

同步对齐示例（推荐写法）：
    def play_scene_2(self, elements, geometry):
        # 读白第1句："首先，我们来看三角形ABC"
        self.wait_for_narration("三角形ABC")
        self.play(Create(triangle, run_time=1.0))

        # 读白第2句："它的内切圆I，分别切三条边"
        self.wait_for_narration("内切圆")
        self.play(FadeIn(incircle, run_time=0.5))

        # 无需手动兜底——end_scene_with_audio() 会自动补齐
"""
