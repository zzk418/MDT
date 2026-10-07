@echo off
chcp 65001 >nul
title MDT 启动

cd /d "%~dp0\.."

echo ============================================
echo   MDT 启动（代码热更新，无需重建镜像）
echo ============================================
echo.
echo   适用场景：修改了 Python 代码、startup.sh、model_settings.yaml
echo   首次启动 / 修改了 Dockerfile 或 requirements 时，请用 run_docker.bat
echo.

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop！
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
if /i "%MODEL_PROVIDER%"=="ollama" set "COMPOSE_PROFILES=ollama"
if /i "%MODEL_PROVIDER%"=="auto" if "%CLOUD_API_KEY%"=="" set "COMPOSE_PROFILES=ollama"
if /i "%MODEL_PROVIDER%"=="auto" if "%CLOUD_API_BASE_URL%"=="" set "COMPOSE_PROFILES=ollama"
if /i "%MODEL_PROVIDER%"=="auto" if "%CLOUD_LLM_MODEL%"=="" set "COMPOSE_PROFILES=ollama"
if not defined COMPOSE_PROFILES docker compose -f docker\docker-compose.win.yaml --env-file .env stop ollama >nul 2>&1

echo [OK] 启动 chatchat 服务...
rem --force-recreate: 单文件挂载(代码/配置/startup.sh)必须重建容器才能拿到最新文件，
rem 普通 up/restart 在宿主机文件被替换(git checkout、编辑器另存为)后会挂载失败。
docker compose -f docker\docker-compose.win.yaml --env-file .env up -d --no-build --force-recreate chatchat

echo.
echo ============================================
echo   启动完成，等待服务启动约 15-20 秒后访问：
echo   本地 WebUI: http://localhost:8501
echo ============================================
pause
