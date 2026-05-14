# -*- coding: utf-8 -*-
"""
WordStyle Pro - Web管理后台
支持双模式数据源（本地SQLite/云端Supabase）
"""
import streamlit as st
import sys
import os
from datetime import datetime, timedelta
from typing import Optional

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

# 使用统一数据访问层（支持双模式）
from data_manager import (
    get_all_tasks,
    get_task_stats,
    load_all_users_data,
    get_data_source,
    DATA_SOURCE as ACTUAL_DATA_SOURCE
)
from comments_manager import load_feedbacks, get_feedback_stats, delete_comment
from config import DATA_SOURCE as CONFIG_DATA_SOURCE, DATABASE_URL

# 在页面顶部显示数据源配置信息（用于调试）
st.sidebar.info(f"数据源: {get_data_source()}")
st.sidebar.info(f"DB URL: {'已配置' if DATABASE_URL else '未配置'}")

# 显示详细诊断信息
with st.sidebar.expander("诊断信息"):
    st.write(f"**CONFIG_DATA_SOURCE**: {CONFIG_DATA_SOURCE}")
    st.write(f"**ACTUAL_DATA_SOURCE**: {ACTUAL_DATA_SOURCE}")
    st.write(f"**get_data_source()**: {get_data_source()}")
    if DATABASE_URL:
        # 显示部分URL用于调试（隐藏密码）
        parts = DATABASE_URL.split('@')
        if len(parts) == 2:
            safe_url = f"{parts[0].split(':')[0]}://***@{parts[1][:30]}..."
        else:
            safe_url = "***"
        st.write(f"**数据库连接**: {safe_url}")

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="WordStyle Pro - 管理后台",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 样式优化 ====================
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin: 10px 0;
    }
    .metric-value {
        font-size: 2.5em;
        font-weight: bold;
    }
    .metric-label {
        font-size: 1em;
        opacity: 0.9;
    }
