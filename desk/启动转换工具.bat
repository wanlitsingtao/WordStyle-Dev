@echo off
chcp 65001 >nul
echo ========================================
echo   Word文档格式转换工具
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.7+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/2] 检查依赖包...
pip show python-docx >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖包...
    pip install -r requirements.txt
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
python doc_converter_gui.py

if errorlevel 1 (
    echo.
    echo [错误] 程序运行出错
    pause
)
