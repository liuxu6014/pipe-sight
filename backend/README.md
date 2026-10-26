# PipeSight 后端

这是国家管网科技情报与科研辅助平台的 FastAPI 后端。后端采用 `src/app` 源码布局，业务按领域组织，技术设施与 HTTP 横切能力单独归位。

## 当前包入口

长期源码布局为 `src/app/`，统一 Python 导入包名为 `app`。当前 API 入口已建立：

```text
src/app/
├── bootstrap.py          # 应用工厂、生命周期和基础设施组装
├── health/               # 存活与就绪检查
├── system/               # 认证、用户、角色、菜单、配置和字典
│   ├── api/               # 系统管理 HTTP 接口与 API 契约
│   ├── models/            # 系统管理 ORM 模型
│   ├── repositories/      # 系统管理数据访问
│   └── services/          # 系统管理用例
├── intelligence/         # 科技情报业务包
│   ├── services/          # 数据处理、数据源、采集、交接、Prompt、模板
│   ├── api/               # 情报 API 控制器与 Pydantic DTO
│   ├── integrations/      # InsightHub 等外部处理系统适配器
│   ├── tasks/              # 来源定时采集、外部回执轮询等后台任务
│   ├── repositories/      # 情报业务数据访问层
│   ├── models/            # SQLAlchemy 持久化模型
│   └── processing/        # 已并入应用包的 InsightHub 数据处理 Worker
├── library/              # 资料库边界
│   ├── api/controller.py  # 资料库 HTTP 接口
│   ├── services/materials.py # 文件解析能力、API策略、权限、事务和文件生命周期
│   └── tasks/material_parse_scheduler.py # PostgreSQL租约资料解析队列
├── research/             # 科研工作区、任务和成果
│   ├── api/controller.py  # 工作区、任务和报告 HTTP 接口
│   └── services/         # 资料篮、任务生命周期、证据、报告编排、版本、自动计划和后台执行
├── entrypoints/
│   ├── api.py            # API进程入口
│   └── task_worker.py    # 科研任务、报告导出、资料解析持久队列 Worker 入口
└── infrastructure/       # 跨业务技术设施和管理端运维能力
    ├── api/               # 缓存、日志、定时任务、文件和服务器监控接口
    ├── models/            # 审计日志、任务和调度日志模型
    ├── repositories/      # 技术设施数据访问
    └── services/          # 文件、日志、加密、分页、导出、序列化等技术服务
```

`server.py` 仅作为兼容启动入口，应用工厂位于 `app.bootstrap`，API/Worker 入口位于 `app.entrypoints`。`common/` 只承载 HTTP、依赖和注解等横切适配，其中 `common/http/schemas.py` 放置跨业务 HTTP 契约，`common/http/status.py` 放置 HTTP 状态码，`common/http/contracts.py` 放置接口命名空间与缓存分组，`common/http/responses.py` 放置响应构造器，`common/http/context.py` 和 `common/http/dependencies.py` 放置请求上下文与路由依赖；通用运行常量位于 `common/constants.py`，系统菜单常量位于 `app/system/constants.py`。CLI 的文本输出位于 `cli/output.py`，内部 CLI 子进程支持位于 `cli/runtime/nested_cli.py`，不再使用泛化的 `cli/utils.py`。`config/` 承载运行配置与 Alembic 模型发现。旧 `module_*` 业务包和全局 `utils/` 已从正式运行路径移除，新的代码必须按领域模块或基础设施职责放置。数据处理、公开来源采集、Prompt、模板服务、数据访问层、持久化模型和 API DTO 已迁入 `app.intelligence`；资料解析能力已迁入 `app.library.services.materials`，资料篮、任务状态、证据、报告编排和后台执行已分别迁入 `app.research.services`。

InsightHub 处理子系统也按职责拆分，不再使用泛化的 `processing/utils`：领域常量位于 `processing/config/constants`，领域名称映射位于 `processing/domain`，过滤审计、地理编码和 SimHash 位于 `processing/processors`，Worker 健康/日志/时间支持位于 `processing/runtime`，模型调用适配位于 `processing/services/model_generation.py`。

### 分层放置规则

