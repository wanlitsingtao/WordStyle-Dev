"""
评论管理 API 端点
提供评论的增删改查功能，支持持久化存储到数据库
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..core.database import get_db
from ..models import Comment

router = APIRouter(prefix="/comments", tags=["comments"])


# ==================== Pydantic 模型 ====================

class CommentCreate(BaseModel):
    """创建评论请求"""
    username: Optional[str] = None
    content: str
    rating: int = 5
    user_id: Optional[str] = None


class CommentResponse(BaseModel):
    """评论响应"""
    id: str  # UUID字符串
    username: str
    content: str
    rating: int
    timestamp: str  # created_at格式化后的字符串
    likes: int
    user_id: Optional[str] = None
    
    class Config:
        from_attributes = True


# ==================== API 端点 ====================

@router.post("/submit", response_model=CommentResponse)
def submit_comment(
    comment_data: CommentCreate,
    db: Session = Depends(get_db)
):
    """
    提交新评论
    
    - **username**: 用户名（可选）
    - **content**: 评论内容（必填）
    - **rating**: 评分（1-5，默认5）
    - **user_id**: 用户ID（可选）
    """
    try:
        # 创建评论记录
        new_comment = Comment(
            username=comment_data.username or f"用户{comment_data.user_id[:6] if comment_data.user_id else '匿名'}",
            content=comment_data.content,
            rating=comment_data.rating,
            likes=0,
            user_id=comment_data.user_id
        )
        
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)
        
        return CommentResponse(
            id=str(new_comment.id),
            username=new_comment.username,
            content=new_comment.content,
            rating=new_comment.rating,
            timestamp=new_comment.created_at.strftime('%Y-%m-%d %H:%M:%S') if new_comment.created_at else datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            likes=new_comment.likes,
            user_id=new_comment.user_id
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"提交评论失败: {str(e)}")


@router.get("/list", response_model=List[CommentResponse])
def get_comments(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    获取评论列表（按时间倒序）
    
    - **limit**: 返回数量限制（默认50）
    - **offset**: 偏移量（默认0）
    """
    try:
        comments = db.query(Comment)\
            .order_by(Comment.created_at.desc())\
            .offset(offset)\
            .limit(limit)\
            .all()
        
        return [
            CommentResponse(
                id=str(c.id),
                username=c.username,
                content=c.content,
                rating=c.rating,
                timestamp=c.created_at.strftime('%Y-%m-%d %H:%M:%S') if c.created_at else '',
                likes=c.likes,
                user_id=c.user_id
            )
            for c in comments
        ]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取评论列表失败: {str(e)}")


@router.get("/stats")
def get_comment_stats(db: Session = Depends(get_db)):
    """
    获取评论统计信息
    
    返回：
    - total: 总评论数
    - average_rating: 平均评分
    - by_rating: 各评分数量分布
    """
    try:
        from sqlalchemy import func
        
        # 总评论数
        total = db.query(func.count(Comment.id)).scalar()
        
        # 平均评分
        avg_rating_result = db.query(func.avg(Comment.rating)).scalar()
        average_rating = round(float(avg_rating_result), 2) if avg_rating_result else 0.0
        
        # 各评分数量
        by_rating = {}
        rating_counts = db.query(Comment.rating, func.count(Comment.id))\
            .group_by(Comment.rating)\
            .all()
        
        for rating, count in rating_counts:
            by_rating[str(rating)] = count
        
        return {
            "total": total,
            "average_rating": average_rating,
            "by_rating": by_rating
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取评论统计失败: {str(e)}")


@router.put("/like/{comment_id}")
def like_comment(
    comment_id: int,
    db: Session = Depends(get_db)
):
    """
    点赞评论
    
    - **comment_id**: 评论ID
    """
    try:
        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        
        if not comment:
            raise HTTPException(status_code=404, detail="评论不存在")
        
        comment.likes += 1
        db.commit()
        
        return {
            "success": True,
            "comment_id": comment_id,
            "likes": comment.likes
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"点赞失败: {str(e)}")


@router.delete("/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db)
):
    """
    删除评论（管理员功能）
    
    - **comment_id**: 评论ID
    """
    try:
        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        
        if not comment:
            raise HTTPException(status_code=404, detail="评论不存在")
        
        db.delete(comment)
        db.commit()
        
        return {
            "success": True,
            "message": "评论已删除"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除评论失败: {str(e)}")
