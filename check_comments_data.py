# -*- coding: utf-8 -*-
"""
检查Supabase数据库中comments表的结构和数据
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
print("检查comments表结构和数据")
print("=" * 80)

try:
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # 1. 检查comments表是否存在
        print("\n📋 1. 检查comments表是否存在:")
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'comments'
            )
        """))
        exists = result.fetchone()[0]
        
        if exists:
            print("   ✅ comments表存在")
        else:
            print("   ❌ comments表不存在")
            exit(1)
        
        # 2. 查看表结构
        print("\n📋 2. comments表结构:")
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'comments'
            ORDER BY ordinal_position
        """))
        
        for row in result:
            nullable = "NULL" if row[2] == 'YES' else "NOT NULL"
            default = f" DEFAULT {row[3]}" if row[3] else ""
            print(f"   - {row[0]}: {row[1]} ({nullable}{default})")
        
        # 3. 统计记录数
        print("\n📊 3. 数据统计:")
        result = conn.execute(text("SELECT COUNT(*) FROM comments"))
        total_count = result.fetchone()[0]
        print(f"   总评论数: {total_count}")
        
        # 4. 显示最近的5条评论
        if total_count > 0:
            print("\n📝 4. 最近5条评论:")
            result = conn.execute(text("""
                SELECT id, username, content, rating, likes, created_at, user_id
                FROM comments
                ORDER BY created_at DESC
                LIMIT 5
            """))
            
            for i, row in enumerate(result, 1):
                print(f"\n   [{i}] ID: {str(row[0])[:8]}...")
                print(f"       用户: {row[1]}")
                print(f"       内容: {row[2][:50]}{'...' if len(row[2]) > 50 else ''}")
                print(f"       评分: {'⭐' * row[3]}")
                print(f"       点赞: {row[4]}")
                print(f"       时间: {row[5]}")
                print(f"       用户ID: {row[6]}")
        
        # 5. 评分分布统计
        print("\n📈 5. 评分分布:")
        result = conn.execute(text("""
            SELECT rating, COUNT(*) as count
            FROM comments
            GROUP BY rating
            ORDER BY rating DESC
        """))
        
        for row in result:
            bar = '█' * row[1]
            print(f"   {row[0]}星: {row[1]}条 {bar}")
        
        # 6. 平均评分
        print("\n📊 6. 平均评分:")
        result = conn.execute(text("SELECT AVG(rating) FROM comments"))
        avg_rating = result.fetchone()[0]
        print(f"   平均分: {avg_rating:.2f} / 5.00")
        
        print("\n" + "=" * 80)
        print("✅ 检查完成")
        print("=" * 80)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
