# Supabase 数据库初始化指南

## 📋 前置准备

1. **注册 Supabase 账号**
   - 访问 https://supabase.com
   - 使用 GitHub 账号登录或注册

2. **创建新项目**
   - 点击 "New Project"
   - 填写项目名称（如：wordstyle-test）
   - 设置数据库密码（**请妥善保管**）
   - 选择区域（推荐：Singapore 或 Tokyo，离中国较近）
   - 点击 "Create new project"

3. **等待项目初始化**
   - 通常需要 1-2 分钟
   - 完成后会显示项目 Dashboard

---

## 🔧 执行初始化脚本

### 方法一：通过 SQL Editor（推荐）

1. **进入 SQL Editor**
   - 在左侧菜单点击 "SQL Editor"
   - 点击 "New query"

2. **复制并执行脚本**
   - 打开 `E:\LingMa\WSprj\supabase_init.sql`
   - 复制全部内容
   - 粘贴到 SQL Editor
   - 点击 "Run" 按钮（或按 Ctrl+Enter）

3. **验证结果**
   - 查看底部输出面板
   - 应该看到类似以下提示：
     ```
     ========================================
     WordStyle 数据库初始化完成！
     ========================================
     已创建表:
       - users (用户信息)
       - conversion_tasks (转换任务)
       ...
     ========================================
     ```

### 方法二：通过 psql 命令行

```bash
# 获取连接信息
# 在 Supabase Dashboard -> Settings -> Database -> Connection string

# 使用 psql 连接
psql "postgresql://postgres.{project_id}:{password}@aws-{region}.pooler.supabase.com:6543/postgres"

# 执行脚本
\i E:/LingMa/WSprj/supabase_init.sql
```

---

## ✅ 验证数据库

### 1. 检查表是否创建成功

在 SQL Editor 中执行：

```sql
-- 查看所有表
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY table_name;
```

应该看到以下7个表：
- `alembic_version`
- `comments`
- `conversion_tasks`
- `feedbacks`
- `style_mappings`
- `system_config`
- `users`

### 2. 检查测试数据

```sql
-- 查看用户数据
SELECT id, username, paragraphs_remaining, total_converted 
FROM users;

-- 查看转换任务
SELECT user_id, status, created_at 
FROM conversion_tasks;

-- 查看系统配置
SELECT config_key, config_value 
FROM system_config;
```

### 3. 测试视图

```sql
-- 查看用户统计
SELECT * FROM user_statistics;
```

---

## 🔑 获取数据库连接信息

### 1. 找到连接字符串

1. 进入 Supabase Dashboard
2. 左侧菜单点击 **"Settings"** → **"Database"**
3. 找到 **"Connection string"** 部分
4. 选择 **"Transaction mode"**（端口 6543）
5. 复制连接字符串

格式如下：
```
postgresql://postgres.{project_id}:{your_password}@aws-{region}.pooler.supabase.com:6543/postgres
```

### 2. URL 编码特殊字符

如果密码包含特殊字符，需要进行 URL 编码：

| 特殊字符 | URL 编码 |
|---------|---------|
| `@` | `%40` |
| `#` | `%23` |
| `$` | `%24` |
| `%` | `%25` |
| `&` | `%26` |
| `=` | `%3D` |
| `+` | `%2B` |
| `?` | `%3F` |

**示例**：
- 原始密码：`My@Pass#123`
- 编码后：`My%40Pass%23123`

---

## 🚀 配置本地应用

### 1. 创建 .env 文件

在工作目录 `E:\LingMa\WSprj` 创建 `.env` 文件：

```env
# Supabase 配置
USE_SUPABASE=true
DATABASE_URL=postgresql://postgres.{project_id}:{encoded_password}@aws-{region}.pooler.supabase.com:6543/postgres

# 后端 API（可选，如果不使用 API 模式可以留空）
BACKEND_URL=
```

**注意**：
- `USE_SUPABASE=true` 启用 Supabase 模式
- `DATABASE_URL` 使用上面获取的连接字符串（记得 URL 编码密码）
- `BACKEND_URL` 留空表示不使用 API 模式

### 2. 重启应用

```bash
# 停止当前运行的应用（Ctrl+C）

# 重新启动
cd E:\LingMa\WSprj
streamlit run app.py --server.port 8501
streamlit run admin_web.py --server.port 8502
```

启动时应该看到：
```
💾 数据源模式: Supabase (直接连接)
✅ 数据访问层初始化：Supabase 模式 (PostgreSQL)
```

---

## 📊 管理数据库

### 1. 通过 Supabase Dashboard

- **Table Editor**: 可视化查看和编辑数据
- **SQL Editor**: 执行自定义 SQL 查询
- **Authentication**: 管理用户认证（如果使用）
- **Logs**: 查看数据库日志

### 2. 常用查询

```sql
-- 查看最近创建的用戶
SELECT * FROM users ORDER BY created_at DESC LIMIT 10;

-- 查看失败的任务
SELECT * FROM conversion_tasks WHERE status = 'failed';

-- 统计每日用户数
SELECT DATE(created_at) as date, COUNT(*) as user_count
FROM users
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- 清空测试数据（谨慎使用）
DELETE FROM feedbacks;
DELETE FROM conversion_tasks;
DELETE FROM users WHERE id LIKE 'test%';
```

---

## ⚠️ 注意事项

### 1. 安全建议

- **不要将 `.env` 文件提交到 Git**
  - 确保 `.gitignore` 中包含 `.env`
  
- **定期备份数据库**
  - Supabase 提供自动备份（付费计划）
  - 也可以手动导出 SQL

- **限制数据库访问**
  - 在 Supabase Settings → Database → Network 中配置允许访问的 IP

### 2. 性能优化

- **使用连接池器**（已默认使用端口 6543）
- **添加适当的索引**（脚本中已包含常用索引）
- **定期清理过期数据**（如旧的转换任务）

### 3. 常见问题

**Q: 连接超时？**
A: 检查防火墙设置，确保允许访问 Supabase 服务器

**Q: 认证失败？**
A: 检查密码是否正确，特殊字符是否已 URL 编码

**Q: 表不存在？**
A: 确认脚本是否成功执行，检查是否有错误信息

---

## 📚 相关文档

- [Supabase 官方文档](https://supabase.com/docs)
- [PostgreSQL 文档](https://www.postgresql.org/docs/)
- [WordStyle 系统设计文档](./docs/02-系统设计文档.md)
- [WordStyle 部署文档](./docs/05-系统部署详细文档.md)

---

## 🆘 需要帮助？

如果遇到问题：
1. 检查 SQL Editor 中的错误信息
2. 查看应用启动日志
3. 参考 WordStyle 项目文档
4. 联系项目管理员
