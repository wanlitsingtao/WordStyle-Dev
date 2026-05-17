import requests

BACKEND = "https://wstest-backend.onrender.com"

print("=" * 50)
print("1. 查询反馈列表")
print("=" * 50)
try:
    resp = requests.get(f"{BACKEND}/api/feedback/list", timeout=10)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"反馈总数: {len(data)}")
    for fb in data:
        print(f"  id={fb.get('feedback_id','?')}")
        print(f"  title={fb.get('title','?')}")
        print(f"  user_id={fb.get('user_id','?')}")
        print(f"  type={fb.get('type','?')}")
        print(f"  status={fb.get('status','?')}")
        print(f"  created_at={fb.get('created_at','?')}")
        print()
except Exception as e:
    print(f"Error: {e}")

print("=" * 50)
print("2. 提交新反馈")
print("=" * 50)
try:
    payload = {
        "user_id": "7063c43cc2aa",
        "type": "bug",
        "title": "测试反馈 - 请管理员删除",
        "description": "验证数据库写入",
        "contact": "test@test.com"
    }
    resp = requests.post(f"{BACKEND}/api/feedback/submit", json=payload, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
except Exception as e:
    print(f"Error: {e}")

print("=" * 50)
print("3. 再次查询反馈列表（验证新增）")
print("=" * 50)
try:
    resp = requests.get(f"{BACKEND}/api/feedback/list", timeout=10)
    data = resp.json()
    print(f"反馈总数: {len(data)}")
    for fb in data:
        print(f"  {fb.get('feedback_id','?')}: {fb.get('title','?')} (status={fb.get('status','?')})")
except Exception as e:
    print(f"Error: {e}")
