# -*- coding: utf-8 -*-
"""
文件上传与样式分析组件
从 app.py 提取的工具函数
"""
import streamlit as st
from pathlib import Path
import logging
from docx import Document
from docx.enum.style import WD_STYLE_TYPE

logger = logging.getLogger('WordStyle')


def count_paragraphs(docx_file):
    """统计文档段落数（不包括标题）"""
    try:
        doc = docx_file if hasattr(docx_file, 'paragraphs') else Document(docx_file)
        paragraph_count = 0
        
        for para in doc.paragraphs:
            # 检查是否为标题样式
            style_name = para.style.name.lower() if para.style else ''
            
            # 排除所有标题样式（Heading 1-9）
            is_heading = (
                'heading' in style_name
                or '标题' in style_name
                or (
                    para.style
                    and para.style.type == WD_STYLE_TYPE.PARAGRAPH
                    and hasattr(para, 'outline_level')
                    and para.outline_level is not None
                )
            )
            
            # 只统计非标题段落
            if not is_heading:
                paragraph_count += 1
        
        return paragraph_count
    except:
        return 0


def get_template_styles_list(template_file):
    """获取模板文档中所有可选的「目标样式」。

    返回两段拼起来的列表（真实样式在前、格式快照在后）：
      1) 模板里真实存在的段落样式名
      2) 模板段落身上出现过的「样式 + 直接格式」组合（格式快照）

    第 2 类是 Word 样式窗格里显示的形如
      「标题 1 + 四号, 段前: 0 磅, 段后: 0 磅, 行距: 1.5 倍行距」
    的条目 —— 它不是文档里真正的样式，而是某段落套了 X 样式、又在段落上额外刷了格式。
    用户把它选为目标时，转换器会先套 X 样式，再把这套直接格式补回段落。
    """
    try:
        doc = Document(template_file)
        styles = []
        for style in doc.styles:
            # 某些 WPS 模板存在缺少名称的样式，不能加入下拉框或排序列表。
            if style.type == WD_STYLE_TYPE.PARAGRAPH and style.name:
                styles.append(style.name)
        plain_styles = sorted(styles)
        plain_set = set(styles)

        # 模板段落上的「样式 + 直接格式」快照（与转换引擎共用同一份提取逻辑）
        try:
            from doc_converter import extract_template_format_snapshots
            snapshots = extract_template_format_snapshots(doc)
        except Exception as e:
            logger.warning(f"提取模板格式快照失败: {e}")
            snapshots = {}

        # 与真实样式同名的不重复添加，避免下拉框里出现两个一模一样的选项
        snapshot_names = sorted(n for n in snapshots if n not in plain_set)
        return plain_styles + snapshot_names
    except:
        return ["Normal"]  # 默认返回Normal样式


def analyze_source_styles(source_files, user_id):
    """
    分析源文档样式（不显示进度条，避免布局问题）
    :param source_files: 上传的文件对象列表
    :param user_id: 用户ID
    :return: {filename: [styles]} 字典，每个文件对应其样式列表
    """
    import os
    
    file_styles_map = {}  # {filename: [styles]}
    total_files = len(source_files)
    
    for idx, source_file in enumerate(source_files, 1):
        # 保存临时文件
        from config import TEMP_DIR
        temp_source = str(TEMP_DIR / f"temp_source_{user_id}_{source_file.name}")
        try:
            with open(temp_source, 'wb') as f:
                f.write(source_file.getbuffer())
            
            # 读取样式
            doc = Document(temp_source)
            styles = set()
            
            for para in doc.paragraphs:
                if para.style and para.style.name:
                    styles.add(para.style.name)
            
            # 保存该文件的样式
            file_styles_map[source_file.name] = sorted(list(styles))
            
        except Exception as e:
            st.error(f"❌ 分析文件 {source_file.name} 失败: {e}")
            continue
    
    return file_styles_map


def count_pages(docx_file):
    """估算文档页数（基于段落数）"""
    try:
        doc = Document(docx_file)
        # 粗略估算：每50个段落约1页
        paragraphs = len(doc.paragraphs)
        estimated_pages = max(1, paragraphs // 50)
        return estimated_pages
    except:
        return 0  # 无法计算时返回0


def detect_missing_heading_styles(source_files, user_id):
    """检测源文档是否缺少标题样式（供转换页引导提示 P1-1）。

    Args:
        source_files: 已上传的源文件对象列表。
        user_id: 当前用户ID（用于生成临时文件路径）。

    Returns:
        Dict[str, bool]：{文件名: 是否缺少标题样式}。无法分析的文件标记为 False。
    """
    from title_preprocessor import TitlePreprocessor

    result = {}
    for sf in source_files:
        from config import TEMP_DIR
        temp_source = str(TEMP_DIR / f"temp_source_{user_id}_{sf.name}")
        try:
            with open(temp_source, 'wb') as f:
                f.write(sf.getbuffer())
            result[sf.name] = not TitlePreprocessor.has_heading_styles(temp_source)
        except Exception as e:
            logger.warning(f"检测标题样式失败 {sf.name}: {e}")
            result[sf.name] = False
    return result


def count_template_styles(template_file):
    """统计模板文档的总样式数（供转换页引导提示 P1-2）。

    Args:
        template_file: 模板文档本地路径。

    Returns:
        int: 样式总数；分析失败返回 0。
    """
    from style_cleaner import StyleCleaner

    try:
        analysis = StyleCleaner.analyze_styles(template_file)
        return analysis.get("total", 0)
    except Exception as e:
        logger.warning(f"统计模板样式失败: {e}")
        return 0
