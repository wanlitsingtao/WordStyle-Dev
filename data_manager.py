# -*- coding: utf-8 -*-
"""
统一数据访问层 - 支持三模式（SQLite/Supabase/API）
自动检测环境并选择合适的数据源
- local: 本地开发（SQLite + JSON）
- supabase: 直接连接 Supabase（Render 等允许出站数据库连接的环境）
- api: 通过后端 API 获取数据（Streamlit Cloud 等受限环境）
"""
import os
import sys
import logging
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

# 导入配置
sys.path.insert(0, os.path.dirname(__file__))
from config import DATA_SOURCE, DATABASE_URL, BACKEND_URL, USER_DATA_FILE, TASKS_DB_FILE

# ==================== 本地模式导入 ====================
if DATA_SOURCE == "local":
    from user_manager import (
        load_user_data as _load_user,
        save_user_data as _save_user,
        load_all_users_data as _load_all_users,
        claim_free_paragraphs as _claim_free,
        recharge_user as _recharge_user,
        deduct_paragraphs as _deduct_paragraphs,
        add_conversion_record as _add_conversion_record,
        get_user_stats as _get_user_stats,
        generate_user_id as _generate_user_id,
    )
    from task_manager import (
        create_task as _create_task,
        update_task_status as _update_task_status,
        complete_task as _complete_task,
        fail_task as _fail_task,
        get_all_tasks as _get_all_tasks,
        get_task_stats as _get_task_stats,
        register_or_login_user as _register_user,
        get_user_active_task as _get_user_active_task,
        get_user_completed_tasks as _get_user_completed_tasks,
        has_active_task as _has_active_task,
        cleanup_expired_tasks as _cleanup_expired_tasks,
    )
    
    def _get_or_create_user_by_device(device_fingerprint: str, user_agent: str = None) -> Dict[str, Any]:
        """
        通过设备指纹获取或创建用户（Local模式 - 基于JSON文件）
        
        Args:
            device_fingerprint: 设备指纹（32位MD5）
            user_agent: User-Agent字符串（可选，用于日志）
        
        Returns:
            用户数据字典
        """
        import json
        import hashlib
        from pathlib import Path
        from config import FREE_PARAGRAPHS_DAILY
        from datetime import datetime
        
        # 使用user_mapping.json存储设备指纹映射
        mapping_file = Path(__file__).parent / "user_mapping.json"
        
        try:
            # 读取映射文件
            user_mapping = {}
            if mapping_file.exists():
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    user_mapping = json.load(f)
            
            # 查找设备指纹对应的用户ID
            if device_fingerprint in user_mapping:
                user_id = user_mapping[device_fingerprint]
                
                # 加载用户数据
                user_data = _load_user(user_id)
                if user_data:
                    # 更新last_login
                    user_data['last_login'] = datetime.now().isoformat()
                    _save_user(user_data, user_id)
                    return user_data
            
            # 用户不存在，创建新用户
            user_id = hashlib.md5(f"wordstyle_device_{device_fingerprint}".encode()).hexdigest()[:12]
            
            # 准备用户数据
            new_user_data = {
                'user_id': user_id,
                'balance': 0.0,
                'paragraphs_remaining': FREE_PARAGRAPHS_DAILY,
                'total_paragraphs_used': 0,
                'total_converted': 0,
                'is_active': True,
                'created_at': datetime.now().isoformat(),
                'last_login': datetime.now().isoformat(),
                'conversion_history': [],  # ✅ 添加转换历史字段
            }
            
            # 保存用户数据
            _register_user(user_id, new_user_data)
            
            # 保存设备指纹映射
            user_mapping[device_fingerprint] = user_id
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(user_mapping, f, ensure_ascii=False, indent=2)
            
            return new_user_data
            
        except Exception as e:
            raise Exception(f"Local模式创建设备指纹用户失败: {e}")
    
    print(f"[OK] 数据访问层初始化：本地模式 (SQLite + JSON)")

