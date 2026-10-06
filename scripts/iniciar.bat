@echo off
setlocal
cd /d "%~dp0.."

if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" goto iniciar_python_local

py -3.14 -c "import sys" >nul 2>&1
if not errorlevel 1 goto iniciar

where winget >nul 2>&1
if errorlevel 1 (
    echo O Python 3.14 nao foi encontrado e o winget nao esta disponivel.
    echo Instale o Python 3.14 ou atualize o Instalador de Aplicativos do Windows.
    pause
    exit /b 1
)

echo Preparando o Python 3.14 automaticamente...
winget install --id Python.Python.3.14 --exact --scope user --silent --accept-source-agreements --accept-package-agreements
if errorlevel 1 (
    echo Nao foi possivel instalar o Python automaticamente.
    pause
    exit /b 1
)

if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" goto iniciar_python_local

py -3.14 -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo O Python foi instalado, mas o iniciador py ainda nao esta disponivel.
    echo Feche e abra novamente este inicializador para concluir a preparacao.
    pause
    exit /b 1
)

:iniciar
py -3.14 scripts\bootstrap.py
if errorlevel 1 pause
exit /b

:iniciar_python_local
"%LOCALAPPDATA%\Programs\Python\Python314\python.exe" scripts\bootstrap.py
if errorlevel 1 pause
