#!/bin/bash

# 设置错误处理
set -e

echo "=== 启动 MDT 服务 ==="

# 加载环境变量
if [ -f "/root/MDT/.env" ]; then
    echo "加载环境变量..."
    source /root/MDT/.env
fi

# 兼容 Windows CRLF：去除环境变量值尾部可能残留的 \r
# （.env 在 Windows 上编辑后行尾可能是 \r\n，导致变量值含 \r）
CLOUD_API_KEY="${CLOUD_API_KEY//$'\r'/}"
CLOUD_API_BASE_URL="${CLOUD_API_BASE_URL//$'\r'/}"
CLOUD_LLM_MODEL="${CLOUD_LLM_MODEL//$'\r'/}"
CLOUD_LLM_MODELS="${CLOUD_LLM_MODELS//$'\r'/}"
DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY//$'\r'/}"
DEEPSEEK_API_BASE_URL="${DEEPSEEK_API_BASE_URL//$'\r'/}"
DEEPSEEK_LLM_MODELS="${DEEPSEEK_LLM_MODELS//$'\r'/}"
MTD_DEFAULT_LLM_MODEL="${MTD_DEFAULT_LLM_MODEL//$'\r'/}"
CLOUD_EMBED_MODEL="${CLOUD_EMBED_MODEL//$'\r'/}"
MODEL_PROVIDER="${MODEL_PROVIDER//$'\r'/}"
OLLAMA_MODELS="${OLLAMA_MODELS//$'\r'/}"
OLLAMA_LLM_MODEL="${OLLAMA_LLM_MODEL//$'\r'/}"
OLLAMA_EMBED_MODEL="${OLLAMA_EMBED_MODEL//$'\r'/}"
OLLAMA_AUTO_PULL="${OLLAMA_AUTO_PULL//$'\r'/}"
KB_REBUILD_ON_START="${KB_REBUILD_ON_START//$'\r'/}"
MDT_REGEN_MODEL_SETTINGS="${MDT_REGEN_MODEL_SETTINGS//$'\r'/}"
NGROK_AUTHTOKEN="${NGROK_AUTHTOKEN//$'\r'/}"
ENABLE_NGROK="${ENABLE_NGROK//$'\r'/}"

MODEL_PROVIDER="${MODEL_PROVIDER:-cloud}"
OLLAMA_LLM_MODEL="${OLLAMA_LLM_MODEL:-smollm2:135m}"
OLLAMA_EMBED_MODEL="${OLLAMA_EMBED_MODEL:-}"
OLLAMA_AUTO_PULL="${OLLAMA_AUTO_PULL:-true}"
KB_REBUILD_ON_START="${KB_REBUILD_ON_START:-false}"
MDT_REGEN_MODEL_SETTINGS="${MDT_REGEN_MODEL_SETTINGS:-false}"

# ngrok 内网穿透开关: 设为 false 可完全跳过。
# 隔离网络/无外网环境必须设为 false —— 否则 ngrok 连不上时, 下面第 32x 行的
# `curl localhost:4040` 会返回退出码 7, 在 `set -e` 下直接终止整个启动脚本,
# 容器以 exit 7 死亡(连 7861/8501 一起挂)。没有 token 时也自动跳过。
ENABLE_NGROK="${ENABLE_NGROK:-true}"
if [ -z "$NGROK_AUTHTOKEN" ]; then
    ENABLE_NGROK=false
fi

CLOUD_READY=false
if [ -n "$CLOUD_API_KEY" ] && [ -n "$CLOUD_API_BASE_URL" ] && [ -n "$CLOUD_LLM_MODEL" ]; then
    CLOUD_READY=true
fi

case "$MODEL_PROVIDER" in
    cloud|ollama|auto) ;;
    *)
        echo "未知 MODEL_PROVIDER=$MODEL_PROVIDER，回退为 auto"
        MODEL_PROVIDER="auto"
        ;;
esac

ACTIVE_PROVIDER="$MODEL_PROVIDER"
if [ "$ACTIVE_PROVIDER" = "auto" ]; then
    if [ "$CLOUD_READY" = true ]; then
        ACTIVE_PROVIDER="cloud"
    else
        ACTIVE_PROVIDER="ollama"
    fi
elif [ "$ACTIVE_PROVIDER" = "cloud" ] && [ "$CLOUD_READY" != true ]; then
    echo "错误: MODEL_PROVIDER=cloud 但云API配置不完整"
    echo "请填写 CLOUD_API_KEY、CLOUD_API_BASE_URL、CLOUD_LLM_MODEL"
    exit 1
