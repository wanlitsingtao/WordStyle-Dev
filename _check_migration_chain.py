import os, re

versions_dir = r'E:\LingMa\WSprj\backend\alembic\versions'
files = sorted(os.listdir(versions_dir))

# 解析每个迁移的 revision 和 down_revision
migrations = {}
for f in files:
    if not f.endswith('.py'):
        continue
    path = os.path.join(versions_dir, f)
    with open(path, 'r', encoding='utf-8') as fh:
        content = fh.read()
    rev = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", content)
    down = re.search(r"down_revision\s*=\s*['\"]([^'\"]+)['\"]", content)
    has_conv = 'conversion_history' in content
    migrations[f] = {
        'revision': rev.group(1) if rev else 'N/A',
        'down_revision': down.group(1) if down else None,
        'has_conversion_history': has_conv
    }

print("=== 迁移链检查 ===")
for f, info in sorted(migrations.items()):
    print(f"  {f}")
    print(f"    rev={info['revision']}, down={info['down_revision']}, conv={info['has_conversion_history']}")

# 验证链完整性
print("\n=== 链完整性验证 ===")
rev_map = {info['revision']: f for f, info in migrations.items()}
for f, info in sorted(migrations.items()):
    if info['down_revision']:
        if info['down_revision'] in rev_map:
            print(f"  {f} -> down_revision={info['down_revision']} OK")
        else:
            print(f"  {f} -> down_revision={info['down_revision']} XXXXXX 未找到父迁移!")
    else:
        print(f"  {f} -> 根迁移 (no down_revision)")

print("\n=== 结论 ===")
# 检查conversion_history迁移是否在链尾
conv_files = [f for f, info in migrations.items() if info['has_conversion_history']]
if conv_files:
    print(f"conversion_history迁移文件: {conv_files}")
    for f in conv_files:
        info = migrations[f]
        # 检查有没有其他迁移以它为 down_revision
        is_last = all(
            i['down_revision'] != info['revision'] 
            for fi, i in migrations.items() if fi != f
        )
        print(f"  是否为链尾: {is_last}")
else:
    print("!!! 未找到 conversion_history 迁移文件 !!!")
