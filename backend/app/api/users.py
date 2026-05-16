# -*- coding: utf-8 -*-
"""
用户 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models import User
from app.schemas import UserResponse, UserUpdate
from app.core.config import settings

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

@router.post("/{user_id}/claim-free")
def claim_free_paragraphs(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    领取免费段落（每日一次）
    
    Args:
        user_id: 用户ID
        db: 数据库会话
    
    Returns:
        {
            "success": True/False,
            "paragraphs": 领取的段落数,
            "message": 提示信息
        }
    """
    try:
        # 查找用户
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        today = date.today()
        
        # 检查今日是否已领取
        if user.last_claim_date:
            last_claim = user.last_claim_date.date() if hasattr(user.last_claim_date, 'date') else user.last_claim_date
            if last_claim == today:
                return {
                    "success": False,
                    "paragraphs": 0,
                    "message": "今日已领取过免费额度",
                    "remaining": user.paragraphs_remaining
                }
        
        # 今日首次领取：重置为免费额度（不累计）
        free_paragraphs = settings.FREE_PARAGRAPHS_DAILY
        user.paragraphs_remaining = free_paragraphs
        user.last_claim_date = datetime.now()
        db.commit()
        
        return {
            "success": True,
            "paragraphs": free_paragraphs,
            "message": f"成功领取 {free_paragraphs} 个免费段落",
            "remaining": user.paragraphs_remaining
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"领取失败: {str(e)}")
