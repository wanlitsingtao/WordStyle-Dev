# -*- coding: utf-8 -*-
"""最终调试：用真实模板和源文档，检查 copy_chapter 三个模板的样式"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from doc_converter import DocumentConverter
from docx import Document
from docx.oxml.ns import qn
import shutil

TEMPLATE = r"E:\LingMa\WordStyle\WordStyle-Dev\test\jsmb.docx"
SOURCE = r"E:\LingMa\WordStyle\WordStyle-Dev\test\1517.docx"

conv = DocumentConverter()

# 第1步：做样式转换，生成临时文件
tmp1 = r"E:\LingMa\WordStyle\WordStyle-Dev\test\_debug_tmp1.docx"
success, actual, msg = conv.convert_styles(SOURCE, TEMPLATE, tmp1)
print(f"【1】样式转换: {success}")

# 第2步：直接调用 insert_response_after_headings
# 使用三个不同的、容易区分的样式
tmp2 = r"E:\LingMa\WordStyle\WordStyle-Dev\test\_debug_tmp2.docx"

# 为了让结果可区分，用三个明显不同的样式
ans_style = "Heading 1"       # 应答句样式（大标题样式，容易识别）
src_style = "Body Text"       # 原文格式
cpy_style = "List Paragraph"  # 应答原文格式

success, actual, msg = conv.insert_response_after_headings(
    tmp1, tmp2,
    answer_text="应答：测试应答句",
    answer_style=ans_style,
    answer_mode='copy_chapter',
    answer_source_style=src_style,
    answer_copy_style=cpy_style
)
print(f"【2】应答插入: {success}")

# 第3步：分析结果
doc = Document(tmp2)
body = doc.element.body
children = list(body)

print("\n【3】查找所有应答相关段落:")
print(f"共 {len(children)} 个元素")

for i, child in enumerate(children):
    if not hasattr(child, 'tag') or child.tag != qn('w:p'):
        continue
    
    # 获取文本
    texts = [r.text or '' for r in child.findall('.//' + qn('w:r'))]
    text = ''.join(texts).strip()
    
    # 获取样式名
    pPr = child.find(qn('w:pPr'))
    style_name = "(无)"
    if pPr is not None:
        pStyle = pPr.find(qn('w:pStyle'))
        if pStyle is not None:
            style_name = pStyle.get(qn('w:val'))
    
    # 只显示有应答文本的段落 或 明显的空段落
    if '应答' in text:
        print(f"  段落[{i}] style='{style_name}' text='{text[:60]}'")

# 清理
for f in [tmp1, tmp2]:
    if os.path.exists(f):
        os.remove(f)
print("\n【4】测试完成")
