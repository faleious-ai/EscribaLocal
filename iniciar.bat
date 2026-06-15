@echo off
title EscribaLocal Launcher
cls

:: Libera a porta 8000 se houver algum servidor antigo rodando nela
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1

echo =======================================================================
echo          ESCRIBA LOCAL - TRANSCRIÇÃO DE ALTA PERFORMANCE
echo =======================================================================
echo.
echo [1/4] Verificando instalacao do Python...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] O Python nao foi encontrado no sistema.
    echo Por favor, instale o Python 3.12 ou superior e marque a opcao:
    echo "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

:: Cria o ambiente virtual caso nao exista
if not exist ".venv" (
    echo [2/4] Criando ambiente virtual local venv...
    python -m venv .venv
)

if not exist ".venv\Scripts\activate.bat" (
    echo [ERRO] Nao foi possivel criar o ambiente virtual em .venv.
    echo Verifique as permissoes da pasta.
    echo.
    pause
    exit /b 1
)

echo [2/4] Ativando ambiente virtual...
call ".venv\Scripts\activate.bat"

echo [3/4] Verificando instalacao do PyTorch e suporte CUDA GPU...
python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>nul
if %errorlevel% equ 0 (
    echo Suporte a GPU CUDA ja configurado no PyTorch.
    echo [3/4] Instalando/Atualizando demais dependencias...
    python -m pip install -r requirements.txt
) else (
    echo Instalando PyTorch com suporte a GPU NVIDIA CUDA...
    echo Isso pode levar alguns minutos dependendo da sua internet.
    python -m pip install torch --index-url https://download.pytorch.org/whl/cu121
    python -m pip install -r requirements.txt
)

echo [4/4] Inicializando o servidor FastAPI...
if exist "temp_uploads\.browser_opened" del /q "temp_uploads\.browser_opened" >nul 2>&1

echo =======================================================================
echo Servidor rodando em http://127.0.0.1:8000
echo Mantenha esta janela aberta para usar o aplicativo.
echo Para fechar, feche esta janela ou aperte Ctrl+C.
echo =======================================================================
echo.

python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
if %errorlevel% neq 0 (
    echo [ERRO] Servidor encerrou com falha.
    pause
)
