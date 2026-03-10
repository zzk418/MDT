#!/bin/bash
cd "$(dirname "$0")/../docker"

# 检测平台，Linux 用 host 网络模式，其他用 bridge
OS="$(uname -s)"
if [ "$OS" = "Linux" ]; then
    docker compose -f docker-compose.yaml --env-file ../.env up --build
else
    docker compose -f docker-compose.win.yaml --env-file ../.env up --build
fi
