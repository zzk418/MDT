@echo off
chcp 65001 >nul
title MDT Docker 重新构建

cd /d "%~dp0\.."

echo ============================================
echo   MDT Docker 强制重新构建镜像
echo   项目目录: %CD%
echo ============================================
echo.

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop！
    pause
    exit /b 1
)

echo [INFO] 开始重新构建镜像并启动（约需几分钟）...
echo.

docker compose -f docker\docker-compose.win.yaml --env-file .env up --build -d

echo.
echo ============================================
echo   构建完成，服务已在后台启动。
echo ============================================
pause
