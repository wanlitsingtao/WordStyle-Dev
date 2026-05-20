# -*- coding: utf-8 -*-
"""检查WSprj/app.py中是否包含文档转换按钮"""
import re
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'E:\LingMa\WSprj\app.py', 'rb') as f:
    content = f.read()
text = content.decode('utf-8', errors='replace')
lines = text.split('\n')

# 检查970-1050之间的所有内容
print("=== Content L970-L1050 ===")
for i in range(969, min(1050, len(lines))):
    line = lines[i]
    stripped = line.strip()
    if stripped and not stripped.startswith('#') and not stripped.startswith('/*'):
        # Show significant lines
        out = line.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        print(f'L{i+1}: {out}')

# 特别检查所有st.xxx调用
print("\n=== All st.* calls in the file ===")
for i, line in enumerate(lines):
    if 'st.' in line:
        out = line.strip().encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        print(f'L{i+1}: {out}')
