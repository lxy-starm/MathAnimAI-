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
# 核心合成函数（ffmpeg 版本）
# ================================================================
def compose_video(
    animation_path: str,
    audio_path: str,
    subtitle_path: str = None,
    title: str = "",
    output_path: str = None,
    add_intro: bool = False,
    add_outro: bool = False,
    encoding_preset: str = "fast",
) -> Optional[str]:
    """
    合成完整教学视频：动画 + 音频 + 字幕

    使用 ffmpeg 直接处理，比 moviepy 快 10-100 倍。
    -subtitles 滤镜原生烧录字幕
    -shortest 自动裁剪视频以匹配最短流（通常是音频）
    -preset fast 加速编码

    Args:
        animation_path: Manim 渲染的无声动画视频路径
        audio_path: 人声音频路径
        subtitle_path: SRT 字幕文件路径
        title: 视频标题（当前版本暂不添加片头）
        output_path: 输出路径
        add_intro: 是否添加片头（ffmpeg 模式暂不支持，保留参数兼容）
        add_outro: 是否添加片尾（ffmpeg 模式暂不支持，保留参数兼容）
        encoding_preset: ffmpeg preset (fast/medium/ultrafast)，默认 fast

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

        has_audio = audio_path and os.path.exists(audio_path)
        has_subtitle = subtitle_path and os.path.exists(subtitle_path)

        logger.info(
            f"开始视频合成 (ffmpeg): animation={animation_path}, "
            f"audio={'有' if has_audio else '无'}, "
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

        # 输入：音频（如果有）
        if has_audio:
            cmd.extend(["-i", audio_path])

        # 视频滤镜：字幕烧录
        video_filters = []
        if has_subtitle:
            # ffmpeg subtitles 滤镜需要绝对路径
            abs_subtitle = os.path.abspath(subtitle_path)
            # Windows 路径在 subtitles 滤镜中需要转义冒号
            escaped_sub = abs_subtitle.replace("\\", "/").replace(":", "\\:")
            style = _build_subtitle_style()
            sub_filter = f"subtitles='{escaped_sub}':force_style='{style}'"
            video_filters.append(sub_filter)
            logger.info(f"字幕文件: {abs_subtitle}")

        # 视频编码参数
        if video_filters:
            cmd.extend(["-vf", ",".join(video_filters)])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", encoding_preset,
            "-crf", "23",             # 质量：18=接近无损，23=默认，28=较低
            "-pix_fmt", "yuv420p",    # 兼容所有播放器
        ])

        # 音频编码参数
        if has_audio:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "128k",
            ])
        else:
            cmd.extend(["-an"])  # 无音频

        # -shortest：以最短的流（通常是音频）为准裁剪视频
        # 这解决了"视频比音频长"导致的不同步问题
        cmd.append("-shortest")

        # 输出选项
        cmd.extend([
            "-movflags", "+faststart",  # Web 渐进式加载
            "-y",                        # 覆盖输出
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
            timeout=600,  # 10分钟超时
        )

        if result.returncode != 0:
            stderr_tail = result.stderr.strip()[-500:] if result.stderr else ""
            logger.error(f"ffmpeg 合成失败 (returncode={result.returncode}):\n{stderr_tail}")

            # 如果字幕滤镜失败，尝试无字幕合成
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
