@echo off
cd /d "%~dp0\..\docker"
docker compose -f docker-compose.win.yaml --env-file ../.env up --build
