import requests
r = requests.get('https://wstest-backend.onrender.com/api/admin/tasks?user_id=d2279d8c0cdb')
tasks = r.json()
print(f'返回数据类型: {type(tasks)}')
print(f'返回数据: {tasks}')