fi

echo "模型提供方: $ACTIVE_PROVIDER"

# 配置ngrok认证令牌
if [ -n "$NGROK_AUTHTOKEN" ]; then
    echo "配置ngrok认证令牌..."
    ngrok config add-authtoken $NGROK_AUTHTOKEN
fi

# 支持跨平台：Linux host 模式用 localhost，Windows bridge 模式用服务名
OLLAMA_HOST="${OLLAMA_HOST:-localhost}"

# 通过 /api/tags 接口查询模型是否已在 ollama 中存在
model_exists() {
    local model="$1"
    # 取 name 字段（格式为 "model:tag"），精确匹配
    curl -s "http://${OLLAMA_HOST}:11434/api/tags" \
        | grep -o '"name":"[^"]*"' \
        | grep -q "\"name\":\"${model}\""
}

REQUIRED_OLLAMA_MODELS=""
if [ "$ACTIVE_PROVIDER" = "ollama" ]; then
    # 本地模式默认只拉最小 LLM，适合启动/接口测试。
    # 需要本地知识库向量化时，再通过 OLLAMA_MODELS 追加 embedding 模型。
    REQUIRED_OLLAMA_MODELS="$OLLAMA_LLM_MODEL"
    if [ -n "$OLLAMA_EMBED_MODEL" ]; then
        REQUIRED_OLLAMA_MODELS="$REQUIRED_OLLAMA_MODELS,$OLLAMA_EMBED_MODEL"
    fi
fi

# 兼容旧配置：仅在本地模式下接受 OLLAMA_MODELS，云模式永远不拉 Ollama 模型。
if [ "$ACTIVE_PROVIDER" = "ollama" ] && [ -n "$OLLAMA_MODELS" ]; then
    REQUIRED_OLLAMA_MODELS="$OLLAMA_MODELS"
fi

ALL_MODELS_READY=true

if [ -n "$REQUIRED_OLLAMA_MODELS" ]; then
    echo "需要的Ollama模型: $REQUIRED_OLLAMA_MODELS"

    OLLAMA_READY=false
    echo "等待Ollama服务启动..."
    for i in {1..30}; do
        if curl -s http://${OLLAMA_HOST}:11434/api/tags > /dev/null 2>&1; then
            echo "Ollama服务已启动"
            OLLAMA_READY=true
            break
        fi
        echo "等待Ollama服务启动... ($i/30)"
        sleep 2
    done

    if [ "$OLLAMA_READY" = false ]; then
        echo "警告: Ollama服务在60秒内未启动"
        ALL_MODELS_READY=false
    fi

    IFS=',' read -ra MODELS <<< "$REQUIRED_OLLAMA_MODELS"

    if [ "$OLLAMA_READY" = true ]; then
        for model in "${MODELS[@]}"; do
            model="$(echo "$model" | tr -d '[:space:]')"
            [ -z "$model" ] && continue

            # 先查 /api/tags 确认是否已存在，避免重复拉取
            if model_exists "$model"; then
                echo "模型 $model 已存在，跳过拉取"
                continue
            fi

            if [ "$OLLAMA_AUTO_PULL" != "true" ]; then
                echo "模型 $model 不存在，且 OLLAMA_AUTO_PULL=$OLLAMA_AUTO_PULL，跳过自动拉取"
                ALL_MODELS_READY=false
                continue
            fi

            echo "================================================"
            echo "开始拉取模型: $model"
            echo "（大模型文件较大，请耐心等待，实时进度如下）"
            echo "================================================"

            MAX_RETRIES=3
            RETRY_COUNT=0
            SUCCESS=false

            while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
                echo ">>> 尝试 $((RETRY_COUNT+1))/$MAX_RETRIES ..."

                # 流式拉取，实时输出进度到终端
                curl -s -X POST "http://${OLLAMA_HOST}:11434/api/pull" \
                    -H "Content-Type: application/json" \
                    -d "{\"name\": \"$model\", \"stream\": true}" \
                    --no-buffer \
                    --max-time 3600

                # 拉取结束后，查 /api/tags 真实验证
                echo ""
                if model_exists "$model"; then
                    echo "✅ 模型 $model 拉取并验证成功（已在 /api/tags 中确认）"
                    SUCCESS=true
                else
                    echo "❌ 拉取结束但 /api/tags 中未找到 $model（可能tag不存在或下载不完整）"
                    RETRY_COUNT=$((RETRY_COUNT+1))
                    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                        echo "等待15秒后重试..."
                        sleep 15
                    fi
                fi
            done

            if [ "$SUCCESS" = false ]; then
                echo "================================================"
                echo "❌ 错误: 模型 $model 拉取失败，已重试 $MAX_RETRIES 次"
                echo "    请检查:"
                echo "    1. 模型名称是否正确（当前: $model）"
                echo "    2. 宿主机代理是否开启（需监听7890端口并允许局域网连接）"
                echo "    3. 网络连接是否正常"
                echo "    修复后重启容器: docker compose restart chatchat"
                echo "================================================"
                ALL_MODELS_READY=false
            fi
        done
        echo "模型拉取阶段完成"
    fi
