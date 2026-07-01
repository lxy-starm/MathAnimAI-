"""
============================================================
MathAnimAI — 字幕自动生成模块
功能：
  1. 根据每个步骤的音频时长自动计算时间轴
  2. 生成标准 SRT 字幕文件
  3. 自动对齐动画步骤
============================================================
"""

import os
import logging
from typing import Optional

from config import OUTPUT_SUBTITLE_DIR, get_timestamp, ensure_dirs

logger = logging.getLogger("MathAnimAI.Subtitle")


# ================================================================
# SRT格式生成
# ================================================================
def seconds_to_srt_time(seconds: float) -> str:
    """
    将秒数转换为SRT时间格式 HH:MM:SS,mmm

    Args:
        seconds: 秒数

    Returns:
        SRT时间字符串，如 "00:01:23,456"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt_from_steps(
    step_audios: list[dict],
    extra_padding: float = 0.2,
) -> str:
    """
    根据步骤音频时长生成SRT字幕内容

    Args:
        step_audios: 步骤音频列表 [{"step_number": 1, "duration": 2.5, "voice_text": "..."}, ...]
        extra_padding: 额外时间缓冲（秒），避免字幕播完太仓促

    Returns:
        SRT格式字符串
    """
    srt_lines = []
    current_time = 0.0
    subtitle_index = 1

    for audio in step_audios:
        duration = audio.get("duration", 2.0)
        step_num = audio.get("step_number", subtitle_index)
        text = audio.get("voice_text", "")

        if not text:
            continue

        # 计算开始和结束时间
        start_time = current_time
        end_time = start_time + duration + extra_padding

        # 构建SRT条目
        srt_lines.append(str(subtitle_index))
        srt_lines.append(
            f"{seconds_to_srt_time(start_time)} --> {seconds_to_srt_time(end_time)}"
        )
        srt_lines.append(text)
        srt_lines.append("")  # 空行分隔

        # 更新时间和索引
        current_time = end_time
        subtitle_index += 1

    return "\n".join(srt_lines)


def save_srt_file(
    step_audios: list[dict],
    output_path: str = None,
) -> Optional[str]:
    """
    生成并保存SRT字幕文件

    Args:
        step_audios: 步骤音频列表
        output_path: 输出文件路径，默认自动生成

    Returns:
        SRT文件路径
    """
    if output_path is None:
        timestamp = get_timestamp()
        output_path = os.path.join(OUTPUT_SUBTITLE_DIR, f"subtitle_{timestamp}.srt")

    ensure_dirs()

    try:
        srt_content = generate_srt_from_steps(step_audios)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        logger.info(f"字幕文件已保存: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"字幕生成失败: {e}")
        return None


# ================================================================
# 手动时间轴生成（用于无TTS情况）
# ================================================================
def generate_srt_manual(
    texts: list[str],
    durations: list[float],
    output_path: str = None,
) -> Optional[str]:
    """
    手动指定文本和时长生成字幕

    Args:
        texts: 每条字幕的文本
        durations: 每条字幕的时长（秒）

    Returns:
        SRT文件路径
    """
    if len(texts) != len(durations):
        logger.error("文本和时长列表长度不一致")
        return None

    # 构造step_audios格式
    step_audios = [
        {"step_number": i + 1, "duration": d, "voice_text": t}
        for i, (t, d) in enumerate(zip(texts, durations))
    ]

    return save_srt_file(step_audios, output_path)


# ================================================================
# 字幕附加到视频的配置文件生成
# ================================================================
def get_subtitle_texts(step_audios: list[dict]) -> list[str]:
    """
    从步骤音频列表中提取所有字幕文本（供moviepy字幕渲染使用）

    Returns:
        字幕文本列表
    """
    return [a.get("voice_text", a.get("text", "")) for a in step_audios]


def get_subtitle_timestamps(step_audios: list[dict]) -> list[tuple[float, float]]:
    """
    获取每条字幕的开始和结束时间

    Returns:
        [(start_time, end_time), ...]
    """
    timestamps = []
    current_time = 0.0

    for audio in step_audios:
        duration = audio.get("duration", 2.0)
        timestamps.append((current_time, current_time + duration))
        current_time += duration

    return timestamps
