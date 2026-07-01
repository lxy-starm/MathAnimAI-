# MathAnimAI — 数学教育动画智能体 运行说明

## 项目简介

MathAnimAI 是一个面向中小学数学教育的 AI 动画智能体，用于大学生科创竞赛。核心能力：

> 输入数学题（文本/图片） → AI 自动拆解 → 生成教学动画视频

全程 LLM 输出标准化 JSON 指令驱动 Manim 动画，规避代码幻觉。

---

## 系统要求

- **操作系统**: Windows 10/11（也支持 macOS/Linux）
- **Python**: 3.10+
- **磁盘空间**: 至少 2GB（Manim 及其依赖较大）

---

## 前置依赖安装

### 1. 安装 FFmpeg（必须）

Manim 依赖 FFmpeg 生成视频。

**Windows**:
- 从 https://ffmpeg.org/download.html 下载
- 解压后将 `bin` 目录添加到系统 PATH 环境变量
- 验证：`ffmpeg -version`

**或使用 Chocolatey**:
```bash
choco install ffmpeg
```

### 2. 安装 MiKTeX（可选，数学公式需要）

如果动画中包含 LaTeX 数学公式，需要 MiKTeX。
- 从 https://miktex.org/download 下载安装

### 3. 中文 OCR 依赖

如果使用图片上传功能：
- 安装 Tesseract OCR：https://github.com/UB-Mannheim/tesseract/wiki
- 安装时勾选中文简体语言包 `Chinese (Simplified)`

---

## 安装步骤

### 第一步：创建虚拟环境

```bash
# 使用 Conda（推荐）
conda create -n mathanim python=3.10
conda activate mathanim

# 或使用 venv
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
```

### 第二步：安装 Python 依赖

```bash
cd education_agent
pip install -r requirements.txt
```

> 注意：Manim 安装可能耗时较长（包含大量依赖）。如果网络不好，可以使用清华镜像：
> ```bash
> pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

### 第三步：配置环境变量

复制 `.env` 文件并根据实际情况修改：

```bash
# 编辑 .env 文件
notepad .env  # Windows

# 关键配置项：
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=你的API密钥
LLM_MODEL=deepseek-chat
```

> **如果不配置 LLM_API_KEY**，系统将使用内置示例动画脚本，仍可渲染动画，但智能程度受限。

---

## 启动运行

```bash
cd education_agent
python main.py
```

启动后访问：**http://127.0.0.1:7860**

### 使用步骤

1. **输入题目**：在左侧文本框中输入数学题，或上传题目图片
2. **选择学段**：小学 / 初中
3. **点击「开始生成教学动画」**
4. **等待生成**：系统依次执行 OCR → LLM规划 → 动画渲染 → TTS配音 → 视频合成
5. **查看结果**：右侧面板显示生成的视频和动画脚本

---

## 项目结构

```
education_agent/
├── main.py                 # Gradio Web 入口，串联全流水线
├── config.py               # 全局配置（配色/字号/时长）
├── .env                    # API Key、渲染参数
├── requirements.txt        # Python 依赖
│
├── parser/                 # 题目解析模块
│   ├── schema.py           # Pydantic 结构化数据模型
│   ├── prompt.py           # 分题型专属 Prompt
│   ├── llm_engine.py       # OpenAI 兼容 API 调用
│   └── ocr.py              # 图片文字/公式 OCR
│
├── animation/              # Manim 动画渲染引擎（核心）
│   ├── common.py           # 全局公共美化工具库
│   ├── builder.py          # JSON 脚本自动分发调度器
│   ├── renderer.py         # Manim 渲染管道
│   └── scenes/             # 分题型独立场景
│       ├── equation.py     # 方程推导
│       ├── geometry.py     # 平面几何
│       ├── function.py     # 函数图像
│       ├── word_problem.py # 应用题（线段图/柱状图）
│       └── fraction.py     # 分数（饼图/数轴）
│
├── audio/                  # 语音 + 字幕
│   ├── tts.py              # edge-tts 语音生成
│   ├── subtitle.py         # SRT 字幕自动生成
│   └── mixer.py            # 人声+背景音乐混合
│
├── video/                  # 视频合成
│   └── composer.py         # moviepy 视频合成（片头片尾字幕）
│
├── storage/                # 本地持久化
│   └── history.py          # SQLite 历史记录
│
├── ui/                     # Gradio Web 界面
│   ├── components.py       # 组件封装
│   └── layout.py           # 左右分栏布局
│
└── demo/                   # 测试素材
    ├── sample_questions.json
    └── videos/
```

---

## 测试验证

### 使用内置测试素材

1. 打开 `demo/sample_questions.json`
2. 里面有 3 个完整测试脚本：
   - **小学应用题**：行程问题（速度×时间=路程）
   - **初中几何**：直角三角形勾股定理
   - **初中代数**：一元二次方程因式分解
3. 复制任意脚本的 `problem_text` 到 Web 界面测试

### 命令行快速测试

```bash
# 测试 Pydantic 数据模型
python -c "from parser.schema import ProblemScript; print('Schema OK')"

# 测试配置文件
python -c "from config import Colors; print(Colors.PRIMARY)"

# 测试（如果 Manim 安装正常）
manim --version
```

---

## 支持题型

| 题型 | 覆盖内容 | 动画特点 |
|------|----------|----------|
| 方程 | 一元一次/二次方程、方程组 | 等号对齐、逐步变形高亮 |
| 几何 | 三角形、四边形、圆、角度 | 辅助线、角度标注、顶点标签 |
| 函数 | 一次/二次函数 | 坐标系常驻、曲线绘制、动点 |
| 应用题 | 行程、工程、面积 | 线段图、柱状图动态生长 |
| 分数 | 加减乘除、比较 | 饼图分割、数轴标注 |

---

## 核心设计原则

1. **LLM 只输出 JSON，不生成 Manim 代码** — 完全规避代码幻觉
2. **所有步骤内容永久保留在画布上** — 不清除、不消失
3. **全场景统一配色/字号/动画参数** — 集中在 config.py 管理
4. **public 工具库驱动** — common.py 被所有 Scene 复用

---

## 常见问题

### Q: Manim 安装失败
A: Manim 依赖较多，请确保：
- Python 3.10+
- 已安装 Visual C++ Redistributable
- 使用清华镜像加速：`pip install manim -i https://pypi.tuna.tsinghua.edu.cn/simple`

### Q: 动画中中文显示为方框
A: 系统默认使用 `Microsoft YaHei` 字体，Windows 下一般已安装。可以修改 `config.py` 中的 `FONT_FAMILY` 为系统已有中文字体。

### Q: edge-tts 合成无声音
A: edge-tts 需要网络连接（调用微软免费TTS服务）。确保网络通畅。

### Q: 视频没有声音
A: 检查 `config.py` 中是否正确配置了 LLM API Key，以及 `.env` 中 `TTS_VOICE` 是否正确。

### Q: OCR 识别不准确
A: 确保已安装 Tesseract 并配置中文语言包。可以先用图片预处理提高识别率。

---

## 许可证

本项目用于大学生科创竞赛，仅供学习和竞赛使用。

---

**项目地址**: 大学生科创竞赛 MathAnimAI 团队
**最后更新**: 2026年6月
