import os, re

print("========== 检查 1: 迁移链修复 ==========")

versions_dir = r'E:\LingMa\WSprj\backend\alembic\versions'
files = sorted(os.listdir(versions_dir))

rev_map = {}
for f in files:
    if not f.endswith('.py'):
        continue
    path = os.path.join(versions_dir, f)
    with open(path, 'r', encoding='utf-8') as fh:
        content = fh.read()
    rev = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", content)
    down = re.search(r"down_revision\s*=\s*['\"]([^'\"]+)['\"]", content)
    rev_info = {'revision': rev.group(1) if rev else None, 'down_revision': down.group(1) if down else None}
    rev_map[f] = rev_info
    print(f"  {f}")
    print(f"    rev={rev_info['revision']}, down={rev_info['down_revision']}")

print("\n--- 链断裂检查 ---")
rev_lookup = {info['revision']: f for f, info in rev_map.items() if info['revision']}
broken = False
for f, info in sorted(rev_map.items()):
    if info['down_revision']:
        if info['down_revision'] not in rev_lookup:
            print(f"  [断裂] {f}: down_revision='{info['down_revision']}' 找不到父迁移!")
            broken = True
        else:
            print(f"  [OK] {f} -> {info['down_revision']}")
    else:
        print(f"  [OK] {f} (根迁移)")

if broken:
    print("\n  *** 迁移链仍存在断裂 ***")
else:
    print("\n  *** 迁移链完整! ***")

print("\n========== 检查 2: conversion_history 迁移是否存在 ==========")
conv_files = [f for f, info in rev_map.items() if os.path.exists(os.path.join(versions_dir, f))]
found_conv = False
for f in conv_files:
    path = os.path.join(versions_dir, f)
    with open(path, 'r', encoding='utf-8') as fh:
        content = fh.read()
    if 'conversion_history' in content:
        print(f"  [OK] {f} 包含 conversion_history")
        found_conv = True
if found_conv:
    print("  *** conversion_history 迁移已存在 ***")
else:
    print("  *** 未找到 conversion_history 迁移! ***")

print("\n========== 检查 3: models.py 字段一致性 ==========")
with open(r'E:\LingMa\WSprj\backend\app\models.py', 'r', encoding='utf-8') as f:
    content = f.read()
user_start = content.find('class User(')
user_end = content.find('class ConversionTask(')
user_block = content[user_start:user_end]
cols = re.findall(r'\n\s+(\w+)\s*=\s*Column\(', user_block)
print(f"  User模型字段: {cols}")
if 'conversion_history' in cols:
    print("  [OK] models.py 包含 conversion_history")
else:
    print("  [缺少] models.py 缺少 conversion_history!")

print("\n========== 检查 4: admin.py API端点 ==========")
with open(r'E:\LingMa\WSprj\backend\app\api\admin.py', 'r', encoding='utf-8') as f:
    content = f.read()
# 检查 users/by-device 端点
if 'conversion_history' in content:
    count = content.count('conversion_history')
    print(f"  [OK] admin.py 中 conversion_history 出现 {count} 次")
else:
    print("  [缺少] admin.py 中缺少 conversion_history!")

print("\n========== 检查 5: WSprj vs WordStyle 一致性 ==========")
import hashlib
# WordStyle 的 api 目录是文件不是目录，所以 admin.py 路径不同
wsprj_files = [
    (r'E:\LingMa\WSprj\backend\app\models.py', r'E:\LingMa\WordStyle\backend\app\models.py'),
    (r'E:\LingMa\WSprj\backend\app\main.py', r'E:\LingMa\WordStyle\backend\app\main.py'),
]
# WSprj 的 admin.py 在 backend/app/api/admin.py
# WordStyle 的 admin.py 可能在 backend/app/api 下
wss_api = r'E:\LingMa\WordStyle\backend\app\api'
if os.path.isdir(wss_api):
    print(f"  WordStyle api 是目录")
    wsprj_files.append((r'E:\LingMa\WSprj\backend\app\api\admin.py', os.path.join(wss_api, 'admin.py')))
else:
    print(f"  WordStyle api 是文件: {wss_api}")
    # 检查是否是一个Python文件
    with open(wss_api, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
    print(f"  首行: {first_line}")

all_match = True
for wsprj_path, wss_path in wsprj_files:
    if not os.path.exists(wss_path):
        print(f"  [N/A] WordStyle 无 {os.path.basename(wss_path)} (路径: {wss_path})")
        continue
    with open(wsprj_path, 'rb') as f:
        h1 = hashlib.md5(f.read()).hexdigest()
    with open(wss_path, 'rb') as f:
        h2 = hashlib.md5(f.read()).hexdigest()
    match = h1 == h2
    status = "OK" if match else "DIFF"
    if not match:
        all_match = False
    name = os.path.basename(wsprj_path)
    print(f"  [{status}] {name}: WSprj={h1}, WordStyle={h2}")

if all_match:
    print("  *** 两个目录一致 (可检查部分) ***")
else:
    print("  *** 存在差异文件! ***")

print("\n========== 最终结论 ==========")
if not broken and found_conv and 'conversion_history' in cols:
    print("  *** 本地代码已修复! 可直接同步到发布目录 ***")
    print("  需要操作: 1) 同步到WordStyle  2) 部署到Render  3) 验证API")
else:
    print("  *** 本地代码仍存在问题 ***")
