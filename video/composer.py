"""
============================================================
MathAnimAI — 视频合成模块 (ffmpeg 原生版)
功能：
  1. 将 TTS 音频合并到 Manim 动画视频
  2. 用 ffmpeg subtitles 滤镜烧录 SRT 字幕
  3. -shortest 自动裁剪视频以匹配音频时长
  4. 比 moviepy 方案提速 10-100 倍

替代旧的 moviepy 实现，解决：
  - 视频合成耗时过长（16 分钟 → 约 30 秒）
  - 音画不同步（音频结束但视频继续播放）
============================================================
"""

import os
import re
import subprocess
import logging
from typing import Optional

from config import (
    OUTPUT_VIDEO_DIR,
    SUBTITLE_FONT_SIZE,
    get_timestamp,
    ensure_dirs,
    RESOLUTION_WIDTH,
    RESOLUTION_HEIGHT,
)

logger = logging.getLogger("MathAnimAI.Composer")


# ================================================================
# FFmpeg 路径检测
# ================================================================
def _find_ffmpeg() -> Optional[str]:
    """查找 ffmpeg 可执行文件"""
    # 方法1：从 imageio_ffmpeg 获取（与 Manim 渲染器一致）
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass

    # 方法2：系统 PATH
    for name in ["ffmpeg", "ffmpeg.exe"]:
        try:
            result = subprocess.run(
                [name, "-version"],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                return name
        except Exception:
            continue

    return None


_FFMPEG_PATH = _find_ffmpeg()

if _FFMPEG_PATH:
    logger.info(f"FFmpeg 路径: {_FFMPEG_PATH}")
else:
    logger.warning("未找到 FFmpeg，视频合成将降级到 moviepy")


# ================================================================
# SRT 字幕 → ffmpeg force_style 字符串
# ================================================================
def _build_subtitle_style() -> str:
    """构建 ffmpeg subtitles 滤镜的 force_style 参数"""
    # 检测中文字体
    font_name = "Microsoft YaHei"
    font_dir = "C\\:/Windows/Fonts" if os.path.exists("C:/Windows/Fonts") else ""

    styles = [
        f"FontName={font_name}",
        f"FontSize={SUBTITLE_FONT_SIZE}",
        "PrimaryColour=&H00FFFFFF",     # 白色文字
        "OutlineColour=&H00000000",      # 黑色描边
        "Outline=2",
        "BackColour=&H80000000",         # 半透明黑色背景
        "BorderStyle=4",                 # 背景框模式
        "Alignment=2",                   # 底部居中
        "MarginV=40",                    # 底部边距
    ]
    return ",".join(styles)


def _escape_ffmpeg_path(path: str) -> str:
    """将 Windows 路径转义为 ffmpeg 可接受的格式"""
    # ffmpeg 的 subtitles 滤镜中，路径中的 : 和 \ 需要特殊处理
    # 将反斜杠替换为正斜杠，然后用单引号包裹
    escaped = path.replace("\\", "/")
    # 对冒号进行转义（Windows 盘符如 C:/... 中的冒号）
    escaped = escaped.replace(":", "\\\\:")
    return escaped


# ================================================================
# 检测视频是否已包含音频流
# ================================================================
def _has_audio_stream(video_path: str) -> bool:
    """检测视频文件是否包含音频流"""
    if not _FFMPEG_PATH or not os.path.exists(video_path):
        return False
    try:
        cmd = [_FFMPEG_PATH, "-i", video_path, "-hide_banner"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return "Audio:" in result.stderr
    except Exception:
        return False


# ================================================================
# 核心合成函数（ffmpeg 版本）
# ================================================================
def compose_video(
    animation_path: str,
    audio_path: str = None,
    subtitle_path: str = None,
    title: str = "",
    output_path: str = None,
    add_intro: bool = False,
    add_outro: bool = False,
    encoding_preset: str = "fast",
) -> Optional[str]:
    """
    合成完整教学视频：动画 + 音频 + 字幕

    音画同步策略（参考 MathLens 模板项目）：
    - 如果动画视频已通过 Manim add_sound() 嵌入音频，则不再合并外部音频
    - 仅烧录字幕
    - 如果动画视频无音频（降级情况），则合并外部音频

    Args:
        animation_path: Manim 渲染的动画视频路径（可能已含音频）
        audio_path: 外部音频路径（仅在动画无音频时使用）
        subtitle_path: SRT 字幕文件路径
        title: 视频标题
        output_path: 输出路径
        add_intro: 是否添加片头（保留参数兼容）
        add_outro: 是否添加片尾（保留参数兼容）
        encoding_preset: ffmpeg preset

    Returns:
        合成的 MP4 视频路径
    """
    # 如果没有 ffmpeg，降级到 moviepy
    if not _FFMPEG_PATH:
        return _compose_video_moviepy_fallback(
            animation_path, audio_path, subtitle_path,
            title, output_path, add_intro, add_outro,
        )

    try:
        # 验证输入
        if not os.path.exists(animation_path):
            logger.error(f"动画视频不存在: {animation_path}")
            return None

        # 检测动画视频是否已包含音频流（通过 add_sound 嵌入）
        video_has_audio = _has_audio_stream(animation_path)
        external_audio = audio_path and os.path.exists(audio_path)
        has_subtitle = subtitle_path and os.path.exists(subtitle_path)

        # 决定音频来源
        if video_has_audio:
            # 视频已含音频（add_sound 嵌入），无需外部音频
            has_audio = True
            use_external_audio = False
            logger.info("动画视频已含音频流（add_sound 嵌入），跳过外部音频合并")
        elif external_audio:
            # 视频无音频，使用外部音频
            has_audio = True
            use_external_audio = True
            logger.info("动画视频无音频，使用外部音频合并")
        else:
            has_audio = False
            use_external_audio = False
            logger.info("无音频源，输出静音视频")

        logger.info(
            f"开始视频合成 (ffmpeg): animation={animation_path}, "
            f"video_has_audio={video_has_audio}, "
            f"subtitle={'有' if has_subtitle else '无'}"
        )

        # 输出路径
        if output_path is None:
            timestamp = get_timestamp()
            output_path = os.path.join(OUTPUT_VIDEO_DIR, f"final_{timestamp}.mp4")
        ensure_dirs()

        # ================================================================
        # 构建 ffmpeg 命令
        # ================================================================
        cmd = [_FFMPEG_PATH, "-hide_banner", "-loglevel", "warning"]

        # 输入：动画视频
        cmd.extend(["-i", animation_path])

        # 输入：外部音频（仅当视频无音频且外部音频存在时）
        if use_external_audio:
            cmd.extend(["-i", audio_path])

        # 视频滤镜：字幕烧录
        video_filters = []
        if has_subtitle:
            abs_subtitle = os.path.abspath(subtitle_path)
            escaped_sub = abs_subtitle.replace("\\", "/").replace(":", "\\:")
            style = _build_subtitle_style()
            sub_filter = f"subtitles='{escaped_sub}':force_style='{style}'"
            video_filters.append(sub_filter)
            logger.info(f"字幕文件: {abs_subtitle}")

        if video_filters:
            cmd.extend(["-vf", ",".join(video_filters)])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", encoding_preset,
            "-crf", "23",
            "-pix_fmt", "yuv420p",
        ])

        # 音频编码参数
        if has_audio:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "128k",
            ])
        else:
            cmd.extend(["-an"])

        # -shortest：仅在使用外部音频时需要（匹配最短流）
        # 当视频已含音频时不需要 -shortest（音视频已在 Manim 中同步）
        if use_external_audio:
            cmd.append("-shortest")

        # 输出选项
        cmd.extend([
            "-movflags", "+faststart",
            "-y",
            output_path,
        ])

        # ================================================================
        # 执行 ffmpeg
        # ================================================================
        logger.info(f"ffmpeg 命令: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode != 0:
            stderr_tail = result.stderr.strip()[-500:] if result.stderr else ""
            logger.error(f"ffmpeg 合成失败 (returncode={result.returncode}):\n{stderr_tail}")

            if has_subtitle and "subtitles" in stderr_tail:
                logger.warning("字幕滤镜失败，尝试无字幕合成...")
                return compose_video(
                    animation_path, audio_path,
                    subtitle_path=None,
                    output_path=output_path,
                )
            return None

        logger.info(f"视频合成完成: {output_path}")
        return output_path

    except subprocess.TimeoutExpired:
        logger.error("ffmpeg 合成超时（10分钟）")
        return None
    except Exception as e:
        logger.error(f"视频合成异常: {e}")
        return None


# ================================================================
# Moviepy 降级方案（当 ffmpeg 不可用时）
# ================================================================
def _compose_video_moviepy_fallback(
    animation_path: str,
    audio_path: str,
    subtitle_path: str = None,
    title: str = "",
    output_path: str = None,
    add_intro: bool = True,
    add_outro: bool = True,
) -> Optional[str]:
    """moviepy 降级合成方案（保留旧逻辑作为兜底）"""
    try:
        from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip
        from moviepy import TextClip, ColorClip, vfx

        logger.info(f"[moviepy降级] 开始视频合成: animation={animation_path}")

        if not os.path.exists(animation_path):
            logger.error(f"动画视频不存在: {animation_path}")
            return None

        video = VideoFileClip(animation_path)
        video_duration = video.duration
        raw_w, raw_h = video.size
        width, height = int(raw_w), int(raw_h)
        logger.info(f"动画视频: {width}x{height}, 时长={video_duration:.1f}s")

        # 加载音频
        if audio_path and os.path.exists(audio_path):
            audio = AudioFileClip(audio_path)
            logger.info(f"音频时长={audio.duration:.1f}s")

            if audio.duration > video_duration + 0.3:
                gap = audio.duration - video_duration
                logger.info(f"音频比视频长 {gap:.1f}s，扩展视频")
                video = _extend_video_with_freeze(video, audio.duration)

            video = video.with_audio(audio)

        # 字幕
        if subtitle_path and os.path.exists(subtitle_path):
            video = _add_subtitles_to_video(video, subtitle_path, width, height)

        # 输出
        if output_path is None:
            timestamp = get_timestamp()
            output_path = os.path.join(OUTPUT_VIDEO_DIR, f"final_{timestamp}.mp4")
        ensure_dirs()

        logger.info(f"渲染输出: {output_path}")
        video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            logger=None,
        )
        logger.info(f"视频合成完成: {output_path}")
        return output_path

    except ImportError:
        logger.error("moviepy 未安装")
        return animation_path
    except Exception as e:
        logger.error(f"moviepy 合成失败: {e}")
        return animation_path


