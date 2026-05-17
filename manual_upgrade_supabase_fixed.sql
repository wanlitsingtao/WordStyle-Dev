-- =====================================================
-- Supabase数据库手动升级脚本（简化版）
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

ALTER TABLE conversion_tasks 
ADD COLUMN IF NOT EXISTS paragraphs INTEGER DEFAULT 0;

-- =====================================================
-- 步骤2: 创建或更新alembic_version表
-- =====================================================

-- 创建alembic_version表（如果不存在）
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL
);

-- 清空现有版本记录
DELETE FROM alembic_version;

-- 插入最新版本号
INSERT INTO alembic_version (version_num) VALUES ('20260517_1330');

COMMIT;

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
