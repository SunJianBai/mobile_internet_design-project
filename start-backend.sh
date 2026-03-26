#!/bin/bash
# 启动后端服务：Python Agent (5001) + Java Backend (8080)

set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

export JAVA_HOME="/opt/homebrew/opt/openjdk@21"
export PATH="$JAVA_HOME/bin:$PATH"

echo "========== 启动 MySQL =========="
brew services start mysql 2>/dev/null || true
sleep 1

echo "========== 启动 Python Agent (port 5001) =========="
cd "$ROOT_DIR/CampusCompanionAgent"
source venv/bin/activate
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 5001 > /tmp/campus-agent.log 2>&1 &
AGENT_PID=$!
echo "$AGENT_PID" > /tmp/campus-agent.pid
echo "Python Agent PID: $AGENT_PID (log: /tmp/campus-agent.log)"

echo "========== 启动 Java Backend (port 8080) =========="
cd "$ROOT_DIR/CampusCompanionBackend"
chmod +x mvnw
nohup ./mvnw spring-boot:run -q > /tmp/campus-backend.log 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > /tmp/campus-backend.pid
echo "Java Backend PID: $BACKEND_PID (log: /tmp/campus-backend.log)"

echo ""
echo "========== 等待服务就绪 =========="
for i in $(seq 1 30); do
    if curl -s http://localhost:5001/health > /dev/null 2>&1; then
        echo "✅ Python Agent 就绪 (http://localhost:5001)"
        break
    fi
    sleep 1
done

for i in $(seq 1 60); do
    if curl -s http://localhost:8080/api/v1/agent/conversations > /dev/null 2>&1; then
        echo "✅ Java Backend 就绪 (http://localhost:8080)"
        break
    fi
    sleep 2
done

echo ""
echo "========== 后端启动完成 =========="
echo "停止命令: bash stop-backend.sh"
