#!/bin/bash
# 启动前端开发服务器

set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========== 启动前端 (Vite Dev Server) =========="
cd "$ROOT_DIR/CampusCompanionWeb"

# 安装依赖（如果 node_modules 不存在）
if [ ! -d "node_modules" ]; then
    echo "正在安装前端依赖..."
    npm install
fi

nohup npm run dev > /tmp/campus-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > /tmp/campus-frontend.pid
echo "前端 PID: $FRONTEND_PID (log: /tmp/campus-frontend.log)"

# 等待启动
for i in $(seq 1 15); do
    PORT=$(grep -o 'http://localhost:[0-9]*' /tmp/campus-frontend.log 2>/dev/null | head -1)
    if [ -n "$PORT" ]; then
        echo "✅ 前端就绪 ($PORT)"
        break
    fi
    sleep 1
done

echo ""
echo "========== 前端启动完成 =========="
echo "停止命令: bash stop-frontend.sh"
