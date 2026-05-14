# -*- coding: utf-8 -*-
"""
WordStyle 集中配置文件
统一管理所有配置项，避免硬编码和分散配置
"""
import os
import sys
from pathlib import Path

# ==================== 基础路径配置 ====================
BASE_DIR = Path(__file__).parent.absolute()
RESULTS_DIR = BASE_DIR / "conversion_results"
DATA_DIR = BASE_DIR / "data"

# 确保目录存在
RESULTS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ==================== 加载 .env 文件（本地开发用）====================
try:
    from dotenv import load_dotenv
    env_file = BASE_DIR / '.env'
    if env_file.exists():
        load_dotenv(env_file)
        print(f"[OK] 已加载 .env 配置文件")
    else:
        print(f"[INFO] 未找到 .env 文件，使用系统环境变量或默认值")
except ImportError:
    print(f"[WARN] python-dotenv 未安装，无法加载 .env 文件")

# ==================== 数据源配置 ====================
# 支持三种模式：
#   1. local - 本地开发（SQLite + JSON）
#   2. supabase - 直接连接 Supabase（仅 Render 等允许出站数据库连接的环境）
#   3. api - 通过后端 API 获取数据（Streamlit Cloud 等受限环境）
# 优先级：st.secrets > os.getenv() > 默认值
# 自动检测：如果 USE_SUPABASE=true 且 BACKEND_URL 存在，则使用 api 模式

def _load_config_from_secrets():
    """尝试从 Streamlit Secrets 加载配置"""
    try:
        import streamlit as st
        # 检查是否在 Streamlit 环境中
        if hasattr(st, 'secrets') and len(st.secrets) > 0:
            secrets = st.secrets
            
            # 处理 USE_SUPABASE：支持布尔值和字符串
            use_supabase_raw = secrets.get('USE_SUPABASE', False)
            if isinstance(use_supabase_raw, bool):
                use_supabase = use_supabase_raw
            else:
                use_supabase = str(use_supabase_raw).lower() == 'true'
            
            # 获取 DATABASE_URL 和 BACKEND_URL
            database_url = secrets.get('DATABASE_URL')
            backend_url = secrets.get('BACKEND_URL')
            
            return {
                'use_supabase': use_supabase,
                'database_url': database_url,
                'backend_url': backend_url
            }
    except Exception:
        pass
    return None

# 尝试从 Streamlit Secrets 加载
secrets_config = _load_config_from_secrets()

if secrets_config:
    # 从 Streamlit Secrets 加载（云端部署）
    USE_SUPABASE = secrets_config['use_supabase']
    DATABASE_URL = secrets_config['database_url']
    BACKEND_URL = secrets_config.get('backend_url')
else:
    # 从环境变量加载（本地开发或 Render）
    USE_SUPABASE = os.getenv("USE_SUPABASE", "false").lower() == "true"
    DATABASE_URL = os.getenv("DATABASE_URL")
    BACKEND_URL = os.getenv("BACKEND_URL")

# 自动检测数据源模式：
# - 如果 BACKEND_URL 存在且 USE_SUPABASE=true，使用 api 模式（Streamlit Cloud）
# - 如果只有 DATABASE_URL 且 USE_SUPABASE=true，使用 supabase 模式（Render）
# - 否则使用 local 模式（本地开发）
if BACKEND_URL and USE_SUPABASE:
    # Streamlit Cloud 等受限环境：通过后端 API 访问
    DATA_SOURCE = "api"
    print(f"🌐 数据源模式: API (后端: {BACKEND_URL})")
elif USE_SUPABASE and DATABASE_URL:
    # Render 等允许出站连接的环境：直接连接数据库
    DATA_SOURCE = "supabase"
    print(f" 数据源模式: Supabase (直接连接)")
else:
    # 本地开发
    DATA_SOURCE = "local"
    print(f"[INFO] 数据源模式: 本地 (SQLite + JSON)")

# ==================== 计费配置 ====================
# 计费规则：100个段落 = 0.1元
PARAGRAPH_PRICE = 0.001  # 每个段落的价格（元）
MIN_RECHARGE = 1.0  # 最低充值金额（元）

# 充值档位
RECHARGE_PACKAGES = [
    {'amount': 1, 'paragraphs': 1000, 'label': '体验版'},
    {'amount': 5, 'paragraphs': 5000, 'label': '标准版'},
    {'amount': 10, 'paragraphs': 10000, 'label': '专业版'},
    {'amount': 50, 'paragraphs': 50000, 'label': '企业版'},
    {'amount': 100, 'paragraphs': 100000, 'label': '旗舰版'},
]

