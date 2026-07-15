@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   维护模式功能测试
echo ========================================
echo.
echo [INFO] 当前工作目录: %CD%
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
echo [OK] Python环境正常: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

REM 运行测试脚本
echo [INFO] 开始运行测试...
echo.
%PYTHON_CMD% test_maintenance_mode.py

if errorlevel 1 (
    echo.
    echo [ERROR] 测试失败，请检查错误信息
    pause
    exit /b 1
)

echo.
echo ========================================
echo [OK] 所有测试通过！
echo ========================================
echo.
echo 下一步操作：
echo 1. 启动管理后台: %PYTHON_CMD% -m streamlit run admin_web.py --server.port 8502
echo 2. 访问 http://localhost:8502
echo 3. 进入「系统配置」页面
echo 4. 展开「维护模式配置」
echo 5. 勾选「启用维护模式」并保存
echo 6. 启动用户前端: %PYTHON_CMD% -m streamlit run app.py --server.port 8501
echo 7. 访问 http://localhost:8501 查看效果
echo.
pause
