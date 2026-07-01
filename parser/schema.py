"""
============================================================
MathAnimAI — Pydantic 严格结构化数据模型
功能：
  1. 定义完整动画脚本 JSON 结构
  2. animation_type 枚举校验，非法值自动修正
  3. 支持题目解析 → 动画引擎的标准化数据流
============================================================
"""

from enum import Enum
from typing import Optional, Literal, Any
from pydantic import BaseModel, Field, field_validator


# ================================================================
# 合法动画类型枚举 — 全场景覆盖
# ================================================================
class AnimationType(str, Enum):
    """动画类型枚举，LLM必须从此列表中选取，非法值自动修正为 text_slide_in"""

    # 文本类
    TEXT_SLIDE_IN = "text_slide_in"          # 文字滑入+淡入
    TITLE_DISPLAY = "title_display"           # 标题展示

    # 图形绘制类
    DRAW_SHAPE = "draw_shape"                # 绘制基本图形（逐笔Create）
    DRAW_DASHED_LINE = "draw_dashed_line"    # 绘制虚线辅助线
    DRAW_CIRCLE = "draw_circle"              # 绘制圆形
    DRAW_ARC = "draw_arc"                    # 绘制圆弧

    # 高亮标注类
    HIGHLIGHT = "highlight"                  # 高亮渐变扫光
    HIGHLIGHT_REGION = "highlight_region"    # 区域高亮

    # 角度标注类
    MARK_ANGLE = "mark_angle"               # 角度弧线标注
    MARK_RIGHT_ANGLE = "mark_right_angle"    # 直角符号标注

    # 标签类
    LABEL_VERTEX = "label_vertex"            # 顶点字母标签
    LABEL_SIDE = "label_side"                # 边长标注
    LABEL_TEXT = "label_text"                # 通用文字标注

    # 函数图像类
    PLOT_FUNCTION = "plot_function"          # 绘制函数曲线
    PLOT_COORDINATE = "plot_coordinate"      # 绘制坐标系
    PLOT_POINT = "plot_point"               # 标注动点

    # 图表类
    DRAW_BAR_CHART = "draw_bar_chart"        # 绘制柱状图
    DRAW_PIE_CHART = "draw_pie_chart"        # 绘制饼图
    DRAW_SEGMENT_DIAGRAM = "draw_segment_diagram"  # 绘制线段图

    # 控制类
    WAIT = "wait"                            # 暂停等待
    TRANSFORM = "transform"                  # 图形变换

    @classmethod
    def _missing_(cls, value):
        """枚举值不存在时的fallback：任何非法animation_type自动修正为 text_slide_in"""
        return cls.TEXT_SLIDE_IN


# ================================================================
# 题目类型枚举
# ================================================================
class ProblemType(str, Enum):
    EQUATION = "equation"          # 方程
    GEOMETRY = "geometry"          # 几何
    FUNCTION = "function"          # 函数
    WORD_PROBLEM = "word_problem"  # 应用题
    FRACTION = "fraction"          # 分数

    @classmethod
    def _missing_(cls, value):
        """自动将中文题型名映射到英文枚举值"""
        if not isinstance(value, str):
            return cls.EQUATION
        v = value.strip()
        mapping = {
            "方程": cls.EQUATION, "方程式": cls.EQUATION,
            "几何": cls.GEOMETRY, "几何题": cls.GEOMETRY, "三角形": cls.GEOMETRY,
            "四边形": cls.GEOMETRY, "圆": cls.GEOMETRY, "角度": cls.GEOMETRY,
            "函数": cls.FUNCTION, "一次函数": cls.FUNCTION, "二次函数": cls.FUNCTION,
            "应用题": cls.WORD_PROBLEM, "行程": cls.WORD_PROBLEM, "工程": cls.WORD_PROBLEM,
            "分数": cls.FRACTION, "小数": cls.FRACTION,
        }
        for cn_key, enum_val in mapping.items():
            if cn_key in v:
                return enum_val
        # 包含常见几何关键词 → 几何
        geo_hints = ["三角形", "四边形", "正方形", "长方形", "矩形", "圆", "角度", "勾股", "边"]
        if any(h in v for h in geo_hints):
            return cls.GEOMETRY
        return cls.EQUATION  # 默认方程


# ================================================================
# 步骤内容位置枚举
# ================================================================
class StepPosition(str, Enum):
    BELOW = "below"
    ABOVE = "above"
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"


# ================================================================
# 动画全局设置
# ================================================================
class AnimationSettings(BaseModel):
    """动画全局参数"""
    duration: float = Field(default=1.0, description="动画默认时长（秒）")
    slide_duration: float = Field(default=0.8, description="切入动画时长（秒）")
    auto_advance: bool = Field(default=True, description="是否自动推进步骤")
    step_pause: float = Field(default=1.0, description="步骤间默认停顿（秒）")


