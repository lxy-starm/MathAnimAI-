"""
============================================================
MathAnimAI — 图片OCR识别模块
功能：
  1. pytesseract 中文+英文文字识别
  2. pix2tex 数学公式OCR
  3. 组合输出纯文本题目，传给LLM解析
============================================================
"""

import logging
from typing import Optional
from PIL import Image

logger = logging.getLogger("MathAnimAI.OCR")


# ================================================================
# Tesseract OCR 文字识别
# ================================================================
def tesseract_ocr(image_path: str, lang: str = "chi_sim+eng") -> str:
    """
    使用pytesseract对图片进行OCR文字识别

    Args:
        image_path: 图片路径
        lang: 识别语言，默认 中文简体 + 英文

    Returns:
        识别出的文本内容
    """
    try:
        import pytesseract

        # 打开图片
        img = Image.open(image_path)

        # 图片预处理：转灰度 + 二值化，提高识别率
        img_gray = img.convert("L")

        # OCR识别
        text = pytesseract.image_to_string(img_gray, lang=lang)

        # 清理文本
        text = text.strip()
        # 合并多余空白行
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

        logger.info(f"Tesseract识别完成，共{len(text)}字符")
        return text

    except ImportError:
        logger.warning("pytesseract未安装，返回空文本")
        return ""
    except Exception as e:
        logger.error(f"Tesseract OCR失败: {e}")
        return ""


# ================================================================
# pix2tex 数学公式OCR
# ================================================================
def pix2tex_formula(image_path: str) -> str:
    """
    使用pix2tex识别图片中的LaTeX数学公式

    Args:
        image_path: 图片路径

    Returns:
        LaTeX格式的数学公式
    """
    try:
        from pix2tex.cli import LatexOCR

        # 加载模型
        model = LatexOCR()
        result = model(image_path)
        logger.info(f"pix2tex识别公式: {result}")
        return result

    except ImportError:
        logger.warning("pix2tex未安装，跳过数学公式OCR")
        return ""
    except Exception as e:
        logger.error(f"pix2tex OCR失败: {e}")
        return ""


# ================================================================
# 组合OCR：文字 + 公式，输出完整题目文本
# ================================================================
def ocr_problem(image_path: str) -> str:
    """
    完整OCR流程：文字识别 + 数学公式识别，拼接为完整题目文本

    Args:
        image_path: 题目图片路径

    Returns:
        完整的题目文本（含LaTeX公式）
    """
    logger.info(f"开始OCR识别: {image_path}")

    # 第一步：文字识别
    text = tesseract_ocr(image_path, lang="chi_sim+eng")

    # 第二步：数学公式识别（如果安装了pix2tex）
    formula = pix2tex_formula(image_path)

    # 第三步：组合结果
    if formula:
        # 如果有公式识别结果，附加到文本中
        combined = f"{text}\n\n（数学公式：{formula}）" if text else formula
    else:
        combined = text

    if not combined:
        logger.warning("OCR未能识别任何内容")
        return ""

    logger.info(f"OCR完成，结果: {combined[:100]}...")
    return combined


# ================================================================
# 简易图片预处理工具
# ================================================================
def preprocess_image(image_path: str, output_path: Optional[str] = None) -> str:
    """
    图片预处理：放大、去噪、增强对比度
    提高OCR识别准确率

    Args:
        image_path: 原始图片路径
        output_path: 预处理后保存路径，默认在原图同目录生成

    Returns:
        预处理后的图片路径
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter

        img = Image.open(image_path)

        # 如果图片太小，放大到合适尺寸
        if img.width < 800 or img.height < 600:
            scale = max(800 / img.width, 600 / img.height)
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.LANCZOS)

        # 转灰度
        img = img.convert("L")

        # 增强对比度
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # 轻微锐化
        img = img.filter(ImageFilter.SHARPEN)

        # 保存
        if output_path is None:
            import os
            base, ext = os.path.splitext(image_path)
            output_path = f"{base}_processed{ext}"

        img.save(output_path)
        logger.info(f"图片预处理完成: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"图片预处理失败: {e}")
        return image_path  # 失败时返回原图
