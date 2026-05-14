@echo off
chcp 65001 >nul
echo ========================================
echo   WordStyle Pro - 微信扫码登录测试
echo ========================================
echo.

cd /d %~dp0

echo [1/3] 检查数据库...
if not exist wordstyle.db (
    echo ⚠️  数据库不存在，正在初始化...
    call "重新初始化数据库.bat"
) else (
    echo ✅ 数据库已存在
)

echo.
echo [2/3] 检查后端服务...
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
echo [3/3] 打开测试页面...
start wechat_login.html
echo ✅ 微信扫码登录页面已在浏览器中打开
echo.
echo ========================================
echo   使用说明
echo ========================================
echo.
echo 1. 点击"生成微信登录二维码"按钮
echo 2. 系统会模拟扫码并自动登录
echo 3. 首次登录将赠送免费额度（默认10000段）
echo 4. 管理员可访问 admin_config.html 修改配置
echo.
echo 📖 详细说明请查看：微信扫码登录系统说明.md
echo.
echo 按任意键关闭此窗口...
pause >nul
