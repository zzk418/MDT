#!/bin/bash

# 设置错误处理
set -e

echo "=== 启动 MDT 服务 ==="

# 加载环境变量
if [ -f "/root/MDT/.env" ]; then
    echo "加载环境变量..."
    source /root/MDT/.env
fi

# 配置ngrok认证令牌
if [ -n "$NGROK_AUTHTOKEN" ]; then
    echo "配置ngrok认证令牌..."
    ngrok config add-authtoken $NGROK_AUTHTOKEN
fi

# 等待ollama服务启动
echo "等待ollama服务启动..."
# 支持跨平台：Linux host 模式用 localhost，Windows bridge 模式用服务名
OLLAMA_HOST="${OLLAMA_HOST:-localhost}"
# 等待ollama服务完全启动，检查API是否可用
OLLAMA_READY=false
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
    echo "警告: Ollama服务在60秒内未启动，模型拉取可能会失败"
fi

# 通过 /api/tags 接口查询模型是否已在 ollama 中存在
model_exists() {
    local model="$1"
    # 取 name 字段（格式为 "model:tag"），精确匹配
    curl -s "http://${OLLAMA_HOST}:11434/api/tags" \
        | grep -o '"name":"[^"]*"' \
        | grep -q "\"name\":\"${model}\""
}

# 拉取Ollama模型（chatchat容器内没有ollama命令，只能用curl HTTP API）
# 所有模型必须拉取成功，否则阻塞不继续启动后续服务
ALL_MODELS_READY=true

if [ -n "$OLLAMA_MODELS" ]; then
    echo "开始拉取Ollama模型: $OLLAMA_MODELS"
    IFS=',' read -ra MODELS <<< "$OLLAMA_MODELS"

    if [ "$OLLAMA_READY" = true ]; then
        for model in "${MODELS[@]}"; do
            model="$(echo "$model" | tr -d '[:space:]')"

            # 先查 /api/tags 确认是否已存在，避免重复拉取
            if model_exists "$model"; then
                echo "模型 $model 已存在，跳过拉取"
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
    else
        echo "❌ 错误: Ollama服务未就绪，无法拉取模型，中止启动"
        ALL_MODELS_READY=false
    fi
else
    echo "未找到OLLAMA_MODELS环境变量，跳过模型拉取"
fi

# 模型未全部就绪则阻塞，不启动 chatchat 和 ngrok
if [ "$ALL_MODELS_READY" = false ]; then
    echo ""
    echo "================================================"
    echo "🚫 模型未全部就绪，服务启动已中止"
    echo "   请解决上述问题后重启容器:"
    echo "   docker compose -f docker/docker-compose.win.yaml restart chatchat"
    echo "================================================"
    # 保持容器运行以便查看日志，但不启动任何服务
    tail -f /dev/null
fi

# 配置目录路径
cd /root/MDT/libs/chatchat-server/chatchat

# 确保使用正确的模型配置
echo "确保模型配置正确..."
if [ -f "/root/MDT/model_settings.yaml" ]; then
    cp -f /root/MDT/model_settings.yaml /root/mdt_data/model_settings.yaml
    # 将 api_base_url 中的地址替换为实际 ollama 服务地址（bridge 网络下为服务名，host 网络下为 127.0.0.1）
    sed -i "s|http://127.0.0.1:11434|http://${OLLAMA_HOST}:11434|g" /root/mdt_data/model_settings.yaml
    echo "模型配置已更新，ollama地址: http://${OLLAMA_HOST}:11434"
fi

# 初始化知识库
echo "运行 chatchat kb -r..."
python cli.py kb -r

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
    TUNNEL_INFO=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null)
    
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

echo ""
echo "🔍 ngrok日志文件: /tmp/ngrok.log"
echo "📝 实时查看日志: tail -f /tmp/ngrok.log"
echo "🔄 服务运行中..."

# 保持容器运行，同时定期检查并显示ngrok状态
while true; do
    # 每30秒检查一次ngrok状态
    sleep 30
    
    # 检查ngrok进程是否还在运行
    if ! kill -0 $NGROK_PID 2>/dev/null; then
        echo "❌ ngrok进程已停止，尝试重新启动..."
        ngrok http 8501 --log=stdout > /tmp/ngrok.log 2>&1 &
        NGROK_PID=$!
        echo "ngrok已重新启动，进程ID: $NGROK_PID"
        sleep 5
    fi
    
    # 显示当前时间和服务状态
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 服务运行正常 | 本地WebUI: http://localhost:8501 | Ollama: http://localhost:11434"
    
    # 如果之前获取到了URL，也显示公网URL
    if [ -f "$NGROK_URL_FILE" ] && [ -s "$NGROK_URL_FILE" ]; then
        CURRENT_URL=$(cat $NGROK_URL_FILE)
        echo "   公网访问: $CURRENT_URL"
    fi
done
