# -*- coding: utf-8 -*-
import sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf8', buffering=1)
"""检查反馈数据写入feedbacks表的问题"""
import requests, json, sys

api_base = 'https://wstest-backend.onrender.com'

print("="*60)
print("Check1: Submit new feedback")
print("="*60)
test_feedback = {
    'user_id': 'test_check_user',
    'feedback_type': 'feature',
    'title': '测试-馈是否写入feedbacks表',
    'description': '这是测试提交，检查API是否写入feedbacks表',
    'contact': 'test@test.com'
}
r = requests.post(f"{api_base}/api/feedback/submit", json=test_feedback, timeout=10)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    result = r.json()
    print(f"返回字段: {json.dumps(result, ensure_ascii=False, indent=2)}")
    print(f"feedback_id: {result.get('id', result.get('feedback_id', 'N/A'))}")
    # 注意后端返回的是 id （UUID格式），不是 feedback_id
else:
    print(f"错误: {r.text}")

print()

print("="*60)
print("检查2: 现有反馈列- 检查返回字段名")
print("="*60)
r2 = requests.get(f"{api_base}/api/feedback/list", timeout=10)
data = r2.json()
if isinstance(data, list):
    print(f"共 {len(data)} 条反馈")
    for fb in data:
        # 列出所有字段
        print(f"\n反馈记录:")
        for key, value in fb.items():
            print(f"  {key} = {value}")
    print()
else:
    print(f"返回类型: {type(data)}")
    print(data)

print()

print("="*60)
print("检查3: 通过管理页面API直接查询")
print("="*60)
# 试试看 admin_web.py 是怎么读取反馈的 - 看是否有独立API
r3 = requests.get(f"{api_base}/api/admin/feedback/list", timeout=10)
print(f"/api/admin/feedback/list Status: {r3.status_code}")
if r3.status_code == 200:
    print(r3.json())
else:
    print(r3.text)

# 也试试 /api/feedback/stats
r4 = requests.get(f"{api_base}/api/feedback/stats", timeout=10)
print(f"\n/api/feedback/stats Status: {r4.status_code}")
if r4.status_code == 200:
    print(json.dumps(r4.json(), ensure_ascii=False, indent=2))
else:
    print(r4.text)