# ==================== 免费额度配置 ====================
FREE_PARAGRAPHS_DAILY = 10000  # 每日免费段落数

# ==================== 管理员配置 ====================
ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "微信号：your_wechat_id")  # 管理员联系方式

# ==================== 文件配置 ====================
USER_DATA_FILE = DATA_DIR / "user_data.json"
COMMENTS_FILE = DATA_DIR / "comments_data.json"
TASKS_DB_FILE = BASE_DIR / "conversion_tasks.db"

# 文件上传限制
MAX_FILE_SIZE_MB = 50  # 最大文件大小（MB）
ALLOWED_EXTENSIONS = ['.docx']  # 允许的文件扩展名

# ==================== 缓存配置 ====================
CACHE_TTL_SECONDS = 5  # 缓存有效期（秒）

# ==================== 日志配置 ====================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # 日志级别
LOG_FILE = BASE_DIR / "app.log"  # 日志文件路径

# ==================== 任务清理配置 ====================
TASK_EXPIRY_DAYS = 7  # 任务过期天数
CLEANUP_INTERVAL_HOURS = 24  # 清理间隔（小时）

# ==================== 样式映射默认配置 ====================
DEFAULT_STYLE_MAPPINGS = {
    'Heading 1': '标题 1',
    'Heading 2': '标题 2',
    'Heading 3': '标题 3',
    'Normal': '正文',
}

# ==================== 应答句配置 ====================
DEFAULT_ANSWER_TEXT = "应答：本投标人理解并满足要求。"
DEFAULT_ANSWER_STYLE = "Normal"
DEFAULT_ANSWER_MODE = 'before_heading'

ANSWER_MODE_OPTIONS = {
    'before_heading': '章节前插入',
    'after_heading': '章节后插入',
    'copy_chapter': '章节招标原文+应答句+招标原文副本',
    'before_paragraph': '逐段前应答',
    'after_paragraph': '逐段后应答'
}

# ==================== 列表符号配置 ====================
DEFAULT_LIST_BULLET = "•"

# ==================== 转换配置 ====================
CONVERTER_STEPS = 7  # 转换器步骤数
PROGRESS_BASE = 10  # 进度基数
PROGRESS_MAX = 80  # 进度最大值

# ==================== 安全配置 ====================
FILENAME_MAX_LENGTH = 200  # 文件名最大长度
LOCK_TIMEOUT_SECONDS = 10  # 文件锁超时时间

# ==================== UI配置 ====================
PAGE_TITLE = "标书抄写神器（Beta测试版）"
PAGE_ICON = "📄"
LAYOUT = "wide"  # wide 或 centered
SIDEBAR_STATE = "expanded"  # expanded 或 collapsed

# ==================== 评论系统配置 ====================
COMMENTS_PER_PAGE = 20  # 每页显示的评论数
MAX_COMMENT_LENGTH = 500  # 评论最大长度

# ==================== 导出配置 ====================
def get_config_summary():
    """获取配置摘要（用于调试）"""
    return {
        'PARAGRAPH_PRICE': PARAGRAPH_PRICE,
        'FREE_PARAGRAPHS_DAILY': FREE_PARAGRAPHS_DAILY,
        'BACKEND_URL': BACKEND_URL,
        'ADMIN_CONTACT': ADMIN_CONTACT,
        'RESULTS_DIR': str(RESULTS_DIR),
        'TASK_EXPIRY_DAYS': TASK_EXPIRY_DAYS,
    }

# ==================== 验证配置 ====================
def validate_config():
    """验证配置的有效性"""
    errors = []
    
    if PARAGRAPH_PRICE <= 0:
        errors.append("PARAGRAPH_PRICE 必须大于0")
    
    if MIN_RECHARGE <= 0:
        errors.append("MIN_RECHARGE 必须大于0")
    
    if FREE_PARAGRAPHS_DAILY <= 0:
        errors.append("FREE_PARAGRAPHS_DAILY 必须大于0")
    
    if not RESULTS_DIR.exists():
        try:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"无法创建结果目录: {e}")
    
    return errors

# 启动时验证配置
if __name__ == "__main__":
    errors = validate_config()
    if errors:
        print("[ERROR] 配置错误:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("[OK] 配置验证通过")
        print("\n配置摘要:")
        for key, value in get_config_summary().items():
            print(f"  {key}: {value}")