- `api` 只负责 HTTP 参数、认证依赖、服务调用和响应转换。
- `services` 负责业务用例、权限、事务和状态流转；不直接暴露数据库细节。
- `repositories` 负责所属边界的数据访问；不自行决定业务权限或提交事务。
- `models` 只描述持久化结构和关联；API 契约放在 `schemas`。
- `infrastructure` 提供可复用技术能力，不反向依赖具体业务模块。
- `common` 只放真正跨业务的 HTTP/依赖适配；具体业务公共逻辑必须回到所属领域。

## 常用入口

```bash
uv run pipesight-api
uv run ruoyi app run --env=dev
```

### 上传资料安全扫描

知识资料上传后先进入 `pending` 扫描状态。只有外部扫描命令返回退出码 `0` 才会标记为 `clean`，退出码 `1` 标记为 `quarantined`，超时、命令不存在或其他退出码标记为 `failed`；未通过扫描的资料不能解析、下载或用于 AI 证据。扫描通过后只写入 `queued`，由独立 Worker 按租约异步解析，API 不再同步等待大文件解析。

通过环境变量配置扫描模式。生产环境应使用 `external`，文件路径会作为最后一个参数
传入扫描命令，后端不经过 shell：

```bash
FILE_SCAN_MODE=external
FILE_SCAN_COMMAND="clamdscan --no-summary"
FILE_SCAN_TIMEOUT_SECONDS=30
```

本地开发/验收可以显式使用基础检查模式：

```bash
FILE_SCAN_MODE=basic
```

`basic` 只校验文件大小和常见可执行文件头，不检查压缩包内部内容、宏、脚本行为或病毒特征库，不能作为生产杀毒方案。`external` 未配置扫描命令时保持 `pending`，不会把文件头校验误认为病毒扫描。扫描状态和 SHA-256 文件摘要持久化在 `knowledge_files` 中。

### 数据源调度

数据源保存时会立即校验五段式 APScheduler Cron 表达式，并统一按 `Asia/Shanghai` 解析；空表达式表示仅允许手动触发。采集、手动运行队列和 InsightHub 回执由 `pipesight-task-worker` 执行，API 进程不会同步执行采集。错误的调度表达式会在配置阶段直接返回，不会保存成功后才被 Worker 跳过。

`ruoyi app run` 仍作为兼容入口保留；运行环境需要先安装 `requirements-pg.txt` 或对应的锁定依赖。独立任务 Worker 可通过 `uv run pipesight-task-worker` 启动，统一负责数据源采集、InsightHub 交接回执、科研生成、报告导出和资料解析。Compose 环境由 `pipesight-db-migrate` 在 API/Worker 前执行 Alembic 迁移；采集来源和交接回执通过数据库租约实现跨进程防重。

### 报告导出任务

DOCX/PDF 导出先写入 PostgreSQL 的 `report_exports`，再由独立 `pipesight-task-worker` 按数据库租约领取。任务包含报告快照、版本/模板信息、尝试次数、租约到期时间、退避重试时间、文件大小和 SHA-256；Worker 重启后，过期租约会重新进入领取流程。导出文件通过受保护下载接口返回，不暴露上传目录。

PostgreSQL Compose 环境将 `vf_admin/upload_path` 挂载到 `ruoyi-upload-data` 持久卷，保证容器重建不会只留下数据库记录而丢失已生成文件。API 通过 `PIPELINE_TASK_SCHEDULER_ENABLED=false` 放弃采集、InsightHub 交接、科研、导出和资料解析任务，由 `pipesight-task-worker` 专职执行；对象存储、保留期和清理策略仍属于后续运维增强项。

科研生成任务同样先写入 `generation_tasks`，由独立 Task Worker 按租约领取；任务心跳会续租，通用异常最多自动重试 3 次，Worker 重启后会重新扫描 queued 或租约过期任务。取消会先记录 `cancel_requested_at`，运行中的执行器在阶段边界安全停止，避免取消请求与报告发布发生竞态；取消、完成和租约失效由数据库状态与执行器持有者共同裁决，避免旧执行器在取消或重试后再次发布报告。
自动重试耗尽的瞬态异常会进入 `dead_letter` 状态，用户可在任务页人工重新生成；业务校验类不可重试错误仍保持 `failed`，避免无意义地重复调用模型。

## 迁移原则

- API 只负责请求、认证依赖和响应转换。
- Service 负责业务规则、权限和事务编排。
- Repository 负责所属业务的数据访问。
- Worker 调用业务 Service，不复制一套处理逻辑。
- 数据库迁移统一由 `alembic/` 管理，模型发现入口位于 `config/model_discovery.py`。
