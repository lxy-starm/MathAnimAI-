"""
============================================================
MathAnimAI — Manim渲染管道
功能：
  1. 支持1080P高清 / 720P预览双分辨率
  2. 程序化渲染Scene
  3. 自动输出视频到指定目录
  4. 捕获渲染异常
============================================================
"""

import os
import sys
import shutil
import subprocess
import logging
import tempfile
from typing import Optional

from config import (
    RESOLUTION_WIDTH, RESOLUTION_HEIGHT, FRAME_RATE,
    QUALITY_FLAG, CACHE_DIR, OUTPUT_VIDEO_DIR,
    get_timestamp,
)

logger = logging.getLogger("MathAnimAI.Renderer")


# ================================================================
# 临时场景代码生成
# ================================================================
SCENE_TEMPLATE = '''
# Auto-generated MathAnimAI Scene
from manim import *
import sys
sys.path.insert(0, r"{project_root}")

from config import RESOLUTION_WIDTH, RESOLUTION_HEIGHT, FRAME_RATE
from animation.common import *
from animation.scenes.equation import *
from animation.scenes.geometry import *
from animation.scenes.function import *
from animation.scenes.word_problem import *
from animation.scenes.fraction import *

class GeneratedScene({base_class}):
    def construct(self):
        # 此方法由builder.py动态生成
        pass
'''


def generate_scene_file(
    scene_code: str,
    scene_class_name: str,
    base_class: str,
    output_dir: str,
) -> str:
    """
    生成Manim场景Python文件

    Args:
        scene_code: construct()方法内的代码
        scene_class_name: 场景类名
        base_class: 继承的基类名
        output_dir: 输出目录

    Returns:
        生成的.py文件路径
    """
    # 使用当前项目的绝对路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    template = f'''# Auto-generated MathAnimAI Scene
from manim import *
import sys
import os
sys.path.insert(0, r"{project_root}")
sys.path.insert(0, r"{os.path.dirname(project_root)}")

from config import RESOLUTION_WIDTH, RESOLUTION_HEIGHT, FRAME_RATE
from animation.common import *
from animation.scenes.equation import *
from animation.scenes.geometry import *
from animation.scenes.function import *
from animation.scenes.word_problem import *
from animation.scenes.fraction import *

config.pixel_width = {RESOLUTION_WIDTH}
config.pixel_height = {RESOLUTION_HEIGHT}
config.frame_rate = {FRAME_RATE}

class {scene_class_name}({base_class}):
    def construct(self):
{scene_code}
'''

    file_path = os.path.join(output_dir, f"{scene_class_name}.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(template)

    logger.info(f"场景文件已生成: {file_path}")
    return file_path


# ================================================================
# Manim CLI渲染
# ================================================================
def render_scene(
    scene_file: str,
    scene_class: str,
    quality: str = None,
    output_dir: str = None,
) -> Optional[str]:
    """
    使用Manim CLI渲染场景

    Args:
        scene_file: 场景.py文件路径
        scene_class: 场景类名
        quality: 渲染质量 ("h"=高清, "m"=标清, "l"=低清)
        output_dir: 输出视频保存目录

    Returns:
        渲染完成的视频文件路径，失败返回None
    """
    quality_flag = quality or QUALITY_FLAG
    output_path = output_dir or OUTPUT_VIDEO_DIR
    os.makedirs(output_path, exist_ok=True)

    # 确定Python可执行文件路径（使用venv中的Python，确保manim可用）
    python_exe = sys.executable

    # 检测FFmpeg路径（imageio-ffmpeg提供的二进制）
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        ffmpeg_path = None

    # 检测LaTeX是否可用
    import shutil
    has_latex = shutil.which("pdflatex") is not None or shutil.which("xelatex") is not None

    # 构建manim命令 — 使用Python -m manim确保找到正确的manim
    cmd = [
        python_exe, "-m", "manim",
        f"-q{quality_flag}",
    ]
    cmd.extend([scene_file, scene_class])

    # 设置环境变量，注入FFmpeg路径
    env = os.environ.copy()
    if ffmpeg_path:
        env["FFMPEG_BINARY"] = ffmpeg_path
        env["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + env.get("PATH", "")
        logger.info(f"FFmpeg路径: {ffmpeg_path}")

    logger.info(f"渲染命令: {' '.join(cmd)}")

    try:
        # 运行manim命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10分钟超时
            cwd=os.path.dirname(scene_file),
        )

        # 检查输出
        if result.returncode != 0:
            logger.error(f"Manim渲染失败:\n{result.stderr[-500:]}")
            return None

        # 查找生成的视频文件
        # Manim输出路径: media/videos/{scene_name}/{quality_dir}/{scene_class}.mp4
        scene_name = os.path.splitext(os.path.basename(scene_file))[0]

        # 由于模板中硬编码了 1080p 分辨率，实际输出始终在 1080p60 目录
        # 尝试多个可能的质量目录
        possible_dirs = ["1080p60", "720p30", "480p15"]
        video_file = None

        media_base = os.path.join(os.path.dirname(scene_file), "media", "videos", scene_name)
        for qdir in possible_dirs:
            expected_dir = os.path.join(media_base, qdir)
            if os.path.exists(expected_dir):
                for f in os.listdir(expected_dir):
                    if f.endswith(".mp4"):
                        # 优先匹配场景类名，否则取第一个 mp4
                        candidate = os.path.join(expected_dir, f)
                        if scene_class in f:
                            video_file = candidate
                            break
                if not video_file:
                    # 未匹配到类名，取第一个 mp4
                    mp4s = [f for f in os.listdir(expected_dir) if f.endswith(".mp4")]
                    if mp4s:
                        video_file = os.path.join(expected_dir, mp4s[0])
                if video_file:
                    break

        if video_file:
            # 复制到输出目录
            import shutil
            timestamp = get_timestamp()
            dest = os.path.join(output_path, f"{scene_class}_{timestamp}.mp4")
            shutil.copy2(video_file, dest)
            logger.info(f"视频已输出: {dest}")
            return dest
        else:
            logger.error("未找到生成视频文件")
            return None

    except subprocess.TimeoutExpired:
        logger.error("Manim渲染超时（10分钟）")
        return None
    except FileNotFoundError:
        logger.error("Manim 未安装或不在PATH中")
        logger.error("请运行: pip install manim")
        return None
    except Exception as e:
        logger.error(f"渲染异常: {e}")
        return None


# ================================================================
# 简化渲染入口（用于测试）
# ================================================================
def render_scene_quality(
    scene_file: str,
    scene_class: str,
    hd: bool = True,
    output_dir: str = None,
) -> Optional[str]:
    """
    便捷渲染入口

    Args:
        scene_file: 场景文件路径
        scene_class: 场景类名
        hd: True=1080P, False=720P
        output_dir: 自定义输出目录
    """
    quality = "h" if hd else "m"
    return render_scene(scene_file, scene_class, quality=quality, output_dir=output_dir)
