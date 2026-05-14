# -*- coding: utf-8 -*-
"""
应用配置管理
支持 Streamlit Cloud Secrets 自动读取
"""
from pydantic_settings import BaseSettings
from typing import List
import os

def _load_database_url():
    """
    加载 DATABASE_URL，优先从 Streamlit Secrets 读取，并自动转换连接池器为直连地址
    """
    from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
    
    database_url = None
    
    # 1. 尝试从 Streamlit Secrets 读取
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and len(st.secrets) > 0:
            secrets_db_url = st.secrets.get('DATABASE_URL')
            if secrets_db_url:
                database_url = secrets_db_url
                print(f"✅ 从 Streamlit Secrets 加载 DATABASE_URL")
    except Exception as e:
        print(f"⚠️ 读取 Streamlit Secrets 失败: {e}")
    
    # 2. 从环境变量读取
    if not database_url:
        database_url = os.getenv("DATABASE_URL", "sqlite:///./wordstyle.db")
        print(f"📝 从环境变量加载 DATABASE_URL")
    
    # 3. 自动转换连接池器为直连地址（Streamlit Cloud 兼容）
    if database_url and database_url.startswith("postgresql"):
        if "pooler.supabase.com" in database_url:
            try:
                # 使用 urlparse 解析 URL
                parsed = urlparse(database_url)
                
                # 提取项目 ID
                # hostname: cgfdhubkklpyvjgezeeq.pooler.supabase.com
                hostname = parsed.hostname or ""
                project_id = hostname.replace(".pooler.supabase.com", "")
                
                # 新主机名: db.{project_id}.supabase.co
                new_hostname = f"db.{project_id}.supabase.co"
                
                # 新端口: 5432
                new_port = 5432
                
                # 用户名转换: postgres.{project_id} -> postgres
                username = parsed.username or "postgres"
                new_username = username.replace(f"postgres.{project_id}", "postgres")
                
                # 构建新 URL
                new_netloc = f"{new_username}"
                if parsed.password:
                    new_netloc += f":{parsed.password}"
                new_netloc += f"@{new_hostname}:{new_port}"
                
                # 重建 URL
                database_url = urlunparse((
                    parsed.scheme,
                    new_netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment
                ))
                
                print(f"✅ 自动转换连接池器为直连地址（Streamlit Cloud 兼容）")
                print(f"   原始: {database_url[:60]}...")
            except Exception as e:
                print(f"⚠️ URL 转换失败: {e}，使用原始 URL")
    
    return database_url

class Settings(BaseSettings):
    """应用配置"""
    
    # 应用信息
    APP_NAME: str = "WordStyle Pro"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # 数据库
    DATABASE_URL: str = _load_database_url()
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 微信支付
    WECHAT_APP_ID: str = ""
    WECHAT_MCH_ID: str = ""
    WECHAT_API_KEY: str = ""
    WECHAT_NOTIFY_URL: str = ""
    
    # 支付宝
    ALIPAY_APP_ID: str = ""
    ALIPAY_PRIVATE_KEY: str = ""
    ALIPAY_PUBLIC_KEY: str = ""
    ALIPAY_NOTIFY_URL: str = ""
    
    # 文件存储
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 52428800  # 50MB
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:8501,http://localhost:3000"
    
    @property
    def ALLOWED_ORIGINS_LIST(self) -> List[str]:
        """将逗号分隔的字符串转换为列表"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略未在模型中定义的环境变量

# 创建全局配置实例
settings = Settings()
