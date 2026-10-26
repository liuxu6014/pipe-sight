# 项目结构整理

本文用于管网项目设计管理、开发交接和后续模块扩展。说明以当前仓库为准，并刻意排除了依赖、构建产物、缓存和运行日志目录。

> 本文是现有结构概览，部分示意省略了实际文件。后续重构请使用 [项目目标结构与分层开发规范](architecture/project-structure-and-layering.md)。`backend/src/app/` 的统一入口、情报核心层和资料解析能力已落地，旧模块代码已退出运行路径，后续仅维护业务闭环和部署验收。

## 1. 项目总览

`pipeSight` 是一个前后端分离项目，主体基于 `RuoYi-Vue3-FastAPI` 扩展，当前业务聚焦“国家管网科技情报与科研辅助平台”。

| 层级 | 目录 | 职责 |
| --- | --- | --- |
| 前端 | `frontend/` | Vue 3 管理端、管网用户门户、页面路由、API 封装和 UI 组件 |
| 后端 | `backend/` | FastAPI 应用、系统管理、管网业务 API、AI 模块、调度和 CLI |
| InsightHub Worker | `backend/src/app/intelligence/processing/` | PostgreSQL 新闻处理 Worker、领域处理器、Prompt、向量写入和测试 |
| 文档 | `docs/` | 按架构、需求、参考、计划、交接和汇报分类的项目资料 |
| 图片资产 | `images/` | 项目展示、方案或文档配图 |
| 容器编排 | `docker-compose.pg.yml` | PostgreSQL + pgvector + Redis 的默认运行入口；`docker-compose.my.yml` 仅保留作历史迁移参考 |

顶层结构：

