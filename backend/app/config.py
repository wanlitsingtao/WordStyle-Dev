# -*- coding: utf-8 -*-
"""
后端配置文件
与前端 config.py 保持一致的配置项
"""

# ========== 免费额度配置 ==========
FREE_PARAGRAPHS_DAILY = 10000  # 每日免费段落数

# ========== 计费配置 ==========
PARAGRAPH_PRICE = 0.001  # 每个段落的价格（元）
MIN_RECHARGE = 1.0  # 最低充值金额（元）

# ========== 文件上传配置 ==========
MAX_FILE_SIZE_MB = 50  # 最大文件大小（MB）
ALLOWED_EXTENSIONS = ['.docx']  # 允许的文件扩展名
