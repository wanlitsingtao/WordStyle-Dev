# -*- coding: utf-8 -*-
"""
检查Supabase数据库当前迁移状态和表结构
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
print("Supabase数据库结构检查")
print("=" * 80)
print(f"数据库连接: {DATABASE_URL[:50]}...")
print()

try:
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # 1. 检查alembic版本
        print("📋 1. Alembic迁移版本:")
        try:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            if row:
                current_version = row[0]
                print(f"   当前版本: {current_version}")
                
                # 判断是否需要升级
                expected_version = '20260517_1330'
                if current_version == expected_version:
                    print(f"   ✅ 数据库已是最新版本")
                else:
                    print(f"   ⚠️ 需要升级到版本: {expected_version}")
            else:
                print(f"   ⚠️ alembic_version表为空，可能需要初始化")
        except Exception as e:
            print(f"   ❌ 查询失败: {e}")
        
        print()
        
        # 2. 检查users表结构
        print("📋 2. users表结构:")
        try:
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'users'
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            for col in columns:
                nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col[3]}" if col[3] else ""
                print(f"   - {col[0]:30} {col[1]:20} {nullable}{default}")
        except Exception as e:
            print(f"   ❌ 查询失败: {e}")
        
        print()
        
        # 3. 检查conversion_tasks表结构
        print("📋 3. conversion_tasks表结构:")
        try:
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'conversion_tasks'
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            
            has_paragraphs = False
            for col in columns:
                nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col[3]}" if col[3] else ""
                print(f"   - {col[0]:30} {col[1]:20} {nullable}{default}")
                if col[0] == 'paragraphs':
                    has_paragraphs = True
            
            if has_paragraphs:
                print(f"   ✅ paragraphs字段已存在")
            else:
                print(f"   ❌ paragraphs字段缺失，需要添加")
        except Exception as e:
            print(f"   ❌ 查询失败: {e}")
        
        print()
        
        # 4. 检查feedbacks表结构
        print("📋 4. feedbacks表结构:")
        try:
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
        except Exception as e:
            print(f"   ❌ 查询失败: {e}")
        
        print()
        
        # 5. 统计信息
        print("📊 5. 数据统计:")
        try:
            tables = ['users', 'conversion_tasks', 'feedbacks']
            for table in tables:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.fetchone()[0]
                print(f"   - {table:30} {count} 条记录")
        except Exception as e:
            print(f"   ❌ 查询失败: {e}")

except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
