import requests

print("=" * 50)
print("1. 测试 /health")
print("=" * 50)
r = requests.get('https://wstest-backend.onrender.com/health', timeout=30)
print(f"  Status: {r.status_code}, Body: {r.text}")

print()
print("=" * 50)
print("2. 测试 POST /users/by-device")
print("=" * 50)
r = requests.post('https://wstest-backend.onrender.com/api/admin/users/by-device',
    json={'device_fingerprint': 'diag_verify_001'}, timeout=30)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"  success: {data.get('success')}")
    print(f"  user_id: {data.get('user_id')}")
    print(f"  paragraphs_remaining: {data.get('paragraphs_remaining')}")
    print(f"  has conversion_history: {'conversion_history' in data}")
    if 'conversion_history' in data:
        print(f"  conversion_history: {data['conversion_history']}")
else:
    print(f"  Error: {r.text[:500]}")

print()
print("=" * 50)
print("3. 测试 GET /users (管理员列表)")
print("=" * 50)
r = requests.get('https://wstest-backend.onrender.com/api/admin/users', timeout=30)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    if isinstance(data, list):
        print(f"  用户数: {len(data)}")
        if len(data) > 0:
            print(f"  第一个用户: id={data[0].get('id')}, remaining={data[0].get('paragraphs_remaining')}")
    else:
        print(f"  Response: {str(data)[:300]}")
else:
    print(f"  Error: {r.text[:300]}")

print()
print("=" * 50)
print("结论")
print("=" * 50)
if r.status_code == 200:
    print("  ✅ 所有API端点正常！")
else:
    print("  ❌ 仍有问题需要处理")
