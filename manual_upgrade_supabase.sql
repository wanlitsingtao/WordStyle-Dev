-- =====================================================
-- Supabase数据库手动升级脚本
-- 生成时间: 2026-05-17
-- 目标版本: 20260517_1330 (添加paragraphs字段)
-- =====================================================

-- 使用说明：
-- 1. 在Supabase Dashboard的SQL Editor中执行此脚本
-- 2. 或者使用psql命令行工具连接后执行
-- 3. 执行前建议先备份数据库

BEGIN;

-- =====================================================
-- 步骤1: 为conversion_tasks表添加paragraphs字段
-- =====================================================

-- 检查字段是否已存在，避免重复添加
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

-- =====================================================
-- 步骤2: 更新alembic_version表记录当前版本
-- =====================================================

-- 检查alembic_version表是否存在
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'alembic_version'
    ) THEN
        -- 创建alembic_version表
        CREATE TABLE alembic_version (
            version_num VARCHAR(32) NOT NULL
        );
        
        RAISE NOTICE '✅ 成功创建 alembic_version 表';
    ELSE
        RAISE NOTICE '⚠️  alembic_version 表已存在';
    END IF;
END $$;

-- 清空现有版本记录（如果有）
DELETE FROM alembic_version;

-- 插入最新版本号
INSERT INTO alembic_version (version_num) VALUES ('20260517_1330');

-- 显示成功消息
DO $$
BEGIN
    RAISE NOTICE '✅ 成功更新 alembic_version 到 20260517_1330';
END $$;

-- =====================================================
-- 验证升级结果
-- =====================================================

-- 检查paragraphs字段是否添加成功
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'conversion_tasks' 
            AND column_name = 'paragraphs'
        ) THEN '✅ paragraphs 字段验证通过'
        ELSE '❌ paragraphs 字段验证失败'
    END AS verification_result;

-- 检查alembic版本是否正确
SELECT 
    CASE 
        WHEN version_num = '20260517_1330' THEN '✅ Alembic版本验证通过'
        ELSE '❌ Alembic版本验证失败: ' || COALESCE(version_num, 'NULL')
    END AS version_verification
FROM alembic_version
LIMIT 1;

COMMIT;

-- =====================================================
-- 升级完成提示
-- =====================================================
-- 
-- ✅ 如果看到以上两个验证都通过，说明升级成功！
-- 
-- 后续操作：
-- 1. 重启后端服务以应用新的模型定义
-- 2. 检查后端日志确认没有数据库相关错误
-- 3. 测试转换功能确保paragraphs字段正常工作
-- 
-- =====================================================
