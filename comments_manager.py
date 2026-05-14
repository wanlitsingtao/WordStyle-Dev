# -*- coding: utf-8 -*-
"""
评论系统管理模块
负责评论的增删改查、点赞等功能
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from config import COMMENTS_FILE, MAX_COMMENT_LENGTH, COMMENTS_PER_PAGE, LOCK_TIMEOUT_SECONDS
from utils import sanitize_html
import logging

logger = logging.getLogger('WordStyle')


# 文件锁机制（与user_manager中相同）
from contextlib import contextmanager

@contextmanager
def file_lock(file_path, timeout=LOCK_TIMEOUT_SECONDS):
    """文件锁上下文管理器，确保并发安全"""
    lock_file = Path(str(file_path) + '.lock')
    start_time = datetime.now()
    
    try:
        while True:
            try:
                fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.close(fd)
                break
            except FileExistsError:
                if lock_file.exists():
                    lock_age = (datetime.now() - datetime.fromtimestamp(lock_file.stat().st_ctime)).total_seconds()
                    if lock_age > timeout:
                        try:
                            lock_file.unlink()
                            logger.warning(f"强制释放过期锁: {lock_file}")
                            continue
                        except:
                            pass
                
                if (datetime.now() - start_time).total_seconds() > timeout:
                    raise TimeoutError(f"获取文件锁超时: {file_path}")
                time.sleep(0.1)
        
        yield
        
    finally:
        try:
            if lock_file.exists():
                lock_file.unlink()
        except:
            pass


def load_comments():
    """加载评论数据（带文件锁）"""
    with file_lock(COMMENTS_FILE):
        if COMMENTS_FILE.exists():
            try:
                with open(COMMENTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"评论数据JSON解析失败: {e}")
                return []
            except Exception as e:
                logger.error(f"加载评论数据失败: {e}")
                return []
        return []


def save_comments(comments):
    """保存评论数据（带文件锁和原子写入）"""
    with file_lock(COMMENTS_FILE):
        # 原子写入：先写临时文件，再重命名
        temp_file = COMMENTS_FILE.with_suffix('.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(comments, f, ensure_ascii=False, indent=2)
            # 原子替换
            temp_file.replace(COMMENTS_FILE)
            logger.debug("评论数据保存成功")
        except Exception as e:
            logger.error(f"保存评论数据失败: {e}")
            # 清理临时文件
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            raise


def add_comment(username, content, rating=5, user_id=None):
    """添加新评论"""
    comments = load_comments()
    
    # HTML转义防止XSS
    safe_content = sanitize_html(content)
    safe_username = sanitize_html(username) if username else f'用户{user_id[:6] if user_id else "匿名"}'
    
    new_comment = {
        'id': len(comments) + 1,
        'username': safe_username,
        'content': safe_content,
        'rating': rating,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'likes': 0,
        'user_id': user_id
    }
    
    comments.append(new_comment)
    save_comments(comments)
    return new_comment


def like_comment(comment_id):
    """点赞评论"""
    comments = load_comments()
    for comment in comments:
        if comment['id'] == comment_id:
            comment['likes'] += 1
            break
    save_comments(comments)


def delete_comment(comment_id):
    """删除评论（管理员功能）"""
    comments = load_comments()
    comments = [c for c in comments if c['id'] != comment_id]
    # 重新编号
    for idx, comment in enumerate(comments, 1):
        comment['id'] = idx
    save_comments(comments)
    return len(comments)


def get_comments(page=1, per_page=COMMENTS_PER_PAGE):
    """获取分页评论列表"""
    comments = load_comments()
    # 按时间倒序排序
    comments_sorted = sorted(comments, key=lambda x: x['timestamp'], reverse=True)
    
    # 分页
    start = (page - 1) * per_page
    end = start + per_page
    return comments_sorted[start:end], len(comments_sorted)


def get_comment_stats():
    """获取评论统计信息"""
    comments = load_comments()
    
    if not comments:
        return {
            'total_comments': 0,
            'avg_rating': 0,
            'total_likes': 0
        }
    
    total_comments = len(comments)
    avg_rating = sum(c.get('rating', 5) for c in comments) / total_comments
    total_likes = sum(c.get('likes', 0) for c in comments)
    
    return {
        'total_comments': total_comments,
        'avg_rating': round(avg_rating, 1),
        'total_likes': total_likes
    }


def validate_comment_content(content):
    """验证评论内容"""
    if not content or not content.strip():
        return False, "评论内容不能为空"
    
    if len(content) > MAX_COMMENT_LENGTH:
        return False, f"评论内容过长，最多{MAX_COMMENT_LENGTH}个字符"
    
    return True, None


# 测试代码
if __name__ == "__main__":
    print("测试评论系统...")
    
    # 测试添加评论
    comment = add_comment("测试用户", "这是一个测试评论", 5, "test_user_123")
    print(f"✅ 添加评论成功: ID={comment['id']}")
    
    # 测试获取统计
    stats = get_comment_stats()
    print(f"📊 评论统计: {stats}")
    
    # 测试点赞
    like_comment(comment['id'])
    print(f"👍 点赞成功")
    
    # 测试获取评论列表
    comments, total = get_comments()
    print(f"📝 获取评论列表: {len(comments)} 条评论，共 {total} 条")
    
    print("\n✅ 所有测试通过！")


# ==================== 反馈管理功能 ====================

FEEDBACK_FILE = Path("feedback_data.json")


def load_feedbacks():
    """加载反馈数据（带文件锁）"""
    with file_lock(FEEDBACK_FILE):
        if FEEDBACK_FILE.exists():
            try:
                with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"反馈数据JSON解析失败: {e}")
                return []
            except Exception as e:
                logger.error(f"加载反馈数据失败: {e}")
                return []
        return []


def save_feedbacks(feedbacks):
    """保存反馈数据（带文件锁和原子写入）"""
    with file_lock(FEEDBACK_FILE):
        # 原子写入：先写临时文件，再重命名
        temp_file = FEEDBACK_FILE.with_suffix('.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(feedbacks, f, ensure_ascii=False, indent=2)
            # 原子替换
            temp_file.replace(FEEDBACK_FILE)
            logger.debug("反馈数据保存成功")
        except Exception as e:
            logger.error(f"保存反馈数据失败: {e}")
            # 清理临时文件
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            raise


def add_feedback(user_id, feedback_type, title, description, contact=''):
    """添加新反馈"""
    feedbacks = load_feedbacks()
    
    # HTML转义防止XSS
    safe_title = sanitize_html(title)
    safe_description = sanitize_html(description)
    safe_contact = sanitize_html(contact)
    
    new_feedback = {
        'id': len(feedbacks) + 1,
        'user_id': user_id,
        'feedback_type': feedback_type,
        'title': safe_title,
        'description': safe_description,
        'contact': safe_contact,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'pending'  # pending, processing, resolved
    }
    
    feedbacks.append(new_feedback)
    save_feedbacks(feedbacks)
    
    logger.info(f"用户 {user_id} 提交了反馈: {safe_title}")
    return new_feedback


def get_feedbacks(page=1, per_page=20):
    """获取反馈列表（分页）"""
    feedbacks = load_feedbacks()
    
    # 按时间倒序排列
    feedbacks.sort(key=lambda x: x['timestamp'], reverse=True)
    
    total = len(feedbacks)
    start = (page - 1) * per_page
    end = start + per_page
    
    return feedbacks[start:end], total


def get_feedback_stats():
    """获取反馈统计信息"""
    feedbacks = load_feedbacks()
    
    stats = {
        'total': len(feedbacks),
        'by_type': {},
        'by_status': {}
    }
    
    for fb in feedbacks:
        # 按类型统计
        fb_type = fb.get('feedback_type', 'other')
        stats['by_type'][fb_type] = stats['by_type'].get(fb_type, 0) + 1
        
        # 按状态统计
        fb_status = fb.get('status', 'pending')
        stats['by_status'][fb_status] = stats['by_status'].get(fb_status, 0) + 1
    
    return stats
