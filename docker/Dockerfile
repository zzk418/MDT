# 基础镜像
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.11
LABEL maintainer=MDT
WORKDIR /root

# 环境变量
ENV CHATCHAT_ROOT=/root/mdt_data
ENV UV_VERSION=0.4.7

# 本机(Windows 宿主 clash/Desktop 代理)会把访问国内镜像的流量绕到境外, 导致 ~150KB/s 且大包必超时。
# 这里把国内镜像域名加入 NO_PROXY 强制直连(走代理反而慢/断), 境外资源(如 ngrok 的 equinox.io)仍走代理。
ENV NO_PROXY="localhost,127.0.0.1,::1,127.0.0.0/8,.huaweicloud.com,.tuna.tsinghua.edu.cn,mirrors.aliyun.com,mirrors.ustc.edu.cn"
ENV no_proxy="${NO_PROXY}"

# 初始化环境
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

# 配置华为云APT镜像源
# 配置华为云 APT 镜像（Debian 12 / Bookworm）
RUN sed -i 's|http://deb.debian.org|https://mirrors.huaweicloud.com|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|http://security.debian.org|https://mirrors.huaweicloud.com|g' /etc/apt/sources.list.d/debian.sources

# libgl1/libglib2.0-0 原为 opencv-python 运行时 GL 依赖, opencv 已精简掉, 一并移除
RUN apt-get update -y && \
    apt-get install -y git wget curl unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 配置华为云pip镜像源
RUN pip config set global.index-url https://mirrors.huaweicloud.com/repository/pypi/simple && \
    pip config set global.trusted-host mirrors.huaweicloud.com

# 安装uv (Python包管理器)
RUN pip install --upgrade pip setuptools && \
    pip install uv==${UV_VERSION}

# 下载ngrok (用于内网穿透)
RUN wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz -O ngrok.tgz && \
    tar -xzf ngrok.tgz && \
    mv ngrok /usr/local/bin/ && \
    rm ngrok.tgz

# 复制整个MDT项目
COPY . /root/MDT

RUN sed -i 's/\r$//' /root/MDT/.env || true

# 使用uv安装依赖
WORKDIR /root/MDT/libs/chatchat-server

# 配置uv使用清华镜像源(包最全; 访问走上面的 NO_PROXY 直连)
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
# 本机直连国内镜像约 0.1~0.6MB/s, 且波动大:
#   拉大超时, 避免大 wheel(如 streamlit-aggrid 7.7MB)下载中断;
#   限制并发数, 防止几十路并行把慢链路饿死导致个别小包也超时。
ENV UV_HTTP_TIMEOUT=1800
ENV UV_CONCURRENT_DOWNLOADS=8
ENV UV_CACHE_DIR=/root/.cache/uv

# 使用uv同步依赖（替代poetry install）- 移除xinference扩展
# env -u: 剥掉 Docker Desktop / 宿主注入的代理, 让清华源直连(代理绕境外会慢到超时)
# -v: 逐包打印正在拉取的 wheel(uv 默认在非交互日志里不显示任何进度)
# --mount=type=cache: 下载缓存跨构建/跨失败保留, 依赖只需下一次(慢链路下省最多时间)
RUN --mount=type=cache,target=/root/.cache/uv \
    env -u http_proxy -u https_proxy -u all_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
    uv pip install -v --system .

# 安装llama-cpp-python（如果需要LLaMA环境）
# RUN uv pip install --system ollama  # 注释掉，因为可能已经在依赖中

## 确保 Python 可以找到 chatchat 模块
ENV PYTHONPATH="/root/MDT/libs/chatchat-server:${PYTHONPATH}"

# 初始化配置
WORKDIR /root/MDT/libs/chatchat-server/chatchat

RUN cp -r /root/MDT/data/* ./data/

RUN python cli.py init

# 覆盖默认配置为正确的模型配置
COPY model_settings.yaml /root/mdt_data/model_settings.yaml

# -----------------------------------------------------------------------------
# 预置配置与知识库（纯镜像部署用）
#   cli init 只会生成 samples 默认值, 这里用仓库版本覆盖:
#     - kb/prompt/basic 配置: 默认知识库 MDT知识库、RAG 提示词修正、监听 0.0.0.0
#     - data/knowledge_base : MDT知识库 的源文件 + FAISS 向量库 + info.db 登记
#     - 删除 samples, 并清空对话记录, 避免把本机测试会话烘进发布镜像
# -----------------------------------------------------------------------------
COPY kb_settings.yaml /root/mdt_data/kb_settings.yaml
COPY prompt_settings.yaml /root/mdt_data/prompt_settings.yaml
COPY basic_settings.yaml /root/mdt_data/basic_settings.yaml
COPY docker/sanitize_kb_db.py /tmp/sanitize_kb_db.py

RUN rm -rf /root/mdt_data/data/knowledge_base/samples && \
    cp -a /root/MDT/data/knowledge_base/. /root/mdt_data/data/knowledge_base/ && \
    python /tmp/sanitize_kb_db.py /root/mdt_data/data/knowledge_base/info.db && \
    rm -f /tmp/sanitize_kb_db.py

EXPOSE 7861 8501

# 复制启动脚本
COPY docker/startup.sh /root/startup.sh

# win 修改 CRLF
RUN sed -i 's/\r$//' /root/startup.sh

RUN chmod +x /root/startup.sh

ENTRYPOINT ["/root/startup.sh"]
