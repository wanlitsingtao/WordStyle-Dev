# -*- coding: utf-8 -*-
"""
用户管理模块
负责用户数据管理、充值、免费额度等功能
"""
import json
import hashlib
import time
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
import os

# 导入Streamlit用于缓存
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

from config import (
    USER_DATA_FILE, FREE_PARAGRAPHS_DAILY, PARAGRAPH_PRICE,
    CACHE_TTL_SECONDS, LOCK_TIMEOUT_SECONDS
)
import logging

logger = logging.getLogger('WordStyle')


@contextmanager
def file_lock(file_path, timeout=LOCK_TIMEOUT_SECONDS):
    """
    文件锁上下文管理器，确保并发安全
    :param file_path: 文件路径
    :param timeout: 超时时间（秒）
    """
    lock_file = Path(str(file_path) + '.lock')
    start_time = datetime.now()
    
    try:
        # 尝试获取锁
        while True:
            try:
                # 以独占模式创建锁文件
                fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.close(fd)
                break
            except FileExistsError:
                # 检查锁是否过期（防止死锁）
                if lock_file.exists():
                    lock_age = (datetime.now() - datetime.fromtimestamp(lock_file.stat().st_ctime)).total_seconds()
                    if lock_age > timeout:
                        # 锁已过期，强制删除
                        try:
                            lock_file.unlink()
                            logger.warning(f"强制释放过期锁: {lock_file}")
                            continue
                        except:
                            pass
                
                # 等待后重试
                if (datetime.now() - start_time).total_seconds() > timeout:
                    raise TimeoutError(f"获取文件锁超时: {file_path}")
                time.sleep(0.1)
        
        yield  # 执行受保护的代码
        
    finally:
        # 释放锁
        try:
            if lock_file.exists():
                lock_file.unlink()
        except:
            pass


def generate_user_id():
    """
    生成稳定的用户ID
    注意：此函数仅在 app.py 初始化时调用一次
    实际使用时应该从 st.session_state.user_id 获取
    """
    import streamlit as st
    
    # 如果 session_state 中已有 user_id，直接返回
    if 'user_id' in st.session_state:
        return st.session_state.user_id
    
    # 否则生成一个基于固定种子的 ID（仅用于首次初始化）
    import hashlib
    import socket
    
    try:
        hostname = socket.gethostname()
    except:
        hostname = "default"
    
    unique_key = f"wordstyle_{hostname}_first_user"
    user_id = hashlib.md5(unique_key.encode()).hexdigest()[:12]
    st.session_state.user_id = user_id
    
    return user_id


# ==================== 缓存优化 ====================

def _load_user_data_from_file(user_id=None):
    """
    从文件加载用户数据（不带缓存，供cache_data装饰器使用）
    :param user_id: 用户ID，如果为None则生成新的
    :return: 用户数据字典
    """
    if user_id is None:
        user_id = generate_user_id()
    
    with file_lock(USER_DATA_FILE):
        if USER_DATA_FILE.exists():
            try:
                with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
                    return all_data.get(user_id, _get_default_user_data())
            except Exception as e:
                logger.error(f"加载用户数据失败: {e}")
                return _get_default_user_data()
        else:
            return _get_default_user_data()


# 如果Streamlit可用，创建带缓存的版本
if STREAMLIT_AVAILABLE:
    @st.cache_data(ttl=CACHE_TTL_SECONDS)
    def load_user_data_cached(user_id=None):
        """
        带缓存的用户数据加载（推荐）
        使用@st.cache_data装饰器，自动管理缓存生命周期
        :param user_id: 用户ID
        :return: 用户数据字典
        """
        return _load_user_data_from_file(user_id)
else:
    # 如果Streamlit不可用，回退到原始版本
    load_user_data_cached = _load_user_data_from_file


