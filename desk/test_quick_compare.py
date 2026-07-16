# -*- coding: utf-8 -*-
"""快速对比分析两个转换后的文档"""
from docx import Document
from docx.oxml.ns import qn
import os, sys

base = r'E:\LingMa\WordStyle\WordStyle-Dev\test'

# 找最新文件
files = [f for f in os.listdir(base) if f.startswith('1517_converted') and f.endswith('.docx')]
files.sort()
print('找到的转换文件:')
for f in files:
    print(f'  {f}')

# 选最新的两个
if len(files) >= 2:
    f_no_chk = os.path.join(base, files[0])  # 较早的=不勾选
    f_chk = os.path.join(base, files[-1])     # 最新的=勾选
else:
    print('文件不足')
    sys.exit(1)

print(f'\n比对: 不勾选={files[0]}, 勾选={files[-1]}')

# 只检查重点段落，不遍历全部
keywords = ['15号线乘客信息系统', '17号线一期', '图纸（如有）']

for label, kw in [('15号线', '15号线'), ('17号线', '17号线'), ('第六章', '图纸')]:
    print(f'\n=== {label} ===')
    
    for fpath, tag in [(f_no_chk, '不勾选'), (f_chk, '勾选')]:
        doc = Document(fpath)
        found = False
        for i, p in enumerate(doc.paragraphs):
            if kw in p.text:
                pPr = p._element.find(qn('w:pPr'))
                olvl = pPr.find(qn('w:outlineLvl')) if pPr is not None else None
                numPr = pPr.find(qn('w:numPr')) if pPr is not None else None
                olvl_val = olvl.get(qn('w:val')) if olvl is not None else None
                print(f'  {tag} §{i}: {p.text[:80]!r}  style={p.style.name} olvl={olvl_val} numPr={numPr is not None}')
                found = True
                break
        if not found:
            print(f'  {tag}: 未找到包含"{kw}"的段落')
        # doc.close() not needed - Document doesn't need explicit close
