@echo off
chcp 65001 >nul
echo ========================================
echo WordStyle - Supabase 模式启动脚本
echo ========================================
echo.

REM 检查Python环境（优先使用 py 启动器）
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :python_found
)

python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
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

REM 检查 .env 文件是否存在
if not exist ".env" (
    echo [ERROR] 未找到 .env 文件！
    echo.
    echo 请先创建 .env 文件并配置 Supabase 连接信息：
    echo   1. 复制 .env.example 为 .env
    echo   2. 填写 DATABASE_URL
    echo   3. 设置 USE_SUPABASE=true
    echo.
    echo 参考文档: SUPABASE_SETUP_GUIDE.md
    echo.
    pause
    exit /b 1
)

echo [INFO] 检测到 .env 文件
echo [INFO] Python: %PYTHON_CMD%
%PYTHON_CMD% --version
echo [INFO] 正在启动应用...
echo.

REM 启动主应用（后台运行）
echo [1/2] 启动主应用 (http://localhost:8501)...
start "WordStyle Main App" cmd /k "%PYTHON_CMD% -m streamlit run app.py --server.port 8501"
timeout /t 3 /nobreak >nul

REM 启动管理后台
echo [2/2] 启动管理后台 (http://localhost:8502)...
start "WordStyle Admin Panel" cmd /k "%PYTHON_CMD% -m streamlit run admin_web.py --server.port 8502"

echo.
echo ========================================
echo 应用启动成功！
echo ========================================
echo.
echo 主应用:     http://localhost:8501
echo 管理后台:   http://localhost:8502
echo.
echo 提示: 
echo   - 两个窗口会保持打开状态
echo   - 关闭窗口即可停止对应服务
echo   - 查看日志请切换到对应窗口
echo.
echo ========================================
pause
