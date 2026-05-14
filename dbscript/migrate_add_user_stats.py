import sqlite3
import os

# 修复SQLite数据库表结构
ws_db = os.path.join(os.path.dirname(__file__), 'wordstyle.db')

print("=== 修复 wordstyle.db - 添加缺失字段 ===")
if os.path.exists(ws_db):
    conn = sqlite3.connect(ws_db)
    cursor = conn.cursor()
    
    # 检查当前表结构
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    field_names = [col[1] for col in columns]
    
    print(f"\n当前 users 表有 {len(field_names)} 个字段:")
    for name in field_names:
        print(f"  - {name}")
    
    # 添加缺失的字段
    modifications = []
    
    if 'total_paragraphs_used' not in field_names:
        print("\n➕ 添加字段: total_paragraphs_used")
        cursor.execute("ALTER TABLE users ADD COLUMN total_paragraphs_used INTEGER DEFAULT 0")
        modifications.append('total_paragraphs_used')
    
    if 'total_converted' not in field_names:
        print("➕ 添加字段: total_converted")
        cursor.execute("ALTER TABLE users ADD COLUMN total_converted INTEGER DEFAULT 0")
        modifications.append('total_converted')
    
    if modifications:
        conn.commit()
        print(f"\n✅ 成功添加了 {len(modifications)} 个字段: {', '.join(modifications)}")
    else:
        print("\n✅ 表结构已是最新的，无需修改")
    
    # 验证修复结果
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print(f"\n修复后 users 表共有 {len(columns)} 个字段:")
    for col in columns:
        print(f"  {col[1]:30s} ({col[2]})")
    
    conn.close()
else:
    print("❌ 数据库文件不存在")

print("\n" + "="*60)
print("=== 验证修复 ===")
if os.path.exists(ws_db):
    conn = sqlite3.connect(ws_db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    field_names = [col[1] for col in columns]
    
    if 'total_paragraphs_used' in field_names and 'total_converted' in field_names:
        print("✅ 验证通过！所有必需字段都存在")
    else:
        print("❌ 验证失败！仍有缺失字段")
    
    conn.close()
