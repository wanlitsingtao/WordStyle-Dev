# -*- coding: utf-8 -*-
"""
后台任务管理器
负责管理转换任务的队列、状态和文件清理
"""
import sqlite3
import os
import uuid
import threading
from datetime import datetime, timedelta
from pathlib import Path

# 数据库文件路径
DB_PATH = "conversion_tasks.db"
RESULTS_DIR = "conversion_results"

def init_database():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建任务表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversion_tasks (
            task_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_count INTEGER DEFAULT 1,
            paragraphs INTEGER,
            cost REAL,
            status TEXT DEFAULT 'PENDING',
            progress INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            output_files TEXT,
            error_message TEXT,
            expires_at TIMESTAMP
        )
    """)
    
    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_status 
        ON conversion_tasks(user_id, status)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_expires 
        ON conversion_tasks(expires_at)
    """)
    
    conn.commit()
    conn.close()
    
    # 创建结果目录
    os.makedirs(RESULTS_DIR, exist_ok=True)

def create_task(user_id, filename, file_count, paragraphs, cost):
    """创建新的转换任务"""
    task_id = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(days=7)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO conversion_tasks 
        (task_id, user_id, filename, file_count, paragraphs, cost, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (task_id, user_id, filename, file_count, paragraphs, cost, expires_at))
    
    conn.commit()
    conn.close()
    
    return task_id

def update_task_status(task_id, status, progress=None, error_message=None):
    """更新任务状态"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if status == 'PROCESSING' and progress is None:
        progress = 0
        cursor.execute("""
            UPDATE conversion_tasks 
            SET status = ?, started_at = CURRENT_TIMESTAMP, progress = ?
            WHERE task_id = ?
        """, (status, progress, task_id))
    elif progress is not None:
        cursor.execute("""
            UPDATE conversion_tasks 
            SET status = ?, progress = ?
            WHERE task_id = ?
        """, (status, progress, task_id))
    else:
        cursor.execute("""
            UPDATE conversion_tasks 
            SET status = ?
            WHERE task_id = ?
        """, (status, task_id))
    
    if error_message:
        cursor.execute("""
            UPDATE conversion_tasks 
            SET error_message = ?
            WHERE task_id = ?
        """, (error_message, task_id))
    
    conn.commit()
    conn.close()

def complete_task(task_id, output_files):
    """完成任务"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # output_files 是列表，转换为JSON字符串存储
    import json
    output_files_json = json.dumps(output_files)
    
    cursor.execute("""
        UPDATE conversion_tasks 
        SET status = 'COMPLETED', 
            completed_at = CURRENT_TIMESTAMP,
            output_files = ?
        WHERE task_id = ?
    """, (output_files_json, task_id))
    
    conn.commit()
    conn.close()

def fail_task(task_id, error_message):
    """标记任务失败"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE conversion_tasks 
        SET status = 'FAILED', 
            completed_at = CURRENT_TIMESTAMP,
            error_message = ?
        WHERE task_id = ?
    """, (error_message, task_id))
    
    conn.commit()
    conn.close()

def get_user_active_task(user_id):
    """获取用户当前进行中的任务（PENDING或PROCESSING）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT task_id, status, progress, filename, created_at
        FROM conversion_tasks
        WHERE user_id = ? AND status IN ('PENDING', 'PROCESSING')
        ORDER BY created_at DESC
        LIMIT 1
    """, (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'task_id': result[0],
            'status': result[1],
            'progress': result[2],
            'filename': result[3],
            'created_at': result[4]
        }
    return None

def get_user_completed_tasks(user_id, limit=20):
    """获取用户已完成的任务历史"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT task_id, filename, file_count, paragraphs, cost, 
               status, progress, created_at, completed_at, output_files, error_message
        FROM conversion_tasks
        WHERE user_id = ? AND status IN ('COMPLETED', 'FAILED')
        ORDER BY created_at DESC
        LIMIT ?
    """, (user_id, limit))
    
    results = cursor.fetchall()
    conn.close()
    
    tasks = []
    for row in results:
        import json
        output_files = json.loads(row[9]) if row[9] else []
        
        tasks.append({
            'task_id': row[0],
            'filename': row[1],
            'file_count': row[2],
            'paragraphs': row[3],
            'cost': row[4],
            'status': row[5],
            'progress': row[6],
            'created_at': row[7],
            'completed_at': row[8],
            'output_files': output_files,
            'error_message': row[10]
        })
    
    return tasks

