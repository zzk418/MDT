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
NGROK_AUTHTOKEN="${NGROK_AUTHTOKEN//$'\r'/}"

# 配置ngrok认证令牌
if [ -n "$NGROK_AUTHTOKEN" ]; then
    echo "配置ngrok认证令牌..."
    ngrok config add-authtoken $NGROK_AUTHTOKEN
fi

# 校验云API配置
echo "检查云API配置..."
if [ -n "$CLOUD_API_KEY" ] && [ -n "$CLOUD_API_BASE_URL" ] && [ -n "$CLOUD_LLM_MODEL" ]; then
    echo "✅ 云API配置已就绪: ${CLOUD_API_BASE_URL} 模型: ${CLOUD_LLM_MODEL}"
else
    echo "❌ 未配置云API，请在 .env 中设置以下变量后重启:"
    echo "   CLOUD_API_KEY=your_key"
    echo "   CLOUD_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1"
    echo "   CLOUD_LLM_MODEL=qwen-plus"
    tail -f /dev/null
fi

# 配置目录路径
cd /root/MDT/libs/chatchat-server/chatchat

# 生成最终 model_settings.yaml（先从源文件复制，再注入云API）
echo "生成模型配置..."
MODEL_SETTINGS_FILE="/root/mdt_data/model_settings.yaml"
if [ -f "/root/MDT/model_settings.yaml" ]; then
    cp -f /root/MDT/model_settings.yaml "$MODEL_SETTINGS_FILE"
    echo "基础模型配置已复制"
fi

# 注入云API平台配置
echo "注入云API平台配置: ${CLOUD_API_BASE_URL} 模型: ${CLOUD_LLM_MODEL}"

cat >> "$MODEL_SETTINGS_FILE" << YAML_EOF
  - platform_name: cloud-api
    platform_type: openai
    api_base_url: ${CLOUD_API_BASE_URL}
    api_key: ${CLOUD_API_KEY}
    api_proxy: ''
    api_concurrencies: 5
    auto_detect_model: false
    llm_models:
      - ${CLOUD_LLM_MODEL}
    embed_models: []
    text2image_models: []
    image2text_models: []
    rerank_models: []
    speech2text_models: []
    text2speech_models: []
YAML_EOF

# 将默认模型切换为云端模型
sed -i "s/^DEFAULT_LLM_MODEL:.*/DEFAULT_LLM_MODEL: ${CLOUD_LLM_MODEL}/" "$MODEL_SETTINGS_FILE"
echo "✅ 云API注入完成，默认模型已切换为: ${CLOUD_LLM_MODEL}"

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
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 服务运行正常 | 本地WebUI: http://localhost:8501"

    # 如果之前获取到了URL，也显示公网URL
    if [ -f "$NGROK_URL_FILE" ] && [ -s "$NGROK_URL_FILE" ]; then
        CURRENT_URL=$(cat $NGROK_URL_FILE)
        echo "   公网访问: $CURRENT_URL"
    fi
done
