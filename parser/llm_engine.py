"""
============================================================
MathAnimAI — LLM大模型调用引擎
功能：
  1. OpenAI兼容API调用（支持DeepSeek/通义千问/任意兼容端点）
  2. Anthropic Claude 原生API调用（支持 Claude Code 中转站）
  3. 自动重试 + 指数退避
  4. JSON输出校验 + 错误捕获
  5. 返回标准化的 ProblemScript 对象
  6. Claude 直生代码模式 — generate_manim_code() 直接生成 Manim 源码
============================================================
"""

import json
import re
import time
import logging
from typing import Optional
from dataclasses import dataclass, field
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import (
    LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_MAX_TOKENS,
    LLM_TEMPERATURE, LLM_RETRY_TIMES, LLM_RETRY_BACKOFF, LLM_PROVIDER,
)
from parser.schema import ProblemScript, ProblemType, AnimationSettings, Step, AnimationType

# 日志
logger = logging.getLogger("MathAnimAI.LLM")


# ================================================================
# OpenAI兼容客户端（单例模式）
# ================================================================
_client: Optional[OpenAI] = None
_anthropic_client = None  # Anthropic原生客户端


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


def get_anthropic_client():
    """获取Anthropic原生客户端实例（懒加载）"""
    global _anthropic_client
    if _anthropic_client is None:
        try:
            from anthropic import Anthropic
            # Anthropic SDK 会在 base_url 后追加 /v1/messages
            # 如果 LLM_BASE_URL 已包含 /v1，需要去掉以避免 /v1/v1/messages
            base_url = LLM_BASE_URL
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]
            _anthropic_client = Anthropic(
                api_key=LLM_API_KEY,
                base_url=base_url,
                timeout=120.0,
            )
        except ImportError:
            logger.error("anthropic SDK 未安装，请运行: pip install anthropic")
            raise
    return _anthropic_client


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
# 支持 OpenAI 兼容 API 和 Anthropic 原生 API
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
    model_name = model or LLM_MODEL
    temp = temperature if temperature is not None else LLM_TEMPERATURE

    # 根据 LLM_PROVIDER 选择调用方式
    if LLM_PROVIDER == "anthropic":
        return _call_anthropic(system_prompt, user_prompt, model_name, temp)
    else:
        return _call_openai_compatible(system_prompt, user_prompt, model_name, temp)


def _call_anthropic(
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    temperature: float,
) -> ProblemScript:
    """Anthropic Claude 原生 API 调用"""
    client = get_anthropic_client()

    logger.info(f"调用 Anthropic Claude: model={model_name}, temperature={temperature}")
    start_time = time.time()

    try:
        # Claude 原生 API 调用
        # 注意：Claude 不支持 response_format，需要在 system_prompt 里约束 JSON 输出
        response = client.messages.create(
            model=model_name,
            max_tokens=LLM_MAX_TOKENS,
            temperature=temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )

        elapsed = time.time() - start_time
        raw_text = response.content[0].text if response.content else ""
        logger.info(f"LLM响应完成，耗时{elapsed:.1f}s，长度{len(raw_text)}字符")

        # 后续处理和 OpenAI 兼容接口相同
        return _process_llm_response(raw_text, user_prompt, elapsed)

    except Exception as e:
        logger.error(f"Anthropic API调用异常: {type(e).__name__}: {e}")
        raise


def _call_openai_compatible(
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    temperature: float,
) -> ProblemScript:
    """OpenAI 兼容 API 调用（原有逻辑）"""
    client = get_client()

    logger.info(f"调用 LLM (OpenAI兼容): model={model_name}, temperature={temperature}")
    start_time = time.time()

    try:
        # 发起API调用
        kwargs = dict(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=LLM_MAX_TOKENS,
        )
        # 只有非 Ollama 本地模型才尝试 response_format
        if LLM_PROVIDER not in ("ollama",):
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)

        elapsed = time.time() - start_time
        raw_text = response.choices[0].message.content or ""
        logger.info(f"LLM响应完成，耗时{elapsed:.1f}s，长度{len(raw_text)}字符")

        return _process_llm_response(raw_text, user_prompt, elapsed)

    except Exception as e:
        logger.error(f"OpenAI兼容API调用异常: {type(e).__name__}: {e}")
        raise