# ================================================================
# 几何元素定义
# ================================================================
class GeoPoint(BaseModel):
    """二维坐标点"""
    x: float
    y: float
    label: str = ""


class GeoElement(BaseModel):
    """几何图形元素定义"""
    type: str = Field(
        ...,
        description="几何类型：triangle, quadrilateral, circle, line, arc, point"
    )
    points: list[list[float]] = Field(
        default_factory=list,
        description="顶点坐标列表 [[x1,y1], [x2,y2], ...]"
    )
    labels: list[str] = Field(
        default_factory=list,
        description="顶点标签，如 ['A','B','C']"
    )
    radius: float = Field(default=1.0, description="圆半径")
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="额外样式配置（颜色、线宽等）"
    )


# ================================================================
# 坐标系统配置
# ================================================================
class CoordinateConfig(BaseModel):
    """函数图像坐标系配置"""
    x_range: list[float] = Field(default=[-10, 10, 1])
    y_range: list[float] = Field(default=[-10, 10, 1])
    x_length: float = Field(default=10.0)
    y_length: float = Field(default=6.0)
    show_numbers: bool = Field(default=True)
    grid_opacity: float = Field(default=0.3)


# ================================================================
# 动画步骤定义（核心数据结构）
# ================================================================
class Step(BaseModel):
    """单个动画步骤"""
    step_number: int = Field(..., ge=1, description="步骤序号，从1开始")
    title: str = Field(..., description="步骤标题")
    text: str = Field(..., description="讲解文字")
    animation_type: AnimationType = Field(
        default=AnimationType.TEXT_SLIDE_IN,
        description="动画类型，非法值自动修正为text_slide_in"
    )
    target: str = Field(default="", description="目标元素标识符")
    position: StepPosition = Field(default=StepPosition.BELOW, description="内容排布位置")
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="额外参数：颜色、时长、坐标、公式等"
    )
    voice_text: str = Field(default="", description="TTS配音文本")
    math_expr: str = Field(default="", description="数学公式LaTeX")
    sub_steps: list[dict[str, Any]] = Field(
        default_factory=list,
        description="子步骤（用于方程多步推导等）"
    )


# ================================================================
# 完整题目动画脚本（顶层JSON结构）
# ================================================================
class ProblemScript(BaseModel):
    """完整题目动画脚本，parser输出 + animation输入的唯一数据结构"""
    # 基础信息
    problem_type: ProblemType = Field(..., description="题目类型")
    grade_level: str = Field(..., description="学段：小学/初中")
    problem_text: str = Field(..., description="原始题目文本")
    final_answer: str = Field(..., description="最终答案")

    # 视觉配置
    settings: AnimationSettings = Field(
        default_factory=AnimationSettings,
        description="动画全局设置"
    )

    # 几何/函数专用 — 底图元素（首次渲染后永久保留）
    base_figure: Optional[GeoElement] = Field(
        default=None,
        description="几何题基础图形定义"
    )
    coordinate_system: Optional[CoordinateConfig] = Field(
        default=None,
        description="函数题坐标系定义"
    )

    # 动画步骤 — 核心内容
    steps: list[Step] = Field(
        default_factory=list,
        description="逐步动画列表，顺序播放"
    )

    # 元信息
    created_at: str = Field(default="", description="创建时间戳")
    model_used: str = Field(default="", description="使用的大模型")

    @field_validator("steps")
    @classmethod
    def validate_steps_not_empty(cls, v):
        """验证至少有一个动画步骤"""
        if not v or len(v) == 0:
            raise ValueError("动画脚本至少需要一个步骤")
        # 检查步骤序号连续性
        for i, step in enumerate(v):
            if step.step_number != i + 1:
                step.step_number = i + 1  # 自动修正序号
        return v

    @field_validator("grade_level")
    @classmethod
    def validate_grade(cls, v):
        """验证学段合法"""
        valid_grades = ["小学", "初中", "高中"]
        if v not in valid_grades:
            return "初中"  # 默认初中
        return v

    def to_json_str(self) -> str:
        """序列化为JSON字符串"""
        return self.model_dump_json(indent=2, ensure_ascii=False)

    @classmethod
    def from_json_str(cls, json_str: str) -> "ProblemScript":
        """从JSON字符串解析，带容错处理"""
        try:
            return cls.model_validate_json(json_str)
        except Exception as e:
            raise ValueError(f"JSON解析失败: {e}")


# ================================================================
# 历史记录数据模型
# ================================================================
class HistoryRecord(BaseModel):
    """数据库历史记录映射"""
    id: int
    problem_text: str
    problem_type: str
    grade_level: str
    script_json: str
    video_path: str
    audio_path: str
    subtitle_path: str
    created_at: str
