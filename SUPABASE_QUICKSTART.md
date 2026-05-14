# Supabase 数据库切换 - 快速开始

## 📦 已创建的文件

1. **`supabase_init.sql`** - 完整的数据库初始化脚本
2. **`SUPABASE_SETUP_GUIDE.md`** - 详细的配置指南
3. **`.env.example`** - 环境变量配置模板
4. **`启动Supabase模式.bat`** - Windows 快速启动脚本

---

## 🚀 快速开始（3步完成）

### 第1步：在 Supabase 创建数据库

1. 访问 https://supabase.com 并登录
2. 点击 "New Project" 创建新项目
3. 记录数据库密码（后续需要用到）
4. 等待项目初始化完成（约1-2分钟）

### 第2步：执行初始化脚本

1. 进入 Supabase Dashboard → SQL Editor
2. 打开 `E:\LingMa\WSprj\supabase_init.sql`
3. 复制全部内容并粘贴到 SQL Editor
4. 点击 "Run" 执行
5. 确认看到 "WordStyle 数据库初始化完成！" 提示

### 第3步：配置本地应用

1. 获取数据库连接字符串：
   - Settings → Database → Connection string
   - 选择 "Transaction mode" (端口 6543)
   - 复制连接字符串

2. 创建 `.env` 文件：
   ```bash
   # 在工作目录 E:\LingMa\WSprj 执行
   copy .env.example .env
   ```

3. 编辑 `.env` 文件，填写实际的 `DATABASE_URL`

4. 双击运行 `启动Supabase模式.bat`

---

## ✅ 验证是否成功

启动后应该看到：
```
[INFO] 数据源模式: Supabase (直接连接)
[OK] 数据访问层初始化：Supabase 模式 (PostgreSQL)
```

访问：
- 主应用：http://localhost:8501
- 管理后台：http://localhost:8502

测试功能：
1. 上传文档进行转换
2. 查看用户信息是否正确保存到数据库
3. 在管理后台查看转换历史

---

## 🔍 故障排查

### 问题1：找不到 .env 文件

**解决**：
```bash
cd E:\LingMa\WSprj
copy .env.example .env
notepad .env
```

### 问题2：连接超时

**可能原因**：
- 防火墙阻止访问
- 网络连接问题
- Supabase 服务异常

**解决**：
1. 检查网络连接
2. 尝试 ping Supabase 服务器
3. 查看 Supabase Dashboard 状态

### 问题3：认证失败

**可能原因**：
- 密码错误
- 特殊字符未 URL 编码

**解决**：
1. 确认密码正确
2. 对特殊字符进行 URL 编码：
   - `@` → `%40`
   - `#` → `%23`
   - `$` → `%24`
   - 等等

### 问题4：表不存在

**解决**：
1. 确认 `supabase_init.sql` 已成功执行
2. 在 SQL Editor 中执行：
   ```sql
   SELECT table_name FROM information_schema.tables 
   WHERE table_schema = 'public';
   ```
3. 应该看到7个业务表

---

## 📊 数据库结构概览

| 表名 | 说明 | 字段数 |
|------|------|--------|
| `users` | 用户信息 | 11 |
| `conversion_tasks` | 转换任务 | 11 |
| `system_config` | 系统配置 | 5 |
| `comments` | 用户评论 | 7 |
| `feedbacks` | 用户反馈 | 10 |
| `style_mappings` | 样式映射 | 6 |
| `alembic_version` | 版本管理 | 1 |

**总计**：7个业务表 + 1个系统表

---

## 🎯 下一步

1. **测试基本功能**
   - 用户注册/登录
   - 文档转换
   - 查看历史记录

2. **监控数据库**
   - 使用 Supabase Dashboard 查看数据
   - 执行自定义 SQL 查询
   - 分析用户行为

3. **优化性能**
   - 添加更多索引（如需要）
   - 定期清理过期数据
   - 监控查询性能

4. **备份策略**
   - 启用 Supabase 自动备份
   - 定期手动导出 SQL
   - 测试恢复流程

---

## 📚 相关文档

- [详细配置指南](./SUPABASE_SETUP_GUIDE.md)
- [系统设计文档](./docs/02-系统设计文档.md)
- [部署文档](./docs/05-系统部署详细文档.md)

---

## 💡 提示

- **开发时**：可以使用本地 SQLite 模式（设置 `USE_SUPABASE=false`）
- **测试时**：使用 Supabase 测试数据库
- **生产环境**：使用 Supabase 生产数据库（建议付费计划）

---

## 🆘 需要帮助？

1. 查看详细指南：`SUPABASE_SETUP_GUIDE.md`
2. 检查应用日志
3. 查看 Supabase Dashboard 日志
4. 联系项目管理员
