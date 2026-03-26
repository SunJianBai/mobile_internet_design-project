#!/bin/bash
# 停止后端服务：Python Agent + Java Backend

echo "========== 停止 Python Agent =========="
if [ -f /tmp/campus-agent.pid ]; then
    PID=$(cat /tmp/campus-agent.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "已停止 Python Agent (PID: $PID)"
    else
        echo "Python Agent 未在运行 (PID: $PID)"
    fi
    rm -f /tmp/campus-agent.pid
else
    # fallback: 按端口杀
    PID=$(lsof -ti :5001 2>/dev/null)
    if [ -n "$PID" ]; then
        kill $PID
        echo "已停止 port 5001 进程 (PID: $PID)"
    else
        echo "Python Agent 未在运行"
    fi
fi

echo "========== 停止 Java Backend =========="
if [ -f /tmp/campus-backend.pid ]; then
    PID=$(cat /tmp/campus-backend.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "已停止 Java Backend (PID: $PID)"
    else
        echo "Java Backend 未在运行 (PID: $PID)"
    fi
    rm -f /tmp/campus-backend.pid
else
    PID=$(lsof -ti :8080 2>/dev/null)
    if [ -n "$PID" ]; then
        kill $PID
        echo "已停止 port 8080 进程 (PID: $PID)"
    else
        echo "Java Backend 未在运行"
    fi
fi

echo ""
echo "========== 后端已停止 =========="
