# Render 环境变量配置检查清单

**检查时间**: 2026-05-16  
**测试环境服务**: 
- 后端API: https://wstest-backend.onrender.com
- 用户页面: https://wsprj.onrender.com
- 管理后台: https://wsprj-admin.onrender.com

---

## 📋 Render 环境变量配置要求

根据记忆中的配置规范和当前项目需求，以下是必须配置的环境变量：

### 🔴 必需配置项

#### 1. DATABASE_URL (最关键)

**格式要求**:
```
postgresql://postgres.{project_id}:{password}@aws-{region}.pooler.supabase.com:6543/postgres
```

**测试环境正确值**:
```
postgresql://postgres.inptqgbpmbgizcnrcqxb:wanli%4019780703@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres
```

**常见错误**:
- ❌ 使用直连地址（端口5432）而非连接池器（端口6543）
- ❌ 密码中的`@`未URL编码为`%40`
- ❌ 使用了错误的project_id或region
- ❌ URL被方括号包围
- ❌ 使用了占位符而非真实地址

**验证方法**:
```bash
# 在浏览器访问后端健康检查
curl https://wstest-backend.onrender.com/health
# 应返回: {"status": "healthy"}
```

---

#### 2. SECRET_KEY

**生成方式**:
```python
import secrets
print(secrets.token_urlsafe(32))
```

**或使用Render的"Generate Value"功能自动生成**

**注意**: 
- 所有三个服务（backend、wsprj、wsprj-admin）可以使用相同的SECRET_KEY
- 长度至少32字符

---

#### 3. ALLOWED_ORIGINS

**后端API服务** (wstest-backend.onrender.com):
```
https://*.streamlit.app,https://wsprj.onrender.com,https://wsprj-admin.onrender.com
```

**前端服务** (wsprj.onrender.com 和 wsprj-admin.onrender.com):
```
https://*.streamlit.app
```

**说明**:
- 允许所有Streamlit Cloud域名跨域访问
- 后端需要额外允许前端服务的域名

---

#### 4. DEBUG

**生产环境必须设置为**:
```
false
```

**注意**: 
- 不要设置为`True`或`true`（大小写敏感）
- 必须是字符串`"false"`

---

#### 5. UPLOAD_DIR

**Render临时目录**:
```
/tmp/uploads
```

**说明**:
- Render重启后会清空此目录
- 不要使用相对路径如`./uploads`

---

### 🟡 可选配置项

#### 6. BACKEND_URL (仅前端服务需要)

**用户页面** (wsprj.onrender.com):
```
https://wstest-backend.onrender.com
```

**管理后台** (wsprj-admin.onrender.com):
```
https://wstest-backend.onrender.com
```

**说明**:
- 只有前端Streamlit应用需要此变量
- 后端API服务不需要
- 用于启用API模式

---

#### 7. USE_SUPABASE (仅前端服务需要)

**值**:
```
true
```

**说明**:
- 设置为`true`启用Supabase/API模式
- 与BACKEND_URL配合使用
- 后端API服务不需要此变量

---

## 🔍 各服务配置对比

### 后端API服务 (wstest-backend.onrender.com)

| 变量名 | 必需 | 值 |
|--------|------|-----|
| DATABASE_URL | ✅ | `postgresql://postgres.inptqgbpmbgizcnrcqxb:wanli%4019780703@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres` |
| SECRET_KEY | ✅ | (自动生成或手动设置) |
| ALLOWED_ORIGINS | ✅ | `https://*.streamlit.app,https://wsprj.onrender.com,https://wsprj-admin.onrender.com` |
| DEBUG | ✅ | `false` |
| UPLOAD_DIR | ✅ | `/tmp/uploads` |
| BACKEND_URL | ❌ | 不需要 |
| USE_SUPABASE | ❌ | 不需要 |

---

### 用户页面 (wsprj.onrender.com)

