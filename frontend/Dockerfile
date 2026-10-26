# 构建阶段
FROM node:20-slim AS builder
WORKDIR /app

# 设置npm镜像源
RUN npm config set registry https://registry.npmmirror.com

# 先安装锁定依赖，业务代码变更时可以复用依赖层。
COPY package.json package-lock.json ./
RUN npm ci

# 复制源代码
COPY . .

# 执行docker构建命令
RUN npm run build:docker

# 运行阶段
FROM nginx:latest
WORKDIR /usr/share/nginx/html

# 复制构建产物
COPY --from=builder /app/dist .

# 暴露端口
EXPOSE 80

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]
