#!/usr/bin/env python
import sys
root = r'E:\LingMa\WSprj'
app_path = root + r'\app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== 页面结构分析 ===")
for i, line in enumerate(lines):
    s = line.strip()
    if (s.startswith('st.subheader(') or 
        s.startswith("st.markdown('---") or 
        s.startswith('st.markdown("---') or
        '开始转换' in s or
        '转换执行' in s or
        s.startswith('st.button(')):
        print(f'  L{i+1}: {s[:120]}')

print()
print("=== 转换配置区完整内容 (L940-L990) ===")
for i in range(939, min(len(lines), 990)):
    s = lines[i].rstrip()
    if s.strip():
        print(f'  L{i+1}: {s[:150]}')
