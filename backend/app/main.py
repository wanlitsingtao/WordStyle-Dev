# -*- coding: utf-8 -*-
"""
FastAPI 主应用
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import admin, feedback, comments, monitoring, tasks  # ✅ 添加comments和tasks导入
# 已移除的路由：auth, wechat_auth, conversions, users（这些功能未实现或与业务需求不符）
# 注意：users.py依赖认证系统，暂不可用
import logging

logger = logging.getLogger(__name__)


def run_migrations():
    """
    运行数据库迁移（Alembic）
    
    注意：此函数会在应用启动时自动执行，确保数据库结构与代码模型同步。
    如果迁移失败，应用仍会启动，但会在日志中记录错误。
    """
    try:
        from alembic.config import Config
        from alembic import command
        import os
        
        logger.info("正在检查数据库迁移...")
        alembic_cfg = Config("alembic.ini")
        
        # 从环境变量读取 DATABASE_URL
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            # 转义 % 字符，避免 ConfigParser 插值问题
            escaped_url = database_url.replace('%', '%%')
            alembic_cfg.set_main_option('sqlalchemy.url', escaped_url)
            logger.info("✅ Alembic 使用环境变量 DATABASE_URL")
        
        # ✅ 修复：直接执行 upgrade，不使用 stamp
        # stamp 会将数据库标记为最新版本，导致 upgrade 跳过所有迁移
        # 如果有多 head 冲突，Alembic 会抛出明确错误，需要手动解决
        logger.info("🔄 执行数据库迁移...")
        command.upgrade(alembic_cfg, "head")
        logger.info("✅ 数据库迁移完成")
        
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}")
        logger.warning("应用将继续启动，但请检查数据库状态")
        # 不抛出异常，允许应用继续启动

def create_application() -> FastAPI:
    """创建 FastAPI 应用实例"""
    
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="文档转换平台 API",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # 配置 CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS_LIST,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    # application.include_router(users.router, prefix="/api/users", tags=["用户"])  # 暂不可用 - 依赖认证系统
    application.include_router(admin.router, prefix="/api/admin", tags=["管理员"])
    application.include_router(feedback.router, prefix="/api/feedback", tags=["用户反馈"])
    application.include_router(comments.router, prefix="/api/comments", tags=["评论"])  # ✅ 新增：评论API
    application.include_router(tasks.router, prefix="/api/conversion-tasks", tags=["转换任务"])  # ✅ 新增：转换任务API
    application.include_router(monitoring.router, prefix="/monitoring", tags=["监控"])
    
    # 健康检查（同时支持 GET 和 POST，兼容 UptimeRobot 只能发送 POST 的限制）
    @application.get("/health")
    @application.post("/health")
    def health_check():
        return {"status": "healthy"}
    
    @application.get("/")
    def root():
        return {
            "message": f"{settings.APP_NAME} API",
            "version": settings.APP_VERSION,
            "docs": "/docs"
        }
    
    return application

# 创建应用实例
app = create_application()

# 注册启动事件 - 自动运行数据库迁移
@app.on_event("startup")
def startup_event():
    """应用启动时执行的任务"""
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    run_migrations()
