# -*- coding: utf-8 -*-
"""
初始化数据库 - 创建所有表
"""
from app.core.database import engine, Base
from app.models import User, ConversionTask, SystemConfig
# 已移除：Order模型（项目无充值/订单功能）

def init_db():
    """创建所有数据库表并初始化默认配置"""
    print("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建成功！")
    
    # 显示创建的表
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\n已创建的表: {', '.join(tables)}")
    
    # 初始化默认配置
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        # 检查是否已有配置
        existing_config = db.query(SystemConfig).filter(
            SystemConfig.config_key == "free_paragraphs_on_first_login"
        ).first()
        
        if not existing_config:
            default_config = SystemConfig(
                config_key="free_paragraphs_on_first_login",
                config_value="10000",
                description="新用户首次登录赠送的免费段落数"
            )
            db.add(default_config)
            db.commit()
            print("✅ 已初始化默认配置：新用户赠送 10000 段免费额度")
        else:
            print(f"ℹ️  当前免费额度配置：{existing_config.config_value} 段")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
