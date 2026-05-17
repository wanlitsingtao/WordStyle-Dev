import requests, json

# 测试1: 反馈提交
r = requests.post('https://wstest-backend.onrender.com/api/feedback/submit', json={
    'user_id': 'test_diag',
    'feedback_type': 'bug',
    'title': '诊断测试',
    'description': '测试描述',
    'contact': 'test@test.com'
}, timeout=15)
print(f'[提交] 状态: {r.status_code}')

# 测试2: 反馈列表 - 查看原始响应
r = requests.get('https://wstest-backend.onrender.com/api/feedback/list', timeout=15)
print(f'[列表] 状态: {r.status_code}')
data = r.json()
print(f'[列表] 类型: {type(data).__name__}')
if isinstance(data, list):
    print(f'[列表] 数量: {len(data)}')
    if data:
        print(f'[列表] 第一条字段: {list(data[0].keys())}')
        print(f'[列表] 第一条: {json.dumps(data[0], ensure_ascii=False)[:300]}')
elif isinstance(data, dict):
    print(f'[列表] keys: {list(data.keys())}')
    print(f'[列表] 内容: {json.dumps(data, ensure_ascii=False)[:300]}')

# 测试3: 反馈统计
r2 = requests.get('https://wstest-backend.onrender.com/api/feedback/stats', timeout=15)
print(f'\n[统计] 状态: {r2.status_code}')
print(f'[统计] 内容: {r2.text[:200]}')
