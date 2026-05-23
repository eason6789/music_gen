#!/bin/bash
# 合并music_gen到主nginx配置

sshpass -p '*7;Vf3@BkrzD,g+u' ssh -o StrictHostKeyChecking=no -p 22 root@119.29.178.222 << 'ENDSSH'
# 备份原配置
cp /etc/nginx/conf.d/tuteng3.site.conf /etc/nginx/conf.d/tuteng3.site.conf.bak_music_gen

# 检查是否已经有music_gen配置
if grep -q "music_gen" /etc/nginx/conf.d/tuteng3.site.conf; then
    echo "已存在music_gen配置，跳过"
    exit 0
fi

# 在第一个server块的location / 之前添加music_gen路由
sed -i '/location \/claw\/management\//i\
    # music_gen 前端\
    location /music_gen/ {\
        alias /var/www/music_gen/;\
        index index.html;\
        try_files $uri $uri/ /index.html;\
    }\
\
    # music_gen API代理\
    location /music/api/ {\
        proxy_pass http://127.0.0.1:5000/api/;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_read_timeout 180s;\
        proxy_connect_timeout 10s;\
        proxy_send_timeout 120s;\
    }\
' /etc/nginx/conf.d/tuteng3.site.conf

# 同样处理443的server块
sed -i '/location \/claw\/management\//i\
    # music_gen 前端\
    location /music_gen/ {\
        alias /var/www/music_gen/;\
        index index.html;\
        try_files $uri $uri/ /index.html;\
    }\
\
    # music_gen API代理\
    location /music/api/ {\
        proxy_pass http://127.0.0.1:5000/api/;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_read_timeout 180s;\
        proxy_connect_timeout 10s;\
        proxy_send_timeout 120s;\
    }\
' /etc/nginx/conf.d/tuteng3.site.conf

nginx -t && nginx -s reload && echo "✅ 配置完成"
ENDSSH