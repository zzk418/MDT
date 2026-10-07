![MDT 多学科诊疗教学平台](docs/img/mdt_logo_long.png)

[![Python](https://img.shields.io/badge/python-3.10%7C3.11-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Based on](https://img.shields.io/badge/based%20on-LangChain--Chatchat-blue)](https://github.com/chatchat-space/Langchain-Chatchat)

**MDT（Multi-Disciplinary Team）多学科诊疗教学平台** 是基于 [LangChain-Chatchat](https://github.com/chatchat-space/Langchain-Chatchat) 二次开发的医学教学应用，集成本地 LLM（Ollama）与国内云 API 双模式，面向医学院校提供 MDT 诊疗教学、案例分析、虚拟仿真等功能。

---

## 目录

- [快速启动](#快速启动)
- [环境配置](#环境配置)
- [数据与配置的本地位置](#数据与配置的本地位置)
- [功能介绍](#功能介绍)
- [项目架构](#项目架构)

---

## 快速启动

### 前置条件

- Windows 系统，已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（需启动并保持运行）
- 已安装 [Git](https://git-scm.com/)

### 1. 拉取代码

```bash
git clone https://github.com/zzk418/MDT.git
cd MDT
```

### 2. 配置环境变量

复制并编辑配置文件：

```bash
# Windows 下直接用记事本或 VSCode 打开 .env 编辑
copy .env.example .env
```

> `.env` 文件已提供默认配置，默认使用云 API；填写 `CLOUD_API_KEY`、`CLOUD_API_BASE_URL` 和 `CLOUD_LLM_MODEL` 后即可启动，详见 [环境配置](#环境配置)。

### 3. 启动服务

**双击运行：**

```
scripts/run_docker.bat
```

或在项目根目录命令行执行：

```bash
scripts\run_docker.bat --build
```

### 4. 访问服务

启动成功后，命令行会打印如下信息：

```
✅ ngrok公网URL获取成功:
   https://xxxx.ngrok-free.app
```

| 访问方式 | 地址 |
|---------|------|
| 本地 WebUI | http://localhost:8501 |
| 公网访问（ngrok） | 命令行输出的 ngrok URL |
| API 文档 | http://localhost:7861/docs |
| ngrok 管理界面 | http://localhost:4040 |

---

## 环境配置

编辑项目根目录的 `.env` 文件：

```ini
# =============================================
# 必填项
# =============================================

# Ngrok 内网穿透令牌（用于公网访问）
# 获取地址：https://dashboard.ngrok.com/get-started/your-authtoken
NGROK_AUTHTOKEN=your_ngrok_token_here

# =============================================
# 模型配置：默认云 API
# =============================================
MODEL_PROVIDER=cloud

# 国内云 API（推荐，默认不启动/不拉 Ollama 镜像）
# 支持：阿里云百炼 / 智谱AI / 深度求索 / 月之暗面 / 字节豆包
CLOUD_API_KEY=sk-your_api_key_here
CLOUD_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
CLOUD_LLM_MODEL=gpt-5.5
CLOUD_EMBED_MODEL=text-embedding-v3
# 首次配置 embedding 后如需重建知识库再改为 true，平时保持 false。
KB_REBUILD_ON_START=false

# 后续切换模型只改这一行，然后执行 scripts\start.bat，无需重建镜像。
# CLOUD_LLM_MODEL=gpt-4o
# CLOUD_LLM_MODEL=qwen-plus

# 本地轻量测试（需要时再切换）
# MODEL_PROVIDER=ollama
# OLLAMA_LLM_MODEL=smollm2:135m
# OLLAMA_EMBED_MODEL=
```

### 模型启动逻辑

```
MODEL_PROVIDER=cloud
    ↓ 默认只启动 chatchat，不启动/不拉 Ollama
    ↓ 使用 CLOUD_LLM_MODEL 和 CLOUD_EMBED_MODEL

MODEL_PROVIDER=ollama
    ↓ 启用 compose 的 ollama profile
    ↓ 默认只拉 smollm2:135m（约 0.27GB）
    ↓ 需要知识库向量化时，再配置 OLLAMA_EMBED_MODEL
```

> 平时建议使用 `MODEL_PROVIDER=cloud`。本地 Ollama 仅用于联调和故障排查，`smollm2:135m` 不适合医学 RAG 正式回答。

### 国内云 API 推荐

| 服务商 | BASE_URL | 推荐模型 | 特点 |
|--------|---------|---------|------|
| 阿里云百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | 与 Ollama qwen 同系列，切换无感 |
| 深度求索 | `https://api.deepseek.com/v1` | `deepseek-chat` | 性价比极高 |
| 智谱AI | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` | 有免费额度 |
| 月之暗面 | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` | 长文本能力强 |

---

## 数据与配置的本地位置

用 `docker/docker-compose.win.yaml` 启动时（Windows + Docker Desktop），网页里的改动会直接落到宿主机这份仓库里，重启容器/重启 Docker 都不会丢：

| 内容 | 宿主机路径 | 容器内路径 |
|------|-----------|-----------|
| 知识库源文件 + 向量库 | `data/knowledge_base/` | `/root/mdt_data/data/knowledge_base` |
| 对话、知识库信息（SQLite） | `data/knowledge_base/info.db` | 同上 |
| 知识库 / 提示词 / 基础设置 | `kb_settings.yaml`、`prompt_settings.yaml`、`basic_settings.yaml` | `/root/mdt_data/*.yaml` |
| 模型平台配置 | 不回写仓库，见下 | `/root/mdt_data/model_settings.yaml` |
| 服务端代码、启动脚本 | `libs/chatchat-server/`、`docker/startup.sh` | 挂载生效，改完 `docker compose restart chatchat` 即可 |

`model_settings.yaml` 由启动脚本用 `.env` + 仓库里的 `model_settings.yaml` 模板生成。默认只**合并** `.env` 管理的平台（cloud-api / deepseek-api）和默认模型，文件里其它改动（自己加的平台、温度等）不会被重启冲掉；想按 `.env` 全量重建就设 `MDT_REGEN_MODEL_SETTINGS=true`。

> 网页「高级配置」里临时选的模型、System Message 存在浏览器会话（上游 chatchat 的设计），刷新或重启会回到 `.env` 默认值，不算落盘配置。

> ⚠️ 代码、`startup.sh`、几个 `*_settings.yaml` 都是**单文件挂载**。在宿主机上用 `git checkout` 或“另存为”式编辑器改完这些文件后，文件被换掉（inode 变了），Docker Desktop 会挂载失败、容器起不来。用 `scripts\start.bat` 或 `docker compose -f docker/docker-compose.win.yaml --env-file .env up -d --force-recreate` 重建容器即可。

### 备份 / 恢复

```bash
scripts/backup_data.sh                # 整卷打包到 ~/mdt-backups/（知识库 + 配置 + 对话）
scripts/restore_data.sh <备份文件.tgz>  # 恢复（会先清空数据卷）
```

---

## 功能介绍

### MDT 诊疗教学

多学科团队（MDT）教学核心模块，支持四种教学模式：

| 教学模式 | 说明 |
|---------|------|
| **案例分析** | 加载真实 MDT 病例，AI 扮演多学科专家提供诊疗意见 |
| **虚拟仿真** | 模拟临床 MDT 会诊场景，学生可与 AI 专家团队交互 |
| **团队协作** | 多角色扮演，学生选择科室角色参与 MDT 讨论 |
| **考核评估** | 基于病例的诊疗思维评估，AI 给出评分和反馈 |

### 模型切换

侧边栏直接切换，支持：
- **本地 Ollama 模型**：qwen3:4b 等（需 GPU，完全私密）
- **云端 API 模型**：qwen-plus、deepseek-chat 等（无需 GPU，即开即用）

### RAG 知识库对话

基于医学文献知识库的智能问答，支持上传 PDF、Word、Markdown 等格式的医学资料。

### 知识库管理

可视化管理医学知识库，支持文档上传、索引重建、知识检索测试。

---

## 项目架构

```
MDT/
├── scripts/
│   └── run_docker.bat          # Windows 一键启动脚本
├── docker/
│   ├── docker-compose.win.yaml # Windows Docker 编排配置
│   ├── Dockerfile              # 容器构建文件
│   └── startup.sh              # 容器启动脚本（含模型冗余切换逻辑）
├── libs/
│   └── chatchat-server/        # 基于 LangChain-Chatchat 的服务端
│       └── chatchat/
│           ├── webui.py        # WebUI 入口（MDT 品牌定制）
│           └── webui_pages/
│               └── mdt_teaching.py  # MDT 教学核心页面
├── data/
│   └── knowledge_base/         # 知识库源文件 + 向量库 + 对话数据库（挂载进容器）
├── .env                        # 环境变量配置（不提交到 git）
├── model_settings.yaml         # 模型平台配置模板（生成物在数据卷里）
└── README.md
```

**技术栈：**
- 前端：[Streamlit](https://streamlit.io/)
- 后端：[LangChain-Chatchat](https://github.com/chatchat-space/Langchain-Chatchat) + [FastAPI](https://fastapi.tiangolo.com/)
- 本地推理：[Ollama](https://ollama.com/)
- 向量库：FAISS
- 公网穿透：[ngrok](https://ngrok.com/)

---

## 协议

本项目代码遵循 [Apache-2.0](LICENSE) 协议。基于 [LangChain-Chatchat](https://github.com/chatchat-space/Langchain-Chatchat) 开发，保留原项目协议声明。
