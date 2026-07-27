# -*- coding: utf-8 -*-
"""
账号绑定/登录 API 路由（无需认证，公开接口）

支持：
  - 绑定设备指纹到用户名/密码
  - 使用用户名/密码登录，返回用户 ID
  - 检查用户名是否可用
  - 查询设备指纹绑定的账号
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
import hashlib

from app.core.database import get_db
from app.models import User
from app.schemas import (
    AccountBindRequest, AccountLoginRequest,
    AccountBindResponse, AccountLoginResponse,
    CheckUsernameResponse, BoundAccountResponse
)

router = APIRouter()


def _hash_password(password: str) -> str:
    """SHA-256 哈希"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


@router.post("/bind", response_model=AccountBindResponse)
def bind_account(req: AccountBindRequest, db: Session = Depends(get_db)):
    """
    将设备指纹绑定到用户名/密码。

    规则：
      - 一个设备指纹只能绑定一个用户名
      - 用户名不区分大小写、不可重复
    """
    device_fp = req.device_fingerprint.strip()
    username = req.username.strip()
    username_lower = username.lower()
    password = req.password

    if not device_fp or not username or not password:
        return AccountBindResponse(success=False, message="设备指纹、用户名和密码不能为空")

    # 检查设备是否已绑定
    existing_device = db.query(User).filter(
        User.device_fingerprint == device_fp
    ).first()
    if existing_device and existing_device.username and existing_device.username.strip():
        return AccountBindResponse(
            success=False,
            message=f"该设备已绑定账号「{existing_device.username}」，一个设备只能绑定一个账号"
        )

    # 检查用户名是否已存在（不区分大小写）
    dup = db.query(User).filter(
        func.lower(User.username) == username_lower
    ).first()
    if dup:
        return AccountBindResponse(
            success=False,
            message=f"用户名「{username}」已被使用，请更换"
        )

    try:
        # 更新或创建用户
        if existing_device:
            existing_device.username = username
            existing_device.password_hash = _hash_password(password)
            existing_device.updated_at = datetime.now()
        else:
            # 为新设备创建用户记录
            import hashlib as hl
            user_id = hl.md5(f"wordstyle_device_{device_fp}".encode()).hexdigest()[:12]
            new_user = User(
                id=user_id,
                device_fingerprint=device_fp,
                username=username,
                password_hash=_hash_password(password),
                paragraphs_remaining=10000,
                is_active=True,
                created_at=datetime.now(),
                last_login=datetime.now(),
            )
            db.add(new_user)

        db.commit()
        return AccountBindResponse(
            success=True,
            message=f"账号「{username}」绑定成功！"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"绑定失败: {str(e)}")


@router.post("/login", response_model=AccountLoginResponse)
def login_account(req: AccountLoginRequest, db: Session = Depends(get_db)):
    """
    使用用户名和密码登录。

    Returns:
        user_id: 登录成功返回用户 ID，供前端切换身份使用
    """
    username_lower = req.username.strip().lower()
    password = req.password

    if not username_lower or not password:
        return AccountLoginResponse(success=False, message="用户名和密码不能为空", user_id=None)

    user = db.query(User).filter(
        func.lower(User.username) == username_lower
    ).first()

    if not user:
        return AccountLoginResponse(success=False, message="用户名或密码错误", user_id=None)

    stored_hash = getattr(user, 'password_hash', None)
    if not stored_hash or stored_hash != _hash_password(password):
        return AccountLoginResponse(success=False, message="用户名或密码错误", user_id=None)

    # 更新最后登录时间
    user.last_login = datetime.now()
    db.commit()

    return AccountLoginResponse(
        success=True,
        message=f"登录成功，欢迎 {user.username}！",
        user_id=user.id
    )


@router.get("/check-username/{username}", response_model=CheckUsernameResponse)
def check_username(username: str, db: Session = Depends(get_db)):
    """检查用户名是否可用（不区分大小写）"""
    username_lower = username.strip().lower()
    if not username_lower:
        return CheckUsernameResponse(available=False, message="用户名不能为空")

    exists = db.query(User).filter(
        func.lower(User.username) == username_lower
    ).count() > 0

    if exists:
        return CheckUsernameResponse(available=False, message=f"用户名「{username}」已被使用")
    return CheckUsernameResponse(available=True, message=f"用户名「{username}」可用")


@router.get("/bound-account/{device_fp}", response_model=BoundAccountResponse)
def get_bound_account(device_fp: str, db: Session = Depends(get_db)):
    """查询设备指纹绑定的账号"""
    if not device_fp or device_fp == "null":
        return BoundAccountResponse(bound=False, username=None, created_at=None)

    user = db.query(User).filter(User.device_fingerprint == device_fp).first()
    if not user or not user.username:
        return BoundAccountResponse(bound=False, username=None, created_at=None)

    return BoundAccountResponse(
        bound=True,
        username=user.username,
        created_at=user.created_at.isoformat() if user.created_at else None
    )


@router.get("/user-id/{username_lower}")
def get_user_id_by_username(username_lower: str, db: Session = Depends(get_db)):
    """通过用户名（小写）获取 user_id"""
    user = db.query(User).filter(
        func.lower(User.username) == username_lower
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"user_id": user.id}
