# -*- coding: utf-8 -*-
"""
标书编写神器 - 应用入口（多页面导航壳）

使用 st.navigation 函数式注册 4 个页面：
- 文档转换      → pages/conversion.py   (render_conversion_page)
- 工具箱        → pages/toolbox.py      (render_toolbox_page)
- 祈使语气配置  → pages/tone_config.py  (render_tone_config_page)
- 用户评价      → pages/comments.py     (render_comments_page)

本文件仅负责：全局页面配置、后台服务、用户初始化、维护模式、导航注册。
"""
import streamlit as st

# [WARN] set_page_config必须在所有Streamlit命令之前调用
# [OK] 支持UptimeRobot健康检查：通过URL参数检测
import sys
from urllib.parse import urlparse, parse_qs
try:
    # 获取当前URL参数
    query_params = st.query_params
    if 'health' in query_params:
        # 返回health检查响应
        import json
        st.json({"status": "healthy", "service": "user-page", "version": "1.0.0"})
        st.stop()
except Exception:
    # 如果query_params不可用（旧版本Streamlit），忽略
    pass

st.set_page_config(
    page_title="标书编写神器",
    page_icon="📄",
    layout="wide",  # 使用宽屏布局
    initial_sidebar_state="expanded"
)

import os
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 添加当前目录到路径，以便导入其他模块
sys.path.insert(0, os.path.dirname(__file__))

# 统一状态管理器
from state import app_state

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('WordStyle')


# ==================== 后台服务（进程级单例）====================
# [PERF] 修复：旧代码每次 rerun 都新建 BackgroundScheduler 线程（线程泄漏）。
# 改用 @st.cache_resource 保证只启动一次。
@st.cache_resource
def _start_background_services():
    """
    启动后台服务（进程级单例）：
    1. 服务启动时执行文件清理
    2. 每日定时清理任务（APScheduler，每天零点执行）
    """
    # 1. 服务启动时执行文件清理
    try:
        from file_manager import cleanup_on_startup
        cleanup_on_startup()
        logger.info("[OK] 启动时文件清理完成")
    except Exception as e:
        logger.warning(f"启动时文件清理失败（不影响服务）: {e}")

    # 2. 每日定时清理任务（每天零点执行）
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from file_manager import schedule_daily_cleanup

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=schedule_daily_cleanup,
            trigger='cron',
            hour=0,
            minute=0,
            id='daily_file_cleanup',
            name='每日文件清理任务',
            replace_existing=True
        )
        scheduler.start()
        logger.info("[OK] 每日文件清理任务已启动（每天零点执行）")
        return scheduler
    except ImportError:
        logger.warning("[WARN] APScheduler未安装，跳过定时清理任务")
    except Exception as e:
        logger.warning(f"定时清理任务启动失败: {e}")
    return None


_start_background_services()


# ==================== 用户初始化（设备指纹）====================
from config import DATA_SOURCE
from data_manager import load_user_data, claim_free_paragraphs
from data_manager import generate_device_fingerprint, get_or_create_user_by_device

import hashlib

# 标记：用户初始化是否成功
user_init_success = False

try:
    # 第一步：获取客户端User-Agent并生成设备指纹
    try:
        headers = st.context.headers if hasattr(st, 'context') and hasattr(st.context, 'headers') else {}
        user_agent = headers.get('User-Agent', 'unknown')
        device_fingerprint = generate_device_fingerprint(user_agent)
        logger.info(f"设备指纹生成成功: {device_fingerprint[:16]}...")
    except Exception as e:
        logger.warning(f"[WARN] User-Agent获取失败，使用备用方案: {e}")
        device_fingerprint = generate_device_fingerprint(f"fallback_{id(st.session_state)}")

    # 第二步：通过设备指纹从数据库获取或创建用户（带会话级缓存守卫）
    # 但是如果用户已通过账号登录，则保持登录身份不变
    _logged_in_uid = st.session_state.get('logged_in_user_id', None)

    # [PERF] 身份标识：登录账号 或 设备指纹。身份变化（登录/退出/解绑）时强制重新加载
    _identity_key = _logged_in_uid or f"device_{device_fingerprint}"
    if st.session_state.get('_user_init_identity') != _identity_key:
        st.session_state.pop('user_data', None)
        st.session_state.pop('sidebar_user_data', None)
        st.session_state._user_init_identity = _identity_key

    # [PERF] 用户数据会话级缓存
    if 'user_data' in st.session_state and not st.session_state.get('user_data_stale', False):
        user_data = st.session_state.user_data
        app_state.set_user_id(user_data['user_id'])
        app_state.set_device_fingerprint(device_fingerprint)
    else:
        if _logged_in_uid:
            app_state.set_user_id(_logged_in_uid)
            app_state.set_device_fingerprint(device_fingerprint)
            user_data = load_user_data(_logged_in_uid)
            if not user_data:
                user_data = get_or_create_user_by_device(device_fingerprint, user_agent)
            logger.info(f"[OK] 已登录用户 - ID: {_logged_in_uid}, 额度: {user_data.get('paragraphs_remaining', 0)}")
        else:
            user_data = get_or_create_user_by_device(device_fingerprint, user_agent)
            app_state.set_user_id(user_data['user_id'])
            app_state.set_device_fingerprint(device_fingerprint)
            logger.info(f"[OK] 用户初始化成功 - ID: {app_state.get_user_id()}")
        st.session_state.user_data = user_data
        st.session_state.user_data_stale = False
    user_init_success = True

