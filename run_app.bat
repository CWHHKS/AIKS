@echo off
echo ===================================================
echo   AIKA Vendor Research Tool - Startup Script
echo ===================================================
echo.

if exist .venv goto :activate
echo [INFO] Python virtual environment (.venv) not found. Creating one...
python -m venv .venv
if errorlevel 1 goto :venv_error
echo [INFO] Virtual environment created successfully.

:activate
echo [INFO] Activating virtual environment...
call .venv\Scripts\activate

echo [INFO] Installing/Checking dependencies...
pip install -r requirements.txt
if errorlevel 1 goto :pip_error

echo [INFO] Starting Streamlit app...
streamlit run app.py
goto :end

:venv_error
echo [ERROR] Failed to create virtual environment. Please check if Python is installed and added to PATH.
pause
exit /b 1

:pip_error
echo [ERROR] Failed to install requirements.
pause
exit /b 1

:end
pause
