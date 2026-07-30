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
    # [FIX] 使用环境变量 DATABASE_URL 原样连接，不再自动切换到 PgBouncer 连接池
    # PgBouncer 在 Supabase 免费套餐中可能将写操作路由到只读副本，导致 ReadOnlySqlTransaction
    # 直连模式更可靠
    logger.info(f"[OK] PostgreSQL 直连模式: {final_url[:60]}...")

logger.info(f"[LINK] 数据库引擎创建 - URL: {final_url[:60]}...")
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