except Exception as e:
    logger.error(f"[ERROR] 用户初始化失败: {e}", exc_info=True)

    # 最终降级方案：生成一个本地可用的临时ID
    try:
        fallback_id = hashlib.md5(f"temp_{id(st.session_state)}_{datetime.now().timestamp()}".encode()).hexdigest()[:12]
    except Exception:
        fallback_id = f"temp_error_{id(st.session_state)}"

    app_state.set_user_id(fallback_id)
    app_state.set_device_fingerprint(None)
    app_state.set_user_init_failed(True)

    user_data = {
        'user_id': fallback_id,
        'balance': 0.0,
        'paragraphs_remaining': 0,
        'total_paragraphs_used': 0,
        'total_converted': 0,
        'is_active': False,
        'created_at': datetime.now().isoformat(),
        'last_login': datetime.now().isoformat(),
        'conversion_history': [],
    }
    logger.warning(f"[WARN] 使用临时用户ID（无额度）: {fallback_id}")

# 第三步：只有在初始化成功时才尝试领取免费额度（仅首次加载时执行）
if user_init_success and 'free_claimed_today' not in st.session_state:
    try:
        free_paragraphs = claim_free_paragraphs(app_state.get_user_id())
        if free_paragraphs > 0:
            st.toast(f"🎉 欢迎！今日免费额度已重置为 {free_paragraphs:,} 段", icon="🎁")
            user_data['paragraphs_remaining'] = free_paragraphs
            logger.info(f"[OK] 免费额度领取成功: {free_paragraphs}")
            app_state.set_free_claimed_today(True)
        else:
            logger.info(f"ℹ️ 无需领取额度或已领取过，当前额度: {user_data.get('paragraphs_remaining', 0)}")
            app_state.set_free_claimed_today(True)
    except Exception as e:
        logger.warning(f"[WARN] 领取免费额度失败: {e}，但不影响用户使用")
        app_state.set_free_claimed_today(True)
else:
    if not user_init_success:
        logger.warning("[WARN] 用户初始化失败，跳过额度领取")

logger.info(f"用户 {app_state.get_user_id()} 初始化完成，剩余额度: {user_data['paragraphs_remaining']}")

# 新手引导标志
if 'has_seen_guide' not in st.session_state:
    app_state.set_has_seen_guide(False)


# ==================== 维护模式检查 ====================
try:
    from data_manager import get_config
    maintenance_mode = get_config('maintenance_mode')

    is_maintenance = False
    if maintenance_mode is not None:
        if isinstance(maintenance_mode, bool):
            is_maintenance = maintenance_mode
        elif isinstance(maintenance_mode, str):
            is_maintenance = maintenance_mode.lower() in ('true', '1', 'yes', 'on')
        else:
            is_maintenance = bool(maintenance_mode)

    if is_maintenance:
        import base64

        script_dir = Path(__file__).parent
        logo_path = script_dir / "resource" / "wh.jpg"

        st.markdown("""
<style>
    .stApp {
        background-color: #000000 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    .block-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        max-width: 100% !important;
    }
    main {
        padding-top: 0 !important;
        margin-top: 0 !important;
        display: block !important;
        visibility: visible !important;
    }
    div[data-testid="stVerticalBlock"] {
        display: block !important;
        visibility: visible !important;
    }
    @keyframes breathe {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(1.05); }
    }
    .breathe-text {
        animation: breathe 3s ease-in-out infinite;
        color: #ffffff !important;
        font-size: 2rem;
        font-weight: bold;
        text-align: center;
        margin-top: 2rem;
        text-shadow: 0 0 20px rgba(255, 255, 255, 0.8);
        display: block !important;
        visibility: visible !important;
    }
</style>
""", unsafe_allow_html=True)

        if logo_path.exists():
            try:
                with open(logo_path, 'rb') as f:
                    encoded_image = base64.b64encode(f.read()).decode()

                st.markdown(f'''
                <div style="width: 100vw; height: 100vh; margin: 0; padding: 0; position: fixed; top: 0; left: 0; z-index: 0; overflow: hidden;">
                    <img src="data:image/jpeg;base64,{encoded_image}"
                         style="position: absolute; top: 0; left: 50%; transform: translateX(-50%); height: 100vh; width: auto; min-width: 100vw; display: block;">
                </div>
                ''', unsafe_allow_html=True)
            except Exception as e:
                logger.error(f"[维护模式] Logo图片加载失败: {e}")

        st.markdown('''
<div class="breathe-text" style="position: fixed; bottom: 5vh; left: 0; right: 0; text-align: center; z-index: 1;">
    我会回来的！
</div>
''', unsafe_allow_html=True)

        st.stop()
except Exception as e:
    logger.warning(f"维护模式检查失败（不影响服务）: {e}")


# ==================== 多页面导航（st.navigation 函数式注册）====================
from pages.conversion import render_conversion_page
from pages.toolbox import render_toolbox_page
from pages.tone_config import render_tone_config_page
from pages.comments import render_comments_page

navigation_pages = {
    "conversion": st.Page(render_conversion_page, title="文档转换", icon="📄", default=True),
    "toolbox": st.Page(render_toolbox_page, title="工具箱", icon="🛠️"),
    "tone_config": st.Page(render_tone_config_page, title="祈使语气配置", icon="⚙️"),
    "comments": st.Page(render_comments_page, title="用户评价", icon="💬"),
}
from components.sidebar import configure_navigation_pages
configure_navigation_pages(navigation_pages)
pg = st.navigation([
    navigation_pages["conversion"],
    navigation_pages["toolbox"],
    navigation_pages["tone_config"],
    navigation_pages["comments"],
], position="hidden")
pg.run()
