# -*- coding: utf-8 -*-
"""
Pydantic Schemas - 用于 API 请求和响应验证
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# ==================== 用户相关 ====================

class UserResponse(BaseModel):
    """用户信息响应（基于实际数据库结构）"""
    id: str  # 12位字符串用户ID
    username: Optional[str] = None
    balance: float = 0.0
    paragraphs_remaining: int = 0
    total_paragraphs_used: int = 0
    total_converted: int = 0
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ==================== 评论相关 ====================

class CommentResponse(BaseModel):
    """评论响应"""
    id: UUID
    user_id: Optional[str] = None
    username: Optional[str] = None
    content: str
    rating: int = 5
    likes: int = 0
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== 反馈相关 ====================

class FeedbackResponse(BaseModel):
    """反馈响应"""
    id: UUID
    user_id: Optional[str] = None
    feedback_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    contact: Optional[str] = None
    status: str = 'pending'
    reply: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ==================== 样式映射相关 ====================

class StyleMappingResponse(BaseModel):
    """样式映射响应"""
    id: UUID
    user_id: str
    filename: str
    source_style: str
    target_style: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# 订单相关已移除，直接进入转换任务相关

# ==================== 转换任务相关 ====================

class ConversionTaskResponse(BaseModel):
    """转换任务响应（基于实际数据库结构）"""
    id: UUID
    user_id: str
    source_file: str
    template_file: str
    converted_file: Optional[str] = None
    status: str
    progress: int
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
