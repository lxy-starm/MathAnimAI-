"""
============================================================
MathAnimAI — Gradio Web 主入口
串联完整 Agent 流水线：
  1. OCR 识别 (图片→文本)
  2. LLM 规划 (文本→JSON动画脚本)
  3. Manim 渲染 (JSON→无声动画视频)
  4. TTS 配音 (文本→分段语音)
  5. 字幕生成 (步骤时长→SRT)
  6. 视频合成 (动画+音频+字幕→MP4)
  7. 存储记录 (SQLite持久化)
============================================================
"""

import io
import os
import sys
import json
import time
import logging
import traceback
from typing import Optional, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows 控制台 UTF-8 支持
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from config import (
    LLM_API_KEY, get_timestamp, ensure_dirs,
    OUTPUT_VIDEO_DIR, OUTPUT_AUDIO_DIR, OUTPUT_SUBTITLE_DIR,
    GRADIO_PORT,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(stream=sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "math_anim_ai.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("MathAnimAI")


# ================================================================
# 核心流水线 — 完整 Agent 闭环
# ================================================================
def run_full_pipeline(
    problem_text: str,
    problem_image_path: str = "",
    grade_level: str = "初中",
    problem_type: str = "自动识别",
) -> dict[str, Any]:
    """
    完整 Agent 流水线入口

    Args:
        problem_text: 题目文本
        problem_image_path: 题目图片路径（可选）
        grade_level: 学段
        problem_type: 题型

    Returns:
        {
            "success": bool,
            "video_path": str,
            "script_json": str,
            "message": str,
            "steps": list
        }
    """
    result = {
        "success": False,
        "video_path": "",
        "script_json": "",
        "message": "",
        "steps": [],
    }

    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"流水线启动: grade={grade_level}, type={problem_type}")
    logger.info(f"题目: {problem_text[:100]}")

    try:
        # ================================================================
        # Step 1: OCR 预处理（如果有图片）
        # ================================================================
        logger.info("[Step 1/7] OCR 预处理")
        if problem_image_path and os.path.exists(problem_image_path):
            from parser.ocr import ocr_problem, preprocess_image
            processed_img = preprocess_image(problem_image_path)
            ocr_text = ocr_problem(processed_img)
            if ocr_text and not problem_text.strip():
                problem_text = ocr_text
                logger.info(f"OCR识别结果: {ocr_text[:100]}...")
            elif ocr_text:
                problem_text = f"{problem_text}\n{ocr_text}"
        elif not problem_text.strip():
            result["message"] = "请输入题目文本或上传题目图片"
            return result

        # ================================================================
        # Step 2: 题目类型自动识别
        # ================================================================
        logger.info("[Step 2/7] 题目类型识别")
        if problem_type == "自动识别":
            from parser.llm_engine import detect_problem_type
            problem_type = detect_problem_type(problem_text)
            logger.info(f"自动识别题型: {problem_type}")

        # 映射中文题型到英文
        type_map = {
            "方程": "equation", "几何": "geometry", "函数": "function",
            "应用题": "word_problem", "分数": "fraction",
        }
        problem_type_en = type_map.get(problem_type, problem_type)

        # ================================================================
        # Step 3: LLM 规划动画脚本
        # ================================================================
        logger.info("[Step 3/7] LLM 规划动画脚本")

        # 检查 LLM 可用性
        if not _is_llm_available():
            logger.warning("LLM 不可用，使用内置示例脚本")
            script = _get_demo_script(problem_text, problem_type_en, grade_level)
        else:
            from parser.prompt import get_prompt, get_user_prompt
            from parser.llm_engine import call_llm

            system_prompt = get_prompt(problem_type_en)
            user_prompt = get_user_prompt(problem_text, problem_type_en, grade_level)

            try:
                script = call_llm(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
            except Exception as e:
                logger.error(f"LLM调用失败，降级使用内置示例: {e}")
                script = _get_demo_script(problem_text, problem_type_en, grade_level)

        # 保存脚本JSON
        script_json = script.to_json_str()
        result["script_json"] = script_json
        logger.info(f"动画脚本生成完成: {len(script.steps)}个步骤")

        # ================================================================
        # Step 4: 存入数据库（初始记录）
        # ================================================================
        logger.info("[Step 4/7] 保存记录到数据库")
        from storage.history import get_history
        history_db = get_history()
        record_id = history_db.insert_record(
            problem_text=problem_text,
            script_json=script_json,
            problem_type=problem_type_en,
            grade_level=grade_level,
        )
        logger.info(f"数据库记录 ID={record_id}")

        # ================================================================
        # Step 5: Manim 动画渲染
        # ================================================================
        logger.info("[Step 5/7] Manim 动画渲染")

        # 检查 Manim 是否可用
        try:
            import manim
            logger.info(f"Manim 版本: {manim.__version__}")
            manim_available = True
        except ImportError:
            logger.warning("Manim 未安装，将跳过动画渲染")
            manim_available = False

        if manim_available:
            from animation.builder import build_and_render
            try:
                animation_path = build_and_render(
                    script=script,
                    hd=True,
                )
                if animation_path:
                    result["video_path"] = animation_path
                    history_db.update_record(record_id, animation_path=animation_path)
                    logger.info(f"动画渲染完成: {animation_path}")
                else:
                    logger.warning("动画渲染失败，跳过")
                    history_db.update_record(
                        record_id,
                        status="failed",
                        error_message="动画渲染失败",
                    )
            except Exception as e:
                logger.error(f"动画渲染异常: {e}")
                history_db.update_record(
                    record_id,
                    status="failed",
                    error_message=f"动画渲染异常: {str(e)}",
                )
        else:
            logger.info("跳过动画渲染（Manim未安装）")

        # ================================================================
        # Step 6: TTS 语音生成
        # ================================================================
        logger.info("[Step 6/7] TTS 语音生成")

        try:
            import edge_tts
            tts_available = True
        except ImportError:
            logger.warning("edge-tts 未安装，跳过语音生成")
            tts_available = False

        step_audios = []
        if tts_available:
            from audio.tts import generate_all_audios_sync

            # 将 Pydantic 步骤转为字典
            steps_data = [
                {
                    "step_number": s.step_number,
                    "voice_text": s.voice_text or s.text,
                    "text": s.text,
                }
                for s in script.steps
            ]

            if steps_data:
                try:
                    step_audios = generate_all_audios_sync(steps_data)
                    logger.info(f"语音生成完成: {len(step_audios)}段")

                    # 合并为完整音频
                    audio_files = [a["path"] for a in step_audios if a.get("path")]
                    if audio_files:
                        from audio.tts import merge_audio_segments
                        timestamp = get_timestamp()
                        audio_output = os.path.join(OUTPUT_AUDIO_DIR, f"full_{timestamp}.mp3")
                        merged_audio = merge_audio_segments(audio_files, audio_output)
                        if merged_audio:
                            history_db.update_record(record_id, audio_path=merged_audio)
                except Exception as e:
                    logger.warning(f"语音生成降级: {e}")

        # ================================================================
        # Step 7: 字幕生成 & 视频合成
        # ================================================================
        logger.info("[Step 7/7] 字幕生成 & 视频合成")

        # 字幕
        subtitle_path = ""
        if step_audios:
            try:
                from audio.subtitle import save_srt_file
                subtitle_path = save_srt_file(step_audios)
                if subtitle_path:
                    history_db.update_record(record_id, subtitle_path=subtitle_path)
                    logger.info(f"字幕生成完成: {subtitle_path}")
            except Exception as e:
                logger.warning(f"字幕生成失败: {e}")

        # 如果 Manim 渲染成功且有音频，合成最终视频
        if result["video_path"] and os.path.exists(result["video_path"]):
            try:
                from video.composer import compose_video
                audio_input = history_db.get_record(record_id)
                audio_path_input = audio_input.get("audio_path", "") if audio_input else ""

                if audio_path_input and os.path.exists(audio_path_input):
                    final_video = compose_video(
                        animation_path=result["video_path"],
                        audio_path=audio_path_input,
                        subtitle_path=subtitle_path,
                        title=problem_text[:30],
                    )
                    if final_video:
                        result["video_path"] = final_video
                        history_db.update_record(
                            record_id,
                            final_video_path=final_video,
                            status="completed",
                        )
                        logger.info(f"最终视频合成完成: {final_video}")
                else:
                    # 无音频，直接标记完成
                    history_db.update_record(
                        record_id,
                        final_video_path=result["video_path"],
                        status="completed",
                    )
            except Exception as e:
                logger.warning(f"视频合成降级: {e}")
                history_db.update_record(
                    record_id,
                    final_video_path=result["video_path"],
                    status="completed",
                )

        # ================================================================
        # 完成
        # ================================================================
        elapsed = time.time() - start_time
        result["success"] = True
        result["steps"] = [
            {
                "step_number": s.step_number,
                "title": s.title,
                "text": s.text,
                "voice_text": s.voice_text,
            }
            for s in script.steps
        ]

        if result["video_path"]:
            result["message"] = (
                f"[OK] 教学动画生成完成！\n"
                f"耗时: {elapsed:.1f}s\n"
                f"题型: {problem_type_en}\n"
                f"步骤: {len(script.steps)}\n"
                f"视频: {result['video_path']}"
            )
        else:
            result["message"] = (
                f"[WARN] 动画脚本已生成，但渲染/合成未完成\n"
                f"耗时: {elapsed:.1f}s\n"
                f"步骤: {len(script.steps)}\n"
                f"请确保 Manim 环境配置正确"
            )

        logger.info(f"流水线完成: 耗时{elapsed:.1f}s")
        logger.info(f"结果: {result['message']}")

        return result

    except Exception as e:
        elapsed = time.time() - start_time
        error_detail = traceback.format_exc()
        logger.error(f"流水线异常: {error_detail}")
        result["message"] = f"[FAIL] 生成失败: {str(e)}\n耗时: {elapsed:.1f}s"
        return result


# ================================================================
# 内置示例脚本（LLM不可用时的降级方案）
# ================================================================
def _get_demo_script(
    problem_text: str,
    problem_type: str,
    grade_level: str,
):
    """生成内置示例动画脚本（当LLM API不可用时使用）"""
    from parser.schema import (
        ProblemScript, AnimationSettings, Step, AnimationType, StepPosition
    )
    import datetime

    # 根据题目文本推断
    text = problem_text.strip()
    steps = []

    # 通用步骤模板 — 所有步骤使用 TEXT_SLIDE_IN 保证文本变量存在
    steps_data = [
        {
            "step_number": 1,
            "title": "审题分析",
            "text": f"题目：{text}",
            "animation_type": AnimationType.TITLE_DISPLAY,
            "position": StepPosition.CENTER,
            "voice_text": f"我们来看这道题目：{text}",
        },
        {
            "step_number": 2,
            "title": "解题思路",
            "text": "分析题目中的已知条件和求解目标",
            "animation_type": AnimationType.TEXT_SLIDE_IN,
            "position": StepPosition.BELOW,
            "voice_text": "首先分析题目中的已知条件和求解目标。",
        },
        {
            "step_number": 3,
            "title": "列式解答",
            "text": "根据已知条件列出算式或方程",
            "animation_type": AnimationType.TEXT_SLIDE_IN,
            "position": StepPosition.BELOW,
            "voice_text": "根据已知条件，列出算式或方程。",
        },
        {
            "step_number": 4,
            "title": "计算求解",
            "text": "逐步计算得出最终结果",
            "animation_type": AnimationType.HIGHLIGHT,
            "position": StepPosition.BELOW,
            "voice_text": "现在进行逐步计算，得出最终结果。",
        },
        {
            "step_number": 5,
            "title": "检验作答",
            "text": "验证结果，给出最终答案",
            "animation_type": AnimationType.TEXT_SLIDE_IN,
            "position": StepPosition.BELOW,
            "voice_text": "最后验证结果的正确性，给出最终答案。",
        },
    ]

    for sd in steps_data:
        steps.append(Step(**sd))

    return ProblemScript(
        problem_type=problem_type,
        grade_level=grade_level,
        problem_text=text,
        final_answer="请等待动画展示",
        settings=AnimationSettings(),
        steps=steps,
        created_at=datetime.datetime.now().isoformat(),
        model_used="内置模板（LLM未配置）",
    )


# ================================================================
# Gradio 事件处理函数
# ================================================================
def handle_generate(
    problem_text: str,
    problem_image: str,
    grade_level: str,
    problem_type: str,
):
    """
    Gradio「生成」按钮回调
    """
    if not problem_text.strip() and not problem_image:
        return (
            None,
            "",
            "请输入题目文本或上传题目图片",
            _get_history_data(),
        )

    # 运行流水线
    result = run_full_pipeline(
        problem_text=problem_text,
        problem_image_path=problem_image or "",
        grade_level=grade_level,
        problem_type=problem_type.split("（")[0] if "（" in problem_type else problem_type,
    )

    # 构建输出
    video_path = result.get("video_path", "")
    # 规范化路径：绝对路径 + 正斜杠（Gradio 跨平台兼容）
    if video_path and os.path.exists(video_path):
        video_path = os.path.abspath(video_path).replace("\\", "/")
    else:
        video_path = None
    script_json = result.get("script_json", "")
    message = result.get("message", "")
    history_data = _get_history_data()

    # 格式化状态日志
    steps_info = ""
    for step in result.get("steps", []):
        steps_info += f"\n  [{step['step_number']}] {step['title']}: {step['text'][:50]}..."

    full_message = message
    if steps_info:
        full_message += f"\n\n步骤详情:{steps_info}"

    return (
        video_path,
        script_json,
        full_message,
        history_data,
    )


def handle_ocr(image_path: str):
    """
    Gradio「图片上传」回调 — OCR识别
    """
    if not image_path:
        return "", "等待上传图片..."

    try:
        from parser.ocr import ocr_problem, preprocess_image
        processed = preprocess_image(image_path)
        text = ocr_problem(processed)
        if text:
            return text, f"OCR识别成功，已填充题目文本框"
        else:
            return "", "OCR未识别到文字，请手动输入题目"
    except Exception as e:
        logger.error(f"OCR失败: {e}")
        return "", f"OCR识别失败: {str(e)}"


def _get_history_data():
    """获取历史记录表格数据"""
    try:
        from storage.history import get_history
        db = get_history()
        records = db.get_all_records(limit=10)
        data = []
        for r in records:
            data.append([
                r.get("id", ""),
                r.get("created_at", "")[:19],
                r.get("problem_text", "")[:40] + ("..." if len(r.get("problem_text", "")) > 40 else ""),
                r.get("problem_type", ""),
                r.get("status", "unknown"),
                "可回放" if r.get("final_video_path") and os.path.exists(r.get("final_video_path", "")) else "待生成",
            ])
        return data if data else []
    except Exception as e:
        logger.warning(f"获取历史记录失败: {e}")
        return []


def handle_history():
    """刷新历史记录"""
    return _get_history_data()


# ================================================================
# 主启动函数
# ================================================================
def main():
    """启动 Gradio Web 服务"""
    logger.info("=" * 60)
    logger.info("MathAnimAI 启动中...")
    logger.info("=" * 60)

    # 检查依赖
    _check_dependencies()

    # 创建目录
    ensure_dirs()

    # 初始化数据库
    from storage.history import get_history
    get_history()
    logger.info("数据库就绪")

    # 启动 UI
    from ui.layout import launch_app

    logger.info(f"启动 Web 服务: http://127.0.0.1:{GRADIO_PORT}")
    launch_app(
        pipeline_handler=handle_generate,
        ocr_handler=handle_ocr,
        history_handler=handle_history,
        port=GRADIO_PORT,
    )


def _check_dependencies():
    """检查关键依赖是否安装"""
    deps_ok = True

    # 检查 Manim
    try:
        import manim
        logger.info(f"[OK] Manim {manim.__version__}")
    except ImportError:
        logger.warning("[FAIL] Manim 未安装 — 动画渲染将不可用")
        deps_ok = False

    # 检查 edge-tts
    try:
        import edge_tts
        logger.info("[OK] edge-tts")
    except ImportError:
        logger.warning("[FAIL] edge-tts 未安装 — 语音合成将不可用")
        deps_ok = False

    # 检查 moviepy
    try:
        import moviepy
        logger.info("[OK] moviepy")
    except ImportError:
        logger.warning("[FAIL] moviepy 未安装 — 视频合成将不可用")
        deps_ok = False

    # 检查 OpenAI
    try:
        import openai
        logger.info("[OK] openai")
    except ImportError:
        logger.warning("[FAIL] openai 未安装 — LLM调用将降级")
        deps_ok = False

    # 检查 LLM 可用性
    if not _is_llm_available():
        logger.warning("[WARN] LLM 不可用 — 将使用内置模板脚本")
        deps_ok = False

    if not deps_ok:
        logger.warning("部分依赖缺失，系统将以降级模式运行")


def _is_llm_available() -> bool:
    """
    检测 LLM 是否可用
    支持 Ollama（本地）和远程 API 两种模式
    """
    from config import LLM_PROVIDER, LLM_BASE_URL

    # 远程 API：检查 API Key 是否有效
    if LLM_PROVIDER != "ollama":
        from config import LLM_API_KEY
        if not LLM_API_KEY or LLM_API_KEY in ("your_api_key_here", "your-api-key"):
            logger.warning("远程 API Key 未配置")
            return False
        return True

    # 本地 Ollama：轻量 HTTP 健康检查
    try:
        import urllib.request, json
        # Ollama 原生 API 在根路径，不在 /v1 下
        from urllib.parse import urlparse
        parsed = urlparse(LLM_BASE_URL)
        ollama_host = f"{parsed.scheme}://{parsed.netloc}"
        url = ollama_host + "/api/tags"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            logger.info(f"Ollama 已连接，可用模型: {models}")
            return len(models) > 0
    except Exception as e:
        logger.warning(f"Ollama 连接失败 ({LLM_BASE_URL}): {e}")
        return False


# ================================================================
# 入口
# ================================================================
if __name__ == "__main__":
    main()
