"""
============================================================
MathAnimAI — 视频合成模块 (moviepy)
功能：
  1. 加载Manim渲染的无声动画
  2. 叠加合成人声音频
  3. SRT字幕渲染在画面底部半透明区域
  4. 自动添加片头标题、片尾总结
  5. 输出完整MP4文件
============================================================
"""

import os
import re
import logging
from typing import Optional

from config import (
    OUTPUT_VIDEO_DIR, INTRO_DURATION, OUTRO_DURATION,
    SUBTITLE_FONT_SIZE, SUBTITLE_BG_OPACITY,
    Colors, FONT_FAMILY, get_timestamp, ensure_dirs,
    RESOLUTION_WIDTH, RESOLUTION_HEIGHT,
)

logger = logging.getLogger("MathAnimAI.Composer")

# ================================================================
# 字体检测
# ================================================================
# 检测可用的中文字体（用于 moviepy/Pillow 渲染）
_available_font = None
try:
    from PIL import ImageFont
    # 尝试常见中文字体（按优先级排序）
    _candidate_fonts = [
        "C:/Windows/Fonts/msyh.ttc",          # Microsoft YaHei
        "C:/Windows/Fonts/msyhbd.ttc",        # Microsoft YaHei Bold
        "C:/Windows/Fonts/simhei.ttf",        # 黑体
        "C:/Windows/Fonts/simsun.ttc",        # 宋体
        "C:/Windows/Fonts/simkai.ttf",        # 楷体
        "C:/Windows/Fonts/STKAITI.TTF",       # 华文楷体
        "C:/Windows/Fonts/Deng.ttf",          # DengXian
        "C:/Windows/Fonts/Dengb.ttf",         # DengXian Bold
        "C:/Windows/Fonts/STFANGSO.TTF",      # 华文仿宋
    ]
    for _f in _candidate_fonts:
        if os.path.exists(_f):
            _available_font = _f
            logger.info(f"使用字幕字体: {_f}")
            break
    if _available_font is None:
        # 回退：扫描 Windows Fonts 目录找任意 .ttf
        for _f in os.listdir("C:/Windows/Fonts"):
            if _f.lower().endswith(('.ttf', '.ttc')):
                _available_font = os.path.join("C:/Windows/Fonts", _f)
                logger.warning(f"未找到中文字体，回退使用: {_available_font}")
                break
except Exception:
    _available_font = None

if _available_font is None:
    _available_font = "Microsoft-YaHei"  # Pillow 可能通过名称找到
    logger.warning("无法检测系统字体，字幕渲染可能失败")


