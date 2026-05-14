# WordStyle Pro Backend - 快速开始指南

## 📋 目录

1. [项目概述](#项目概述)
2. [快速启动](#快速启动)
3. [API 文档](#api-文档)
4. [开发指南](#开发指南)
5. [部署说明](#部署说明)

---

## 项目概述

WordStyle Pro Backend 是一个基于 FastAPI 构建的生产级文档转换平台后端服务。

### 核心功能

✅ **用户认证系统**
- 邮箱注册/登录
- JWT Token 认证
- 密码加密存储（bcrypt）

✅ **支付系统**
- 微信支付集成
- 支付宝集成
- 订单管理
- 自动充值

✅ **文档转换**
- 异步任务处理
- 进度跟踪
- 历史记录
- 结果下载

### 技术栈

- **Web 框架**: FastAPI 0.104+
- **数据库**: PostgreSQL / SQLite（开发）
- **ORM**: SQLAlchemy 2.0+
- **认证**: JWT (PyJWT)
- **缓存**: Redis（可选）
- **任务队列**: Celery（可选）

---

## 快速启动

### 方式一：使用启动脚本（推荐）

```bash
# Windows
启动后端服务.bat

# Linux/Mac
chmod +x start.sh
./start.sh
```

### 方式二：手动启动

#### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 2. 配置环境变量

```bash
# 复制配置文件
cp .env.example .env

# 编辑 .env 文件（开发环境可使用默认值）
```

#### 3. 初始化数据库

```bash
python init_db.py
```

#### 4. 启动服务器

```bash
# 开发模式（使用 SQLite）
python run_dev.py

# 或
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 验证安装

访问 API 文档：http://localhost:8000/docs

运行测试脚本：
```bash
python test_api.py
```

---

## API 文档

启动服务后，访问以下地址查看完整 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 主要 API 端点

#### 认证接口

```
POST /api/auth/register    # 用户注册
POST /api/auth/login       # 用户登录
GET  /api/auth/me          # 获取当前用户信息
```

#### 用户接口

```
GET  /api/users/profile    # 获取个人资料
PUT  /api/users/profile    # 更新个人资料
GET  /api/users/balance    # 查询余额
```

#### 支付接口

```
POST /api/payments/create-order           # 创建充值订单
GET  /api/payments/{order_no}/status      # 查询订单状态
POST /api/payments/wechat/callback        # 微信支付回调
POST /api/payments/alipay/callback        # 支付宝回调
```

#### 转换接口

```
POST /api/conversions/start               # 开始转换
GET  /api/conversions/{task_id}/status    # 查询任务状态
GET  /api/conversions/history             # 转换历史
GET  /api/conversions/{task_id}/download  # 下载结果
```

---

## 开发指南

### 项目结构

```
backend/
├── app/
│   ├── api/              # API 路由
│   │   ├── auth.py       # 认证接口
│   │   ├── users.py      # 用户接口
│   │   ├── payments.py   # 支付接口
│   │   └── conversions.py # 转换接口
│   ├── core/             # 核心模块
│   │   ├── config.py     # 配置管理
│   │   ├── database.py   # 数据库连接
│   │   ├── security.py   # 安全模块
│   │   └── auth.py       # 认证依赖
│   ├── models.py         # 数据模型
│   ├── schemas.py        # Pydantic 模式
│   └── main.py           # 应用入口
├── alembic/              # 数据库迁移
├── tests/                # 测试代码
├── requirements.txt      # 依赖包
├── .env.example          # 配置模板
├── docker-compose.yml    # Docker 配置
└── README.md            # 本文档
```

### 添加新的 API 端点

1. **在 `app/api/` 下创建新路由文件**

```python
# app/api/example.py
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user

router = APIRouter()

@router.get("/example")
def get_example(current_user = Depends(get_current_user)):
    return {"message": "Hello"}
```

2. **在 `app/main.py` 中注册路由**

```python
from app.api import example
application.include_router(example.router, prefix="/api/example", tags=["示例"])
```

3. **定义 Pydantic Schema（如果需要）**

```python
# app/schemas.py
class ExampleRequest(BaseModel):
    name: str

class ExampleResponse(BaseModel):
    message: str
```

### 数据库迁移

```bash
# 创建新迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

### 运行测试

```bash
pytest tests/ -v
```

---

## 部署说明

### 开发环境

使用 SQLite 数据库，适合快速开发和测试：

```bash
python run_dev.py
```

### 生产环境

#### 1. 使用 Docker Compose

```bash
# 启动所有服务（PostgreSQL + Redis + Backend）
docker-compose up -d

# 查看日志
docker-compose logs -f backend

# 停止服务
docker-compose down
```

#### 2. 手动部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
vim .env  # 修改为生产配置

# 3. 初始化数据库
alembic upgrade head

# 4. 启动服务（使用 Gunicorn）
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

#### 3. Nginx 配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 4. SSL 证书

```bash
# 使用 Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 常见问题

### Q: 如何重置数据库？

```bash
# SQLite
rm wordstyle.db
python init_db.py

# PostgreSQL
docker-compose down -v
docker-compose up -d
alembic upgrade head
```

### Q: 端口被占用怎么办？

修改启动命令的端口号：
```bash
uvicorn app.main:app --reload --port 8001
```

### Q: 如何查看详细的错误日志？

设置 DEBUG=True 在 `.env` 文件中，或查看控制台输出。

### Q: 支付回调不工作？

检查：
1. 回调 URL 是否公网可访问
2. 支付平台配置的回调地址是否正确
3. 签名验证逻辑是否正确

---

## 下一步

1. ✅ 阅读 [IMPLEMENTATION_GUIDE.md](../IMPLEMENTATION_GUIDE.md) 了解完整实施方案
2. ✅ 集成 Streamlit 前端
3. ✅ 申请微信支付和支付宝商户号
4. ✅ 配置生产环境
5. ✅ 部署到服务器

---

**祝您开发顺利！** 🚀
