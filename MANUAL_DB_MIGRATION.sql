-- =====================================================
-- 手动数据库迁移脚本
-- 用于在Supabase/PostgreSQL中手动添加缺失的字段
-- =====================================================
-- 
-- 使用说明：
-- 1. 登录 Supabase Dashboard → SQL Editor
-- 2. 复制以下SQL并执行
-- 3. 确认执行成功后刷新应用
--
-- 注意：此脚本包含所有必要的迁移，按顺序执行
-- =====================================================

BEGIN;

-- =====================================================
-- 迁移1: 添加用户统计字段 (如果不存在)
-- =====================================================
DO $$
BEGIN
    -- total_paragraphs_used
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'total_paragraphs_used'
    ) THEN
        ALTER TABLE users ADD COLUMN total_paragraphs_used INTEGER DEFAULT 0;
        RAISE NOTICE '✅ 已添加 total_paragraphs_used 字段';
    ELSE
        RAISE NOTICE '⚠️ total_paragraphs_used 字段已存在，跳过';
    END IF;

    -- total_converted
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'total_converted'
    ) THEN
        ALTER TABLE users ADD COLUMN total_converted INTEGER DEFAULT 0;
        RAISE NOTICE '✅ 已添加 total_converted 字段';
    ELSE
        RAISE NOTICE '⚠️ total_converted 字段已存在，跳过';
    END IF;
END $$;

-- =====================================================
-- 迁移2: 添加设备指纹字段 (如果不存在)
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'device_fingerprint'
    ) THEN
        ALTER TABLE users ADD COLUMN device_fingerprint VARCHAR(64);
        CREATE INDEX idx_users_device_fingerprint ON users(device_fingerprint);
        RAISE NOTICE '✅ 已添加 device_fingerprint 字段和索引';
    ELSE
        RAISE NOTICE '⚠️ device_fingerprint 字段已存在，跳过';
    END IF;
END $$;

-- =====================================================
-- 迁移3: 添加最后领取日期字段 (如果不存在)
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'last_claim_date'
    ) THEN
        ALTER TABLE users ADD COLUMN last_claim_date TIMESTAMP;
        RAISE NOTICE '✅ 已添加 last_claim_date 字段';
    ELSE
        RAISE NOTICE '⚠️ last_claim_date 字段已存在，跳过';
    END IF;
END $$;

-- =====================================================
-- 迁移4: 添加转换历史字段 (本次修复的核心)
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'conversion_history'
    ) THEN
        ALTER TABLE users ADD COLUMN conversion_history JSONB DEFAULT '[]'::jsonb;
        RAISE NOTICE '✅ 已添加 conversion_history 字段 (JSONB类型)';
    ELSE
        RAISE NOTICE '⚠️ conversion_history 字段已存在，跳过';
    END IF;
END $$;

COMMIT;

-- =====================================================
-- 验证查询：检查所有字段是否已添加
-- =====================================================
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'users'
    AND column_name IN (
        'total_paragraphs_used',
        'total_converted',
        'device_fingerprint',
        'last_claim_date',
        'conversion_history'
    )
ORDER BY ordinal_position;

-- =====================================================
-- 预期输出：
-- column_name            | data_type    | is_nullable | column_default
-- ----------------------+--------------+-------------+------------------
-- device_fingerprint     | varchar      | YES         | NULL
-- total_paragraphs_used  | integer      | YES         | 0
-- total_converted        | integer      | YES         | 0
-- last_claim_date        | timestamp    | YES         | NULL
-- conversion_history     | jsonb        | YES         | '[]'::jsonb
-- =====================================================
