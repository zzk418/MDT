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

echo [OK] Docker 已就绪，检查镜像...
echo.

:: 检查镜像是否已存在
docker image inspect mdt-chatchat >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] 镜像已存在，直接启动容器（跳过构建）...
    echo      如需重新构建，请运行 scripts\rebuild_docker.bat
    echo.
    docker compose -f docker\docker-compose.win.yaml --env-file .env up -d
) else (
    echo [INFO] 首次运行，开始构建镜像（约需几分钟）...
    echo.
    docker compose -f docker\docker-compose.win.yaml --env-file .env up --build -d
)

echo.
echo ============================================
echo   服务已在后台启动，关闭此窗口不影响运行。
echo   查看日志: docker compose -f docker\docker-compose.win.yaml logs -f
echo   停止服务: docker compose -f docker\docker-compose.win.yaml down
echo ============================================
pause
