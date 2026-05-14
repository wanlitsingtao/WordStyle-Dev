# -*- coding: utf-8 -*-
"""
监控和指标API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db

router = APIRouter(tags=["监控"])


@router.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    """
    获取系统指标
    
    返回关键业务指标，用于监控和告警。
    """
    metrics = {}
    
    try:
        # 用户总数
        result = db.execute(text("SELECT COUNT(*) FROM users"))
        metrics['total_users'] = result.scalar() or 0
        
        # 今日活跃用户（今日有转换任务的用户）
        result = db.execute(text(
            "SELECT COUNT(DISTINCT user_id) FROM conversion_tasks "
            "WHERE DATE(created_at) = CURRENT_DATE"
        ))
        metrics['daily_active_users'] = result.scalar() or 0
        
        # 今日转换任务数
        result = db.execute(text(
            "SELECT COUNT(*) FROM conversion_tasks "
            "WHERE DATE(created_at) = CURRENT_DATE"
        ))
        metrics['daily_tasks'] = result.scalar() or 0
        
        # 待处理任务数
        result = db.execute(text(
            "SELECT COUNT(*) FROM conversion_tasks WHERE status = 'PENDING'"
        ))
        metrics['pending_tasks'] = result.scalar() or 0
        
        # 处理中任务数
        result = db.execute(text(
            "SELECT COUNT(*) FROM conversion_tasks WHERE status = 'PROCESSING'"
        ))
        metrics['processing_tasks'] = result.scalar() or 0
        
        # 订单相关统计已移除（项目无充值/订单功能）
        metrics['daily_orders'] = 0
        metrics['daily_revenue'] = 0.0
        metrics['total_orders'] = 0
        metrics['total_revenue'] = 0.0
        
        # 系统配置
        result = db.execute(text(
            "SELECT config_key, config_value FROM system_config"
        ))
        configs = result.fetchall()
        metrics['config'] = {row[0]: row[1] for row in configs}
        
        metrics['status'] = 'ok'
        
    except Exception as e:
        metrics['status'] = 'error'
        metrics['error'] = str(e)
    
    return metrics


@router.get("/metrics/summary")
def get_summary_metrics(db: Session = Depends(get_db)):
    """
    获取简化版指标（用于快速健康检查）
    """
    try:
        # 数据库连接测试
        db.execute(text("SELECT 1"))
        
        # 基本统计
        result = db.execute(text("SELECT COUNT(*) FROM users"))
        total_users = result.scalar() or 0
        
        result = db.execute(text(
            "SELECT COUNT(*) FROM conversion_tasks WHERE status = 'PENDING'"
        ))
        pending_tasks = result.scalar() or 0
        
        return {
            "status": "healthy",
            "total_users": total_users,
            "pending_tasks": pending_tasks,
            "database": "connected"
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "database": "disconnected"
        }
