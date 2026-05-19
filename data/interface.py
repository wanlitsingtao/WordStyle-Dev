# -*- coding: utf-8 -*-
"""
数据访问层抽象接口
定义所有数据源必须实现的方法
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class IDataAccess(ABC):
    """数据访问接口 - 所有数据源必须实现此接口"""
    
    # ==================== 用户管理 ====================
    
    @abstractmethod
    def load_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """加载用户数据"""
        pass
    
    @abstractmethod
    def save_user_data(self, user_data: Dict[str, Any], user_id: str = None):
        """保存用户数据"""
        pass
    
    @abstractmethod
    def load_all_users_data(self) -> List[Dict[str, Any]]:
        """加载所有用户数据"""
        pass
    
    @abstractmethod
    def register_or_login_user(self, user_id: str, user_data: Dict[str, Any]):
        """注册或登录用户"""
        pass
    
    @abstractmethod
    def get_or_create_user_by_device(self, device_fingerprint: str, user_agent: str = None) -> Dict[str, Any]:
        """通过设备指纹获取或创建用户"""
        pass
    
    # ==================== 额度管理 ====================
    
    @abstractmethod
    def claim_free_paragraphs(self, user_id=None) -> Dict[str, Any]:
        """领取免费段落额度"""
        pass
    
    @abstractmethod
    def recharge_user(self, amount, package_label, user_id=None) -> Dict[str, Any]:
        """用户充值"""
        pass
    
    @abstractmethod
    def deduct_paragraphs(self, paragraphs, user_id=None) -> bool:
        """扣除段落额度"""
        pass
    
    # ==================== 转换记录 ====================
    
    @abstractmethod
    def add_conversion_record(self, files_count, success_count, failed_count, user_id=None, paragraphs=0) -> Dict[str, Any]:
        """添加转换记录"""
        pass
    
    @abstractmethod
    def get_user_stats(self, user_id=None) -> Dict[str, Any]:
        """获取用户统计信息"""
        pass
    
    # ==================== 任务管理 ====================
    
    @abstractmethod
    def create_task(self, *args, **kwargs) -> Dict[str, Any]:
        """创建任务"""
        pass
    
    @abstractmethod
    def update_task_status(self, *args, **kwargs) -> bool:
        """更新任务状态"""
        pass
    
    @abstractmethod
    def complete_task(self, *args, **kwargs) -> bool:
        """完成任务"""
        pass
    
    @abstractmethod
    def fail_task(self, *args, **kwargs) -> bool:
        """标记任务失败"""
        pass
    
    @abstractmethod
    def get_all_tasks(self, status_filter=None, limit=100, offset=0) -> List[Dict[str, Any]]:
        """获取所有任务"""
        pass
    
    @abstractmethod
    def get_task_stats(self) -> Dict[str, Any]:
        """获取任务统计"""
        pass
    
    @abstractmethod
    def get_user_active_task(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户活跃任务"""
        pass
    
    @abstractmethod
    def get_user_completed_tasks(self, user_id: str, limit=50) -> List[Dict[str, Any]]:
        """获取用户已完成任务"""
        pass
    
    @abstractmethod
    def has_active_task(self, user_id: str) -> bool:
        """检查用户是否有活跃任务"""
        pass
    
    @abstractmethod
    def cleanup_expired_tasks(self) -> int:
        """清理过期任务"""
        pass
    
    # ==================== 系统配置 ====================
    
    @abstractmethod
    def get_config(self, key: str) -> Optional[str]:
        """获取配置项"""
        pass
    
    @abstractmethod
    def get_all_configs(self) -> Dict[str, str]:
        """获取所有配置"""
        pass
    
    @abstractmethod
    def update_config(self, key: str, value: str) -> bool:
        """更新配置项"""
        pass
    
    # ==================== 反馈管理 ====================
    
    @abstractmethod
    def add_feedback(self, user_id: str, feedback_type: str, title: str, description: str, contact: str = "") -> Dict[str, Any]:
        """添加反馈"""
        pass
    
    @abstractmethod
    def get_all_feedbacks(self, limit=100, offset=0) -> List[Dict[str, Any]]:
        """获取所有反馈"""
        pass
    
    @abstractmethod
    def get_user_feedbacks(self, user_id: str, limit=50) -> List[Dict[str, Any]]:
        """获取用户反馈"""
        pass
    
    # ==================== 评论管理 ====================
    
    @abstractmethod
    def add_comment(self, username: str, content: str, rating: int = 5) -> Dict[str, Any]:
        """添加评论"""
        pass
    
    @abstractmethod
    def get_comments(self, limit=50) -> List[Dict[str, Any]]:
        """获取评论列表"""
        pass
    
    @abstractmethod
    def like_comment(self, comment_id: str) -> bool:
        """点赞评论"""
        pass


class DataAccessFactory:
    """数据访问工厂 - 根据配置创建合适的实例"""
    
    @staticmethod
    def create(data_source: str = "local") -> IDataAccess:
        """
        创建数据访问实例
        
        Args:
            data_source: 数据源类型 (local/supabase/api)
        
        Returns:
            IDataAccess 实例
        """
        if data_source == "local":
            from data.local import LocalDataAccess
            return LocalDataAccess()
        elif data_source == "supabase":
            from data.supabase import SupabaseDataAccess
            return SupabaseDataAccess()
        elif data_source == "api":
            from data.api import APIDataAccess
            return APIDataAccess()
        else:
            raise ValueError(f"Unsupported data source: {data_source}")
