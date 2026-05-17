# -*- coding: utf-8 -*-
"""
检查Supabase数据库中feedbacks表的数据
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ 错误: 未找到DATABASE_URL环境变量")
    exit(1)

print("=" * 80)
print("检查feedbacks表数据")
print("=" * 80)

try:
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # 1. 检查feedbacks表是否存在
        print("\n📋 1. 检查feedbacks表是否存在:")
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'feedbacks'
            )
        """))
        exists = result.fetchone()[0]
        
        if exists:
            print("   ✅ feedbacks表存在")
        else:
            print("   ❌ feedbacks表不存在！")
            print("\n💡 提示: 需要执行数据库初始化脚本创建feedbacks表")
            exit(1)
        
        # 2. 检查表结构
        print("\n📋 2. feedbacks表结构:")
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'feedbacks'
            ORDER BY ordinal_position
        """))
        columns = result.fetchall()
        for col in columns:
            nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
            default = f" DEFAULT {col[3]}" if col[3] else ""
            print(f"   - {col[0]:30} {col[1]:20} {nullable}{default}")
        
        # 3. 统计记录数
        print("\n📊 3. 数据统计:")
        result = conn.execute(text("SELECT COUNT(*) FROM feedbacks"))
        count = result.fetchone()[0]
        print(f"   总记录数: {count}")
        
        # 4. 显示最近的反馈
        if count > 0:
            print("\n📝 4. 最近的5条反馈:")
            result = conn.execute(text("""
                SELECT id, user_id, feedback_type, title, status, created_at
                FROM feedbacks
                ORDER BY created_at DESC
                LIMIT 5
            """))
            rows = result.fetchall()
            for i, row in enumerate(rows, 1):
                print(f"\n   {i}. ID: {str(row[0])[:8]}...")
                print(f"      用户ID: {row[1]}")
                print(f"      类型: {row[2]}")
                print(f"      标题: {row[3][:50]}")
                print(f"      状态: {row[4]}")
                print(f"      时间: {row[5]}")
        else:
            print("\n⚠️  feedbacks表中没有任何记录！")
            print("\n💡 可能的原因:")
            print("   1. 前端提交失败（检查浏览器控制台）")
            print("   2. 后端API调用失败（检查后端日志）")
            print("   3. 后端代码未正确部署到Render")
            print("   4. 数据库连接配置错误")

except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
