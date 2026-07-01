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
# 三、全局配色方案（柔和教学风，禁止高饱和刺眼颜色）
# ================================================================
class Colors:
    """全局统一配色常量"""
    # 画布底色 — 柔和浅灰，替换纯白刺眼背景
    BG = "#F0F2F5"

    # 基础图形实线 — 柔和蓝
    PRIMARY = "#3498DB"

    # 辅助线虚线 — 中性灰
    DASHED = "#7F8C8D"

    # 顶点标记 — 温和红
    VERTEX = "#E74C3C"

    # 已知条件文字 — 深蓝
    KNOWN = "#2980B9"

    # 推导结论文字 — 柔和绿
    RESULT = "#27AE60"

    # 重点高亮底色 — 浅黄渐变扫光
    HIGHLIGHT_BG = "#FFF3CD"
    HIGHLIGHT_BORDER = "#FFC107"

    # 文字底色 — 圆角半透明白
    TEXT_BG = "#FFFFFFCC"

    # 标题文字色 — 深灰
    TITLE_TEXT = "#2C3E50"

    # 步骤文字色 — 中灰
    STEP_TEXT = "#34495E"

    # 标注文字色 — 深灰
    LABEL_TEXT = "#2C3E50"

    # 白色
    WHITE = "#FFFFFF"
    # 黑色
    BLACK = "#1A1A2E"

    # 饼图分块色
    PIE_COLORS = ["#3498DB", "#E74C3C", "#27AE60", "#F39C12",
                  "#9B59B6", "#1ABC9C", "#E67E22", "#2ECC71"]

    # 柱状图颜色
    BAR_COLORS = ["#3498DB", "#2ECC71", "#E74C3C", "#F39C12"]

    # 函数曲线颜色
    FUNCTION_CURVE = "#E74C3C"
    FUNCTION_SECONDARY = "#3498DB"


# ================================================================
# 四、字体统一规范
# ================================================================
FONT_FAMILY = "Microsoft YaHei"  # 圆润无衬线中文字体

# 分层字号
FONT_TITLE = 36      # 标题文字
FONT_STEP = 26       # 步骤讲解
FONT_LABEL = 20      # 标注文字
FONT_ANNOTATION = 16  # 小字注释

# 数学公式字号
MATH_FONT_SIZE = 32


# ================================================================
# 五、动画统一时长
# ================================================================
ANIMATION_DURATION = float(os.getenv("ANIMATION_DURATION", "1.0"))
SLIDE_DURATION = float(os.getenv("SLIDE_DURATION", "0.8"))

# 各类型动画具体时长
DURATION_CREATE = 1.0        # 图形逐笔绘制
DURATION_SLIDE_IN = 0.8      # 文字滑入+淡入
DURATION_HIGHLIGHT = 1.2     # 高亮渐变扫光
DURATION_TRANSITION = 0.5    # 步骤之间过渡
DURATION_WRITE = 0.6         # 逐字写入
DURATION_GROW = 0.8          # 图形生长
DURATION_FADE = 1.0          # 渐变
DURATION_WAIT_SHORT = 0.5    # 短停顿
DURATION_WAIT_LONG = 1.5     # 长停顿
DURATION_SHIFT = 0.6         # 位置偏移


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

# 字幕配置
SUBTITLE_FONT_SIZE = 24
SUBTITLE_BG_OPACITY = 0.6
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