def load_user_data(user_id=None):
    """加载用户数据（基于浏览器会话）"""
    import streamlit as st
    
    if user_id is None:
        user_id = generate_user_id()
    
    # 使用缓存减少文件读取
    cache_key = f"user_data_{user_id}"
    if cache_key in st.session_state:
        cached_data, cache_time = st.session_state[cache_key]
        # 缓存有效期
        if (datetime.now() - cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return cached_data
    
    # 使用文件锁确保并发安全
    with file_lock(USER_DATA_FILE):
        if USER_DATA_FILE.exists():
            try:
                with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
                    user_data = all_data.get(user_id, _get_default_user_data())
                    # 更新缓存
                    st.session_state[cache_key] = (user_data, datetime.now())
                    return user_data
            except json.JSONDecodeError as e:
                logger.error(f"用户数据JSON解析失败: {e}")
                return _get_default_user_data()
            except Exception as e:
                logger.error(f"加载用户数据失败: {e}")
                return _get_default_user_data()
        else:
            return _get_default_user_data()


def save_user_data(user_data, user_id=None):
    """保存用户数据（带文件锁和错误处理）"""
    import streamlit as st
    
    if user_id is None:
        user_id = generate_user_id()
    
    # 清除缓存
    cache_key = f"user_data_{user_id}"
    if cache_key in st.session_state:
        del st.session_state[cache_key]
    
    # 使用文件锁确保并发安全
    with file_lock(USER_DATA_FILE):
        all_data = {}
        if USER_DATA_FILE.exists():
            try:
                with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"读取用户数据失败，将创建新文件: {e}")
                all_data = {}
            except Exception as e:
                logger.error(f"读取用户数据异常: {e}")
                all_data = {}
        
        all_data[user_id] = user_data
        
        # 原子写入：先写临时文件，再重命名
        temp_file = USER_DATA_FILE.with_suffix('.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            # 原子替换
            temp_file.replace(USER_DATA_FILE)
            logger.debug(f"用户数据保存成功: {user_id}")
        except Exception as e:
            logger.error(f"保存用户数据失败: {e}")
            # 清理临时文件
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            raise


def _get_default_user_data():
    """获取默认用户数据结构"""
    return {
        'balance': 0.0,
        'paragraphs_remaining': 0,
        'total_converted': 0,
        'total_paragraphs_used': 0,
        'recharge_history': [],
        'conversion_history': [],
        'last_free_quota_date': '',
        'style_mappings': {}  # 样式映射配置
    }


def claim_free_paragraphs(user_id=None):
    """领取每日免费额度（每天固定额度，不累计）"""
    user_data = load_user_data(user_id)
    
    # 获取今天的日期
    today = datetime.now().strftime('%Y-%m-%d')
    last_claim_date = user_data.get('last_free_quota_date', '')
    
    # 检查是否是同一天
    if last_claim_date == today:
        # 今天已经领取过，不再重复领取
        return 0
    
    # 新的一天，重置免费额度
    free_paragraphs = FREE_PARAGRAPHS_DAILY
    
    # 设置今日免费额度（不累计，直接设置为固定值）
    user_data['paragraphs_remaining'] = free_paragraphs
    
    # 更新最后领取日期
    user_data['last_free_quota_date'] = today
    
    # 添加领取记录
    if 'free_quota_history' not in user_data:
        user_data['free_quota_history'] = []
    
    user_data['free_quota_history'].append({
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'amount': free_paragraphs,
        'type': 'daily_free_quota',
        'date': today
    })
    
    save_user_data(user_data, user_id)
    return free_paragraphs


def recharge_user(amount, package_label, user_id=None):
    """用户充值"""
    user_data = load_user_data(user_id)
    
    # 计算获得的段落数
    paragraphs_to_add = int(amount / PARAGRAPH_PRICE)
    
    # 更新余额和段落数
    user_data['balance'] += amount
    user_data['paragraphs_remaining'] += paragraphs_to_add
    
    # 记录充值历史
    recharge_record = {
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'amount': amount,
        'paragraphs': paragraphs_to_add,
        'package': package_label
    }
    user_data['recharge_history'].append(recharge_record)
    
    # 保存
    save_user_data(user_data, user_id)
    
    return paragraphs_to_add


def deduct_paragraphs(paragraphs, user_id=None):
    """扣除段落数（转换成功后调用）"""
    user_data = load_user_data(user_id)
    
    # 确保余额不会出现负数
    if user_data['paragraphs_remaining'] >= paragraphs:
        user_data['paragraphs_remaining'] -= paragraphs
    else:
        # 如果余额不足，只扣除剩余部分，最低为0
        user_data['paragraphs_remaining'] = 0
    
    # 更新使用统计
    user_data['total_paragraphs_used'] += paragraphs
    user_data['total_converted'] += 1
    
    save_user_data(user_data, user_id)


def add_conversion_record(files_count, success_count, failed_count, 
                          paragraphs_charged, cost, mode='foreground', user_id=None):
    """添加转换记录"""
    user_data = load_user_data(user_id)
    
    conversion_record = {
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'files': files_count,
        'success': success_count,
        'failed': failed_count,
        'paragraphs_charged': paragraphs_charged,
        'cost': cost,
        'mode': mode
    }
    
    user_data['conversion_history'].append(conversion_record)
    save_user_data(user_data, user_id)


def get_user_stats(user_id=None):
    """获取用户统计信息"""
    user_data = load_user_data(user_id)
    
    return {
        'balance': user_data['balance'],
        'paragraphs_remaining': user_data['paragraphs_remaining'],
        'total_converted': user_data['total_converted'],
        'total_paragraphs_used': user_data['total_paragraphs_used'],
        'recharge_count': len(user_data.get('recharge_history', [])),
        'conversion_count': len(user_data.get('conversion_history', []))
    }


def save_style_mappings(style_mappings, user_id=None):
    """保存样式映射配置"""
    user_data = load_user_data(user_id)
    user_data['style_mappings'] = style_mappings
    save_user_data(user_data, user_id)


def load_style_mappings(user_id=None):
    """加载样式映射配置"""
    user_data = load_user_data(user_id)
    return user_data.get('style_mappings', {})


def load_all_users_data():
    """
    加载所有用户数据（管理后台使用）
    :return: 用户数据列表
    """
    if not USER_DATA_FILE.exists():
        return []
    
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
            
            users = []
            for user_id, user_data in all_data.items():
                users.append({
                    'user_id': user_id,
                    'balance': user_data.get('balance', 0),
                    'paragraphs_remaining': user_data.get('paragraphs_remaining', 0),
                    'paragraphs_used': user_data.get('paragraphs_used', 0),
                    'total_converted': user_data.get('total_converted', 0),
                    'is_active': user_data.get('is_active', True),
                    'created_at': user_data.get('created_at', ''),
                    'last_login': user_data.get('last_login', ''),
                })
            
            return users
    except Exception as e:
        print(f"[WARN] 加载所有用户数据失败: {e}")
        return []


# 测试代码
if __name__ == "__main__":
    print("[WARN] 用户管理模块需要在Streamlit环境中运行")
    print("请使用: streamlit run user_manager.py 进行测试")
