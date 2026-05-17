# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
os.chdir(r'E:\LingMa\WSprj')
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# 找 conversion_history.append
for i, line in enumerate(lines):
    if 'conversion_history' in line and 'append' in line:
        print(f"✅ Line {i+1}: {line.strip()[:150]}")
        print(f"   上下文:")
        for j in range(max(0,i-2), min(len(lines), i+5)):
            print(f"    {j+1}: {lines[j].strip()[:120]}")
        break
else:
    print("❌ 未找到 conversion_history.append")
    
# 总数统计
total = content.count('conversion_history')
print(f"\nconversion_history 出现总次数: {total}")

# 检查 feedback.py 路径
print("\n--- feedback.py 路径 ---")
with open(r'E:\LingMa\WSprj\backend\app\api\feedback.py', 'r', encoding='utf-8') as f:
    for line in f.readlines()[:30]:
        if 'FEEDBACK_FILE' in line or 'Path' in line:
            print(f"  {line.strip()}")
