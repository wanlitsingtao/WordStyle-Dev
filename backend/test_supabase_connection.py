@echo off
chcp 65001 >nul
REM ============================================
REM WordStyle Supabase数据库连接测试脚本
REM 功能：验证数据库连接和表结构
REM ============================================

echo.
echo ========================================
echo   Supabase数据库连接测试
echo ========================================
echo.

REM 检查.env.production文件
if not exist ".env.production" (
    echo [错误] 未找到 .env.production 文件
    echo.
    echo 请先执行：
    echo   copy .env.production.template .env.production
    echo   然后编辑 .env.production 填写实际值
    echo.
    pause
    exit /b 1
)

echo [1/3] 加载环境变量...
echo   文件: .env.production
echo.

echo [2/3] 测试数据库连接...
python init_supabase.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   ✓ 数据库连接测试成功！
    echo ========================================
    echo.
    echo 下一步：
    echo   1. 提交代码到GitHub
    echo   2. 在Render创建Web Service
    echo   3. 配置环境变量
    echo.
) else (
    echo.
    echo ========================================
    echo   ✗ 数据库连接测试失败
    echo ========================================
    echo.
    echo 请检查：
    echo   1. DATABASE_URL 格式是否正确
    echo   2. 密码是否包含特殊字符（需要URL编码）
    echo   3. Supabase项目是否已创建
    echo   4. SQL脚本是否已执行
    echo.
    echo 参考文档：
    echo   DEPLOYMENT_UPGRADE_PLAN.md 第一步.1.2
    echo.
)

pause
