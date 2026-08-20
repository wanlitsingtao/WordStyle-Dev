@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
cd /d "%ROOT%"
echo ========================================
echo WordStyle - Supabase mode
echo ========================================

if not exist "%ROOT%.env" if not exist "%ROOT%.streamlit\secrets.toml" (
    echo [ERROR] No .env or .streamlit\secrets.toml found.
    echo Configure USE_SUPABASE and DATABASE_URL first.
    pause
    exit /b 1
)

call :select_python
if errorlevel 1 exit /b 1
call :check_streamlit
if errorlevel 1 exit /b 1

echo [1/2] Starting main app: http://localhost:8501
start "WordStyle Main App" /D "%ROOT%" "%PYTHON_EXE%" -m streamlit run app.py --server.port 8501 --server.headless true
timeout /t 3 /nobreak >nul
echo [2/2] Starting admin app: http://localhost:8502
start "WordStyle Admin Panel" /D "%ROOT%" "%PYTHON_EXE%" -m streamlit run admin_web.py --server.port 8502 --server.headless true
echo Started.
pause
exit /b 0

:select_python
if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
    "%PYTHON_EXE%" --version >nul 2>&1
    if not errorlevel 1 (
        "%PYTHON_EXE%" -c "import streamlit" >nul 2>&1
        if not errorlevel 1 exit /b 0
    )
)
if not defined PYTHON_EXE if exist "%ROOT%.venv-dev-validation\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT%.venv-dev-validation\Scripts\python.exe"
)
if not defined PYTHON_EXE for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE (
    echo [ERROR] Python 3 not found.
    pause
    exit /b 1
)
exit /b 0

:check_streamlit
"%PYTHON_EXE%" -c "import streamlit" >nul 2>&1
if not errorlevel 1 exit /b 0
echo [ERROR] Streamlit is not installed in the selected Python environment.
echo Run: "%PYTHON_EXE%" -m pip install -r requirements.txt
pause
exit /b 1
