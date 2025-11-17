#!/usr/bin/env python3
"""
测试ollama配置是否正常工作
"""

import requests
import json

def test_ollama_connection():
    """测试ollama连接"""
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags")
        if response.status_code == 200:
            models = response.json()
            print("✅ Ollama连接成功")
            print(f"可用模型: {[model['name'] for model in models['models']]}")
            return True
        else:
            print(f"❌ Ollama连接失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ollama连接异常: {e}")
        return False

def test_chatchat_api():
    """测试ChatChat API"""
    try:
        response = requests.get("http://127.0.0.1:7861/docs")
        if response.status_code == 200:
            print("✅ ChatChat API服务正常")
            return True
        else:
            print(f"❌ ChatChat API服务异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ ChatChat API连接异常: {e}")
        return False

def test_model_availability():
    """测试模型可用性"""
    try:
        # 测试默认LLM模型
        from chatchat.server.utils import get_default_llm, get_default_embedding
        llm_model = get_default_llm()
        embed_model = get_default_embedding()
        
        print(f"✅ 默认LLM模型: {llm_model}")
        print(f"✅ 默认嵌入模型: {embed_model}")
        
        # 检查模型是否在ollama中
        response = requests.get("http://127.0.0.1:11434/api/tags")
        models = response.json()
        available_models = [model['name'] for model in models['models']]
        
        if llm_model in available_models:
            print(f"✅ LLM模型 '{llm_model}' 在ollama中可用")
        else:
            print(f"⚠️ LLM模型 '{llm_model}' 在ollama中不可用")
            
        if embed_model in available_models:
            print(f"✅ 嵌入模型 '{embed_model}' 在ollama中可用")
        else:
            print(f"⚠️ 嵌入模型 '{embed_model}' 在ollama中不可用")
            
        return True
    except Exception as e:
        print(f"❌ 模型可用性测试失败: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("测试ollama配置")
    print("=" * 50)
    
    # 测试ollama连接
    test_ollama_connection()
    print()
    
    # 测试模型可用性
    test_model_availability()
    print()
    
    print("配置总结:")
    print("- 默认LLM: qwen3:4b-instruct-2507-q8_0")
    print("- 默认嵌入模型: nomic-embed-text:latest") 
    print("- ollama平台: http://127.0.0.1:11434/v1")
    print("- 项目已配置为使用本地ollama服务")
