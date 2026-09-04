# -*- coding: utf-8 -*-
"""
用户评价页（T03 / 从 app.py 迁移）
统计 / 发表评论 / 评论列表 / 点赞。
"""
import json
import logging
from datetime import datetime
from pathlib import Path

import streamlit as st

from state import app_state
from utils import sanitize_html

logger = logging.getLogger('WordStyle')

COMMENTS_FILE = Path("comments_data.json")


def load_comments():
    """加载评论数据（优先从API获取）"""
    from config import BACKEND_URL, DATA_SOURCE

    if BACKEND_URL and DATA_SOURCE == 'api':
        try:
            import requests
            api_url = f"{BACKEND_URL.rstrip('/')}/api/comments/comments/list?limit=100"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            comments = response.json()
            for c in comments:
                if isinstance(c.get('id'), str) and len(c['id']) > 20:
                    c['display_id'] = c['id'][:8]
            return comments
        except Exception as e:
            logger.error(f"[ERROR] API加载评论失败: {e}，降级到本地文件")

    if COMMENTS_FILE.exists():
        with open(COMMENTS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []


def save_comments(comments):
    """保存评论数据"""
    with open(COMMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(comments, f, ensure_ascii=False, indent=2)


def add_comment(username, content, rating=5):
    """添加新评论（使用API提交到数据库）"""
    from config import BACKEND_URL, DATA_SOURCE

    if BACKEND_URL and DATA_SOURCE == 'api':
        try:
            import requests
            api_url = f"{BACKEND_URL.rstrip('/')}/api/comments/comments/submit"
            logger.info(f"[INFO] 尝试调用API: {api_url}")
            response = requests.post(
                api_url,
                json={
                    'username': username or f'用户{app_state.get_user_id()[:6]}',
                    'content': content,
                    'rating': rating,
                    'user_id': app_state.get_user_id()
                },
                timeout=10
            )
            logger.info(f"[INFO] API响应状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                new_comment = {
                    'id': result.get('id'),
                    'username': result.get('username'),
                    'content': result.get('content'),
                    'rating': result.get('rating'),
                    'timestamp': result.get('timestamp'),
                    'likes': result.get('likes', 0),
                    'user_id': result.get('user_id')
                }
                comments = load_comments()
                comments.append(new_comment)
                save_comments(comments)
                logger.info("[SUCCESS] 评论已成功写入数据库并同步到本地")
                return new_comment
            else:
                error_detail = response.json().get('detail', '未知错误')
                logger.error(f"[ERROR] API返回错误状态码 {response.status_code}: {error_detail}")
                raise Exception(f"数据库写入失败: {error_detail}")
        except Exception as e:
            logger.error(f"[ERROR] API提交评论失败: {e}，降级到本地存储")

    # 本地/Supabase 模式：使用本地存储（兜底逻辑）
    comments = load_comments()
    new_comment = {
        'id': len(comments) + 1,
        'username': username or f'用户{app_state.get_user_id()[:6]}',
        'content': content,
        'rating': rating,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'likes': 0,
        'user_id': app_state.get_user_id()
    }
    comments.append(new_comment)
    save_comments(comments)
    logger.info("[SUCCESS] 评论已保存到本地文件")
    return new_comment


def like_comment(comment_id):
    """点赞评论（API模式下同步到数据库，保持数据一致性）"""
    from config import BACKEND_URL, DATA_SOURCE

    if BACKEND_URL and DATA_SOURCE == 'api':
        try:
            import requests
            api_url = f"{BACKEND_URL.rstrip('/')}/api/comments/comments/like/{comment_id}"
            response = requests.put(api_url, timeout=10)
            response.raise_for_status()
            logger.info(f"[OK] 评论 {comment_id} 点赞成功（已同步到数据库）")
            return
        except Exception as e:
            logger.error(f"[ERROR] API点赞失败: {e}，降级到本地文件")

    comments = load_comments()
    for comment in comments:
        if comment['id'] == comment_id:
            comment['likes'] += 1
            break
    save_comments(comments)


def render_comments_page():
    """用户评价页入口（供 st.navigation 调用）"""
    from components.sidebar import render_sidebar
    render_sidebar("comments")

    st.title("💬 用户评价")

    if app_state.get_comment_refresh_needed():
        app_state.set_comment_refresh_needed(False)
        st.session_state.comments_dirty = True

    if 'comments_cache' not in st.session_state or st.session_state.get('comments_dirty', False):
        st.session_state.comments_cache = load_comments()
        st.session_state.comments_dirty = False
    comments = st.session_state.comments_cache

    # 统计信息
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总评论数", len(comments))
    with col2:
        if comments:
            avg_rating = sum(c.get('rating', 5) for c in comments) / len(comments)
            st.metric("平均评分", f"{avg_rating:.1f} ⭐")
        else:
            st.metric("平均评分", "暂无")
    with col3:
        total_likes = sum(c.get('likes', 0) for c in comments)
        st.metric("总点赞数", total_likes)

    st.markdown("---")

    # 发表评论表单
    with st.expander("✍️ 发表评论", expanded=False):
        with st.form("comment_form", clear_on_submit=True):
            rating = st.slider("评分", 1, 5, 5, help="请为工具打分")
            content = st.text_area(
                "评论内容",
                placeholder="分享您的使用体验、建议或问题...",
                height=100,
                max_chars=500
            )
            col_submit, col_cancel = st.columns([1, 3])
            with col_submit:
                submit_comment = st.form_submit_button("📤 发表", type="primary")

            if submit_comment:
                if not content.strip():
                    st.error("❌ 请输入评论内容")
                else:
                    with st.spinner('正在提交评论...'):
                        new_comment = add_comment(None, content, rating)
                    if new_comment:
                        st.success("✅ 评论发表成功！")
                        st.session_state.comments_dirty = True
                        app_state.set_comment_refresh_needed(True)
                        st.rerun()
                    else:
                        st.error("❌ 评论发表失败，请稍后重试")

    st.markdown("---")

    # 评论列表
    if not comments:
        st.info("💭 暂无评论，快来发表第一条评论吧！")
    else:
        comments_sorted = sorted(comments, key=lambda x: x['timestamp'], reverse=True)
        for comment in comments_sorted[:20]:
            with st.container():
                col_header, col_like = st.columns([4, 1])
                with col_header:
                    rating = comment.get('rating', 5)
                    stars = "⭐" * rating
                    _ts = sanitize_html(comment.get('timestamp', ''))
                    _content = sanitize_html(comment.get('content', ''))
                    st.markdown(
                        f"<div style='padding: 10px; background-color: #f0f2f6; "
                        f"border-radius: 5px; margin: 5px 0;'>"
                        f"{stars}<br>"
                        f"<span style='color: #666; font-size: 0.85em;'>🕒 {_ts}</span><br>"
                        f"{_content}</div>",
                        unsafe_allow_html=True
                    )
                with col_like:
                    likes = comment.get('likes', 0)
                    if st.button(f"👍 {likes}", key=f"like_{comment['id']}"):
                        st.session_state.comments_dirty = True
                        like_comment(comment['id'])
                st.markdown("---")

        if len(comments) > 20:
            st.caption(f"显示最近20条评论，共 {len(comments)} 条")