# ==================== Supabase 模式导入 ====================
elif DATA_SOURCE == "supabase":
    try:
        # 添加 backend 路径
        backend_path = Path(__file__).parent / "backend"
        sys.path.insert(0, str(backend_path))
        
        from app.core.database import SessionLocal
        from app.models import User, ConversionTask
        
        def _load_user(user_id: str) -> Dict[str, Any]:
            """从 Supabase 加载用户数据
            
            ✅ 防御性编程：失败时返回默认用户数据，而不是None
            """
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    return {
                        'user_id': user.id,
                        'balance': float(user.balance or 0),
                        'paragraphs_remaining': int(user.paragraphs_remaining or 0),
                        'total_paragraphs_used': int(user.total_paragraphs_used or 0),
                        'total_converted': int(user.total_converted or 0),
                        'is_active': bool(user.is_active),
                        'created_at': user.created_at.isoformat() if user.created_at else '',
                        'last_login': user.last_login.isoformat() if user.last_login else '',
                        'conversion_history': [],  # ✅ 添加默认值
                        'style_mappings': {},  # ✅ 添加默认值
                    }
                # ✅ 用户不存在时返回默认数据而不是None
                logger.warning(f"️ 用户不存在: {user_id}，返回默认用户数据")
                return {
                    'user_id': user_id,
                    'balance': 0.0,
                    'paragraphs_remaining': 0,
                    'total_paragraphs_used': 0,
                    'total_converted': 0,
                    'is_active': False,
                    'created_at': '',
                    'last_login': '',
                    'conversion_history': [],
                    'style_mappings': {},
                }
            except Exception as e:
                logger.error(f"️ Supabase加载用户数据异常: {e}，返回默认数据")
                return {
                    'user_id': user_id,
                    'balance': 0.0,
                    'paragraphs_remaining': 0,
                    'total_paragraphs_used': 0,
                    'total_converted': 0,
                    'is_active': False,
                    'created_at': '',
                    'last_login': '',
                    'conversion_history': [],
                    'style_mappings': {},
                }
            finally:
                db.close()
        
        def _save_user(user_data: Dict[str, Any], user_id: str = None):
            """保存用户数据到 Supabase"""
            # Supabase 模式下，用户数据通过 ORM 管理
            # 此函数主要用于兼容性，实际保存在其他地方处理
            pass
        
        def _load_all_users() -> List[Dict[str, Any]]:
            """从 Supabase 加载所有用户"""
            db = SessionLocal()
            try:
                users = db.query(User).all()
                return [
                    {
                        'user_id': u.id,
                        'balance': float(u.balance or 0),
                        'paragraphs_remaining': int(u.paragraphs_remaining or 0),
                        'total_paragraphs_used': int(u.total_paragraphs_used or 0),
                        'total_converted': int(u.total_converted or 0),
                        'is_active': bool(u.is_active),
                        'created_at': u.created_at.isoformat() if u.created_at else '',
                        'last_login': u.last_login.isoformat() if u.last_login else '',
                    }
                    for u in users
                ]
            finally:
                db.close()
        
        def _register_user(user_id: str, user_data: Dict[str, Any]):
            """注册或更新用户到 Supabase"""
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    # 更新现有用户
                    user.balance = user_data.get('balance', 0)
                    user.paragraphs_remaining = user_data.get('paragraphs_remaining', 0)
                    user.total_paragraphs_used = user_data.get('total_paragraphs_used', 0)
                    user.total_converted = user_data.get('total_converted', 0)
                    user.last_login = datetime.now()
                else:
                    # 创建新用户
                    user = User(
                        id=user_id,
                        balance=user_data.get('balance', 0),
                        paragraphs_remaining=user_data.get('paragraphs_remaining', 0),
                        total_paragraphs_used=user_data.get('total_paragraphs_used', 0),
                        total_converted=user_data.get('total_converted', 0),
                        is_active=True,
                        created_at=datetime.now(),
                        last_login=datetime.now(),
                    )
                    db.add(user)
                db.commit()
            except Exception as e:
                db.rollback()
                raise e
            finally:
                db.close()
        
        def _create_task(*args, **kwargs):
            """创建任务（Supabase 模式）"""
            # TODO: 实现 Supabase 任务创建
            pass
        
        def _complete_task(*args, **kwargs):
            """完成任务（Supabase 模式）"""
            # TODO: 实现 Supabase 任务完成
            pass
        
        def _fail_task(*args, **kwargs):
            """标记任务失败（Supabase 模式）"""
            # TODO: 实现 Supabase 任务失败
            pass
        
        def _get_all_tasks(status_filter=None, limit=100, offset=0):
            """获取所有任务（Supabase 模式）"""
            db = SessionLocal()
            try:
                query = db.query(ConversionTask)
                if status_filter and status_filter != 'ALL':
                    query = query.filter(ConversionTask.status == status_filter)
                
                tasks = query.order_by(ConversionTask.created_at.desc()).limit(limit).offset(offset).all()
                
                return [
                    {
                        'task_id': t.task_id,
                        'user_id': t.user_id,
                        'filename': t.filename,
                        'file_count': t.file_count,
                        'paragraphs': t.paragraphs,
                        'cost': float(t.cost or 0),
                        'status': t.status,
                        'progress': t.progress,
                        'created_at': t.created_at.isoformat() if t.created_at else '',
                        'completed_at': t.completed_at.isoformat() if t.completed_at else '',
                        'error_message': t.error_message,
                    }
                    for t in tasks
                ]
            finally:
                db.close()
        
        def _get_task_stats():
            """获取任务统计（Supabase 模式）"""
            db = SessionLocal()
            try:
                total = db.query(ConversionTask).count()
                completed = db.query(ConversionTask).filter(
                    ConversionTask.status == 'COMPLETED'
                ).count()
                processing = db.query(ConversionTask).filter(
                    ConversionTask.status == 'PROCESSING'
                ).count()
                pending = db.query(ConversionTask).filter(
                    ConversionTask.status == 'PENDING'
                ).count()
                failed = db.query(ConversionTask).filter(
                    ConversionTask.status == 'FAILED'
                ).count()
                
                return {
                    'total_tasks': total,
                    'completed_tasks': completed,
                    'processing_tasks': processing,
                    'pending_tasks': pending,
                    'failed_tasks': failed,
                }
            finally:
                db.close()
        
        # 用户管理相关函数（Supabase 模式 - 完整实现）
        def _claim_free(user_id=None):
            """领取免费段落（Supabase 模式）- 每日只领取一次"""
            from config import FREE_PARAGRAPHS_DAILY
            from datetime import date
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    today = date.today()
                    
                    # 检查今日是否已领取
                    if user.last_claim_date:
                        last_claim = user.last_claim_date.date() if hasattr(user.last_claim_date, 'date') else user.last_claim_date
                        if last_claim == today:
                            # 今日已领取，不再重复发放
                            return 0
                    
                    # 今日首次领取：重置为免费额度（不累计）
                    user.paragraphs_remaining = FREE_PARAGRAPHS_DAILY
                    user.last_claim_date = datetime.now()
                    db.commit()
                    return FREE_PARAGRAPHS_DAILY
                return 0
            except Exception as e:
                db.rollback()
                print(f"[WARN] 领取免费段落失败: {e}")
                return 0
            finally:
                db.close()
        
        def _recharge_user(amount, package_label, user_id=None):
            """充值用户（Supabase 模式）"""
            # 计算段落数：1元 = 1000段落
            paragraphs = int(amount * 1000)
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.balance += amount
                    user.paragraphs_remaining += paragraphs
                    db.commit()
                    return {
                        'success': True,
                        'amount': amount,
                        'paragraphs': paragraphs,
                        'new_balance': user.balance,
                        'new_paragraphs': user.paragraphs_remaining
                    }
                return {'success': False, 'error': '用户不存在'}
            except Exception as e:
                db.rollback()
                print(f"[WARN] 充值失败: {e}")
                return {'success': False, 'error': str(e)}
            finally:
                db.close()
        
        def _deduct_paragraphs(paragraphs, user_id=None):
            """扣除段落（Supabase 模式）"""
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    if user.paragraphs_remaining >= paragraphs:
                        user.paragraphs_remaining -= paragraphs
                        db.commit()
                        return True
                    else:
                        return False  # 余额不足
                return False
            except Exception as e:
                db.rollback()
                print(f"[WARN] 扣除段落失败: {e}")
                return False
            finally:
                db.close()
        
        def _add_conversion_record(files_count, success_count, failed_count, user_id=None):
            """添加转换记录（Supabase 模式）"""
            # Supabase 模式下，转换记录通过 ConversionTask 表管理
            # 此函数主要用于兼容性，实际在任务完成时自动记录
            pass
        
        def _get_user_stats(user_id=None):
            """获取用户统计（Supabase 模式）"""
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    return {
                        'user_id': str(user.id),
                        'balance': float(user.balance or 0),
                        'paragraphs_remaining': int(user.paragraphs_remaining or 0),
                        'is_active': bool(user.is_active),
                        'created_at': user.created_at.isoformat() if user.created_at else '',
                    }
                return {}
            finally:
                db.close()
        
        def _generate_user_id():
            """生成用户ID（Supabase 模式）"""
            import uuid
            return str(uuid.uuid4())
        
        def _create_task(task_id, user_id, filename, file_count=1, paragraphs=0, cost=0.0):
            """创建任务（Supabase 模式）"""
            db = SessionLocal()
            try:
                task = ConversionTask(
                    task_id=task_id,
                    user_id=user_id,
                    filename=filename,
                    file_count=file_count,
                    paragraphs=paragraphs,
                    cost=cost,
                    status='PENDING',
                    progress=0
                )
                db.add(task)
                db.commit()
                return task_id
            except Exception as e:
                db.rollback()
                print(f"[WARN] 创建任务失败: {e}")
                return None
            finally:
                db.close()
        
        def _update_task_status(task_id, status, progress=None, error_message=None):
            """更新任务状态（Supabase 模式）"""
            db = SessionLocal()
            try:
                task = db.query(ConversionTask).filter(ConversionTask.task_id == task_id).first()
                if task:
                    task.status = status
                    if progress is not None:
                        task.progress = progress
                    if error_message is not None:
                        task.error_message = error_message
                    if status == 'COMPLETED':
                        task.completed_at = datetime.now()
                    db.commit()
                    return True
                return False
            except Exception as e:
                db.rollback()
                print(f"[WARN] 更新任务状态失败: {e}")
                return False
            finally:
                db.close()
        
        def _complete_task(task_id):
            """完成任务（Supabase 模式）"""
            return _update_task_status(task_id, 'COMPLETED', progress=100)
        
        def _fail_task(task_id, error_message=""):
            """标记任务失败（Supabase 模式）"""
            return _update_task_status(task_id, 'FAILED', error_message=error_message)
        
        def _get_user_active_task(user_id):
            """获取用户活动任务（Supabase 模式）"""
            db = SessionLocal()
            try:
                task = db.query(ConversionTask).filter(
                    ConversionTask.user_id == user_id,
                    ConversionTask.status.in_(['PENDING', 'PROCESSING'])
                ).first()
                return task
            finally:
                db.close()
        
        def _get_user_completed_tasks(user_id, limit=20):
            """获取用户已完成任务（Supabase 模式）"""
            db = SessionLocal()
            try:
                tasks = db.query(ConversionTask).filter(
                    ConversionTask.user_id == user_id,
                    ConversionTask.status == 'COMPLETED'
                ).order_by(ConversionTask.created_at.desc()).limit(limit).all()
                
                return [
                    {
                        'task_id': t.task_id,
                        'filename': t.filename,
                        'paragraphs': t.paragraphs,
                        'cost': float(t.cost or 0),
                        'created_at': t.created_at.isoformat() if t.created_at else '',
                        'completed_at': t.completed_at.isoformat() if t.completed_at else '',
                    }
                    for t in tasks
                ]
            finally:
                db.close()
        
        def _has_active_task(user_id):
            """检查用户是否有活动任务（Supabase 模式）"""
            return _get_user_active_task(user_id) is not None
        
        def _cleanup_expired_tasks():
            """清理过期任务（Supabase 模式）"""
            from config import TASK_EXPIRY_DAYS
            from datetime import timedelta
            
            db = SessionLocal()
            try:
                expiry_date = datetime.now() - timedelta(days=TASK_EXPIRY_DAYS)
                deleted = db.query(ConversionTask).filter(
                    ConversionTask.created_at < expiry_date,
                    ConversionTask.status == 'COMPLETED'
                ).delete()
                db.commit()
                return deleted
            except Exception as e:
                db.rollback()
                print(f"[WARN] 清理过期任务失败: {e}")
                return 0
            finally:
                db.close()
        
        print(f"[OK] 数据访问层初始化：Supabase 模式 (PostgreSQL)")
    
    except ImportError as e:
        import traceback
        error_msg = f"Supabase 模式初始化失败: {e}"
        print(f"️ {error_msg}")
        print(f"   详细错误: {traceback.format_exc()}")
        print("   回退到本地模式")
        DATA_SOURCE = "local"
        from user_manager import (
            load_user_data as _load_user,
            save_user_data as _save_user,
            load_all_users_data as _load_all_users,
        )
        from task_manager import (
            create_task as _create_task,
            complete_task as _complete_task,
            fail_task as _fail_task,
            get_all_tasks as _get_all_tasks,
            get_task_stats as _get_task_stats,
            register_or_login_user as _register_user,
        )
    except Exception as e:
        import traceback
        error_msg = f"Supabase 模式初始化异常: {e}"
        print(f"️ {error_msg}")
        print(f"   详细错误: {traceback.format_exc()}")
        print("   回退到本地模式")
        DATA_SOURCE = "local"
        from user_manager import (
            load_user_data as _load_user,
            save_user_data as _save_user,
            load_all_users_data as _load_all_users,
        )
        from task_manager import (
            create_task as _create_task,
            complete_task as _complete_task,
            fail_task as _fail_task,
            get_all_tasks as _get_all_tasks,
            get_task_stats as _get_task_stats,
            register_or_login_user as _register_user,
        )

