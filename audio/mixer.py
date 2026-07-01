"""
============================================================
MathAnimAI — 音频混合模块
功能：
  1. 人声语音 + 低音量背景音乐混合
  2. 背景音乐自动循环匹配人声时长
  3. 输出混音后的成品音频
============================================================
"""

import os
import logging
from typing import Optional

from config import OUTPUT_AUDIO_DIR, get_timestamp

logger = logging.getLogger("MathAnimAI.Mixer")


# ================================================================
# 音频混合核心函数
# ================================================================
def mix_audio_with_bgm(
    voice_path: str,
    bgm_path: str = None,
    output_path: str = None,
    voice_volume: float = 1.0,
    bgm_volume: float = 0.15,  # 背景音乐低音量
    fade_in: float = 1.0,
    fade_out: float = 2.0,
) -> Optional[str]:
    """
    将人声语音与背景音乐混合

    Args:
        voice_path: 人声文件路径
        bgm_path: 背景音乐路径（可选的轻柔BGM）
        output_path: 输出路径
        voice_volume: 人声音量（0-1）
        bgm_volume: 背景音乐音量（0-1），默认很低
        fade_in: 淡入时长
        fade_out: 淡出时长

    Returns:
        混音后文件路径
    """
    try:
        from pydub import AudioSegment

        # 加载人声
        if not voice_path or not os.path.exists(voice_path):
            logger.warning("人声文件不存在")
            return None

        voice = AudioSegment.from_file(voice_path)
        # 调整人声音量：pydub 的 + 和 - 运算符以 dB 为单位增减音量
        # voice_volume=1.0 时不调整，小于1.0时按比例降低
        if voice_volume != 1.0:
            db_change = (voice_volume - 1.0) * 10  # 将比例转为dB变化
            voice = voice + db_change

        # 如果提供了背景音乐，混合
        if bgm_path and os.path.exists(bgm_path):
            bgm = AudioSegment.from_file(bgm_path)
            # 降低背景音乐音量
            bgm = bgm - int((1 - bgm_volume) * 30)  # 降低约15dB

            # 如果背景音乐比人声短，循环播放
            voice_duration = len(voice)
            bgm_duration = len(bgm)
            if bgm_duration < voice_duration:
                repeat_times = voice_duration // bgm_duration + 1
                bgm = bgm * repeat_times
                logger.debug(f"BGM循环{repeat_times}次以匹配人声时长")

            # 截取与人声相同长度
            bgm = bgm[:voice_duration]

            # 淡入淡出
            bgm = bgm.fade_in(int(fade_in * 1000)).fade_out(int(fade_out * 1000))

            # 叠加混音
            combined = voice.overlay(bgm)
            logger.info(f"人声+背景音乐混合完成")
        else:
            # 无背景音乐，直接使用人声
            combined = voice
            logger.info("无背景音乐，直接使用人声")

        # 输出
        if output_path is None:
            timestamp = get_timestamp()
            output_path = os.path.join(OUTPUT_AUDIO_DIR, f"mixed_{timestamp}.mp3")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        combined.export(output_path, format="mp3")

        logger.info(f"混音完成: {output_path}, 时长={len(combined)/1000:.1f}s")
        return output_path

    except ImportError:
        logger.error("pydub 未安装。请运行: pip install pydub")
        # 降级：直接返回人声文件
        return voice_path
    except Exception as e:
        logger.error(f"音频混合失败: {e}")
        # 降级：返回人声文件
        return voice_path


# ================================================================
# 生成静音片段
# ================================================================
def generate_silent_audio(duration: float, output_path: str = None) -> Optional[str]:
    """
    生成纯静音音频

    Args:
        duration: 时长（秒）
        output_path: 输出路径

    Returns:
        音频文件路径
    """
    try:
        from pydub import AudioSegment

        silence = AudioSegment.silent(duration=int(duration * 1000))

        if output_path is None:
            timestamp = get_timestamp()
            output_path = os.path.join(OUTPUT_AUDIO_DIR, f"silence_{timestamp}.mp3")

        silence.export(output_path, format="mp3")
        return output_path

    except ImportError:
        logger.error("pydub 未安装")
        return None
    except Exception as e:
        logger.error(f"静音生成失败: {e}")
        return None


# ================================================================
# 批量音频拼接
# ================================================================
def concatenate_audio_files(
    audio_paths: list[str],
    output_path: str = None,
    gaps: list[float] = None,
) -> Optional[str]:
    """
    按顺序拼接多个音频文件

    Args:
        audio_paths: 音频文件路径列表
        output_path: 输出路径
        gaps: 各段之间的间隔（秒），None表示无间隔

    Returns:
        拼接后的文件路径
    """
    try:
        from pydub import AudioSegment

        if not audio_paths:
            return None

        combined = AudioSegment.empty()

        for i, path in enumerate(audio_paths):
            if not os.path.exists(path):
                logger.warning(f"音频不存在: {path}")
                continue

            segment = AudioSegment.from_file(path)
            combined += segment

            # 添加间隔
            if gaps and i < len(gaps):
                gap_ms = int(gaps[i] * 1000)
                combined += AudioSegment.silent(duration=gap_ms)

        if output_path is None:
            timestamp = get_timestamp()
            output_path = os.path.join(OUTPUT_AUDIO_DIR, f"concat_{timestamp}.mp3")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        combined.export(output_path, format="mp3")
        logger.info(f"音频拼接完成: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"音频拼接失败: {e}")
        return None