| 变量名 | 必需 | 值 |
|--------|------|-----|
| BACKEND_URL | ✅ | `https://wstest-backend.onrender.com` |
| USE_SUPABASE | ✅ | `true` |
| DATABASE_URL | ⚠️ | 同后端（用于fallback） |
| SECRET_KEY | ⚠️ | 同后端 |
| ALLOWED_ORIGINS | ⚠️ | `https://*.streamlit.app` |
| DEBUG | ⚠️ | `false` |
| UPLOAD_DIR | ⚠️ | `/tmp/uploads` |

**注意**: 
- Streamlit应用在API模式下主要通过BACKEND_URL访问后端
- DATABASE_URL等作为本地fallback使用

---

### 管理后台 (wsprj-admin.onrender.com)

| 变量名 | 必需 | 值 |
|--------|------|-----|
| BACKEND_URL | ✅ | `https://wstest-backend.onrender.com` |
| USE_SUPABASE | ✅ | `true` |
| DATABASE_URL | ⚠️ | 同后端（用于fallback） |
| SECRET_KEY | ⚠️ | 同后端 |
| ALLOWED_ORIGINS | ⚠️ | `https://*.streamlit.app` |
| DEBUG | ⚠️ | `false` |
| UPLOAD_DIR | ⚠️ | `/tmp/uploads` |

---

## ⚠️ 常见问题排查

### 问题1: 所有API返回500错误

**可能原因**:
- DATABASE_URL配置错误
- 密码特殊字符未URL编码
- 使用了错误的Supabase项目ID

**解决方法**:
1. 检查DATABASE_URL格式是否正确
2. 确认密码中的`@`已编码为`%40`
3. 验证Supabase项目ID和region是否正确
4. 查看Render Logs中的错误信息

---

### 问题2: 管理后台显示"数据源: local"

**可能原因**:
- BACKEND_URL未配置
- USE_SUPABASE未设置为`true`
- config.py无法读取环境变量

**解决方法**:
1. 确认BACKEND_URL已配置且指向正确的后端地址
2. 确认USE_SUPABASE设置为`true`（不是`True`）
3. 检查config.py是否能正确读取环境变量
4. 重启服务使配置生效

---

### 问题3: CORS错误

**可能原因**:
- ALLOWED_ORIGINS配置不完整
- 缺少前端域名

**解决方法**:
1. 后端ALLOWED_ORIGINS必须包含所有前端域名
2. 使用`https://*.streamlit.app`允许所有Streamlit Cloud域名
3. 添加具体的Render域名如`https://wsprj.onrender.com`

---

### 问题4: 数据库迁移失败

**可能原因**:
- DATABASE_URL配置错误
- Alembic配置问题
- 多head冲突

**解决方法**:
1. 确认DATABASE_URL可连接
2. 检查main.py中的run_migrations()函数
3. 查看Logs中的Alembic错误信息
4. 可能需要手动执行`alembic stamp head`

---

## ✅ 配置验证步骤

### 步骤1: 检查后端健康状态

```bash
curl https://wstest-backend.onrender.com/health
```

**期望输出**:
```json
{"status": "healthy"}
```

---

### 步骤2: 检查API文档是否可访问

访问: https://wstest-backend.onrender.com/docs

**期望**: 能看到Swagger UI界面

---

### 步骤3: 测试免费额度接口

```bash
curl -X POST https://wstest-backend.onrender.com/api/admin/users/test-user-id/claim-free
```

**期望**: 返回成功响应，包含paragraphs字段

---

### 步骤4: 检查前端数据源显示

访问: https://wsprj-admin.onrender.com

**期望**: 页面顶部显示"数据源: API (https://wstest-backend.onrender.com)"

**如果显示"数据源: local"**，说明BACKEND_URL或USE_SUPABASE配置有问题

---

### 步骤5: 查看Render Logs

1. 登录Render Dashboard
2. 选择对应的服务
3. 点击"Logs"标签
4. 查看启动日志和运行时错误

**关键日志**:
- `✅ 从环境变量加载 DATABASE_URL`
- `✅ 数据库迁移完成`
- `🚀 WordStyle Pro v1.0.0 启动中...`

---

## 📝 配置操作指南

### 如何在Render控制台配置环境变量

1. **登录Render Dashboard**
   - 访问: https://dashboard.render.com/

