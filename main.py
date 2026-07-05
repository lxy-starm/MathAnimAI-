"""
============================================================
MathAnimAI — Gradio Web 主入口
串联完整 Agent 流水线，支持双模式：

【代码直生模式】（Claude 可用时优先）
  1. OCR 识别 (图片→文本)
  2. 题目类型识别
  3. Claude 直生 Manim 代码 (文本→完整Python源码)
  4. 存入数据库
  5. TTS 配音 (narration→分段语音+sync_points)
  6. Manim 渲染 (直接渲染Claude代码，无需builder.py)

【JSON 中间格式模式】（降级方案）
  1. OCR 识别 (图片→文本)
  2. 题目类型识别
  3. LLM 规划 (文本→JSON动画脚本)
  4. 存入数据库
  5. TTS 配音 (文本→分段语音，获取真实时长用于精确同步)
  6. Manim 渲染 (JSON + 真实音频时长→精确同步动画视频)
  7. 字幕生成 & 视频合成 (ffmpeg, 动画+音频+字幕→MP4)
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

        # ===== 脚本后处理增强：自动补全 LLM 遗漏的数据 =====
        from parser.script_enricher import enrich_script
        script = enrich_script(script)
        logger.info(f"脚本增强完成: base_figure={'有' if script.base_figure else '无'}, steps={len(script.steps)}")

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
        # Step 5: TTS 语音生成（在 Manim 之前，获取真实音频时长用于精确同步）
        # ================================================================
        logger.info("[Step 5/7] TTS 语音生成")

        try:
            import edge_tts
            tts_available = True
        except ImportError:
            logger.warning("edge-tts 未安装，跳过语音生成")
            tts_available = False

        step_audios = []
        step_audio_durations = {}  # {step_number: actual_duration_seconds}
        step_audio_paths = {}      # {step_number: absolute_audio_file_path}
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

                    # 提取真实音频时长和路径，用于 Manim 精确同步
                    for a in step_audios:
                        if a.get("step_number") and a.get("duration"):
                            step_audio_durations[a["step_number"]] = a["duration"]
                        if a.get("step_number") and a.get("path"):
                            step_audio_paths[a["step_number"]] = a["path"]
                    logger.info(f"TTS 真实时长: {step_audio_durations}")
                    logger.info(f"TTS 音频路径: {step_audio_paths}")

                    # 合并为完整音频（保留作为后备，主流程使用 add_sound 嵌入）
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
        # Step 6: Manim 动画渲染（使用 TTS 真实时长精确同步）
        # ================================================================
        logger.info("[Step 6/7] Manim 动画渲染")

        # 检查 Manim 是否可用
        try:
            import manim
            logger.info(f"Manim 版本: {manim.__version__}")
            manim_available = True
        except ImportError:
            logger.warning("Manim 未安装，将跳过动画渲染")
            manim_available = False

        # 判断是否支持每步独立渲染（无持久化图形的题型）
        PER_STEP_TYPES = {"word_problem", "fraction", "equation"}
        use_per_step = (
            manim_available
            and problem_type_en in PER_STEP_TYPES
            and len(step_audio_durations) > 0
        )

        step_videos = []  # 每步独立渲染结果

        if manim_available:
            if use_per_step:
                # === 每步独立渲染模式（精确音画同步） ===
                from animation.builder import build_and_render_per_step
                logger.info(f"使用每步独立渲染模式: {problem_type_en}")
                try:
                    step_videos = build_and_render_per_step(
                        script=script,
                        audio_durations=step_audio_durations,
                        hd=True,
                        audio_paths=step_audio_paths,
                    )
                    if step_videos:
                        logger.info(f"每步渲染完成: {len(step_videos)}/{len(script.steps)} 步骤")
                    else:
                        logger.warning("每步渲染全部失败，降级到单场景模式")
                        use_per_step = False
                except Exception as e:
                    logger.warning(f"每步渲染异常，降级到单场景: {e}")
                    use_per_step = False
                    step_videos = []

            if not use_per_step:
                # === 单场景渲染模式（add_sound 嵌入音频 + end_scene_with_audio 同步） ===
                from animation.builder import build_and_render
                try:
                    animation_path = build_and_render(
                        script=script,
                        hd=True,
                        audio_durations=step_audio_durations if step_audio_durations else None,
                        audio_paths=step_audio_paths if step_audio_paths else None,
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
        # Step 7: 字幕生成 & 视频合成
        # ================================================================
        logger.info("[Step 7/7] 字幕生成 & 视频合成")

        # 字幕
        subtitle_path = ""
        if step_audios:
            try:
                from audio.subtitle import save_srt_file
                # 计算字幕时间偏移：标题动画时长 + 停顿
                # 单场景模式：标题在所有步骤之前
                # 每步模式：标题在第一个步骤视频中
                title_offset = float(script.settings.duration) + 1.0  # 标题动画 + 停顿
                step_gap = 0.8 if not use_per_step else 0.3  # 单场景有过渡动画，每步模式无
                subtitle_path = save_srt_file(
                    step_audios,
                    start_offset=title_offset if not use_per_step else title_offset,
                    step_gap=step_gap,
                )
                if subtitle_path:
                    history_db.update_record(record_id, subtitle_path=subtitle_path)
                    logger.info(f"字幕生成完成: {subtitle_path}")
            except Exception as e:
                logger.warning(f"字幕生成失败: {e}")

        # 合成最终视频
        if use_per_step and step_videos:
            # === 每步拼接合成（步骤视频 + 步骤音频 + 字幕） ===
            try:
                from video.composer import compose_from_steps
                step_audio_paths = [
                    a["path"] for a in step_audios
                    if a.get("path") and os.path.exists(a["path"])
                ]
                if step_audio_paths:
                    logger.info(f"每步拼接合成: {len(step_videos)} 视频 + {len(step_audio_paths)} 音频")
                    final_video = compose_from_steps(
                        step_videos=step_videos,
                        step_audios=step_audio_paths,
                        subtitle_path=subtitle_path,
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
                        history_db.update_record(
                            record_id,
                            status="completed",
                        )
                else:
                    logger.warning("步骤音频路径缺失，跳过合成")
                    history_db.update_record(
                        record_id,
                        status="completed",
                    )
            except Exception as e:
                logger.warning(f"每步拼接合成降级: {e}")
                history_db.update_record(
                    record_id,
                    status="completed",
                )

        elif result.get("video_path") and os.path.exists(result["video_path"]):
            # === 传统单场景合成 ===
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
# Claude 直生代码模式流水线
# ================================================================
def run_code_gen_pipeline(
    problem_text: str,
    problem_image_path: str = "",
    grade_level: str = "初中",
    problem_type: str = "自动识别",
) -> dict[str, Any]:
    """
    Claude 直生代码模式流水线：
      1. OCR 预处理
      2. 题目类型识别
      3. Claude 直生 Manim 代码（替代 JSON 中间格式）
      4. 存入数据库
      5. TTS 配音（从 scenes narration 生成，带 sync_points）
      6. Manim 渲染（直接渲染 Claude 生成的代码，无需 builder.py）
      7. 视频已内嵌音频，直接输出
    """
    result = {
        "success": False,
        "video_path": "",
        "script_json": "",
        "message": "",
        "steps": [],
        "manim_code": "",
    }

    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"[代码直生模式] 流水线启动: grade={grade_level}, type={problem_type}")
    logger.info(f"题目: {problem_text[:100]}")

    try:
        # ================================================================
        # Step 1: OCR 预处理
        # ================================================================
        logger.info("[Step 1/6] OCR 预处理")
        if problem_image_path and os.path.exists(problem_image_path):
            from parser.ocr import ocr_problem, preprocess_image
            processed_img = preprocess_image(problem_image_path)
            ocr_text = ocr_problem(processed_img)
            if ocr_text and not problem_text.strip():
                problem_text = ocr_text
            elif ocr_text:
                problem_text = f"{problem_text}\n{ocr_text}"
        elif not problem_text.strip():
            result["message"] = "请输入题目文本或上传题目图片"
            return result

        # ================================================================
        # Step 2: 题目类型自动识别
        # ================================================================
        logger.info("[Step 2/6] 题目类型识别")
        if problem_type == "自动识别":
            from parser.llm_engine import detect_problem_type
            problem_type = detect_problem_type(problem_text)
            logger.info(f"自动识别题型: {problem_type}")

        type_map = {
            "方程": "equation", "几何": "geometry", "函数": "function",
            "应用题": "word_problem", "分数": "fraction",
        }
        problem_type_en = type_map.get(problem_type, problem_type)

        # ================================================================
        # Step 3: Claude 直生 Manim 代码
        # ================================================================
        logger.info("[Step 3/6] Claude 直生 Manim 代码")

        if not _is_llm_available():
            logger.warning("LLM 不可用，降级到 JSON 模式")
            return run_full_pipeline(problem_text, problem_image_path, grade_level, problem_type)

        from parser.llm_engine import generate_manim_code
        gen_code = generate_manim_code(
            problem_text=problem_text,
            grade_level=grade_level,
            problem_type=problem_type_en,
        )

        if not gen_code.success:
            logger.error(f"Claude 代码生成失败: {gen_code.error}")
            logger.warning("降级到 JSON 模式")
            return run_full_pipeline(problem_text, problem_image_path, grade_level, problem_type)

        logger.info(f"代码生成成功: {gen_code.scene_count}幕, 代码{len(gen_code.manim_code)}字符")
        result["manim_code"] = gen_code.manim_code

        # 保存 scenes 信息作为 script_json（兼容前端显示）
        result["script_json"] = json.dumps({
            "scenes": gen_code.scenes,
            "problem_text": problem_text,
            "problem_type": problem_type_en,
            "mode": "code_generation",
        }, ensure_ascii=False, indent=2)

        # ================================================================
        # Step 4: 存入数据库
        # ================================================================
        logger.info("[Step 4/6] 保存记录到数据库")
        from storage.history import get_history
        history_db = get_history()
        record_id = history_db.insert_record(
            problem_text=problem_text,
            script_json=result["script_json"],
            problem_type=problem_type_en,
            grade_level=grade_level,
        )
        logger.info(f"数据库记录 ID={record_id}")

        # ================================================================
        # Step 5: TTS 语音生成（从 scenes narration 生成，带 sync_points）
        # ================================================================
        logger.info("[Step 5/6] TTS 语音生成")

        audio_dir = None
        try:
            import edge_tts
            tts_available = True
        except ImportError:
            logger.warning("edge-tts 未安装，跳过语音生成")
            tts_available = False

        if tts_available:
            audio_dir = _generate_scene_audios(gen_code)
            if audio_dir:
                logger.info(f"语音生成完成，音频目录: {audio_dir}")
            else:
                logger.warning("语音生成失败，将渲染无声动画")

        # ================================================================
        # Step 6: Manim 渲染（直接渲染 Claude 生成的代码）
        # ================================================================
        logger.info("[Step 6/6] Manim 动画渲染")

        try:
            import manim
            logger.info(f"Manim 版本: {manim.__version__}")
            manim_available = True
        except ImportError:
            logger.warning("Manim 未安装，将跳过动画渲染")
            manim_available = False

        if manim_available:
            video_path = _render_generated_code(
                manim_code=gen_code.manim_code,
                audio_dir=audio_dir,
                record_id=record_id,
            )
            if video_path:
                result["video_path"] = video_path
                history_db.update_record(record_id, final_video_path=video_path, status="completed")
                logger.info(f"动画渲染完成: {video_path}")
            else:
                logger.error("动画渲染失败")
                history_db.update_record(record_id, status="failed", error_message="动画渲染失败")
        else:
            logger.info("跳过动画渲染（Manim未安装）")

        # ================================================================
        # 完成
        # ================================================================
        elapsed = time.time() - start_time
        result["success"] = True
        result["steps"] = [
            {
                "step_number": s.get("scene_num", i + 1),
                "title": s.get("name", f"第{i+1}幕"),
                "text": s.get("narration", ""),
                "voice_text": s.get("narration", ""),
            }
            for i, s in enumerate(gen_code.scenes)
        ]

        if result["video_path"]:
            result["message"] = (
                f"[OK] 教学动画生成完成（代码直生模式）！\n"
                f"耗时: {elapsed:.1f}s\n"
                f"题型: {problem_type_en}\n"
                f"幕数: {gen_code.scene_count}\n"
                f"视频: {result['video_path']}"
            )
        else:
            result["message"] = (
                f"[WARN] 代码已生成但渲染未完成\n"
                f"耗时: {elapsed:.1f}s\n"
                f"幕数: {gen_code.scene_count}\n"
                f"请确保 Manim 环境配置正确"
            )

        logger.info(f"流水线完成: 耗时{elapsed:.1f}s")
        return result

    except Exception as e:
        elapsed = time.time() - start_time
        error_detail = traceback.format_exc()
        logger.error(f"代码直生流水线异常: {error_detail}")
        result["message"] = f"[FAIL] 生成失败: {str(e)}\n耗时: {elapsed:.1f}s"
        return result


# ================================================================
# 辅助函数：从 scenes 生成 TTS 音频
# ================================================================
def _generate_scene_audios(gen_code) -> Optional[str]:
    """
    从 GeneratedCode 的 scenes 生成 TTS 音频。

    为每幕生成音频文件，文件名匹配 manim_code 中 SCENES 数组的命名。
    生成 audio_info.json 供 MathAnimScene 基类加载同步点。

    Returns:
        音频目录路径，失败返回 None
    """
    from audio.tts import generate_speech_with_sync, save_audio_info, _estimate_duration
    from config import TTS_VOICE, OUTPUT_AUDIO_DIR

    narrations = gen_code.get_narrations()
    if not narrations:
        logger.warning("没有 narration 文本，跳过 TTS")
        return None

    # 创建本次运行的音频子目录
    timestamp = get_timestamp()
    audio_dir = os.path.join(OUTPUT_AUDIO_DIR, f"run_{timestamp}")
    os.makedirs(audio_dir, exist_ok=True)

    results = []
    for item in narrations:
        scene_num = item["scene_num"]
        name = item["name"]
        narration = item["narration"]

        if not narration.strip():
            logger.warning(f"幕{scene_num} narration 为空，跳过")
            results.append({
                "step_number": scene_num,
                "path": "",
                "duration": 2.0,
                "voice_text": "",
                "sync_points": [],
            })
            continue

        # 构造音频文件名（与 manim_code 中 SCENES 的格式一致）
        audio_filename = f"audio_{scene_num:03d}_{name}.mp3"
        audio_path = os.path.join(audio_dir, audio_filename)

        logger.info(f"生成幕{scene_num}语音: {name}, 文本长度={len(narration)}")

        result = generate_speech_with_sync(
            text=narration,
            output_path=audio_path,
            voice=TTS_VOICE,
        )

        if result:
            result["step_number"] = scene_num
            result["voice_text"] = narration
            results.append(result)
            logger.info(
                f"幕{scene_num}语音生成成功: 时长={result['duration']:.1f}s, "
                f"同步点={len(result.get('sync_points', []))}句"
            )
        else:
            logger.warning(f"幕{scene_num}语音生成失败")
            results.append({
                "step_number": scene_num,
                "path": "",
                "duration": 3.0,
                "voice_text": narration,
                "sync_points": [],
            })

    # 生成 audio_info.json
    save_audio_info(results, audio_dir, TTS_VOICE)

    # 同时生成一份 audio_info.json 在 OUTPUT_AUDIO_DIR 根目录
    # （兼容基类默认查找路径）
    save_audio_info(results, OUTPUT_AUDIO_DIR, TTS_VOICE)

    # 将音频文件也复制到 OUTPUT_AUDIO_DIR 根目录（兼容默认查找路径）
    import shutil
    for r in results:
        if r.get("path") and os.path.exists(r["path"]):
            dest = os.path.join(OUTPUT_AUDIO_DIR, os.path.basename(r["path"]))
            if not os.path.exists(dest):
                shutil.copy2(r["path"], dest)

    return audio_dir


# ================================================================
# 辅助函数：渲染 Claude 生成的 Manim 代码
# ================================================================
def _render_generated_code(
    manim_code: str,
    audio_dir: Optional[str],
    record_id: int,
) -> Optional[str]:
    """
    将 Claude 生成的 Manim 代码写入文件并渲染。

    Args:
        manim_code: Claude 生成的完整 Manim 场景代码
        audio_dir: 音频文件目录路径
        record_id: 数据库记录 ID

    Returns:
        渲染完成的视频文件路径，失败返回 None
    """
    import subprocess
    import shutil
    import re

    # 确保代码中有必要的 import
    project_root = os.path.dirname(os.path.abspath(__file__))

    # 将音频目录和视频输出目录转为绝对路径，避免 manim 渲染时工作目录不同导致找不到文件
    abs_audio_dir = os.path.abspath(audio_dir) if audio_dir else os.path.join(project_root, 'output', 'audio')
    abs_video_dir = os.path.abspath(OUTPUT_VIDEO_DIR)

    # 构建完整的场景文件
    # 在 Claude 生成的代码前添加必要的 import 和路径设置
    preamble = f'''# Auto-generated by Claude Code Generation Mode
# Record ID: {record_id}
# Generated at: {time.strftime("%Y-%m-%d %H:%M:%S")}

from manim import *
import numpy as np
import math
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, r"{project_root}")

# 设置音频目录环境变量（使用绝对路径）
os.environ["MATHANIM_AUDIO_DIR"] = r"{abs_audio_dir}"
os.environ["MATHANIM_VIDEO_OUTPUT"] = r"{abs_video_dir}"

# 导入基类
from animation.base_scene import MathAnimScene

# 设置渲染参数
config.pixel_width = 1920
config.pixel_height = 1080
config.frame_rate = 60

'''

    # 提取场景类名（寻找 class XXX(MathAnimScene) 或 class XXX(Scene)）
    class_match = re.search(r'class\s+(\w+)\s*\(\s*(?:MathAnimScene|Scene)\s*\)', manim_code)
    if class_match:
        scene_class_name = class_match.group(1)
    else:
        # 如果没找到，使用默认名称
        scene_class_name = "MathProblemScene"
        # 在代码开头插入类名
        manim_code = manim_code.replace("MathAnimScene", "MathAnimScene")

    # 如果代码中没有继承 MathAnimScene，替换 Scene 为 MathAnimScene
    if "MathAnimScene" not in manim_code:
        manim_code = manim_code.replace("(Scene)", "(MathAnimScene)")

    full_code = preamble + manim_code

    # 写入临时场景文件
    timestamp = get_timestamp()
    scene_file_dir = os.path.join(project_root, "cache", f"codegen_{timestamp}")
    os.makedirs(scene_file_dir, exist_ok=True)
    scene_file = os.path.join(scene_file_dir, f"{scene_class_name}.py")

    with open(scene_file, "w", encoding="utf-8") as f:
        f.write(full_code)

    logger.info(f"场景文件已写入: {scene_file}")
    logger.info(f"场景类名: {scene_class_name}")

    # 检测 FFmpeg 路径
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        ffmpeg_path = None

    # 构建 manim 命令
    python_exe = sys.executable
    cmd = [python_exe, "-m", "manim", "-qh", scene_file, scene_class_name]

    # 设置环境变量
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"  # Windows GBK 兼容
    if ffmpeg_path:
        env["FFMPEG_BINARY"] = ffmpeg_path
        env["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + env.get("PATH", "")
        logger.info(f"FFmpeg路径: {ffmpeg_path}")

    logger.info(f"渲染命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            cwd=scene_file_dir,
            env=env,
        )

        if result.returncode != 0:
            logger.error(f"Manim渲染失败 (返回码={result.returncode}):")
            stderr_tail = (result.stderr or "")[-1000:]
            stdout_tail = (result.stdout or "")[-500:]
            logger.error(f"stderr: {stderr_tail}")
            logger.error(f"stdout: {stdout_tail}")
            return None

        # 查找生成的视频文件
        scene_name = os.path.splitext(os.path.basename(scene_file))[0]
        possible_dirs = ["1080p60", "720p30", "480p15", "1920p60"]
        video_file = None

        media_base = os.path.join(scene_file_dir, "media", "videos", scene_name)
        for qdir in possible_dirs:
            expected_dir = os.path.join(media_base, qdir)
            if os.path.exists(expected_dir):
                for f in os.listdir(expected_dir):
                    if f.endswith(".mp4"):
                        candidate = os.path.join(expected_dir, f)
                        if scene_class_name in f:
                            video_file = candidate
                            break
                if not video_file:
                    mp4s = [f for f in os.listdir(expected_dir) if f.endswith(".mp4")]
                    if mp4s:
                        video_file = os.path.join(expected_dir, mp4s[0])
                if video_file:
                    break

        # 递归搜索
        if not video_file:
            media_dir = os.path.join(scene_file_dir, "media", "videos")
            if os.path.exists(media_dir):
                for mp4 in os.listdir(media_dir) if os.path.isdir(media_dir) else []:
                    pass
                # Use os.walk for deeper search
                for root, dirs, files in os.walk(media_dir):
                    for f in files:
                        if f.endswith(".mp4"):
                            video_file = os.path.join(root, f)
                            break
                    if video_file:
                        break

        if video_file:
            dest = os.path.join(OUTPUT_VIDEO_DIR, f"{scene_class_name}_{timestamp}.mp4")
            shutil.copy2(video_file, dest)
            logger.info(f"视频已输出: {dest}")
            return dest
        else:
            logger.error("未找到生成视频文件")
            logger.error(f"搜索路径: {media_base}")
            return None

    except subprocess.TimeoutExpired:
        logger.error("Manim渲染超时（10分钟）")
        return None
    except FileNotFoundError:
        logger.error("Manim 未安装或不在PATH中")
        return None
    except Exception as e:
        logger.error(f"渲染异常: {e}")
        return None


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

    # 运行流水线 — 优先使用代码直生模式（Claude），降级到 JSON 模式
    from config import LLM_PROVIDER
    use_code_gen = (LLM_PROVIDER == "anthropic" and _is_llm_available())

    if use_code_gen:
        logger.info("使用 Claude 直生代码模式")
        result = run_code_gen_pipeline(
            problem_text=problem_text,
            problem_image_path=problem_image or "",
            grade_level=grade_level,
            problem_type=problem_type.split("（")[0] if "（" in problem_type else problem_type,
        )
        # 如果代码直生模式失败，降级到 JSON 模式
        if not result.get("success") and not result.get("manim_code"):
            logger.warning("代码直生模式失败，降级到 JSON 模式")
            result = run_full_pipeline(
                problem_text=problem_text,
                problem_image_path=problem_image or "",
                grade_level=grade_level,
                problem_type=problem_type.split("（")[0] if "（" in problem_type else problem_type,
            )
    else:
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
    支持 Anthropic Claude 原生 API
    """
    from config import LLM_PROVIDER, LLM_BASE_URL

    # Anthropic Claude 原生 API：检查 API Key 是否有效
    if LLM_PROVIDER == "anthropic":
        from config import LLM_API_KEY
        if not LLM_API_KEY or LLM_API_KEY in ("your_api_key_here", "your-api-key", ""):
            logger.warning("Anthropic API Key 未配置")
            return False
        # 尝试轻量调用验证连通性
        try:
            from parser.llm_engine import call_llm_raw
            result = call_llm_raw("test", "hi")
            if result:
                logger.info("Anthropic API 连接成功")
                return True
        except Exception as e:
            logger.warning(f"Anthropic API 连接失败: {e}")
            return False

    # 远程 API（OpenAI 兼容）：检查 API Key 是否有效
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
