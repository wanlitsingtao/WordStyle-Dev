# -*- coding: utf-8 -*-
"""调试脚本：检查 copy_chapter 模式下三个段落的实际样式"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from doc_converter import DocumentConverter
from docx import Document
from docx.oxml.ns import qn
import shutil

# 配置
SOURCE = r"E:\LingMa\WordStyle\WordStyle-Dev\test\1517.docx"
TEMPLATE = r"E:\LingMa\WordStyle\WordStyle-Dev\test\jsmb.docx"
OUTPUT = r"E:\LingMa\WordStyle\WordStyle-Dev\test\debug_styles_output.docx"

# 模拟用户选择的样式
USER_SOURCE_STYLE = "BN_原文缩进"    # 原文格式
USER_ANSWER_STYLE = "BN_应答句"      # 应答句样式
USER_COPY_STYLE = "BN_应答缩进"      # 应答原文格式

print(f"用户设置的样式:")
print(f"  原文格式: {USER_SOURCE_STYLE}")
print(f"  应答句样式: {USER_ANSWER_STYLE}")
print(f"  应答原文格式: {USER_COPY_STYLE}")
print()

# 做一个简化测试：直接调用 insert_response_after_headings
# 先做一个样式转换
conv = DocumentConverter()

# 先做样式转换到临时文件
temp1 = OUTPUT.replace('.docx', '_temp1.docx')
success, actual, msg = conv.convert_styles(SOURCE, TEMPLATE, temp1)
print(f"样式转换: {success} - {msg}")

# 再插入应答句（copy_chapter模式）
temp2 = OUTPUT.replace('.docx', '_temp2.docx')
success, actual, msg = conv.insert_response_after_headings(
    temp1, temp2,
    answer_text="应答：本投标人理解并满足要求。",
    answer_style=USER_ANSWER_STYLE,
    answer_mode='copy_chapter',
    answer_source_style=USER_SOURCE_STYLE,
    answer_copy_style=USER_COPY_STYLE
)
print(f"应答插入: {success} - {msg}")
print()

# 分析输出文档中应答相关段落的样式
doc = Document(temp2)
body = doc.element.body
children = list(body)

print("=" * 70)
print("分析输出文档中所有段落的样式（仅显示与应答相关的段落）")
print("=" * 70)

# 遍历段落，查找包含"应答"文本的段落
for i, child in enumerate(children):
    if not hasattr(child, 'tag') or child.tag != qn('w:p'):
        continue
    
    # 获取段落文本
    texts = [r.text or '' for r in child.findall('.//' + qn('w:r'))]
    text = ''.join(texts).strip()
    
    if '应答' in text or not text:
        # 获取段落样式
        pPr = child.find(qn('w:pPr'))
        style_name = "无样式"
        if pPr is not None:
            pStyle = pPr.find(qn('w:pStyle'))
            if pStyle is not None:
                style_name = pStyle.get(qn('w:val'))
        
        if '应答' in text:
            print(f"段落 {i}: 样式='{style_name}', 文本='{text[:50]}'")
        elif not text:
            print(f"段落 {i}: 样式='{style_name}', 文本=[空段落]")

# 清理临时文件
for f in [temp1, OUTPUT]:
    if os.path.exists(f):
        os.remove(f)
print()
print("测试完成")
