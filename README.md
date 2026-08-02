# 广西水鱼 - 部署指南

## 一、后端部署 (Render)

1. 打开 https://render.com
2. 用GitHub登录
3. 点 New → Web Service
4. 连接你的GitHub仓库（需要先上传 server.py 和 requirements.txt）
5. 配置：
   - Build Command: pip install -r requirements.txt
   - Start Command: python server.py
6. 点 Create Web Service
7. 记住生成的域名，如 waterfish.onrender.com

## 二、前端部署 (GitHub Pages)

1. 打开你的GitHub仓库
2. 上传 index.html
3. Settings → Pages → Source: main branch → Save
4. 等1-2分钟，得到链接如 https://你的用户名.github.io/仓库名

## 三、修改服务器地址

在 index.html 中搜索 waterfish.onrender.com 改为你的Render域名

## 四、分享链接

把GitHub Pages链接发到微信群，朋友直接点开玩！
