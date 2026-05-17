# -*- coding: utf-8 -*-
"""
转换任务 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from ..core.database import get_db
from ..models import ConversionTask

router = APIRouter(prefix="/conversion-tasks", tags=["转换任务"])


class ConversionTaskCreate(BaseModel):
    """创建转换任务请求"""
    user_id: str
    source_file: str
    template_file: str
    status: str = 'COMPLETED'
    progress: int = 100
    error_message: Optional[str] = None


@router.post("/", response_model=dict)
def create_conversion_task(
    task_data: ConversionTaskCreate,
    db: Session = Depends(get_db)
):
    """
    创建转换任务记录
    
    Args:
        task_data: 转换任务数据
        db: 数据库会话
        
    Returns:
        创建结果
    """
    try:
        # 创建转换任务记录
        new_task = ConversionTask(
            user_id=task_data.user_id,
            source_file=task_data.source_file,
            template_file=task_data.template_file,
            status=task_data.status,
            progress=task_data.progress,
            error_message=task_data.error_message,
            completed_at=datetime.now() if task_data.status in ['COMPLETED', 'FAILED'] else None,
            created_at=datetime.now()
        )
        
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        
        return {
            'success': True,
            'task_id': str(new_task.id),
            'message': '转换任务记录已创建'
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")
