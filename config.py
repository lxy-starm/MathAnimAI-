"""
============================================================
MathAnimAI — 全局统一配置文件
所有颜色、字号、动画时长、画布边距、分辨率等参数
集中在此管理，一处修改全局生效。
============================================================
"""

import os
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()


# ================================================================
# 一、LLM大模型配置
# ================================================================
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # ollama | deepseek | openai | custom
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
LLM_MAX_TOKENS = 4096
LLM_TEMPERATURE = 0.3  # 数学题需要稳定输出，温度不宜过高
LLM_RETRY_TIMES = 3  # API调用失败重试次数
LLM_RETRY_BACKOFF = 2  # 重试退避因子


# ================================================================
# 二、动画渲染分辨率
# ================================================================
RENDER_QUALITY = os.getenv("RENDER_QUALITY", "HD")
if RENDER_QUALITY == "HD":
    RESOLUTION_WIDTH = 1920
    RESOLUTION_HEIGHT = 1080
    FRAME_RATE = 60
    QUALITY_FLAG = "h"  # manim -qh
else:
    RESOLUTION_WIDTH = 1280
    RESOLUTION_HEIGHT = 720
    FRAME_RATE = 30
    QUALITY_FLAG = "m"  # manim -qm


# ================================================================
# 三、全局配色方案（参考 MathLens 模板，深色背景 + 亮色配色）
# ================================================================
class Colors:
    """全局统一配色常量 — 深色教学风格"""
    # 画布底色 — 深蓝夜色背景（参考模板 #1a1a2e）
    BG = "#1a1a2e"

    # 基础图形实线 — 亮青色（主色，参考模板 #4ecca3）
    PRIMARY = "#4ecca3"

    # 辅助线虚线 — 红色（辅助色，参考模板 #e94560）
    SECONDARY = "#e94560"
    DASHED = "#e94560"

    # 顶点标记 — 黄色（高亮色，参考模板 #ffc107）
    VERTEX = "#ffc107"
    HIGHLIGHT = "#ffc107"

    # 已知条件文字 — 亮青色
    KNOWN = "#4ecca3"

    # 推导结论文字 — 亮青色
    RESULT = "#4ecca3"

    # 重点高亮底色 — 黄色
    HIGHLIGHT_BG = "#ffc107"
    HIGHLIGHT_BORDER = "#ffc107"

    # 文字底色 — 深紫色（用于需要背景的场景）
    TEXT_BG = "#2a2a4e"

    # 标题文字色 — 白色
    TITLE_TEXT = "#ffffff"

    # 步骤文字色 — 白色
    STEP_TEXT = "#ffffff"

    # 标注文字色 — 白色
    LABEL_TEXT = "#ffffff"

    # 通用文字色 — 白色
    TEXT = "#ffffff"

    # 次要文字色 — 浅灰
    TEXT_SECONDARY = "#aaaaaa"

    # 白色
    WHITE = "#ffffff"
    # 黑色
    BLACK = "#1a1a2e"

    # 网格线色
    GRID = "#2a2a4e"
    AXIS = "#444466"

    # 饼图分块色（亮色系，适配深色背景）
    PIE_COLORS = ["#4ecca3", "#e94560", "#ffc107", "#ff6b6b",
                  "#4ecdc4", "#ffe66d", "#a8e6cf", "#ff8b94"]

    # 柱状图颜色（亮色系）
    BAR_COLORS = ["#4ecca3", "#e94560", "#ffc107", "#ff6b6b"]

    # 函数曲线颜色
    FUNCTION_CURVE = "#e94560"
    FUNCTION_SECONDARY = "#4ecca3"


# ================================================================
# 四、字体统一规范（参考模板，增大字号提升可读性）
# ================================================================
FONT_FAMILY = "Microsoft YaHei"  # 圆润无衬线中文字体

# 分层字号（参考模板：标题60, 字幕36-40, 步骤36, 标签28）
FONT_TITLE = 44      # 标题文字（模板用60，但我们的标题是题干需要稍小）
FONT_STEP = 34       # 步骤讲解（模板用36）
FONT_LABEL = 28      # 标注文字（模板用28-32）
FONT_ANNOTATION = 22 # 小字注释（模板用24）
FONT_SUBTITLE = 36   # 字幕专用字号（模板用36-40）
FONT_CONCLUSION = 42 # 结论公式字号（模板用48）

# 数学公式字号
MATH_FONT_SIZE = 34


# ================================================================
# 五、动画统一时长（参考模板：简洁明快，避免过长等待）
# ================================================================
ANIMATION_DURATION = float(os.getenv("ANIMATION_DURATION", "1.0"))
SLIDE_DURATION = float(os.getenv("SLIDE_DURATION", "0.5"))

