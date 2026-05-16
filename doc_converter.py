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
        # 使用实例变量中的样式映射，避免使用全局变量
        style_map = getattr(self, 'current_style_map', STYLE_MAP)
        target = style_map.get(original_style_name)
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
    
    def extract_and_add_images(self, source_para, new_para, page_width_emu, available_width_emu):
        """从源段落提取图片并添加到新段落（DRY原则：避免代码重复）"""
        for run in source_para.runs:
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
            # ⚡ 使用统一的图片处理方法
            self.extract_and_add_images(source_para, new_para, page_width_emu, available_width_emu)
            return new_para
        
        if self.has_numbering(source_para):
            new_para.add_run(self.list_bullet)
            self.remove_auto_numbering(new_para)
            # 对于列表段落，使用专门的编号清理函数
            full_text = ''.join(run.text for run in source_para.runs)
            cleaned_text = clean_list_numbering(full_text)
            if cleaned_text:
                new_para.add_run(cleaned_text)
            # ⚡ 使用统一的图片处理方法
            self.extract_and_add_images(source_para, new_para, page_width_emu, available_width_emu)
            return new_para
        
        # 普通段落：复制文本和图片
        for run in source_para.runs:
            if run.text:
                new_para.add_run(run.text)
        
        # ⚡ 使用统一的图片处理方法
        self.extract_and_add_images(source_para, new_para, page_width_emu, available_width_emu)
        
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
                       warning_callback=None, source_styles_cache=None):
        """
        样式转换主函数
        :param source_file: 源文件路径
        :param template_file: 模板文件路径
        :param output_file: 输出文件路径
        :param custom_style_map: 自定义样式映射表（可选）
        :param list_bullet: 列表段落符号（可选，默认为配置常量）
        :param warning_callback: 警告回调函数 callback(message)
        :param source_styles_cache: 缓存的源文件样式列表（可选，避免重复分析）
        :return: 是否成功
        """
        # 使用局部样式映射副本，避免修改全局变量
        style_map = STYLE_MAP.copy()
        if custom_style_map:
            style_map.update(custom_style_map)
        
        # 将样式映射存储为实例变量，供get_target_style使用
        self.current_style_map = style_map
        
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
        
        # ⚡ 性能优化：使用缓存的样式列表，避免重复分析
        if source_styles_cache:
            self.source_styles = source_styles_cache
        else:
            # 如果没有缓存，重新分析（兜底逻辑）
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
        """
        判断段落是否为标题
        判断条件（满足任一即可）：
        1. 有大纲级别（outlineLvl > 0）
        2. 样式名称以 'Heading' 开头（如 Heading 1, Heading 2 等）
        3. 样式ID是纯数字（Word中常见：1=Heading 1, 2=Heading 2, ...）
        """
        # 方法1：检查大纲级别
        if self.get_outline_level(elem, doc) > 0:
            return True
        
        # 方法2：检查样式名称或样式ID
        if hasattr(elem, 'tag') and elem.tag == qn('w:p'):
            pPr = elem.find(qn('w:pPr'))
            if pPr is not None:
                pStyle = pPr.find(qn('w:pStyle'))
                if pStyle is not None:
                    style_id = pStyle.get(qn('w:val'))
                    if style_id:
                        # 检查样式ID是否包含'heading'
                        if 'heading' in style_id.lower():
                            return True
                        # 检查样式ID是否为纯数字（Word中的Heading样式）
                        if style_id.isdigit():
                            return True
                        # 检查样式名称是否包含'heading'（需要doc）
                        if doc is not None:
                            try:
                                style = doc.styles[style_id]
                                style_name = style.name
                                if 'heading' in style_name.lower():
                                    return True
                            except:
                                pass
        
        return False
    
    def insert_response_after_headings(self, input_file, output_file=None, 
                                       answer_text=None, answer_style=None,
                                       mode='before_heading'):
        """
        在标题前后插入应答句（改进版：使用大纲级别识别标题）
        :param input_file: 输入文件
        :param output_file: 输出文件（如果为None则覆盖原文件）
        :param answer_text: 应答文本
        :param answer_style: 应答样式
        :param mode: 插入模式
            - 'before_heading': 标题前插入（默认，原有逻辑）
            - 'after_heading': 章节后插入（在章节正文最后一段后插入）
            - 'copy_chapter': 复制章节内容（未来扩展）
            - 'before_paragraph': 逐段前插入（未来扩展）
            - 'after_paragraph': 逐段后插入（未来扩展）
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
        
        # 根据模式选择不同的处理逻辑
        if mode == 'before_heading':
            # 原有逻辑：标题前插入（下一个不是标题时插入）
            insert_count, total_heading_count = self._insert_before_headings(
                children, new_children, answer_template, doc
            )
        elif mode == 'after_heading':
            # 新需求：章节后插入（在章节正文最后一段后插入）
            insert_count, total_heading_count = self._insert_after_headings(
                children, new_children, answer_template, doc
            )
        elif mode == 'copy_chapter':
            # 复制章节插入（在应答句后复制章节内容）
            insert_count, total_heading_count = self._insert_with_copy_chapter(
                children, new_children, answer_template, doc
            )
        elif mode == 'before_paragraph':
            # 逐段前应答（在非标题段落前插入应答句）
            insert_count, total_heading_count = self._insert_before_paragraphs(
                children, new_children, answer_template, doc
            )
        elif mode == 'after_paragraph':
            # 逐段后应答（在非标题段落后插入应答句）
            insert_count, total_heading_count = self._insert_after_paragraphs(
                children, new_children, answer_template, doc
            )
        else:
            return False, output_file, f"不支持的插入模式: {mode}"
        
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
    
    def _insert_before_headings(self, children, new_children, answer_template, doc):
        """
        在标题前插入应答句（原有逻辑）
        判断条件：如果标题后下一个元素不是标题，则在该标题前插入
        :return: (insert_count, total_heading_count)
        """
        insert_count = 0
        total_heading_count = 0
        i = 0
        
        while i < len(children):
            child = children[i]
            
            # 安全检查
            if not hasattr(child, 'tag'):
                i += 1
                continue
            
            new_children.append(child)
            
            # 检查是否为标题
            if child.tag == qn('w:p') and self.is_heading_paragraph(child, doc):
                total_heading_count += 1
                
                # 检查下一个元素
                if i + 1 < len(children):
                    next_elem = children[i + 1]
                    
                    if hasattr(next_elem, 'tag'):
                        # 如果下一个不是标题，则插入应答句
                        if not self.is_heading_paragraph(next_elem, doc):
                            answer_elem = deepcopy(answer_template)
                            new_children.append(answer_elem)
                            insert_count += 1
            
            i += 1
        
        return insert_count, total_heading_count
    
    def _insert_after_headings(self, children, new_children, answer_template, doc):
        """
        在章节末尾插入应答句（需求2：章节后插入）
        判断条件：如果标题前是正文段落（不是标题），就在这个正文后插入应答句
        特殊情况：
        - 全文档第一个标题前不插入（因为前面没有章节）
        - 两个标题之间不插入
        - 文章最后一段如果是正文，在其后插入
        :return: (insert_count, total_heading_count)
        """
        insert_count = 0
        total_heading_count = 0
        
        # 第一步：遍历所有元素，添加元素并统计标题
        for i, child in enumerate(children):
            # 安全检查
            if not hasattr(child, 'tag'):
                new_children.append(child)
                continue
            
            # 统计标题数量
            if child.tag == qn('w:p') and self.is_heading_paragraph(child, doc):
                total_heading_count += 1
            
            # 添加当前元素
            new_children.append(child)
            
            # 第二步：判断是否需要在当前元素后插入应答句
            # 条件：当前不是标题 + 下一个元素是标题
            if i + 1 < len(children):
                next_elem = children[i + 1]
                
                # 检查下一个元素是否为标题
                if hasattr(next_elem, 'tag') and next_elem.tag == qn('w:p'):
                    if self.is_heading_paragraph(next_elem, doc):
                        # 下一个是标题，检查当前元素是否不是标题
                        is_not_heading = True
                        
                        # 检查当前是否为标题
                        if hasattr(child, 'tag') and child.tag == qn('w:p'):
                            if self.is_heading_paragraph(child, doc):
                                is_not_heading = False
                        
                        # 如果当前不是标题（可以是正文、表格、图片等），则在其后插入应答句
                        if is_not_heading:
                            answer_elem = deepcopy(answer_template)
                            new_children.append(answer_elem)
                            insert_count += 1
        
        # 第三步：处理文章最后一段
        # 从后往前找第一个非标题元素（可以是正文、表格、图片等），在其后插入应答句
        if children:
            # 从后往前遍历，找到第一个非标题元素
            last_content_elem = None
            for i in range(len(children) - 1, -1, -1):
                elem = children[i]
                
                if not hasattr(elem, 'tag'):
                    continue
                
                # 检查是否为标题段落
                is_heading = False
                if elem.tag == qn('w:p'):
                    if self.is_heading_paragraph(elem, doc):
                        is_heading = True
                
                # 如果不是标题，则作为最后一个内容元素
                if not is_heading:
                    last_content_elem = elem
                    break
            
            # 如果找到非标题元素，在其后插入应答句
            if last_content_elem is not None:
                answer_elem = deepcopy(answer_template)
                new_children.append(answer_elem)
                insert_count += 1
        
        return insert_count, total_heading_count
    
    def _insert_with_copy_chapter(self, children, new_children, answer_template, doc):
        """
        复制章节插入（需求3）
        逻辑：
        1. 找到章节末尾（和章节后插入一样的判断条件）
        2. 在该位置插入应答句
        3. 复制从上一个标题后到当前位置的所有内容，插入到应答句之后
        :return: (insert_count, total_heading_count)
        """
        from copy import deepcopy as deep_copy
        
        insert_count = 0
        total_heading_count = 0
        
        # 第一步：遍历所有元素，记录每个标题的位置
        heading_positions = []  # 存储标题的索引
        for i, child in enumerate(children):
            if hasattr(child, 'tag') and child.tag == qn('w:p'):
                if self.is_heading_paragraph(child, doc):
                    heading_positions.append(i)
                    total_heading_count += 1
        
        # 第二步：处理每个元素，在章节末尾插入应答句并复制章节内容
        i = 0
        while i < len(children):
            child = children[i]
            
            # 安全检查
            if not hasattr(child, 'tag'):
                new_children.append(child)
                i += 1
                continue
            
            # 添加当前元素
            new_children.append(child)
            
            # 判断是否需要在当前元素后插入应答句并复制章节
            # 条件：当前不是标题 + 下一个元素是标题
            if i + 1 < len(children):
                next_elem = children[i + 1]
                
                # 检查下一个元素是否为标题
                if hasattr(next_elem, 'tag') and next_elem.tag == qn('w:p'):
                    if self.is_heading_paragraph(next_elem, doc):
                        # 下一个是标题，检查当前元素是否不是标题
                        is_not_heading = True
                        
                        # 检查当前是否为标题
                        if hasattr(child, 'tag') and child.tag == qn('w:p'):
                            if self.is_heading_paragraph(child, doc):
                                is_not_heading = False
                        
                        # 如果当前不是标题（可以是正文、表格、图片等），则在其后插入应答句并复制章节
                        if is_not_heading:
                            # 1. 插入应答句
                            answer_elem = deep_copy(answer_template)
                            new_children.append(answer_elem)
                            insert_count += 1
                            
                            # 2. 找到上一个标题的位置
                            last_heading_idx = -1
                            for h_idx in heading_positions:
                                if h_idx < i:
                                    last_heading_idx = h_idx
                                else:
                                    break
                            
                            # 3. 复制从上一个标题后到当前位置的所有内容
                            if last_heading_idx >= 0:
                                # 从 last_heading_idx + 1 到 i（包含i）
                                for j in range(last_heading_idx + 1, i + 1):
                                    copied_elem = deep_copy(children[j])
                                    new_children.append(copied_elem)
            
            i += 1
        
        # 第三步：处理文章最后一段
        # 从后往前找第一个非标题元素，在其后插入应答句并复制章节内容
        if children:
            # 从后往前遍历，找到第一个非标题元素
            last_content_idx = -1
            for i in range(len(children) - 1, -1, -1):
                elem = children[i]
                
                if not hasattr(elem, 'tag'):
                    continue
                
                # 检查是否为标题段落
                is_heading = False
                if elem.tag == qn('w:p'):
                    if self.is_heading_paragraph(elem, doc):
                        is_heading = True
                
                # 如果不是标题，则作为最后一个内容元素
                if not is_heading:
                    last_content_idx = i
                    break
            
            # 如果找到非标题元素，在其后插入应答句并复制章节内容
            if last_content_idx >= 0:
                # 1. 插入应答句
                answer_elem = deep_copy(answer_template)
                new_children.append(answer_elem)
                insert_count += 1
                
                # 2. 找到上一个标题的位置
                last_heading_idx = -1
                for h_idx in heading_positions:
                    if h_idx < last_content_idx:
                        last_heading_idx = h_idx
                    else:
                        break
                
                # 3. 复制从上一个标题后到当前位置的所有内容
                if last_heading_idx >= 0:
                    # 从 last_heading_idx + 1 到 last_content_idx（包含）
                    for j in range(last_heading_idx + 1, last_content_idx + 1):
                        copied_elem = deep_copy(children[j])
                        new_children.append(copied_elem)
        
        return insert_count, total_heading_count
    
    def _insert_before_paragraphs(self, children, new_children, answer_template, doc):
        """
        逐段前应答（需求4）- 改进版：支持语义段落分组
        逻辑：
        1. 将连续的语义相关段落分组（短句、引号上下文、列表）
        2. 在每个语义单元前插入一个应答句
        :return: (insert_count, total_heading_count)
        """
        from copy import deepcopy as deep_copy
        
        insert_count = 0
        total_heading_count = 0
        
        # 第一步：将元素分组为语义单元
        semantic_groups = self._group_semantic_units(children, doc)
        
        # 第二步：遍历每个语义单元，在单元前插入应答句
        for group in semantic_groups:
            if not group:
                continue
            
            first_elem = group[0]
            
            # 统计标题数量
            if hasattr(first_elem, 'tag') and first_elem.tag == qn('w:p'):
                if self.is_heading_paragraph(first_elem, doc):
                    total_heading_count += len([e for e in group if hasattr(e, 'tag') and e.tag == qn('w:p') and self.is_heading_paragraph(e, doc)])
            
            # 判断是否为需要插入应答句的语义单元
            should_insert = self._should_insert_answer_for_group(group, doc)
            
            if should_insert:
                # 在语义单元前插入应答句
                answer_elem = deep_copy(answer_template)
                new_children.append(answer_elem)
                insert_count += 1
            
            # 添加语义单元中的所有元素
            for elem in group:
                new_children.append(elem)
        
        return insert_count, total_heading_count
    
    def _is_list_paragraph(self, elem):
        """
        判断段落是否是列表（有编号或项目符号）
        :param elem: 段落元素
        :return: True 如果是列表段落
        """
        if not hasattr(elem, 'tag') or elem.tag != qn('w:p'):
            return False
        
        pPr = elem.find(qn('w:pPr'))
        if pPr is not None:
            # 检查是否有编号（numPr）
            numPr = pPr.find(qn('w:numPr'))
            if numPr is not None:
                return True
        
        return False
    
    def _get_paragraph_text(self, elem):
        """
        获取段落的文本内容
        :param elem: 段落元素
        :return: 文本字符串
        """
        if not hasattr(elem, 'tag') or elem.tag != qn('w:p'):
            return ""
        
        text_elems = elem.findall('.//' + qn('w:t'))
        return ''.join([t.text for t in text_elems if t.text])
    
    def _ends_with_colon_or_quote(self, text):
        """
        判断文本是否以冒号或引号结尾（需要与下一段合并）
        :param text: 文本内容
        :return: True 如果需要合并
        """
        if not text:
            return False
        
        # 去除末尾空白
        text = text.rstrip()
        
        # 检查是否以冒号、冒号+引号结尾
        if text.endswith('：') or text.endswith(':'):
            return True
        if text.endswith('”') or text.endswith('"'):
            # 检查前面是否有冒号
            if len(text) > 1 and (text[-2] == '：' or text[-2] == ':'):
                return True
        
        return False
    
    def _is_short_paragraph(self, text, threshold=20):
        """
        判断是否为短段落
        :param text: 文本内容
        :param threshold: 字数阈值
        :return: True 如果是短段落
        """
        if not text:
            return True
        return len(text.strip()) < threshold
    
    def _is_manual_numbered_paragraph(self, text):
        """
        判断段落是否是手动编号（如"1、"、"2）"、"a."等）
        :param text: 段落文本
        :return: True 如果是手动编号段落
        """
        if not text:
            return False
        
        text = text.strip()
        
        # 匹配常见的中文编号格式
        import re
        patterns = [
            r'^\d+[、\.．]',      # 1、 或 1. 或 1．
            r'^\d+）',             # 1）
            r'^\d+\)',             # 1)
            r'^[（(]\d+[）)]',     # （1） 或 (1)
            r'^[一二三四五六七八九十]+[、\.．]',  # 一、 或 一.
            r'^[a-zA-Z][、\.．]',  # a. 或 A、
            r'^[a-zA-Z]）',        # a）
            r'^[a-zA-Z]\)',        # a)
        ]
        
        for pattern in patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _is_bullet_point_paragraph(self, text):
        """
        判断段落是否是项目符号列表（如●、■、◆等）
        :param text: 段落文本
        :return: True 如果是项目符号段落
        """
        if not text:
            return False
        
        text = text.strip()
        
        # 常见的项目符号
        bullet_symbols = ['●', '○', '■', '□', '◆', '◇', '▲', '△', '►', '▶', '•', '-', '*']
        
        for symbol in bullet_symbols:
            if text.startswith(symbol):
                return True
        
        return False
    
    def _is_empty_paragraph(self, text):
        """
        判断段落是否为空行
        :param text: 段落文本
        :return: True 如果是空行
        """
        if not text:
            return True
        return len(text.strip()) == 0
    
    def _group_semantic_units(self, children, doc):
        """
        将元素分组为语义单元
        规则：
        1. 标题单独成组
        2. 连续的列表项合并为一个组
        3. 以冒号/引号结尾的段落与下一段合并
        4. 连续的短段落合并为一个组
        :param children: 所有元素列表
        :param doc: 文档对象
        :return: 分组后的列表 [[elem1, elem2], [elem3], ...]
        """
        groups = []
        current_group = []
        
        for i, child in enumerate(children):
            if not hasattr(child, 'tag'):
                # 非段落元素（如表格），单独成组
                if current_group:
                    groups.append(current_group)
                    current_group = []
                groups.append([child])
                continue
            
            # 检查是否为标题
            is_heading = False
            if child.tag == qn('w:p') and self.is_heading_paragraph(child, doc):
                is_heading = True
            
            # 获取文本内容（提前获取，供后续判断使用）
            text = self._get_paragraph_text(child) if child.tag == qn('w:p') else ""
            
            # 检查是否为空行
            is_empty = False
            if child.tag == qn('w:p'):
                is_empty = self._is_empty_paragraph(text)
            
            # 如果是空行，跳过不处理
            if is_empty:
                continue
            
            # 检查是否为列表
            is_list = False
            if child.tag == qn('w:p'):
                is_list = self._is_list_paragraph(child)
            
            # 检查是否为手动编号段落
            is_manual_numbered = False
            if child.tag == qn('w:p'):
                is_manual_numbered = self._is_manual_numbered_paragraph(text)
            
            # 检查是否为项目符号段落
            is_bullet_point = False
            if child.tag == qn('w:p'):
                is_bullet_point = self._is_bullet_point_paragraph(text)
            
            # 决策逻辑
            if is_heading:
                # 标题：结束当前组，标题单独成组
                if current_group:
                    groups.append(current_group)
                    current_group = []
                groups.append([child])
            elif is_list or is_manual_numbered or is_bullet_point:
                # 列表项（包括自动列表、手动编号、项目符号）：如果前一个也是列表，则合并；否则新起一组
                should_merge = False
                
                if current_group:
                    # 检查前一段是否是列表/编号/项目符号
                    if (self._is_last_group_list(current_group, doc) or 
                        self._is_last_group_manual_numbered(current_group) or
                        self._is_last_group_bullet_point(current_group)):
                        should_merge = True
                    else:
                        # 检查前一段是否以冒号/引号结尾
                        prev_text = self._get_last_paragraph_text(current_group)
                        if self._ends_with_colon_or_quote(prev_text):
                            should_merge = True
                
                if should_merge:
                    current_group.append(child)
                else:
                    if current_group:
                        groups.append(current_group)
                    current_group = [child]
            elif self._ends_with_colon_or_quote(text):
                # 以冒号/引号结尾：与下一段合并
                current_group.append(child)
                # 标记需要与下一段合并（通过保持 current_group 不结束）
            elif self._is_short_paragraph(text) and current_group:
                # 短段落：尝试与前一段合并
                prev_text = self._get_last_paragraph_text(current_group)
                if self._is_short_paragraph(prev_text) or self._ends_with_colon_or_quote(prev_text):
                    # 前一段也是短句或以冒号结尾，合并
                    current_group.append(child)
                else:
                    # 否则新起一组
                    groups.append(current_group)
                    current_group = [child]
            else:
                # 普通段落：检查是否需要与前一段合并
                if current_group:
                    prev_text = self._get_last_paragraph_text(current_group)
                    prev_is_numbered_or_bullet = self._is_last_group_manual_numbered(current_group) or self._is_last_group_bullet_point(current_group)
                    
                    if self._ends_with_colon_or_quote(prev_text):
                        # 前一段以冒号结尾，合并
                        current_group.append(child)
                    elif prev_is_numbered_or_bullet:
                        # 前一段是手动编号或项目符号，当前普通段落是其内容，合并
                        current_group.append(child)
                    else:
                        # 否则新起一组
                        groups.append(current_group)
                        current_group = [child]
                else:
                    current_group = [child]
        
        # 处理最后一组
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _is_last_group_list(self, group, doc):
        """检查组中最后一个元素是否是列表"""
        if not group:
            return False
        last_elem = group[-1]
        if hasattr(last_elem, 'tag') and last_elem.tag == qn('w:p'):
            return self._is_list_paragraph(last_elem)
        return False
    
    def _is_last_group_manual_numbered(self, group):
        """检查组中最后一个元素是否是手动编号段落"""
        if not group:
            return False
        last_elem = group[-1]
        if hasattr(last_elem, 'tag') and last_elem.tag == qn('w:p'):
            text = self._get_paragraph_text(last_elem)
            return self._is_manual_numbered_paragraph(text)
        return False
    
    def _is_last_group_bullet_point(self, group):
        """检查组中最后一个元素是否是项目符号段落"""
        if not group:
            return False
        last_elem = group[-1]
        if hasattr(last_elem, 'tag') and last_elem.tag == qn('w:p'):
            text = self._get_paragraph_text(last_elem)
            return self._is_bullet_point_paragraph(text)
        return False
    
    def _get_last_paragraph_text(self, group):
        """获取组中最后一个段落的文本"""
        for elem in reversed(group):
            if hasattr(elem, 'tag') and elem.tag == qn('w:p'):
                return self._get_paragraph_text(elem)
        return ""
    
    def _should_insert_answer_for_group(self, group, doc):
        """
        判断是否应该为该语义单元插入应答句
        :param group: 语义单元（元素列表）
        :param doc: 文档对象
        :return: True 如果需要插入
        """
        if not group:
            return False
        
        first_elem = group[0]
        
        # 排除标题
        if hasattr(first_elem, 'tag') and first_elem.tag == qn('w:p'):
            if self.is_heading_paragraph(first_elem, doc):
                return False
        
        # 排除图片
        if hasattr(first_elem, 'tag') and first_elem.tag == qn('w:p'):
            if len(first_elem.findall('.//' + qn('a:blip'))) > 0:
                return False
        
        # 其他情况都插入（包括列表、普通段落等）
        return True
    
    def _insert_after_paragraphs(self, children, new_children, answer_template, doc):
        """
        逐段后应答（需求5）- 改进版：支持语义段落分组
        逻辑：
        1. 将连续的语义相关段落分组（短句、引号上下文、列表）
        2. 在每个语义单元后插入一个应答句
        :return: (insert_count, total_heading_count)
        """
        from copy import deepcopy as deep_copy
        
        insert_count = 0
        total_heading_count = 0
        
        # 第一步：将元素分组为语义单元
        semantic_groups = self._group_semantic_units(children, doc)
        
        # 第二步：遍历每个语义单元，在单元后插入应答句
        for group in semantic_groups:
            if not group:
                continue
            
            first_elem = group[0]
            
            # 统计标题数量
            if hasattr(first_elem, 'tag') and first_elem.tag == qn('w:p'):
                if self.is_heading_paragraph(first_elem, doc):
                    total_heading_count += len([e for e in group if hasattr(e, 'tag') and e.tag == qn('w:p') and self.is_heading_paragraph(e, doc)])
            
            # 先添加语义单元中的所有元素
            for elem in group:
                new_children.append(elem)
            
            # 判断是否为需要插入应答句的语义单元
            should_insert = self._should_insert_answer_for_group(group, doc)
            
            if should_insert:
                # 在语义单元后插入应答句
                answer_elem = deep_copy(answer_template)
                new_children.append(answer_elem)
                insert_count += 1
        
        return insert_count, total_heading_count
    
    def full_convert(self, source_file, template_file, output_file, 
                     custom_style_map=None, do_mood=True, 
                     answer_text=None, answer_style=None,
                     list_bullet=None, do_answer_insertion=True,
                     answer_mode='before_heading',
                     progress_callback=None, warning_callback=None,
                     source_styles_cache=None):
        """
        完整转换流程：样式转换 -> 语气转换 -> 插入应答句
        ⚡ 性能优化：合并为一次性流水线，避免多次加载/保存文档
        :param source_file: 源文件
        :param template_file: 模板文件
        :param output_file: 最终输出文件
        :param custom_style_map: 自定义样式映射
        :param do_mood: 是否进行语气转换
        :param answer_text: 应答文本
        :param answer_style: 应答样式
        :param list_bullet: 列表段落符号
        :param do_answer_insertion: 是否插入应答句
        :param answer_mode: 应答句插入模式
            - 'before_heading': 标题前插入（默认）
            - 'after_heading': 章节后插入（在章节正文最后一段后插入）
        :param progress_callback: 进度回调函数 callback(step, message)
        :param warning_callback: 警告回调函数 callback(message)
        :param source_styles_cache: 缓存的源文件样式列表（可选，避免重复分析）
        :return: (success, actual_output_file, message)
        """
        import time
        start_time = time.time()
        
        # 固定7个步骤，确保进度条能正确填满
        if progress_callback:
            progress_callback(1, "正在进行转换...")
        
        # ========== ⚡ 性能优化：一次性流水线处理 ==========
        # 原来：Load → StyleConv → Save → Load → MoodConv → Save → Load → AnswerInsert → Save
        # 现在：  Load → StyleConv → MoodConv → AnswerInsert → Save（一次加载，一次保存）
        
        # 步骤1：样式转换（返回Document对象，不保存）
        doc = self._convert_styles_in_memory(source_file, template_file, custom_style_map, list_bullet,
                                              warning_callback, source_styles_cache)
        if doc is None:
            elapsed = time.time() - start_time
            return False, output_file, f"样式转换失败（耗时{elapsed:.1f}秒）"
        
        if progress_callback:
            progress_callback(2, "正在进行转换...")
        
        # 步骤2-3：语气转换（直接在内存中的Document对象上操作）
        if do_mood:
            if progress_callback:
                progress_callback(3, "正在进行转换...")
            mood_result = self._convert_mood_in_memory(doc)
            if not mood_result:
                elapsed = time.time() - start_time
                return False, output_file, f"语气转换失败（耗时{elapsed:.1f}秒）"
            if progress_callback:
                progress_callback(4, "正在进行转换...")
        else:
            # 跳过语气转换，但仍然占用步骤3和4
            if progress_callback:
                progress_callback(3, "正在进行转换...")
                progress_callback(4, "正在进行转换...")
        
        # 步骤5-6：插入应答句（直接在内存中的Document对象上操作）
        actual_output_file = output_file  # 默认使用原始输出文件名
        if do_answer_insertion:
            if progress_callback:
                progress_callback(5, "正在进行转换...")
            insert_result = self._insert_response_in_memory(
                doc, answer_text, answer_style, mode=answer_mode
            )
            if not insert_result:
                elapsed = time.time() - start_time
                return False, output_file, f"插入应答句失败（耗时{elapsed:.1f}秒）"
            
            if progress_callback:
                progress_callback(6, "正在进行转换...")
        else:
            # 不插入应答句，但仍然占用步骤5和6
            if progress_callback:
                progress_callback(5, "正在进行转换...")
                progress_callback(6, "正在进行转换...")
        
        # 步骤7：保存文档（只保存一次！）
        if progress_callback:
            progress_callback(7, "正在保存...")
        
        success, actual_file, msg = self.save_with_retry(doc, output_file)
        elapsed = time.time() - start_time
        
        if success:
            return True, actual_file, f"转换成功完成！（耗时{elapsed:.1f}秒）"
        else:
            return False, output_file, f"保存失败: {msg}（耗时{elapsed:.1f}秒）"
    
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
                time_suffix = datetime.now().strftime("_%H%M")
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
    
    def _convert_styles_in_memory(self, source_file, template_file, custom_style_map=None, list_bullet=None,
                                   warning_callback=None, source_styles_cache=None):
        """
        ⚡ 性能优化：在内存中进行样式转换，不保存中间文件
        :return: Document对象或None（失败时）
        """
        try:
            from docx import Document
            from copy import deepcopy
            from lxml import etree
            from docx.oxml.ns import qn
            
            # 加载源文档和模板文档
            source_doc = Document(source_file)
            new_doc = Document(template_file)
            self.clear_document_content(new_doc)
            
            # 设置样式映射
            style_map = STYLE_MAP.copy()
            if custom_style_map:
                style_map.update(custom_style_map)
            self.current_style_map = style_map
            
            # 使用缓存的样式列表或重新分析
            if source_styles_cache:
                self.source_styles = source_styles_cache
            else:
                self.source_styles = self.get_all_styles_from_doc(source_doc)
            
            # 获取页面宽度信息
            section = new_doc.sections[0]
            page_width = section.page_width
            left_margin = section.left_margin
            right_margin = section.right_margin
            available_width = page_width - left_margin - right_margin
            
            # 处理源文档的所有元素
            body = source_doc.element.body
            para_idx = 0
            table_idx = 0
            
            for child in body:
                if child.tag == qn('w:p'):
                    if para_idx < len(source_doc.paragraphs):
                        para = source_doc.paragraphs[para_idx]
                        src_style = para.style.name
                        target_style = self.get_target_style(src_style, new_doc, source_file)
                        
                        # 使用copy_paragraph_with_images方法复制段落
                        self.copy_paragraph_with_images(
                            para, new_doc, target_style,
                            page_width, available_width,
                            para_idx, source_file,
                            warning_callback=None
                        )
                        para_idx += 1
                elif child.tag == qn('w:tbl'):
                    if table_idx < len(source_doc.tables):
                        table = source_doc.tables[table_idx]
                        self.copy_table_with_images(
                            table, new_doc, table_idx, available_width,
                            source_file, warning_callback=None
                        )
                        table_idx += 1
            
            return new_doc
        except Exception as e:
            print(f"样式转换失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _convert_mood_in_memory(self, doc):
        """
        ⚡ 性能优化：在内存中进行语气转换，不保存中间文件
        :param doc: Document对象
        :return: True/False
        """
        try:
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
            
            print(f"语气转换完成！处理段落: {para_count}, 修改: {modified_count}")
            return True
        except Exception as e:
            print(f"语气转换失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _insert_response_in_memory(self, doc, answer_text=None, answer_style=None, mode='before_heading'):
        """
        ⚡ 性能优化：在内存中插入应答句，不保存中间文件
        :param doc: Document对象
        :param answer_text: 应答文本
        :param answer_style: 应答样式
        :param mode: 插入模式
        :return: True/False
        """
        try:
            from copy import deepcopy
            from docx.oxml.ns import qn
            
            if answer_text is None:
                answer_text = ANSWER_TEXT
            if answer_style is None:
                answer_style = ANSWER_STYLE
            
            self.ensure_style_exists(doc, answer_style)
            
            # 预创建应答段落模板
            temp_para = doc.add_paragraph(answer_text)
            temp_para.style = answer_style
            answer_template = deepcopy(temp_para._element)
            temp_para._element.getparent().remove(temp_para._element)
            
            body = doc.element.body
            children = list(body)
            new_children = []
            
            # 根据模式选择不同的处理逻辑
            if mode == 'before_heading':
                insert_count, total_heading_count = self._insert_before_headings(
                    children, new_children, answer_template, doc
                )
            elif mode == 'after_heading':
                insert_count, total_heading_count = self._insert_after_chapters(
                    children, new_children, answer_template, doc
                )
            else:
                # 默认使用标题前插入
                insert_count, total_heading_count = self._insert_before_headings(
                    children, new_children, answer_template, doc
                )
            
            # 清空并重组body
            for child in list(body):
                body.remove(child)
            for elem in new_children:
                body.append(elem)
            
            print(f"插入应答句完成！插入: {insert_count}个，标题: {total_heading_count}个")
            return True
        except Exception as e:
            print(f"插入应答句失败: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    # 测试代码
    converter = DocumentConverter()
    print("文档转换器模块加载成功")
    print(f"Pillow可用: {PIL_AVAILABLE}")
