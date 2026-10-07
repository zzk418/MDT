#!/bin/bash
# =============================================================================
# 一条命令完成「改代码 → 出新镜像 → 推到腾讯云」整个发布流程
# =============================================================================
# 用法:
#   scripts/release_image.sh              # 用当天日期做 tag
#   scripts/release_image.sh 2026-09-18   # 指定 tag
#
# 它做的事:
#   ① docker buildx build -f docker/Dockerfile.fast   ← 只重建代码层(约 12 秒)
#   ② docker save                                     ← 导出可推送的归档
#   ③ crane push                                      ← 走代理推到 TCR
#
# 之后部署机:
#   docker pull ccr.ccs.tencentyun.com/kie-project/mdt:<tag>
#   docker compose -f docker-compose.image.yaml --env-file .env up -d
#
# 说明:
#   - 之所以用 Dockerfile.fast: 依赖层(1GB, 187 个包)与源码解耦, 改代码只重建
#     3.4MB 的代码层; 用原版 Dockerfile 每次要重装依赖(15-35 分钟)。
#   - 之所以用 crane 而不是 docker push: Docker 引擎走 Docker Desktop 的代理,
#     大层会上传超时; crane 从宿主直接走 Clash 代理(实测 2026-09-17 可用)。
# =============================================================================
set -euo pipefail

TAG="${1:-$(date +%Y-%m-%d)}"
REGISTRY="ccr.ccs.tencentyun.com"
NAMESPACE="${MDT_TCR_NAMESPACE:-kie-project}"
LOCAL_IMAGE="mdt:release"
REMOTE="${REGISTRY}/${NAMESPACE}/mdt:${TAG}"
TAR="/tmp/mdt-release-${TAG}.tar"

CRANE="${CRANE:-$(command -v crane || echo /home/kie/bin/crane)}"
if [ ! -x "$CRANE" ]; then
    echo "[错误] 找不到 crane: $CRANE"
    echo "       它用于绕开 Docker 引擎代理推送镜像(见 WSL_NETWORK_FIX_HANDOFF.md 第十节)"
    exit 1
fi

cd "$(dirname "$0")/.."
echo "================================================================"
echo "  MDT 镜像发布"
echo "  本地镜像 : $LOCAL_IMAGE"
echo "  目标     : $REMOTE"
echo "================================================================"
echo

echo "▶ 1/3 构建（只重建代码层）"
start=$(date +%s)
docker buildx build -f docker/Dockerfile.fast -t "$LOCAL_IMAGE" . >/tmp/mdt-release-build.log 2>&1 \
    || { echo "[错误] 构建失败，日志: /tmp/mdt-release-build.log"; tail -20 /tmp/mdt-release-build.log; exit 1; }
echo "   OK，耗时 $(( $(date +%s)-start )) 秒"

echo "▶ 2/3 导出归档"
docker save "$LOCAL_IMAGE" -o "$TAR"
echo "   OK，$(du -h "$TAR" | cut -f1)"

echo "▶ 3/3 推送（走代理，已存在的层会自动跳过）"
# 关键: 只把 localhost 放进 NO_PROXY, 让 ccr 走 Clash 代理(mirrored 模式下直连不通)
export NO_PROXY="localhost,127.0.0.1"
export no_proxy="$NO_PROXY"
"$CRANE" push "$TAR" "$REMOTE"

echo
echo "✅ 发布完成"
echo
echo "── 部署机执行 ──────────────────────────────────────────────"
echo "  docker pull $REMOTE"
echo "  # compose 里 image: 改为 $REMOTE 后:"
echo "  docker compose -f docker-compose.image.yaml --env-file .env up -d"
echo "────────────────────────────────────────────────────────────"
