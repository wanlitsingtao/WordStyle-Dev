# Backend - FastAPI 生产级后端

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填写数据库、Redis、支付密钥等配置
```

### 3. 启动数据库和 Redis

```bash
docker-compose up -d postgres redis
```

### 4. 运行数据库迁移

```bash
alembic upgrade head
```

### 5. 启动开发服务器

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 查看 API 文档

## 项目结构

```
backend/
├── app/
│   ├── api/              # API 路由
│   ├── core/             # 核心配置
│   ├── models/           # 数据模型
│   ├── schemas/          # Pydantic 模式
│   ├── services/         # 业务逻辑
│   ├── tasks/            # Celery 任务
│   └── main.py           # 应用入口
├── tests/                # 测试代码
├── alembic/              # 数据库迁移
├── requirements.txt
└── Dockerfile
```

## API 端点

### 认证
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/logout` - 用户登出
- `GET /api/auth/me` - 获取当前用户信息

### 用户
- `GET /api/users/profile` - 获取个人资料
- `PUT /api/users/profile` - 更新个人资料
- `GET /api/users/balance` - 查询余额

### 支付
- `POST /api/payments/create-order` - 创建支付订单
- `POST /api/payments/wechat/callback` - 微信支付回调
- `POST /api/payments/alipay/callback` - 支付宝回调
- `GET /api/payments/orders` - 查询订单列表

### 转换
- `POST /api/conversions/upload` - 上传文件
- `POST /api/conversions/start` - 开始转换
- `GET /api/conversions/{task_id}/status` - 查询任务状态
- `GET /api/conversions/{task_id}/download` - 下载结果
- `GET /api/conversions/history` - 转换历史

### 管理
- `GET /api/admin/users` - 用户列表
- `GET /api/admin/orders` - 订单列表
- `GET /api/admin/stats` - 统计数据

## 开发指南

### 添加新的 API 端点

1. 在 `app/api/` 下创建新的路由文件
2. 定义 Pydantic schemas 在 `app/schemas/`
3. 实现业务逻辑在 `app/services/`
4. 在 `app/main.py` 中注册路由

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

## 部署

### Docker 部署

```bash
docker build -t wordstyle-backend .
docker run -d --name backend -p 8000:8000 wordstyle-backend
```

### 生产环境

使用 `docker-compose.prod.yml` 进行生产部署：

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 监控

- 健康检查: `GET /health`
- 指标: `GET /metrics` (Prometheus)
- 日志: 查看 Docker logs 或 ELK

## 常见问题

### Q: 如何重置数据库？
```bash
docker-compose down -v
docker-compose up -d
alembic upgrade head
```

### Q: 如何查看 Celery 任务队列？
```bash
celery -A app.core.celery_app inspect active
```

### Q: 支付回调不工作？
检查：
1. 公网可访问的回调 URL
2. 支付平台配置的回调地址
3. 签名验证逻辑
