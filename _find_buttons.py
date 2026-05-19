#!/usr/bin/env python
import sys
app_path = r'E:\LingMa\WSprj\app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== 模板分析完成后的转换执行按钮/区域 ===")
# 搜索所有st.button
for i, line in enumerate(lines):
    s = line.strip()
    if s.startswith('st.button(') or s.startswith('if st.button('):
        print(f'  L{i+1}: {s[:150]}')

print()
print("=== L690-L730 (上传源文档区域底部) ===")
for i in range(689, min(len(lines), 732)):
    s = lines[i].rstrip()
    if s.strip():
        print(f'  L{i+1}: {s[:150]}')

print()
print("=== L1100-1116 (页面末尾) ===")
for i in range(1099, len(lines)):
    s = lines[i].rstrip()
    if s.strip():
        print(f'  L{i+1}: {s[:150]}')
