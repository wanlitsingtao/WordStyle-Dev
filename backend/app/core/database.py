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
    # [FIX 2026-10-06] SQLAlchemy 2.x 对 postgresql:// 默认改用 psycopg3 驱动，
    # 而云端 requirements 只装 psycopg2-binary → ModuleNotFoundError: No module named 'psycopg'
    # 且 data_manager 初始化失败后静默回退 local。URL 未显式指定驱动时固定用 psycopg2。
    if final_url.startswith("postgresql://"):
        final_url = "postgresql+psycopg2://" + final_url[len("postgresql://"):]
        logger.info("[FIX] PostgreSQL URL 已固定驱动 psycopg2")
    # [PERF] 连接超时：Supabase 不可达/慢时快速失败，避免首页无限期挂起
    connect_args = {"connect_timeout": 10}
    # [FIX 2026-10-06] Supabase（尤其是 pooler 6543 / 直连 5432）要求 SSL；
    # 很多部署的 DATABASE_URL 没有 sslmode，导致初始化时连接被拒绝/握手失败，
    # data_manager 捕获异常后回退到 local。自动补 sslmode=require，已有时不再覆盖。
    if ("supabase" in final_url.lower() or "pooler.supabase" in final_url.lower()) \
            and "sslmode=" not in final_url.lower():
        sep = "&" if "?" in final_url else "?"
        final_url = f"{final_url}{sep}sslmode=require"
        logger.info("[FIX] PostgreSQL URL 已自动补全 sslmode=require")

logger.info(f"[LINK] 数据库引擎创建 - URL: {final_url[:60]}...")
engine = create_engine(
    final_url,
    connect_args=connect_args,
    pool_pre_ping=True,   # [PERF] 复用前探活，避免 pgbouncer 回收后的僵尸连接挂起
    pool_recycle=300,     # [PERF] 5 分钟回收，对齐 Supabase pgbouncer 空闲回收
)

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
