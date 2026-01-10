# 基础镜像
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.11
LABEL maintainer=MDT
WORKDIR /root

# 环境变量
ENV CHATCHAT_ROOT=/root/mdt_data
ENV UV_VERSION=0.4.7

# 初始化环境
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

# 配置华为云APT镜像源
# 配置华为云 APT 镜像（Debian 12 / Bookworm）
RUN sed -i 's|http://deb.debian.org|https://mirrors.huaweicloud.com|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|http://security.debian.org|https://mirrors.huaweicloud.com|g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update -y && \
    apt-get install -y git wget curl unzip && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && \
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

# 使用uv安装依赖
WORKDIR /root/MDT/libs/chatchat-server

# 配置uv使用华为云镜像源
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 使用uv同步依赖（替代poetry install）- 移除xinference扩展
RUN uv pip install --system .

# 安装llama-cpp-python（如果需要LLaMA环境）
# RUN uv pip install --system ollama  # 注释掉，因为可能已经在依赖中

## 确保 Python 可以找到 chatchat 模块
ENV PYTHONPATH="/root/MDT/libs/chatchat-server:${PYTHONPATH}"

# 初始化配置
WORKDIR /root/MDT/libs/chatchat-server/chatchat
RUN python cli.py init

# 覆盖默认配置为正确的模型配置
COPY model_settings.yaml /root/mdt_data/model_settings.yaml

EXPOSE 7861 8501

# 复制启动脚本
COPY docker/startup.sh /root/startup.sh
RUN chmod +x /root/startup.sh

ENTRYPOINT ["/root/startup.sh"]
