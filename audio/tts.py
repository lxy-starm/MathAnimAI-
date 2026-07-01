"""
============================================================
MathAnimAI — edge-tts 语音合成模块
功能：
  1. 使用 edge-tts 的晓晓女声生成中文讲解语音
  2. 批量生成各步骤分段语音
  3. 返回音频文件路径和时长信息
============================================================
"""

import os
import sys
import asyncio
import subprocess
import logging
from typing import Optional
from pathlib import Path

from config import (
    TTS_VOICE, TTS_RATE, TTS_PITCH,
    OUTPUT_AUDIO_DIR, get_timestamp, ensure_dirs,
)

logger = logging.getLogger("MathAnimAI.TTS")


# ================================================================
# 语音生成核心函数
# ================================================================
async def generate_speech(
    text: str,
    output_path: str,
    voice: str = None,
    rate: str = None,
    pitch: str = None,
) -> Optional[dict]:
    """
    使用 edge-tts 生成单段语音

    Args:
        text: 要朗读的文本
        output_path: 输出音频文件路径（.mp3）
        voice: 语音角色，默认晓晓女声
        rate: 语速调整，如 "+10%"
        pitch: 音调调整

    Returns:
        {"path": str, "duration": float} 或 None（失败时）
    """
    try:
        import edge_tts

        voice_name = voice or TTS_VOICE
        rate_val = rate or TTS_RATE
        pitch_val = pitch or TTS_PITCH

        # 清理文本（移除特殊字符，保留标点）
        clean_text = text.strip()
        if not clean_text:
            logger.warning("TTS文本为空，跳过")
            return None

        logger.info(f"生成语音: voice={voice_name}, 文本长度={len(clean_text)}")

        # 创建 Communicate 实例
        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=voice_name,
            rate=rate_val,
            pitch=pitch_val,
        )

        # 保存音频文件
        await communicate.save(output_path)

        # 获取音频时长（使用 pydub）
        from pydub import AudioSegment
        audio = AudioSegment.from_file(output_path)
        duration = len(audio) / 1000.0  # 转换为秒

        logger.info(f"语音生成成功: {output_path}, 时长={duration:.1f}s")
        return {"path": output_path, "duration": duration}

    except ImportError:
        logger.error("edge_tts 未安装。请运行: pip install edge-tts")
        return None
    except Exception as e:
        logger.error(f"语音生成失败: {e}")
        return None


# ================================================================
# 批量生成各步骤语音
# ================================================================
async def generate_step_audios(
    steps: list[dict],
    output_dir: str = None,
    voice: str = None,
) -> list[dict]:
    """
    批量生成所有步骤的分段语音

    Args:
        steps: 步骤列表，每个步骤含 step_number, voice_text
        output_dir: 输出目录
        voice: 语音角色

    Returns:
        [{"step_number": 1, "path": "...", "duration": 2.5}, ...]
    """
    output_path = output_dir or OUTPUT_AUDIO_DIR
    ensure_dirs()

    results = []
    timestamp = get_timestamp()

    for step in steps:
        voice_text = step.get("voice_text", "")
        step_num = step.get("step_number", len(results) + 1)

        if not voice_text:
            # 如果没有配音文本，用讲解文字代替
            voice_text = step.get("text", "")
        if not voice_text:
            logger.warning(f"步骤{step_num}无配音文本，跳过")
            continue

        # 生成语音文件
        file_name = f"step_{step_num:02d}_{timestamp}.mp3"
        file_path = os.path.join(output_path, file_name)

        result = await generate_speech(
            text=voice_text,
            output_path=file_path,
            voice=voice,
        )

        if result:
            result["step_number"] = step_num
            result["voice_text"] = voice_text
            results.append(result)
        else:
            # 生成失败时返回一个占位项
            results.append({
                "step_number": step_num,
                "path": "",
                "duration": 2.0,  # 默认2秒
                "voice_text": voice_text,
            })

        # 步骤间短暂间隔，避免API限流
        await asyncio.sleep(0.3)

    logger.info(f"批量语音生成完成: 共{len(results)}段")
    return results


# ================================================================
# 合并所有步骤语音
# ================================================================
def merge_audio_segments(
    audio_files: list[str],
    output_path: str,
    crossfade: float = 0.3,
) -> Optional[str]:
    """
    合并多个音频文件为一个完整音频（使用 ffmpeg 命令行）

    Args:
        audio_files: 音频文件路径列表
        output_path: 合并后的输出路径
        crossfade: 交叉淡入淡出时长（秒）

    Returns:
        合并后的文件路径
    """
    import subprocess

    if not audio_files:
        logger.warning("无音频文件可合并")
        return None

    # 获取 ffmpeg 路径
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    try:
        if len(audio_files) == 1:
            # 只有一个文件，直接复制
            import shutil
            shutil.copy2(audio_files[0], output_path)
            logger.info(f"音频合并完成(单文件): {output_path}")
            return output_path

        # 使用 ffmpeg concat 协议合并
        # 写 concat 文件列表
        concat_file = output_path + ".concat.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for af in audio_files:
                abs_path = os.path.abspath(af).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

        cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        # 清理临时文件
        try:
            os.unlink(concat_file)
        except Exception:
            pass

        if result.returncode != 0:
            logger.error(f"音频合并失败: {result.stderr[:300]}")
            return None

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"音频合并完成: {output_path}")
            return output_path
        else:
            return None

    except Exception as e:
        logger.error(f"音频合并失败: {e}")
        return None