# 各类型动画具体时长（参考模板 script_example.py）
DURATION_CREATE = 1.0        # 图形逐笔绘制（模板 run_time=1.0）
DURATION_SLIDE_IN = 0.5      # 文字淡入（模板 FadeIn run_time=0.5）
DURATION_HIGHLIGHT = 0.8     # 高亮渐变（模板 0.4+0.4=0.8）
DURATION_TRANSITION = 0.5    # 步骤之间过渡
DURATION_WRITE = 0.5         # 逐字写入（模板 run_time=0.5）
DURATION_GROW = 0.8          # 图形生长
DURATION_FADE = 0.5          # 渐变（模板 FadeIn/FadeOut run_time=0.5）
DURATION_WAIT_SHORT = 0.3    # 短停顿
DURATION_WAIT_LONG = 1.0     # 长停顿
DURATION_SHIFT = 0.5         # 位置偏移


# ================================================================
# 六、画布布局参数
# ================================================================
CANVAS_MARGIN_TOP = 1.0     # 顶部留白
CANVAS_MARGIN_BOTTOM = 1.0   # 底部留白
CANVAS_MARGIN_LEFT = 1.5     # 左侧留白
CANVAS_MARGIN_RIGHT = 1.5    # 右侧留白

# 文字排版间距
TEXT_LINE_SPACING = 0.4      # 行间距（Manim单位）
TEXT_STEP_OFFSET = 0.3       # 步骤之间额外间距

# Manim 画布可视区域边界（HD 1920x1080，约 14.22 x 8.0 单位）
CANVAS_MAX_WIDTH = 13.0      # 文本最大宽度（留边距）
CANVAS_TOP_Y = 3.6           # 顶部边界（标题区域）
CANVAS_BOTTOM_Y = -3.8       # 底部边界（字幕区域）
MAX_STACK_STEPS = 6          # 超过此步骤数时，自动缩放旧内容腾空间

# 旧内容缩移参数（新步骤出现时，旧内容微缩上移）
OLD_CONTENT_SCALE = 0.85     # 旧内容缩放比例
OLD_CONTENT_SHIFT_UP = 0.3   # 旧内容上移距离

# 侧边栏布局参数（讲解完后内容缩放到左侧）
LEFT_PANEL_X = -5.5          # 左侧面板 x 坐标
LEFT_PANEL_TOP_Y = 2.5       # 左侧面板顶部 y 坐标
LEFT_PANEL_SCALE = 0.45      # 侧边栏元素缩放比例
LEFT_PANEL_SPACING = 0.25    # 侧边栏元素垂直间距
LEFT_PANEL_MAX_ITEMS = 8     # 侧边栏最多容纳元素数（超过则进一步缩小）
CENTER_CONTENT_Y = 0.5       # 中央内容基准 y 坐标
CENTER_CONTENT_MAX_WIDTH = 10.0  # 中央内容最大宽度

# 音频时长估算参数（仅当无法获取 TTS 真实时长时作为兜底）
AUDIO_CHARS_PER_SEC = 5.0    # TTS 中文字数每秒（晓晓语音实测约 4.8-5.0 字/秒）


# ================================================================
# 七、TTS语音配置
# ================================================================
TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
TTS_RATE = os.getenv("TTS_RATE", "+0%")
TTS_PITCH = "+0Hz"


# ================================================================
# 八、视频输出配置
# ================================================================
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
CACHE_DIR = os.getenv("CACHE_DIR", "./cache")
OUTPUT_VIDEO_DIR = os.path.join(OUTPUT_DIR, "videos")
OUTPUT_AUDIO_DIR = os.path.join(OUTPUT_DIR, "audio")
OUTPUT_SUBTITLE_DIR = os.path.join(OUTPUT_DIR, "subtitles")

# 视频片头片尾配置（秒）
INTRO_DURATION = 3.0  # 片头时长
OUTRO_DURATION = 2.0  # 片尾时长

# 字幕配置（参考模板：底部纯文字，无背景框）
SUBTITLE_FONT_SIZE = 36
SUBTITLE_BG_OPACITY = 0.0  # 深色背景不需要字幕背景框
SUBTITLE_POSITION = "bottom"  # 字幕位置


# ================================================================
# 九、Gradio Web UI配置
# ================================================================
GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7060"))
GRADIO_HOST = os.getenv("GRADIO_HOST", "127.0.0.1")
GRADIO_SHARE = os.getenv("GRADIO_SHARE", "False").lower() == "true"

# UI主题色
UI_PRIMARY_COLOR = "#3498DB"
UI_SECONDARY_COLOR = "#2ECC71"
UI_BG_COLOR = "#F5F7FA"


# ================================================================
# 十、存储数据库配置
# ================================================================
DB_PATH = os.path.join(OUTPUT_DIR, "history.db")


# ================================================================
# 十一、路径工厂函数
# ================================================================
def ensure_dirs():
    """确保所有输出目录存在"""
    for d in [OUTPUT_DIR, CACHE_DIR, OUTPUT_VIDEO_DIR,
              OUTPUT_AUDIO_DIR, OUTPUT_SUBTITLE_DIR]:
        os.makedirs(d, exist_ok=True)


def get_timestamp():
    """生成时间戳字符串，用于文件命名"""
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# 启动时自动创建目录
ensure_dirs()