# ================================================================
# Moviepy 工具函数（降级方案复用）
# ================================================================
def _add_subtitles_to_video(video, subtitle_path, width, height):
    """SRT 字幕渲染（moviepy 方案）"""
    try:
        from moviepy import CompositeVideoClip, TextClip
        from PIL import ImageFont
    except ImportError:
        return video

    # 找字体
    font = None
    for f in [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]:
        if os.path.exists(f):
            font = f
            break
    if font is None:
        font = "Arial"

    subtitles = _parse_srt(subtitle_path)
    if not subtitles:
        return video

    subtitle_clips = []
    for start, end, text in subtitles:
        if len(text) > 30:
            wrapped = []
            for i in range(0, len(text), 25):
                wrapped.append(text[i:i+25])
            text = "\n".join(wrapped)

        txt_clip = TextClip(
            text=text, font=font, font_size=SUBTITLE_FONT_SIZE,
            color="white", stroke_color="black", stroke_width=2,
            size=(int(width * 0.85), None),
            method="caption", text_align="center",
        )

        from moviepy import ColorClip
        bg = ColorClip(
            size=(max(1, int(txt_clip.w * 1.05)), max(1, int(txt_clip.h * 1.1))),
            color=(0, 0, 0),
        ).with_opacity(0.6)

        group = CompositeVideoClip([bg, txt_clip.with_position("center")])
        group = group.with_start(start).with_end(end)
        group = group.with_position(("center", int(height * 0.82)))
        subtitle_clips.append(group)

    return CompositeVideoClip([video] + subtitle_clips)


