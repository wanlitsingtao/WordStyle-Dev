import urllib.request, json, time

print("="*60)
print("  WordStyle 部署状态检查")
print("="*60)

# 测试1：健康检查
print("\n[1/4] 健康检查...")
try:
    req = urllib.request.Request('https://wstest-backend.onrender.com/health')
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    print(f"  状态: {resp.status}")
    print(f"  响应: {data}")
except Exception as e:
    print(f"  失败: {e}")

# 测试2：用户端点
print("\n[2/4] 测试 /users/by-device...")
try:
    body = json.dumps({"device_fingerprint": "test_check_fix_001_v2"}).encode()
    req = urllib.request.Request(
        'https://wstest-backend.onrender.com/api/admin/users/by-device',
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    print(f"  状态: {resp.status}")
    print(f"  success: {data.get('success')}")
    print(f"  user_id: {data.get('user_id')}")
    print(f"  conversion_history 字段: {'conversion_history' in data}")
    print(f"  total_paragraphs_used 字段: {'total_paragraphs_used' in data}")
    if 'conversion_history' in data:
        print(f"  conversion_history 值: {data['conversion_history']}")
except urllib.error.HTTPError as e:
    print(f"  HTTP错误: {e.code}")
    detail = e.read().decode()
    print(f"  详情: {detail[:300]}")
except Exception as e:
    print(f"  失败: {e}")

# 测试3：用户列表
print("\n[3/4] 测试 /users...")
try:
    req = urllib.request.Request('https://wstest-backend.onrender.com/api/admin/users')
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    users = data.get('users', data.get('data', []))
    print(f"  状态: {resp.status}")
    if isinstance(users, list):
        print(f"  用户数: {len(users)}")
        if users:
            print(f"  首个用户有 conversion_history: {'conversion_history' in users[0]}")
    else:
        print(f"  响应: {str(data)[:200]}")
except Exception as e:
    print(f"  失败: {e}")

# 测试4：API 版本
print("\n[4/4] 检查 API 版本...")
try:
    req = urllib.request.Request('https://wstest-backend.onrender.com/')
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    print(f"  版本: {data.get('version', 'unknown')}")
except Exception as e:
    print(f"  失败: {e}")

print("\n" + "="*60)
print("  检查完成")
print("="*60)
