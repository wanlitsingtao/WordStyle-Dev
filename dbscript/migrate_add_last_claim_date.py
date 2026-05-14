# -*- coding: utf-8 -*-
"""
添加 users 表的 last_claim_date 字段
用于记录用户上次领取免费额度的日期，防止重复领取
"""
import sys
from pathlib import Path

# 添加 backend 路径
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.database import engine, SessionLocal
from sqlalchemy import text

def add_last_claim_date_column():
    """添加 last_claim_date 字段"""
    print("=" * 60)
    print("📊 添加 last_claim_date 字段")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # 检查字段是否已存在
        check_sql = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'last_claim_date'
        """
        result = db.execute(text(check_sql)).fetchone()
        
        if result:
            print("✅ last_claim_date 字段已存在，无需添加")
            return True
        
        # 添加字段
        print("📝 正在添加 last_claim_date 字段...")
        add_sql = """
            ALTER TABLE users 
            ADD COLUMN last_claim_date TIMESTAMP WITH TIME ZONE
        """
        db.execute(text(add_sql))
        db.commit()
        
        print("✅ last_claim_date 字段添加成功")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ 添加字段失败: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = add_last_claim_date_column()
    if success:
        print("\n✅ 数据库迁移完成")
        sys.exit(0)
    else:
        print("\n❌ 数据库迁移失败")
        sys.exit(1)
