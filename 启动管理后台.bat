@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
cd /d "%ROOT%"
if exist "%ROOT%.venv\Scripts\python.exe" (
	set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
	"%PYTHON_EXE%" -c "import streamlit" >nul 2>&1
	if errorlevel 1 set "PYTHON_EXE="
)
if not defined PYTHON_EXE if exist "%ROOT%.venv-dev-validation\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv-dev-validation\Scripts\python.exe"
if not defined PYTHON_EXE for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE (
	echo [ERROR] Python 3 not found.
	pause
	exit /b 1
)
"%PYTHON_EXE%" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
	echo [ERROR] Streamlit is not installed.
	pause
	exit /b 1
)
echo Admin: http://localhost:8502
"%PYTHON_EXE%" -m streamlit run "%ROOT%admin_web.py" --server.port 8502 --server.headless true
pause
