import requests

BACKEND = "https://wstest-backend.onrender.com"

# 查反馈列表 - 详细字段
resp = requests.get(f"{BACKEND}/api/feedback/list", timeout=10)
data = resp.json()
print(f"反馈总数: {len(data)}")
for fb in data:
    print()
    print(f"  feedback_id: {fb.get('feedback_id', 'N/A')}")
    print(f"  id (raw get): {fb.get('id', 'NOT_FOUND')}")
    print(f"  user_id: {fb.get('user_id', 'N/A')}")
    print(f"  type: {fb.get('type', 'N/A')}")
    print(f"  feedback_type: {fb.get('feedback_type', 'N/A')}")
    print(f"  title: {fb.get('title', 'N/A')}")
    print(f"  status: {fb.get('status', 'N/A')}")
    print(f"  created_at: {fb.get('created_at', 'N/A')}")
    print(f"  timestamp: {fb.get('timestamp', 'N/A')}")
