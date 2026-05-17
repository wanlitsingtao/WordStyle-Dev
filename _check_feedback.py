import urllib.request, json

# 测试提交新反馈
print("=== 提交新反馈 ===")
url = 'https://wstest-backend.onrender.com/api/feedback/submit'
body = json.dumps({
    'user_id': '7063c43cc2aa',
    'type': 'bug',
    'title': '测试反馈 - 请删除',
    'description': '这是一个测试反馈，用于验证数据库写入',
    'contact': 'test@test.com'
}).encode('utf-8')
req = urllib.request.Request(url, data=body, method='POST', headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
result = json.loads(resp.read())
print(f"提交结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

# 查反馈列表
print("\n=== 反馈列表 ===")
req2 = urllib.request.Request('https://wstest-backend.onrender.com/api/feedback/list', method='GET', headers={'Content-Type':'application/json'})
resp2 = urllib.request.urlopen(req2)
data = json.loads(resp2.read())
print(f"反馈总数: {len(data)}")
for fb in data:
    fb_id = fb.get("feedback_id", "?")
    title = fb.get("title", "?")
    status = fb.get("status", "?")
    user_id = fb.get("user_id", "?")
    created = fb.get("created_at", "?")
    print(f"  - {fb_id}: {title} (user={user_id}, status={status}, time={created})")

# 直接查数据库（通过后端）
print("\n=== 数据库查询 ===")
req3 = urllib.request.Request('https://wstest-backend.onrender.com/api/admin/feedback/db-check', method='GET', headers={'Content-Type':'application/json'})
try:
    resp3 = urllib.request.urlopen(req3)
    db_data = json.loads(resp3.read())
    print(json.dumps(db_data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"直接数据库查询不可用: {e}")
