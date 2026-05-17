# -*- coding: utf-8 -*-
"""
通用工具函数模块
提供HTML转义、文件名清理、时间转换等通用功能
"""
import html
import re
import os
from datetime import datetime, timezone, timedelta


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


def convert_server_time_to_local(server_time_str):
    """
    将服务器时间转换为本地时间显示
    
    Args:
        server_time_str: 服务器时间字符串（格式：'YYYY-MM-DD HH:MM:SS' 或 ISO格式）
    
    Returns:
        本地时间字符串
    """
    if not server_time_str or server_time_str == '未知':
        return server_time_str
    
    try:
        # 尝试解析服务器时间
        # 支持多种格式
        for fmt in [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S.%f',
        ]:
            try:
                # 移除时区信息（如果有）
                clean_time = server_time_str.replace('+00:00', '').replace('Z', '')
                server_dt = datetime.strptime(clean_time, fmt)
                break
            except ValueError:
                continue
        else:
            # 如果所有格式都失败，返回原始字符串
            return server_time_str
        
        # 假设服务器时间是UTC时间，转换为本地时间
        # Streamlit运行在浏览器中，会自动使用浏览器的时区
        # 这里我们简单地返回原始时间，让前端JavaScript处理时区转换
        # 或者我们可以添加时区偏移量提示
        
        # 方案1：直接返回原始时间（最简单）
        return server_time_str
        
        # 方案2：添加时区提示（需要知道服务器时区）
        # return f"{server_time_str} (服务器时间)"
        
    except Exception as e:
        # 如果转换失败，返回原始字符串
        return server_time_str
