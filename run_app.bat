@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install Python 3.10+ and add it to PATH.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 exit /b 1
)

echo Installing/updating dependencies...
.\.venv\Scripts\python.exe -m pip install --upgrade pip >nul
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env from .env.example.
  echo Add GEMINI_API_KEY in .env, or set MOCK_AI=true for demo mode.
)

echo Starting RentRakshak...
.\.venv\Scripts\python.exe -m streamlit run app.py