```text
pipeSight/
|-- backend/
|-- frontend/
|-- docs/
|-- images/
|-- docker-compose.pg.yml       # 默认运行入口
|-- docker-compose.my.yml       # 历史迁移参考
`-- README.md
```

## 2. 后端结构

后端采用可安装的 FastAPI 应用包。当前入口是 `backend/src/app/entrypoints/api.py`，应用组装、生命周期、路由注册和基础设施初始化统一位于 `app/bootstrap.py`；旧的 `backend/app.py` 已删除，避免与 `app` 包同名遮蔽。`backend/server.py` 仅保留启动兼容导入，路由由 `app.entrypoints.routes` 按显式控制器清单注册；管网业务控制器位于 `app.intelligence.api.pipeline_controller`，路由组件位于 `backend/common/http/routing.py`，旧 `common/router.py` 及其通配扫描已移除。新包化入口使用 `python -m app.entrypoints.api`。

```text
backend/
|-- src/app/                       # 目标Python包，API入口已建立
|   |-- entrypoints/api.py         # API 进程入口
|   |-- entrypoints/task_worker.py # 科研任务、报告导出、资料解析持久队列 Worker
|   |-- entrypoints/routes.py      # 显式控制器清单与路由注册
|   |-- system/                    # 认证、RBAC和系统管理能力
|   |   |-- api/login_controller.py # 登录/注册 API
|   |   |-- api/captcha_controller.py # 图片验证码 API
|   |   |-- api/dictionary_controller.py # 字典管理 API
|   |   |-- schemas/           # 登录、菜单、用户、角色、配置、字典和当前用户契约
|   |   |-- models/                # 用户、角色、菜单、配置和字典 ORM
|   |   |-- repositories/          # 认证、用户、角色、菜单、配置和字典查询
|   |   `-- services/              # 认证、用户、角色、菜单、配置和字典用例
|   |-- infrastructure/            # 跨业务技术设施和运维能力
|   |   |-- api/cache_controller.py # Redis缓存监控 API
|   |   |-- api/server_controller.py # 主机与进程监控 API
|   |   |-- api/transport_crypto_controller.py # 传输加密配置与监控 API
|   |   |-- api/log_controller.py   # 操作日志与登录日志 API
|   |   |-- api/job_controller.py   # 定时任务与调度日志 API
|   |   |-- api/file_controller.py  # 通用文件上传与下载 API
|   |   |-- api/online_controller.py # Redis在线会话监控 API
|   |   |-- schemas/cache.py   # 缓存监控 API 契约
|   |   |-- schemas/server.py  # 服务器监控 API 契约
|   |   |-- schemas/transport_crypto.py # 传输加密 API 契约
|   |   |-- schemas/log.py     # 审计日志 API 契约
|   |   |-- schemas/jobs.py    # 定时任务与调度日志契约
|   |   |-- schemas/files.py   # 文件传输 API 契约
|   |   |-- schemas/online.py  # 在线会话 API 契约
|   |   |-- services/cache.py      # Redis缓存监控服务
|   |   |-- services/server.py     # 主机与进程监控服务
|   |   |-- services/transport_crypto.py # 传输加密 API 服务
|   |   |-- models/audit.py        # 登录与操作日志 ORM
|   |   |-- models/jobs.py         # 定时任务与调度日志 ORM
|   |   |-- repositories/audit_logs.py # 审计日志数据访问
|   |   |-- repositories/jobs.py   # 定时任务数据访问
|   |   |-- repositories/job_logs.py # 调度日志数据访问
|   |   |-- services/log.py        # 日志查询、队列与聚合服务
|   |   |-- services/jobs.py       # 定时任务管理与执行服务
|   |   |-- services/job_logs.py   # 调度日志查询与导出服务
|   |   |-- services/file_storage.py # 受控文件存储与内容校验
|   |   |-- services/file_transfer.py # 通用文件上传、下载与路径校验
|   |   `-- services/online.py     # 在线会话查询与强制下线
|   |-- intelligence/              # 科技情报业务包
|   |   |-- services/              # 数据处理、采集、交接、Prompt、模板等服务
|   |   |-- api/                  # 情报 API 控制器和 DTO
|   |   |-- integrations/          # InsightHub 等外部处理系统适配器
|   |   |-- tasks/                 # 来源定时采集、外部回执轮询等后台任务
|   |   |-- repositories/          # 情报业务数据访问层
|   |   |-- models/                # 按业务领域拆分的 SQLAlchemy 持久化模型
|   |   |   |-- collection.py      # 数据源与采集运行
|   |   |   |-- configuration.py   # Prompt、模型路由与模板
|   |   |   |-- content.py         # 资讯、论文与审核事件
|   |   |   |-- governance.py      # 质量问题与重复内容治理
|   |   |   `-- pipeline_models.py # 情报域模型聚合导出
|   |   `-- api/                   # Pydantic API DTO
|   |-- library/                   # 上传资料解析与受控访问
|   |   |-- services/materials.py  # 资料文件解析与路径安全
|   |   `-- tasks/material_parse_scheduler.py # 资料解析持久队列
|   |-- research/                  # 科研工作区、任务和成果
|   |   `-- services/              # 工作区、任务、证据、报告和后台执行
|   `-- bootstrap.py               # FastAPI 应用工厂、生命周期和基础设施组装
|-- server.py                      # 旧应用工厂兼容导入
|-- config/                        # 环境、数据库、Redis、调度器配置
|-- common/                        # HTTP契约/响应/上下文/依赖、接口契约、运行常量、切面、注解
|-- middlewares/                   # CORS、GZip、上下文、传输加密、响应头等中间件
|-- exceptions/                    # 全局异常定义和处理
|-- utils/                         # 响应、日志、文件、加密、Excel、服务信息等工具
|-- cli/                           # ruoyi 命令行工具
|-- sql/                           # PostgreSQL 初始化 SQL（MySQL 脚本仅作迁移参考）
|-- alembic/                       # 数据库迁移
|-- tests/                         # 后端与 CLI 测试
|-- docs/                          # 后端专项文档
`-- vf_admin/                      # 上传、下载和导出等运行期文件目录
```

Compose 环境将职责拆成两个进程：`ruoyi-backend-pg` 只提供 HTTP API 和系统级定时任务，
`pipesight-task-worker` 独立运行数据源 Cron、InsightHub 回执轮询，并扫描 `generation_tasks`、`report_exports` 与 `knowledge_files` 资料解析队列。
两者通过 PostgreSQL 租约、心跳和条件状态更新协作；API 侧使用
`PIPELINE_TASK_SCHEDULER_ENABLED=false`，避免 API 与 Worker 重复运行采集、交接和持久队列恢复。Compose 由 `pipesight-db-migrate` 在 API/Worker 前执行 Alembic 迁移；采集来源和交接运行通过 PostgreSQL 租约做跨进程防重。

后端请求流：

```text
frontend axios
  -> Vite/Nginx /dev-api
  -> app.entrypoints.api / app.bootstrap.create_app()
  -> middlewares
  -> exceptions handlers
  -> app.entrypoints.routes 按显式清单注册控制器
  -> controller
  -> service
  -> dao / db / redis / external service
  -> ResponseUtil / DataResponseModel

