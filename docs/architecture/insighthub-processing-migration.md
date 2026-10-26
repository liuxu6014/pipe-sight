# InsightHub 处理 Worker 归并说明

## 当前唯一运行入口

InsightHub 的处理代码已经归入后端应用包：

```text
backend/src/app/intelligence/processing/
├── config/          配置
├── db/              PostgreSQL、pgvector、Redis、MinIO 适配
├── domain/          专题领域处理器
├── email_support/   告警与邮件
├── models/          新闻处理模型
├── processors/      处理流程编排
├── prompts/         领域提示词
├── runtime/         PostgreSQL/Kafka 消费运行时
├── services/        领域配置与下游发布
├── supported_text/  停用词等资源
└── utils/           健康检查和通用工具
```

Worker 仍然保持独立进程，以隔离长耗时的数据处理，但不再是独立 Python 项目。统一入口为：

```text
python -m app.intelligence.processing.main
```

统一镜像为 `backend/Dockerfile.processing.pg`，根 Compose 的 `insighthub-worker` 从 `./backend` 构建。

## 配置与数据归属

- Python 依赖统一维护在 `backend/pyproject.toml`、`backend/requirements-pg.txt` 和 `backend/uv.lock`。
- PostgreSQL 初始化脚本位于 `backend/sql/insighthub-schema.pg.sql`。
- 处理 Worker 的测试位于 `backend/tests/intelligence/processing/`。
- 运行日志统一挂载到根目录 `logs/insighthub/`，不作为源代码目录。
- PipeSight 使用 `public` schema，InsightHub 使用同一数据库实例的 `news` schema。

## 已完成的验证

1. 迁移后的处理包可被安装 wheel 正确导入，提示词、词表和邮件模板均进入构建产物。
2. 迁移后的 Worker 已在本地 Compose 中启动，容器健康状态为 `healthy`。
3. Worker `/health` 已确认 PostgreSQL、Redis、pgvector 正常。
4. 后端和迁移后的 Worker 测试均已通过；具体数量以当前 checkout 的测试输出为准。

## 维护边界

新功能只能写入 `backend/src/app/intelligence/processing`，不得重新创建 `insighthub/news_processor` 独立包。数据库、提示词、处理运行时和测试都通过后端项目统一构建和发布。

## 领域配置与提示词生效规则

`news.domains` 持久化的是中文领域名称（例如“科技”），代码处理器使用稳定的英文标识（例如 `tech`）。领域工厂通过统一映射将两者关联，并为同名领域创建混合处理器；因此管理端保存的领域配置可以进入 Worker 的实际处理链。运行查询直接读取物理表，不再依赖 `sys_domain` 或 `hp_domain` 兼容视图。

混合处理器的优先级如下：

1. 管理端已配置的数据库过滤、分类、评分提示词优先使用；
2. 对应数据库提示词为空时，回退到文件系统默认提示词；
3. 预警提示词和证据词目前沿用文件系统领域规则；
4. 新闻已存在领域缓存时，使用已注册处理器键解析，避免生成 `db_<domain>_None` 等无效键。

二次分类采用显式的默认行为：基类在未配置领域规则时原样返回新闻对象，不改变一级分类结果；领域处理器只有在确实存在二次分类业务规则时才需要覆写该方法。这样不会用空的 `try/except + pass` 冒充已实现逻辑，混合处理器仍会优先调用文件系统领域处理器的真实实现。

数据过滤的结果记录分为两个阶段：采集阶段可以先写入轻量规则预筛选结果，交接给 Worker 后，Worker 使用已发布的提示词版本和模型路由完成最终判断。最终结果会覆盖 `pipesight_filter.mode`/`executionMode`（`llm` 或 `llm-fallback`），并在顶层 `decision` 与 `workerExecution` 中保留最终判断；采集阶段的 `mode`、`executionMode`、`decision` 和 `fallback` 会保存在 `preFilter` 中。因此下游列表、重试和审计应以 Worker 结果为准，预筛选信息只用于解释为什么进入处理队列。旧记录读取时也会按该规则兼容规范化。

Inbox 的 `processing_started_at` 只表示活动 Worker 租约：领取时写入，租约过期回收或处理进入 `failed`、`rejected`、`completed` 等非活动状态时清空。这样处理状态和租约状态不会出现“已完成但仍占用中”的矛盾。

失败任务按 `POSTGRES_QUEUE_MAX_ATTEMPTS` 自动重试；达到上限后进入独立的 `dead_letter` 终态，`processing_error` 明确写入“已达到最大处理次数，需人工重试”。租约过期回收也遵循同一规则，且不会提前消耗最后一次重试机会，因此不会出现任务静默停止或无限重试。PipeSight 对外兼容展示为失败，同时保留 InsightHub 的原始终态和尝试次数，管理端可以依据失败原因执行人工重试。

这保证了“管理端配置后生效”和“未配置时保留默认处理能力”同时成立。
