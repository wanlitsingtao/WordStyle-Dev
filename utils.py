# -*- coding: utf-8 -*-
"""
通用工具函数模块
提供HTML转义、文件名清理等通用功能
"""
import html
import re
import os
from datetime import datetime


def sanitize_html(text):
    """
    HTML转义，防止XSS攻击
    :param text: 原始文本
    :return: 转义后的安全文本
    """
    if not isinstance(text, str):
        return str(text)
    return html.escape(text, quote=True)


def sanitize_filename(filename):
    """
    清理文件名，防止路径遍历攻击
    :param filename: 原始文件名
    :return: 安全的文件名
    """
    # 获取基本文件名（去除路径）
    safe_name = os.path.basename(filename)
    
    # 移除危险字符
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', safe_name)
    
    # 限制长度
    from config import FILENAME_MAX_LENGTH
    if len(safe_name) > FILENAME_MAX_LENGTH:
        name, ext = os.path.splitext(safe_name)
        safe_name = name[:FILENAME_MAX_LENGTH - 10] + ext
    
    # 确保不为空
    if not safe_name or safe_name.startswith('.'):
        safe_name = f"file_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    return safe_name


def validate_docx_file(file_content):
    """
    验证文件是否为真正的DOCX文件
    :param file_content: 文件字节内容
    :return: (是否有效, 错误消息)
    """
    try:
        # DOCX文件实际上是ZIP格式，检查ZIP文件头
        if len(file_content) < 4:
            return False, "文件太小，不是有效的DOCX文件"
        
        # ZIP文件头签名: PK\x03\x04
        if file_content[:4] != b'PK\x03\x04':
            return False, "文件格式不正确，不是有效的DOCX文件"
        
        return True, None
    except Exception as e:
        import logging
        logger = logging.getLogger('WordStyle')
        logger.error(f"文件验证失败: {e}")
        return False, f"文件验证出错: {str(e)}"


def calculate_cost(paragraphs):
    """
    计算转换费用
    :param paragraphs: 段落数
    :return: 费用（元）
    """
    from config import PARAGRAPH_PRICE
    return paragraphs * PARAGRAPH_PRICE


def format_number(num):
    """
    格式化数字，添加千位分隔符
    :param num: 数字
    :return: 格式化后的字符串
    """
    return f"{num:,}"


# 测试代码
if __name__ == "__main__":
    print("测试工具函数...")
    
    # 测试HTML转义
    test_html = "<script>alert('XSS')</script>"
    safe_html = sanitize_html(test_html)
    print(f"[OK] HTML转义: {test_html} -> {safe_html}")
    
    # 测试文件名清理
    test_filename = "../../../etc/passwd.docx"
    safe_filename = sanitize_filename(test_filename)
    print(f"[OK] 文件名清理: {test_filename} -> {safe_filename}")
    
    # 测试费用计算
    cost = calculate_cost(1000)
    print(f"[OK] 费用计算: 1000段落 = ¥{cost:.2f}")
    
    # 测试数字格式化
    formatted = format_number(1234567)
    print(f"[OK] 数字格式化: {formatted}")
    
    print("\n[OK] 所有测试通过！")
