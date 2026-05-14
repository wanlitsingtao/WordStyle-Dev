@echo off
chcp 65001 >nul
echo ========================================
echo   Word文档转换工具 - Web版
echo ========================================
echo.

cd /d E:\LingMa\WordStyle

REM 检查虚拟环境是否存在
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先运行“修复环境.bat”
    pause
    exit /b 1
)

echo [检查] 验证依赖包...
.venv\Scripts\python.exe -m pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [警告] streamlit未安装，正在安装依赖...
    .venv\Scripts\python.exe -m pip install -r requirements_web.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

echo.
echo 正在启动Web应用...
echo.
echo 主应用: http://localhost:8501
echo 管理端: http://localhost:8502
echo.
echo ========================================
echo.

REM 启动主应用（后台运行）
start "" cmd /c ".venv\Scripts\python.exe -m streamlit run app.py --server.port 8501 --server.headless=true"

REM 等待2秒，确保主应用启动
timeout /t 2 /nobreak >nul

REM 启动管理端（后台运行）
start "" cmd /c ".venv\Scripts\python.exe -m streamlit run admin_web.py --server.port 8502 --server.headless=true"

echo.
echo ✅ 两个服务已启动！
echo    - 主应用: http://localhost:8501
echo    - 管理端: http://localhost:8502
echo.
echo 提示: 关闭此窗口不会停止服务
echo       需要停止时请关闭所有命令行窗口
echo.

pause