# ==================== API 模式导入 ====================
elif DATA_SOURCE == "api":
    """
    API 模式：通过后端 API 获取数据
    适用于 Streamlit Cloud 等无法直连数据库的环境
    """
    # 确保 BACKEND_URL 存在
    if not BACKEND_URL:
        print("[WARN] API 模式需要 BACKEND_URL，回退到本地模式")
        DATA_SOURCE = "local"
        from user_manager import (
            load_user_data as _load_user,
            save_user_data as _save_user,
            load_all_users_data as _load_all_users,
        )
        from task_manager import (
            create_task as _create_task,
            complete_task as _complete_task,
            fail_task as _fail_task,
            get_all_tasks as _get_all_tasks,
            get_task_stats as _get_task_stats,
            register_or_login_user as _register_user,
        )
    else:
        print(f" 数据访问层初始化：API 模式 (后端: {BACKEND_URL})")
        
        def _make_api_request(endpoint: str, params: dict = None, method: str = "get", json: dict = None) -> dict:
            """发送 API 请求到后端（支持 GET/POST/PUT）"""
            try:
                # 根据端点自动选择前缀
                # /users/by-device → /api/admin/users/by-device
                # /users/{id}/claim-free → /api/admin/users/{id}/claim-free
                url = f"{BACKEND_URL}/api/admin{endpoint}"
                logger.info(f"🌐 API请求: {method.upper()} {url}")
                
                if method.lower() == "get":
                    response = requests.get(url, params=params, timeout=10)
                elif method.lower() == "post":
                    response = requests.post(url, json=json, timeout=10)
                elif method.lower() == "put":
                    response = requests.put(url, json=json, timeout=10)
                else:
                    response = requests.get(url, params=params, timeout=10)
                        
                response.raise_for_status()
                result = response.json()
                logger.info(f"✅ API响应成功: {endpoint}")
                return result
            except requests.exceptions.Timeout:
                logger.error(f"⏰ API请求超时 (10秒): {method.upper()} {endpoint}")
                return {}
            except requests.exceptions.ConnectionError as e:
                logger.error(f"❌ API连接失败: {method.upper()} {endpoint} - {e}")
                return {}
            except requests.exceptions.HTTPError as e:
                logger.error(f"❌ API HTTP错误: {method.upper()} {endpoint} - {e.response.status_code} - {e.response.text}")
                return {}
            except Exception as e:
                logger.error(f"❌ API请求异常: {method.upper()} {endpoint} - {type(e).__name__}: {e}")
                return {}
        
        def _load_user(user_id: str) -> Dict[str, Any]:
            """
            从 API 加载用户数据
            
            ⚠️ 安全修复：不再使用user_id作为查询参数，改用device_fingerprint
            防止用户通过修改URL参数获取其他用户数据
            
            ✅ 防御性编程：失败时返回默认用户数据，而不是None
            """
            # 🔧 从session_state获取device_fingerprint（需要在调用前设置）
            import streamlit as st
            device_fingerprint = st.session_state.get('device_fingerprint', '')
            
            # ✅ 默认用户数据（用于降级）
            default_user_data = {
                'user_id': user_id or 'unknown',
                'balance': 0.0,
                'paragraphs_remaining': 0,
                'total_paragraphs_used': 0,
                'total_converted': 0,
                'is_active': False,
                'created_at': '',
                'last_login': '',
                'conversion_history': [],
                'style_mappings': {},
            }
            
            if not device_fingerprint:
                logger.warning("⚠️ API模式缺少device_fingerprint，返回默认用户数据")
                return default_user_data
            
            # 调用 /users/by-device 接口，通过设备指纹获取用户
            result = _make_api_request(
                "/users/by-device",
                method="post",
                json={"device_fingerprint": device_fingerprint}
            )
            
            if result.get('success'):
                # ✅ 修复：后端返回的是扁平结构，不是嵌套的'user'字段
                # 需要正确解析后端返回的用户数据
                if 'user' in result:
                    # 如果后端返回嵌套结构，直接使用
                    return result['user']
                else:
                    # 后端返回扁平结构，构造完整的用户数据字典
                    return {
                        'user_id': result.get('user_id', user_id or 'unknown'),
                        'balance': float(result.get('balance', 0)),
                        'paragraphs_remaining': int(result.get('paragraphs_remaining', 0)),
                        'total_paragraphs_used': int(result.get('total_paragraphs_used', 0)),
                        'total_converted': int(result.get('total_converted', 0)),
                        'is_active': True,
                        'created_at': result.get('created_at', ''),
                        'last_login': result.get('last_login', ''),
                        'conversion_history': [],
                        'style_mappings': {},
                    }
            
            # ✅ API请求失败时返回默认用户数据
            logger.warning(f"⚠️ API请求失败，返回默认用户数据: {user_id}")
            return default_user_data
        
        def _save_user(user_data: Dict[str, Any], user_id: str = None):
            """保存用户数据到 API"""
            if user_id:
                return _make_api_request(f"/users/{user_id}", method="post", json=user_data)
            return {}
        
        def _load_all_users() -> List[Dict[str, Any]]:
            """从 API 加载所有用户"""
            result = _make_api_request("/users", params={"limit": 1000})
            return result.get('users', [])
        
        def _register_user(user_id: str, user_data: Dict[str, Any]):
            """注册用户（API 模式）"""
            return _save_user(user_data, user_id)
        
        def _claim_free(user_id=None):
            """领取免费段落（API 模式）"""
            if user_id:
                logger.info(f"🌐 API请求: POST /users/{user_id}/claim-free")
                result = _make_api_request(f"/users/{user_id}/claim-free", method="post")
                logger.info(f"🔍 API响应: {result}")
                if result.get('success'):
                    paragraphs = result.get('paragraphs', 0)
                    logger.info(f"✅ 领取成功: {paragraphs} 段落")
                    return paragraphs
                else:
                    logger.warning(f"⚠️ 领取失败: {result.get('error', '未知错误')}")
            return 0
        
        def _recharge_user(amount, package_label, user_id=None):
            """充值用户（API 模式）"""
            pass
        
        def _deduct_paragraphs(paragraphs, user_id=None):
            """扣除段落（API 模式）"""
            if user_id:
                result = _make_api_request(f"/users/{user_id}/deduct", method="post", json={"paragraphs": paragraphs})
                return result.get('success', False)
            return False
        
        def _add_conversion_record(files_count, success_count, failed_count, user_id=None):
            """添加转换记录（API 模式）"""
            pass
        
        def _get_user_stats(user_id=None) -> Dict[str, Any]:
            """获取用户统计（API 模式）"""
            return {}
        
        def _generate_user_id():
            """生成用户ID（API 模式）"""
            import uuid
            return str(uuid.uuid4())
        
        def _get_or_create_user_by_device(device_fingerprint: str, user_agent: str = None) -> Dict[str, Any]:
            """
            通过设备指纹获取或创建用户（API模式）
            
            Args:
                device_fingerprint: 设备指纹（32位MD5）
                user_agent: User-Agent字符串（可选，用于日志）
            
            Returns:
                用户数据字典
            """
            result = _make_api_request(
                "/users/by-device", 
                method="post", 
                json={
                    "device_fingerprint": device_fingerprint,
                    "user_agent": user_agent
                }
            )
            
            # 🔧 检查API请求是否成功
            if not result:
                logger.error(f"❌ API返回空结果，可能是后端服务不可用或网络超时")
                raise Exception("API请求失败：后端服务不可用或网络超时")
            
            if result.get('success'):
                return {
                    'user_id': result['user_id'],
                    'balance': result.get('balance', 0.0),
                    'paragraphs_remaining': result.get('paragraphs_remaining', 0),
                    'total_paragraphs_used': 0,
                    'total_converted': result.get('total_converted', 0),
                    'is_active': True,
                    'created_at': '',
                    'last_login': '',
                    'conversion_history': [],  # ✅ 添加转换历史字段
                }
            else:
                error_msg = result.get('message', '未知错误')
                logger.error(f"❌ API返回失败: {error_msg}")
                raise Exception(f"API返回失败: {error_msg}")
        
        def _create_task(task_id, user_id, filename, file_count=1, paragraphs=0, cost=0.0):
            """创建任务（API 模式）"""
            task_data = {
                'task_id': task_id,
                'user_id': user_id,
                'filename': filename,
                'paragraphs': paragraphs,
                'cost': cost
            }
            result = _make_api_request("/tasks", method="post", json=task_data)
            return task_id if result.get('success') else None
        
        def _update_task_status(task_id, status, progress=None, error_message=None):
            """更新任务状态（API 模式）"""
            status_data = {'status': status}
            if progress is not None:
                status_data['progress'] = progress
            if error_message is not None:
                status_data['error_message'] = error_message
            
            result = _make_api_request(f"/tasks/{task_id}", method="put", json=status_data)
            return result.get('success', False)
        
        def _complete_task(task_id):
            """完成任务（API 模式）"""
            return _update_task_status(task_id, 'COMPLETED', progress=100)
        
        def _fail_task(task_id, error_message=""):
            """标记任务失败（API 模式）"""
            return _update_task_status(task_id, 'FAILED', error_message=error_message)
        
        def _get_all_tasks(status_filter=None, limit=100, offset=0):
            """从 API 获取所有任务"""
            params = {"skip": offset, "limit": limit}
            if status_filter and status_filter != 'ALL':
                params['status_filter'] = status_filter
            
            result = _make_api_request("/tasks", params=params)
            return result.get('tasks', [])
        
        def _get_task_stats() -> Dict[str, Any]:
            """从 API 获取任务统计"""
            return _make_api_request("/task-stats")
        
        def _get_user_active_task(user_id):
            """获取用户活动任务（API 模式）"""
            tasks = _get_all_tasks(status_filter='PROCESSING', limit=100)
            for task in tasks:
                if task.get('user_id') == user_id:
                    return task
            return None
        
        def _get_user_completed_tasks(user_id, limit=20):
            """获取用户已完成任务（API 模式）"""
            tasks = _get_all_tasks(status_filter='COMPLETED', limit=limit)
            return [t for t in tasks if t.get('user_id') == user_id]
        
        def _has_active_task(user_id):
            """检查用户是否有活动任务（API 模式）"""
            return False
        
        def _cleanup_expired_tasks():
            """清理过期任务（API 模式）"""
            return 0

