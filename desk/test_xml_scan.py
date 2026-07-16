# -*- coding: utf-8 -*-
"""极速检查 - 使用lxml直接解析"""
from lxml import etree
import os, sys
from zipfile import ZipFile
from io import BytesIO

base = r'E:\LingMa\WordStyle\WordStyle-Dev\test'
files = ['1517_converted.docx', '1517_converted_154902.docx']
ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

for fname in files:
    fpath = os.path.join(base, fname)
    if not os.path.exists(fpath):
        continue
    
    tag = '不勾选' if '154902' not in fname else '勾选'
    print(f'\n=== {tag}: {fname} ===')
    
    with ZipFile(fpath) as z:
        doc_xml = z.read('word/document.xml')
    
    root = etree.fromstring(doc_xml)
    body = root.find(f'{{{ns}}}body')
    all_paras = body.findall(f'.//{{{ns}}}p')
    print(f'总段落数(XML): {len(all_paras)}')
    
    outline_count = 0
    for i, para_el in enumerate(all_paras):
        pPr = para_el.find(f'{{{ns}}}pPr')
        if pPr is not None:
            olvl = pPr.find(f'{{{ns}}}outlineLvl')
            if olvl is not None:
                olvl_val = olvl.get(f'{{{ns}}}val')
                # 获取文本
                texts = para_el.findall(f'.//{{{ns}}}t')
                text = ''.join(t.text or '' for t in texts)
                
                if outline_count < 10:
                    print(f'  大纲 §{i} Lv{olvl_val}: {text[:60]!r}')
                outline_count += 1
    
    print(f'大纲标题总数: {outline_count}')
    
    # 找 15号线 17号线 第六章
    print(f'\n  搜索特定标题:')
    for label, kw in [('15号线','15号线'), ('17号线','17号线'), ('图纸','图纸')]:
        found = False
        for i, para_el in enumerate(all_paras):
            texts = para_el.findall(f'.//{{{ns}}}t')
            text = ''.join(t.text or '' for t in texts)
            if kw in text:
                pPr = para_el.find(f'{{{ns}}}pPr')
                olvl = pPr.find(f'{{{ns}}}outlineLvl') if pPr is not None else None
                numPr = pPr.find(f'{{{ns}}}numPr') if pPr is not None else None
                olvl_val = olvl.get(f'{{{ns}}}val') if olvl is not None else None
                print(f'    §{i}: {text[:80]!r}  olvl={olvl_val} numPr={numPr is not None}')
                found = True
                break
        if not found:
            print(f'    未找到"{kw}"')