else
    echo "无需Ollama模型，跳过本地模型检查"
fi

# 模型未全部就绪时，尝试切换到云API冗余
if [ "$ALL_MODELS_READY" = false ]; then
    echo ""
    echo "================================================"
    echo "⚠️  Ollama模型未就绪，尝试切换到云API冗余方案..."
    echo "================================================"

    if [ "$CLOUD_READY" = true ]; then
        echo "✅ 检测到云API配置，将以云API为主模型启动..."
        ACTIVE_PROVIDER="cloud"
        ALL_MODELS_READY=true
    else
        echo "❌ 未配置云API（CLOUD_API_KEY/CLOUD_API_BASE_URL/CLOUD_LLM_MODEL），无法冗余切换"
        echo ""
        echo "================================================"
        echo "🚫 模型未全部就绪，服务启动已中止"
        echo "   解决方案："
        echo "   方案1: 修复网络后重启: docker compose restart chatchat"
        echo "   方案2: 在 .env 中配置云API后重启:"
        echo "          CLOUD_API_KEY=your_key"
        echo "          CLOUD_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1"
        echo "          CLOUD_LLM_MODEL=qwen-plus"
        echo "================================================"
        tail -f /dev/null
    fi
fi

# 配置目录路径
cd /root/MDT/libs/chatchat-server/chatchat

# 生成 model_settings.yaml（先从源文件复制，再按需注入云API和修正地址）
# 这里只写到临时文件；启动末尾再按「不覆盖已有文件」的策略落地，见下方 install/merge 段
echo "生成模型配置..."
MODEL_SETTINGS_TARGET="/root/mdt_data/model_settings.yaml"
MODEL_SETTINGS_FILE="/tmp/model_settings.generated.yaml"
if [ -f "/root/MDT/model_settings.yaml" ]; then
    cp -f /root/MDT/model_settings.yaml "$MODEL_SETTINGS_FILE"
    # 修正 ollama 服务地址（bridge 网络用服务名，host 网络用 127.0.0.1）
    sed -i "s|http://127.0.0.1:11434|http://${OLLAMA_HOST}:11434|g" "$MODEL_SETTINGS_FILE"
    sed -i "s/^DEFAULT_LLM_MODEL:.*/DEFAULT_LLM_MODEL: ${OLLAMA_LLM_MODEL}/" "$MODEL_SETTINGS_FILE"
    if [ -n "$OLLAMA_EMBED_MODEL" ]; then
        sed -i "s/^DEFAULT_EMBEDDING_MODEL:.*/DEFAULT_EMBEDDING_MODEL: ${OLLAMA_EMBED_MODEL}/" "$MODEL_SETTINGS_FILE"
    fi
    sed -i "s/qwen3:1.7b/${OLLAMA_LLM_MODEL}/g" "$MODEL_SETTINGS_FILE"
    echo "基础模型配置已复制，ollama地址: http://${OLLAMA_HOST}:11434"
fi

