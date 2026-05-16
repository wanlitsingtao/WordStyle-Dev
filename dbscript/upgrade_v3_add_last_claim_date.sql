-- =====================================================
-- 数据库手动升级脚本
-- 功能：添加 last_claim_date 字段到 users 表
-- 创建日期：2026-05-16
-- 适用环境：Supabase PostgreSQL
-- =====================================================

-- 检查字段是否已存在，避免重复执行
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'last_claim_date'
    ) THEN
        -- 添加 last_claim_date 字段
        ALTER TABLE users 
        ADD COLUMN last_claim_date TIMESTAMP WITH TIME ZONE;
        
        RAISE NOTICE '✅ 已添加 last_claim_date 字段';
    ELSE
        RAISE NOTICE '⚠️ last_claim_date 字段已存在，跳过';
    END IF;
END $$;

-- 验证字段是否添加成功
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'users'
AND column_name = 'last_claim_date';

-- 预期输出：
-- column_name     | data_type                  | is_nullable
-- ----------------+----------------------------+------------
-- last_claim_date | timestamp with time zone   | YES
