# -*- coding: utf-8 -*-
"""检查工作目录下问题修复情况"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

print('=' * 60)
print('问题1：转换历史 — 检查修复情况')
print('=' * 60)

# 1. models.py
with open('backend/app/models.py', 'r', encoding='utf-8') as f:
    content = f.read()
has_field = 'conversion_history' in content
print(f'\n1.1 User 模型 conversion_history 字段: {"✅ 存在" if has_field else "❌ 不存在"}')
if has_field:
    for line in content.split('\n'):
        if 'conversion_history' in line:
            print(f'     {line.strip()}')

# 2. admin.py
with open('backend/app/api/admin.py', 'r', encoding='utf-8') as f:
    content = f.read()

# create_or_update_user
idx = content.find('def create_or_update_user')
end = content.find('@router.post("/users/{user_id}/claim-free"', idx)
func_body = content[idx:end] if end > 0 else content[idx:idx+2000]
has_save = 'conversion_history' in func_body
print(f'\n1.2 create_or_update_user 处理 conversion_history: {"✅ 是" if has_save else "❌ 否"}')
if has_save:
    for line in func_body.split('\n'):
        if 'conversion_history' in line:
            print(f'     {line.strip()}')

# /users/by-device 返回
idx2 = content.find('/users/by-device')
section = content[idx2:idx2+2500]
return_count = section.count('conversion_history')
print(f'\n1.3 /users/by-device 返回 conversion_history: {"✅ 是" if return_count > 0 else "❌ 否"}')
print(f'     出现次数: {return_count}')

# 3. app.py 前端
with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# show_history_dialog
print('\n1.4 show_history_dialog 读取逻辑:')
for i, line in enumerate(lines):
    if 'def show_history_dialog' in line:
        for j in range(i, min(len(lines), i+15)):
            if 'conversion_history' in lines[j]:
                print(f'     ✅ Line {j+1}: {lines[j].rstrip()[:100]}')
        break

# 转换完成保存
print('\n1.5 转换完成后保存:')
for i, line in enumerate(lines):
    if 'conversion_history.append' in line:
        print(f'     ✅ Line {i+1}: {line.rstrip()[:100]}')
        for k in range(i, min(len(lines), i+10)):
            if 'save_user_data' in lines[k]:
                print(f'     ✅ Line {k+1}: {lines[k].rstrip()[:100]}')
        break


print('\n' + '=' * 60)
print('问题2：反馈管理页面 — 检查修复情况')
print('=' * 60)

with open('admin_web.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找 show_feedback_management 函数
func_start = None
for i, line in enumerate(lines):
    if 'def show_feedback_management' in line:
        func_start = i
        break

print(f'\n2.1 字段名检查 (admin_web.py Line {func_start+1} 起):')
if func_start:
    for i in range(func_start, min(len(lines), func_start+200)):
        line = lines[i]
        if "fb.get(" in line:
            print(f'     Line {i+1}: {line.rstrip()[:100]}')

# 检查存储方式
print('\n2.2 存储方式:')
with open('admin_web.py', 'r', encoding='utf-8') as f:
    content = f.read()
if 'make_api_request' in content or 'BACKEND_URL' in content:
    print('     管理页面通过 API 读取反馈数据')
else:
    print('     管理页面使用本地文件读取 (load_feedbacks)')

# 检查 app.py 反馈提交方式
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()
if 'make_api_request' in content and 'feedback' in content:
    print('     前端通过 API 提交反馈')
else:
    print('     前端使用本地存储 (add_feedback)')

# 检查 feedback.py 路径
with open('backend/app/api/feedback.py', 'r', encoding='utf-8') as f:
    content = f.read()
print('\n2.3 feedback.py 后端 API:')
for line in content.split('\n')[:30]:
    if 'FEEDBACK_FILE' in line or 'Path' in line:
        print(f'     {line.strip()}')
has_abs_path = 'e:/' in content.lower() or 'c:/' in content.lower()
if has_abs_path:
    print('     ⚠️ 使用了绝对路径 (部署后可能导致 500 错误)')
else:
    print('     ✅ 使用相对路径')

print('\n' + '=' * 60)
print('检查完成')
print('=' * 60)