# ================================================================
# 完整视频合成
# ================================================================
def compose_video(
    animation_path: str,
    audio_path: str,
    subtitle_path: str = None,
    title: str = "",
    output_path: str = None,
    add_intro: bool = True,
    add_outro: bool = True,
) -> Optional[str]:
    """
    合成完整教学视频：动画 + 音频 + 字幕 + 片头片尾

    Args:
        animation_path: Manim渲染的无声动画视频路径
        audio_path: 人声音频路径
        subtitle_path: SRT字幕文件路径
        title: 视频标题（用于片头）
        output_path: 输出路径
        add_intro: 是否添加片头
        add_outro: 是否添加片尾

    Returns:
        合成的MP4视频路径
    """
    try:
        from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip
        from moviepy import TextClip, ColorClip, vfx

        logger.info(f"开始视频合成: animation={animation_path}")

        # 加载动画视频
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

            # 音画同步策略：
            # - 音频 ≤ 视频：正常，视频末尾保持静音
            # - 音频 > 视频：扩展视频（冻结最后一帧）+ 完整保留音频
            if audio.duration > video_duration + 0.3:
                gap = audio.duration - video_duration
                logger.info(f"音频比视频长 {gap:.1f}s，扩展视频（冻结最后一帧）")
                video = _extend_video_with_freeze(video, audio.duration)
            elif audio.duration < video_duration:
                # 视频末尾保留静音即可（moviepy自动处理）
                pass

            video = video.with_audio(audio)
        else:
            logger.warning("无音频文件，视频将无声")

        # 添加字幕
        if subtitle_path and os.path.exists(subtitle_path):
            video = _add_subtitles_to_video(video, subtitle_path, width, height)
        else:
            logger.info("无字幕文件")

        # 构建片头
        segments = []
        if add_intro and title:
            intro = _create_intro_clip(title, width, height, INTRO_DURATION)
            segments.append(intro)

        segments.append(video)

        # 构建片尾
        if add_outro:
            outro = _create_outro_clip(width, height, OUTRO_DURATION)
            segments.append(outro)

        # 拼接所有片段
        if len(segments) > 1:
            final_video = _concatenate_clips(segments)
        else:
            final_video = video

        # 输出
        if output_path is None:
            timestamp = get_timestamp()
            output_path = os.path.join(OUTPUT_VIDEO_DIR, f"final_{timestamp}.mp4")

        ensure_dirs()

        logger.info(f"渲染输出: {output_path}")
        final_video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            logger=None,  # 禁用moviepy日志
        )

        logger.info(f"视频合成完成: {output_path}")
        return output_path

    except ImportError:
        logger.error("moviepy 未安装。请运行: pip install moviepy")
        # 降级返回原始动画视频
        return animation_path
    except Exception as e:
        logger.error(f"视频合成失败: {e}")
        return animation_path  # 降级


# ================================================================
# 字幕添加
# ================================================================
def _add_subtitles_to_video(
    video,
    subtitle_path: str,
    width: int,
    height: int,
) -> "CompositeVideoClip":
    """
    将SRT字幕渲染到视频底部

    Args:
        video: VideoFileClip
        subtitle_path: SRT文件路径
        width: 视频宽度
        height: 视频高度

    Returns:
        叠加字幕后的CompositeVideoClip
    """
    try:
        from moviepy import CompositeVideoClip, TextClip
        import re

        # 解析SRT文件
        subtitles = _parse_srt(subtitle_path)
        if not subtitles:
            logger.warning("SRT解析为空，跳过字幕")
            return video

        # 为每条字幕创建TextClip
        _font = _available_font or "Arial"
        subtitle_clips = []
        for start, end, text in subtitles:
            # 字幕文本过长时自动换行
            if len(text) > 30:
                # 约每25字插入换行
                wrapped_lines = []
                for i in range(0, len(text), 25):
                    wrapped_lines.append(text[i:i+25])
                text = "\n".join(wrapped_lines)

            # 创建字幕文本
            txt_clip = TextClip(
                text=text,
                font=_font,
                font_size=SUBTITLE_FONT_SIZE,
                color="white",
                stroke_color="black",
                stroke_width=2,
                size=(int(width * 0.85), None),
                method="caption",
                text_align="center",
            )

            # 添加半透明背景
            bg_clip = _create_subtitle_background(
                txt_clip, width, height, SUBTITLE_BG_OPACITY
            )

            # 组合字幕
            subtitle_group = CompositeVideoClip(
                [bg_clip, txt_clip.with_position("center")]
            )

            # 设置显示时间
            subtitle_group = subtitle_group.with_start(start).with_end(end)
            subtitle_group = subtitle_group.with_position(("center", int(height * 0.82)))
            subtitle_clips.append(subtitle_group)

        # 叠加到视频上
        result = CompositeVideoClip([video] + subtitle_clips)
        return result

    except Exception as e:
        logger.warning(f"字幕添加失败: {e}，返回无字幕视频")
        return video


def _parse_srt(srt_path: str) -> list[tuple[float, float, str]]:
    """解析SRT文件"""
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
    """SRT时间转秒"""
    import re
    match = re.match(r"(\d+):(\d+):(\d+)[.,](\d+)", time_str)
    if match:
        h, m, s, ms = map(int, match.groups())
        return h * 3600 + m * 60 + s + ms / 1000
    return 0.0


