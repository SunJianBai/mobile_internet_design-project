# CampusHubAgent

## Agent 验证命令

在 `CampusHubAgent` 目录下可以运行以下脚本，分别验证意图路由和智能体调度防循环能力。

```powershell
python scripts/run_intent_eval.py --timeout 10
python scripts/run_delegation_guard_eval.py
```

`run_delegation_guard_eval.py` 不会调用真实大模型、后端或高德接口，只验证同一轮对话内的调度防线：重复任务复用、单个专家调用上限、总委派上限，以及不同用户轮次之间的状态隔离。

## `.env` 示例

```env
# SiliconFlow API
SILICONFLOW_API_KEY=sk-
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=Qwen/Qwen3-32B

# MySQL (与 Java 后端共用)
DB_HOST=localhost
DB_PORT=3306
DB_NAME=campus_companion
DB_USER=root
DB_PASSWORD=your_password

# Service
AGENT_PORT=5001
```
