-- 1. 添加密码哈希字段
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(256);

-- 2. 创建用户名不区分大小写的唯一索引
--    确保不同用户不能使用相同用户名（忽略大小写）
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower 
    ON users (LOWER(username))
    WHERE username IS NOT NULL AND username != '';