def _parse_srt(srt_path: str) -> list:
    """解析 SRT 文件"""
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r"(\d+:\d+:\d+[.,]\d+)\s*-->\s*(\d+:\d+:\d+[.,]\d+)\n(.+?)(?=\n\n|\n$|\Z)"
    matches = re.findall(pattern, content, re.DOTALL)

    subtitles = []
    for start_str, end_str, text in matches:
        start = _srt_time_to_seconds(start_str)
        end = _srt_time_to_seconds(end_str)
        text = text.strip().replace("\n", " ")
        subtitles.append((start, end, text))
    return subtitles


def _srt_time_to_seconds(time_str: str) -> float:
    """SRT 时间转秒"""
    match = re.match(r"(\d+):(\d+):(\d+)[.,](\d+)", time_str)
    if match:
        h, m, s, ms = map(int, match.groups())
        return h * 3600 + m * 60 + s + ms / 1000
    return 0.0


def _extend_video_with_freeze(video, target_duration: float):
    """冻结最后一帧扩展视频"""
    from moviepy import concatenate_videoclips, vfx
    gap = target_duration - video.duration
    if gap <= 0.1:
        return video
    try:
        last_frame = video.to_ImageClip(t=video.duration - 0.05, duration=gap)
        last_frame = last_frame.with_effects([vfx.FadeOut(0.5)])
        return concatenate_videoclips([video, last_frame], method="compose")
    except Exception:
        return video