第一条纵向迁移样板是情报采集链路：数据处理实现位于
`app.intelligence.services.data_processing`，公开来源采集实现位于
`app.intelligence.services.collection`，Prompt 版本管理位于
`app.intelligence.services.prompts`，模板版本管理位于
`app.intelligence.services.templates`，共享数据访问位于
`app.intelligence.repositories.pipeline_repository`。
数据源配置和采集运行状态位于 `app.intelligence.services.sources`，InsightHub 交接编排位于 `app.intelligence.services.handoff`，外部 PostgreSQL 适配器位于 `app.intelligence.integrations.insighthub`，定时采集和回执轮询位于 `app.intelligence.tasks`，独立 Worker 的编排入口位于 `app.intelligence.tasks.operational_scheduler`；采集来源租约和交接运行租约由 `PipelineDao` 统一维护。情报应用编排位于 `app.intelligence.services.application.IntelligenceApplicationService`，HTTP 控制器位于 `app.intelligence.api.controller`。资料 API 位于 `app.library.api.controller`；资料解析和路径安全位于 `app.library.services.materials.MaterialFileService`，资料查询、权限、事务和文件生命周期位于同文件的 `MaterialService`，API 应用策略组合位于 `MaterialApiService`；资料解析队列位于 `app.library.tasks.material_parse_scheduler`，由 `pipesight-task-worker` 统一执行。资料篮和科研 API 位于 `app.research.api.controller`，应用编排位于 `app.research.services.application.ResearchApplicationService`，任务状态位于 `app.research.services.jobs`，证据和报告编排分别位于 `app.research.services.evidence`、`app.research.services.report_builder`，后台执行用例位于 `app.research.services.execution`。
```

## 3. InsightHub Worker 结构

InsightHub 是同仓库内与 PipeSight 共用 PostgreSQL 的处理 Worker，作为根 Compose 的默认服务运行；它保持独立进程以隔离长耗时处理。源码已经归入后端的 `app` 包，根 Compose 不再从独立 `insighthub` 包构建：

```text
backend/
|-- src/app/intelligence/processing/
|   |-- config/                  # Worker 配置
|   |-- db/                      # PostgreSQL、pgvector、Redis 和兼容适配
|   |-- domain/                  # 领域处理器和动态领域加载
|   |-- email_support/           # 告警与邮件中转
|   |-- models/                  # 新闻和处理结果模型
|   |-- processors/              # 处理流程编排
|   |-- prompts/                 # 各领域 Prompt
|   |-- runtime/                 # PostgreSQL/Kafka 消费运行时
|   |-- services/                # Kafka、领域配置和下游发布
|   |-- supported_text/          # 停用词和领域文本
|   `-- utils/                   # 健康检查、时间、日志和通用工具
|-- Dockerfile.processing.pg    # 统一后端依赖的 Worker 镜像
|-- tests/architecture/         # 包清单、资源和迁移边界测试
`-- tests/intelligence/processing/ # Worker 单元、集成和端到端测试