</style>
""", unsafe_allow_html=True)

# ==================== 辅助函数 ====================

def format_datetime(dt_str):
    """格式化日期时间字符串"""
    if dt_str and dt_str != '-':
        try:
            return datetime.fromisoformat(dt_str).strftime('%Y-%m-%d %H:%M:%S')
        except:
            return dt_str
    return '-'

def format_currency(amount):
    """格式化金额"""
    return f"¥{amount:,.2f}" if amount else "¥0.00"

# ==================== 数据看板 ====================

def show_dashboard():
    """显示数据看板"""
    st.title("📊 数据看板")
    st.markdown("---")
    
    try:
        # 获取统计数据（从统一数据访问层）
        stats = get_task_stats()
        
        # 调试信息：检查 stats 是否为空
        if not stats:
            st.warning("⚠️ 无法获取任务统计数据，请检查后端服务是否正常运行")
            st.info(f"当前数据源: {get_data_source()}")
            if get_data_source() == 'api':
                from config import BACKEND_URL
                st.info(f"后端地址: {BACKEND_URL}")
                st.error("请确认后端服务已启动并可访问")
        
        # 获取用户总数（从 JSON/Supabase）
        all_users = load_all_users_data()
        
        # 调试信息：显示详细的数据加载情况
        st.sidebar.markdown("### 🔍 数据加载诊断")
        st.sidebar.write(f"**数据源模式**: {get_data_source()}")
        st.sidebar.write(f"**用户数量**: {len(all_users)}")
        
        if get_data_source() == 'api':
            from config import BACKEND_URL
            st.sidebar.write(f"**后端地址**: {BACKEND_URL}")
            
            # 测试后端 API 连接
            try:
                import requests
                test_url = f"{BACKEND_URL}/api/admin/users?limit=5"
                response = requests.get(test_url, timeout=5)
                st.sidebar.write(f"**API 状态码**: {response.status_code}")
                if response.status_code == 200:
                    api_data = response.json()
                    st.sidebar.write(f"**API 返回用户数**: {api_data.get('total', 0)}")
                    if api_data.get('users'):
                        st.sidebar.success("✅ API 连接正常，用户数据可获取")
                    else:
                        st.sidebar.warning("⚠️ API 返回空用户列表")
                else:
                    st.sidebar.error(f"❌ API 请求失败: {response.status_code}")
            except Exception as e:
                st.sidebar.error(f"❌ API 连接失败: {str(e)}")
        
        # 调试信息：检查用户数据
        if not all_users:
            st.warning("⚠️ 未找到用户数据")
            st.info(f"当前数据源: {get_data_source()}")
            if get_data_source() == 'api':
                from config import BACKEND_URL
                st.info(f"后端地址: {BACKEND_URL}")
                st.error("请确认：1) 后端服务已启动 2) 数据库中有用户数据 3) API 端点正确")
        total_users = len(all_users)
        
        # 计算今日新增用户
        today = datetime.now().strftime('%Y-%m-%d')
        today_users = sum(1 for u in all_users if u.get('last_login', '').startswith(today))
        
        # 显示关键指标
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{total_users}</div>
                <div class="metric-label">总用户数</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{today_users}</div>
                <div class="metric-label">今日新增</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats.get('total_tasks', 0)}</div>
                <div class="metric-label">转换任务</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("### 📈 转换任务统计")
        
        # 任务状态分布
        task_col1, task_col2, task_col3, task_col4 = st.columns(4)
        
        with task_col1:
            st.metric("✅ 已完成", stats.get('completed_tasks', 0))
        
        with task_col2:
            st.metric("⏳ 处理中", stats.get('processing_tasks', 0))
        
        with task_col3:
            st.metric("⏸️ 等待中", stats.get('pending_tasks', 0))
        
        with task_col4:
            st.metric("❌ 失败", stats.get('failed_tasks', 0))
        
        # 成功率
        success_rate = 0
        if stats.get('total_tasks', 0) > 0:
            success_rate = (stats.get('completed_tasks', 0) / stats.get('total_tasks', 1)) * 100
        
        st.metric("🎯 成功率", f"{success_rate:.1f}%")
        
    except Exception as e:
        st.error(f"加载数据失败: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

# ==================== 用户管理 ====================

def show_user_management():
    """显示用户管理"""
    st.title("👥 用户管理")
    st.markdown("---")
    
    try:
        # 显示当前数据源信息（调试用）
        st.info(f"📊 当前数据源: {get_data_source()}")
        
        # 搜索和筛选
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            search_keyword = st.text_input("🔍 搜索用户", placeholder="输入用户ID或昵称")
        
        with col2:
            sort_by = st.selectbox("排序方式", ["注册时间", "剩余段落", "余额"])
        
        with col3:
            show_count = st.selectbox("显示数量", [20, 50, 100], index=0)
        
        # 加载所有用户数据
        with st.spinner("正在从数据库加载用户数据..."):
            try:
                all_users = load_all_users_data()
                st.success(f" 从数据库加载了 {len(all_users)} 个用户")
            except Exception as e:
                st.error(f"加载用户数据失败: {e}")
                import traceback
                st.code(traceback.format_exc())
                all_users = []
        
        # 如果是Supabase模式，显示原始数据供调试
        if get_data_source() == 'supabase' and len(all_users) > 0:
            with st.expander(" 查看原始数据（调试）"):
                st.json(all_users[:2])  # 只显示前2个用户的数据
        
        # 搜索过滤
        if search_keyword:
            filtered_users = [
                u for u in all_users
                if search_keyword.lower() in str(u.get('user_id', '')).lower()
            ]
        else:
            filtered_users = all_users
        
        # 排序
        if sort_by == "注册时间":
            filtered_users.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        elif sort_by == "剩余段落":
            filtered_users.sort(key=lambda x: x.get('paragraphs_remaining', 0), reverse=True)
        elif sort_by == "余额":
            filtered_users.sort(key=lambda x: x.get('balance', 0.0), reverse=True)
        
        # 分页
        total = len(filtered_users)
        users = filtered_users[:show_count]
        
        st.info(f"共找到 {total} 个用户，显示前 {len(users)} 个")
        
        if users:
            # 显示用户列表
            user_data = []
            for user in users:
                user_data.append({
                    "用户ID": user.get('user_id', '-'),
                    "剩余段落": user.get('paragraphs_remaining', 0),
                    "已用段落": user.get('paragraphs_used', 0),
                    "总转换数": user.get('total_converted', 0),
                    "余额": user.get('balance', 0.0),
                    "状态": "✅ 活跃" if user.get('is_active', True) else "❌ 禁用",
                    "注册时间": format_datetime(user.get('created_at', ''))
                })
            
            st.dataframe(user_data, use_container_width=True, hide_index=True)
            
            # 用户操作
            st.markdown("### 🔧 用户操作")
            
            selected_user_id = st.text_input("输入用户ID进行操作", placeholder="粘贴完整的用户ID")
            
            if selected_user_id:
                # 查找用户（使用统一数据访问层）
                from data_manager import load_user_data, save_user_data
                user_data_dict = load_user_data(selected_user_id)
                
                if user_data_dict:
                    st.success(f"找到用户: {selected_user_id}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_paragraphs = st.number_input(
                            "调整剩余段落",
                            value=int(user_data_dict.get('paragraphs_remaining', 0)),
                            step=100,
                            key=f"para_{selected_user_id}"
                        )
                        if st.button("保存段落数", key=f"save_para_{selected_user_id}"):
                            user_data_dict['paragraphs_remaining'] = new_paragraphs
                            save_user_data(selected_user_id, user_data_dict)
                            st.success("✅ 段落数已更新")
                            st.rerun()
                    
                    with col2:
                        new_balance = st.number_input(
                            "调整余额",
                            value=float(user_data_dict.get('balance', 0.0)),
                            step=1.0,
                            key=f"balance_{selected_user_id}"
                        )
                        if st.button("保存余额", key=f"save_balance_{selected_user_id}"):
                            user_data_dict['balance'] = new_balance
                            save_user_data(selected_user_id, user_data_dict)
                            st.success("✅ 余额已更新")
                            st.rerun()
                else:
                    st.error("❌ 未找到该用户")
        else:
            st.warning("未找到匹配的用户")
            
            # 如果是 Supabase 模式但没有用户，给出提示
            if get_data_source() == 'supabase':
                st.info("💡 提示：数据库中没有用户数据。如果转换页面有用户，说明数据源配置可能不一致。请检查：1. 管理后台和转换页面是否使用同一个数据库 2. 管理后台的 USE_SUPABASE 和 DATABASE_URL 环境变量是否正确")
    
    except Exception as e:
        st.error(f"加载用户数据失败: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

# ==================== 转换任务管理 ====================

def show_task_management():
    """显示转换任务管理"""
    st.title("📝 转换任务管理")
    st.markdown("---")
    
    try:
        # 筛选条件
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.selectbox(
                "任务状态",
                ["ALL", "PENDING", "PROCESSING", "COMPLETED", "FAILED"]
            )
        
        with col2:
            date_filter = st.date_input("筛选日期", value=None)
        
        with col3:
            task_limit = st.selectbox("显示数量", [20, 50, 100], index=0)
        
        # 从SQLite获取任务列表
        all_tasks = get_all_tasks(status_filter=status_filter, limit=1000)
        
        # 日期过滤
        if date_filter:
            filtered_tasks = [
                t for t in all_tasks
                if t.get('created_at', '').startswith(str(date_filter))
            ]
        else:
            filtered_tasks = all_tasks
        
        # 限制显示数量
        tasks = filtered_tasks[:task_limit]
        total = len(filtered_tasks)
        
        st.info(f"共找到 {total} 个任务，显示前 {len(tasks)} 个")
        
        if tasks:
            task_data = []
            for task in tasks:
                status_emoji = {
                    'PENDING': '⏳',
                    'PROCESSING': '🔄',
                    'COMPLETED': '✅',
                    'FAILED': '❌'
                }.get(task.get('status', ''), '❓')
                
                task_data.append({
                    "任务ID": task.get('task_id', '-'),
                    "用户ID": str(task.get('user_id', ''))[:8] + "..." if task.get('user_id') else '-',
                    "文件名": task.get('filename', '-') or '-',
                    "段落数": task.get('paragraphs', '-') or '-',
                    "费用": f"¥{task.get('cost', 0):.2f}" if task.get('cost') else '-',
                    "状态": f"{status_emoji} {task.get('status', '')}",
                    "进度": f"{task.get('progress', 0)}%",
                    "错误信息": task.get('error_message', '-') or '-',
                    "创建时间": format_datetime(task.get('created_at', '')),
                    "完成时间": format_datetime(task.get('completed_at', ''))
                })
            
            st.dataframe(task_data, use_container_width=True, hide_index=True)
            
            # 任务操作
            st.markdown("### 🔧 任务操作")
            
            selected_task_id = st.text_input("输入任务ID进行操作", placeholder="粘贴完整的任务ID")
            
            if selected_task_id:
                # 使用统一数据访问层
                from data_manager import update_task_status
                
                # 查找任务
                task_found = any(t['task_id'] == selected_task_id for t in all_tasks)
                
                if task_found:
                    st.success(f"找到任务: {selected_task_id}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("标记为完成", key=f"complete_{selected_task_id}"):
                            update_task_status(selected_task_id, 'COMPLETED', progress=100)
                            st.success("✅ 任务已标记为完成")
                            st.rerun()
                    
                    with col2:
                        if st.button("标记为失败", key=f"fail_{selected_task_id}"):
                            update_task_status(selected_task_id, 'FAILED')
                            st.success("✅ 任务已标记为失败")
                            st.rerun()
                else:
                    st.error("❌ 未找到该任务")
        else:
            st.warning("未找到匹配的任务")
    
    except Exception as e:
        st.error(f"加载任务数据失败: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

# ==================== 订单管理 ====================

def show_order_management():
    """显示订单管理（暂未实现）"""
    st.title("💰 订单管理")
    st.markdown("---")
    
    st.info("ℹ️ 订单管理功能暂未实现。当前版本使用本地JSON存储，不支持订单系统。")
    st.warning("如需订单管理功能，请切换到云端Supabase模式。")

# ==================== 反馈管理 ====================

def show_feedback_management():
    """显示反馈管理"""
    st.title("💬 用户反馈管理")
    st.markdown("---")
    
    try:
        # 获取反馈统计
        stats = get_feedback_stats()
        
        # 显示统计信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📝 总反馈数", stats.get('total', 0))
        with col2:
            st.metric("⏳ 待处理", stats.get('pending', 0))
        with col3:
            st.metric("✅ 已处理", stats.get('processed', 0))
        
        st.markdown("---")
        
        # 加载所有反馈
        all_feedbacks = load_feedbacks()
        
        if all_feedbacks:
            # 显示反馈列表
            feedback_data = []
            for fb in all_feedbacks:
                feedback_data.append({
                    "ID": fb.get('id', '-'),
                    "用户ID": str(fb.get('user_id', ''))[:12] + "..." if fb.get('user_id') else '-',
                    "类型": fb.get('type', '-'),
                    "内容": fb.get('content', '-')[:50] + "..." if len(fb.get('content', '')) > 50 else fb.get('content', '-'),
                    "状态": "✅ 已处理" if fb.get('processed', False) else "⏳ 待处理",
                    "提交时间": format_datetime(fb.get('created_at', '')),
                })
            
            st.dataframe(feedback_data, use_container_width=True, hide_index=True)
            
            # 反馈操作
            st.markdown("### 🔧 反馈操作")
            
            selected_feedback_id = st.text_input("输入反馈ID进行操作", placeholder="粘贴完整的反馈ID")
            
            if selected_feedback_id:
                # 查找反馈
                feedback_found = next((fb for fb in all_feedbacks if fb.get('id') == selected_feedback_id), None)
                
                if feedback_found:
                    st.success(f"找到反馈 ID: {selected_feedback_id}")
                    
                    # 显示完整内容
                    with st.expander("查看完整反馈内容", expanded=True):
                        st.write(f"**用户ID:** {feedback_found.get('user_id', '-')}")
                        st.write(f"**类型:** {feedback_found.get('type', '-')}")
                        st.write(f"**内容:** {feedback_found.get('content', '-')}")
                        st.write(f"**提交时间:** {format_datetime(feedback_found.get('created_at', ''))}")
                        st.write(f"**状态:** {'✅ 已处理' if feedback_found.get('processed', False) else '⏳ 待处理'}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if not feedback_found.get('processed', False):
                            if st.button("标记为已处理", key=f"process_{selected_feedback_id}"):
                                from comments_manager import save_feedbacks
                                feedback_found['processed'] = True
                                # 重新保存
                                all_fb = load_feedbacks()
                                for fb in all_fb:
                                    if fb.get('id') == selected_feedback_id:
                                        fb['processed'] = True
                                        break
                                save_feedbacks(all_fb)
                                st.success("✅ 已标记为已处理")
                                st.rerun()
                    
                    with col2:
                        if st.button("删除反馈", key=f"delete_{selected_feedback_id}", type="secondary"):
                            delete_comment(selected_feedback_id)  # 复用删除评论函数
                            st.success("✅ 反馈已删除")
                            st.rerun()
                else:
                    st.error("❌ 未找到该反馈")
        else:
            st.info("📭 暂无用户反馈")
    
    except Exception as e:
        st.error(f"加载反馈数据失败: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

# ==================== 系统配置 ====================

def show_system_config():
    """显示系统配置（暂未实现）"""
    st.title("⚙️ 系统配置")
    st.markdown("---")
    
    st.info("ℹ️ 系统配置功能暂未实现。当前版本使用config.py配置文件。")
    st.warning("如需动态配置管理，请切换到云端Supabase模式。")

# ==================== 主界面 ====================

def main():
    """主函数"""
    
    # 侧边栏导航
    with st.sidebar:
        st.header("🔧 WordStyle Pro 管理后台")
        st.markdown("---")
        
        page = st.radio(
            "选择页面",
            [
                "📊 数据看板",
                "👥 用户管理",
                "📝 转换任务",
                "💬 用户反馈",
                "💰 订单管理",
                "⚙️ 系统配置"
            ],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.caption("© 2026 WordStyle Pro")
        st.caption("版本: v2.9.0")
    
    # 根据选择显示不同页面
    if page == "📊 数据看板":
        show_dashboard()
    elif page == "👥 用户管理":
        show_user_management()
    elif page == "📝 转换任务":
        show_task_management()
    elif page == "💬 用户反馈":
        show_feedback_management()
    elif page == "💰 订单管理":
        show_order_management()
    elif page == "⚙️ 系统配置":
        show_system_config()

if __name__ == "__main__":
    main()
