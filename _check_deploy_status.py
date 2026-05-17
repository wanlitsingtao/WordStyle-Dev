import requests

print("=== Render 上运行的版本 ===")
r = requests.get('https://wstest-backend.onrender.com/', timeout=30)
if r.status_code == 200:
    data = r.json()
    print(f"  Message: {data.get('message')}")
    print(f"  Version: {data.get('version')}")

print()
print("=== API 路由列表 ===")
r = requests.get('https://wstest-backend.onrender.com/openapi.json', timeout=30)
if r.status_code == 200:
    data = r.json()
    print(f"  版本: {data.get('info', {}).get('version')}")
    paths = list(data.get('paths', {}).keys())
    print(f"  路由数: {len(paths)}")
    for p in sorted(paths):
        methods = list(data['paths'][p].keys())
        print(f"    {p}: {methods}")

print()
print("=== 直接测试 users/by-device ===")
r = requests.post('https://wstest-backend.onrender.com/api/admin/users/by-device',
    json={'device_fingerprint': 'status_check'}, timeout=30)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    print("  ✅ 端点工作正常")
elif r.status_code == 500:
    print(f"  ❌ 500错误: {r.text[:200]}")
else:
    print(f"  Other: {r.text[:200]}")

print()
print("=== 结论 ===")
print("  如果 Version 不是最新的，或 users/by-device 仍返回 500")
print("  需要在 Render Dashboard 手动触发部署")
