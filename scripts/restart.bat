@echo off
chcp 65001 >nul
title MDT 快速重启

cd /d "%~dp0\.."

echo ============================================
echo   MDT 快速重启（代码热更新，无需重建镜像）
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

echo [OK] 重启 chatchat 服务...
docker compose -f docker\docker-compose.win.yaml --env-file .env restart chatchat

echo.
echo ============================================
echo   重启完成，等待服务启动约 15-20 秒后访问：
echo   本地 WebUI: http://localhost:8501
echo ============================================
pause
