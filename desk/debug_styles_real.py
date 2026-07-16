# -*- coding: utf-8 -*-
"""从真实模板加载文档，直接检查三个模板的样式"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from docx import Document
from docx.oxml.ns import qn
from copy import deepcopy

TEMPLATE = r"E:\LingMa\WordStyle\WordStyle-Dev\test\jsmb.docx"

doc = Document(TEMPLATE)

# 三个用户选择的样式（从 jsmb.docx 中存在的样式）
# 先列出模板中的所有段落样式
para_styles = [s.name for s in doc.styles if s.type is not None and str(s.type) == 'Paragraph (1)']
print("模板中的段落样式（前30个）:")
for s in para_styles[:30]:
    print(f"  - {s}")

# 随便选三个存在的样式来测试
available = [s for s in para_styles if 'Normal' in s or '正文' in s or '缩进' in s or '应答' in s or 'BN' in s]
print(f"\n相关的样式: {available[:10]}")

# 使用实际能用的样式
answer_style = available[0] if available else "Normal"
source_style = available[1] if len(available) > 1 else "Normal"
copy_style = available[2] if len(available) > 2 else "Normal"

print(f"\n测试用的样式:")
print(f"  answer_style (应答句样式) = {answer_style}")
print(f"  source_style (原文格式) = {source_style}")
print(f"  copy_style (应答原文格式) = {copy_style}")