# ==================== 统一 API ====================

def load_user_data(user_id: str) -> Optional[Dict[str, Any]]:
    """加载用户数据"""
    return _load_user(user_id)

def save_user_data(user_data: Dict[str, Any], user_id: str = None):
    """保存用户数据"""
    return _save_user(user_data, user_id)

def load_all_users_data() -> List[Dict[str, Any]]:
    """加载所有用户数据"""
    return _load_all_users()

def register_or_login_user(user_id: str, user_data: Dict[str, Any]):
    """注册用户或更新登录时间"""
    return _register_user(user_id, user_data)

def claim_free_paragraphs(user_id=None):
    """领取免费段落"""
    return _claim_free(user_id)

def recharge_user(amount, package_label, user_id=None):
    """充值用户"""
    return _recharge_user(amount, package_label, user_id)

def deduct_paragraphs(paragraphs, user_id=None):
    """扣除段落"""
    return _deduct_paragraphs(paragraphs, user_id)

def add_conversion_record(files_count, success_count, failed_count, user_id=None):
    """添加转换记录"""
    return _add_conversion_record(files_count, success_count, failed_count, user_id)

def get_user_stats(user_id=None):
    """获取用户统计"""
    return _get_user_stats(user_id)

def generate_user_id():
    """生成用户ID"""
    return _generate_user_id()

