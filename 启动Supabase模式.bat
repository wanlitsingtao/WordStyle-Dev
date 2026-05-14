@echo off
chcp 65001 >nul
echo ========================================
echo WordStyle - Supabase 模式启动脚本
echo ========================================
echo.

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
echo [INFO] 正在启动应用...
echo.

REM 启动主应用（后台运行）
echo [1/2] 启动主应用 (http://localhost:8501)...
start "WordStyle Main App" cmd /k "streamlit run app.py --server.port 8501"
timeout /t 3 /nobreak >nul

REM 启动管理后台
echo [2/2] 启动管理后台 (http://localhost:8502)...
start "WordStyle Admin Panel" cmd /k "streamlit run admin_web.py --server.port 8502"

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
