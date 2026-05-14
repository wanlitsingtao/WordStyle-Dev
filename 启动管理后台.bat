@echo off
chcp 65001 >nul
echo ========================================
echo   WordStyle Pro - Web管理后台启动器
echo ========================================
echo.

REM 检查虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先运行: python -m venv .venv
    pause
    exit /b 1
)

echo [信息] 正在启动Web管理后台...
echo [信息] 访问地址: http://localhost:8502
echo.

REM 启动Streamlit
.venv\Scripts\python.exe -m streamlit run admin_web.py --server.port=8502 --server.headless=true

pause
