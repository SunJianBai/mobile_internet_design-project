#!/bin/bash
# 停止前端开发服务器

echo "========== 停止前端 =========="
if [ -f /tmp/campus-frontend.pid ]; then
    PID=$(cat /tmp/campus-frontend.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "已停止前端 (PID: $PID)"
    else
        echo "前端未在运行 (PID: $PID)"
    fi
    rm -f /tmp/campus-frontend.pid
else
    # fallback: 杀 vite 相关进程
    PIDS=$(lsof -ti :5173 2>/dev/null; lsof -ti :5174 2>/dev/null)
    if [ -n "$PIDS" ]; then
        kill $PIDS 2>/dev/null
        echo "已停止前端进程"
    else
        echo "前端未在运行"
    fi
fi

echo ""
echo "========== 前端已停止 =========="
