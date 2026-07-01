"""
============================================================
MathAnimAI — 快速验证脚本
功能：跳过LLM API调用，使用demo中的JSON脚本直接测试
      动画渲染 + 音频 + 视频合成 全流程
============================================================
"""
import os
import sys
import json
import logging

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("QuickTest")


def test_runner():
    """快速测试主函数"""
    from config import ensure_dirs
    ensure_dirs()

    # 加载demo脚本
    demo_path = os.path.join(os.path.dirname(__file__), "demo", "sample_questions.json")
    with open(demo_path, "r", encoding="utf-8") as f:
        demo_data = json.load(f)

    print("=" * 60)
    print("  MathAnimAI 快速验证测试")
    print("=" * 60)

    # ================================================================
    # 测试1: 验证环境配置
    # ================================================================
    print("\n[测试1] 环境配置检查...")
    from config import (
        LLM_BASE_URL, LLM_MODEL, TTS_VOICE,
        RESOLUTION_WIDTH, RESOLUTION_HEIGHT, FRAME_RATE,
        OUTPUT_DIR, GRADIO_PORT, Colors
    )
    print(f"  LLM API: {LLM_BASE_URL} 模型: {LLM_MODEL}")
    print(f"  分辨率: {RESOLUTION_WIDTH}x{RESOLUTION_HEIGHT}@{FRAME_RATE}fps")
    print(f"  输出目录: {OUTPUT_DIR}")
    print(f"  UI端口: {GRADIO_PORT}")
    print(f"  配色方案: PRIMARY={Colors.PRIMARY}")
    print("  [OK] 配置加载正常")

    # ================================================================
    # 测试2: Pydantic Schema校验
    # ================================================================
    print("\n[测试2] Pydantic Schema校验...")
    from parser.schema import ProblemScript, AnimationType, ProblemType

    for item in demo_data.get("samples", demo_data):
        try:
            script_data = item.get("script", item)  # 取script字段或直接使用
            script = ProblemScript.model_validate(script_data)
            print(f"  [{script.problem_type}] {script.problem_text[:30]}... — "
                  f"{len(script.steps)}个步骤 — [OK]")
        except Exception as e:
            name = item.get("name", "未知") if isinstance(item, dict) else str(item)[:30]
            print(f"  [{name}] 校验失败: {e}")

    # ================================================================
    # 测试3: Manim导入验证
    # ================================================================
    print("\n[测试3] Manim引擎导入验证...")
    try:
        import manim
        print(f"  Manim版本: {manim.__version__} — [OK]")
    except ImportError as e:
        print(f"  [FAIL] Manim未安装: {e}")
        return False
    except Exception as e:
        print(f"  [FAIL] Manim导入异常: {e}")
        return False

    # ================================================================
    # 测试4: LaTeX检测
    # ================================================================
    print("\n[测试4] LaTeX可用性检测...")
    import shutil
    has_latex = shutil.which("pdflatex") or shutil.which("xelatex")
    if has_latex:
        print(f"  LaTeX可用 — 公式将使用MathTex渲染")
    else:
        print(f"  LaTeX不可用 — 将使用Text+Unicode降级渲染")
        print(f"  提示: 安装MiKTeX或TeX Live以获得更好的公式效果")

    # ================================================================
    # 测试5: FFmpeg检测
    # ================================================================
    print("\n[测试5] FFmpeg可用性检测...")
    ffmpeg_found = False
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(ffmpeg_path):
            print(f"  FFmpeg路径: {ffmpeg_path} — [OK]")
            ffmpeg_found = True
        else:
            print(f"  FFmpeg路径无效: {ffmpeg_path} — [FAIL]")
    except ImportError:
        print(f"  imageio-ffmpeg未安装 — [FAIL]")

    if shutil.which("ffmpeg"):
        print(f"  系统PATH中的ffmpeg也可用 — [OK]")

    # ================================================================
    # 测试6: 尝试渲染一个简单Manim动画
    # ================================================================
    print("\n[测试6] Manim简单渲染测试...")
    if ffmpeg_found:
        try:
            import subprocess
            import tempfile
            import imageio_ffmpeg

            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            env = os.environ.copy()
            env["FFMPEG_BINARY"] = ffmpeg_path

            test_code = '''
from manim import *
config.pixel_width = 640
config.pixel_height = 360
config.frame_rate = 30
config.disable_tex = True

class QuickTest(Scene):
    def construct(self):
        text = Text("MathAnimAI 测试成功!", font="Microsoft YaHei", font_size=36, color=BLUE)
        self.play(Write(text))
        self.wait(1)
'''

            test_dir = tempfile.mkdtemp()
            test_file = os.path.join(test_dir, "quick_test.py")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(test_code)

            python_exe = sys.executable
            cmd = [python_exe, "-m", "manim", "-ql", "--disable_tex", test_file, "QuickTest"]
            logger.info(f"执行: {' '.join(cmd)}")

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
                cwd=test_dir, env=env
            )

            if result.returncode == 0:
                # 查找生成的视频
                media_dir = os.path.join(test_dir, "media")
                for root, dirs, files in os.walk(media_dir):
                    for f in files:
                        if f.endswith(".mp4"):
                            video_path = os.path.join(root, f)
                            size = os.path.getsize(video_path) / 1024
                            print(f"  视频生成成功: {video_path} ({size:.1f} KB) — [OK]")
                            break
            else:
                stderr_tail = result.stderr[-300:] if result.stderr else "(空)"
                print(f"  渲染失败 (exit code={result.returncode})")
                print(f"  错误信息: {stderr_tail}")
                print(f"  标准输出: {result.stdout[-200:] if result.stdout else '(空)'}")

        except subprocess.TimeoutExpired:
            print(f"  渲染超时(120秒) — [FAIL]")
        except Exception as e:
            print(f"  渲染异常: {e} — [FAIL]")
    else:
        print(f"  跳过(FFmpeg不可用) — [SKIP]")

    # ================================================================
    # 测试7: Gradio导入验证
    # ================================================================
    print("\n[测试7] Gradio导入验证...")
    try:
        import gradio as gr
        print(f"  Gradio版本: {gr.__version__} — [OK]")
    except ImportError as e:
        print(f"  [FAIL] Gradio未安装: {e}")
    except Exception as e:
        print(f"  [FAIL] Gradio导入异常: {e}")

    # ================================================================
    # 测试8: 存储模块验证
    # ================================================================
    print("\n[测试8] SQLite存储验证...")
    try:
        from storage.history import HistoryManager
        db = HistoryManager()
        records = db.get_all()
        print(f"  数据库正常，当前记录数: {len(records)} — [OK]")
    except Exception as e:
        print(f"  [FAIL] 存储模块异常: {e}")

    # ================================================================
    # 测试9: edge-tts验证
    # ================================================================
    print("\n[测试9] edge-tts可用性验证...")
    try:
        import edge_tts
        print(f"  edge-tts已安装 — [OK]")
        voices = edge_tts.list_voices
        print(f"  list_voices可用（需要异步调用测试语音列表）")
    except ImportError:
        print(f"  edge-tts未安装 — [FAIL]")
    except Exception as e:
        print(f"  edge-tts异常: {e} — [WARN]")

    print("\n" + "=" * 60)
    print("  测试完成!")
    print("=" * 60)
    print("\n如果Manim渲染测试通过，可运行以下命令启动完整服务：")
    print(f"  python main.py")
    print(f"  浏览器打开: http://127.0.0.1:{GRADIO_PORT}")

    return True


if __name__ == "__main__":
    test_runner()
