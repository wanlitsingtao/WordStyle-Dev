@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
cd /d "%ROOT%"
echo Starting WordStyle Web app...
call :select_python
if errorlevel 1 exit /b 1
call :check_streamlit
if errorlevel 1 exit /b 1
start "WordStyle Main App" /D "%ROOT%" "%PYTHON_EXE%" -m streamlit run app.py --server.port 8501 --server.headless true
timeout /t 2 /nobreak >nul
start "WordStyle Admin Panel" /D "%ROOT%" "%PYTHON_EXE%" -m streamlit run admin_web.py --server.port 8502 --server.headless true
echo Main:  http://localhost:8501
echo Admin: http://localhost:8502
pause
exit /b 0

:select_python
if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
    "%PYTHON_EXE%" -c "import streamlit" >nul 2>&1
    if not errorlevel 1 exit /b 0
)
if not defined PYTHON_EXE if exist "%ROOT%.venv-dev-validation\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv-dev-validation\Scripts\python.exe"
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
echo [ERROR] Streamlit is not installed. Run pip install -r requirements_web.txt
pause
exit /b 1
