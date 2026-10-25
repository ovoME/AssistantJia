# ---------- Stage 1: 构建前端 ----------
FROM node:20-alpine AS builder
WORKDIR /app

# 先安装依赖（最大化缓存命中）
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
RUN npm run build

# ---------- Stage 2: Nginx 托管 ----------
FROM nginx:1.27-alpine
LABEL org.opencontainers.image.title="xiaojia-frontend"
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
