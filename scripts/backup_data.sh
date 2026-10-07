#!/bin/bash
# =============================================================================
# 备份 MDT 数据卷 —— 知识库(源文件+向量库) + 配置 + 对话记录 一次打包
# =============================================================================
# 用法:
#   scripts/backup_data.sh                      # 备份到 ~/mdt-backups/
#   scripts/backup_data.sh /path/to/dir         # 指定输出目录
#   KEEP=20 scripts/backup_data.sh              # 保留最近 20 份(默认 10)
#   MDT_VOLUME=mdt_data scripts/backup_data.sh  # 指定卷名(默认 mdt_data)
#
# 为什么用"整卷打包"而不是只备份源文件:
#   知识库目录里同时含 content/(源文件) 和 vector_store/(向量索引)。
#   整卷备份 = 恢复后直接可用, 不需要重新向量化(也就不依赖 embedding 模型)。
#
# 恢复用 scripts/restore_data.sh
# =============================================================================
set -euo pipefail

VOLUME="${MDT_VOLUME:-mdt_data}"
OUTDIR="${1:-$HOME/mdt-backups}"
KEEP="${KEEP:-10}"
STAMP="$(date +%Y%m%d_%H%M%S)"
NAME="mdt_data_${STAMP}.tgz"

mkdir -p "$OUTDIR"
OUTDIR="$(realpath "$OUTDIR")"

if ! docker volume inspect "$VOLUME" >/dev/null 2>&1; then
    echo "[错误] 卷不存在: $VOLUME"
    echo "       现有卷:"; docker volume ls --format '  {{.Name}}' | grep -i mdt || echo "  (无)"
    exit 1
fi

echo "▶ 备份卷 $VOLUME → $OUTDIR/$NAME"
# :ro 只读挂载, 保证备份过程绝不改动原数据
docker run --rm -v "$VOLUME":/data:ro -v "$OUTDIR":/out alpine \
    tar czf "/out/${NAME}" -C /data .

SIZE="$(du -h "$OUTDIR/$NAME" | cut -f1)"
echo "   ✅ 完成，大小 $SIZE"

echo "▶ 清理旧备份（保留最近 $KEEP 份）"
mapfile -t OLD < <(ls -1t "$OUTDIR"/mdt_data_*.tgz 2>/dev/null | tail -n +$((KEEP + 1)))
if [ "${#OLD[@]}" -gt 0 ]; then
    for f in "${OLD[@]}"; do
        rm -f "$f" && echo "   已删除旧备份: $(basename "$f")"
    done
else
    echo "   无需清理"
fi

echo
echo "当前备份列表:"
ls -1t "$OUTDIR"/mdt_data_*.tgz 2>/dev/null | head -5 | sed 's|^|   |'
