-- =====================================================
-- WordStyle 数据库升级脚本 v4
-- 版本: 2026-05-30
-- 用途: 添加 conversion_history、paragraphs 字段和维护模式配置
-- 执行前请备份数据库！
-- =====================================================

-- =====================================================
-- 步骤1: 为 system_config 表添加 maintenance_mode 配置
-- =====================================================
-- 说明: 系统维护模式开关（true/false）
-- 默认值: 'false'（非维护模式）

INSERT INTO system_config (config_key, config_value, description) 
VALUES ('maintenance_mode', 'false', '系统维护模式开关')
ON CONFLICT (config_key) DO NOTHING;

-- 同时补充其他缺失的配置项（如果不存在）
INSERT INTO system_config (config_key, config_value, description) 
VALUES 
    ('free_paragraphs_daily', '10000', '每日免费段落额度'),
    ('paragraph_price', '0.001', '每个段落的价格（元）'),
    ('max_file_size_mb', '50', '最大文件大小（MB）'),
    ('admin_contact', '微信号：your_wechat_id', '管理员联系方式')
ON CONFLICT (config_key) DO NOTHING;

RAISE NOTICE '[OK] 已添加/更新 system_config 配置项';

-- =====================================================
-- 步骤2: 为 users 表添加 conversion_history 字段
-- =====================================================
-- 说明: 存储用户转换历史记录（JSONB 格式）
-- 兼容性检查: 如果字段已存在则跳过

DO $$ 
BEGIN
    -- 检查字段是否已存在
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'conversion_history'
    ) THEN
        -- PostgreSQL 使用 JSONB 类型
        ALTER TABLE users 
        ADD COLUMN conversion_history JSONB DEFAULT '[]'::jsonb;
        
        RAISE NOTICE '[OK] 已添加 conversion_history 字段 (JSONB)';
    ELSE
        RAISE NOTICE '[WARN] conversion_history 字段已存在，跳过';
    END IF;
END $$;

-- =====================================================
-- 步骤3: 为 conversion_tasks 表添加 paragraphs 字段
-- =====================================================
-- 说明: 记录每次转换的段落数
-- 默认值: 0

DO $$ 
BEGIN
    -- 检查字段是否已存在
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'conversion_tasks' 
        AND column_name = 'paragraphs'
    ) THEN
        ALTER TABLE conversion_tasks 
        ADD COLUMN paragraphs INTEGER DEFAULT 0;
        
        RAISE NOTICE '[OK] 已添加 paragraphs 字段 (INTEGER)';
    ELSE
        RAISE NOTICE '[WARN] paragraphs 字段已存在，跳过';
    END IF;
END $$;

-- =====================================================
-- 验证升级结果
-- =====================================================
SELECT 
    'users.conversion_history' AS field,
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'conversion_history'
        ) THEN '✅ 已添加'
        ELSE '❌ 缺失'
    END AS status
UNION ALL
SELECT 
    'conversion_tasks.paragraphs' AS field,
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'conversion_tasks' 
            AND column_name = 'paragraphs'
        ) THEN '✅ 已添加'
        ELSE '❌ 缺失'
    END AS status;

-- =====================================================
-- 完成提示
-- =====================================================
SELECT '✅ 数据库升级 v4 完成！' AS message;
