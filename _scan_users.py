import os, sys, re

# 设置输出编码为utf-8
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\LingMa\WSprj'
results = []

for dirpath, dirnames, filenames in os.walk(root):
    skip = ['.venv', '__pycache__', 'node_modules', '.git']
    dirnames[:] = [d for d in dirnames if d not in skip]
    for f in filenames:
        if not f.endswith('.py'):
            continue
        path = os.path.join(dirpath, f)
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                lines = fh.readlines()
        except:
            continue
        for lineno, line in enumerate(lines, 1):
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            low = s.lower()
            if any(kw in low for kw in [
                'users/by-device', 'users/by_device',
                'get_or_create_user', 'register_or_login',
                'new_user', '_create_user', '_register_user',
                'add_user', 'insert into users'
            ]):
                # 清理emoji和特殊字符
                clean = s.encode('ascii', 'ignore').decode('ascii').strip()
                if clean:
                    results.append((os.path.relpath(path, root), lineno, clean[:150]))

# 去重打印
seen = set()
for path, lineno, s in results:
    key = f"{path}:{lineno}"
    if key not in seen:
        seen.add(key)
        print(f"{path}:{lineno}: {s}")
