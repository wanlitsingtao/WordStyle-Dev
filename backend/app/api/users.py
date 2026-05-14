# -*- coding: utf-8 -*-
"""
用户 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models import User
from app.schemas import UserResponse, UserUpdate

router = APIRouter()

@router.get("/profile", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """获取当前用户个人资料"""
    return current_user

@router.put("/profile", response_model=UserResponse)
def update_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新用户个人资料"""
    if user_update.username:
        current_user.username = user_update.username
    
    if user_update.email:
        # 检查邮箱是否已被其他用户使用
        existing = db.query(User).filter(User.email == user_update.email).first()
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = user_update.email
    
    db.commit()
    db.refresh(current_user)
    
    return current_user

@router.get("/balance")
def get_balance(current_user: User = Depends(get_current_user)):
    """查询用户余额"""
    return {
        "balance": current_user.balance,
        "paragraphs_remaining": current_user.paragraphs_remaining
    }
