# -*- coding: utf-8 -*-
"""
数据模型定义
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.core.database import Base
from sqlalchemy import TypeDecorator

# SQLite 兼容的 UUID 类型
class UUID(TypeDecorator):
    impl = String(36)  # UUID 字符串长度为 36
    cache_ok = True
    
    def __init__(self, as_uuid=False):
        super().__init__()
        self.as_uuid = as_uuid
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        return str(value)
    
    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        if self.as_uuid and isinstance(value, str):
            return uuid.UUID(value)
        return value

class User(Base):
    """用户模型（简化版 - 基于实际数据库结构）"""
    __tablename__ = "users"
    
    id = Column(String(12), primary_key=True)  # 12位字符串用户ID
    username = Column(String(50))  # 用户名
    style_mappings = Column(JSONB, default='{}')  # 样式映射配置
    balance = Column(Float, default=0.0)  # 账户余额
    paragraphs_remaining = Column(Integer, default=0)  # 剩余段落数
    total_paragraphs_used = Column(Integer, default=0)  # 累计使用段落数
    total_converted = Column(Integer, default=0)  # 累计转换文件数
    is_active = Column(Boolean, default=True)  # 是否激活
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 创建时间
    last_login = Column(DateTime(timezone=True))  # 最后登录时间
    last_claim_date = Column(DateTime(timezone=True))  # 上次领取免费额度日期
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # 更新时间
    
    def __repr__(self):
        return f"<User {self.id}>"

# User 模型定义完成后，直接到 ConversionTask

class ConversionTask(Base):
    """转换任务模型（基于实际数据库结构）"""
    __tablename__ = "conversion_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(12), ForeignKey("users.id"), nullable=False)  # 用户ID
    source_file = Column(String(500), nullable=False)  # 源文件路径
    template_file = Column(String(500), nullable=False)  # 模板文件路径
    converted_file = Column(String(500))  # 转换后文件路径
    status = Column(String(20), default='pending')  # 任务状态
    progress = Column(Integer, default=0)  # 进度（0-100）
    error_message = Column(Text)  # 错误信息
    completed_at = Column(DateTime(timezone=True))  # 完成时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 创建时间
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # 更新时间
    
    def __repr__(self):
        return f"<ConversionTask {self.id}>"

class SystemConfig(Base):
    """系统配置模型"""
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(Text, nullable=False)
    description = Column(String(500))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SystemConfig {self.config_key}>"

class Comment(Base):
    """评论模型"""
    __tablename__ = "comments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(50))  # 用户ID
    username = Column(String(100))  # 用户名
    content = Column(Text, nullable=False)  # 评论内容
    rating = Column(Integer, default=5)  # 评分
    likes = Column(Integer, default=0)  # 点赞数
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 创建时间
    
    def __repr__(self):
        return f"<Comment {self.id}>"

class Feedback(Base):
    """反馈模型"""
    __tablename__ = "feedbacks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(50))  # 用户ID
    feedback_type = Column(String(20))  # 反馈类型
    title = Column(String(200))  # 标题
    description = Column(Text)  # 描述
    contact = Column(String(200))  # 联系方式
    status = Column(String(20), default='pending')  # 状态
    reply = Column(Text)  # 回复
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 创建时间
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # 更新时间
    
    def __repr__(self):
        return f"<Feedback {self.id}>"

class StyleMapping(Base):
    """样式映射模型"""
    __tablename__ = "style_mappings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(50), nullable=False)  # 用户ID
    filename = Column(String(255), nullable=False)  # 文件名
    source_style = Column(String(255), nullable=False)  # 源样式
    target_style = Column(String(255), nullable=False)  # 目标样式
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 创建时间
    
    def __repr__(self):
        return f"<StyleMapping {self.id}>"