2. **选择服务**
   - 找到对应的服务（wstest-backend、wsprj、wsprj-admin）

3. **进入Environment标签**
   - 点击服务名称
   - 选择"Environment"标签页

4. **添加/编辑环境变量**
   - 点击"Add Environment Variable"
   - 输入Key和Value
   - 点击"Save Changes"

5. **触发重新部署**
   - 保存后会自动触发重新部署
   - 或在"Manual Deploy"中点击"Deploy latest commit"

6. **验证配置**
   - 等待部署完成
   - 查看Logs确认配置加载成功
   - 访问健康检查端点验证

---

## 🎯 当前配置状态检查

根据你提供的配置信息：

### ✅ 后端API (wstest-backend.onrender.com)
```
DATABASE_URL=postgresql://postgres.inptqgbpmbgizcnrcqxb:wanli%4019780703@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres ✅
SECRET_KEY=f5f31149f5964c1b87be8555c38325a32925afda3628a4015d7bd18d0c436925 ✅
ALLOWED_ORIGINS=https://*.streamlit.app ⚠️ (建议添加前端域名)
DEBUG=false ✅
UPLOAD_DIR=/tmp/uploads ✅
```

### ✅ 用户页面 (wsprj.onrender.com)
```
BACKEND_URL=https://wstest-backend.onrender.com ✅
USE_SUPABASE=true ✅
DATABASE_URL=postgresql://postgres.inptqgbpmbgizcnrcqxb:wanli%4019780703@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres ✅
SECRET_KEY=f5f31149f5964c1b87be8555c38325a32925afda3628a4015d7bd18d0c436925 ✅
ALLOWED_ORIGINS=https://*.streamlit.app ✅
DEBUG=false ✅
UPLOAD_DIR=/tmp/uploads ✅
```

### ✅ 管理后台 (wsprj-admin.onrender.com)
```
BACKEND_URL=https://wstest-backend.onrender.com ✅
USE_SUPABASE=true ✅
DATABASE_URL=postgresql://postgres.inptqgbpmbgizcnrcqxb:wanli%4019780703@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres ✅
SECRET_KEY=f5f31149f5964c1b87be8555c38325a32925afda3628a4015d7bd18d0c436925 ✅
ALLOWED_ORIGINS=https://*.streamlit.app ✅
DEBUG=false ✅
UPLOAD_DIR=/tmp/upload ⚠️ (应该是/tmp/uploads，少了一个s)
```

---

## ⚠️ 发现的问题

### 问题1: 管理后台UPLOAD_DIR拼写错误

**当前值**: `/tmp/upload`  
**正确值**: `/tmp/uploads`

**影响**: 
- 文件上传可能失败
- 与其他服务不一致

**修复**: 在Render控制台修改为`/tmp/uploads`

---

### 问题2: 后端ALLOWED_ORIGINS可能不完整

**当前值**: `https://*.streamlit.app`  
**建议值**: `https://*.streamlit.app,https://wsprj.onrender.com,https://wsprj-admin.onrender.com`

**影响**: 
- 如果前端部署在Render而非Streamlit Cloud，可能会有CORS问题
- 当前配置应该够用（因为前端也在*.streamlit.app下）

---

## 📊 总结

### ✅ 配置正确的部分
1. DATABASE_URL格式正确，使用了连接池器和URL编码
2. BACKEND_URL和USE_SUPABASE已正确配置
3. SECRET_KEY统一
4. DEBUG设置为false

### ⚠️ 需要修复的问题
1. **管理后台UPLOAD_DIR拼写错误** (`/tmp/upload` → `/tmp/uploads`)

### 💡 建议优化
1. 后端ALLOWED_ORIGINS可以添加具体的Render域名（可选）

---

## 🚀 下一步行动

1. **立即修复**: 在Render控制台修正管理后台的UPLOAD_DIR
2. **验证配置**: 访问各服务的健康检查端点
3. **测试功能**: 尝试转换文件和管理后台功能
4. **查看日志**: 确认没有ERROR级别的日志

需要我帮你生成具体的修复命令或验证脚本吗？
