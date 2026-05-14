# -*- coding: utf-8 -*-
"""
文档格式转换程序 - 核心处理模块
整合样式转换、祈使语气转换、标题后插入应答句功能
"""
import os
import sys
import re
import io
import logging
from datetime import datetime
from copy import deepcopy
from collections import defaultdict

try:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement, parse_xml
    from lxml import etree
    from docx.shared import Emu
    from docx.enum.style import WD_STYLE_TYPE
    from docx.image.exceptions import UnrecognizedImageError
except ImportError:
    print("错误：未安装 python-docx 库。请运行: pip install python-docx")
    sys.exit(1)

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ==================== 配置常量 ====================
DEFAULT_TARGET = "Normal"
TARGET_STYLE_FOR_TABLES = "Body Text"
TARGET_STYLE_FOR_IMAGES = "Body Text"
IMAGE_SCALE_RATIO = 2 / 3
LIST_BULLET_SYMBOL = "● "
TABLE_BORDER_SIZE = '4'
TABLE_BORDER_COLOR = '000000'
ANSWER_TEXT = "应答：本投标人理解并满足要求。"
ANSWER_STYLE = "应答句"
HEADING_STYLE_IDS = {'1', '2', '3', '4', '5', '6', '7', '8', '9'}
HEADING_STYLES = {f"Heading {i}" for i in range(1, 10)}

# 样式映射表
STYLE_MAP = {
    "Heading 1": "Heading 1",
    "Heading 2": "Heading 2",
    "Heading 3": "Heading 3",
    "Heading 4": "Heading 4",
    "Heading 5": "Heading 5",
    "Heading 6": "Heading 6",
    "List Paragraph": "List Paragraph",
}

OUTLINE_STYLE_MAP = {
    1: "Heading 1", 2: "Heading 2", 3: "Heading 3",
    4: "Heading 4", 5: "Heading 5", 6: "Heading 6",
    7: "Heading 7", 8: "Heading 8", 9: "Heading 9",
}

# 祈使语气替换规则
MULTI_IMPERATIVE_TO_STATEMENT = {
    "必须": "将", "不得": "不会", "不应": "不会", "不可": "不会",
    "不能": "无法", "切勿": "不要", "严禁": "禁止", "请勿": "请避免",
    "不许": "不允许",
}

MULTI_EXCEPTIONS = [
    "不可抗力", "不得已", "不由得", "不可通行", "不可开交", "不可理喻", "不可或缺",
    "不得少于", "不得大于", "不得超过", "不得低于", "不得高于", "不得小于", "不得用于",
    "不可否认", "不可避免", "不可逆", "不可分割",
]

SINGLE_REPLACE = {"应": "将", "须": "将"}

EXCEPTION_WORDS_YING = [
    "响应", "应用", "适应", "相应", "供应", "反应", "效应", "对应", "有应", "报应",
    "呼应", "感应", "应邀", "应酬", "应允", "应声", "应景", "应试", "应变", "应付",
    "应急", "应验", "应战", "应征", "应运", "应答", "应对", "应接", "应诺", "应求",
    "应时", "应需",
]
EXCEPTION_WORDS_XU = ["必须", "无须", "无需"]
REPLACE_MAP = {"投标人": "本投标人"}


def build_word_pattern(word):
    return r'(?<![a-zA-Z0-9])' + re.escape(word) + r'(?![a-zA-Z0-9])'


def clean_list_numbering(text):
    """清理开头数字编号：1、 1） (1) 等"""
    pattern = r'^\s*(?:\d+[、\)）]|[（(]\d+[）\)])\s*'
    cleaned = re.sub(pattern, '', text, count=1)
    return cleaned


MULTI_IMPERATIVE_PATTERNS = [build_word_pattern(w) for w in MULTI_IMPERATIVE_TO_STATEMENT.keys()]
MULTI_IMPERATIVE_REGEX = re.compile('|'.join(MULTI_IMPERATIVE_PATTERNS))

SINGLE_IMPERATIVE_PATTERNS = [build_word_pattern(w) for w in SINGLE_REPLACE.keys()]
SINGLE_IMPERATIVE_REGEX = re.compile('|'.join(SINGLE_IMPERATIVE_PATTERNS))

REPLACE_REGEX = None
if REPLACE_MAP:
    patterns = []
    for word, repl in REPLACE_MAP.items():
        if word == "投标人":
            pat = r'(?<![本])' + re.escape(word) + r'(?![a-zA-Z0-9])'
        else:
            pat = build_word_pattern(word)
        patterns.append(pat)
    REPLACE_REGEX = re.compile('|'.join(patterns))


