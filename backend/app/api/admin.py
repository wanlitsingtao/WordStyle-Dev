# -*- coding: utf-8 -*-
"""
管理员 API 路由 - 系统配置管理
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy import case, func, update as sa_update
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import SystemConfig, User, ConversionTask
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== [IDENTITY v2] 历史账号认领 ====================
# 说明：后端（backend/）是独立部署单元，不引入仓库根目录的 identity.py，
# 因此这里内联同一套最小逻辑，与 data_manager._claim_legacy_identity 保持一致。
# 背景：原"设备指纹"= md5(User-Agent)，导致同版本浏览器的不同用户共用同一账号。
# v2 改用浏览器持久化 cookie 派生指纹，老账号通过"改写身份键"完成一次认领。
_UNTRUSTED_V1_FINGERPRINTS = frozenset(
    __import__("hashlib").md5(x.encode("utf-8")).hexdigest()
    for x in ("", "unknown", "none", "null", "fallback")
)


def _is_claimable_legacy_fingerprint(fingerprint) -> bool:
    """仅放行形态合法且不属于"多人共用桶"的 v1 指纹。"""
    import re
    if not isinstance(fingerprint, str):
        return False
    fp = fingerprint.strip().lower()
    if not re.match(r"^[0-9a-f]{32}$", fp):
        return False
    return fp not in _UNTRUSTED_V1_FINGERPRINTS


def _claim_legacy_identity(db: Session, v2_fingerprint: str, legacy_fingerprint: str):
    """把历史（v1）账号的 device_fingerprint 原子改写为 v2 指纹。

    不新建表/列、不复制数据；改写后 v1 指纹不复存在 → 恰好一次。
    返回被认领的 User；未命中或不满足条件返回 None（调用方照常建新号）。
    """
    if not v2_fingerprint or v2_fingerprint == legacy_fingerprint:
        return None
    if not _is_claimable_legacy_fingerprint(legacy_fingerprint):
        return None
    try:
        updated = db.query(User).filter(
            User.device_fingerprint == legacy_fingerprint
        ).update(
            {User.device_fingerprint: v2_fingerprint, User.last_login: datetime.now()},
            synchronize_session=False,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"[IDENTITY] 认领历史账号失败（不影响建号）: {e}")
        return None
    if updated != 1:
        return None
    return db.query(User).filter(User.device_fingerprint == v2_fingerprint).first()


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
    
    # 总转换次数
    total_conversions = db.query(User).filter(
        User.total_converted > 0
    ).count()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_conversions": total_conversions,
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
                'username': u.username or '',  # [NEW] 管理后台用户列表展示用户名（未绑定时为空字符串）
                'device_fingerprint': u.device_fingerprint,
                'balance': float(u.balance or 0),
                'paragraphs_remaining': int(u.paragraphs_remaining or 0),
                # [FIX 2026-09-15] 统一键名为 total_paragraphs_used（与数据库模型、本文件其他端点一致）；
                # 原键名 paragraphs_used 与数据库字段名不符，导致管理后台「已用段落」列读取不到值
                'total_paragraphs_used': int(u.total_paragraphs_used or 0),
                'total_converted': int(u.total_converted or 0),
                'is_active': bool(u.is_active),
                'created_at': u.created_at.isoformat() if u.created_at else '',
                'last_login': u.last_login.isoformat() if u.last_login else '',
            }
            for u in users
        ]
    }

@router.get("/users/{user_id}")
def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    通过用户ID获取用户信息（包含转换历史）
    
    Args:
        user_id: 用户ID
    
    Returns:
        用户信息字典，包含conversion_history
    """
    try:
        from app.models import ConversionTask
        
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")
        
        # [OK] 修复：从 conversion_tasks 表实时查询用户的转换记录
        tasks = db.query(ConversionTask).filter(
            ConversionTask.user_id == user_id,
            ConversionTask.status == 'COMPLETED'  # 只返回已完成的任务
        ).order_by(ConversionTask.created_at.desc()).all()
        
        # 构建转换历史列表
        conversion_history = []
        for task in tasks:
            conversion_history.append({
                'time': task.completed_at.strftime('%Y-%m-%d %H:%M:%S') if task.completed_at else task.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'files': 1,  # 每个任务对应一个文件
                'success': 1 if task.status == 'COMPLETED' else 0,
                'failed': 0 if task.status == 'COMPLETED' else 1,
                'paragraphs_charged': int(task.paragraphs or 0),  # [OK] 从数据库读取段落数
                'mode': 'foreground'
            })
        
        return {
            'success': True,
            'user_id': user.id,
            'device_fingerprint': user.device_fingerprint,
            'balance': float(user.balance or 0),
            'paragraphs_remaining': int(user.paragraphs_remaining or 0),
            'total_converted': int(user.total_converted or 0),
            'total_paragraphs_used': int(user.total_paragraphs_used or 0),
            'conversion_history': conversion_history,  # [OK] 使用实时查询的数据
            'is_active': bool(user.is_active),
            'created_at': user.created_at.isoformat() if user.created_at else '',
            'last_login': user.last_login.isoformat() if user.last_login else '',
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] 获取用户信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

