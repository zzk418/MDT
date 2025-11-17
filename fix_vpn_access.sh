#!/bin/bash

# ChatChat VPN访问修复脚本
# 解决VPN连接时无法访问ChatChat服务的问题

echo "正在修复ChatChat VPN访问问题..."

# 检查ChatChat服务是否在运行
if ! pgrep -f "chatchat start -a" > /dev/null; then
    echo "错误：ChatChat服务未运行，请先启动服务：chatchat start -a"
    exit 1
fi

# 获取当前IP地址
CURRENT_IP=$(hostname -I | awk '{print $1}')
echo "当前IP地址: $CURRENT_IP"

# 检查防火墙状态
echo "检查防火墙状态..."
if command -v ufw > /dev/null; then
    echo "UFW防火墙状态:"
    ufw status
    echo "添加防火墙规则允许ChatChat端口..."
    sudo ufw allow 7861/tcp comment "ChatChat API Server"
    sudo ufw allow 8501/tcp comment "ChatChat WebUI Server"
fi

if command -v firewall-cmd > /dev/null; then
    echo "firewalld状态:"
    firewall-cmd --state
    echo "添加防火墙规则允许ChatChat端口..."
    sudo firewall-cmd --permanent --add-port=7861/tcp
    sudo firewall-cmd --permanent --add-port=8501/tcp
    sudo firewall-cmd --reload
fi

# 检查服务绑定状态
echo "检查服务绑定状态..."
netstat -tlnp | grep -E "(7861|8501)" || echo "服务未在监听端口，可能需要重启服务"

# 创建本地访问脚本
cat > access_chatchat_local.sh << 'EOF'
#!/bin/bash
# 本地访问ChatChat脚本 - 绕过VPN问题

echo "ChatChat本地访问地址:"
echo "API Server: http://127.0.0.1:7861"
echo "WebUI Server: http://127.0.0.1:8501"
echo ""
echo "如果无法通过浏览器访问，请尝试以下方法:"
echo "1. 使用 localhost 替代 IP 地址"
echo "2. 检查VPN设置，确保允许本地网络访问"
echo "3. 临时禁用VPN进行测试"
EOF

chmod +x access_chatchat_local.sh

# 创建配置备份和修复
cat > fix_chatchat_config.py << 'EOF'
#!/usr/bin/env python3
"""
ChatChat配置修复脚本
解决VPN连接时的网络访问问题
"""

import yaml
import os

def fix_basic_settings():
    """修复basic_settings.yaml配置"""
    config_file = "basic_settings.yaml"
    
    if not os.path.exists(config_file):
        print(f"配置文件 {config_file} 不存在")
        return
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 确保使用0.0.0.0绑定
    if 'API_SERVER' in config:
        config['API_SERVER']['host'] = '0.0.0.0'
    if 'WEBUI_SERVER' in config:
        config['WEBUI_SERVER']['host'] = '0.0.0.0'
    
    # 保存修复后的配置
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    print(f"已修复 {config_file} 配置")

def main():
    print("开始修复ChatChat配置...")
    fix_basic_settings()
    print("配置修复完成！")
    print("")
    print("建议操作:")
    print("1. 重启ChatChat服务: chatchat start -a")
    print("2. 使用本地地址访问: http://127.0.0.1:8501")
    print("3. 如果仍有问题，尝试临时禁用VPN")

if __name__ == "__main__":
    main()
EOF

chmod +x fix_chatchat_config.py

echo ""
echo "修复完成！"
echo ""
echo "建议操作:"
echo "1. 运行配置修复: ./fix_chatchat_config.py"
echo "2. 重启ChatChat服务: chatchat start -a"
echo "3. 使用本地访问脚本: ./access_chatchat_local.sh"
echo "4. 如果仍有问题，检查VPN设置或临时禁用VPN"
echo ""
echo "访问地址:"
echo "Web界面: http://127.0.0.1:8501"
echo "API接口: http://127.0.0.1:7861"