def create_task(*args, **kwargs):
    """创建转换任务"""
    return _create_task(*args, **kwargs)

def update_task_status(*args, **kwargs):
    """更新任务状态"""
    return _update_task_status(*args, **kwargs)

def complete_task(*args, **kwargs):
    """标记任务完成"""
    return _complete_task(*args, **kwargs)

def fail_task(*args, **kwargs):
    """标记任务失败"""
    return _fail_task(*args, **kwargs)

def get_all_tasks(status_filter=None, limit=100, offset=0):
    """获取所有任务"""
    return _get_all_tasks(status_filter=status_filter, limit=limit, offset=offset)

def get_task_stats():
    """获取任务统计"""
    return _get_task_stats()

def get_user_active_task(user_id):
    """获取用户活动任务"""
    return _get_user_active_task(user_id)

def get_user_completed_tasks(user_id, limit=20):
    """获取用户已完成任务"""
    return _get_user_completed_tasks(user_id, limit)

def has_active_task(user_id):
    """检查用户是否有活动任务"""
    return _has_active_task(user_id)

def cleanup_expired_tasks():
    """清理过期任务"""
    return _cleanup_expired_tasks()

# ==================== 导出当前数据源类型 ====================
def get_data_source():
    """获取当前数据源类型"""
    return DATA_SOURCE

