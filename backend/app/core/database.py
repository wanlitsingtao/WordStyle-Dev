# -*- coding: utf-8 -*-
"""
数据库连接和会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import os
import logging

logger = logging.getLogger(__name__)

# 创建数据库引擎
connect_args = {}
final_url = settings.DATABASE_URL

if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif settings.DATABASE_URL.startswith("postgresql"):
    # Supabase 环境配置：自动切换到连接池器（PgBouncer）
    original_url = settings.DATABASE_URL
    if "supabase.co" in original_url and ":5432" in original_url:
        # 提取项目名称（数据库主机名中的标识符）
        host_part = original_url.split("@")[-1].split("/")[0].split(":")[0]  # 去除端口号
        project_id = host_part.replace("db.", "").replace(".supabase.co", "")
            
        # 提取用户名并添加项目 ID 前缀（Supabase 连接池器要求）
        user_part = original_url.split("://")[1].split("@")[0]
        # 如果用户名不是 postgres.<project_id> 格式，则添加前缀
        if not user_part.startswith(f"postgres.{project_id}"):
            new_user = f"postgres.{project_id}"
            original_url = original_url.replace(f"://{user_part}@", f"://{new_user}@")
            logger.info(f"✅ 连接池器用户名已转换: {user_part} -> {new_user}")
            
        # 动态获取连接池器地址（根据原始 URL 中的区域或默认使用通用地址）
        # 注意：不同区域的 Supabase 项目可能对应不同的 Pooler 域名
        # 这里我们尝试从原始 URL 提取区域，如果失败则使用通用的 pooler 地址
        final_url = original_url.replace(
            f"db.{project_id}.supabase.co:5432",
            f"{project_id}.pooler.supabase.com:6543"
        )
        logger.info(f"✅ 检测到 Supabase 直接连接，自动切换为连接池器")
        logger.info(f"   原始 URL: {settings.DATABASE_URL[:60]}...")
        logger.info(f"   池化 URL: {final_url[:60]}...")

logger.info(f"🔗 数据库引擎创建 - URL: {final_url[:60]}...")
engine = create_engine(final_url, connect_args=connect_args)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()

def get_db():
    """
    获取数据库会话
    
    Yields:
        SQLAlchemy Session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