def get_task_by_id(task_id):
    """根据ID获取任务详情"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM conversion_tasks WHERE task_id = ?
    """, (task_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        import json
        return {
            'task_id': row[0],
            'user_id': row[1],
            'filename': row[2],
            'file_count': row[3],
            'paragraphs': row[4],
            'cost': row[5],
            'status': row[6],
            'progress': row[7],
            'created_at': row[8],
            'started_at': row[9],
            'completed_at': row[10],
            'output_files': json.loads(row[11]) if row[11] else [],
            'error_message': row[12],
            'expires_at': row[13]
        }
    return None

def cleanup_expired_tasks():
    """清理过期任务和文件（7天前）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 查询过期的任务
    cursor.execute("""
        SELECT task_id, output_files FROM conversion_tasks 
        WHERE expires_at < datetime('now')
    """)
    
    expired_tasks = cursor.fetchall()
    
    for task_id, output_files_json in expired_tasks:
        # 删除文件
        if output_files_json:
            import json
            output_files = json.loads(output_files_json)
            for filepath in output_files:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception as e:
                    print(f"删除文件失败 {filepath}: {e}")
        
        # 删除记录
        cursor.execute("DELETE FROM conversion_tasks WHERE task_id = ?", (task_id,))
    
    conn.commit()
    conn.close()
    
    return len(expired_tasks)

def has_active_task(user_id):
    """检查用户是否有进行中的任务"""
    return get_user_active_task(user_id) is not None


def register_or_login_user(user_id, user_data):
    """
    用户首次访问时注册或更新登录时间
    :param user_id: 用户ID
    :param user_data: 用户数据字典（从JSON读取）
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 检查用户是否存在
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            # 更新最后登录时间和用户信息
            cursor.execute("""
                UPDATE users 
                SET balance = ?,
                    paragraphs_remaining = ?,
                    total_converted = ?,
                    total_paragraphs_used = ?,
                    last_login = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            """, (
                user_data.get('balance', 0.0),
                user_data.get('paragraphs_remaining', 0),
                user_data.get('total_converted', 0),
                user_data.get('paragraphs_used', 0),
                user_id
            ))
        else:
            # 创建新用户
            cursor.execute("""
                INSERT INTO users (
                    user_id, balance, paragraphs_remaining,
                    total_converted, total_paragraphs_used,
                    created_at, last_login
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                user_id,
                user_data.get('balance', 0.0),
                user_data.get('paragraphs_remaining', 0),
                user_data.get('total_converted', 0),
                user_data.get('paragraphs_used', 0)
            ))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[WARN] 注册用户失败: {e}")
    finally:
        conn.close()


def get_all_tasks(status_filter=None, limit=100, offset=0):
    """
    获取所有任务（管理后台使用）
    :param status_filter: 状态过滤 ('ALL', 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')
    :param limit: 返回数量限制
    :param offset: 偏移量
    :return: 任务列表
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 构建查询
    if status_filter and status_filter != 'ALL':
        cursor.execute("""
            SELECT task_id, user_id, filename, file_count, paragraphs, cost, 
                   status, progress, created_at, completed_at, error_message
            FROM conversion_tasks
            WHERE status = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (status_filter, limit, offset))
    else:
        cursor.execute("""
            SELECT task_id, user_id, filename, file_count, paragraphs, cost, 
                   status, progress, created_at, completed_at, error_message
            FROM conversion_tasks
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
    
    rows = cursor.fetchall()
    conn.close()
    
    tasks = []
    for row in rows:
        tasks.append({
            'task_id': row[0],
            'user_id': row[1],
            'filename': row[2],
            'file_count': row[3],
            'paragraphs': row[4],
            'cost': row[5],
            'status': row[6],
            'progress': row[7],
            'created_at': row[8],
            'completed_at': row[9],
            'error_message': row[10],
        })
    
    return tasks


def get_task_stats():
    """
    获取任务统计信息（管理后台使用）
    :return: 统计字典
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 总任务数
    cursor.execute("SELECT COUNT(*) FROM conversion_tasks")
    total = cursor.fetchone()[0]
    
    # 各状态任务数
    cursor.execute("SELECT COUNT(*) FROM conversion_tasks WHERE status = 'COMPLETED'")
    completed = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM conversion_tasks WHERE status = 'PROCESSING'")
    processing = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM conversion_tasks WHERE status = 'PENDING'")
    pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM conversion_tasks WHERE status = 'FAILED'")
    failed = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_tasks': total,
        'completed_tasks': completed,
        'processing_tasks': processing,
        'pending_tasks': pending,
        'failed_tasks': failed,
    }


# 初始化数据库
init_database()
