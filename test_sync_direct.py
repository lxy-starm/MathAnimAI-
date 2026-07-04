"""
直接测试核心音画同步流水线（绕过数据库）
测试：TTS生成 → Manim渲染(add_sound嵌入音频) → 视频合成
"""
import sys
import os
import io
import time
import logging
import tempfile

# Windows UTF-8
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 设置输出目录到临时目录（避免沙箱阻止）
import config
_tmp_output = tempfile.mkdtemp(prefix="mathanim_test_")
config.OUTPUT_DIR = _tmp_output
config.OUTPUT_VIDEO_DIR = os.path.join(_tmp_output, "videos")
config.OUTPUT_AUDIO_DIR = os.path.join(_tmp_output, "audio")
config.OUTPUT_SUBTITLE_DIR = os.path.join(_tmp_output, "subtitles")
config.CACHE_DIR = os.path.join(_tmp_output, "cache")
config.DB_PATH = os.path.join(_tmp_output, "history.db")
for d in [config.OUTPUT_DIR, config.CACHE_DIR, config.OUTPUT_VIDEO_DIR, config.OUTPUT_AUDIO_DIR, config.OUTPUT_SUBTITLE_DIR]:
    os.makedirs(d, exist_ok=True)

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(stream=sys.stdout)],
)
logger = logging.getLogger("TestSync")

print("=" * 60)
print("核心音画同步测试（绕过数据库）")
print(f"输出目录: {_tmp_output}")
print("=" * 60)

# ================================================================
# 1. 生成动画脚本（使用内置 demo）
# ================================================================
print("\n[1] 生成动画脚本...")
from main import _get_demo_script
from parser.schema import AnimationType, StepPosition, Step, AnimationSettings
import datetime

problem_text = "小明有12个苹果，小红给了他8个，小明一共有多少个苹果？"

# 手动构建一个简单的脚本（跳过 LLM）
from parser.schema import ProblemScript, ProblemType
steps = [
    Step(
        step_number=1,
        title="审题",
        text="小明有12个苹果，小红给了他8个",
        animation_type=AnimationType.TEXT_SLIDE_IN,
        position=StepPosition.CENTER,
        voice_text="我们来看这道题。小明有12个苹果，小红给了他8个。",
    ),
    Step(
        step_number=2,
        title="列式",
        text="12 + 8 = ?",
        animation_type=AnimationType.TEXT_SLIDE_IN,
        position=StepPosition.CENTER,
        voice_text="我们列出算式：12加8等于多少？",
    ),
    Step(
        step_number=3,
        title="计算",
        text="12 + 8 = 20",
        animation_type=AnimationType.HIGHLIGHT,
        position=StepPosition.CENTER,
        voice_text="计算结果：12加8等于20。",
    ),
    Step(
        step_number=4,
        title="答案",
        text="答：小明一共有20个苹果",
        animation_type=AnimationType.TEXT_SLIDE_IN,
        position=StepPosition.CENTER,
        voice_text="所以小明一共有20个苹果。",
    ),
]

script = ProblemScript(
    problem_type="word_problem",
    grade_level="小学",
    problem_text=problem_text,
    final_answer="20个苹果",
    settings=AnimationSettings(),
    steps=steps,
    created_at=datetime.datetime.now().isoformat(),
    model_used="测试脚本",
)
print(f"  脚本生成完成: {len(script.steps)} 步骤")

# ================================================================
# 2. TTS 语音生成（带 WordBoundary 同步点）
# ================================================================
print("\n[2] TTS 语音生成...")
from audio.tts import generate_all_audios_sync

steps_data = [
    {
        "step_number": s.step_number,
        "voice_text": s.voice_text or s.text,
        "text": s.text,
    }
    for s in script.steps
]

step_audios = generate_all_audios_sync(steps_data)
print(f"  TTS 完成: {len(step_audios)} 段")

step_audio_durations = {}
step_audio_paths = {}
for a in step_audios:
    if a.get("step_number") and a.get("duration"):
        step_audio_durations[a["step_number"]] = a["duration"]
    if a.get("step_number") and a.get("path"):
        step_audio_paths[a["step_number"]] = a["path"]

