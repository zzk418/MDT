@echo off
chcp 65001 >nul
title MDT Docker 部署
setlocal

:: 切到项目根目录 (bat 所在目录的上一级)
cd /d "%~dp0\.."

set "COMPOSE_FILE=docker\docker-compose.win.yaml"
set "LOG_DIR=logs"
set "LOG_FILE=%LOG_DIR%\deploy.log"
set "FORCE_BUILD=0"
if "%~1"=="--build" set "FORCE_BUILD=1"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ============================================================
echo   MDT Docker 部署
echo   配置文件: %COMPOSE_FILE%
echo   构建日志: %LOG_FILE%
echo ============================================================

:: 检查 .env
if not exist ".env" (
    echo [错误] 未找到 .env 文件!
    echo        请先: copy .env.example .env  再填写 NGROK_AUTHTOKEN / OLLAMA_MODELS 等配置。
    echo.
    pause
    exit /b 1
)

:: 检查 docker
docker info >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未运行, 请先启动 Docker Desktop!
    echo.
    pause
    exit /b 1
)

set "MODEL_PROVIDER=cloud"
for /f "tokens=1,* delims==" %%A in ('findstr /b /c:"MODEL_PROVIDER=" .env 2^>nul') do set "MODEL_PROVIDER=%%B"
set "CLOUD_API_KEY="
set "CLOUD_API_BASE_URL="
set "CLOUD_LLM_MODEL="
for /f "tokens=1,* delims==" %%A in ('findstr /b /c:"CLOUD_API_KEY=" /c:"CLOUD_API_BASE_URL=" /c:"CLOUD_LLM_MODEL=" .env 2^>nul') do set "%%A=%%B"
set "COMPOSE_PROFILES="
set "PROFILE_TEXT=cloud 默认模式，不启动/不拉 Ollama"
if /i "%MODEL_PROVIDER%"=="ollama" (
    set "COMPOSE_PROFILES=ollama"
    set "PROFILE_TEXT=ollama 本地模式，会启动 Ollama 服务"
) else if /i "%MODEL_PROVIDER%"=="auto" if "%CLOUD_API_KEY%"=="" (
    set "COMPOSE_PROFILES=ollama"
    set "PROFILE_TEXT=auto 本地模式，会启动 Ollama 服务"
) else if /i "%MODEL_PROVIDER%"=="auto" if "%CLOUD_API_BASE_URL%"=="" (
    set "COMPOSE_PROFILES=ollama"
    set "PROFILE_TEXT=auto 本地模式，会启动 Ollama 服务"
) else if /i "%MODEL_PROVIDER%"=="auto" if "%CLOUD_LLM_MODEL%"=="" (
    set "COMPOSE_PROFILES=ollama"
    set "PROFILE_TEXT=auto 本地模式，会启动 Ollama 服务"
)
if not defined COMPOSE_PROFILES docker compose -f "%COMPOSE_FILE%" --env-file .env stop ollama >nul 2>&1

echo.
echo   模型模式: %PROFILE_TEXT%

docker image inspect docker-chatchat:latest >nul 2>&1
if errorlevel 1 set "FORCE_BUILD=1"

if "%FORCE_BUILD%"=="1" (
    echo ▶ 第 1/2 步: 构建 chatchat 镜像 ^(--build 可强制重建^)
    docker compose --progress=plain -f "%COMPOSE_FILE%" --env-file .env build chatchat > "%LOG_FILE%" 2>&1
    if errorlevel 1 (
        echo.
        echo   [构建失败] 最近报错:
        powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG_FILE%' -Tail 20" 2>nul
        echo.
        echo   完整日志见: %LOG_FILE%
        echo.
        pause
        exit /b 1
    )
    echo   [OK] 镜像构建成功
) else (
    echo ▶ 第 1/2 步: 复用已有 chatchat 镜像 ^(需要重建时执行: scripts\run_docker.bat --build^)
)

echo.
echo ▶ 第 2/2 步: 启动 chatchat 服务
echo.
docker compose -f "%COMPOSE_FILE%" --env-file .env up -d --no-build --force-recreate chatchat
