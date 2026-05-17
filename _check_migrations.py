import re, os

versions_dir = r'E:\LingMa\WSprj\backend\alembic\versions'
files = sorted(os.listdir(versions_dir))
print("=== 迁移文件链 ===")
for f in files:
    if not f.endswith('.py'):
        continue
    with open(os.path.join(versions_dir, f), 'r', encoding='utf-8') as fh:
        content = fh.read()
    rev = re.search(r'revision = ["\']([^"\']+)["\']', content)
    down_rev = re.search(r'down_revision = ["\']([^"\']+)["\']', content)
    has_conv = 'conversion_history' in content
    print(f'{f}')
    print(f'  revision: {rev.group(1) if rev else "N/A"}')
    print(f'  down_revision: {down_rev.group(1) if down_rev else "N/A"}')
    print(f'  has_conversion_history: {has_conv}')
    print()

# 检查 models.py 和数据库的实际差异
print("=== models.py 中的 User 字段 ===")
with open(r'E:\LingMa\WSprj\backend\app\models.py', 'r', encoding='utf-8') as f:
    content = f.read()
user_start = content.find('class User(')
user_end = content.find('class ConversionTask(')
user_block = content[user_start:user_end]
cols = re.findall(r'\n\s+(\w+)\s*=\s*Column\(', user_block)
print('User模型字段:', cols)

# 检查这些字段在迁移脚本中的出现情况
print("\n=== 迁移脚本覆盖检查 ===")
covered = set()
for f in files:
    if not f.endswith('.py'):
        continue
    with open(os.path.join(versions_dir, f), 'r', encoding='utf-8') as fh:
        content = fh.read()
    for col in cols:
        if col in content:
            covered.add(col)
missing = [c for c in cols if c not in covered]
if missing:
    print(f'缺少迁移覆盖的字段: {missing}')
else:
    print('所有字段都有迁移覆盖')
