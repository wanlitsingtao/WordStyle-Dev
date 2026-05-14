-- =====================================================
-- WordStyle Supabase 数据库初始化脚本
-- 版本: 1.0
-- 创建日期: 2026-05-14
-- 说明: 在 Supabase SQL Editor 中执行此脚本
-- =====================================================

-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =====================================================
-- 1. users 表（用户信息）
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(12) PRIMARY KEY,          -- 12位字符串ID（应用层生成）
    username VARCHAR(50),                -- 用户名
    style_mappings JSONB DEFAULT '{}'::jsonb, -- 样式映射配置
    balance FLOAT DEFAULT 0.0,           -- 账户余额（元）
    paragraphs_remaining INTEGER DEFAULT 0,  -- 剩余段落数
    total_paragraphs_used INTEGER DEFAULT 0, -- 累计使用段落数
    total_converted INTEGER DEFAULT 0,   -- 累计转换文件数
    is_active BOOLEAN DEFAULT TRUE,      -- 是否激活
    created_at TIMESTAMPTZ DEFAULT NOW(), -- 创建时间
    last_login TIMESTAMPTZ,              -- 最后登录时间
    updated_at TIMESTAMPTZ DEFAULT NOW()  -- 更新时间
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login);

-- 添加注释
COMMENT ON TABLE users IS '用户信息表';
COMMENT ON COLUMN users.id IS '用户唯一标识，12位 MD5 哈希字符串';
COMMENT ON COLUMN users.username IS '用户名';
COMMENT ON COLUMN users.style_mappings IS '样式映射配置（JSON格式）';
COMMENT ON COLUMN users.balance IS '账户余额（元）';
COMMENT ON COLUMN users.paragraphs_remaining IS '剩余可用段落数';
COMMENT ON COLUMN users.total_paragraphs_used IS '累计已用段落数';
COMMENT ON COLUMN users.total_converted IS '累计转换文件数';
COMMENT ON COLUMN users.is_active IS '用户是否激活';
COMMENT ON COLUMN users.created_at IS '用户创建时间';
COMMENT ON COLUMN users.last_login IS '最后登录时间';
COMMENT ON COLUMN users.updated_at IS '最后更新时间';

-- =====================================================
-- 2. conversion_tasks 表（转换任务）
-- =====================================================
CREATE TABLE IF NOT EXISTS conversion_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(12) NOT NULL,          -- 用户ID（外键）
    source_file VARCHAR(500),              -- 源文件路径
    template_file VARCHAR(500),            -- 模板文件路径
    converted_file VARCHAR(500),           -- 转换后文件路径
    status VARCHAR(20) DEFAULT 'pending',  -- 任务状态
    progress INTEGER DEFAULT 0,            -- 进度（0-100）
    error_message TEXT,                    -- 错误信息
    completed_at TIMESTAMPTZ,              -- 完成时间
    created_at TIMESTAMPTZ DEFAULT NOW(),  -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT NOW(),  -- 更新时间
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_conversion_tasks_user_id ON conversion_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_conversion_tasks_status ON conversion_tasks(status);
CREATE INDEX IF NOT EXISTS idx_conversion_tasks_created_at ON conversion_tasks(created_at);

-- 添加注释
COMMENT ON TABLE conversion_tasks IS '文档转换任务表';
COMMENT ON COLUMN conversion_tasks.id IS '任务唯一标识';
COMMENT ON COLUMN conversion_tasks.user_id IS '关联用户ID（外键）';
COMMENT ON COLUMN conversion_tasks.source_file IS '源文件路径';
COMMENT ON COLUMN conversion_tasks.template_file IS '模板文件路径';
COMMENT ON COLUMN conversion_tasks.converted_file IS '转换后文件路径';
COMMENT ON COLUMN conversion_tasks.status IS '任务状态（pending、processing、completed、failed）';
COMMENT ON COLUMN conversion_tasks.progress IS '转换进度（0-100）';
COMMENT ON COLUMN conversion_tasks.error_message IS '错误信息（失败时）';
COMMENT ON COLUMN conversion_tasks.completed_at IS '任务完成时间';
COMMENT ON COLUMN conversion_tasks.created_at IS '任务创建时间';
COMMENT ON COLUMN conversion_tasks.updated_at IS '最后更新时间';