def _create_subtitle_background(txt_clip, width: int, height: int, opacity: float):
    """创建字幕的半透明背景"""
    from moviepy import ColorClip
    bg_w = max(1, int(txt_clip.w * 1.05))
    bg_h = max(1, int(txt_clip.h * 1.1))
    bg = ColorClip(
        size=(bg_w, bg_h),
        color=(0, 0, 0),
    )
    bg = bg.with_opacity(opacity)
    return bg


# ================================================================
# 片头片尾生成
# ================================================================
def _create_intro_clip(
    title: str,
    width: int,
    height: int,
    duration: float,
):
    """创建片头：标题 + 柔和背景"""
    from moviepy import TextClip, ColorClip, CompositeVideoClip

    # 背景
    bg = ColorClip(size=(width, height), color=(52, 152, 219))
    bg = bg.with_duration(duration)

    # 标题文字
    title_text = TextClip(
        text=title,
        font=_available_font,
        font_size=48,
        color="white",
        size=(int(width * 0.8), None),
        method="caption",
        text_align="center",
    )
    title_text = title_text.with_position("center").with_duration(duration)

    # 副标题
    subtitle = TextClip(
        text="数学动画教学",
        font=_available_font,
        font_size=28,
        color="#DDDDDD",
        size=(int(width * 0.8), None),
        method="caption",
        text_align="center",
    )
    subtitle = subtitle.with_position(("center", int(height * 0.65))).with_duration(duration)

    intro = CompositeVideoClip([bg, title_text, subtitle])
    return intro


def _create_outro_clip(width: int, height: int, duration: float):
    """创建片尾"""
    from moviepy import TextClip, ColorClip, CompositeVideoClip

    bg = ColorClip(size=(width, height), color=(44, 62, 80))
    bg = bg.with_duration(duration)

    text = TextClip(
        text="感谢观看\nMathAnimAI 呈现",
        font=_available_font,
        font_size=36,
        color="white",
        size=(int(width * 0.8), None),
        method="caption",
        text_align="center",
    )
    text = text.with_position("center").with_duration(duration)

    return CompositeVideoClip([bg, text])


def _concatenate_clips(clips: list):
    """拼接多个视频片段"""
    from moviepy import concatenate_videoclips
    return concatenate_videoclips(clips, method="compose")


def _extend_video_with_freeze(video, target_duration: float):
    """
    当音频比视频长时，冻结视频最后一帧来扩展视频时长。

    使用 moviepy 的 freeze 功能：截取最后一帧作为静态图片，
    然后拼接到视频末尾，确保音频不会在视频结束后继续播放。

    Args:
        video: VideoFileClip
        target_duration: 目标总时长（秒）

    Returns:
        扩展后的 VideoClip
    """
    from moviepy import concatenate_videoclips

    gap = target_duration - video.duration
    if gap <= 0.1:
        return video

    try:
        # 方法1: 使用 to_ImageClip 截取最后一帧
        last_frame = video.to_ImageClip(t=video.duration - 0.05, duration=gap)
        # 加一点淡出效果避免突兀
        last_frame = last_frame.with_effects([vfx.FadeOut(0.5)])
        extended = concatenate_videoclips([video, last_frame], method="compose")
        logger.info(f"视频已扩展: {video.duration:.1f}s → {extended.duration:.1f}s")
        return extended
    except Exception as e:
        logger.warning(f"to_ImageClip 方法失败 ({e})，尝试 freeze 方法")
        try:
            # 方法2: 使用 time_mirror / freeze 技巧
            # 创建一个简单的静态延长
            extended = video.with_duration(target_duration)
            return extended
        except Exception as e2:
            logger.warning(f"扩展视频失败 ({e2})，保持原视频长度")
            return video
