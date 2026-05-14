# -*- coding: utf-8 -*-
"""
用户反馈和需求提交 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import json
from pathlib import Path
from typing import Optional

router = APIRouter()

# 数据文件路径
FEEDBACK_FILE = Path("e:/LingMa/WordStyle/feedback_data.json")

class FeedbackRequest(BaseModel):
    """反馈请求"""
    user_id: str
    feedback_type: str  # bug, feature, suggestion, other
    title: str
    description: str
    contact: Optional[str] = None  # 联系方式（可选）

class FeedbackResponse(BaseModel):
    """反馈响应"""
    success: bool
    message: str
    feedback_id: str

@router.post("/submit", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest):
    """
    提交用户反馈或需求
    
    Args:
        request: 反馈信息
        
    Returns:
        提交结果
    """
    try:
        # 生成反馈ID
        import uuid
        feedback_id = f"FB{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        
        # 读取现有反馈数据
        if FEEDBACK_FILE.exists():
            with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
                try:
                    all_feedback = json.load(f)
                except:
                    all_feedback = []
        else:
            all_feedback = []
        
        # 创建新的反馈记录
        feedback_record = {
            'feedback_id': feedback_id,
            'user_id': request.user_id,
            'type': request.feedback_type,
            'title': request.title,
            'description': request.description,
            'contact': request.contact,
            'status': 'pending',  # pending, reviewing, completed, rejected
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'admin_reply': None
        }
        
        # 添加到列表
        all_feedback.append(feedback_record)
        
        # 保存
        with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_feedback, f, ensure_ascii=False, indent=2)
        
        return FeedbackResponse(
            success=True,
            message="✅ 感谢您的反馈！我们会尽快处理",
            feedback_id=feedback_id
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")

@router.get("/list")
def get_feedback_list(status: Optional[str] = None, limit: int = 50):
    """
    获取反馈列表（管理员使用）
    
    Args:
        status: 筛选状态（可选）
        limit: 返回数量限制
        
    Returns:
        反馈列表
    """
    if not FEEDBACK_FILE.exists():
        return []
    
    with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
        try:
            all_feedback = json.load(f)
        except:
            return []
    
    # 按状态筛选
    if status:
        all_feedback = [f for f in all_feedback if f['status'] == status]
    
    # 按时间倒序排列
    all_feedback.sort(key=lambda x: x['created_at'], reverse=True)
    
    # 限制数量
    return all_feedback[:limit]

@router.get("/stats")
def get_feedback_stats():
    """
    获取反馈统计信息
    
    Returns:
        统计数据
    """
    if not FEEDBACK_FILE.exists():
        return {
            'total': 0,
            'by_type': {},
            'by_status': {}
        }
    
    with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
        try:
            all_feedback = json.load(f)
        except:
            return {'total': 0, 'by_type': {}, 'by_status': {}}
    
    # 统计
    stats = {
        'total': len(all_feedback),
        'by_type': {},
        'by_status': {}
    }
    
    for feedback in all_feedback:
        # 按类型统计
        fb_type = feedback.get('type', 'other')
        stats['by_type'][fb_type] = stats['by_type'].get(fb_type, 0) + 1
        
        # 按状态统计
        fb_status = feedback.get('status', 'pending')
        stats['by_status'][fb_status] = stats['by_status'].get(fb_status, 0) + 1
    
    return stats

@router.put("/update-status/{feedback_id}")
def update_feedback_status(feedback_id: str, status: str, admin_reply: Optional[str] = None):
    """
    更新反馈状态（管理员使用）
    
    Args:
        feedback_id: 反馈ID
        status: 新状态
        admin_reply: 管理员回复（可选）
    """
    if not FEEDBACK_FILE.exists():
        raise HTTPException(status_code=404, detail="反馈不存在")
    
    with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
        try:
            all_feedback = json.load(f)
        except:
            raise HTTPException(status_code=500, detail="数据读取失败")
    
    # 查找反馈
    found = False
    for feedback in all_feedback:
        if feedback['feedback_id'] == feedback_id:
            feedback['status'] = status
            feedback['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if admin_reply:
                feedback['admin_reply'] = admin_reply
            found = True
            break
    
    if not found:
        raise HTTPException(status_code=404, detail="反馈不存在")
    
    # 保存
    with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_feedback, f, ensure_ascii=False, indent=2)
    
    return {"success": True, "message": "状态已更新"}