@router.post("/users/by-device")
def get_or_create_user_by_device_api(
    device_fingerprint: str = Body(..., embed=False),
    user_agent: Optional[str] = Body(None),
    legacy_fingerprint: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    request = None  # [OK] 新增：获取请求对象以记录IP
):
    """
    通过设备指纹获取或创建用户
    
    Args:
        device_fingerprint: 身份指纹（32位MD5哈希）。
            [IDENTITY v2] = md5("ws2|" + 浏览器持久化ID)
        user_agent: User-Agent字符串（可选，用于日志）
        legacy_fingerprint: [IDENTITY v2] 可选。v1（= md5(User-Agent)）指纹，
            仅用于"恰好一次"认领历史账号，不参与身份判定。
    
    Returns:
        用户信息字典
    """
    from datetime import datetime
    from app.config import FREE_PARAGRAPHS_DAILY as FALLBACK_FREE_PARAGRAPHS
    import hashlib
    from fastapi import Request
    
    try:
        # [FIX] Bug#010: 优先从config表读取动态配置，用于新用户初始额度
        config_record = db.query(SystemConfig).filter(
            SystemConfig.config_key == "free_paragraphs_daily"
        ).first()
        new_user_paragraphs = int(config_record.config_value) if config_record else FALLBACK_FREE_PARAGRAPHS
        
        # [OK] 新增：获取客户端IP地址
        client_ip = "unknown"
        if request:
            client_ip = request.client.host if request.client else "unknown"
        
        # [OK] 新增：记录API调用详情
        logger.info(f"[SEARCH] /users/by-device API被调用 - IP: {client_ip}, Device: {device_fingerprint[:16]}..., UA: {user_agent[:50] if user_agent else 'N/A'}...")
        
        # 1. 优先通过device_fingerprint查询
        user = db.query(User).filter(User.device_fingerprint == device_fingerprint).first()

        # 1.5) [IDENTITY v2] 未命中 v2 指纹 → 尝试"恰好一次"认领该浏览器的历史(v1)账号。
        #      只改写身份键，user_id / 额度 / 历史 / 样式映射全部原地保留，不复制数据。
        #      改写后 v1 指纹在库中不复存在 → 天然恰好一次，也天然终结了
        #      "同版本浏览器多人共用一个账号"的问题（先到者认领，其余人各建新号）。
        if not user and legacy_fingerprint:
            user = _claim_legacy_identity(db, device_fingerprint, legacy_fingerprint)
            if user:
                logger.info(f"[IDENTITY] 已认领历史账号 → user_id={user.id} "
                            f"(v1={str(legacy_fingerprint)[:12]}… → v2={device_fingerprint[:12]}…)")
        
        if user:
            # 用户已存在，更新last_login
            user.last_login = datetime.now()
            db.commit()
            
            logger.info(f"[OK] 从数据库恢复用户: {user.id} (device: {device_fingerprint[:8]}..., IP: {client_ip})")
            
            return {
                'success': True,
                'user_id': user.id,
                'is_new': False,
                'paragraphs_remaining': user.paragraphs_remaining,
                'balance': float(user.balance or 0),
                'total_converted': user.total_converted,
                'total_paragraphs_used': user.total_paragraphs_used,  # [OK] 修复：添加累计使用段落数字段
                'conversion_history': user.conversion_history or [],  # [OK] 修复：添加转换历史字段
                'style_mappings': user.style_mappings or {},
                'message': '用户已存在'
            }
        
        # 2. 用户不存在，创建新用户
        # 生成用户ID
        # [IDENTITY v2] 改为随机生成，不再用 md5("wordstyle_device_"+指纹)[:12]：
        # 旧写法使任何知道某人 UA 的人都能推算其 user_id，且让 ID 可被外部预测。
        import uuid as _uuid
        user_id = _uuid.uuid4().hex[:12]
        
        # [OK] 新增：检测是否为测试用户
        is_test_user = device_fingerprint.startswith('test_') or (user_agent and 'test' in user_agent.lower())
        if is_test_user:
            logger.warning(f"[WARN] 检测到测试用户创建请求 - Device: {device_fingerprint}, IP: {client_ip}")
        
        # 创建用户记录
        new_user = User(
            id=user_id,
            device_fingerprint=device_fingerprint,
            balance=0.0,
            paragraphs_remaining=new_user_paragraphs,
            total_paragraphs_used=0,
            total_converted=0,
            is_active=True,
            created_at=datetime.now(),
            last_login=datetime.now()
        )
        
        db.add(new_user)
        db.commit()
        
        logger.info(f"[OK] 创建新用户: {user_id} (device: {device_fingerprint[:8]}..., IP: {client_ip}, Test: {is_test_user})")
        
        return {
            'success': True,
            'user_id': user_id,
            'is_new': True,
            'paragraphs_remaining': new_user_paragraphs,
            'balance': 0.0,
            'total_converted': 0,
            'total_paragraphs_used': 0,
            'conversion_history': [],  # [OK] 修复：新用户初始化转换历史为空列表
            'style_mappings': {},
            'message': '新用户创建成功'
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"[ERROR] 获取或创建用户失败: {e}")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

