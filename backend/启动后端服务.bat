@echo off
chcp 65001 >nul
echo ========================================
echo   WordStyle Pro Backend - 快速启动
echo ========================================
echo.

REM 检查虚拟环境
if not exist "venv" (
    echo [1/4] 创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo ✅ 虚拟环境创建成功
) else (
    echo [1/4] 虚拟环境已存在
)

echo.
echo [2/4] 激活虚拟环境...
call venv\Scripts\activate.bat

echo.
echo [3/4] 安装依赖包...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ 安装依赖失败
    pause
    exit /b 1
)
echo ✅ 依赖安装完成

echo.
echo [4/4] 检查配置文件...
if not exist ".env" (
    echo ⚠️  .env 文件不存在，从 .env.example 复制...
    copy .env.example .env
    echo ⚠️  请编辑 .env 文件配置数据库和支付信息
) else (
    echo ✅ 配置文件已存在
)

echo.
echo ========================================
echo   启动 FastAPI 服务器
echo ========================================
echo.
echo 📖 API 文档: http://localhost:8000/docs
echo 🔍 ReDoc: http://localhost:8000/redoc
echo.
echo 按 Ctrl+C 停止服务器
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
