# CampusHubAgent

## Agent 验证命令

在 `CampusHubAgent` 目录下可以运行以下脚本，分别验证意图路由和智能体调度防循环能力。

```powershell
python scripts/run_agent_quality_suite.py
python scripts/run_agent_quality_suite.py --include-semantic
python scripts/run_intent_eval.py --timeout 10
python scripts/run_intent_eval.py --suite evals/persona_scenarios.json --timeout 12
python scripts/run_intent_eval.py --suite evals/semantic_scenarios.json --semantic-only --timeout 30
python scripts/run_direct_read_eval.py
python scripts/run_contextual_order_eval.py
python scripts/run_memory_filter_eval.py
python scripts/run_delegation_guard_eval.py
python scripts/run_journey_eval.py
python scripts/run_router_fallback_eval.py
```

`run_agent_quality_suite.py` 是推荐的阶段性质量门。默认会一次运行基础意图、真人 persona、多轮 journey、直接读取结果卡片、地图结果转订单草稿、记忆过滤、委派防循环、路由降级等回归检查；`--include-semantic` 会额外运行较慢的 LLM semantic-only 路由，用来验证复杂自然语言不是靠关键词硬分流。
该质量门默认使用 `--jobs 3` 并发运行互不依赖的检查；如果需要排查单个脚本日志顺序，可以加 `--jobs 1` 串行执行。
`persona_scenarios.json` 覆盖更接近真人表达的请求，例如先查地图再创建草稿、否定发布动态、草稿追改、记忆偏好、评论/点赞确认等，用来防止意图分析在自然语言场景里退化。

`semantic_scenarios.json` 建议配合 `--semantic-only` 使用。该模式会临时关闭本地快捷路由，让请求进入轻量大模型语义路由，用来验证“不是单纯关键词匹配”的复杂表达和上下文追改能力。

`run_direct_read_eval.py` 使用假地图/天气工具结果验证直读响应，确保地图推荐会返回可渲染地图和下一步引导卡片，同时不访问外部接口。

`run_contextual_order_eval.py` 验证多轮地图到订单草稿的衔接：用户先查地图候选，下一轮说“就第一家”时，Agent 应进入订单草稿确认门控，并自动带上地点名称、坐标、人数、活动类型和校区。

`run_memory_filter_eval.py` 不调用大模型、后端或高德，只验证 Python Agent 在返回记忆抽取结果前会过滤 `none`、无事实、低置信猜测、临时地图/草稿/搜索结果等噪声，同时保留长期偏好和稳定个人事实。

`run_delegation_guard_eval.py` 不会调用真实大模型、后端或高德接口，只验证同一轮对话内的调度防线：重复任务复用、语义相近任务复用、单个专家调用上限、总委派上限，以及不同用户轮次之间的状态隔离。

`run_journey_eval.py` 使用多轮真人旅程验证上下文路由：先查地图再创建草稿、草稿追改、谨慎报名、只读切换、天气后改室内安排，以及长期偏好记忆确认。

`run_router_fallback_eval.py` 会模拟轻量意图路由模型不可用，验证明确只读请求仍能安全降级到地图/约伴查询，而不是退化成 `unknown`。

## `.env` 示例

```env
# SiliconFlow API
SILICONFLOW_API_KEY=sk-
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=Qwen/Qwen3-32B
SILICONFLOW_ROUTER_MODEL=Qwen/Qwen3-32B

# MySQL (与 Java 后端共用)
DB_HOST=localhost
DB_PORT=3306
DB_NAME=campus_companion
DB_USER=root
DB_PASSWORD=your_password

# Service
AGENT_PORT=5001
```

`SILICONFLOW_MODEL` 用于主回复、子智能体和复杂确认草稿；`SILICONFLOW_ROUTER_MODEL` 只负责意图分类，建议生产环境配置为响应更快、成本更低的兼容模型，并用 `python scripts/run_intent_eval.py --suite evals/semantic_scenarios.json --semantic-only` 验证语义路由质量。