-- =====================================================
-- 3. system_config 表（系统配置）
-- =====================================================
CREATE TABLE IF NOT EXISTS system_config (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    description VARCHAR(500),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_config(config_key);

-- 添加注释
COMMENT ON TABLE system_config IS '系统配置表';
COMMENT ON COLUMN system_config.config_key IS '配置键（唯一）';
COMMENT ON COLUMN system_config.config_value IS '配置值';
COMMENT ON COLUMN system_config.description IS '配置描述';
COMMENT ON COLUMN system_config.updated_at IS '最后更新时间';

-- 插入默认配置
INSERT INTO system_config (config_key, config_value, description) VALUES
    ('free_paragraphs_daily', '10000', '每日免费段落额度'),
    ('paragraph_price', '0.001', '每个段落的价格（元）'),
    ('max_file_size_mb', '50', '最大文件大小（MB）'),
    ('admin_contact', '微信号：your_wechat_id', '管理员联系方式')
ON CONFLICT (config_key) DO NOTHING;

-- =====================================================
-- 4. comments 表（评论）
-- =====================================================
CREATE TABLE IF NOT EXISTS comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(50),                   -- 用户ID
    username VARCHAR(100),                 -- 用户名
    content TEXT NOT NULL,                 -- 评论内容
    rating INTEGER DEFAULT 5,              -- 评分（1-5）
    likes INTEGER DEFAULT 0,               -- 点赞数
    created_at TIMESTAMPTZ DEFAULT NOW()   -- 创建时间
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_comments_user_id ON comments(user_id);
CREATE INDEX IF NOT EXISTS idx_comments_created_at ON comments(created_at);
CREATE INDEX IF NOT EXISTS idx_comments_rating ON comments(rating);

-- 添加注释
COMMENT ON TABLE comments IS '用户评论表';
COMMENT ON COLUMN comments.user_id IS '用户ID';
COMMENT ON COLUMN comments.username IS '用户名';
COMMENT ON COLUMN comments.content IS '评论内容';
COMMENT ON COLUMN comments.rating IS '评分（1-5星）';
COMMENT ON COLUMN comments.likes IS '点赞数';
COMMENT ON COLUMN comments.created_at IS '评论创建时间';

-- =====================================================
-- 5. feedbacks 表（反馈）
-- =====================================================
CREATE TABLE IF NOT EXISTS feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(50),                   -- 用户ID
    feedback_type VARCHAR(50),             -- 反馈类型
    title VARCHAR(200),                    -- 标题
    description TEXT,                      -- 详细描述
    contact VARCHAR(100),                  -- 联系方式
    status VARCHAR(20) DEFAULT 'pending',  -- 状态
    reply TEXT,                            -- 管理员回复
    created_at TIMESTAMPTZ DEFAULT NOW(),  -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT NOW()   -- 更新时间
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_feedbacks_user_id ON feedbacks(user_id);
CREATE INDEX IF NOT EXISTS idx_feedbacks_status ON feedbacks(status);
CREATE INDEX IF NOT EXISTS idx_feedbacks_created_at ON feedbacks(created_at);

-- 添加注释
COMMENT ON TABLE feedbacks IS '用户反馈表';
COMMENT ON COLUMN feedbacks.user_id IS '用户ID';
COMMENT ON COLUMN feedbacks.feedback_type IS '反馈类型（建议、Bug报告、问题等）';
COMMENT ON COLUMN feedbacks.title IS '反馈标题';
COMMENT ON COLUMN feedbacks.description IS '详细描述';
COMMENT ON COLUMN feedbacks.contact IS '联系方式';
COMMENT ON COLUMN feedbacks.status IS '状态（pending、processing、resolved）';
COMMENT ON COLUMN feedbacks.reply IS '管理员回复';
COMMENT ON COLUMN feedbacks.created_at IS '创建时间';
COMMENT ON COLUMN feedbacks.updated_at IS '更新时间';

-- =====================================================
-- 6. style_mappings 表（样式映射）
-- =====================================================
CREATE TABLE IF NOT EXISTS style_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(50) NOT NULL,          -- 用户ID
    filename VARCHAR(255) NOT NULL,        -- 文件名
    source_style VARCHAR(255) NOT NULL,    -- 源样式名称
    target_style VARCHAR(255) NOT NULL,    -- 目标样式名称
    created_at TIMESTAMPTZ DEFAULT NOW()   -- 创建时间
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_style_mappings_user_id ON style_mappings(user_id);
CREATE INDEX IF NOT EXISTS idx_style_mappings_filename ON style_mappings(filename);
CREATE INDEX IF NOT EXISTS idx_style_mappings_created_at ON style_mappings(created_at);

-- 添加注释
COMMENT ON TABLE style_mappings IS '样式映射配置表';
COMMENT ON COLUMN style_mappings.user_id IS '用户ID';
COMMENT ON COLUMN style_mappings.filename IS '文件名';
COMMENT ON COLUMN style_mappings.source_style IS '源样式名称';
COMMENT ON COLUMN style_mappings.target_style IS '目标样式名称';
COMMENT ON COLUMN style_mappings.created_at IS '创建时间';

-- =====================================================
-- 7. alembic_version 表（数据库版本管理）
-- =====================================================
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);

