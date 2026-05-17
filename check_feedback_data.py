# -*- coding: utf-8 -*-
"""
诊断脚本：检查feedbacks表中的数据
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from config import DATABASE_URL, BACKEND_URL, DATA_SOURCE
import requests

print("=" * 60)
print("反馈数据诊断工具")
print("=" * 60)
print(f"\n当前数据源模式: {DATA_SOURCE}")
print(f"后端URL: {BACKEND_URL}")
print(f"数据库URL: {'已配置' if DATABASE_URL else '未配置'}")

if DATA_SOURCE == 'api' and BACKEND_URL:
    print("\n✅ API模式：通过后端API检查反馈数据")
    try:
        api_url = f"{BACKEND_URL.rstrip('/')}/api/feedback/list"
        print(f"请求URL: {api_url}")
        
        response = requests.get(api_url, timeout=10)
        print(f"HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            feedbacks = response.json()
            print(f"\n✅ 成功获取到 {len(feedbacks)} 条反馈记录")
            
            # 打印第一条记录的原始数据用于调试
            if feedbacks:
                print("\n📋 第一条记录的原始JSON数据：")
                import json
                print(json.dumps(feedbacks[0], indent=2, ensure_ascii=False))
            
            if feedbacks:
                print("\n最近的5条反馈：")
                print("-" * 60)
                for i, fb in enumerate(feedbacks[:5], 1):
                    # ✅ 兼容多种字段名
                    fb_id = fb.get('id') or fb.get('feedback_id', 'N/A')
                    fb_type = fb.get('feedback_type') or fb.get('type', 'N/A')
                    
                    print(f"\n{i}. ID: {fb_id}")
                    print(f"   用户ID: {fb.get('user_id', 'N/A')}")
                    print(f"   类型: {fb_type}")
                    print(f"   标题: {fb.get('title', 'N/A')[:50]}")
                    print(f"   描述: {fb.get('description', 'N/A')[:50]}")
                    print(f"   状态: {fb.get('status', 'N/A')}")
                    print(f"   创建时间: {fb.get('created_at', fb.get('timestamp', 'N/A'))}")
            else:
                print("\n⚠️ 数据库中没有反馈记录")
        else:
            print(f"\n❌ API请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
    
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

elif DATA_SOURCE == 'supabase':
    print("\n✅ Supabase模式：直接查询数据库")
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        try:
            from backend.app.models import Feedback
            
            # 查询所有反馈
            feedbacks = db.query(Feedback).order_by(Feedback.created_at.desc()).all()
            print(f"\n✅ 数据库中查询到 {len(feedbacks)} 条反馈记录")
            
            if feedbacks:
                print("\n最近的5条反馈：")
                print("-" * 60)
                for i, fb in enumerate(feedbacks[:5], 1):
                    print(f"\n{i}. ID: {fb.id}")
                    print(f"   用户ID: {fb.user_id}")
                    print(f"   类型: {fb.feedback_type}")
                    print(f"   标题: {fb.title[:50] if fb.title else 'N/A'}")
                    print(f"   描述: {fb.description[:50] if fb.description else 'N/A'}")
                    print(f"   状态: {fb.status}")
                    print(f"   创建时间: {fb.created_at}")
            else:
                print("\n⚠️ 数据库中没有反馈记录")
        
        finally:
            db.close()
    
    except Exception as e:
        print(f"\n❌ 数据库查询失败: {e}")
        import traceback
        traceback.print_exc()

else:
    print("\n✅ 本地模式：检查本地JSON文件")
    try:
        from comments_manager import load_feedbacks
        
        feedbacks = load_feedbacks()
        print(f"\n✅ 本地文件中查询到 {len(feedbacks)} 条反馈记录")
        
        if feedbacks:
            print("\n最近的5条反馈：")
            print("-" * 60)
            for i, fb in enumerate(feedbacks[:5], 1):
                print(f"\n{i}. ID: {fb.get('id', 'N/A')}")
                print(f"   用户ID: {fb.get('user_id', 'N/A')}")
                print(f"   类型: {fb.get('feedback_type', 'N/A')}")
                print(f"   标题: {fb.get('title', 'N/A')[:50]}")
                print(f"   描述: {fb.get('description', 'N/A')[:50]}")
                print(f"   状态: {fb.get('status', 'N/A')}")
                print(f"   时间: {fb.get('timestamp', 'N/A')}")
        else:
            print("\n⚠️ 本地文件中没有反馈记录")
    
    except Exception as e:
        print(f"\n❌ 加载本地文件失败: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