# ================================================================
# 步骤独立渲染 → ffmpeg 拼接合成
# ================================================================
def compose_from_steps(
    step_videos: list[dict],
    step_audios: list[str],
    subtitle_path: str = None,
    output_path: str = None,
    encoding_preset: str = "fast",
) -> Optional[str]:
    """
    将 N 个独立渲染的步骤视频拼接为最终视频。

    音画同步策略（参考 MathLens 模板项目）：
    - 如果步骤视频已通过 add_sound() 嵌入音频，直接拼接视频+烧录字幕
    - 如果步骤视频无音频（降级），拼接视频+拼接音频+合并

    流程（视频已含音频）：
    1. ffmpeg concat 拼接所有步骤视频（含音频） → combined.mp4
    2. ffmpeg 烧录字幕 → final.mp4

    流程（视频无音频，降级）：
    1. ffmpeg concat 拼接所有步骤视频 → silent.mp4
    2. ffmpeg concat 拼接所有步骤音频 → full_audio.mp3
    3. ffmpeg 合并视频+音频+字幕 → final.mp4

    Args:
        step_videos: [{"step_number": 1, "video_path": "...", "duration": 11.2}, ...]
        step_audios: ["step_01.mp3", "step_02.mp3", ...] 按步骤顺序
        subtitle_path: SRT 字幕文件路径
        output_path: 输出路径
        encoding_preset: ffmpeg preset

    Returns:
        最终 MP4 路径
    """
    if not _FFMPEG_PATH:
        logger.error("compose_from_steps 需要 FFmpeg，请确认已安装")
        return None

    if not step_videos:
        logger.error("步骤视频列表为空")
        return None

    try:
        timestamp = get_timestamp()
        if output_path is None:
            output_path = os.path.join(OUTPUT_VIDEO_DIR, f"final_{timestamp}.mp4")
        ensure_dirs()

        # 临时工作目录
        tmp_dir = os.path.join(OUTPUT_VIDEO_DIR, f"_tmp_{timestamp}")
        os.makedirs(tmp_dir, exist_ok=True)

        video_concat_list = os.path.join(tmp_dir, "video_concat.txt")
        combined_video = os.path.join(tmp_dir, "combined.mp4")

        # ================================================================
        # 第1步：拼接所有步骤视频
        # ================================================================
        logger.info(f"拼接 {len(step_videos)} 个步骤视频...")
        with open(video_concat_list, "w", encoding="utf-8") as f:
            for sv in step_videos:
                abs_path = os.path.abspath(sv["video_path"]).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

        # 检测步骤视频是否含音频
        first_video = step_videos[0]["video_path"]
        videos_have_audio = _has_audio_stream(first_video)

        if videos_have_audio:
            # 视频已含音频，直接拼接（含音视频流）
            cmd_concat = [
                _FFMPEG_PATH, "-y", "-hide_banner", "-loglevel", "warning",
                "-f", "concat", "-safe", "0",
                "-i", video_concat_list,
                "-c", "copy",
                combined_video,
            ]
            result = subprocess.run(cmd_concat, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                # -c copy 可能因编码差异失败，降级重编码
                logger.warning(f"直接拼接失败，尝试重编码: {result.stderr[-200:]}")
                cmd_concat = [
                    _FFMPEG_PATH, "-y", "-hide_banner", "-loglevel", "warning",
                    "-f", "concat", "-safe", "0",
                    "-i", video_concat_list,
                    "-c:v", "libx264", "-preset", encoding_preset, "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    combined_video,
                ]
                result = subprocess.run(cmd_concat, capture_output=True, text=True, timeout=600)
                if result.returncode != 0:
                    logger.error(f"视频拼接失败: {result.stderr[-300:]}")
                    return None
            logger.info(f"视频拼接完成(含音频): {combined_video}")

            # 烧录字幕
            final = compose_video(
                animation_path=combined_video,
                audio_path=None,  # 视频已含音频
                subtitle_path=subtitle_path,
                output_path=output_path,
                encoding_preset=encoding_preset,
            )
        else:
            # 降级：视频无音频，需要单独拼接音频
            logger.info("步骤视频无音频，使用降级方案：拼接视频+拼接音频+合并")

            silent_video = os.path.join(tmp_dir, "silent.mp4")
            cmd_concat_video = [
                _FFMPEG_PATH, "-y", "-hide_banner", "-loglevel", "warning",
                "-f", "concat", "-safe", "0",
                "-i", video_concat_list,
                "-c", "copy",
                silent_video,
            ]
            result = subprocess.run(cmd_concat_video, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                logger.error(f"视频拼接失败: {result.stderr[-300:]}")
                return None
            logger.info(f"视频拼接完成(无音频): {silent_video}")

            # 拼接音频
            merged_audio = os.path.join(tmp_dir, "merged_audio.mp3")
            audio_concat_list = os.path.join(tmp_dir, "audio_concat.txt")
            if step_audios:
                with open(audio_concat_list, "w", encoding="utf-8") as f:
                    for ap in step_audios:
                        abs_path = os.path.abspath(ap).replace("\\", "/")
                        f.write(f"file '{abs_path}'\n")

                cmd_concat_audio = [
                    _FFMPEG_PATH, "-y", "-hide_banner", "-loglevel", "warning",
                    "-f", "concat", "-safe", "0",
                    "-i", audio_concat_list,
                    "-c", "copy",
                    merged_audio,
                ]
                result = subprocess.run(cmd_concat_audio, capture_output=True, text=True, timeout=120)
                if result.returncode != 0:
                    logger.error(f"音频拼接失败: {result.stderr[-300:]}")
                    return None
                logger.info(f"音频拼接完成: {merged_audio}")
            else:
                merged_audio = None

            # 合并视频+音频+字幕
            final = compose_video(
                animation_path=silent_video,
                audio_path=merged_audio,
                subtitle_path=subtitle_path,
                output_path=output_path,
                encoding_preset=encoding_preset,
            )

        # 清理临时文件
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

        return final

    except Exception as e:
        logger.error(f"步骤拼接合成异常: {e}")
        return None
