@echo off
chcp 65001 >nul
echo ========================================
echo   WordStyle Pro Backend - 快速启动
echo ========================================
echo.

REM 检查Python环境（优先使用 py 启动器）
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    set PIP_CMD=py -m pip
    goto :python_found
)

python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    set PIP_CMD=python -m pip
    goto :python_found
)

echo [ERROR] Python未安装或不在PATH中
echo.
echo 注意：安装时务必勾选 "Add Python to PATH" 选项
echo 如果已安装但仍报此错误，请在 Windows 设置中：
echo   应用 ^> 应用执行别名 ^> 关闭 python.exe 和 python3.exe 的别名
pause
exit /b 1

:python_found
echo [OK] 检测到Python: %PYTHON_CMD%
%PYTHON_CMD% --version

REM 检查虚拟环境
if not exist "venv" (
    echo.
    echo [1/4] 创建虚拟环境...
    %PYTHON_CMD% -m venv venv
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
