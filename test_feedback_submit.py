# -*- coding: utf-8 -*-
"""
测试脚本：提交一条测试反馈并验证是否写入数据库
"""
import sys
import os
import requests
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from config import BACKEND_URL, DATA_SOURCE

print("=" * 70)
print("反馈提交测试")
print("=" * 70)

if DATA_SOURCE != 'api' or not BACKEND_URL:
    print(f"\n❌ 当前不是API模式 (DATA_SOURCE={DATA_SOURCE})")
    print("此测试仅在API模式下有效")
    sys.exit(1)

print(f"\n✅ API模式已启用")
print(f"后端URL: {BACKEND_URL}")

# 1. 提交测试反馈
print("\n" + "-" * 70)
print("步骤1: 提交测试反馈")
print("-" * 70)

test_feedback = {
    'user_id': 'test_user_12345',
    'feedback_type': 'bug',
    'title': '【测试】验证反馈写入数据库',
    'description': '这是一条测试反馈，用于验证是否正确写入feedbacks表。如果看到这条记录，说明API正常工作。',
    'contact': 'test@example.com'
}

try:
    api_url = f"{BACKEND_URL.rstrip('/')}/api/feedback/submit"
    print(f"请求URL: {api_url}")
    print(f"请求数据: {json.dumps(test_feedback, ensure_ascii=False, indent=2)}")
    
    response = requests.post(api_url, json=test_feedback, timeout=10)
    print(f"\nHTTP状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ 提交成功！")
        print(f"响应数据:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        feedback_id = result.get('id') or result.get('feedback_id')
        print(f"\n反馈ID: {feedback_id}")
    else:
        print(f"\n❌ 提交失败: {response.status_code}")
        print(f"响应内容: {response.text}")
        sys.exit(1)

except Exception as e:
    print(f"\n❌ 发生错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. 查询所有反馈，验证测试反馈是否存在
print("\n" + "-" * 70)
print("步骤2: 查询反馈列表，验证测试反馈是否存在")
print("-" * 70)

try:
    list_url = f"{BACKEND_URL.rstrip('/')}/api/feedback/list"
    print(f"请求URL: {list_url}")
    
    response = requests.get(list_url, timeout=10)
    print(f"HTTP状态码: {response.status_code}")
    
    if response.status_code == 200:
        feedbacks = response.json()
        print(f"\n✅ 查询成功！共 {len(feedbacks)} 条反馈记录")
        
        # 查找测试反馈
        test_feedback_found = None
        for fb in feedbacks:
            title = fb.get('title') or fb.get('feedback_title', '')
            if '【测试】' in str(title):
                test_feedback_found = fb
                break
        
        if test_feedback_found:
            print(f"\n✅✅✅ 测试反馈已成功写入数据库！")
            print(f"\n找到的测试反馈详情：")
            print(json.dumps(test_feedback_found, indent=2, ensure_ascii=False))
        else:
            print(f"\n⚠️ 未找到测试反馈")
            print(f"\n最近的5条反馈：")
            for i, fb in enumerate(feedbacks[:5], 1):
                print(f"\n{i}. ID: {fb.get('id') or fb.get('feedback_id', 'N/A')}")
                print(f"   标题: {fb.get('title', 'N/A')[:50]}")
                print(f"   用户ID: {fb.get('user_id', 'N/A')}")
                print(f"   时间: {fb.get('created_at', 'N/A')}")
    else:
        print(f"\n❌ 查询失败: {response.status_code}")
        print(f"响应内容: {response.text}")

except Exception as e:
    print(f"\n❌ 发生错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
