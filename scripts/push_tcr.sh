#!/bin/bash
# =============================================================================
# 推送 MDT 镜像到腾讯云 TCR（个人版）
# =============================================================================
# 用法:
#   scripts/run_docker.sh              # 构建/启动（原脚本，未改动）
#   scripts/push_tcr.sh <命名空间> [标签] [本地镜像]
#
# 例:
#   scripts/push_tcr.sh mdt                     # 推 mdt:release-<日期>
#   scripts/push_tcr.sh mdt 2026-09-16          # 指定标签
#   scripts/push_tcr.sh mdt v1 mdt:dev          # 指定本地镜像
#
# 前置条件:
#   1. 腾讯云控制台已建好命名空间（TCR 个人版, 广州地域）
#   2. 已登录: docker login ccr.ccs.tencentyun.com --username=<腾讯云账号ID>
#      （密码 = 控制台"初始化密码"设的固定密码, 不是腾讯云登录密码）
# =============================================================================
set -uo pipefail

REGISTRY="ccr.ccs.tencentyun.com"
USERNAME="${TCR_USERNAME:-100045577205}"

NAMESPACE="${1:-}"
TAG="${2:-$(date +%Y-%m-%d)}"
LOCAL_IMAGE="${3:-mdt:release-20260916}"

if [ -z "$NAMESPACE" ]; then
    echo "用法: $0 <命名空间> [镜像标签] [本地镜像]"
    echo "  例: $0 mdt 2026-09-16 mdt:release-20260916"
    echo
    echo "本地可用镜像:"
    docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}' | grep -E '^mdt:' | sed 's/^/  /' || echo "  (无)"
    echo
    echo "命名空间在腾讯云控制台创建: 容器镜像服务 TCR -> 命名空间 -> 个人版实例 -> 新建"
    exit 1
fi

if ! docker image inspect "$LOCAL_IMAGE" >/dev/null 2>&1; then
    echo "[错误] 本地镜像不存在: $LOCAL_IMAGE"
    echo "       先构建: docker buildx build -f docker/Dockerfile.fast -t mdt:dev ."
    exit 1
fi

REMOTE="$REGISTRY/$NAMESPACE/mdt:$TAG"

echo "================================================================"
echo "  推送镜像到腾讯云 TCR"
echo "  本地镜像 : $LOCAL_IMAGE"
echo "  目标地址 : $REMOTE"
echo "================================================================"
echo

echo "▶ 打标签"
docker tag "$LOCAL_IMAGE" "$REMOTE" || { echo "[错误] docker tag 失败"; exit 1; }

echo "▶ 推送（首次约需上传 3GB 压缩层, 之后只传变化的层）"
if ! docker push "$REMOTE"; then
    echo
    echo "[错误] 推送失败。常见原因:"
    echo "  1. 未登录: docker login $REGISTRY --username=$USERNAME"
    echo "  2. 命名空间不存在或名字写错（个人版命名空间全局唯一）"
    echo "  3. 个人版实例只在广州地域创建"
    exit 1
fi

echo
echo "[OK] 推送完成"
echo
echo "── 部署机执行 ──────────────────────────────────────────────"
echo "  docker login $REGISTRY --username=$USERNAME"
echo "  docker pull $REMOTE"
echo
echo "  compose 里将 build: 改为:"
echo "    image: $REMOTE"
echo "  然后: docker compose up -d --no-build"
echo "────────────────────────────────────────────────────────────"
