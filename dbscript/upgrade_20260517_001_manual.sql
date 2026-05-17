-- =====================================================
-- WordStyle 数据库手动升级脚本
-- 生成时间: 2026-05-17
-- 版本: v20260517_001
-- 说明: 包含conversion_tasks表和feedbacks表的最新变更
-- =====================================================

-- 使用说明：
-- 1. 在Supabase Dashboard的SQL Editor中执行此脚本
-- 2. 或者使用psql命令行工具连接后执行
-- 3. 执行前建议先备份数据库
-- 4. 如果自动迁移失败，可以手动执行此脚本

BEGIN;

-- =====================================================
-- 第一部分：conversion_tasks表升级
-- =====================================================

-- 1.1 为conversion_tasks表添加paragraphs字段（如果不存在）
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
        
        RAISE NOTICE '✅ 成功添加 paragraphs 字段到 conversion_tasks 表';
    ELSE
        RAISE NOTICE '⚠️  paragraphs 字段已存在，跳过';
    END IF;
END $$;

-- 1.2 更新现有记录的paragraphs字段为0（如果为NULL）
UPDATE conversion_tasks 
SET paragraphs = 0 
WHERE paragraphs IS NULL;

DO $$
BEGIN
    RAISE NOTICE '✅ 已更新 conversion_tasks 表中 NULL 值的 paragraphs 字段';
END $$;

-- =====================================================
-- 第二部分：feedbacks表验证
-- =====================================================

-- 2.1 验证feedbacks表是否存在
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'feedbacks'
    ) THEN
        RAISE EXCEPTION '❌ feedbacks 表不存在，请先创建该表';
    ELSE
        RAISE NOTICE '✅ feedbacks 表已存在';
    END IF;
END $$;

-- 2.2 验证feedbacks表结构是否完整
DO $$
DECLARE
    missing_columns TEXT[];
BEGIN
    SELECT ARRAY(
        SELECT col
        FROM unnest(ARRAY['id', 'user_id', 'feedback_type', 'title', 'description', 'contact', 'status', 'created_at']) AS col
        WHERE NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'feedbacks' 
            AND column_name = col
        )
    ) INTO missing_columns;
    
    IF array_length(missing_columns, 1) > 0 THEN
        RAISE EXCEPTION '❌ feedbacks 表缺少以下字段: %', array_to_string(missing_columns, ', ');
    ELSE
        RAISE NOTICE '✅ feedbacks 表结构完整';
    END IF;
END $$;

-- =====================================================
-- 第三部分：comments表验证（可选）
-- =====================================================

-- 3.1 检查comments表是否存在（评论系统尚未启用数据库存储）
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'comments'
    ) THEN
        RAISE NOTICE 'ℹ️  comments 表已存在（当前评论系统仍使用本地JSON文件存储）';
    ELSE
        RAISE NOTICE 'ℹ️  comments 表不存在（评论系统使用本地JSON文件存储）';
    END IF;
END $$;

-- =====================================================
-- 第四部分：alembic_version表更新
-- =====================================================

-- 4.1 创建或更新alembic_version表
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'alembic_version'
    ) THEN
        CREATE TABLE alembic_version (
            version_num VARCHAR(32) NOT NULL
        );
        RAISE NOTICE '✅ 成功创建 alembic_version 表';
    ELSE
        RAISE NOTICE '⚠️  alembic_version 表已存在';
    END IF;
END $$;

-- 4.2 更新版本号
DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('20260517_001');

DO $$
BEGIN
    RAISE NOTICE '✅ 成功更新 alembic_version 到 20260517_001';
END $$;

-- =====================================================
-- 第五部分：验证升级结果
-- =====================================================

-- 5.1 验证conversion_tasks表的paragraphs字段
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'conversion_tasks' 
            AND column_name = 'paragraphs'
        ) THEN '✅ conversion_tasks.paragraphs 字段验证通过'
        ELSE '❌ conversion_tasks.paragraphs 字段验证失败'
    END AS verification_result;

-- 5.2 验证alembic版本
SELECT 
    CASE 
        WHEN version_num = '20260517_001' THEN '✅ Alembic版本验证通过'
        ELSE '❌ Alembic版本验证失败: ' || COALESCE(version_num, 'NULL')
    END AS version_verification
FROM alembic_version
LIMIT 1;

-- 5.3 统计信息
SELECT 
    'conversion_tasks' AS table_name,
    COUNT(*) AS total_records,
    COUNT(paragraphs) AS records_with_paragraphs,
    SUM(CASE WHEN paragraphs IS NULL THEN 1 ELSE 0 END) AS null_paragraphs
FROM conversion_tasks

UNION ALL

SELECT 
    'feedbacks' AS table_name,
    COUNT(*) AS total_records,
    COUNT(id) AS records_with_id,
    0 AS null_paragraphs
FROM feedbacks;

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '=================================================';
    RAISE NOTICE '✅ 数据库升级完成！';
    RAISE NOTICE '=================================================';
    RAISE NOTICE '升级内容：';
    RAISE NOTICE '1. conversion_tasks表添加paragraphs字段';
    RAISE NOTICE '2. feedbacks表结构验证';
    RAISE NOTICE '3. alembic_version更新到20260517_001';
    RAISE NOTICE '=================================================';
END $$;

COMMIT;