class DocumentConverter:
    """文档转换器主类"""
    
    def __init__(self):
        self.logger = None
        self.stats = {"para": 0, "table": 0, "heading": 0}
        self.source_styles = set()  # 源文档中使用的样式
        self.template_styles = set()  # 模板文档中的样式
        self.list_bullet = LIST_BULLET_SYMBOL  # 列表段落符号，默认为配置常量
        
    def setup_logger(self, source_file):
        log_filename = os.path.splitext(source_file)[0] + "_err.log"
        logger = logging.getLogger(f"converter_{os.path.basename(source_file)}")
        logger.setLevel(logging.WARNING)
        if not logger.handlers:
            handler = logging.FileHandler(log_filename, encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        self.logger = logger
        return logger
    
    def get_all_styles_from_doc(self, doc):
        """获取文档中使用的所有样式"""
        styles = set()
        for para in doc.paragraphs:
            if para.style and para.style.name:
                styles.add(para.style.name)
        return styles
    
    def get_template_styles(self, template_doc):
        """获取模板文档中的所有可用样式"""
        styles = set()
        for style in template_doc.styles:
            if style.type == WD_STYLE_TYPE.PARAGRAPH:
                styles.add(style.name)
        return styles
    
    def clear_document_content(self, doc):
        """清空文档内容但保留样式"""
        for table in doc.tables:
            table._element.getparent().remove(table._element)
        for para in doc.paragraphs:
            p = para._element
            p.getparent().remove(p)
        doc.add_paragraph()
    
    def get_outline_level(self, paragraph_or_elem, doc=None):
        """获取段落的大纲级别
        
        参数可以是：
        - python-docx 的 Paragraph 对象
        - lxml 的 XML 元素
        """
        # 判断输入类型
        if hasattr(paragraph_or_elem, '_element'):
            # 这是 Paragraph 对象
            elem = paragraph_or_elem._element
        else:
            # 这是 XML 元素
            elem = paragraph_or_elem
        
        # 安全检查：确保elem是XML元素
        if not hasattr(elem, 'tag'):
            return 0
        if elem.tag != qn('w:p'):
            return 0
        
        # 1. 从段落自身 w:pPr/w:outlineLvl 获取
        pPr = elem.find(qn('w:pPr'))
        if pPr is not None:
            outline = pPr.find(qn('w:outlineLvl'))
            if outline is not None:
                val = outline.get(qn('w:val'))
                if val is not None:
                    try:
                        level = int(val) + 1
                        return level
                    except ValueError:
                        pass
        
        # 2. 从段落应用的样式中获取（仅当提供doc时）
        if doc is not None and pPr is not None:
            pStyle = pPr.find(qn('w:pStyle'))
            if pStyle is not None:
                style_id = pStyle.get(qn('w:val'))
                if style_id:
                    try:
                        style = doc.styles[style_id]
                        style_elem = style._element
                        style_pPr = style_elem.find(qn('w:pPr'))
                        if style_pPr is not None:
                            outline = style_pPr.find(qn('w:outlineLvl'))
                            if outline is not None:
                                val = outline.get(qn('w:val'))
                                if val is not None:
                                    try:
                                        return int(val) + 1
                                    except ValueError:
                                        pass
                    except KeyError:
                        pass
        
        return 0
    
    def is_toc_paragraph(self, paragraph):
        """检查段落是否为目录（TOC）"""
        # 只通过域代码来判断，不依赖样式名称，避免误判
        elem = paragraph._element
        
        # 检查是否包含 TOC 域指令
        has_toc_instr = False
        for instr_text in elem.findall('.//' + qn('w:instrText')):
            if instr_text.text and 'TOC' in instr_text.text.upper():
                has_toc_instr = True
                break
        
        if has_toc_instr:
            return True
        
        # 检查是否有 PAGEREF 域（TOC 中的页码引用）且有超链接
        has_pageref = False
        for instr_text in elem.findall('.//' + qn('w:instrText')):
            if instr_text.text and 'PAGEREF' in instr_text.text.upper():
                has_pageref = True
                break
        
        has_hyperlink = len(elem.findall('.//' + qn('w:hyperlink'))) > 0
        
        # 只有同时有 PAGEREF 和超链接时，才判定为目录
        if has_pageref and has_hyperlink:
            return True
        
        return False
    
    def has_numbering(self, paragraph):
        """检查段落是否有编号"""
        pPr = paragraph._element.find(qn('w:pPr'))
        if pPr is not None:
            numPr = pPr.find(qn('w:numPr'))
            if numPr is not None:
                return True
        return False
    
    def remove_auto_numbering(self, paragraph):
        """移除自动编号"""
        pPr = paragraph._element.get_or_add_pPr()
        numPr = pPr.find(qn('w:numPr'))
        if numPr is not None:
            pPr.remove(numPr)
    
    def remove_manual_numbering(self, text):
        """移除手动编号（智能判断中文数字是否为编号）"""
        fragment_patterns = [
            r'\d+(?:\.\d+)*\.?',
            r'[一二三四五六七八九十]+[、.．)）]',  # 中文数字后带分隔符才视为编号（支持半角/全角右括号）
            r'（[一二三四五六七八九十]+）',  # 括号内的中文数字编号（如"（二）"）
            r'\([0-9]+\)',
            r'[①-⑩]',
            r'[A-Za-z]\.',
        ]
        pattern = r'^\s*(' + '|'.join(fragment_patterns) + r')[\s、，]*'
        compiled = re.compile(pattern)
        cleaned = text
        while True:
            m = compiled.match(cleaned)
            if m:
                cleaned = cleaned[m.end():]
            else:
                break
        return cleaned
    
    def get_target_style(self, original_style_name, template_doc, source_file=""):
        """获取目标样式名称"""
        target = STYLE_MAP.get(original_style_name)
        if target is not None:
            try:
                template_doc.styles[target]
                return target
            except KeyError:
                try:
                    template_doc.styles[original_style_name]
                    return original_style_name
                except KeyError:
                    return DEFAULT_TARGET
        else:
            try:
                template_doc.styles[original_style_name]
                return original_style_name
            except KeyError:
                return DEFAULT_TARGET
    
    def get_image_size(self, image_bytes):
        """获取图片尺寸"""
        if not PIL_AVAILABLE:
            return None, None
        try:
            img = Image.open(io.BytesIO(image_bytes))
            return img.width, img.height
        except:
            return None, None
    
    def get_image_extent(self, blip_element):
        """从 blip 元素向上查找 wp:inline，并返回图片的原始显示尺寸 (cx, cy) 单位 EMU，若失败则返回 (None, None)"""
        parent = blip_element.getparent()
        while parent is not None:
            if parent.tag == qn('wp:inline'):
                extent = parent.find(qn('wp:extent'))
                if extent is not None:
                    cx = int(extent.get('cx', '0'))
                    cy = int(extent.get('cy', '0'))
                    return (cx, cy)
                break
            parent = parent.getparent()
        return (None, None)
    
    def resize_image_to_fixed_width(self, image_bytes, target_width_emu, dpi=96):
        """调整图片大小"""
        w_px, h_px = self.get_image_size(image_bytes)
        if w_px is None or h_px is None:
            return None, None
        w_emu = int(w_px / dpi * 914400)
        if w_emu <= target_width_emu:
            return w_emu, int(h_px / dpi * 914400)
        scale = target_width_emu / w_emu
        return int(w_emu * scale), int(h_px / dpi * 914400 * scale)
    
    def add_picture(self, run, img_bytes, page_width_emu, available_width_emu, emu_width=None, emu_height=None):
        """
        添加图片。
        若提供了源文档的显示尺寸 (emu_width, emu_height)，则优先使用；
        当图片宽度超出可用宽度时，缩放到页面宽度的 IMAGE_SCALE_RATIO，高度等比缩放。
        如果未提供尺寸，则使用图片的像素尺寸（96 DPI 计算）并做相同处理。
        """
        if not PIL_AVAILABLE:
            run.add_picture(io.BytesIO(img_bytes))
            return

        # 如果有源尺寸，直接使用；否则从像素计算
        if emu_width is not None and emu_height is not None:
            w_emu = emu_width
            h_emu = emu_height
        else:
            try:
                img = Image.open(io.BytesIO(img_bytes))
                w_px, h_px = img.size
                w_emu = int(w_px / 96 * 914400)
                h_emu = int(h_px / 96 * 914400)
            except:
                run.add_picture(io.BytesIO(img_bytes))
                return

        # 如果宽度超出可用宽度，则按页面宽度的 IMAGE_SCALE_RATIO 缩放
        if w_emu > available_width_emu:
            target_w = int(page_width_emu * IMAGE_SCALE_RATIO)
            scale = target_w / w_emu
            new_w = int(w_emu * scale)
            new_h = int(h_emu * scale)
            run.add_picture(io.BytesIO(img_bytes), width=Emu(new_w), height=Emu(new_h))
        else:
            run.add_picture(io.BytesIO(img_bytes), width=Emu(w_emu), height=Emu(h_emu))
    
    def set_table_width(self, table, width_emu):
        """设置表格宽度"""
        width_dxa = int(width_emu / 635)
        tbl = table._tbl
        tblPr = tbl.find(qn('w:tblPr'))
        if tblPr is None:
            tblPr = parse_xml('<w:tblPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
            tbl.insert(0, tblPr)
        tblW = tblPr.find(qn('w:tblW'))
        if tblW is None:
            tblW = parse_xml('<w:tblW xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
            tblPr.append(tblW)
        tblW.set(qn('w:w'), str(width_dxa))
        tblW.set(qn('w:type'), 'dxa')
    
    def set_table_borders(self, table):
        """为表格添加边框"""
        for row in table.rows:
            for cell in row.cells:
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                for border_name in ['top', 'left', 'bottom', 'right']:
                    existing = tcPr.find(qn(f'w:{border_name}'))
                    if existing is not None:
                        tcPr.remove(existing)
                for border_name in ['top', 'left', 'bottom', 'right']:
                    border = OxmlElement(f'w:{border_name}')
                    border.set(qn('w:val'), 'single')
                    border.set(qn('w:sz'), TABLE_BORDER_SIZE)
                    border.set(qn('w:space'), '0')
                    border.set(qn('w:color'), TABLE_BORDER_COLOR)
                    tcPr.append(border)
    
    def copy_element_with_objects(self, source_elem, target_doc, target_style_name,
                                  page_width_emu, available_width_emu, para_idx=None, source_file="",
                                  warning_callback=None):
        """复制元素（包含图片、Visio图、OLE对象等）
        :param warning_callback: 警告回调函数 callback(message)
        """
        # 检查是否为段落
        if hasattr(source_elem, 'tag') and source_elem.tag == qn('w:p'):
            return self.copy_paragraph_with_images(
                source_elem, target_doc, target_style_name,
                page_width_emu, available_width_emu, 
                para_idx if para_idx is not None else 0, source_file,
                warning_callback
            )
        
        # 检查是否为表格
        elif hasattr(source_elem, 'tag') and source_elem.tag == qn('w:tbl'):
            # 这里需要找到对应的表格索引
            return None
        
        # 处理其他类型的元素（如OLE对象、Visio图等）
        else:
            return self.copy_special_element(source_elem, target_doc, target_style_name)
    
    def copy_special_element(self, source_elem, target_doc, target_style_name):
        """复制特殊元素（OLE对象、Visio图等）"""
        try:
            # 创建一个新的段落来容纳特殊对象
            new_para = target_doc.add_paragraph()
            try:
                new_para.style = target_style_name
            except KeyError:
                new_para.style = target_doc.styles['Normal']
            
            # 检查是否包含OLE对象或形状（使用正确的命名空间）
            objects = source_elem.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}object')
            shapes = source_elem.findall('.//{urn:schemas-microsoft-com:vml}shape')
            
            if objects or shapes:
                # 对于包含特殊对象的元素，我们尝试直接复制XML结构
                from copy import deepcopy
                new_elem = deepcopy(source_elem)
                
                # 将复制的元素添加到新段落的底层XML中
                new_para._element.append(new_elem)
                
                return new_para
            else:
                # 如果没有特殊对象，返回空段落
                return new_para
        except Exception as e:
            print(f"警告：复制特殊元素时出错: {e}")
            # 出错时返回一个空段落
            new_para = target_doc.add_paragraph()
            try:
                new_para.style = target_style_name
            except KeyError:
                new_para.style = target_doc.styles['Normal']
            return new_para
    
    def copy_paragraph_with_images(self, source_para, target_doc, target_style_name,
                                   page_width_emu, available_width_emu, para_idx, source_file="",
                                   warning_callback=None):
        """复制段落（包含图片、Visio图、OLE对象等）
        :param warning_callback: 警告回调函数 callback(message)
        """
        # 调试：检查大纲级别
        outline_level = self.get_outline_level(source_para)
        
        # 检查是否为目录段落，如果是则保持原样式
        if self.is_toc_paragraph(source_para):
            new_para = target_doc.add_paragraph()
            # 保持原始样式或应用目标样式
            try:
                new_para.style = target_style_name
            except KeyError:
                new_para.style = target_doc.styles['Normal']
            
            # 复制内容但不修改
            for run in source_para.runs:
                new_run = new_para.add_run(run.text)
                # 复制格式
                new_run.bold = run.bold
                new_run.italic = run.italic
                new_run.underline = run.underline
                
                # 复制图片
                blips = run._element.findall('.//' + qn('a:blip'))
                for blip in blips:
                    rId = blip.get(qn('r:embed'))
                    if rId:
                        try:
                            img_part = source_para.part.related_parts[rId]
                            img_bytes = img_part.blob
                            emu_w, emu_h = self.get_image_extent(blip)
                            pic_run = new_para.add_run()
                            self.add_picture(pic_run, img_bytes, page_width_emu, available_width_emu, emu_w, emu_h)
                        except Exception:
                            pass
            return new_para
        
        # 检查是否包含 OLE 对象或 VML 形状
        has_ole_objects = source_para._element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}object')
        has_vml_shapes = source_para._element.findall('.//{urn:schemas-microsoft-com:vml}shape')
        
        # 如果包含特殊对象，暂时跳过并记录警告
        # TODO: 未来需要实现完整的 OLE 对象处理
        if has_ole_objects or has_vml_shapes:
            warning_msg = f"[WARNING] 段落 {para_idx} 包含 OLE/VML 对象，暂时跳过以避免文档损坏\n  - OLE 对象数: {len(has_ole_objects)}\n  - VML 形状数: {len(has_vml_shapes)}"
            print(warning_msg)  # 仍然输出到控制台
            
            # 如果有回调函数，也通过回调输出
            if warning_callback:
                try:
                    warning_callback(warning_msg)
                except:
                    pass
            
            # 创建一个占位段落
            new_para = target_doc.add_paragraph()
            new_para.add_run("[此处有 Visio 图或 OLE 对象，请手动复制]")
            try:
                new_para.style = target_style_name
            except KeyError:
                new_para.style = target_doc.styles['Normal']
            return new_para
        
        # 普通段落处理（原有逻辑）
        has_image = any(run._element.findall('.//' + qn('a:blip')) for run in source_para.runs)
        new_para = target_doc.add_paragraph()
        src_style_name = source_para.style.name
        
        if outline_level > 0:
            final_style = OUTLINE_STYLE_MAP.get(outline_level)
            if final_style is None:
                final_style = f"Heading {outline_level}"
            
            # 检查目标文档中是否存在该样式
            try:
                target_doc.styles[final_style]
            except KeyError:
                # 样式不存在，尝试从源文档复制
                print(f"[WARNING] 模板中缺少样式 '{final_style}'，尝试从源文档复制...")
                try:
                    source_style = source_para.part.document.styles[final_style]
                    # 复制样式到目标文档
                    new_style = target_doc.styles.add_style(final_style, WD_STYLE_TYPE.PARAGRAPH)
                    new_style.base_style = target_doc.styles['Normal']
                    # 复制基本格式
                    if hasattr(source_style, 'font'):
                        if source_style.font.bold:
                            new_style.font.bold = True
                        if source_style.font.size:
                            new_style.font.size = source_style.font.size
                        if source_style.font.color and source_style.font.color.rgb:
                            new_style.font.color.rgb = source_style.font.color.rgb
                    print(f"[INFO] 已从源文档复制样式 '{final_style}'")
                except Exception as e:
                    print(f"[WARNING] 无法复制样式 '{final_style}': {e}，将尝试创建基本样式")
                    try:
                        # 创建基本的标题样式
                        new_style = target_doc.styles.add_style(final_style, WD_STYLE_TYPE.PARAGRAPH)
                        new_style.base_style = target_doc.styles['Normal']
                        new_style.font.bold = True
                        # 根据大纲级别设置字体大小
                        size_map = {1: 24, 2: 20, 3: 16, 4: 14, 5: 13, 6: 12, 7: 12, 8: 12, 9: 12}
                        from docx.shared import Pt
                        new_style.font.size = Pt(size_map.get(outline_level, 12))
                        print(f"[INFO] 已创建基本样式 '{final_style}'")
                    except Exception as e2:
                        print(f"[ERROR] 无法创建样式 '{final_style}': {e2}，使用默认样式")
                        final_style = DEFAULT_TARGET
        else:
            if has_image:
                final_style = TARGET_STYLE_FOR_IMAGES
                try:
                    target_doc.styles[final_style]
                except KeyError:
                    final_style = DEFAULT_TARGET
            else:
                final_style = target_style_name
        
        try:
            new_para.style = final_style
        except Exception:
            new_para.style = target_doc.styles['Normal']
        
        is_heading_by_outline = outline_level > 0
        is_heading_by_style = src_style_name in HEADING_STYLES
        
        if is_heading_by_outline or is_heading_by_style:
            if not is_heading_by_outline:
                self.remove_auto_numbering(new_para)
            full_text = ''.join(run.text for run in source_para.runs)
            cleaned_text = self.remove_manual_numbering(full_text)
            new_para.clear()
            new_para.add_run(cleaned_text)
            for run_idx, run in enumerate(source_para.runs):
                blips = run._element.findall('.//' + qn('a:blip'))
                for blip in blips:
                    rId = blip.get(qn('r:embed'))
                    if rId:
                        try:
                            img_part = source_para.part.related_parts[rId]
                            img_bytes = img_part.blob
                            emu_w, emu_h = self.get_image_extent(blip)
                            pic_run = new_para.add_run()
                            self.add_picture(pic_run, img_bytes, page_width_emu, available_width_emu, emu_w, emu_h)
                        except Exception:
                            pass
            return new_para
        
        if self.has_numbering(source_para):
            new_para.add_run(self.list_bullet)
            self.remove_auto_numbering(new_para)
            # 对于列表段落，使用专门的编号清理函数
            full_text = ''.join(run.text for run in source_para.runs)
            cleaned_text = clean_list_numbering(full_text)
            if cleaned_text:
                new_para.add_run(cleaned_text)
            for run_idx, run in enumerate(source_para.runs):
                blips = run._element.findall('.//' + qn('a:blip'))
                for blip in blips:
                    rId = blip.get(qn('r:embed'))
                    if rId:
                        try:
                            img_part = source_para.part.related_parts[rId]
                            img_bytes = img_part.blob
                            emu_w, emu_h = self.get_image_extent(blip)
                            pic_run = new_para.add_run()
                            self.add_picture(pic_run, img_bytes, page_width_emu, available_width_emu, emu_w, emu_h)
                        except Exception:
                            pass
            return new_para
        
        for run_idx, run in enumerate(source_para.runs):
            blips = run._element.findall('.//' + qn('a:blip'))
            if blips:
                for blip in blips:
                    rId = blip.get(qn('r:embed'))
                    if rId:
                        try:
                            img_part = source_para.part.related_parts[rId]
                            img_bytes = img_part.blob
                            emu_w, emu_h = self.get_image_extent(blip)
                            pic_run = new_para.add_run()
                            self.add_picture(pic_run, img_bytes, page_width_emu, available_width_emu, emu_w, emu_h)
                        except Exception:
                            pass
            else:
                if run.text:
                    new_para.add_run(run.text)
        
        return new_para
    
    def detect_merged_cells(self, table):
        """
        检测表格中的合并单元格
        :param table: python-docx 表格对象
        :return: 包含合并信息的字典 {'has_merge': bool, 'grid_span_count': int, 'v_merge_count': int}
        """
        grid_span_count = 0
        v_merge_count = 0
        
        for row in table.rows:
            for cell in row.cells:
                tc_pr = cell._element.find(qn('w:tcPr'))
                if tc_pr is not None:
                    # 检测横向合并
                    grid_span_elem = tc_pr.find(qn('w:gridSpan'))
                    if grid_span_elem is not None:
                        span_val = grid_span_elem.get(qn('w:val'))
                        if span_val:
                            try:
                                span = int(span_val)
                                if span > 1:
                                    grid_span_count += 1
                            except ValueError:
                                pass
                    
                    # 检测纵向合并
                    v_merge_elem = tc_pr.find(qn('w:vMerge'))
                    if v_merge_elem is not None:
                        v_merge_count += 1
        
        has_merge = (grid_span_count > 0 or v_merge_count > 0)
        return {
            'has_merge': has_merge,
            'grid_span_count': grid_span_count,
            'v_merge_count': v_merge_count
        }
    
    def copy_table_with_images(self, source_table, target_doc, table_idx, available_width_emu, source_file="",
                               warning_callback=None):
        """
        复制表格（包含图片、边框）
        注意：不支持合并单元格，会输出警告信息
        :param source_table: 源表格
        :param target_doc: 目标文档
        :param table_idx: 表格索引
        :param available_width_emu: 可用宽度
        :param source_file: 源文件名
        :param warning_callback: 警告回调函数
        """
        # 检测合并单元格
        merge_info = self.detect_merged_cells(source_table)
        if merge_info['has_merge'] and warning_callback:
            warnings = []
            if merge_info['grid_span_count'] > 0:
                warnings.append(f"{merge_info['grid_span_count']}个横向合并")
            if merge_info['v_merge_count'] > 0:
                warnings.append(f"{merge_info['v_merge_count']}个纵向合并")
            warning_msg = f"表格 {table_idx} 包含合并单元格（{'、'.join(warnings)}），已跳过合并属性，请手动调整"
            warning_callback(warning_msg)
        
        # 获取源表格的行数和列数
        rows = len(source_table.rows)
        cols = len(source_table.columns)
        
        # 创建新表格
        new_table = target_doc.add_table(rows=rows, cols=cols)
        new_table.style = source_table.style
        table_style = TARGET_STYLE_FOR_TABLES
        try:
            target_doc.styles[table_style]
        except KeyError:
            table_style = DEFAULT_TARGET
        
        self.set_table_width(new_table, available_width_emu)
        self.set_table_borders(new_table)
        
        # 复制单元格内容（简单的双层循环）
        for i, row in enumerate(source_table.rows):
            for j, cell in enumerate(row.cells):
                try:
                    new_cell = new_table.cell(i, j)
                except IndexError:
                    continue
                
                # 清空单元格内容
                new_cell._element.clear_content()
                
                # 复制段落内容
                for para_idx, para in enumerate(cell.paragraphs):
                    new_para = new_cell.add_paragraph()
                    new_para.style = table_style
                    
                    if self.has_numbering(para):
                        new_para.add_run(self.list_bullet)
                        self.remove_auto_numbering(new_para)
                        full_text = ''.join(run.text for run in para.runs)
                        cleaned_text = clean_list_numbering(full_text)
                        if cleaned_text:
                            new_para.add_run(cleaned_text)
                        for run_idx, run in enumerate(para.runs):
                            blips = run._element.findall('.//' + qn('a:blip'))
                            for blip in blips:
                                rId = blip.get(qn('r:embed'))
                                if rId:
                                    try:
                                        img_part = para.part.related_parts[rId]
                                        img_bytes = img_part.blob
                                        emu_w, emu_h = self.get_image_extent(blip)
                                        pic_run = new_para.add_run()
                                        self.add_picture(pic_run, img_bytes, available_width_emu, available_width_emu, emu_w, emu_h)
                                    except Exception:
                                        pass
                        continue
                    
                    # 检查是否包含特殊对象（Visio图、OLE对象等）
                    objects = para._element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}object')
                    shapes = para._element.findall('.//{urn:schemas-microsoft-com:vml}shape')
                    
                    if objects or shapes:
                        # 复制特殊对象
                        for obj in objects + shapes:
                            new_obj = deepcopy(obj)
                            new_para._element.append(new_obj)
                        
                        # 输出警告
                        if warning_callback:
                            try:
                                warning_msg = f"表格 {table_idx} 单元格 [{i},{j}] 包含 OLE/VML 对象"
                                warning_callback(warning_msg)
                            except:
                                pass
                    else:
                        # 处理普通文本和图片
                        for run_idx, run in enumerate(para.runs):
                            blips = run._element.findall('.//' + qn('a:blip'))
                            if blips:
                                for blip in blips:
                                    rId = blip.get(qn('r:embed'))
                                    if rId:
                                        try:
                                            img_part = para.part.related_parts[rId]
                                            img_bytes = img_part.blob
                                            emu_w, emu_h = self.get_image_extent(blip)
                                            pic_run = new_para.add_run()
                                            self.add_picture(pic_run, img_bytes, available_width_emu, available_width_emu, emu_w, emu_h)
                                        except Exception:
                                            pass
                            else:
                                if run.text:
                                    new_para.add_run(run.text)
        
        return new_table
    
    def convert_styles(self, source_file, template_file, output_file, custom_style_map=None, list_bullet=None,
                       warning_callback=None):
        """
        样式转换主函数
        :param source_file: 源文件路径
        :param template_file: 模板文件路径
        :param output_file: 输出文件路径
        :param custom_style_map: 自定义样式映射表（可选）
        :param list_bullet: 列表段落符号（可选，默认为配置常量）
        :param warning_callback: 警告回调函数 callback(message)
        :return: 是否成功
        """
        global STYLE_MAP
        if custom_style_map:
            STYLE_MAP.update(custom_style_map)
        
        # 设置列表符号
        if list_bullet is not None:
            self.list_bullet = list_bullet
        
        logger = self.setup_logger(source_file)
        
        try:
            template_doc = Document(template_file)
        except Exception as e:
            return False, f"加载模板文档失败: {e}"
        
        # 获取模板和源文档的样式
        self.template_styles = self.get_template_styles(template_doc)
        
        try:
            source_doc = Document(source_file)
        except Exception as e:
            return False, f"加载源文档失败: {e}"
        
        # 调试：检查加载的源文档中的大纲级别
        for i, para in enumerate(source_doc.paragraphs):
            pPr_check = para._element.find(qn('w:pPr'))
            if pPr_check is not None:
                outline_check = pPr_check.find(qn('w:outlineLvl'))
                if outline_check is not None:
                    val_check = outline_check.get(qn('w:val'))
        
        self.source_styles = self.get_all_styles_from_doc(source_doc)
        
        new_doc = Document(template_file)
        self.clear_document_content(new_doc)
        
        section = new_doc.sections[0]
        page_width = section.page_width
        left_margin = section.left_margin
        right_margin = section.right_margin
        available_width = page_width - left_margin - right_margin
        
        body = source_doc.element.body
        para_idx = 0
        table_idx = 0
        self.stats = {"para": 0, "table": 0, "heading": 0}
        
        for child in body:
            if child.tag == qn('w:p'):
                if para_idx < len(source_doc.paragraphs):
                    para = source_doc.paragraphs[para_idx]
                    src_style = para.style.name
                    
                    # 调试：检查传入的段落
                    pPr_debug = para._element.find(qn('w:pPr'))
                    outline_debug = pPr_debug.find(qn('w:outlineLvl')) if pPr_debug is not None else None
                    outline_val_debug = outline_debug.get(qn('w:val')) if outline_debug is not None else None
                    
                    target_style = self.get_target_style(src_style, new_doc, source_file)
                    
                    new_para = self.copy_paragraph_with_images(
                        para, new_doc, target_style,
                        page_width, available_width,
                        para_idx, source_file,
                        warning_callback
                    )
                    
                    if self.get_outline_level(para) > 0 or src_style in HEADING_STYLES:
                        self.stats["heading"] += 1
                    self.stats["para"] += 1
                    para_idx += 1
            
            elif child.tag == qn('w:tbl'):
                if table_idx < len(source_doc.tables):
                    table = source_doc.tables[table_idx]
                    self.copy_table_with_images(table, new_doc, table_idx, available_width, source_file,
                                               warning_callback)
                    self.stats["table"] += 1
                    table_idx += 1
            
            else:
                # 处理其他类型的元素（如OLE对象、Visio图等）
                # 尝试获取样式名称，如果无法获取则使用默认样式
                try:
                    # 对于非段落/表格元素，尝试查找其所属段落的样式
                    parent_para = child.getparent()
                    while parent_para is not None and parent_para.tag != qn('w:p'):
                        parent_para = parent_para.getparent()
                    
                    if parent_para is not None:
                        # 找到父段落，尝试获取其样式
                        pPr = parent_para.find(qn('w:pPr'))
                        if pPr is not None:
                            pStyle = pPr.find(qn('w:pStyle'))
                            if pStyle is not None:
                                style_id = pStyle.get(qn('w:val'))
                                if style_id:
                                    target_style = self.get_target_style(style_id, new_doc, source_file)
                                else:
                                    target_style = DEFAULT_TARGET
                            else:
                                target_style = DEFAULT_TARGET
                        else:
                            target_style = DEFAULT_TARGET
                    else:
                        target_style = DEFAULT_TARGET
                except:
                    target_style = DEFAULT_TARGET
                
                # 复制特殊元素
                special_para = self.copy_special_element(child, new_doc, target_style)
                if special_para is not None:
                    self.stats["para"] += 1  # 计入统计
        
        # 使用重试机制保存文档
        success, actual_file, msg = self.save_with_retry(new_doc, output_file)
        if success:
            return True, f"转换完成！段落: {self.stats['para']}, 表格: {self.stats['table']}, 标题: {self.stats['heading']}。{msg}"
        else:
            return False, msg
    
    def is_part_of_exception(self, full_text, match_start, match_end, word):
        """判断单字词是否属于例外词"""
        if word == "应":
            exceptions = EXCEPTION_WORDS_YING
        elif word == "须":
            exceptions = EXCEPTION_WORDS_XU
        else:
            return False
        
        start = max(0, match_start - 20)
        end = min(len(full_text), match_end + 20)
        substr = full_text[start:end]
        for exc in exceptions:
            if exc in substr:
                pos = substr.find(exc)
                while pos != -1:
                    exc_start = start + pos
                    exc_end = exc_start + len(exc)
                    if exc_start <= match_start < exc_end:
                        return True
                    pos = substr.find(exc, pos+1)
        return False
    
    def is_multi_exception(self, full_text, match_start, match_end, word):
        """判断多字祈使词是否属于例外词"""
        start = max(0, match_start - 20)
        end = min(len(full_text), match_end + 20)
        substr = full_text[start:end]
        for exc in MULTI_EXCEPTIONS:
            if exc in substr:
                pos = substr.find(exc)
                while pos != -1:
                    exc_start = start + pos
                    exc_end = exc_start + len(exc)
                    if exc_start <= match_start < exc_end:
                        return True
                    pos = substr.find(exc, pos+1)
        return False
    
    def replace_multiple_imperative(self, run_text, full_text, run_start_offset):
        """替换多字祈使词"""
        if not run_text:
            return run_text
        def repl(match):
            word = match.group(0)
            abs_start = run_start_offset + match.start()
            abs_end = run_start_offset + match.end()
            if self.is_multi_exception(full_text, abs_start, abs_end, word):
                return word
            return MULTI_IMPERATIVE_TO_STATEMENT.get(word, word)
        return MULTI_IMPERATIVE_REGEX.sub(repl, run_text)
    
    def replace_single_imperative(self, run_text, full_text, run_start_offset):
        """替换单字祈使词"""
        if not run_text:
            return run_text
        def repl(match):
            word = match.group(0)
            abs_start = run_start_offset + match.start()
            abs_end = run_start_offset + match.end()
            if self.is_part_of_exception(full_text, abs_start, abs_end, word):
                return word
            return SINGLE_REPLACE.get(word, word)
        return SINGLE_IMPERATIVE_REGEX.sub(repl, run_text)
    
    def process_paragraph_mood(self, para):
        """处理段落语气转换"""
        full_text = ''.join(run.text for run in para.runs)
        modified = False
        current_offset = 0
        
        for run in para.runs:
            text = run.text
            if not text:
                current_offset += len(text)
                continue
            
            new_text = text
            if REPLACE_REGEX:
                new_text = REPLACE_REGEX.sub(lambda m: REPLACE_MAP.get(m.group(0), m.group(0)), new_text)
            new_text = self.replace_multiple_imperative(new_text, full_text, current_offset)
            new_text = self.replace_single_imperative(new_text, full_text, current_offset)
            new_text = new_text.replace('将将', '将把')
            
            if new_text != text:
                run.text = new_text
                modified = True
            
            current_offset += len(text)
        
        return modified
    
    def convert_mood(self, input_file, output_file=None):
        """
        祈使语气转换
        :param input_file: 输入文件
        :param output_file: 输出文件（如果为None则覆盖原文件）
        :return: 是否成功，消息
        """
        if output_file is None:
            output_file = input_file
        
        try:
            doc = Document(input_file)
        except Exception as e:
            return False, f"加载文档失败: {e}"
        
        modified_count = 0
        para_count = 0
        
        for para in doc.paragraphs:
            para_count += 1
            if self.process_paragraph_mood(para):
                modified_count += 1
        
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        para_count += 1
                        if self.process_paragraph_mood(para):
                            modified_count += 1
        
        # 使用重试机制保存文档
        success, actual_file, msg = self.save_with_retry(doc, output_file)
        if success:
            return True, f"语气转换完成！处理段落: {para_count}, 修改: {modified_count}。{msg}"
        else:
            return False, msg
    
    def ensure_style_exists(self, doc, style_name):
        """确保文档中存在指定样式"""
        try:
            doc.styles[style_name]
        except KeyError:
            style = doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
            style.base_style = doc.styles['Normal']
    
    def get_style_id(self, elem):
        """获取段落元素的样式ID"""
        pPr = elem.find(qn('w:pPr'))
        if pPr is None:
            return None
        pStyle = pPr.find(qn('w:pStyle'))
        if pStyle is None:
            return None
        return pStyle.get(qn('w:val'))
    
    def is_heading_paragraph(self, elem):
        """判断是否为标题段落"""
        if not hasattr(elem, 'tag'):
            return False
        if elem.tag != qn('w:p'):
            return False
        style_id = self.get_style_id(elem)
        return style_id in HEADING_STYLE_IDS
    
    def is_plain_paragraph(self, elem):
        """判断是否为无样式的普通正文段落"""
        if not hasattr(elem, 'tag'):
            return False
        if elem.tag != qn('w:p'):
            return False
        pPr = elem.find(qn('w:pPr'))
        if pPr is None:
            return True
        pStyle = pPr.find(qn('w:pStyle'))
        return pStyle is None
    
    def contains_image(self, elem):
        """检查段落是否包含图片"""
        if not hasattr(elem, 'tag'):
            return False
        if elem.tag != qn('w:p'):
            return False
        blips = elem.findall('.//' + qn('a:blip'))
        return len(blips) > 0
    
    def is_table_elem(self, elem):
        """判断是否为表格"""
        if not hasattr(elem, 'tag'):
            return False
        return elem.tag == qn('w:tbl')
    
    def create_answer_paragraph_element(self, doc, answer_text, answer_style):
        """创建应答句段落XML元素"""
        temp_para = doc.add_paragraph(answer_text)
        temp_para.style = answer_style
        para_elem = deepcopy(temp_para._element)
        temp_para._element.getparent().remove(temp_para._element)
        return para_elem
    
    def is_heading_paragraph(self, elem, doc=None):
        """判断段落是否为标题（通过大纲级别）"""
        return self.get_outline_level(elem, doc) > 0
    
    def insert_response_after_headings(self, input_file, output_file=None, 
                                       answer_text=None, answer_style=None):
        """
        在标题后插入应答句（改进版：使用大纲级别识别标题）
        :param input_file: 输入文件
        :param output_file: 输出文件（如果为None则覆盖原文件）
        :param answer_text: 应答文本
        :param answer_style: 应答样式
        :return: 是否成功，消息
        """
        if output_file is None:
            output_file = input_file
        if answer_text is None:
            answer_text = ANSWER_TEXT
        if answer_style is None:
            answer_style = ANSWER_STYLE
        
        try:
            doc = Document(input_file)
        except Exception as e:
            return False, f"加载文档失败: {e}"
        
        self.ensure_style_exists(doc, answer_style)
        
        # 预创建应答段落模板
        temp_para = doc.add_paragraph(answer_text)
        temp_para.style = answer_style
        answer_template = deepcopy(temp_para._element)
        temp_para._element.getparent().remove(temp_para._element)
        
        body = doc.element.body
        children = list(body)
        new_children = []
        insert_count = 0
        total_heading_count = 0
        para_index = 0
        i = 0
        
        while i < len(children):
            child = children[i]
            
            # 安全检查：确保child是XML元素
            if not hasattr(child, 'tag'):
                print(f"警告：跳过非XML元素 {type(child)}")
                i += 1
                continue
            
            new_children.append(child)
            
            # 检查是否为标题（通过大纲级别）
            if child.tag == qn('w:p'):
                if self.is_heading_paragraph(child, doc):
                    total_heading_count += 1
                    level = self.get_outline_level(child, doc)
                    
                    # 检查下一个元素
                    if i + 1 < len(children):
                        next_elem = children[i + 1]
                        
                        # 安全检查：确保next_elem是XML元素
                        if hasattr(next_elem, 'tag'):
                            # 如果下一个不是标题，则插入应答句
                            if not self.is_heading_paragraph(next_elem, doc):
                                # 判断下一个元素类型
                                if next_elem.tag == qn('w:tbl'):
                                    elem_type = "表格"
                                elif next_elem.tag == qn('w:p') and len(next_elem.findall('.//' + qn('a:blip'))) > 0:
                                    elem_type = "图片段落"
                                else:
                                    elem_type = "正文段落"
                                
                                # 插入应答句
                                answer_elem = deepcopy(answer_template)
                                new_children.append(answer_elem)
                                insert_count += 1
                            else:
                                # 连续标题，跳过
                                pass
                        else:
                            print(f"警告：next_elem不是XML元素 {type(next_elem)}")
                para_index += 1
            i += 1
        
        # 清空并重组body
        for child in list(body):
            body.remove(child)
        for elem in new_children:
            body.append(elem)
        
        # 使用重试机制保存文档
        success, actual_file, msg = self.save_with_retry(doc, output_file)
        if success:
            return True, actual_file, f"已插入 {insert_count} 个应答句，共发现标题 {total_heading_count} 个。{msg}"
        else:
            return False, output_file, msg
    
    def full_convert(self, source_file, template_file, output_file, 
                     custom_style_map=None, do_mood=True, 
                     answer_text=None, answer_style=None,
                     list_bullet=None, do_answer_insertion=True,
                     progress_callback=None, warning_callback=None):
        """
        完整转换流程：样式转换 -> 语气转换 -> 插入应答句
        固定为7个步骤，跳过的步骤也会计入进度
        :param source_file: 源文件
        :param template_file: 模板文件
        :param output_file: 最终输出文件
        :param custom_style_map: 自定义样式映射
        :param do_mood: 是否进行语气转换
        :param answer_text: 应答文本
        :param answer_style: 应答样式
        :param list_bullet: 列表段落符号
        :param do_answer_insertion: 是否插入应答句
        :param progress_callback: 进度回调函数 callback(step, message)
        :param warning_callback: 警告回调函数 callback(message)
        :return: (success, actual_output_file, message)
        """
        # 固定7个步骤，确保进度条能正确填满
        if progress_callback:
            progress_callback(1, "开始样式转换...")
        
        # 步骤1：样式转换
        temp_file_1 = output_file.rsplit('.', 1)[0] + "_temp1.docx"
        success, msg = self.convert_styles(source_file, template_file, temp_file_1, custom_style_map, list_bullet,
                                           warning_callback)
        if not success:
            return False, output_file, f"样式转换失败: {msg}"
        
        if progress_callback:
            progress_callback(2, f"样式转换完成: {msg}")
        
        # 步骤2-3：语气转换（占用2个步骤槽位）
        if do_mood:
            if progress_callback:
                progress_callback(3, "开始语气转换...")
            temp_file_2 = output_file.rsplit('.', 1)[0] + "_temp2.docx"
            success, msg = self.convert_mood(temp_file_1, temp_file_2)
            if not success:
                return False, f"语气转换失败: {msg}"
            if progress_callback:
                progress_callback(4, f"语气转换完成: {msg}")
            os.remove(temp_file_1)  # 清理临时文件
            temp_file_1 = temp_file_2
        else:
            # 跳过语气转换，但仍然占用步骤3和4
            if progress_callback:
                progress_callback(3, "跳过语气转换")
                progress_callback(4, "已跳过语气转换")
        
        # 步骤5-6：插入应答句（占用2个步骤槽位）
        actual_output_file = output_file  # 默认使用原始输出文件名
        if do_answer_insertion:
            if progress_callback:
                progress_callback(5, "开始插入应答句...")
            success, actual_file, msg = self.insert_response_after_headings(
                temp_file_1, output_file, answer_text, answer_style
            )
            if not success:
                return False, output_file, f"插入应答句失败: {msg}"
            
            actual_output_file = actual_file  # 更新为实际文件名
            
            if progress_callback:
                progress_callback(6, f"插入应答句完成: {msg}")
        else:
            # 不插入应答句，直接复制文件，但仍然占用步骤5和6
            if progress_callback:
                progress_callback(5, "跳过应答句插入")
            import shutil
            shutil.copy2(temp_file_1, output_file)
            if progress_callback:
                progress_callback(6, "已跳过应答句插入")
        
        # 清理临时文件
        try:
            if os.path.exists(temp_file_1):
                os.remove(temp_file_1)
        except:
            pass
        
        # 步骤7：完成
        if progress_callback:
            progress_callback(7, "转换全部完成！")
        
        return True, actual_output_file, "转换成功完成！"
    
    def save_with_retry(self, doc, output_file, max_retries=10):
        """
        智能保存文档：先检查文件是否被占用，如果是则直接使用备用文件名。
        :param doc: Document对象
        :param output_file: 原始输出文件路径
        :param max_retries: 最大重试次数
        :return: (success, actual_output_file, message)
        """
        import os
        import time
        
        # 首先检查文件是否存在且被占用
        if os.path.exists(output_file):
            try:
                # 尝试以独占模式打开文件，检查是否被占用
                with open(output_file, 'r+b') as f:
                    pass  # 如果能打开，说明没被占用
            except (PermissionError, IOError):
                # 文件被占用，直接使用备用文件名
                base, ext = os.path.splitext(output_file)
                time_suffix = datetime.now().strftime("_%H%M%S")
                backup_file = f"{base}{time_suffix}{ext}"
                print(f"  检测到文件被占用，直接使用备用文件名: {backup_file}")
                
                # 尝试保存备用文件名
                try:
                    doc.save(backup_file)
                    return True, backup_file, f"原文件被占用，文档已保存到: {backup_file}"
                except Exception as e:
                    return False, output_file, f"保存备用文件失败: {e}"
        
        # 文件未被占用或不存在，直接保存
        current_file = output_file
        for attempt in range(max_retries):
            try:
                doc.save(current_file)
                if attempt == 0:
                    return True, current_file, f"文档已保存到 {current_file}"
                else:
                    return True, current_file, f"文档已保存到备用文件名: {current_file}"
            except (PermissionError, OSError, IOError) as e:
                # 文件在保存过程中被占用（罕见情况）
                if attempt == 0:
                    print(f"  警告：保存文档失败（文件可能被占用）: {e}")
                
                # 生成新的文件名
                base, ext = os.path.splitext(output_file)
                time_suffix = datetime.now().strftime("_%H%M%S")
                current_file = f"{base}{time_suffix}{ext}"
                print(f"  尝试备用文件名: {current_file}")
                
                # 稍等片刻再重试
                time.sleep(0.3)
            except Exception as e:
                # 其他异常直接返回失败
                return False, output_file, f"保存文档失败: {e}"
        
        # 重试次数用尽
        return False, output_file, f"无法保存文档，已尝试 {max_retries} 次"


if __name__ == "__main__":
    # 测试代码
    converter = DocumentConverter()
    print("文档转换器模块加载成功")
    print(f"Pillow可用: {PIL_AVAILABLE}")