@router.get("/tasks")
def get_tasks_list(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    user_id: Optional[str] = None,  # [OK] 新增：支持按用户ID过滤
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    from app.models import ConversionTask
    
    query = db.query(ConversionTask)
    if status_filter and status_filter != 'ALL':
        query = query.filter(ConversionTask.status == status_filter)
    if user_id:  # [OK] 新增：按用户ID过滤
        query = query.filter(ConversionTask.user_id == user_id)
    
    tasks = query.order_by(ConversionTask.created_at.desc()).offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "total": total,
        "tasks": [
            {
                'id': str(t.id),
                'user_id': t.user_id,
                'source_file': t.source_file or '',
                'template_file': t.template_file or '',
                'converted_file': t.converted_file or '',
                'status': t.status,
                'progress': t.progress,
                'paragraphs': int(t.paragraphs or 0),  # [OK] 新增：段落数
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
    """创建任务（供 API 模式调用）- [OK] 修复：支持直接创建已完成的任务"""
    import uuid
    from app.models import ConversionTask
    from datetime import datetime
    
    # [OK] 修复：根据传入的状态设置completed_at
    status = task_data.get('status', 'pending')
    completed_at = datetime.now() if status in ['COMPLETED', 'FAILED'] else None
    
    task = ConversionTask(
        user_id=task_data['user_id'],
        source_file=task_data.get('source_file', ''),
        template_file=task_data.get('template_file', ''),
        status=status,
        progress=task_data.get('progress', 0),
        paragraphs=task_data.get('paragraphs', 0),  # [OK] 新增：段落数
        error_message=task_data.get('error_message'),
        completed_at=completed_at,
        created_at=datetime.now()
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
    """更新任务状态（供 API 模式调用）- [OK] 修复：使用正确的字段名id"""
    from uuid import UUID
    
    # [OK] 修复：将字符串task_id转换为UUID进行查询
    try:
        task_uuid = UUID(task_id)
        task = db.query(ConversionTask).filter(ConversionTask.id == task_uuid).first()
    except ValueError:
        return {'success': False, 'error': '无效的任务ID格式'}
    
    if not task:
        return {'success': False, 'error': '任务不存在'}
    
    task.status = status_data.get('status', task.status)
    if 'progress' in status_data:
        task.progress = status_data['progress']
    if 'error_message' in status_data:
        task.error_message = status_data['error_message']
    if 'source_file' in status_data:
        task.source_file = status_data['source_file']
    if 'template_file' in status_data:
        task.template_file = status_data['template_file']
    if 'converted_file' in status_data:
        task.converted_file = status_data['converted_file']
    if task.status in ['COMPLETED', 'FAILED']:
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
        user.conversion_history = user_data.get('conversion_history', user.conversion_history)  # [OK] 修复：保存转换历史
        user.style_mappings = user_data.get('style_mappings', user.style_mappings)
        user.last_login = datetime.now()
    else:
        # 创建新用户
        user = User(
            id=user_id,
            balance=user_data.get('balance', 0.0),
            paragraphs_remaining=user_data.get('paragraphs_remaining', 0),
            total_paragraphs_used=user_data.get('total_paragraphs_used', 0),
            total_converted=user_data.get('total_converted', 0),
            conversion_history=user_data.get('conversion_history', []),  # [OK] 修复：保存转换历史
            style_mappings=user_data.get('style_mappings', {}),
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
    from app.config import FREE_PARAGRAPHS_DAILY as FALLBACK_FREE_PARAGRAPHS
    from datetime import datetime, date
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {'success': False, 'error': '用户不存在'}
    
    # 检查今天是否已经领取过
    today = date.today()
    if user.last_claim_date:
        last_claim_date = user.last_claim_date.date() if hasattr(user.last_claim_date, 'date') else user.last_claim_date
        if last_claim_date == today:
            # 今天已经领取过，返回当前剩余额度
            return {
                'success': True,
                'paragraphs': 0,  # 返回0表示没有新领取
                'message': '今日已领取过免费额度',
                'already_claimed': True
            }
    
    # [FIX] Bug#010: 优先从config表读取动态配置，若不存在则回退到硬编码默认值
    config_record = db.query(SystemConfig).filter(
        SystemConfig.config_key == "free_paragraphs_daily"
    ).first()
    free_paragraphs = int(config_record.config_value) if config_record else FALLBACK_FREE_PARAGRAPHS
    
    # 设置免费段落数并记录领取日期
    user.paragraphs_remaining = free_paragraphs
    user.last_claim_date = datetime.now()
    db.commit()
    
    return {
        'success': True,
        'paragraphs': free_paragraphs,
        'message': f'已领取 {free_paragraphs} 个免费段落',
        'already_claimed': False
    }

@router.post("/users/{user_id}/deduct")
def deduct_paragraphs(user_id: str, paragraphs: int, db: Session = Depends(get_db)):
    """扣除段落（供 API 模式调用）

    [FIX 计数非原子] 改为数据库侧原子扣减：把"校验 + 扣减 + 累加"放进同一条 UPDATE，
    避免原先"先 SELECT 再改属性再 commit"在并发时读到同一个旧值而互相覆盖。
    """
    if paragraphs is None or paragraphs < 0:
        return {'success': False, 'error': '段落数非法'}

    result = db.execute(
        sa_update(User)
        .where(User.id == user_id, func.coalesce(User.paragraphs_remaining, 0) >= paragraphs)
        .values({
            User.paragraphs_remaining: User.paragraphs_remaining - paragraphs,
            User.total_paragraphs_used: func.coalesce(User.total_paragraphs_used, 0) + paragraphs,
        })
    )
    db.commit()

    if result.rowcount != 1:
        exists = db.query(User.id).filter(User.id == user_id).first()
        return {'success': False, 'error': '用户不存在' if not exists else '段落数不足'}

    remaining = db.query(User.paragraphs_remaining).filter(User.id == user_id).scalar()
    return {
        'success': True,
        'remaining': int(remaining or 0),
        'message': f'已扣除 {paragraphs} 个段落'
    }


@router.post("/users/{user_id}/apply-conversion")
def apply_conversion_result_api(user_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    """转换完成后一次性落账（供 API 模式调用）。

    [FIX 计数非原子] 替代原先"内存改 + save_user_data 整行覆盖"的两段写：
    计数字段由一条 UPDATE 在数据库侧完成，conversion_history 只追加该列。
    请求体：{"paragraphs": int, "converted": int, "record": dict|None}
    """
    try:
        paragraphs = max(0, int(payload.get('paragraphs') or 0))
        converted = max(0, int(payload.get('converted') or 0))
        record = payload.get('record')

        if not db.query(User.id).filter(User.id == user_id).first():
            return {'success': False, 'error': '用户不存在'}

        db.execute(
            sa_update(User)
            .where(User.id == user_id)
            .values({
                # 额度不足时归零，不允许出现负数（与客户端原有语义一致）
                User.paragraphs_remaining: case(
                    (func.coalesce(User.paragraphs_remaining, 0) >= paragraphs,
                     func.coalesce(User.paragraphs_remaining, 0) - paragraphs),
                    else_=0,
                ),
                User.total_paragraphs_used: func.coalesce(User.total_paragraphs_used, 0) + paragraphs,
                User.total_converted: func.coalesce(User.total_converted, 0) + converted,
                User.updated_at: datetime.now(),
            })
        )

        if record:
            db.flush()
            row = db.query(User).filter(User.id == user_id).first()
            hist = row.conversion_history
            if not isinstance(hist, list):
                hist = []
            hist.append(record)
            row.conversion_history = hist

        db.commit()
        db.expire_all()
        fresh = db.query(User).filter(User.id == user_id).first()

        return {
            'success': True,
            'user_id': fresh.id,
            'balance': float(fresh.balance or 0),
            'paragraphs_remaining': int(fresh.paragraphs_remaining or 0),
            'total_paragraphs_used': int(fresh.total_paragraphs_used or 0),
            'total_converted': int(fresh.total_converted or 0),
            'conversion_history': fresh.conversion_history if isinstance(fresh.conversion_history, list) else [],
            'created_at': fresh.created_at.isoformat() if fresh.created_at else '',
            'last_login': fresh.last_login.isoformat() if fresh.last_login else '',
        }
    except Exception as e:
        db.rollback()
        logger.error(f"[FIX] apply-conversion 失败: {e}")
        return {'success': False, 'error': str(e)}


# ==================== 文件管理 API ====================

@router.get("/files")
def get_files_list(page: int = 1, page_size: int = 50):
    """
    获取文件列表（支持分页）
    
    Args:
        page: 页码（从1开始）
        page_size: 每页数量
    
    Returns:
        包含文件列表和分页信息的字典
    """
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from file_manager import get_file_manager
        
        fm = get_file_manager()
        return fm.get_file_list(page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"获取文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.post("/files/delete")
def delete_files_endpoint(file_ids: list = Body(...)):
    """
    删除指定的文件
    
    Args:
        file_ids: 文件ID列表
    
    Returns:
        删除统计信息
    """
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from file_manager import get_file_manager
        
        fm = get_file_manager()
        return fm.delete_files(file_ids)
    except Exception as e:
        logger.error(f"删除文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")


@router.get("/files/stats")
def get_storage_statistics():
    """
    获取存储空间统计信息
    
    Returns:
        存储统计信息
    """
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from file_manager import get_file_manager
        
        fm = get_file_manager()
        return fm.get_storage_stats()
    except Exception as e:
        logger.error(f"获取存储统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取存储统计失败: {str(e)}")

# ==================== 系统配置管理 API ====================

class SystemConfigItem(BaseModel):
    """单个配置项"""
    config_key: str
    config_value: str
    description: Optional[str] = None

class SystemConfigBatchUpdate(BaseModel):
    """批量更新配置"""
    configs: dict

@router.get("/configs")
def get_all_configs(db: Session = Depends(get_db)):
    """
    获取所有系统配置
    
    Returns:
        配置列表
    """
    try:
        configs = db.query(SystemConfig).all()
        return {
            "success": True,
            "data": [
                {
                    "config_key": c.config_key,
                    "config_value": c.config_value,
                    "description": c.description,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None
                }
                for c in configs
            ]
        }
    except Exception as e:
        logger.error(f"获取配置列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置列表失败: {str(e)}")

@router.get("/config/{key}")
def get_config(key: str, db: Session = Depends(get_db)):
    """
    获取单个配置项
    
    Args:
        key: 配置键
        
    Returns:
        配置项信息
    """
    try:
        config = db.query(SystemConfig).filter(
            SystemConfig.config_key == key
        ).first()
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"配置项 '{key}' 不存在"
            )
        
        return {
            "success": True,
            "data": {
                "config_key": config.config_key,
                "config_value": config.config_value,
                "description": config.description,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")

@router.put("/config/{key}")
def update_config(key: str, config_data: ConfigUpdate, db: Session = Depends(get_db)):
    """
    更新单个配置项
    
    Args:
        key: 配置键
        config_data: 新的配置值
        
    Returns:
        更新后的配置
    """
    try:
        # 验证配置值的合法性
        _validate_config_value(key, config_data.config_value)
        
        config = db.query(SystemConfig).filter(
            SystemConfig.config_key == key
        ).first()
        
        if not config:
            # 如果不存在，创建新配置
            config = SystemConfig(
                config_key=key,
                config_value=config_data.config_value,
                description=config_data.description or f"配置项: {key}"
            )
            db.add(config)
        else:
            # 更新现有配置
            old_value = config.config_value
            config.config_value = config_data.config_value
            if config_data.description:
                config.description = config_data.description
            
            logger.info(f"配置更新: {key} = {old_value} -> {config_data.config_value}")
        
        db.commit()
        db.refresh(config)
        
        return {
            "success": True,
            "message": f"配置 '{key}' 更新成功",
            "data": {
                "config_key": config.config_key,
                "config_value": config.config_value,
                "description": config.description,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None
            }
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")

@router.post("/configs/batch")
def batch_update_configs(batch_data: SystemConfigBatchUpdate, db: Session = Depends(get_db)):
    """
    批量更新配置
    
    Args:
        batch_data: 配置字典 {key: value}
        
    Returns:
        更新结果
    """
    try:
        updated_count = 0
        errors = []
        
        for key, value in batch_data.configs.items():
            try:
                # 验证配置值
                _validate_config_value(key, str(value))
                
                config = db.query(SystemConfig).filter(
                    SystemConfig.config_key == key
                ).first()
                
                if not config:
                    config = SystemConfig(
                        config_key=key,
                        config_value=str(value),
                        description=f"配置项: {key}"
                    )
                    db.add(config)
                else:
                    config.config_value = str(value)
                
                updated_count += 1
                logger.info(f"批量配置更新: {key} = {value}")
                
            except ValueError as e:
                errors.append({"key": key, "error": str(e)})
        
        db.commit()
        
        return {
            "success": True,
            "message": f"成功更新 {updated_count} 个配置",
            "updated_count": updated_count,
            "errors": errors
        }
    except Exception as e:
        db.rollback()
        logger.error(f"批量更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量更新配置失败: {str(e)}")

@router.post("/config/init-defaults")
def init_default_configs(db: Session = Depends(get_db)):
    """
    初始化默认配置
    
    Returns:
        初始化结果
    """
    try:
        default_configs = [
            {
                "config_key": "paragraph_price",
                "config_value": "0.001",
                "description": "每个段落的价格（元）"
            },
            {
                "config_key": "min_recharge",
                "config_value": "1.0",
                "description": "最低充值金额（元）"
            },
            {
                "config_key": "free_paragraphs_daily",
                "config_value": "10000",
                "description": "每日免费段落数"
            },
            {
                "config_key": "admin_contact",
                "config_value": "微信号：your_wechat_id",
                "description": "管理员联系方式"
            },
            {
                "config_key": "max_file_size_mb",
                "config_value": "50",
                "description": "最大文件大小（MB）"
            },
            {
                "config_key": "task_expiry_days",
                "config_value": "7",
                "description": "转换任务保留天数"
            },
        ]
        
        created_count = 0
        for config_data in default_configs:
            existing = db.query(SystemConfig).filter(
                SystemConfig.config_key == config_data["config_key"]
            ).first()
            
            if not existing:
                config = SystemConfig(**config_data)
                db.add(config)
                created_count += 1
        
        db.commit()
        
        return {
            "success": True,
            "message": f"成功初始化 {created_count} 个默认配置",
            "created_count": created_count
        }
    except Exception as e:
        db.rollback()
        logger.error(f"初始化默认配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"初始化默认配置失败: {str(e)}")

def _validate_config_value(key: str, value: str):
    """
    验证配置值的合法性
    
    Args:
        key: 配置键
        value: 配置值
        
    Raises:
        ValueError: 配置值不合法
    """
    validators = {
        'paragraph_price': lambda v: float(v) > 0,
        'min_recharge': lambda v: float(v) > 0,
        'free_paragraphs_daily': lambda v: int(v) >= 0,
        'admin_contact': lambda v: len(v) > 0 and len(v) <= 500,
        'max_file_size_mb': lambda v: int(v) > 0 and int(v) <= 500,
        'task_expiry_days': lambda v: int(v) > 0 and int(v) <= 365,
    }
    
    validator = validators.get(key)
    if validator:
        try:
            if not validator(value):
                raise ValueError(f"配置值 '{value}' 不合法")
        except (ValueError, TypeError):
            raise ValueError(f"配置值 '{value}' 格式错误")