# ================================================================
# 同步封装（用于在同步代码中调用异步函数）
# ================================================================
def tts_sync(text: str, output_path: str = None, voice: str = None) -> Optional[dict]:
    """
    同步 TTS 语音生成

    使用 Python API 直接调用 edge-tts，避免子进程环境问题。
    自动处理 asyncio 事件循环冲突。

    Args:
        text: 朗读文本
        output_path: 输出路径
        voice: 语音角色

    Returns:
        {"path": str, "duration": float} 或 None
    """
    if output_path is None:
        timestamp = get_timestamp()
        output_path = os.path.join(OUTPUT_AUDIO_DIR, f"tts_{timestamp}.mp3")

    voice_name = voice or TTS_VOICE

    clean_text = text.strip()
    if not clean_text:
        logger.warning("TTS文本为空，跳过")
        return None

    # 确保输出目录为绝对路径并存在
    abs_output = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    logger.info(f"生成语音: voice={voice_name}, 文本长度={len(clean_text)}")

    # ================================================================
    # 方式 1：asyncio.run() 直接调用 Python API
    # ================================================================
    gen_success = False
    try:
        import edge_tts

        async def _gen():
            communicate = edge_tts.Communicate(text=clean_text, voice=voice_name)
            await communicate.save(abs_output)

        # 检查是否有正在运行的事件循环
        try:
            loop = asyncio.get_running_loop()
            # 已有事件循环（Gradio 异步上下文），用独立线程执行
            import threading
            gen_error = [None]

            def _run_in_thread():
                try:
                    asyncio.run(_gen())
                except Exception as e:
                    gen_error[0] = e

            thread = threading.Thread(target=_run_in_thread)
            thread.start()
            thread.join(timeout=120)

            if gen_error[0]:
                raise gen_error[0]
        except RuntimeError:
            # 无运行中的事件循环，直接调用
            asyncio.run(_gen())

        gen_success = True
    except Exception as e:
        logger.warning(f"TTS API 调用失败: {e}")
        gen_success = False

    # ================================================================
    # 检查输出 + 获取时长（pydub 可能因无 ffmpeg 而失败，容忍）
    # ================================================================
    if gen_success and os.path.exists(abs_output) and os.path.getsize(abs_output) > 0:
        duration = _estimate_duration(clean_text, abs_output)
        logger.info(f"语音生成成功: {abs_output}, 时长={duration:.1f}s")
        return {"path": abs_output, "duration": duration}

    # ================================================================
    # 方式 2：子进程回退
    # ================================================================
    logger.info("尝试子进程回退方案...")
    return _tts_subprocess_fallback(clean_text, abs_output, voice_name)


def _estimate_duration(text: str, audio_path: str) -> float:
    """估算音频时长，优先使用 pydub，失败则按字数估算"""
    # 尝试 pydub
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

    try:
        from pydub import AudioSegment
        # 设置 ffmpeg 路径
        try:
            import imageio_ffmpeg
            AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0
    except Exception:
        # pydub 不可用，按中文字数估算（约4字/秒）
        estimated = len(text) / 4.0
        return max(estimated, 1.0)


def _tts_subprocess_fallback(text: str, output_path: str, voice: str) -> Optional[dict]:
    """子进程回退方案：使用 edge-tts CLI 命令"""
    import subprocess

    # 写入临时文件避免命令行编码问题
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as f:
        f.write(text)
        text_file = f.name

    try:
        cmd = [
            sys.executable, "-m", "edge_tts",
            "--voice", voice,
            "--file", text_file,
            "--write-media", output_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            logger.error(f"TTS子进程失败: {result.stderr[:300]}")
            return None

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(output_path)
            duration = len(audio) / 1000.0
            logger.info(f"语音生成成功(子进程): {output_path}, 时长={duration:.1f}s")
            return {"path": output_path, "duration": duration}

        return None
    except Exception as e:
        logger.error(f"TTS子进程回退也失败: {e}")
        return None
    finally:
        try:
            os.unlink(text_file)
        except Exception:
            pass


def generate_all_audios_sync(
    steps: list[dict],
    output_dir: str = None,
    voice: str = None,
) -> list[dict]:
    """
    同步批量生成，逐个调用 tts_sync 避免事件循环问题
    """
    output_path = output_dir or OUTPUT_AUDIO_DIR
    ensure_dirs()

    results = []
    timestamp = get_timestamp()

    for step in steps:
        voice_text = step.get("voice_text", "")
        step_num = step.get("step_number", len(results) + 1)

        if not voice_text:
            voice_text = step.get("text", "")
        if not voice_text:
            logger.warning(f"步骤{step_num}无配音文本，跳过")
            results.append({
                "step_number": step_num,
                "path": "",
                "duration": 2.0,
                "voice_text": "",
            })
            continue

        file_name = f"step_{step_num:02d}_{timestamp}.mp3"
        file_path = os.path.join(output_path, file_name)

        result = tts_sync(text=voice_text, output_path=file_path, voice=voice)
        if result:
            result["step_number"] = step_num
            result["voice_text"] = voice_text
            results.append(result)
        else:
            results.append({
                "step_number": step_num,
                "path": "",
                "duration": 2.0,
                "voice_text": voice_text,
            })

    logger.info(f"批量语音生成完成: 共{len(results)}段")
    return results