logs/insighthub/                 # Worker 运行日志，不作为源码
```

InsightHub 的历史交接资料统一归档在 `docs/handover/`；当前不再保留独立的 `insighthub/` Python 项目目录。

## 4. 后端模块边界

| 模块 | 说明 |
| --- | --- |
| `app.intelligence/`、`app.library/`、`app.research/` | 管网业务的实际 API、服务、模型、Repository、任务和资料/科研能力 |
| `app.system/` | 认证、RBAC、配置、字典、菜单、用户、角色及其 API、Service、Repository 和 ORM |
| `app.infrastructure/` | Redis在线会话、缓存、服务器运行信息、传输加密 API、审计日志、任务调度、受控文件存储和通用文件传输等跨业务技术设施；相关监控 API、日志聚合、任务调度管理和通用文件路由已迁入；不承载用户或情报业务规则 |
| 已退役的代码生成器 | 数据库迁移已移除 `gen_table`、`gen_table_column` 及 `/tool/gen` 路由；不再保留前后端入口或兼容实现 |
| `common/` | 项目通用基础设施，包括 `common/http` 下的 HTTP 契约/响应/上下文/依赖/路由、`common/constants.py` 运行常量、`common/enums/` 技术枚举、权限切面、缓存/限流/日志注解 |
| `config/` | `.env.*` 配置加载、数据库连接、Redis 连接、APScheduler 调度器 |
| `cli/` | `ruoyi` 命令入口，覆盖应用、数据库、缓存、任务、运维和向导能力 |

## 5. 管网业务模块

管网业务后端集中在 `backend/src/app/`，按业务边界拆分：

```text
backend/src/app/
|-- intelligence/
|   |-- api/                       # 情报、来源、采集和模板/Prompt接口
|   |-- services/                  # 采集、处理、筛选、交接和应用编排
|   |-- repositories/              # 情报业务数据访问
|   |-- models/                    # 情报持久化模型
|   |-- integrations/              # InsightHub PostgreSQL适配
|   `-- tasks/                     # 采集和交接后台任务
|-- library/
|   |-- api/                       # 资料查询、上传、下载和解析接口
|   `-- services/                  # 文件解析、授权和生命周期
|-- research/
|   |-- api/                       # 资料篮、科研任务和报告接口
|   `-- services/                  # 任务、证据、报告、版本和后台执行
`-- entrypoints/                  # API入口与显式路由清单
```

旧的静态 `PipelineService` 已删除，科研门面位于 `app.research.services.facade`，避免把内存样例误认为真实数据。

接口与前端调用关系：

| 功能 | 前端 API | HTTP 路径 | 后端入口 |
| --- | --- | --- | --- |
| 工作台概览 | `getPipelineDashboard` | `GET /pipeline/dashboard` | `app.intelligence.api.pipeline_controller` |
| 情报列表 | `listPipelineIntelligence` | `GET /pipeline/intelligence/list` | `app.intelligence.api.controller` |
| 情报详情 | `getPipelineIntelligenceDetail` | `GET /pipeline/intelligence/{itemId}` | `app.intelligence.api.controller` |
| 数据源列表 | `listPipelineSources` | `GET /pipeline/sources` | `app.intelligence.api.controller` |
| 采集任务列表 | `listPipelineTasks` | `GET /pipeline/tasks` | `app.intelligence.api.controller` |
| 手动运行任务 | `runPipelineTask` | `POST /pipeline/tasks/{taskId}/run` | `app.intelligence.api.controller` |
| 报告列表 | `listPipelineReports` | `GET /pipeline/reports` | `app.research.api.controller` |
| 报告导出 | `exportPipelineReport` | `GET /pipeline/reports/{reportId}/export` | `app.research.api.controller` |
| 内部资料 | `listPipelineKnowledgeDocuments` | `GET /pipeline/knowledge/documents` | `app.library.api.controller` |

管网业务前端集中在：

```text
frontend/src/api/pipeline/
`-- intelligence.js                # 管网业务 API 封装

frontend/src/views/pipeline/
|-- dashboard/index.vue             # 管理端工作台
|-- intelligence/index.vue          # 情报检索
|-- intelligence/detail.vue         # 情报详情
|-- source/index.vue                # 数据源管理
|-- task/index.vue                  # 采集任务监控
|-- report/index.vue                # 报告管理
`-- knowledge/index.vue            # 内部资料管理

frontend/src/views/portal/
|-- index.vue                       # 用户端门户
`-- components/NewsSidebar.vue     # 门户侧栏组件
```


## 6. 前端结构

前端是 Vue 3 + Vite + Element Plus + Pinia + Vue Router。`frontend/src/main.js` 创建应用并挂载路由、状态、插件、权限指令和全局组件；`frontend/src/permission.js` 负责登录态、门户访问和动态路由加载。

```text
frontend/
|-- index.html
|-- vite.config.js                 # Vite、别名、代理和构建配置
|-- package.json                   # npm 脚本和依赖
|-- Dockerfile
|-- bin/                           # Nginx 配置
|-- vite/                          # Vite 插件配置
|-- public/                        # 静态资源
|-- tests/                         # 前端测试
`-- src/
    |-- main.js                    # Vue 应用入口
    |-- App.vue                    # 根组件
    |-- permission.js              # 路由守卫和权限加载
    |-- api/                       # API 封装
    |-- assets/                    # 样式、图标、图片等资源
    |-- components/                # 全局/通用组件
    |-- directive/                 # 权限等自定义指令
    |-- layout/                    # 后台布局
    |-- plugins/                   # 全局插件
    |-- router/                    # 静态路由和动态路由声明
    |-- store/                     # Pinia 状态模块
    |-- utils/                     # request、auth、权限、加密、工具函数
    `-- views/                     # 页面
```

主要前端目录职责：

| 目录 | 说明 |
| --- | --- |
| `src/router/` | 静态路由包含 `/portal`、`/login`、错误页和用户中心；后台业务菜单主要由后端菜单数据动态生成 |
| `src/store/` | Pinia 状态，包含 `user`、`permission`、`settings`、`dict`、`tagsView`、`app` |
| `src/utils/request.js` | Axios 实例，统一 baseURL、Token、重复提交保护、传输层加解密、错误处理和下载 |
| `src/api/` | 按业务域封装 API，包括 `pipeline`、`system`、`monitor`、`ai`、`tool` |
| `src/views/pipeline/` | 管网管理端页面 |
| `src/views/portal/` | 管网用户端门户页面 |
| `src/views/system/`、`src/views/monitor/` | 后台管理与监控页面 |

