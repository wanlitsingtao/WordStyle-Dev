@echo off
chcp 65001 >nul
echo ========================================
echo   重新初始化数据库
echo ========================================
echo.

cd /d %~dp0

echo [1/2] 删除旧数据库...
if exist wordstyle.db (
    del wordstyle.db
    echo ✅ 已删除旧数据库
) else (
    echo ℹ️  数据库文件不存在，跳过删除
)

echo.
echo [2/2] 创建新数据库...
venv\Scripts\python.exe init_db.py

echo.
echo ========================================
echo   完成！
echo ========================================
pause
