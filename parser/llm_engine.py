"""
============================================================
MathAnimAI — LLM大模型调用引擎
功能：
  1. OpenAI兼容API调用（支持DeepSeek/通义千问/任意兼容端点）
  2. 自动重试 + 指数退避
  3. JSON输出校验 + 错误捕获
  4. 返回标准化的 ProblemScript 对象
============================================================
"""

import json
import re
import time
import logging
from typing import Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import (
    LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_MAX_TOKENS,
    LLM_TEMPERATURE, LLM_RETRY_TIMES, LLM_RETRY_BACKOFF
)
from parser.schema import ProblemScript, ProblemType, AnimationSettings, Step, AnimationType

# 日志
logger = logging.getLogger("MathAnimAI.LLM")


# ================================================================
# OpenAI兼容客户端（单例模式）
# ================================================================
_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    """获取OpenAI兼容客户端实例"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            timeout=120.0  # 2分钟超时
        )
    return _client


# ================================================================
# JSON提取工具函数
# ================================================================
def extract_json_from_text(text: str) -> str:
    """
    从LLM返回文本中提取JSON
    处理常见情况：被markdown代码块包裹、前后有多余文本
    """
    # 尝试匹配 ```json ... ``` 代码块
    json_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    match = re.search(json_block_pattern, text)
    if match:
        return match.group(1).strip()

    # 尝试匹配第一个 { 到最后一个 } 之间的内容
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1].strip()

    # 返回原文
    return text.strip()


def validate_json_structure(data: dict) -> list[str]:
    """验证JSON结构完整性，返回缺失字段列表"""
    required_top = ["problem_type", "grade_level", "problem_text", "steps"]
    missing = [f for f in required_top if f not in data]
    if "steps" in data:
        if not isinstance(data["steps"], list) or len(data["steps"]) == 0:
            missing.append("steps必须是非空数组")
        else:
            for i, step in enumerate(data["steps"]):
                if not isinstance(step, dict):
                    missing.append(f"steps[{i}]不是有效的对象")
                    continue
                step_required = ["step_number", "title", "text", "animation_type"]
                for f in step_required:
                    if f not in step:
                        missing.append(f"steps[{i}]缺少字段: {f}")
    return missing


def normalize_steps(data: dict) -> dict:
    """
    规范化 steps 数组：将字符串类型的 step 转换为结构化对象
    Ollama 等小模型偶尔将 step 输出为纯字符串，此函数自动修复
    """
    if "steps" not in data or not isinstance(data["steps"], list):
        return data

    normalized = []
    valid_animations = {
        "text_slide_in", "title_display", "draw_shape", "draw_dashed_line",
        "draw_circle", "draw_arc", "highlight", "highlight_region",
        "mark_angle", "mark_right_angle", "label_vertex", "label_side",
        "label_text", "plot_function", "plot_coordinate", "plot_point",
        "draw_bar_chart", "draw_pie_chart", "draw_segment_diagram",
        "wait", "transform",
    }

    for i, step in enumerate(data["steps"]):
        if isinstance(step, str):
            # 字符串 → 结构化对象
            logger.info(f"规范化 steps[{i}]：字符串 → 对象")
            step_title = step[:15].replace("\n", " ")
            normalized.append({
                "step_number": i + 1,
                "title": step_title,
                "text": step,
                "animation_type": "text_slide_in",
                "position": "below",
                "voice_text": step,
                "math_expr": "",
                "config": {},
                "sub_steps": [],
            })
        elif isinstance(step, dict):
            # 补全缺失字段
            step.setdefault("step_number", i + 1)
            step.setdefault("title", step.get("text", f"步骤{i+1}")[:15])
            step.setdefault("text", "")
            if step.get("animation_type") not in valid_animations:
                step["animation_type"] = "text_slide_in"
            step.setdefault("position", "below")
            step.setdefault("voice_text", step.get("text", ""))
            step.setdefault("math_expr", "")
            step.setdefault("config", {})
            step.setdefault("sub_steps", [])
            normalized.append(step)
        else:
            logger.warning(f"跳过非法 steps[{i}]: type={type(step).__name__}")

    data["steps"] = normalized
    return data


# ================================================================
# LLM调用核心函数（带重试和校验）
# ================================================================
@retry(
    stop=stop_after_attempt(LLM_RETRY_TIMES),
    wait=wait_exponential(multiplier=LLM_RETRY_BACKOFF, min=1, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, ValueError))
)
def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = None,
) -> ProblemScript:
    """
    调用LLM生成动画脚本

    Args:
        system_prompt: 系统提示词（题型专用约束）
        user_prompt: 用户提示词（题目内容）
        model: 模型名，默认使用配置值
        temperature: 温度参数，默认使用配置值

    Returns:
        ProblemScript: 经过Pydantic校验的动画脚本对象

    Raises:
        ValueError: JSON解析或校验失败
        ConnectionError: API连接失败
        TimeoutError: API超时
    """
    client = get_client()
    model_name = model or LLM_MODEL
    temp = temperature if temperature is not None else LLM_TEMPERATURE

    logger.info(f"调用LLM: model={model_name}, temperature={temp}")
    start_time = time.time()

    try:
        # 发起API调用
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temp,
            max_tokens=LLM_MAX_TOKENS,
            # 使用JSON模式约束输出（如果模型支持）
            response_format={"type": "json_object"},
        )

        elapsed = time.time() - start_time
        raw_text = response.choices[0].message.content or ""
        logger.info(f"LLM响应完成，耗时{elapsed:.1f}s，长度{len(raw_text)}字符")

        # 提取JSON
        json_text = extract_json_from_text(raw_text)

        # 第一轮：尝试解析为dict
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.debug(f"原始文本前200字: {raw_text[:200]}")
            raise ValueError(f"LLM返回内容无法解析为JSON: {e}")

        # 第二轮：结构完整性校验并规范化
        missing = validate_json_structure(data)
        if missing:
            logger.warning(f"JSON结构缺失字段: {missing}")
            # 尝试补全默认值
            if "problem_type" not in data:
                data["problem_type"] = "equation"
            if "grade_level" not in data:
                data["grade_level"] = "初中"
            if "problem_text" not in data:
                data["problem_text"] = user_prompt[-200:]

        # 规范化 steps（字符串→对象）
        data = normalize_steps(data)

        # 预处理 problem_type：中英文映射
        cn_type_map = {
            "方程": "equation", "方程式": "equation",
            "几何": "geometry", "几何题": "geometry",
            "函数": "function",
            "应用题": "word_problem",
            "分数": "fraction",
        }
        raw_pt = str(data.get("problem_type", ""))
        if raw_pt in cn_type_map:
            data["problem_type"] = cn_type_map[raw_pt]
        elif raw_pt and raw_pt not in ("equation", "geometry", "function", "word_problem", "fraction"):
            # 模糊匹配
            geo_hints = ["三角形", "四边形", "正方形", "长方形", "矩形", "圆", "角度", "勾股", "边", "几何"]
            if any(h in raw_pt for h in geo_hints):
                data["problem_type"] = "geometry"

        # 第三轮：Pydantic模型校验（枚举自动fallback）
        try:
            script = ProblemScript.model_validate(data)
            logger.info(f"Pydantic校验通过，共{len(script.steps)}个步骤")
        except Exception as e:
            logger.warning(f"Pydantic校验告警: {e}，尝试宽松解析")
            # model_construct 跳过校验，但需手动处理嵌套对象
            try:
                # 预处理嵌套对象
                if "settings" in data and isinstance(data["settings"], dict):
                    data["settings"] = AnimationSettings(**data["settings"])
                if "steps" in data and isinstance(data["steps"], list):
                    data["steps"] = [Step(**s) if isinstance(s, dict) else s for s in data["steps"]]
                script = ProblemScript.model_construct(**data)
            except Exception as e2:
                logger.error(f"宽松解析也失败: {e2}，使用最小脚本")
                # 终极回退：只保留必要字段
                steps_raw = data.get("steps", [])
                steps_objs = []
                for i, s in enumerate(steps_raw):
                    if isinstance(s, dict):
                        steps_objs.append(Step(
                            step_number=i+1,
                            title=s.get("title", f"步骤{i+1}"),
                            text=s.get("text", str(s)),
                            animation_type=AnimationType.TEXT_SLIDE_IN,
                            voice_text=s.get("voice_text", s.get("text", "")),
                        ))
                script = ProblemScript.model_construct(
                    problem_type=data.get("problem_type", "equation"),
                    grade_level=data.get("grade_level", "初中"),
                    problem_text=data.get("problem_text", ""),
                    final_answer=data.get("final_answer", ""),
                    steps=steps_objs,
                )
            logger.info("宽松解析成功")

        # 计算token消耗
        usage = response.usage
        if usage:
            logger.info(f"Token消耗 — prompt: {usage.prompt_tokens}, "
                       f"completion: {usage.completion_tokens}, "
                       f"total: {usage.total_tokens}")

        return script

    except (ValueError, json.JSONDecodeError) as e:
        # 这些错误会触发重试
        logger.warning(f"调用失败，将重试: {e}")
        raise ValueError(str(e)) from e

    except Exception as e:
        logger.error(f"LLM调用异常: {type(e).__name__}: {e}")
        raise


# ================================================================
# 轻量调用（不执行Pydantic严格校验，用于流式/快速测试）
# ================================================================
def call_llm_raw(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
) -> str:
    """
    轻量LLM调用，直接返回原始文本
    用于不需要结构化输出的场景（如题目类型判断）
    """
    client = get_client()
    model_name = model or LLM_MODEL

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        max_tokens=512,
    )

    return response.choices[0].message.content or ""


# ================================================================
# 题目类型自动识别
# ================================================================
def detect_problem_type(problem_text: str) -> str:
    """
    自动识别题目类型（不依赖LLM的快速判断）
    作为LLM自动分类的降级方案
    """
    text_lower = problem_text.lower()

    # 几何相关关键词
    geo_keywords = ["三角形", "四边形", "正方形", "长方形", "矩形", "圆", "角度",
                    "面积", "周长", "边长", "垂线", "平行", "直角", "勾股"]
    if any(kw in problem_text for kw in geo_keywords):
        return "geometry"

    # 函数相关关键词
    func_keywords = ["函数", "图像", "抛物线", "对称轴", "顶点", "单调", "坐标",
                     "一次函数", "二次函数", "正比例", "反比例", "y=", "f(x)"]
    if any(kw in problem_text for kw in func_keywords):
        return "function"

    # 方程相关关键词
    eq_keywords = ["解方程", "求x", "求y", "方程", "未知数", "=", "一元二次"]
    if any(kw in problem_text for kw in eq_keywords):
        return "equation"

    # 分数相关关键词
    frac_keywords = ["分数", "几分之", "分母", "分子", "约分", "通分", "/"]
    if any(kw in problem_text for kw in frac_keywords):
        return "fraction"

    # 默认应用题
    return "word_problem"
