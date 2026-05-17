-- =====================================================
-- WordStyle 数据库紧急修复脚本
-- 生成时间: 2026-05-17
-- 用途: 修复因alembic_version错误导致的迁移跳过问题
-- =====================================================

-- 使用说明：
-- 1. 在Supabase Dashboard的SQL Editor中执行此脚本
-- 2. 或者使用psql命令行工具连接后执行
-- 3. 执行前建议先备份数据库
-- 4. 执行后需要重启Render后端服务以重新触发迁移

BEGIN;

-- =====================================================
-- 第一步：检查当前数据库状态
-- =====================================================

-- 1.1 检查alembic_version表
SELECT '当前alembic版本:' AS info, version_num 
FROM alembic_version 
LIMIT 1;

-- 1.2 检查users表是否有conversion_history字段
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'conversion_history'
        ) THEN '✅ conversion_history 字段已存在'
        ELSE '❌ conversion_history 字段缺失 - 需要添加'
    END AS users_conversion_history_status;

-- 1.3 检查users表是否有device_fingerprint字段
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'device_fingerprint'
        ) THEN '✅ device_fingerprint 字段已存在'
        ELSE '❌ device_fingerprint 字段缺失 - 需要添加'
    END AS users_device_fingerprint_status;

-- 1.4 检查users表是否有last_claim_date字段
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'last_claim_date'
        ) THEN '✅ last_claim_date 字段已存在'
        ELSE '❌ last_claim_date 字段缺失 - 需要添加'
    END AS users_last_claim_date_status;

-- 1.5 检查conversion_tasks表是否有paragraphs字段
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'conversion_tasks' 
            AND column_name = 'paragraphs'
        ) THEN '✅ paragraphs 字段已存在'
        ELSE '❌ paragraphs 字段缺失 - 需要添加'
    END AS conversion_tasks_paragraphs_status;

-- =====================================================
-- 第二步：重置alembic_version表
-- =====================================================

-- 2.1 清空alembic_version表（让下次启动时重新执行所有迁移）
DELETE FROM alembic_version;

DO $$
BEGIN
    RAISE NOTICE '✅ 已清空 alembic_version 表';
END $$;

-- =====================================================
-- 第三步：手动添加缺失的字段（作为保险措施）
-- =====================================================

-- 3.1 添加 conversion_history 字段到 users 表
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
        RAISE NOTICE '✅ 已添加 users.conversion_history 字段';
    ELSE
        RAISE NOTICE '⚠️  users.conversion_history 字段已存在，跳过';
    END IF;
END $$;

-- 3.2 添加 device_fingerprint 字段到 users 表
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
        RAISE NOTICE '✅ 已添加 users.device_fingerprint 字段';
    ELSE
        RAISE NOTICE '⚠️  users.device_fingerprint 字段已存在，跳过';
    END IF;
END $$;

-- 3.3 添加 last_claim_date 字段到 users 表
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'last_claim_date'
    ) THEN
        ALTER TABLE users 
        ADD COLUMN last_claim_date TIMESTAMPTZ;
        RAISE NOTICE '✅ 已添加 users.last_claim_date 字段';
    ELSE
        RAISE NOTICE '⚠️  users.last_claim_date 字段已存在，跳过';
    END IF;
END $$;

-- 3.4 添加 paragraphs 字段到 conversion_tasks 表
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
        RAISE NOTICE '✅ 已添加 conversion_tasks.paragraphs 字段';
    ELSE
        RAISE NOTICE '⚠️  conversion_tasks.paragraphs 字段已存在，跳过';
    END IF;
END $$;

-- =====================================================
-- 第四步：验证修复结果
-- =====================================================

-- 4.1 验证users表结构
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'users'
AND column_name IN ('id', 'device_fingerprint', 'last_claim_date', 'conversion_history')
ORDER BY ordinal_position;

-- 4.2 验证conversion_tasks表结构
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'conversion_tasks'
AND column_name IN ('id', 'paragraphs')
ORDER BY ordinal_position;

-- 4.3 验证alembic_version表已清空
SELECT 
    CASE 
        WHEN COUNT(*) = 0 THEN '✅ alembic_version 表已清空（下次启动会重新执行迁移）'
        ELSE '❌ alembic_version 表仍有记录: ' || COUNT(*)
    END AS alembic_version_status
FROM alembic_version;

-- 4.4 统计信息
SELECT 
    'users' AS table_name,
    COUNT(*) AS total_records
FROM users

UNION ALL

SELECT 
    'conversion_tasks' AS table_name,
    COUNT(*) AS total_records
FROM conversion_tasks;

COMMIT;

-- =====================================================
-- 第五步：后续操作说明
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '=================================================';
    RAISE NOTICE '✅ 数据库修复完成！';
    RAISE NOTICE '=================================================';
    RAISE NOTICE '';
    RAISE NOTICE '下一步操作：';
    RAISE NOTICE '1. 在 Render Dashboard 中重启 wstest-backend 服务';
    RAISE NOTICE '2. 等待服务重新启动（约2-3分钟）';
    RAISE NOTICE '3. 检查日志确认迁移正常执行';
    RAISE NOTICE '4. 测试用户界面和管理页面功能';
    RAISE NOTICE '';
    RAISE NOTICE '修复内容：';
    RAISE NOTICE '- 清空了 alembic_version 表';
    RAISE NOTICE '- 添加了缺失的数据库字段（如果不存在）';
    RAISE NOTICE '- 下次启动时会重新执行所有迁移脚本';
    RAISE NOTICE '=================================================';
END $$;