# 注入云API平台配置。只有 cloud 模式才切换默认 LLM，避免 ollama 模式被云配置抢占。
if [ "$ACTIVE_PROVIDER" = "cloud" ] && [ "$CLOUD_READY" = true ]; then
    echo "注入云API平台配置: ${CLOUD_API_BASE_URL} 模型: ${CLOUD_LLM_MODEL}"
    if [ -z "$CLOUD_EMBED_MODEL" ]; then
        echo "警告: CLOUD_EMBED_MODEL 为空，云端聊天可用，但知识库向量化没有云端 embedding"
    fi

    # 生成 llm_models 列表。支持一次配置多个云模型(逗号分隔), 这样 WebUI 的
    # 「高级配置」对话框里就能自由切换:
    #   CLOUD_LLM_MODELS=gpt-5.5,gpt-5.2,gpt-4o
    # 未设置 CLOUD_LLM_MODELS 时退回单个 CLOUD_LLM_MODEL。
    # (注: auto_detect_model 只支持 xinference, openai 兼容平台不会自动拉列表,
    #  所以这里显式列出。)
    CLOUD_MODELS_CSV="${CLOUD_LLM_MODELS:-$CLOUD_LLM_MODEL}"
    CLOUD_MODELS_YAML=$(printf '%s' "$CLOUD_MODELS_CSV" \
        | tr ',' '\n' \
        | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
        | grep -v '^$' \
        | sed 's/^/      - /')
    echo "云端可选模型: $(printf '%s' "$CLOUD_MODELS_CSV" | tr '\n' ' ')"

    cat >> "$MODEL_SETTINGS_FILE" << YAML_EOF
  - platform_name: cloud-api
    platform_type: openai
    api_base_url: ${CLOUD_API_BASE_URL}
    api_key: ${CLOUD_API_KEY}
    api_proxy: ''
    api_concurrencies: 5
    auto_detect_model: false
    llm_models:
${CLOUD_MODELS_YAML}
YAML_EOF

    if [ -n "$CLOUD_EMBED_MODEL" ]; then
        cat >> "$MODEL_SETTINGS_FILE" << YAML_EOF
    embed_models:
      - ${CLOUD_EMBED_MODEL}
YAML_EOF
    else
        cat >> "$MODEL_SETTINGS_FILE" << YAML_EOF
    embed_models: []
YAML_EOF
    fi

    cat >> "$MODEL_SETTINGS_FILE" << YAML_EOF
    text2image_models: []
    image2text_models: []
    rerank_models: []
    speech2text_models: []
    text2speech_models: []
YAML_EOF

    # 将默认模型切换为云端模型
    sed -i "s/^DEFAULT_LLM_MODEL:.*/DEFAULT_LLM_MODEL: ${CLOUD_LLM_MODEL}/" "$MODEL_SETTINGS_FILE"
    if [ -n "$CLOUD_EMBED_MODEL" ]; then
        sed -i "s/^DEFAULT_EMBEDDING_MODEL:.*/DEFAULT_EMBEDDING_MODEL: ${CLOUD_EMBED_MODEL}/" "$MODEL_SETTINGS_FILE"
    fi
    echo "✅ 云API注入完成，默认模型已切换为: ${CLOUD_LLM_MODEL}"
fi

# ---------------------------------------------------------------------------
# 可选的第二个云平台: DeepSeek(独立 base_url / api_key)。
# 之所以要单独一个平台: 当前网关 api.chiyi.cc 并不提供 deepseek 模型,
# DeepSeek 官方 API 与它不同源、不同 key。注入后 WebUI 的
# 「高级配置 / 模型平台」下拉里会多出 deepseek-api, 可与 cloud-api 自由切换。
# 只在 DEEPSEEK_API_KEY 非空时注入。
# ---------------------------------------------------------------------------
if [ -n "$DEEPSEEK_API_KEY" ]; then
    DS_BASE="${DEEPSEEK_API_BASE_URL:-https://api.deepseek.com/v1}"
    DS_MODELS_CSV="${DEEPSEEK_LLM_MODELS:-deepseek-chat,deepseek-reasoner}"
    DS_MODELS_YAML=$(printf '%s' "$DS_MODELS_CSV" \
        | tr ',' '\n' \
        | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
        | grep -v '^$' \
        | sed 's/^/      - /')
    echo "注入 DeepSeek 平台: ${DS_BASE} 模型: ${DS_MODELS_CSV}"
    cat >> "$MODEL_SETTINGS_FILE" << YAML_EOF
  - platform_name: deepseek-api
    platform_type: openai
    api_base_url: ${DS_BASE}
    api_key: ${DEEPSEEK_API_KEY}
    api_proxy: ''
    api_concurrencies: 5
    auto_detect_model: false
    llm_models:
${DS_MODELS_YAML}
    embed_models: []
    text2image_models: []
    image2text_models: []
    rerank_models: []
    speech2text_models: []
    text2speech_models: []
YAML_EOF
fi

