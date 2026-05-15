# -*- coding: utf-8 -*-
"""
管理员 API 路由 - 系统配置管理
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import SystemConfig, User, ConversionTask
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()

class ConfigUpdate(BaseModel):
    """配置更新请求"""
    config_value: str
    description: Optional[str] = None

class FreeParagraphsConfig(BaseModel):
    """免费段落数配置"""
    free_paragraphs: int
    description: Optional[str] = "新用户首次登录赠送的免费段落数"

@router.get("/config/free-paragraphs")
def get_free_paragraphs_config(db: Session = Depends(get_db)):
    """获取免费段落数配置"""
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == "free_paragraphs_on_first_login"
    ).first()
    
    if not config:
        # 如果不存在，创建默认配置
        config = SystemConfig(
            config_key="free_paragraphs_on_first_login",
            config_value="10000",
            description="新用户首次登录赠送的免费段落数"
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    
    return {
        "config_key": config.config_key,
        "config_value": int(config.config_value),
        "description": config.description,
        "updated_at": config.updated_at
    }

@router.put("/config/free-paragraphs")
def update_free_paragraphs_config(
    config_data: FreeParagraphsConfig,
    db: Session = Depends(get_db)
):
    """
    更新免费段落数配置
    
    Args:
        config_data: 新的配置值
        
    Returns:
        更新后的配置
    """
    if config_data.free_paragraphs < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="免费段落数不能为负数"
        )
    
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == "free_paragraphs_on_first_login"
    ).first()
    
    if not config:
        config = SystemConfig(
            config_key="free_paragraphs_on_first_login",
            config_value=str(config_data.free_paragraphs),
            description=config_data.description or "新用户首次登录赠送的免费段落数"
        )
        db.add(config)
    else:
        config.config_value = str(config_data.free_paragraphs)
        if config_data.description:
            config.description = config_data.description
    
    db.commit()
    db.refresh(config)
    
    return {
        "message": f"免费段落数配置已更新为 {config_data.free_paragraphs} 段",
        "config_key": config.config_key,
        "config_value": int(config.config_value),
        "description": config.description,
        "updated_at": config.updated_at
    }

@router.get("/stats")
def get_system_stats(db: Session = Depends(get_db)):
    """获取系统统计信息"""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    
    # 订单/充值功能已移除
    total_revenue = 0.0
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_revenue": float(total_revenue),
        "message": "系统统计信息"
    }

@router.get("/users")
def get_users_list(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取用户列表"""
    users = db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": db.query(User).count(),
        "users": [
            {
                'user_id': u.id,
                'device_fingerprint': u.device_fingerprint,
                'balance': float(u.balance or 0),
                'paragraphs_remaining': int(u.paragraphs_remaining or 0),
                'paragraphs_used': int(u.total_paragraphs_used or 0),
                'total_converted': int(u.total_converted or 0),
                'is_active': bool(u.is_active),
                'created_at': u.created_at.isoformat() if u.created_at else '',
                'last_login': u.last_login.isoformat() if u.last_login else '',
            }
            for u in users
        ]
    }

