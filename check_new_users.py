import requests
from datetime import datetime

# 查询所有用户
r = requests.get('https://wstest-backend.onrender.com/api/admin/users?limit=100')
users_data = r.json()

print(f"API返回数据结构: {list(users_data.keys())}")
print(f"第一个用户的所有字段: {list(users_data.get('users', [{}])[0].keys()) if users_data.get('users') else '无'}\n")

users = users_data.get('users', [])
print(f"数据库中共有 {len(users)} 个用户\n")
print("=" * 80)

# 按创建时间排序
users_sorted = sorted(users, key=lambda u: u.get('created_at', ''), reverse=True)

for i, user in enumerate(users_sorted[:20], 1):  # 只显示最近20个
    created_at = user.get('created_at', 'N/A')
    device_fp = user.get('device_fingerprint', 'N/A')
    user_id = user.get('user_id', user.get('id', 'N/A'))  # ✅ 兼容两种字段名
    
    # 判断是否是最近创建的（部署后）
    print(f"{i}. 用户ID: {user_id}")
    print(f"   设备指纹: {device_fp[:16] if device_fp != 'N/A' else 'N/A'}...")
    print(f"   创建时间: {created_at}")
    print(f"   最后登录: {user.get('last_login', 'N/A')}")
    print(f"   余额: {user.get('balance', 0)}")
    print(f"   段落数: {user.get('paragraphs_remaining', 0)}")
    print()