# 可选: 覆盖默认模型(可指向任意已配置平台的模型, 例如 deepseek-chat)。
# 不设时沿用 cloud-api 的 CLOUD_LLM_MODEL。
if [ -n "$MTD_DEFAULT_LLM_MODEL" ]; then
    sed -i "s/^DEFAULT_LLM_MODEL:.*/DEFAULT_LLM_MODEL: ${MTD_DEFAULT_LLM_MODEL}/" "$MODEL_SETTINGS_FILE"
    echo "默认模型已被 MTD_DEFAULT_LLM_MODEL 覆盖为: ${MTD_DEFAULT_LLM_MODEL}"
fi

# ---------------------------------------------------------------------------
# 落地 model_settings.yaml —— 默认【不覆盖】已存在的文件
#   * 目标不存在(首次启动)            → 直接安装刚生成的结果
#   * MDT_REGEN_MODEL_SETTINGS=true   → 用刚生成的结果强制覆盖(改完 .env 想全量重建时用)
#   * 其它情况                        → 合并: 只把 .env 管理的平台(cloud-api/deepseek-api)
#                                       和默认模型写回已存在的文件, 其余字段与平台保留
# 这样在容器里手工改过的模型配置(新增平台、温度等)不会在重启时被冲掉。
# ---------------------------------------------------------------------------
if [ ! -f "$MODEL_SETTINGS_TARGET" ]; then
    echo "首次生成 model_settings.yaml"
    cp -f "$MODEL_SETTINGS_FILE" "$MODEL_SETTINGS_TARGET"
elif [ "$MDT_REGEN_MODEL_SETTINGS" = "true" ]; then
    echo "MDT_REGEN_MODEL_SETTINGS=true, 按 .env 全量重建 model_settings.yaml"
    cp -f "$MODEL_SETTINGS_FILE" "$MODEL_SETTINGS_TARGET"
else
    echo "合并 model_settings.yaml (保留已有内容, 仅更新 .env 管理的平台与默认模型)"
    if ! MODEL_SETTINGS_TARGET="$MODEL_SETTINGS_TARGET" MODEL_SETTINGS_GENERATED="$MODEL_SETTINGS_FILE" python3 - <<'PY'
import os
import sys

from ruamel.yaml import YAML

target = os.environ["MODEL_SETTINGS_TARGET"]
generated = os.environ["MODEL_SETTINGS_GENERATED"]

yaml = YAML()
yaml.preserve_quotes = True
yaml.width = 4096

with open(target, encoding="utf-8") as fp:
    base = yaml.load(fp)
with open(generated, encoding="utf-8") as fp:
    new = yaml.load(fp)

if base is None or new is None:
    sys.exit("配置文件为空, 改用生成结果")

if not base.get("MODEL_PLATFORMS"):
    base["MODEL_PLATFORMS"] = []

index = {}
for i, platform in enumerate(base["MODEL_PLATFORMS"]):
    index[platform.get("platform_name")] = i

for platform in new.get("MODEL_PLATFORMS") or []:
    name = platform.get("platform_name")
    if name in index:
        base["MODEL_PLATFORMS"][index[name]] = platform
    else:
        base["MODEL_PLATFORMS"].append(platform)
        index[name] = len(base["MODEL_PLATFORMS"]) - 1

for key in ("DEFAULT_LLM_MODEL", "DEFAULT_EMBEDDING_MODEL"):
    if key in new:
        base[key] = new[key]

with open(target, "w", encoding="utf-8") as fp:
    yaml.dump(base, fp)
PY
    then
        echo "警告: 合并失败, 保留原 model_settings.yaml (需要按 .env 重建时设 MDT_REGEN_MODEL_SETTINGS=true)"
    else
        echo "✅ model_settings.yaml 已合并 (env 平台/默认模型已更新, 其余改动保留)"
    fi
fi

# 默认不在每次启动时重建知识库，避免云 API 未配置 embedding 时阻塞启动。
if [ "$KB_REBUILD_ON_START" = "true" ]; then
    echo "运行 chatchat kb -r..."
    python cli.py kb -r
else
    echo "跳过知识库重建（KB_REBUILD_ON_START=$KB_REBUILD_ON_START）"
fi

# 启动ChatChat服务（在后台运行）
echo "启动 chatchat start -a (后台进程)..."
python cli.py start -a &

# 等待服务启动
echo "等待ChatChat服务启动..."
sleep 15

# 检查服务是否运行
if curl -s http://localhost:7861 > /dev/null; then
    echo "MDT服务已成功启动在端口7861"
else
    echo "警告：MDT服务可能未启动，继续..."
fi

if [ "$ENABLE_NGROK" = "true" ]; then

# 启动ngrok内网穿透并持续显示外链
echo "启动ngrok内网穿透..."
echo "ngrok公网URL将在启动后显示..."