@router.post("/users/by-device")
def get_or_create_user_by_device_api(
    device_fingerprint: str,
    user_agent: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    通过设备指纹获取或创建用户
    
    Args:
        device_fingerprint: 设备指纹（32位MD5哈希）
        user_agent: User-Agent字符串（可选，用于日志）
    
    Returns:
        用户信息字典
    """
    from datetime import datetime
    from config import FREE_PARAGRAPHS_DAILY
    import hashlib
    
    try:
        # 1. 优先通过device_fingerprint查询
        user = db.query(User).filter(User.device_fingerprint == device_fingerprint).first()
        
        if user:
            # 用户已存在，更新last_login
            user.last_login = datetime.now()
            db.commit()
            
            logger.info(f"✅ 从数据库恢复用户: {user.id} (device: {device_fingerprint[:8]}...)")
            
            return {
                'success': True,
                'user_id': user.id,
                'is_new': False,
                'paragraphs_remaining': user.paragraphs_remaining,
                'balance': float(user.balance or 0),
                'total_converted': user.total_converted,
                'message': '用户已存在'
            }
        
        # 2. 用户不存在，创建新用户
        # 生成用户ID
        user_id = hashlib.md5(f"wordstyle_device_{device_fingerprint}".encode()).hexdigest()[:12]
        
        # 创建用户记录
        new_user = User(
            id=user_id,
            device_fingerprint=device_fingerprint,
            balance=0.0,
            paragraphs_remaining=FREE_PARAGRAPHS_DAILY,
            total_paragraphs_used=0,
            total_converted=0,
            is_active=True,
            created_at=datetime.now(),
            last_login=datetime.now()
        )
        
        db.add(new_user)
        db.commit()
        
        logger.info(f"✅ 创建新用户: {user_id} (device: {device_fingerprint[:8]}...)")
        
        return {
            'success': True,
            'user_id': user_id,
            'is_new': True,
            'paragraphs_remaining': FREE_PARAGRAPHS_DAILY,
            'balance': 0.0,
            'total_converted': 0,
            'message': '新用户创建成功'
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 获取或创建用户失败: {e}")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

@router.get("/tasks")
def get_tasks_list(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    from app.models import ConversionTask
    
    query = db.query(ConversionTask)
    if status_filter and status_filter != 'ALL':
        query = query.filter(ConversionTask.status == status_filter)
    
    tasks = query.order_by(ConversionTask.created_at.desc()).offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "total": total,
        "tasks": [
            {
                'task_id': t.task_id,
                'user_id': t.user_id,
                'filename': t.filename,
                'file_count': t.file_count,
                'paragraphs': t.paragraphs,
                'cost': float(t.cost or 0),
                'status': t.status,
                'progress': t.progress,
                'created_at': t.created_at.isoformat() if t.created_at else '',
                'completed_at': t.completed_at.isoformat() if t.completed_at else '',
                'error_message': t.error_message,
            }
            for t in tasks
        ]
    }

@router.get("/task-stats")
def get_task_statistics(db: Session = Depends(get_db)):
    """获取任务统计信息"""
    total = db.query(ConversionTask).count()
    completed = db.query(ConversionTask).filter(
        ConversionTask.status == 'COMPLETED'
    ).count()
    processing = db.query(ConversionTask).filter(
        ConversionTask.status == 'PROCESSING'
    ).count()
    pending = db.query(ConversionTask).filter(
        ConversionTask.status == 'PENDING'
    ).count()
    failed = db.query(ConversionTask).filter(
        ConversionTask.status == 'FAILED'
    ).count()
    
    return {
        'total_tasks': total,
        'completed_tasks': completed,
        'processing_tasks': processing,
        'pending_tasks': pending,
        'failed_tasks': failed,
    }

@router.post("/tasks")
def create_task_api(task_data: dict, db: Session = Depends(get_db)):
    """创建任务（供 API 模式调用）"""
    task = ConversionTask(
        task_id=task_data['task_id'],
        user_id=task_data['user_id'],
        filename=task_data.get('filename', ''),
        paragraphs=task_data.get('paragraphs', 0),
        cost=task_data.get('cost', 0.0),
        status='PENDING',
        progress=0
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return {
        'success': True,
        'task_id': str(task.id),
        'message': '任务已创建'
    }

@router.put("/tasks/{task_id}")
def update_task_status_api(task_id: str, status_data: dict, db: Session = Depends(get_db)):
    """更新任务状态（供 API 模式调用）"""
    task = db.query(ConversionTask).filter(ConversionTask.task_id == task_id).first()
    if not task:
        return {'success': False, 'error': '任务不存在'}
    
    task.status = status_data.get('status', task.status)
    if 'progress' in status_data:
        task.progress = status_data['progress']
    if 'error_message' in status_data:
        task.error_message = status_data['error_message']
    if task.status == 'COMPLETED':
        task.completed_at = datetime.now()
    
    db.commit()
    return {'success': True, 'message': '任务状态已更新'}

# ==================== 用户数据写入 API ====================

@router.post("/users/{user_id}")
def create_or_update_user(user_id: str, user_data: dict, db: Session = Depends(get_db)):
    """创建或更新用户数据（供 API 模式调用）"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if user:
        # 更新现有用户
        user.balance = user_data.get('balance', user.balance)
        user.paragraphs_remaining = user_data.get('paragraphs_remaining', user.paragraphs_remaining)
        user.total_paragraphs_used = user_data.get('total_paragraphs_used', user.total_paragraphs_used)
        user.total_converted = user_data.get('total_converted', user.total_converted)
        user.last_login = datetime.now()
    else:
        # 创建新用户
        user = User(
            id=user_id,
            balance=user_data.get('balance', 0.0),
            paragraphs_remaining=user_data.get('paragraphs_remaining', 0),
            total_paragraphs_used=user_data.get('total_paragraphs_used', 0),
            total_converted=user_data.get('total_converted', 0),
            is_active=True,
            last_login=datetime.now(),
        )
        db.add(user)
    
    db.commit()
    db.refresh(user)
    
    return {
        'success': True,
        'user_id': str(user.id),
        'message': '用户数据已保存'
    }

@router.post("/users/{user_id}/claim-free")
def claim_free_paragraphs(user_id: str, db: Session = Depends(get_db)):
    """领取免费段落（供 API 模式调用）- 每日只领取一次"""
    from config import FREE_PARAGRAPHS_DAILY
    from datetime import datetime, date
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {'success': False, 'error': '用户不存在'}
    
    today = date.today()
    
    # 检查今日是否已领取
    if user.last_claim_date:
        last_claim = user.last_claim_date.date() if hasattr(user.last_claim_date, 'date') else user.last_claim_date
        if last_claim == today:
            # 今日已领取，不再重复发放
            return {
                'success': True,
                'paragraphs': 0,
                'message': '今日已领取过免费额度'
            }
    
    # 今日首次领取：重置为免费额度（不累计）
    user.paragraphs_remaining = FREE_PARAGRAPHS_DAILY
    user.last_claim_date = datetime.now()
    db.commit()
    
    return {
        'success': True,
        'paragraphs': FREE_PARAGRAPHS_DAILY,
        'message': f'已领取 {FREE_PARAGRAPHS_DAILY} 个免费段落'
    }

@router.post("/users/{user_id}/deduct")
def deduct_paragraphs(user_id: str, paragraphs: int, db: Session = Depends(get_db)):
    """扣除段落（供 API 模式调用）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {'success': False, 'error': '用户不存在'}
    
    if user.paragraphs_remaining < paragraphs:
        return {'success': False, 'error': '段落数不足'}
    
    user.paragraphs_remaining -= paragraphs
    user.total_paragraphs_used += paragraphs
    db.commit()
    
    return {
        'success': True,
        'remaining': user.paragraphs_remaining,
        'message': f'已扣除 {paragraphs} 个段落'
    }
