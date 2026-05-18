#!/usr/bin/env python3
"""
WordStyle Supabase数据库初始化脚本

功能：
1. 验证数据库连接
2. 检查表结构是否完整
3. 插入默认配置（如果不存在）
4. 显示初始化报告

使用方法：
    cd backend
    python init_supabase.py
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from app.models import Base, SystemConfig
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def get_database_url():
    """获取数据库连接URL"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[ERROR] 错误：未设置 DATABASE_URL 环境变量")
        print("\n请在 backend/.env.production 中配置 DATABASE_URL")
        print("格式：postgresql://postgres:password@db.xxx.supabase.co:5432/postgres")
        sys.exit(1)
    return db_url


def check_connection(db_url):
    """检查数据库连接"""
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[OK] 数据库连接成功")
        return engine
    except Exception as e:
        print(f"[ERROR] 数据库连接失败: {e}")
        print("\n请检查：")
        print("1. DATABASE_URL 格式是否正确")
        print("2. 密码是否包含特殊字符（需要URL编码）")
        print("   例如: @ 编码为 %40, : 编码为 %3A")
        print("3. Supabase项目是否已创建")
        print("4. 网络是否可以访问Supabase")
        sys.exit(1)


def check_tables(engine):
    """检查表结构"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    required_tables = [
        'users', 'conversion_tasks', 
        'system_config', 'comments', 'feedbacks', 'style_mappings'
    ]
    
    missing_tables = [t for t in required_tables if t not in tables]
    
    if missing_tables:
        print(f"[WARN]  缺少表: {', '.join(missing_tables)}")
        print("\n请先执行 SQL Editor 中的初始化脚本")
        print("位置: Supabase控制台 → SQL Editor → New query")
        return False
    else:
        print("[OK] 所有必需的表已存在")
        return True


def init_default_config(engine):
    """初始化默认配置"""
    Session = sessionmaker(bind=engine)
    session = Session()
    
    defaults = {
        'free_paragraphs_daily': ('10000', '每日免费段落数'),
        'paragraph_price': ('0.001', '每段落价格(元)'),
        'admin_contact': ('微信号：your_wechat_id', '管理员联系方式'),
    }
    
    inserted = []
    for key, (value, desc) in defaults.items():
        existing = session.query(SystemConfig).filter_by(config_key=key).first()
        if not existing:
            config = SystemConfig(
                config_key=key,
                config_value=value,
                description=desc
            )
            session.add(config)
            inserted.append(key)
    
    if inserted:
        session.commit()
        print(f"[OK] 已插入默认配置: {', '.join(inserted)}")
    else:
        print("ℹ️  默认配置已存在，跳过初始化")
    
    session.close()


def show_summary(engine):
    """显示初始化摘要"""
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("\n" + "="*60)
    print("[STATS] 数据库初始化报告")
    print("="*60)
    
    # 统计表数量
    table_count = session.execute(text(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
    )).scalar()
    print(f"表总数: {table_count}")
    
    # 统计配置数量
    config_count = session.query(SystemConfig).count()
    print(f"系统配置数: {config_count}")
    
    # 列出所有表
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\n表列表:")
    for table in sorted(tables):
        print(f"  - {table}")
    
    # 显示配置详情
    configs = session.query(SystemConfig).all()
    print(f"\n系统配置:")
    for config in configs:
        print(f"  - {config.config_key}: {config.config_value}")
        print(f"    说明: {config.description}")
    
    print("\n" + "="*60)
    print("[OK] 数据库初始化完成！")
    print("="*60)
    print("\n下一步：")
    print("1. 启动后端服务: python run_dev.py")
    print("2. 访问API文档: http://localhost:8000/docs")
    print("3. 测试健康检查: http://localhost:8000/health")
    
    session.close()


if __name__ == "__main__":
    print("[LAUNCH] 开始初始化Supabase数据库...\n")
    
    # 1. 获取数据库URL
    db_url = get_database_url()
    print(f"📡 连接到: {db_url[:50]}...")
    
    # 2. 检查连接
    engine = check_connection(db_url)
    
    # 3. 检查表结构
    if not check_tables(engine):
        print("\n[ERROR] 初始化失败，请先执行SQL脚本创建表结构")
        print("\nSQL脚本位置: DEPLOYMENT_UPGRADE_PLAN.md 第一步.1.2.A")
        sys.exit(1)
    
    # 4. 初始化默认配置
    init_default_config(engine)
    
    # 5. 显示摘要
    show_summary(engine)