def get_or_create_user_by_device(device_fingerprint: str, user_agent: str = None) -> Dict[str, Any]:
    """
    通过设备指纹获取或创建用户（统一接口）
    
    Args:
        device_fingerprint: 设备指纹（32位MD5）
        user_agent: User-Agent字符串（可选，用于日志）
    
    Returns:
        用户数据字典
    """
    # 根据不同数据源调用对应的实现
    if DATA_SOURCE == "api":
        return _get_or_create_user_by_device(device_fingerprint, user_agent)
    elif DATA_SOURCE == "supabase":
        # Supabase模式直接使用已有的实现
        from backend.app.core.database import SessionLocal
        from config import FREE_PARAGRAPHS_DAILY
        from datetime import datetime
        import hashlib
        
        db = SessionLocal()
        try:
            # 优先通过device_fingerprint查询
            user = db.query(User).filter(User.device_fingerprint == device_fingerprint).first()
            
            if user:
                # 用户已存在，更新last_login
                user.last_login = datetime.now()
                db.commit()
                
                user_data = {
                    'user_id': user.id,
                    'balance': float(user.balance or 0),
                    'paragraphs_remaining': int(user.paragraphs_remaining or 0),
                    'total_paragraphs_used': int(user.total_paragraphs_used or 0),
                    'total_converted': int(user.total_converted or 0),
                    'is_active': bool(user.is_active),
                    'created_at': user.created_at.isoformat() if user.created_at else '',
                    'last_login': user.last_login.isoformat() if user.last_login else '',
                    'conversion_history': [],  # ✅ 添加转换历史字段
                }
                
                return user_data
            
            # 用户不存在，创建新用户
            user_id = hashlib.md5(f"wordstyle_device_{device_fingerprint}".encode()).hexdigest()[:12]
            
            new_user = User(
                id=user_id,
                device_fingerprint=device_fingerprint,
                balance=0.0,
                paragraphs_remaining=FREE_PARAGRAPHS_DAILY,
                total_paragraphs_used=0,
                total_converted=0,
                is_active=True,
                created_at=datetime.now(),
                last_login=datetime.now(),
            )
            
            db.add(new_user)
            db.commit()
            
            return {
                'user_id': user_id,
                'balance': 0.0,
                'paragraphs_remaining': FREE_PARAGRAPHS_DAILY,
                'total_paragraphs_used': 0,
                'total_converted': 0,
                'is_active': True,
                'created_at': datetime.now().isoformat(),
                'last_login': datetime.now().isoformat(),
                'conversion_history': [],  # ✅ 添加转换历史字段
            }
        finally:
            db.close()
    elif DATA_SOURCE == "local":
        # Local模式使用JSON文件存储
        return _get_or_create_user_by_device(device_fingerprint, user_agent)
    else:
        raise ValueError(f"未知的数据源模式: {DATA_SOURCE}")

# ==================== 设备指纹相关辅助函数 ====================

def generate_device_fingerprint(user_agent: str) -> str:
    """
    生成设备指纹
    
    Args:
        user_agent: 浏览器的User-Agent字符串
    
    Returns:
        32位MD5哈希字符串
    """
    import hashlib
    return hashlib.md5(user_agent.encode('utf-8')).hexdigest()[:32]
