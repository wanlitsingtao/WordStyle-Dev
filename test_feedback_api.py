# -*- coding: utf-8 -*-
"""
测试反馈提交API是否正常工作
"""
import requests
import json
from config import BACKEND_URL, DATA_SOURCE

print("=" * 70)
print("测试反馈提交API")
print("=" * 70)

if DATA_SOURCE != 'api' or not BACKEND_URL:
    print(f"\n❌ 当前不是API模式 (DATA_SOURCE={DATA_SOURCE})")
    exit(1)

print(f"\n✅ API模式已启用")
print(f"后端URL: {BACKEND_URL}")

# 测试提交一条反馈
test_feedback = {
    'user_id': 'test_api_check_001',
    'feedback_type': 'bug',
    'title': '【API测试】验证反馈写入',
    'description': '这是一条测试反馈，用于验证API是否正确写入数据库。如果看到这条记录，说明API工作正常。',
    'contact': 'test@example.com'
}

print(f"\n📤 步骤1: 提交测试反馈...")
try:
    api_url = f"{BACKEND_URL.rstrip('/')}/api/feedback/submit"
    response = requests.post(api_url, json=test_feedback, timeout=10)
    
    print(f"   HTTP状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ 提交成功！")
        print(f"   响应数据: {json.dumps(result, indent=2, ensure_ascii=False)}")
        feedback_id = result.get('id')
    else:
        print(f"   ❌ 提交失败: {response.text}")
        exit(1)

except Exception as e:
    print(f"   ❌ 发生错误: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# 查询反馈列表，验证是否写入
print(f"\n📥 步骤2: 查询反馈列表验证...")
try:
    list_url = f"{BACKEND_URL.rstrip('/')}/api/feedback/list"
    response = requests.get(list_url, timeout=10)
    
    if response.status_code == 200:
        feedbacks = response.json()
        print(f"   ✅ 查询成功！共 {len(feedbacks)} 条反馈记录")
        
        # 查找测试反馈
        test_feedback_found = None
        for fb in feedbacks:
            if fb.get('user_id') == 'test_api_check_001':
                test_feedback_found = fb
                break
        
        if test_feedback_found:
            print(f"\n   ✅✅✅ 测试反馈已成功写入数据库！")
            print(f"   反馈详情:")
            print(f"     ID: {test_feedback_found.get('id')}")
            print(f"     用户ID: {test_feedback_found.get('user_id')}")
            print(f"     类型: {test_feedback_found.get('feedback_type')}")
            print(f"     标题: {test_feedback_found.get('title')}")
            print(f"     状态: {test_feedback_found.get('status')}")
            print(f"     时间: {test_feedback_found.get('created_at')}")
        else:
            print(f"\n   ⚠️ 未找到测试反馈（可能API返回的是缓存数据）")
            print(f"   所有反馈的用户ID: {[fb.get('user_id') for fb in feedbacks[:5]]}")
    else:
        print(f"   ❌ 查询失败: {response.status_code}")

except Exception as e:
    print(f"   ❌ 发生错误: {e}")

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
