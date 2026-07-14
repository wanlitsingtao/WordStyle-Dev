@echo off
chcp 65001 >nul
echo ========================================
echo   Word文档格式转换工具
echo ========================================
echo.

REM 优先使用 py 启动器（Windows Python Launcher），避免 App Execution Alias 干扰
REM py 能正确找到真正安装的 Python，而非 Microsoft Store 重定向器

REM 检查Python是否安装（先试 py，再试 python）
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

echo [错误] 未检测到Python，请先安装Python 3.7+
echo 下载地址: https://www.python.org/downloads/
echo.
echo 注意：安装时务必勾选 "Add Python to PATH" 选项
echo 如果已安装但仍报此错误，请在 Windows 设置中：
echo   应用 ^> 应用执行别名 ^> 关闭 python.exe 和 python3.exe 的别名
pause
exit /b 1

:python_found
echo [OK] 检测到Python: %PYTHON_CMD%
%PYTHON_CMD% --version

echo.
echo [1/2] 检查依赖包...
%PIP_CMD% show python-docx >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖包 python-docx 和 Pillow...
    %PIP_CMD% install python-docx Pillow
    if errorlevel 1 (
        echo [错误] 依赖包安装失败
        pause
        exit /b 1
    )
) else (
    echo 依赖包已安装
)

echo.
echo [2/2] 启动程序...
echo.
%PYTHON_CMD% doc_converter_gui.py

if errorlevel 1 (
    echo.
    echo [错误] 程序运行出错
    pause
)
