-- =====================================================
-- WordStyle 数据库完整升级脚本 v4
-- 版本: 2026-05-30
-- 用途: 确保发布目录数据库与工作目录完全一致
-- 执行前请备份数据库！
-- =====================================================

-- =====================================================
-- 步骤1: 修复 Alembic 迁移链（如果需要）
-- =====================================================
-- 说明: 如果发布目录的 Alembic 版本停留在 20260517_1330
--       但缺少 conversion_history 字段，需要手动执行此脚本

-- =====================================================
-- 步骤2: 为 system_config 表补充缺失的配置项
-- =====================================================
-- 说明: 确保所有必要的系统配置都存在

-- 维护模式开关
INSERT INTO system_config (config_key, config_value, description) 
VALUES ('maintenance_mode', 'false', '系统维护模式开关')
ON CONFLICT (config_key) DO NOTHING;

-- 每日免费段落额度
INSERT INTO system_config (config_key, config_value, description) 
VALUES ('free_paragraphs_daily', '10000', '每日免费段落额度')
ON CONFLICT (config_key) DO NOTHING;

-- 段落价格
INSERT INTO system_config (config_key, config_value, description) 
VALUES ('paragraph_price', '0.001', '每个段落的价格（元）')
ON CONFLICT (config_key) DO NOTHING;

-- 最大文件大小
INSERT INTO system_config (config_key, config_value, description) 
VALUES ('max_file_size_mb', '50', '最大文件大小（MB）')
ON CONFLICT (config_key) DO NOTHING;

-- 管理员联系方式
INSERT INTO system_config (config_key, config_value, description) 
VALUES ('admin_contact', '微信号：your_wechat_id', '管理员联系方式')
ON CONFLICT (config_key) DO NOTHING;

DO $$ 
BEGIN
    RAISE NOTICE '[OK] 已检查/添加 system_config 配置项';
END $$;

-- =====================================================
-- 步骤3: 为 users 表添加 conversion_history 字段
-- =====================================================
-- 说明: 存储用户转换历史记录（JSONB 格式）
-- 兼容性检查: 如果字段已存在则跳过

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'conversion_history'
    ) THEN
        ALTER TABLE users 
        ADD COLUMN conversion_history JSONB DEFAULT '[]'::jsonb;
        
        RAISE NOTICE '[OK] 已添加 users.conversion_history 字段 (JSONB)';
    ELSE
        RAISE NOTICE '[WARN] users.conversion_history 字段已存在，跳过';
    END IF;
END $$;

-- =====================================================
-- 步骤4: 为 users 表添加 device_fingerprint 字段（如果缺失）
-- =====================================================

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'device_fingerprint'
    ) THEN
        ALTER TABLE users 
        ADD COLUMN device_fingerprint VARCHAR(255);
        
        RAISE NOTICE '[OK] 已添加 users.device_fingerprint 字段';
    ELSE
        RAISE NOTICE '[WARN] users.device_fingerprint 字段已存在，跳过';
    END IF;
END $$;

-- =====================================================
-- 步骤5: 为 users 表添加 last_claim_date 字段（如果缺失）
-- =====================================================

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'last_claim_date'
    ) THEN
        ALTER TABLE users 
        ADD COLUMN last_claim_date TIMESTAMP WITH TIME ZONE;
        
        RAISE NOTICE '[OK] 已添加 users.last_claim_date 字段';
    ELSE
        RAISE NOTICE '[WARN] users.last_claim_date 字段已存在，跳过';
    END IF;
END $$;

-- =====================================================
-- 步骤6: 为 conversion_tasks 表添加 paragraphs 字段（如果缺失）
-- =====================================================
-- 说明: 记录每次转换的段落数
-- 默认值: 0

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'conversion_tasks' 
        AND column_name = 'paragraphs'
    ) THEN
        ALTER TABLE conversion_tasks 
        ADD COLUMN paragraphs INTEGER DEFAULT 0;
        
        RAISE NOTICE '[OK] 已添加 conversion_tasks.paragraphs 字段 (INTEGER)';
    ELSE
        RAISE NOTICE '[WARN] conversion_tasks.paragraphs 字段已存在，跳过';
    END IF;
END $$;

-- =====================================================
-- 验证升级结果
-- =====================================================
SELECT 
    'system_config.maintenance_mode' AS field,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM system_config WHERE config_key = 'maintenance_mode'
        ) THEN '✅ 已添加'
        ELSE '❌ 缺失'
    END AS status
UNION ALL
SELECT 
    'system_config.free_paragraphs_daily' AS field,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM system_config WHERE config_key = 'free_paragraphs_daily'
        ) THEN '✅ 已添加'
        ELSE '❌ 缺失'
    END AS status
UNION ALL
SELECT 
    'system_config.paragraph_price' AS field,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM system_config WHERE config_key = 'paragraph_price'
        ) THEN '✅ 已添加'
        ELSE '❌ 缺失'
    END AS status
UNION ALL
SELECT 
    'system_config.max_file_size_mb' AS field,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM system_config WHERE config_key = 'max_file_size_mb'
        ) THEN '✅ 已添加'
        ELSE '❌ 缺失'
    END AS status
UNION ALL
SELECT 
    'system_config.admin_contact' AS field,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM system_config WHERE config_key = 'admin_contact'
        ) THEN '✅ 已添加'
        ELSE '❌ 缺失'
    END AS status
UNION ALL
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
    'users.device_fingerprint' AS field,
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'device_fingerprint'
        ) THEN '✅ 已添加'
        ELSE '❌ 缺失'
    END AS status
UNION ALL
SELECT 
    'users.last_claim_date' AS field,
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'last_claim_date'
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
SELECT '✅ 数据库升级 v4 完成！所有必要字段和配置已检查/添加' AS message;
