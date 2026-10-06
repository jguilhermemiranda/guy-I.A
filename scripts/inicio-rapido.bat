@echo off
setlocal
cd /d "%~dp0.."

set "VENV_PYTHON=.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    py -3.14 -m venv .venv
    if errorlevel 1 (
        python -m venv .venv
    )
    if errorlevel 1 (
        echo Nao foi possivel criar o ambiente Python. Instale o Python 3.14.
        pause
        exit /b 1
    )
)

"%VENV_PYTHON%" -c "import sys; raise SystemExit(sys.version_info < (3, 14))" >nul 2>&1
if errorlevel 1 (
    echo O ambiente precisa de Python 3.14 ou mais recente.
    echo Instale uma versao compativel e execute este arquivo novamente.
    pause
    exit /b 1
)

"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 (
    echo Falha ao atualizar o pip.
    pause
    exit /b 1
)

if exist "requirements.txt" (
    "%VENV_PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Falha ao instalar as dependencias.
        pause
        exit /b 1
    )
)

call "%~dp0pre-comit.bat"
if errorlevel 1 (
    echo Nao foi possivel preparar os modelos do Ollama.
    pause
    exit /b 1
)

"%VENV_PYTHON%" main.py
if errorlevel 1 (
    echo O aplicativo foi encerrado com erro.
    pause
    exit /b 1
)
