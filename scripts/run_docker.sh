#!/bin/bash
# MDT Docker 一键部署 (Linux/macOS)
# 两段式: 先构建(带分步进度), 再启动; 构建失败会直接给原因, 不再只甩一句 "failed to execute bake"
set -uo pipefail

cd "$(dirname "$0")/../docker"

# 检测平台: Linux 用 host 网络模式, 其他(macOS)用 bridge
OS="$(uname -s)"
if [ "$OS" = "Linux" ]; then
    COMPOSE_FILE="docker-compose.yaml"
else
    COMPOSE_FILE="docker-compose.win.yaml"
fi

ENV_FILE="../.env"
LOG_DIR="../logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy_$(date +%Y%m%d_%H%M%S).log"
FORCE_BUILD=false
if [ "${1:-}" = "--build" ]; then
    FORCE_BUILD=true
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "[错误] 未找到 $ENV_FILE"
    echo "       请先执行: cp .env.example .env  并填写 NGROK_AUTHTOKEN / OLLAMA_MODELS 等配置"
    exit 1
fi

MODEL_PROVIDER="$(grep -E '^MODEL_PROVIDER=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r\"' | tr -d "'")"
MODEL_PROVIDER="${MODEL_PROVIDER:-cloud}"
CLOUD_API_KEY="$(grep -E '^CLOUD_API_KEY=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r\"' | tr -d "'")"
CLOUD_API_BASE_URL="$(grep -E '^CLOUD_API_BASE_URL=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r\"' | tr -d "'")"
CLOUD_LLM_MODEL="$(grep -E '^CLOUD_LLM_MODEL=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r\"' | tr -d "'")"
if [ "$MODEL_PROVIDER" = "ollama" ]; then
    export COMPOSE_PROFILES=ollama
    PROFILE_TEXT="ollama 本地模式，会启动 Ollama 服务"
elif [ "$MODEL_PROVIDER" = "auto" ] && { [ -z "$CLOUD_API_KEY" ] || [ -z "$CLOUD_API_BASE_URL" ] || [ -z "$CLOUD_LLM_MODEL" ]; }; then
    export COMPOSE_PROFILES=ollama
    PROFILE_TEXT="auto 本地模式，会启动 Ollama 服务"
else
    unset COMPOSE_PROFILES
    PROFILE_TEXT="cloud 默认模式，不启动/不拉 Ollama"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop ollama >/dev/null 2>&1 || true
fi

echo "================================================================"
echo "  MDT Docker 部署"
echo "  配置文件 : $COMPOSE_FILE"
echo "  构建日志 : $LOG_FILE"
echo "  模型模式 : $PROFILE_TEXT"
echo "================================================================"

echo
if [ "$FORCE_BUILD" = true ] || ! docker image inspect docker-chatchat:latest >/dev/null 2>&1; then
    echo "▶ 第 1/2 步: 构建 chatchat 镜像 (--build 可强制重建)"
    echo "  每个 Dockerfile 步骤会以 #[x/19] 实时打印, 卡在哪一步一眼可见"

    if ! docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --progress=plain build chatchat 2>&1 | tee "$LOG_FILE"; then
        echo
        echo "  [✗] 镜像构建失败, 最近报错:"
        grep -iE 'error|caused by|failed|timeout|exit code|exception' "$LOG_FILE" | tail -15 | sed 's/^/      /'
        echo
        echo "  完整日志 : $LOG_FILE"
        exit 1
    fi
    echo "  [OK] 镜像构建成功"
else
    echo "▶ 第 1/2 步: 复用已有 chatchat 镜像 (需要重建时执行: scripts/run_docker.sh --build)"
fi

echo
echo "▶ 第 2/2 步: 启动 chatchat 服务"
echo "  cloud 模式不会启动 Ollama; ollama 模式只拉 ${OLLAMA_LLM_MODEL:-smollm2:135m}"
exec docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --no-build --force-recreate chatchat