# 创建用于存储ngrok URL的文件
NGROK_URL_FILE="/tmp/ngrok_url.txt"
echo "" > $NGROK_URL_FILE

# 在后台启动ngrok，并将输出重定向到文件
ngrok http 8501 --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

echo "ngrok进程ID: $NGROK_PID"

# 等待ngrok启动并获取URL
echo "等待ngrok启动..."
sleep 5

# 尝试从ngrok API获取公网URL
MAX_RETRIES=10
RETRY_COUNT=0
NGROK_URL=""

while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ -z "$NGROK_URL" ]; do
    echo "尝试获取ngrok公网URL (尝试 $((RETRY_COUNT+1))/$MAX_RETRIES)..."
    
    # 从ngrok API获取隧道信息
    # 从ngrok API获取隧道信息（|| true: ngrok 未起来时 curl 返回 7, 不能让 set -e 终止脚本）
    TUNNEL_INFO=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null || true)
    
    if [ $? -eq 0 ] && [ -n "$TUNNEL_INFO" ]; then
        # 解析JSON获取公网URL
        NGROK_URL=$(echo $TUNNEL_INFO | grep -o '"public_url":"[^"]*"' | head -1 | cut -d'"' -f4)
        
        if [ -n "$NGROK_URL" ]; then
            echo "================================================"
            echo "✅ ngrok公网URL获取成功:"
            echo "   $NGROK_URL"
            echo "================================================"
            
            # 将URL保存到文件
            echo $NGROK_URL > $NGROK_URL_FILE
            echo "URL已保存到: $NGROK_URL_FILE"
            
            # 创建方便的访问链接文件
            echo "📎 快速访问链接:" > /tmp/ngrok_access.txt
            echo "WebUI: $NGROK_URL" >> /tmp/ngrok_access.txt
            echo "Ollama API: http://localhost:11434" >> /tmp/ngrok_access.txt
            echo "Ngrok管理界面: http://localhost:4040" >> /tmp/ngrok_access.txt
            echo "" >> /tmp/ngrok_access.txt
            echo "📋 复制以下命令查看实时日志:" >> /tmp/ngrok_access.txt
            echo "tail -f /tmp/ngrok.log" >> /tmp/ngrok_access.txt
            
            cat /tmp/ngrok_access.txt
            break
        fi
    fi
    
    RETRY_COUNT=$((RETRY_COUNT+1))
    sleep 3
done

if [ -z "$NGROK_URL" ]; then
    echo "⚠️  无法获取ngrok公网URL，请检查ngrok日志: /tmp/ngrok.log"
    echo "您仍然可以通过以下方式访问服务:"
    echo "  - 本地WebUI: http://localhost:8501"
    echo "  - Ollama API: http://localhost:11434"
fi

else
    echo "⏭  已跳过 ngrok 内网穿透 (ENABLE_NGROK=$ENABLE_NGROK)"
    echo "   本地访问: WebUI http://localhost:8501 | API http://localhost:7861"
    NGROK_PID=""
fi

echo ""
if [ "$ENABLE_NGROK" = "true" ]; then
    echo "🔍 ngrok日志文件: /tmp/ngrok.log"
    echo "📝 实时查看日志: tail -f /tmp/ngrok.log"
fi
echo "🔄 服务运行中..."

# 保持容器运行，同时定期检查并显示ngrok状态
while true; do
    # 每30秒检查一次ngrok状态
    sleep 30
    
    # 检查ngrok进程是否还在运行（仅在启用 ngrok 时）
    if [ "$ENABLE_NGROK" = "true" ] && ! kill -0 $NGROK_PID 2>/dev/null; then
        echo "❌ ngrok进程已停止，尝试重新启动..."
        ngrok http 8501 --log=stdout > /tmp/ngrok.log 2>&1 &
        NGROK_PID=$!
        echo "ngrok已重新启动，进程ID: $NGROK_PID"
        sleep 5
    fi
    
    # 显示当前时间和服务状态
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 服务运行正常 | 本地WebUI: http://localhost:8501 | Ollama: http://localhost:11434"
    
    # 如果之前获取到了URL，也显示公网URL
    if [ "$ENABLE_NGROK" = "true" ] && [ -f "$NGROK_URL_FILE" ] && [ -s "$NGROK_URL_FILE" ]; then
        CURRENT_URL=$(cat $NGROK_URL_FILE)
        echo "   公网访问: $CURRENT_URL"
    fi
done
