#!/bin/bash

# Music Gen 部署脚本

set -e

echo "🚀 开始部署 Music Gen..."

# 远程服务器地址
REMOTE_HOST="root@119.29.178.222"
REMOTE_PORT=22

# 本地项目目录
LOCAL_DIR="/Users/easonlv/Code/music_gen"

# 远程目录
REMOTE_SERVER_DIR="/www/server/music_gen"
REMOTE_WWW_DIR="/www/wwwroot/music_gen"

echo "📦 同步后端代码..."
sshpass -p '*7;Vf3@BkrzD,g+u' ssh -o StrictHostKeyChecking=no -p $REMOTE_PORT $REMOTE_HOST "mkdir -p $REMOTE_SERVER_DIR"

# 复制后端文件
scp -o StrictHostKeyChecking=no -P $REMOTE_PORT -r $LOCAL_DIR/backend/* $REMOTE_HOST:$REMOTE_SERVER_DIR/

echo "📦 同步前端代码..."
sshpass -p '*7;Vf3@BkrzD,g+u' ssh -o StrictHostKeyChecking=no -p $REMOTE_PORT $REMOTE_HOST "mkdir -p $REMOTE_WWW_DIR"
scp -o StrictHostKeyChecking=no -P $REMOTE_PORT -r $LOCAL_DIR/frontend/* $REMOTE_HOST:$REMOTE_WWW_DIR/

echo "📦 上传Nginx配置..."
scp -o StrictHostKeyChecking=no -P $REMOTE_PORT $LOCAL_DIR/deploy/nginx.conf $REMOTE_HOST:/tmp/music_gen.conf

echo "⚙️ 配置服务..."
sshpass -p '*7;Vf3@BkrzD,g+u' ssh -o StrictHostKeyChecking=no -p $REMOTE_PORT $REMOTE_HOST << 'ENDSSH'
    set -e

    # 复制nginx配置
    cp /tmp/music_gen.conf /etc/nginx/conf.d/music_gen.conf

    # 安装Python依赖
    cd /www/server/music_gen
    pip3 install -r requirements.txt -q

    # 检查端口是否被占用
    if lsof -i:5000 > /dev/null 2>&1; then
        echo "端口5000已被占用，停止旧进程..."
        kill $(lsof -t -i:5000) 2>/dev/null || true
        sleep 1
    fi

    # 启动后端服务 (gunicorn, 4 workers)
    nohup gunicorn -w 4 -b 0.0.0.0:5000 --timeout 300 app:app > /var/log/music_gen.log 2>&1 &
    echo "后端服务已启动，PID: $!"

    # 等待服务启动
    sleep 2

    # 检查服务状态
    if curl -s http://localhost:5000/api/health > /dev/null; then
        echo "✅ 后端服务运行正常"
    else
        echo "❌ 后端服务启动失败，查看日志: tail -f /var/log/music_gen.log"
    fi

    # 重载nginx
    nginx -t && nginx -s reload
    echo "✅ Nginx配置已重载"
ENDSSH

echo "🎉 部署完成!"
echo ""
echo "访问地址: http://119.29.178.222"
echo "后端API: http://119.29.178.222:5000"
echo "日志: tail -f /var/log/music_gen.log"