#!/bin/bash
# =============================================================================
# 从备份恢复 MDT 数据卷
# =============================================================================
# 用法:
#   scripts/restore_data.sh ~/mdt-backups/mdt_data_20260920_1600.tgz
#   scripts/restore_data.sh                 # 不带参数则列出最近的备份
#
# ⚠️ 会先清空目标卷再解压（这是"恢复"的语义）。
#    建议先停掉容器，避免恢复过程中应用还在写数据:
#      docker rm -f mdt
#    恢复后重新起容器即可。
# =============================================================================
set -euo pipefail

VOLUME="${MDT_VOLUME:-mdt_data}"
BACKUP_DIR="${MDT_BACKUP_DIR:-$HOME/mdt-backups}"
FILE="${1:-}"

if [ -z "$FILE" ]; then
    echo "用法: $0 <备份文件.tgz>"
    echo
    echo "可用备份（$BACKUP_DIR）:"
    ls -1t "$BACKUP_DIR"/mdt_data_*.tgz 2>/dev/null | head -10 | sed 's|^|  |' || echo "  (无)"
    exit 1
fi

[ -f "$FILE" ] || { echo "[错误] 文件不存在: $FILE"; exit 1; }
DIR="$(dirname "$(realpath "$FILE")")"
BASE="$(basename "$FILE")"

echo "================================================================"
echo "  从备份恢复"
echo "  备份文件 : $FILE"
echo "  目标卷   : $VOLUME"
echo "================================================================"
echo
echo "⚠️  目标卷 /data 下的现有内容会被【清空】后解压。"
read -r -p "确认继续? 输入 yes: " ans
[ "$ans" = "yes" ] || { echo "已取消"; exit 1; }

echo "▶ 解压恢复中..."
docker run --rm -v "$VOLUME":/data -v "$DIR":/in alpine \
    sh -c "rm -rf /data/* /data/.[!.]* 2>/dev/null; tar xzf '/in/${BASE}' -C /data"

echo "▶ 校验"
docker run --rm -v "$VOLUME":/data alpine \
    sh -c "du -sh /data; find /data/data/knowledge_base -maxdepth 2 2>/dev/null | head -8"

echo
echo "✅ 恢复完成。重新启动容器:"
echo "   docker run -d --name mdt --restart always \\"
echo "     -p 7861:7861 -p 8501:8501 -p 4040:4040 \\"
echo "     -v $VOLUME:/root/mdt_data --env-file /code/MDT/.env \\"
echo "     ccr.ccs.tencentyun.com/kie-project/mdt:2026-09-17"
