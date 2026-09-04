# -*- coding: utf-8 -*-
"""
源文档标题预处理引擎（T04 / 工具箱 Tab A）
无 Streamlit 依赖，可独立测试。

职责：
1. 检测以正文格式出现的编号标题（1. / 1.1 / 1.1.1 等）
2. 按编号层级推断大纲级别（1.→H1, 1.1→H2, 1.1.1→H3）
3. 将选中段落应用对应 Heading N 样式（并设置大纲级别）
4. 判断文档是否已使用标题样式（供转换页引导提示）
"""
import re
from typing import List, Dict, Optional

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# 编号标题检测：1. / 1.1 / 1.1.1 / 1、 / 1） / (1) 等
# 捕获组 1 = 纯数字编号（用于推断层级），组 2 = 标题正文
HEADING_PATTERN = re.compile(r'^\s*(\d+(?:\.\d+)*)\s*[.、）)]?\s*(.*)$')


class TitlePreprocessor:
    """源文档标题预处理引擎（无状态工具类）"""

    MAX_LEVEL = 9

    @staticmethod
    def infer_level(number_part: str) -> int:
        """根据编号推断大纲级别：层级深度 = 点号数量 + 1，上限 9。

        Examples:
            "1"     -> 1
            "1.1"   -> 2
            "1.1.1" -> 3
        """
        depth = number_part.count('.') + 1
        return min(depth, TitlePreprocessor.MAX_LEVEL)

    @staticmethod
    def detect_headings(docx_file) -> List[Dict]:
        """检测文档中的编号标题段落。

        Args:
            docx_file: docx 文件路径。

        Returns:
            List[Dict]，每个元素结构：
                {
                    "index": int,             # 段落索引（doc.paragraphs 中的位置）
                    "text": str,              # 段落原文
                    "number": str,            # 编号部分（如 "1.1.1"）
                    "detected_level": int,    # 自动推断的级别（1-9）
                }
        """
        doc = Document(docx_file)
        headings = []
        for idx, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if not text:
                continue
            m = HEADING_PATTERN.match(text)
            if not m:
                continue
            number_part = m.group(1)
            # 排除纯数字段落（如单纯的 "1" 后面无内容，可能是列表序号残留）
            content = m.group(2).strip()
            if not content:
                continue
            # 排除过长的段落（标题通常较短，正文段落可能以数字开头）
            if len(text) > 60:
                continue
            headings.append({
                "index": idx,
                "text": text,
                "number": number_part,
                "detected_level": TitlePreprocessor.infer_level(number_part),
            })
        return headings

    @staticmethod
    def _set_outline_level(paragraph, level: int) -> None:
        """直接设置段落的大纲级别（w:outlineLvl）。"""
        pPr = paragraph._p.get_or_add_pPr()
        outline = pPr.find(qn('w:outlineLvl'))
        if outline is None:
            outline = OxmlElement('w:outlineLvl')
            pPr.append(outline)
        outline.set(qn('w:val'), str(level - 1))  # outlineLvl 是 0-based

    @staticmethod
    def _apply_heading_style(doc, paragraph, level: int) -> None:
        """将段落应用 Heading N 样式，并设置大纲级别。

        优先使用 python-docx 的样式赋值（按样式名解析 styleId）；
        若文档 styles.xml 未定义该样式，则回退到直接写 XML（pStyle + outlineLvl），
        保证 Word 打开时能识别为内置标题样式。
        """
        style_name = f"Heading {level}"
        applied = False
        try:
            paragraph.style = doc.styles[style_name]
            applied = True
        except Exception:
            applied = False

        if not applied:
            # 回退：直接写 pStyle（内置标题 styleId 为 "Heading1"、"Heading2"...）
            pPr = paragraph._p.get_or_add_pPr()
            pStyle = pPr.find(qn('w:pStyle'))
            if pStyle is None:
                pStyle = OxmlElement('w:pStyle')
                pPr.insert(0, pStyle)
            pStyle.set(qn('w:val'), f'Heading{level}')

        # 无论样式是否成功，都设置大纲级别（确保被大纲级别检测识别）
        TitlePreprocessor._set_outline_level(paragraph, level)

    @staticmethod
    def apply_headings(docx_file, output_file, selections: List[Dict]) -> None:
        """将选中段落应用对应 Heading N 样式，保存为新文档。

        Args:
            docx_file: 输入 docx 路径。
            output_file: 输出 docx 路径。
            selections: List[Dict]，每个元素结构：
                {"index": int, "target_level": int}
                target_level 为 1-9；不在 selections 中的段落保持不变。
        """
        doc = Document(docx_file)
        # 按 index 建立查找表
        sel_map = {s["index"]: s["target_level"] for s in selections if s.get("target_level", 0) >= 1}
        for idx, para in enumerate(doc.paragraphs):
            if idx in sel_map:
                TitlePreprocessor._apply_heading_style(doc, para, sel_map[idx])
        doc.save(output_file)

    @staticmethod
    def has_heading_styles(docx_file) -> bool:
        """判断文档是否已使用标题样式（Heading N / 标题 N / 大纲级别）。"""
        doc = Document(docx_file)
        heading_style_names = {
            'heading 1', 'heading 2', 'heading 3', 'heading 4', 'heading 5',
            'heading 6', 'heading 7', 'heading 8', 'heading 9',
            '标题 1', '标题 2', '标题 3', '标题 4', '标题 5',
            '标题 6', '标题 7', '标题 8', '标题 9',
        }
        for para in doc.paragraphs:
            if para.style and para.style.name:
                if para.style.name.lower() in heading_style_names:
                    return True
            # 检查大纲级别
            pPr = para._p.find(qn('w:pPr'))
            if pPr is not None and pPr.find(qn('w:outlineLvl')) is not None:
                return True
        return False
