-- ============================================
-- WordStyle 数据库升级脚本
-- 版本: 2.0
-- 日期: 2026-05-15
-- 描述: 添加device_fingerprint字段支持跨会话持久化
-- ============================================

-- 1. 添加device_fingerprint字段
ALTER TABLE users ADD COLUMN IF NOT EXISTS device_fingerprint VARCHAR(32);

-- 2. 创建唯一索引（确保同一设备指纹只对应一个用户）
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_device_fingerprint ON users(device_fingerprint);

-- 3. 为已有用户生成device_fingerprint（可选）
-- 注意：由于无法获取历史User-Agent，这里留空，首次访问时补充
-- UPDATE users SET device_fingerprint = NULL WHERE device_fingerprint IS NULL;

-- 4. 验证修改
SELECT column_name, data_type, character_maximum_length 
FROM information_schema.columns 
WHERE table_name = 'users' 
AND column_name = 'device_fingerprint';

-- 5. 检查索引
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'users' 
AND indexname = 'idx_users_device_fingerprint';
