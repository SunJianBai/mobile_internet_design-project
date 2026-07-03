# CampusHubAgent

## Agent 验证命令

在 `CampusHubAgent` 目录下可以运行以下脚本，分别验证意图路由和智能体调度防循环能力。

```powershell
python scripts/run_intent_eval.py --timeout 10
python scripts/run_intent_eval.py --suite evals/persona_scenarios.json --timeout 12
python scripts/run_intent_eval.py --suite evals/semantic_scenarios.json --semantic-only --timeout 30
python scripts/run_direct_read_eval.py
python scripts/run_contextual_order_eval.py
python scripts/run_delegation_guard_eval.py
python scripts/run_journey_eval.py
python scripts/run_router_fallback_eval.py
```

`persona_scenarios.json` 覆盖更接近真人表达的请求，例如先查地图再创建草稿、否定发布动态、草稿追改、记忆偏好、评论/点赞确认等，用来防止意图分析在自然语言场景里退化。

`semantic_scenarios.json` 建议配合 `--semantic-only` 使用。该模式会临时关闭本地快捷路由，让请求进入轻量大模型语义路由，用来验证“不是单纯关键词匹配”的复杂表达和上下文追改能力。

`run_direct_read_eval.py` 使用假地图/天气工具结果验证直读响应，确保地图推荐会返回可渲染地图和下一步引导卡片，同时不访问外部接口。

`run_contextual_order_eval.py` 验证多轮地图到订单草稿的衔接：用户先查地图候选，下一轮说“就第一家”时，Agent 应进入订单草稿确认门控，并自动带上地点名称、坐标、人数、活动类型和校区。

`run_delegation_guard_eval.py` 不会调用真实大模型、后端或高德接口，只验证同一轮对话内的调度防线：重复任务复用、语义相近任务复用、单个专家调用上限、总委派上限，以及不同用户轮次之间的状态隔离。

`run_journey_eval.py` 使用多轮真人旅程验证上下文路由：先查地图再创建草稿、草稿追改、谨慎报名、只读切换、天气后改室内安排，以及长期偏好记忆确认。

`run_router_fallback_eval.py` 会模拟轻量意图路由模型不可用，验证明确只读请求仍能安全降级到地图/约伴查询，而不是退化成 `unknown`。

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
