#!/bin/bash

# 确保data目录存在
mkdir -p data

# 构建并启动容器
docker-compose up -d

echo "Gemini Balance 服务已启动！"
echo "API服务地址: http://localhost:8000"
echo "使用 'docker-compose logs -f' 查看日志"
echo "使用 'docker-compose down' 停止服务"