def _process_llm_response(raw_text: str, user_prompt: str, elapsed: float) -> ProblemScript:
    """
    处理 LLM 返回文本：提取JSON → 校验 → 返回 ProblemScript
    OpenAI 和 Anthropic 共用此函数
    """
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

    # 计算token消耗（Anthropic 格式和 OpenAI 格式不同）
    # Anthropic 在 response.usage, OpenAI 在 response.usage
    # 这里无法访问 response，所以跳过

    return script


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
    model_name = model or LLM_MODEL

    if LLM_PROVIDER == "anthropic":
        client = get_anthropic_client()
        response = client.messages.create(
            model=model_name,
            max_tokens=512,
            temperature=0.1,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text if response.content else ""
    else:
        client = get_client()
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


# ================================================================
# Claude 直生代码模式 — generate_manim_code()
# ================================================================

@dataclass
class GeneratedCode:
    """Claude 直生代码的结果容器"""
    scenes: list[dict] = field(default_factory=list)
    manim_code: str = ""
    raw_response: str = ""
    success: bool = False
    error: str = ""

    @property
    def scene_count(self) -> int:
        return len(self.scenes)

    def get_narrations(self) -> list[dict]:
        """获取所有幕的配音文本（供 TTS 使用）"""
        return [
            {
                "scene_num": s.get("scene_num", i + 1),
                "name": s.get("name", f"第{s.get('scene_num', i+1)}幕"),
                "narration": s.get("narration", ""),
            }
            for i, s in enumerate(self.scenes)
        ]


def generate_manim_code(
    problem_text: str,
    grade_level: str = "初中",
    problem_type: str = "auto",
    model: str = None,
) -> GeneratedCode:
    """
    Claude 直生代码模式：调用 Claude 直接生成完整的 Manim 源码。

    与 call_llm() 的区别：
    - call_llm() 生成 JSON 中间格式（ProblemScript），再由 builder.py 转为代码
    - generate_manim_code() 直接生成可运行的 Manim Python 代码

    Args:
        problem_text: 题目文本
        grade_level: 学段
        problem_type: 题型
        model: 模型名（默认使用配置值）

    Returns:
        GeneratedCode: 包含 scenes 列表和 manim_code 字符串
    """
    from parser.code_gen_prompt import SYSTEM_PROMPT, get_user_prompt

    model_name = model or LLM_MODEL
    user_prompt = get_user_prompt(problem_text, grade_level, problem_type)

    result = GeneratedCode()

    # 代码生成需要更大的 max_tokens
    code_gen_max_tokens = max(LLM_MAX_TOKENS, 16384)

    logger.info(f"调用 Claude 直生代码: model={model_name}, max_tokens={code_gen_max_tokens}")
    start_time = time.time()

    try:
        if LLM_PROVIDER == "anthropic":
            client = get_anthropic_client()
            response = client.messages.create(
                model=model_name,
                max_tokens=code_gen_max_tokens,
                temperature=LLM_TEMPERATURE,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw_text = response.content[0].text if response.content else ""
        else:
            client = get_client()
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=LLM_TEMPERATURE,
                max_tokens=code_gen_max_tokens,
            )
            raw_text = response.choices[0].message.content or ""

        elapsed = time.time() - start_time
        logger.info(f"Claude 代码生成完成，耗时{elapsed:.1f}s，长度{len(raw_text)}字符")

        result.raw_response = raw_text

        # 解析 JSON 响应
        parsed = _parse_code_gen_response(raw_text)
        if parsed is None:
            result.error = "无法从 LLM 响应中解析 JSON"
            logger.error(result.error)
            return result

        result.scenes = parsed.get("scenes", [])
        result.manim_code = parsed.get("manim_code", "")
        result.success = bool(result.manim_code and result.scenes)

        if result.success:
            logger.info(f"代码生成成功: {len(result.scenes)}幕, 代码{len(result.manim_code)}字符")
        else:
            result.error = "scenes 或 manim_code 为空"
            logger.warning(result.error)

        return result

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Claude 代码生成异常({elapsed:.1f}s): {type(e).__name__}: {e}")
        result.error = str(e)
        return result


def _parse_code_gen_response(raw_text: str) -> Optional[dict]:
    """
    从 LLM 响应文本中解析 JSON（包含 scenes 和 manim_code）。

    处理多种情况：
    1. 纯 JSON 文本
    2. 被 ```json ... ``` 代码块包裹
    3. JSON 前后有多余文本
    4. manim_code 中包含嵌套的代码块（需要特殊处理）
    """
    if not raw_text or not raw_text.strip():
        return None

    text = raw_text.strip()

    # 策略1：尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 策略2：提取 ```json ... ``` 代码块
    # 注意：manim_code 内部可能也有 ```python ... ```，需要匹配最外层的 json 块
    json_block_pattern = r'```json\s*\n([\s\S]*?)\n```'
    matches = list(re.finditer(json_block_pattern, text))
    if matches:
        # 取最后一个匹配（通常是完整的 JSON）
        for match in reversed(matches):
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

    # 策略3：提取第一个 { 到最后一个 } 之间的内容
    # 但要小心 manim_code 中的嵌套花括号
    # 找到最外层的 JSON 对象
    start = text.find('{')
    if start == -1:
        return None

    # 从后往前找最后一个 }
    end = text.rfind('}')
    if end == -1 or end <= start:
        return None

    json_text = text[start:end + 1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        pass

    # 策略4：尝试修复常见的 JSON 问题
    # 有时 Claude 会在 manim_code 字符串中包含未转义的特殊字符
    # 尝试逐行解析，找到 "manim_code": "..." 的值
    try:
        return _extract_code_and_scenes(text)
    except Exception:
        pass

    logger.error(f"所有 JSON 解析策略均失败，原始文本前500字: {text[:500]}")
    return None


def _extract_code_and_scenes(text: str) -> Optional[dict]:
    """
    降级解析：分别提取 scenes 和 manim_code。

    当标准 JSON 解析失败时（通常是因为 manim_code 中的转义问题），
    使用正则表达式分别提取两个字段。
    """
    result = {"scenes": [], "manim_code": ""}

    # 提取 scenes 数组
    scenes_match = re.search(r'"scenes"\s*:\s*\[', text)
    if scenes_match:
        # 找到 scenes 数组的开始和结束
        bracket_start = scenes_match.end() - 1
        depth = 0
        end_pos = bracket_start
        for i in range(bracket_start, len(text)):
            if text[i] == '[':
                depth += 1
            elif text[i] == ']':
                depth -= 1
                if depth == 0:
                    end_pos = i + 1
                    break

        scenes_text = text[bracket_start:end_pos]
        try:
            result["scenes"] = json.loads(scenes_text)
        except json.JSONDecodeError:
            # 尝试清理后解析
            try:
                scenes_text = scenes_text.replace('\n', ' ').replace('  ', ' ')
                result["scenes"] = json.loads(scenes_text)
            except json.JSONDecodeError:
                logger.warning("scenes 数组解析失败")

    # 提取 manim_code 字符串
    # 寻找 "manim_code": " 模式
    code_match = re.search(r'"manim_code"\s*:\s*"', text)
    if code_match:
        code_start = code_match.end()
        # 从 code_start 开始，找到匹配的结束引号
        # 需要处理转义的引号和反斜杠
        code_chars = []
        i = code_start
        while i < len(text):
            ch = text[i]
            if ch == '\\' and i + 1 < len(text):
                next_ch = text[i + 1]
                if next_ch == 'n':
                    code_chars.append('\n')
                elif next_ch == 't':
                    code_chars.append('\t')
                elif next_ch == '"':
                    code_chars.append('"')
                elif next_ch == '\\':
                    code_chars.append('\\')
                elif next_ch == "'":
                    code_chars.append("'")
                else:
                    code_chars.append(ch + next_ch)
                i += 2
            elif ch == '"':
                # 可能是结束引号
                break
            else:
                code_chars.append(ch)
                i += 1

        result["manim_code"] = ''.join(code_chars)

    if result["scenes"] or result["manim_code"]:
        return result

    return None
