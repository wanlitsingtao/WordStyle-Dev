import urllib.request, json

device_fp = 'test_convert_test_001'

req = urllib.request.Request(
    'https://wstest-backend.onrender.com/api/admin/users/by-device',
    data=json.dumps({'device_fingerprint': device_fp}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
r = urllib.request.urlopen(req, timeout=30)
user = json.loads(r.read().decode())
user_id = user['user_id']
print(f'User ID: {user_id}')
print(f'Initial conversion_history: {user.get("conversion_history", "MISSING")}')

# 保存带转换历史的用户数据
user_data = {
    'paragraphs_remaining': 9500,
    'total_paragraphs_used': 500,
    'total_converted': 1,
    'conversion_history': [{
        'time': '2026-05-17 12:00:00',
        'files': 1,
        'success': 1,
        'failed': 0,
        'paragraphs_charged': 500,
        'mode': 'foreground'
    }]
}

req2 = urllib.request.Request(
    f'https://wstest-backend.onrender.com/api/admin/users/{user_id}',
    data=json.dumps(user_data).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
r2 = urllib.request.urlopen(req2, timeout=30)
result = json.loads(r2.read().decode())
print(f'Save result: {result}')

# 重新获取验证
req3 = urllib.request.Request(
    'https://wstest-backend.onrender.com/api/admin/users/by-device',
    data=json.dumps({'device_fingerprint': device_fp}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
r3 = urllib.request.urlopen(req3, timeout=30)
user3 = json.loads(r3.read().decode())
print(f'After save conversion_history: {user3.get("conversion_history", "MISSING")}')
