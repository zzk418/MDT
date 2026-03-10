@echo off
chcp 65001 >nul
title MDT Docker 启动

:: 切换到项目根目录（bat文件所在目录的上一级）
cd /d "%~dp0\.."

echo ============================================
echo   MDT Docker 服务启动中...
echo   项目目录: %CD%
echo ============================================
echo.

:: 检查 .env 文件是否存在
if not exist ".env" (
    echo [错误] 未找到 .env 文件！
    echo 请将 .env.example 复制为 .env 并填写配置。
    echo.
    pause
    exit /b 1
)

:: 检查 docker 是否可用
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop！
    echo.
    pause
    exit /b 1
)

echo [OK] Docker 已就绪，开始构建并启动服务...
echo.

docker compose -f docker\docker-compose.win.yaml --env-file .env up --build

echo.
echo ============================================
echo   服务已退出。
echo ============================================
pause
