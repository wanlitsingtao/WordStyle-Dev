# -*- coding: utf-8 -*-
"""
共享侧边栏组件（T03）
从 app.py 提取：用户信息 / 账号绑定·登录 / 宣传图 / 反馈入口 / 版本信息。
所有页面共享，由各页面函数在入口调用 render_sidebar()。
"""
import logging
from pathlib import Path

import streamlit as st

from state import app_state

logger = logging.getLogger('WordStyle')
_NAVIGATION_PAGES = {}


def configure_navigation_pages(pages):
    """保存主入口创建的页面对象，供侧栏导航链接使用。"""
    global _NAVIGATION_PAGES
    _NAVIGATION_PAGES = pages


def _render_feature_menu():
    """在额度信息之后渲染侧栏页面导航。"""
    st.markdown(
        """
        <div class="sidebar-section-divider"></div>
        <div class="sidebar-section-title">
            <span class="sidebar-section-mark"></span>
            <span>功能菜单</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for page_key, label in (
        ("conversion", "文档转换"),
        ("toolbox", "工具箱"),
        ("tone_config", "祈使语气配置"),
        ("comments", "用户评价"),
    ):
        st.page_link(_NAVIGATION_PAGES[page_key], label=label, use_container_width=True)


@st.cache_resource
def _get_logo_base64():
    """读取侧边栏顶部品牌图标。"""
    import base64

    logo_path = Path("resource/logo.png")
    if logo_path.exists():
        return base64.b64encode(logo_path.read_bytes()).decode()
    return None


def render_top_nav(active_page: str = "conversion"):
    """保留兼容函数；推荐布局采用左侧导航，不再在顶部显示横向 Tab。"""
    return None


@st.cache_resource
def _get_ds_image_bytes():
    """读取侧边栏宣传图字节（进程级缓存，仅读取一次）"""
    _ds_image_path = Path("resource/ds.jpg")
    if _ds_image_path.exists():
        return _ds_image_path.read_bytes()
    return None


def render_sidebar(active_page: str = "conversion"):
    """渲染共享侧边栏内容（用户信息 / 账号 / 功能导航 / 宣传图 / 反馈 / 版本）"""
    from config import APP_VERSION

    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #eef4ff 0%, #f8fafc 48%, #f8fafc 100%);
            border-right: 1px solid #dbe5f2;
            width: 286px !important;
            min-width: 286px !important;
        }
        div[data-testid="stSidebarContent"] {
            padding: 0.8rem 0.85rem 1.2rem;
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] {
            margin: 0.18rem 0;
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] > a {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            width: 100%;
            border-radius: 12px;
            background: rgba(255,255,255,0.62);
            border: 1px solid rgba(148,163,184,0.22);
            color: #334155;
            font-size: 0.98rem;
            font-weight: 500;
            padding: 0.7rem 0.8rem;
            text-decoration: none;
            box-shadow: none;
            margin: 0;
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] > a:hover {
            background: #ffffff;
            border-color: #93c5fd;
            color: #1d4ed8;
            transform: translateX(2px);
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a[href*="app.py"] {
            background: rgba(255,255,255,0.82);
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a[href*="toolbox.py"] {
            background: rgba(255,255,255,0.82);
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a[href*="tone_config.py"] {
            background: rgba(255,255,255,0.82);
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a[href*="comments.py"] {
            background: rgba(255,255,255,0.82);
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a[href*="app.py"][href*="app.py"] {
            background: linear-gradient(135deg, #dbeafe, #eff6ff);
            border: 1px solid #93c5fd;
            color: #1d4ed8;
            font-weight: 600;
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a[href*="toolbox.py"] {
            background: rgba(255,255,255,0.52);
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a[href*="tone_config.py"] {
            background: rgba(255,255,255,0.52);
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a[href*="comments.py"] {
            background: rgba(255,255,255,0.52);
        }
        [data-testid="stSidebar"] .user-card {
            background: rgba(255,255,255,0.78);
            border: 1px solid #dbe5f2;
            border-radius: 14px;
            padding: 0.8rem 0.9rem;
            margin: 0.6rem 0 1rem;
        }
        [data-testid="stSidebar"] .kpi-box {
            background: rgba(255,255,255,0.6);
            border: 1px solid #dbe5f2;
            border-radius: 10px;
            padding: 0.55rem 0.7rem;
            margin: 0.4rem 0;
        }
        [data-testid="stSidebar"] .mini-btn {
            background: rgba(255,255,255,0.86);
            border: 1px solid #dbe5f2;
            border-radius: 10px;
            padding: 0.45rem 0.6rem;
            text-align: center;
            font-size: 0.88rem;
            color: #334155;
            margin: 0.2rem 0.2rem 0 0;
        }
        [data-testid="stSidebar"] button {
            white-space: nowrap;
        }
        [data-testid="stSidebar"] [data-testid="stMetricValue"] {
            font-size: 1.25rem;
        }
        [data-testid="stSidebar"] .sidebar-kpi-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.5rem;
            margin: 0.65rem 0 0.9rem;
        }
        [data-testid="stSidebar"] .sidebar-kpi {
            min-width: 0;
            padding: 0.65rem 0.7rem;
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid #dbe5f2;
            border-radius: 10px;
        }
        [data-testid="stSidebar"] .sidebar-kpi-label {
            color: #64748b;
            font-size: 0.72rem;
            line-height: 1.25;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        [data-testid="stSidebar"] .sidebar-kpi-value {
            color: #172b4d;
            font-size: 1.25rem;
            font-weight: 700;
            line-height: 1.2;
            margin-top: 0.2rem;
        }
        [data-testid="stSidebar"] .sidebar-section-divider {
            height: 1px;
            margin: 0.35rem 0 0.9rem;
            background: linear-gradient(90deg, #bfdbfe 0%, #dbe5f2 65%, transparent 100%);
        }
        [data-testid="stSidebar"] .sidebar-section-title {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            margin: 0 0 0.55rem 0.1rem;
            color: #334155;
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        [data-testid="stSidebar"] .sidebar-section-mark {
            width: 4px;
            height: 15px;
            border-radius: 999px;
            background: #2563eb;
        }
        [data-testid="stAppViewContainer"] { background: transparent; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        logo_b64 = _get_logo_base64()
        if logo_b64:
            st.markdown(
                f'''<div style="display:flex;align-items:center;gap:8px;margin:0 0 0.8rem 0;">
                <img src="data:image/png;base64,{logo_b64}" style="height:2.2rem;width:auto;">
                <span style="font-size:1.35rem;font-weight:700;color:#262730;white-space:nowrap;">标书编写神器</span>
                </div>''',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="user-card">', unsafe_allow_html=True)
        st.markdown("<div style='display:flex;align-items:center;gap:10px;font-size:1.02rem;font-weight:700;color:#1f2937;'><span style='display:inline-flex;width:26px;height:26px;border-radius:8px;background:linear-gradient(135deg,#4f46e5,#8b5cf6);color:white;align-items:center;justify-content:center;font-size:0.9rem;'>U</span> 用户信息</div>", unsafe_allow_html=True)
        st.caption(f"用户ID: {app_state.get_user_id()[:12]}...")
        st.markdown('</div>', unsafe_allow_html=True)

        _logged_in_name = st.session_state.get('logged_in_username', None)
        if st.session_state.get('user_init_failed', False):
            st.error("❌ 获取用户ID失败")
            st.caption("用户服务暂时不可用，请稍后刷新页面重试")
        elif _logged_in_name:
            st.caption(f"👤 {_logged_in_name}")

        # ==================== 账号绑定 / 登录按钮 ====================
        from account_manager import create_account_manager

        _device_fp = st.session_state.get('device_fingerprint', '')
        _logged_in_user = st.session_state.get('logged_in_username', None)

        if _logged_in_user:
            st.markdown(f"👤 **{_logged_in_user}**")

            if st.session_state.get('show_unbind_confirm', False):
                st.warning("确定要解绑账号吗？解绑后用户名和密码将被清除，恢复设备指纹身份。")
                col_ub1, col_ub2 = st.columns(2)
                with col_ub1:
                    if st.button("确认解绑", key="confirm_unbind_btn", use_container_width=True):
                        mgr = create_account_manager()
                        success, msg = mgr.unbind_account(_device_fp)
                        if success:
                            st.session_state.logged_in_username = None
                            st.session_state.logged_in_user_id = None
                            st.session_state.sidebar_user_data = None
                            st.session_state.show_unbind_confirm = False
                            st.success(msg + " 已恢复设备指纹身份。")
                            st.rerun()
                        else:
                            st.error(msg)
                with col_ub2:
                    if st.button("取消", key="cancel_unbind_btn", use_container_width=True):
                        st.session_state.show_unbind_confirm = False
                        st.rerun()
            else:
                if st.button("解绑用户", key="unbind_account_btn", use_container_width=True):
                    st.session_state.show_unbind_confirm = True
                    st.rerun()

            if st.button("退出登录", key="logout_btn", use_container_width=True):
                st.session_state.logged_in_username = None
                st.session_state.logged_in_user_id = None
                st.session_state.sidebar_user_data = None
                st.rerun()
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("绑定账号", key="bind_account_btn", use_container_width=True):
                    st.session_state.show_bind_dialog = True
                    st.session_state.show_login_dialog = False
            with col_b:
                if st.button("账号登录", key="login_account_btn", use_container_width=True):
                    st.session_state.show_login_dialog = True
                    st.session_state.show_bind_dialog = False

        # 用户数据加载（复用 app.py 入口统一初始化的会话缓存）
        if not st.session_state.get('user_init_failed', False):
            from data_manager import load_user_data
            user_data = st.session_state.get('user_data')
            if user_data is None:
                user_data = load_user_data(app_state.get_user_id())
                st.session_state.user_data = user_data
            st.session_state.sidebar_user_data = user_data
        else:
            user_data = {
                'user_id': app_state.get_user_id(),
                'balance': 0.0,
                'paragraphs_remaining': 0,
                'total_paragraphs_used': 0,
                'total_converted': 0,
                'is_active': False,
                'created_at': '',
                'last_login': '',
            }
            logger.warning("[WARN] 用户初始化失败，使用本地默认数据（额度=0）")

        if user_data is None:
            logger.warning(f"[WARN] 用户数据加载失败: {app_state.get_user_id()}，尝试重新初始化")
            try:
                device_fingerprint = st.session_state.get('device_fingerprint', '')
                if device_fingerprint:
                    from data_manager import get_or_create_user_by_device
                    user_data = get_or_create_user_by_device(device_fingerprint)
                    app_state.set_user_id(user_data['user_id'])
                    logger.info(f"[OK] 重新初始化用户成功: {app_state.get_user_id()}")
                else:
                    user_data = {
                        'user_id': app_state.get_user_id(),
                        'balance': 0.0,
                        'paragraphs_remaining': 0,
                        'total_paragraphs_used': 0,
                        'total_converted': 0,
                        'is_active': False,
                        'created_at': '',
                        'last_login': '',
                        'conversion_history': [],
                    }
                    logger.warning("[WARN] 使用临时用户数据")
            except Exception as e:
                logger.error(f"[ERROR] 重新初始化用户失败: {e}")
                user_data = {
                    'user_id': app_state.get_user_id(),
                    'balance': 0.0,
                    'paragraphs_remaining': 0,
                    'total_paragraphs_used': 0,
                    'total_converted': 0,
                    'is_active': False,
                    'created_at': '',
                    'last_login': '',
                    'conversion_history': [],
                }

        st.markdown(
            f"""
            <div class="sidebar-kpi-grid">
                <div class="sidebar-kpi">
                    <div class="sidebar-kpi-label">剩余段落数</div>
                    <div class="sidebar-kpi-value">{user_data['paragraphs_remaining']:,}</div>
                </div>
                <div class="sidebar-kpi">
                    <div class="sidebar-kpi-label">累计转换文档</div>
                    <div class="sidebar-kpi-value">{user_data['total_converted']:,}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        _render_feature_menu()

        # ==================== 绑定账号对话框 ====================
        if st.session_state.get('show_bind_dialog', False):
            with st.expander("🔗 绑定账号", expanded=True):
                st.markdown("将当前设备与一个易记的用户名绑定，方便以后跨设备登录。")
                with st.form("bind_account_form"):
                    bind_username = st.text_input(
                        "设置用户名",
                        placeholder="字母、数字或中文，不区分大小写",
                        key="bind_username_input"
                    )
                    bind_password = st.text_input(
                        "设置密码",
                        type="password",
                        placeholder="设置登录密码",
                        key="bind_password_input"
                    )
                    bind_password2 = st.text_input(
                        "确认密码",
                        type="password",
                        placeholder="再次输入密码",
                        key="bind_password2_input"
                    )

                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        submitted_bind = st.form_submit_button("✅ 确定", use_container_width=True)
                    with col_b2:
                        cancelled_bind = st.form_submit_button("取消", use_container_width=True)

                if cancelled_bind:
                    st.session_state.show_bind_dialog = False
                    for k in ('bind_username_input', 'bind_password_input', 'bind_password2_input'):
                        st.session_state.pop(k, None)
                    st.rerun()

                if submitted_bind:
                    if bind_password != bind_password2:
                        st.error("两次输入的密码不一致")
                    elif not bind_username or not bind_password:
                        st.error("用户名和密码不能为空")
                    else:
                        mgr = create_account_manager()
                        success, msg = mgr.bind_account(_device_fp, bind_username, bind_password)
                        if success:
                            st.session_state.logged_in_username = bind_username.strip()
                            st.session_state.logged_in_user_id = app_state.get_user_id()
                            st.session_state.sidebar_user_data = None
                            st.session_state.show_bind_dialog = False
                            for k in ('bind_username_input', 'bind_password_input', 'bind_password2_input'):
                                st.session_state.pop(k, None)
                            st.success(msg + " 已自动登录。")
                            st.rerun()
                        else:
                            st.error(msg)

        # ==================== 账号登录对话框 ====================
        if st.session_state.get('show_login_dialog', False):
            with st.expander("🔑 账号登录", expanded=True):
                st.markdown("使用已绑定的用户名和密码登录。")
                with st.form("login_account_form"):
                    login_username = st.text_input(
                        "用户名",
                        placeholder="输入已绑定的用户名",
                        key="login_username_input"
                    )
                    login_password = st.text_input(
                        "密码",
                        type="password",
                        placeholder="输入登录密码",
                        key="login_password_input"
                    )

                    col_l1, col_l2 = st.columns(2)
                    with col_l1:
                        submitted_login = st.form_submit_button("✅ 登录", use_container_width=True)
                    with col_l2:
                        cancelled_login = st.form_submit_button("取消", use_container_width=True)

                if cancelled_login:
                    st.session_state.show_login_dialog = False
                    for k in ('login_username_input', 'login_password_input'):
                        st.session_state.pop(k, None)
                    st.rerun()

                if submitted_login:
                    if not login_username or not login_password:
                        st.error("用户名和密码不能为空")
                    else:
                        mgr = create_account_manager()
                        success, msg, user_id = mgr.login_account(login_username, login_password)
                        if success and user_id:
                            st.session_state.logged_in_username = login_username.strip()
                            st.session_state.logged_in_user_id = user_id
                            app_state.set_user_id(user_id)
                            st.session_state.sidebar_user_data = None
                            st.session_state.show_login_dialog = False
                            for k in ('login_username_input', 'login_password_input'):
                                st.session_state.pop(k, None)
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        st.markdown("---")

        # 提示文字
        st.markdown('<div style="text-align: center; margin-bottom: 1rem;">', unsafe_allow_html=True)
        st.markdown('**更好的体验，需要你的支持！**')
        st.markdown('</div>', unsafe_allow_html=True)

        # 宣传图
        try:
            _ds_image_bytes = _get_ds_image_bytes()
            if _ds_image_bytes:
                st.image(_ds_image_bytes, use_container_width=True)
        except Exception as e:
            logger.warning(f"加载ds.jpg失败: {e}")

        st.markdown("---")

        # 需求提交入口
        from components.dialogs.feedback import show_feedback_dialog
        if st.button("💡 提交需求/反馈", use_container_width=True, key="feedback_btn"):
            show_feedback_dialog()

        # 版本号和版权信息
        col1, col2, col3 = st.columns([1, 6, 1])
        with col2:
            st.markdown('<div style="text-align: center; white-space: nowrap;">', unsafe_allow_html=True)
            st.markdown(
                f'<p style="text-align: center; margin: 0.5rem 0 0 0; color: #666; font-size: 0.875rem;">标书编写神器{APP_VERSION}</p>',
                unsafe_allow_html=True
            )
            st.markdown(
                '<p style="text-align: center; margin: 0.25rem 0 0 0; color: #666; font-size: 0.75rem; white-space: nowrap;">© 2026 文档转换工具 保留所有权利</p>',
                unsafe_allow_html=True
            )
            st.markdown('</div>', unsafe_allow_html=True)
