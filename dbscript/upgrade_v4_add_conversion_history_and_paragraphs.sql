-- =====================================================
-- WordStyle 数据库升级脚本 v4
-- 版本: 2026-05-30
-- 用途: 添加 conversion_history 和 paragraphs 字段
-- 执行前请备份数据库！
-- =====================================================

-- =====================================================
-- 步骤1: 为 users 表添加 conversion_history 字段
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
-- 步骤2: 为 conversion_tasks 表添加 paragraphs 字段
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