-- 添加注释
COMMENT ON TABLE alembic_version IS 'Alembic 数据库版本管理表';
COMMENT ON COLUMN alembic_version.version_num IS '版本号';

-- =====================================================
-- 8. 创建触发器函数 - 自动更新 updated_at
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为需要自动更新 updated_at 的表创建触发器
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_conversion_tasks_updated_at ON conversion_tasks;
CREATE TRIGGER update_conversion_tasks_updated_at
    BEFORE UPDATE ON conversion_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_system_config_updated_at ON system_config;
CREATE TRIGGER update_system_config_updated_at
    BEFORE UPDATE ON system_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_feedbacks_updated_at ON feedbacks;
CREATE TRIGGER update_feedbacks_updated_at
    BEFORE UPDATE ON feedbacks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 9. 创建视图 - 方便查询
-- =====================================================

-- 用户统计视图
CREATE OR REPLACE VIEW user_statistics AS
SELECT 
    u.id,
    u.username,
    u.balance,
    u.paragraphs_remaining,
    u.total_paragraphs_used,
    u.total_converted,
    u.is_active,
    u.created_at,
    u.last_login,
    COUNT(ct.id) as task_count,
    COUNT(CASE WHEN ct.status = 'completed' THEN 1 END) as completed_tasks,
    COUNT(CASE WHEN ct.status = 'failed' THEN 1 END) as failed_tasks
FROM users u
LEFT JOIN conversion_tasks ct ON u.id = ct.user_id
GROUP BY u.id;

COMMENT ON VIEW user_statistics IS '用户统计视图（包含任务统计）';

-- =====================================================
-- 10. 插入测试数据（可选）
-- =====================================================

-- 插入测试用户
INSERT INTO users (id, username, balance, paragraphs_remaining, total_paragraphs_used, total_converted, is_active, created_at, last_login) VALUES
    ('test001abc', '测试用户1', 0.0, 10000, 0, 0, TRUE, NOW(), NOW()),
    ('test002def', '测试用户2', 0.0, 10000, 500, 5, TRUE, NOW() - INTERVAL '7 days', NOW() - INTERVAL '1 day'),
    ('test003ghi', '测试用户3', 0.0, 8000, 2000, 20, TRUE, NOW() - INTERVAL '30 days', NOW() - INTERVAL '2 hours')
ON CONFLICT (id) DO NOTHING;

-- 插入测试转换任务
INSERT INTO conversion_tasks (user_id, source_file, template_file, converted_file, status, progress, created_at, completed_at) VALUES
    ('test002def', '/uploads/source_1.docx', '/templates/template_1.docx', '/results/result_1.docx', 'completed', 100, NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days' + INTERVAL '2 minutes'),
    ('test002def', '/uploads/source_2.docx', '/templates/template_1.docx', '/results/result_2.docx', 'completed', 100, NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days' + INTERVAL '3 minutes'),
    ('test003ghi', '/uploads/source_3.docx', '/templates/template_2.docx', NULL, 'failed', 45, NOW() - INTERVAL '1 day', NULL)
ON CONFLICT DO NOTHING;

-- 插入测试反馈
INSERT INTO feedbacks (user_id, feedback_type, title, description, contact, status, created_at) VALUES
    ('test002def', '建议', '希望增加批量转换功能', '目前只能单个文件转换，希望能支持批量上传和转换', 'test@example.com', 'pending', NOW() - INTERVAL '2 days'),
    ('test003ghi', 'Bug报告', '某些特殊表格转换失败', '包含合并单元格的表格转换后格式错乱', NULL, 'processing', NOW() - INTERVAL '1 day')
ON CONFLICT DO NOTHING;

-- =====================================================
-- 完成提示
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'WordStyle 数据库初始化完成！';
    RAISE NOTICE '========================================';
    RAISE NOTICE '已创建表:';
    RAISE NOTICE '  - users (用户信息)';
    RAISE NOTICE '  - conversion_tasks (转换任务)';
    RAISE NOTICE '  - system_config (系统配置)';
    RAISE NOTICE '  - comments (评论)';
    RAISE NOTICE '  - feedbacks (反馈)';
    RAISE NOTICE '  - style_mappings (样式映射)';
    RAISE NOTICE '  - alembic_version (版本管理)';
    RAISE NOTICE '========================================';
    RAISE NOTICE '已插入测试数据:';
    RAISE NOTICE '  - 3个测试用户';
    RAISE NOTICE '  - 3个测试任务';
    RAISE NOTICE '  - 2个测试反馈';
    RAISE NOTICE '========================================';
    RAISE NOTICE '提示: 可以在 Supabase Dashboard 中查看数据';
    RAISE NOTICE '========================================';
END $$;
