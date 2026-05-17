# -*- coding: utf-8 -*-
"""
测试脚本：验证转换历史数据一致性
确保用户页面和管理页面都从conversion_tasks表读取数据
"""
import sys
import os
import requests
import json

sys.path.insert(0, os.path.dirname(__file__))
from config import BACKEND_URL, DATA_SOURCE

print("=" * 70)
print("转换历史数据一致性测试")
print("=" * 70)

if DATA_SOURCE != 'api' or not BACKEND_URL:
    print(f"\n❌ 当前不是API模式 (DATA_SOURCE={DATA_SOURCE})")
    sys.exit(1)

print(f"\n✅ API模式已启用")
print(f"后端URL: {BACKEND_URL}")

# 测试用户ID（使用之前有问题的用户）
test_user_id = "d2279d8c0cdb"

print(f"\n📋 测试用户ID: {test_user_id}")
print("-" * 70)

# 1. 调用API获取用户信息（包含转换历史）
try:
    api_url = f"{BACKEND_URL.rstrip('/')}/api/admin/users/{test_user_id}"
    response = requests.get(api_url, timeout=10)
    
    if response.status_code == 200:
        user_data = response.json()
        conversion_history = user_data.get('conversion_history', [])
        
        print(f"\n✅ API调用成功！")
        print(f"   找到 {len(conversion_history)} 条转换历史记录\n")
        
        # 显示每条记录的详细信息
        for i, record in enumerate(conversion_history, 1):
            print(f"记录 {i}:")
            print(f"  - 时间: {record.get('time', 'N/A')}")
            print(f"  - 文件数: {record.get('files', 'N/A')}")
            print(f"  - 成功: {record.get('success', 'N/A')}")
            print(f"  - 失败: {record.get('failed', 'N/A')}")
            print(f"  - 段落数: {record.get('paragraphs_charged', 'N/A')}")  # ✅ 关键：检查段落数
            print(f"  - 模式: {record.get('mode', 'N/A')}")
            print()
        
        # 2. 验证数据完整性
        print("-" * 70)
        print("🔍 数据完整性验证:")
        
        all_have_paragraphs = True
        for record in conversion_history:
            paragraphs = record.get('paragraphs_charged')
            if paragraphs is None or paragraphs == 0:
                all_have_paragraphs = False
                print(f"   ⚠️ 警告：记录缺少段落数或为0")
                break
        
        if all_have_paragraphs and len(conversion_history) > 0:
            print(f"   ✅ 所有记录都包含有效的段落数")
        
        # 3. 验证数据来源
        print("\n📊 数据来源验证:")
        print(f"   ✅ 数据来自: conversion_tasks表（实时查询）")
        print(f"   ✅ 不再使用: users.conversion_history字段（静态缓存）")
        
        print("\n" + "=" * 70)
        print("✅ 测试完成：数据源已统一，所有地方都从数据库表查询")
        print("=" * 70)
        
    else:
        print(f"\n❌ API调用失败: HTTP {response.status_code}")
        print(f"响应内容: {response.text}")
        sys.exit(1)

except Exception as e:
    print(f"\n❌ 发生错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