## 7. 配置与部署

后端配置：

| 文件 | 用途 |
| --- | --- |
| `backend/.env.dev` | 本地开发默认配置 |
| `backend/.env.dockermy` | 历史 Docker + MySQL 配置，仅用于迁移参考 |
| `backend/.env.dockerpg` | Docker + PostgreSQL 配置 |
| `backend/.env.prod` | 生产配置 |

后端通过 `--env` 或 `APP_ENV` 选择环境文件，默认加载 `.env.dev`。服务默认监听 `9099`，`app_root_path` 为 `/dev-api`。

前端配置：

| 文件 | 用途 |
| --- | --- |
| `frontend/.env.development` | 本地开发 |
| `frontend/.env.docker` | Docker 部署 |
| `frontend/.env.production` | 生产构建 |
| `frontend/.env.staging` | 预发构建 |

`vite.config.js` 中 `@` 指向 `frontend/src`，开发服务默认端口为 `80`，`/dev-api` 代理到 `http://127.0.0.1:9099`。

容器部署：

| 文件 | 数据库 | 前端端口 | 后端端口 | 数据库端口 | Redis 端口 |
| --- | --- | --- | --- | --- | --- |
| `docker-compose.pg.yml` | PostgreSQL 16 + pgvector | `12580` | `19099` | `15432` | `16379` |

数据库初始化脚本在 `backend/sql/`，迁移目录在 `backend/alembic/`。

## 8. 文档与设计资料

```text
docs/
|-- architecture/
|-- requirements/
|-- reference/
|-- plans/
|   |-- 2026-07-13-pipeline-intelligence-platform-design.md
|   |-- 2026-07-13-pipeline-intelligence-platform-implementation.md
|   |-- 2026-07-13-pipeline-menu-seed.sql
|   |-- 2026-07-13-pipeline-mvp-completion-plan.md
|   |-- 2026-07-13-pipeline-portal-ui.md
|   |-- 2026-07-14-pipeline-user-portal-consolidation.md
|   |-- 2026-07-15-pipesight-development-flow-and-resume-state.md
|   `-- 2026-07-23-pipeline-requirements-list.md
|-- handover/
|-- reports/
|   `-- biweekly/
|-- README.md
`-- project-structure.md
```

具体归类和入口见 `docs/README.md`。`docs/project-structure.md` 用于维护当前代码结构，不替代业务设计文档。

## 9. 生成目录与不建议纳入结构说明的内容

以下目录或文件主要是依赖、构建产物、缓存、运行日志或本地输出，整理结构时通常不作为源码模块：

| 路径 | 类型 |
| --- | --- |
| `frontend/node_modules/` | npm 依赖 |
| `frontend/dist/` | 前端构建产物 |
| `frontend/test-results/` | 前端测试结果 |
| `frontend/.vite-port80.log`、`frontend/vite-dev*.log` | 前端开发日志 |
| `backend/.venv/` | Python 虚拟环境 |
| `backend/.pytest_cache/` | Pytest 缓存 |
| `backend/__pycache__/`、各级 `__pycache__/` | Python 字节码缓存 |
| `backend/logs/` | 后端运行日志 |
| `backend/build/` | 后端构建产物 |
| `backend/ruoyi_fastapi_backend_cli.egg-info/` | Python 包元数据 |
| `backend/vf_admin/` | 上传、下载和导出等运行期文件 |
| `logs/insighthub/` | InsightHub Worker 运行日志 |

## 10. 后续新增模块建议

新增后端业务模块时，优先保持现有分层：

```text
backend/module_xxx/
|-- controller/xxx_controller.py
|-- service/xxx_service.py
|-- dao/xxx_dao.py
`-- entity/
    |-- do/xxx_do.py
    `-- vo/xxx_vo.py
```

新增前端业务模块时，优先保持 API 与页面分离：

```text
frontend/src/api/xxx/
`-- xxx.js

frontend/src/views/xxx/
`-- index.vue
```

如果需要出现在后台菜单中，补充菜单数据或种子 SQL，并确保 `component` 字段与 `frontend/src/views/` 下的页面路径一致。管网用户端能力优先放在 `frontend/src/views/portal/`，后台管理能力优先放在 `frontend/src/views/pipeline/`。
