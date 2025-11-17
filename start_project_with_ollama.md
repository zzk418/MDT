# Langchain-Chatchat 项目启动指南（使用本地Ollama）

## 配置概览

已成功配置项目使用本地Ollama服务：

### 模型配置
- **默认LLM模型**: `qwen3:4b-instruct-2507-q8_0`
- **默认嵌入模型**: `nomic-embed-text:latest`
- **Ollama服务地址**: `http://127.0.0.1:11434/v1`

### 可用模型
- **LLM模型**: 
  - `qwen3:4b-instruct-2507-q8_0` (默认)
  - `qwen:7b`
  - `qwen2:7b`
- **嵌入模型**:
  - `nomic-embed-text:latest` (默认)
  - `quentinz/bge-large-zh-v1.5`

## 启动项目

### 1. 确保Ollama服务运行
```bash
# 检查Ollama状态
curl http://127.0.0.1:11434/api/tags
```

### 2. 启动ChatChat项目

#### 方式一：启动所有服务（推荐）
```bash
python -c "from chatchat import startup; startup.main()" -a
```

#### 方式二：分别启动服务
```bash
# 启动API服务
python -c "from chatchat import startup; startup.main()" --api

# 启动WebUI服务（新终端）
python -c "from chatchat import startup; startup.main()" --webui
```

### 3. 访问项目

- **API文档**: http://127.0.0.1:7861/docs
- **Web界面**: http://127.0.0.1:8501

## 验证配置

运行测试脚本验证配置：
```bash
python test_ollama_config.py
```

## 故障排除

### 常见问题

1. **Ollama连接失败**
   ```bash
   # 启动Ollama服务
   ollama serve
   ```

2. **模型未加载**
   ```bash
   # 检查Ollama中的模型
   ollama list
   
   # 如果缺少模型，可以拉取
   ollama pull qwen3:4b-instruct-2507-q8_0
   ollama pull nomic-embed-text:latest
   ```

3. **端口冲突**
   - API服务默认端口：7861
   - WebUI服务默认端口：8501
   - 如果端口被占用，可以修改配置

### 配置修改

如果需要修改配置，编辑 `model_settings.yaml` 文件：

```yaml
# 修改默认模型
DEFAULT_LLM_MODEL: your-model-name
DEFAULT_EMBEDDING_MODEL: your-embedding-model

# 修改Ollama配置
MODEL_PLATFORMS:
  - platform_name: ollama
    platform_type: ollama
    api_base_url: http://127.0.0.1:11434/v1
    # ... 其他配置
```

## 使用说明

1. 项目启动后，可以通过Web界面进行对话
2. 支持知识库问答、Agent功能等
3. 所有模型调用都通过本地Ollama服务完成
4. 无需网络连接即可使用（模型已本地部署）

## 性能提示

- `qwen3:4b-instruct-2507-q8_0` 是4B参数的量化模型，适合大多数硬件
- 如果需要更高性能，可以考虑使用更大的模型
- 嵌入模型 `nomic-embed-text:latest` 提供高质量的文本嵌入