print(f"  音频时长: {step_audio_durations}")
print(f"  音频路径: {step_audio_paths}")

# ================================================================
# 3. Manim 渲染（add_sound 嵌入音频 + end_scene_with_audio 同步）
# ================================================================
print("\n[3] Manim 动画渲染（每步独立模式）...")
from animation.builder import build_and_render_per_step

step_videos = build_and_render_per_step(
    script=script,
    audio_durations=step_audio_durations,
    hd=True,
    audio_paths=step_audio_paths,
)
print(f"  渲染完成: {len(step_videos)}/{len(script.steps)} 步骤视频")
for sv in step_videos:
    print(f"    步骤 {sv['step_number']}: {sv['video_path']} ({sv.get('duration', 0):.1f}s)")

# ================================================================
# 4. 视频合成
# ================================================================
print("\n[4] 视频合成...")
from video.composer import compose_from_steps, _has_audio_stream

audio_paths_list = [
    step_audio_paths.get(sv["step_number"], "")
    for sv in step_videos
    if step_audio_paths.get(sv["step_number"])
]

# 生成字幕
from audio.subtitle import save_srt_file
subtitle_path = save_srt_file(step_audios, start_offset=1.5, step_gap=0.3)
print(f"  字幕: {subtitle_path}")

final_video = compose_from_steps(
    step_videos=step_videos,
    step_audios=audio_paths_list,
    subtitle_path=subtitle_path,
)

# ================================================================
# 5. 验证音画同步
# ================================================================
print("\n[5] 验证音画同步...")
if final_video and os.path.exists(final_video):
    print(f"  最终视频: {final_video}")

    import subprocess
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffprobe = ffmpeg_exe.replace("ffmpeg-win-x86_64-v7.1.exe", "ffmpeg-win-x86_64-v7.1.exe")
        # Try to find ffprobe
        ffprobe_path = ffmpeg_exe.replace("ffmpeg", "ffprobe")
        if not os.path.exists(ffprobe_path):
            # Use ffmpeg to probe
            pass
    except:
        ffmpeg_exe = "ffmpeg"
        ffprobe_path = "ffprobe"

    # 用 ffmpeg 检查视频信息
    cmd_info = [ffmpeg_exe, "-i", final_video, "-hide_banner"]
    result_info = subprocess.run(cmd_info, capture_output=True, text=True, timeout=10)
    info_text = result_info.stderr

    # 解析时长
    import re
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", info_text)
    if dur_match:
        h, m, s = dur_match.groups()
        total_dur = int(h) * 3600 + int(m) * 60 + float(s)
        print(f"  视频总时长: {total_dur:.2f}s")

    # 检查音频流
    has_audio = "Audio:" in info_text
    has_video = "Video:" in info_text
    print(f"  含视频流: {has_video}")
    print(f"  含音频流: {has_audio}")

    # 检查每个步骤视频是否含音频
    print("\n  步骤视频音频检查:")
    for sv in step_videos:
        vp = sv["video_path"]
        if os.path.exists(vp):
            has_aud = _has_audio_stream(vp)
            print(f"    步骤 {sv['step_number']}: 含音频={has_aud}")

    # 计算预期总时长 vs 实际总时长
    expected_total = sum(step_audio_durations.values()) + 1.5 + len(step_audios) * 0.3
    print(f"\n  预期总时长（音频+偏移）: {expected_total:.2f}s")
    if dur_match:
        diff = abs(total_dur - expected_total)
        print(f"  实际视频时长: {total_dur:.2f}s")
        print(f"  差异: {diff:.2f}s")
        if diff < 1.0:
            print("  [PASS] 音画同步良好！")
        else:
            print("  [WARN] 时长差异较大")

    print("\n" + "=" * 60)
    print("测试完成！")
    print(f"最终视频: {final_video}")
    print("=" * 60)
else:
    print("  [FAIL] 视频合成失败")
    if not step_videos:
        print("  原因: 无步骤视频")
    print("=" * 60)
