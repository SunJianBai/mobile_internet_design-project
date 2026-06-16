# 前端构建阶段
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# 使用默认的相对路径 /api/v1，与 nginx 反向代理保持一致
RUN npm run build

# 运行阶段：使用 nginx 提供静态资源
FROM nginx:1.27-alpine

# 拷贝自定义 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 拷贝前端构建产物
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx","-g","daemon off;"]
