"""
测试脚本：验证音画同步修复效果
使用内置 demo 脚本（无需 LLM），测试完整流水线
"""
import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows UTF-8
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(stream=sys.stdout)],
)

print("=" * 60)
print("音画同步修复测试")
print("=" * 60)

# 运行完整流水线 — 使用简单的应用题
from main import run_full_pipeline

result = run_full_pipeline(
    problem_text="小明有12个苹果，小红给了他8个，小明一共有多少个苹果？",
    problem_type="应用题",
    grade_level="小学",
)

print()
print("=" * 60)
print("测试结果:")
print(f"  成功: {result['success']}")
print(f"  视频: {result['video_path']}")
print(f"  消息: {result['message']}")
print("=" * 60)

# 如果视频生成成功，检查音画同步
if result["video_path"] and os.path.exists(result["video_path"]):
    video_path = result["video_path"]
    print(f"\n检查视频音画同步: {video_path}")

    # 用 ffprobe 检查视频和音频时长
    import subprocess
    try:
        import imageio_ffmpeg
        ffprobe = imageio_ffmpeg.get_ffmpeg_exe().replace("ffmpeg", "ffprobe")
    except:
        ffprobe = "ffprobe"

    if os.path.exists(ffprobe):
        # 获取视频时长
        cmd_v = [ffprobe, "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "format=duration", "-of", "csv=p=0", video_path]
        video_dur = subprocess.run(cmd_v, capture_output=True, text=True, timeout=10)
        print(f"  视频流时长: {video_dur.stdout.strip()}s")

        # 获取音频时长
        cmd_a = [ffprobe, "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "format=duration", "-of", "csv=p=0", video_path]
        audio_dur = subprocess.run(cmd_a, capture_output=True, text=True, timeout=10)
        print(f"  音频流时长: {audio_dur.stdout.strip()}s")

        # 检查是否含音频流
        cmd_streams = [ffprobe, "-v", "error", "-show_streams", video_path]
        streams_info = subprocess.run(cmd_streams, capture_output=True, text=True, timeout=10)
        has_audio = "codec_type=audio" in streams_info.stdout
        has_video = "codec_type=video" in streams_info.stdout
        print(f"  含视频流: {has_video}")
        print(f"  含音频流: {has_audio}")

        if has_audio and has_video:
            v = float(video_dur.stdout.strip()) if video_dur.stdout.strip() else 0
            a = float(audio_dur.stdout.strip()) if audio_dur.stdout.strip() else 0
            diff = abs(v - a)
            print(f"  音视频时长差: {diff:.3f}s")
            if diff < 0.5:
                print("  [PASS] 音画同步良好！")
            else:
                print("  [WARN] 音画时长差较大，需进一步检查")
        else:
            print("  [WARN] 视频缺少音频流或视频流")
    else:
        print("  ffprobe 不可用，跳过时长检查")
else:
    print("\n[FAIL] 视频未生成")
    print(f"  消息: {result['message']}")
