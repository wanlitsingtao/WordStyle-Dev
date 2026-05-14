@echo off
chcp 65001 >nul
echo ========================================
echo   WordStyle Pro - 前端测试页面
echo ========================================
echo.

REM 检查后端服务是否运行
echo [1/2] 检查后端服务状态...
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo ⚠️  后端服务未运行
    echo.
    choice /C YN /M "是否现在启动后端服务"
    if errorlevel 2 goto :skip_backend
    if errorlevel 1 (
        echo.
        echo 正在启动后端服务...
        start "WordStyle Pro Backend" cmd /k "cd /d %~dp0 && venv\Scripts\python.exe run_dev.py"
        echo ✅ 后端服务已在新窗口启动
        echo.
        echo 等待服务启动...
        timeout /t 5 /nobreak >nul
    )
) else (
    echo ✅ 后端服务正在运行
)

:skip_backend
echo.
echo [2/2] 打开测试页面...
start test_frontend.html
echo ✅ 测试页面已在浏览器中打开
echo.
echo ========================================
echo   测试说明
echo ========================================
echo.
echo 1. 首先点击"检查健康状态"确认连接
echo 2. 注册一个新账号（或登录已有账号）
echo 3. 登录后可以测试充值和转换功能
echo.
echo 📖 详细使用说明请查看：FRONTEND_TEST_GUIDE.md
echo.
echo 按任意键关闭此窗口...
pause >nul
