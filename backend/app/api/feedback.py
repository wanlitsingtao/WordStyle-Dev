# -*- coding: utf-8 -*-
"""
用户反馈和需求提交 API（数据库版本）
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List

from ..core.database import get_db
from ..models import Feedback

router = APIRouter()

class FeedbackRequest(BaseModel):
    """反馈请求"""
    user_id: str
    feedback_type: str  # bug, feature, suggestion, other
    title: str
    description: str
    contact: Optional[str] = None  # 联系方式（可选）

class FeedbackResponse(BaseModel):
    """反馈响应"""
    id: str  # UUID字符串
    user_id: str
    feedback_type: str
    title: str
    description: str
    contact: Optional[str] = None
    status: str
    created_at: str
    
    class Config:
        from_attributes = True

@router.post("/submit", response_model=FeedbackResponse)
def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db)
):
    """
    提交用户反馈或需求（保存到数据库）
    
    Args:
        request: 反馈信息
        db: 数据库会话
        
    Returns:
        提交结果
    """
    try:
        # 创建反馈记录
        new_feedback = Feedback(
            user_id=request.user_id,
            feedback_type=request.feedback_type,
            title=request.title,
            description=request.description,
            contact=request.contact,
            status='pending',
            reply=None
        )
        
        db.add(new_feedback)
        db.commit()
        db.refresh(new_feedback)
        
        return FeedbackResponse(
            id=str(new_feedback.id),
            user_id=new_feedback.user_id,
            feedback_type=new_feedback.feedback_type,
            title=new_feedback.title,
            description=new_feedback.description,
            contact=new_feedback.contact,
            status=new_feedback.status,
            created_at=new_feedback.created_at.strftime('%Y-%m-%d %H:%M:%S') if new_feedback.created_at else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")

@router.get("/list", response_model=List[FeedbackResponse])
def get_feedback_list(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    获取反馈列表（管理员使用）
    
    Args:
        status: 筛选状态（可选）
        limit: 返回数量限制
        db: 数据库会话
        
    Returns:
        反馈列表
    """
    try:
        query = db.query(Feedback)
        
        # 按状态筛选
        if status:
            query = query.filter(Feedback.status == status)
        
        # 按时间倒序排列并限制数量
        feedbacks = query.order_by(Feedback.created_at.desc()).limit(limit).all()
        
        return [
            FeedbackResponse(
                id=str(f.id),
                user_id=f.user_id,
                feedback_type=f.feedback_type,
                title=f.title,
                description=f.description,
                contact=f.contact,
                status=f.status,
                created_at=f.created_at.strftime('%Y-%m-%d %H:%M:%S') if f.created_at else ''
            )
            for f in feedbacks
        ]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取反馈列表失败: {str(e)}")

@router.get("/stats")
def get_feedback_stats(db: Session = Depends(get_db)):
    """
    获取反馈统计信息
    
    Returns:
        统计数据
    """
    try:
        from sqlalchemy import func
        
        # 总反馈数
        total = db.query(func.count(Feedback.id)).scalar()
        
        # 按类型统计
        by_type = {}
        type_counts = db.query(Feedback.feedback_type, func.count(Feedback.id))\
            .group_by(Feedback.feedback_type)\
            .all()
        
        for fb_type, count in type_counts:
            by_type[fb_type or 'other'] = count
        
        # 按状态统计
        by_status = {}
        status_counts = db.query(Feedback.status, func.count(Feedback.id))\
            .group_by(Feedback.status)\
            .all()
        
        for fb_status, count in status_counts:
            by_status[fb_status or 'pending'] = count
        
        return {
            'total': total,
            'by_type': by_type,
            'by_status': by_status
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

@router.put("/update-status/{feedback_id}")
def update_feedback_status(
    feedback_id: str,
    status: str,
    admin_reply: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    更新反馈状态（管理员使用）
    
    Args:
        feedback_id: 反馈ID（UUID字符串）
        status: 新状态
        admin_reply: 管理员回复（可选）
        db: 数据库会话
    """
    try:
        import uuid
        feedback = db.query(Feedback).filter(Feedback.id == uuid.UUID(feedback_id)).first()
        
        if not feedback:
            raise HTTPException(status_code=404, detail="反馈不存在")
        
        feedback.status = status
        feedback.updated_at = datetime.now()
        if admin_reply:
            feedback.reply = admin_reply
        
        db.commit()
        
        return {"success": True, "message": "状态已更新"}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")
