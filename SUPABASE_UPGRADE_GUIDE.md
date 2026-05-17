# Supabase数据库手动升级指南

## 📋 问题诊断结果

经过检查，发现Supabase数据库存在以下问题：

### ❌ 当前状态
1. **alembic_version表为空** - 迁移记录丢失
2. **conversion_tasks表缺少paragraphs字段** - 最新迁移未执行

### ✅ 预期状态
- alembic_version: `20260517_1330`
- conversion_tasks表包含paragraphs字段（INTEGER, DEFAULT 0）

---

## 🔧 手动升级步骤

### 方法1: 使用Supabase Dashboard（推荐）

#### 步骤1: 打开SQL Editor
1. 登录 [Supabase Dashboard](https://app.supabase.com)
2. 选择您的项目
3. 点击左侧菜单的 **SQL Editor**

#### 步骤2: 执行升级脚本
1. 点击 **New query**
2. 复制 `manual_upgrade_supabase.sql` 文件的全部内容
3. 粘贴到SQL Editor中
4. 点击 **Run** 按钮执行

#### 步骤3: 验证结果
执行后应该看到以下输出：
```
✅ 成功添加 paragraphs 字段到 conversion_tasks 表
✅ 成功创建 alembic_version 表
✅ 成功更新 alembic_version 到 20260517_1330
✅ paragraphs 字段验证通过
✅ Alembic版本验证通过
```

---

### 方法2: 使用psql命令行工具

#### 步骤1: 获取数据库连接信息
从 `.env` 文件中找到 `DATABASE_URL`，格式类似：
```
postgresql://postgres.inptqgbpmbgizcnrcqxb:[密码]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
```

#### 步骤2: 连接数据库
```bash
psql "postgresql://postgres.inptqgbpmbgizcnrcqxb:[密码]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
```

#### 步骤3: 执行升级脚本
```sql
\i E:/LingMa/WSprj/manual_upgrade_supabase.sql
```

或者直接复制SQL内容粘贴执行。

---

## ⚠️ 注意事项

### 执行前
1. **备份数据库**（可选但推荐）
   - Supabase Dashboard → Database → Backups
   - 或导出SQL dump

2. **确认连接的是正确的数据库**
   - 检查DATABASE_URL中的项目ID

3. **在低峰期执行**
   - 避免影响正在使用的用户

### 执行中
1. **观察输出信息**
   - 确保所有步骤都显示"✅ 成功"
   - 如果有错误，立即停止并检查

2. **不要中断执行**
   - 等待脚本完全执行完毕

### 执行后
1. **重启后端服务**
   - Render会自动重新部署（检测到代码变更）
   - 或手动触发重新部署

2. **检查后端日志**
   - 确认没有数据库相关错误
   - 查看是否有模型加载警告

3. **测试功能**
   - 提交一次文档转换
   - 检查转换历史是否正确显示段落数

---

## 🔍 验证升级成功

### 方法1: 运行检查脚本
```bash
python check_supabase_structure.py
```

应该看到：
```
📋 1. Alembic迁移版本:
   当前版本: 20260517_1330
   ✅ 数据库已是最新版本

📋 3. conversion_tasks表结构:
   - paragraphs                     integer              NULL DEFAULT 0
   ✅ paragraphs字段已存在
```

### 方法2: 在Supabase Dashboard中检查
1. 进入 **Table Editor**
2. 选择 `conversion_tasks` 表
3. 确认能看到 `paragraphs` 列

### 方法3: 直接查询
```sql
-- 检查paragraphs字段
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'conversion_tasks' 
AND column_name = 'paragraphs';

-- 检查alembic版本
SELECT * FROM alembic_version;
```

---

## 🐛 常见问题

### Q1: 执行时提示"字段已存在"
**A:** 这是正常的，脚本已经做了防护。如果看到"⚠️ paragraphs 字段已存在，跳过"，说明字段已经存在，可以安全继续。

### Q2: 执行失败，提示权限不足
**A:** 确保使用的是Supabase提供的连接字符串，而不是只读连接。需要使用具有写权限的用户。

### Q3: alembic_version表创建失败
**A:** 可能是表已存在但有冲突。可以尝试：
```sql
DROP TABLE IF EXISTS alembic_version;
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
INSERT INTO alembic_version VALUES ('20260517_1330');
```

### Q4: 升级后后端仍然报错
**A:** 
1. 检查Render后端是否已重新部署
2. 查看后端日志中的具体错误信息
3. 确认DATABASE_URL环境变量正确配置

---

## 📞 需要帮助？

如果遇到问题：
1. 保存完整的错误信息
2. 截图Supabase Dashboard的输出
3. 检查后端日志
4. 联系技术支持

---

## 📝 升级历史

| 日期 | 版本 | 变更内容 | 状态 |
|------|------|----------|------|
| 2026-05-17 | 20260517_1330 | 为conversion_tasks表添加paragraphs字段 | 待执行 |

---

**最后更新**: 2026-05-17  
**文档版本**: 1.0
