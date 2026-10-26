# 国家管网科技情报与科研辅助平台

面向国家管网科技创新的"科技情报与科研辅助平台"，基于 **RuoYi-Vue3-FastAPI** 全栈底座构建，提供情报采集、智能检索、资料管理与科研报告生成等核心能力。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3.5 + Vite 6 + Element Plus 2 + Pinia + Vue Router 4 |
| **后端** | FastAPI 0.128 + SQLAlchemy 2.0 (async) + Pydantic v2 |
| **数据库** | PostgreSQL 16 + pgvector（默认运行时） |
| **缓存** | Redis 7 |
| **AI / LLM** | 多模型接入（OpenAI、Anthropic、Gemini、Groq、Ollama、LiteLLM 等） |
| **容器化** | Docker + Docker Compose |
| **构建工具** | Vite 6 + Rollup |

## 项目结构

```
PipeSight/
├── frontend/                    # Vue 3 前端源码
│   ├── src/
│   │   ├── api/                 # API 接口封装
│   │   │   ├── pipeline/        # 管网情报业务接口
│   │   │   ├── system/          # 系统管理接口
│   │   │   ├── monitor/         # 监控管理接口
│   │   │   └── ai/              # 通用 AI 对话与模型接口
│   │   ├── views/
│   │   │   ├── pipeline/        # 管网情报页面
│   │   │   │   ├── dashboard/   # 情报工作台
│   │   │   │   ├── intelligence/# 情报检索与详情
│   │   │   │   ├── source/      # 数据源管理
│   │   │   │   ├── task/        # 采集任务管理
│   │   │   │   ├── report/      # 报告管理
│   │   │   │   └── knowledge/   # 知识库
│   │   │   ├── system/          # 系统管理（用户/角色/菜单/字典）
│   │   │   ├── monitor/         # 监控管理（在线用户/操作日志/定时任务）
│   │   │   ├── ai/              # 通用 AI 对话与模型配置
│   │   │   └── dashboard/       # 首页工作台
│   │   ├── layout/              # 页面布局组件
│   │   ├── router/              # 动态路由
│   │   ├── store/               # Pinia 状态管理
│   │   ├── components/          # 公共组件
│   │   └── utils/               # 工具函数
│   ├── bin/                     # Nginx 配置文件
│   ├── vite/                    # Vite 插件配置
│   ├── Dockerfile               # 前端 Docker 构建文件
├── backend/                     # FastAPI 后端源码
│   ├── pyproject.toml           # 依赖、打包和命令入口
│   ├── src/app/                 # 唯一正式 Python 应用包
│   │   ├── entrypoints/         # API、任务 Worker 入口
│   │   ├── system/              # 认证、RBAC、系统管理
│   │   ├── intelligence/        # 情报、采集、处理、AI 编排
│   │   │   └── processing/      # InsightHub 数据处理 Worker
│   │   ├── library/             # 资料库与文件访问
│   │   ├── research/            # 科研任务、证据与成果
│   │   ├── health/              # 健康检查
│   │   └── infrastructure/      # 监控、模型、文件、日志等技术设施
│   ├── common/                  # HTTP、依赖、注解等跨切面适配
│   ├── config/                  # 配置、数据库模型发现和调度设置
│   ├── middlewares/             # 中间件
│   ├── exceptions/              # 全局异常处理
│   ├── sub_applications/        # 静态文件等应用挂载适配
│   ├── sql/                     # 数据库初始化 SQL
│   ├── tests/                   # 测试用例（含架构测试）
│   ├── alembic/                 # 数据库迁移
│   ├── cli/                     # CLI 命令行工具
│   ├── scripts/                 # 一次性导入、回填和运维脚本
│   ├── server.py                # 兼容启动入口，应用工厂在 app.bootstrap
│   ├── Dockerfile.my            # MySQL 版 Docker 构建
│   └── Dockerfile.pg            # PostgreSQL 版 Docker 构建
│
├── docs/
│   ├── architecture/           # 架构、数据库和环境说明
│   ├── requirements/           # 需求、原型和客户确认资料
│   ├── reference/              # 模板与示例
│   ├── plans/                  # 设计文档与实施计划
│   ├── handover/               # 交接与数据库资料
│   ├── reports/                # 进度和双周汇报
│   └── project-structure.md    # 目录结构说明
│
├── docker-compose.my.yml        # Legacy Docker Compose（MySQL，仅迁移参考）
└── docker-compose.pg.yml        # 默认 Docker Compose（PostgreSQL + pgvector）
```

## 业务功能

### 当前范围 (MVP)

| 功能模块 | 说明 |
|----------|------|
| **情报工作台** | 有效资讯统计、采集状态、热点主题、待审核报告概览 |
| **情报检索** | 按新闻/公众号/论文类别查看和检索管网相关内容，支持关键词搜索和分页 |
| **数据源管理** | 查看采集源名称、类型、采集频率、运行状态和成功率 |
| **采集任务** | 查看任务列表、运行状态、进度，支持手动触发采集任务 |
| **报告管理** | 查看日报/周报/技术路线报告草稿，支持导出 Markdown、DOCX、PDF |
| **内部资料** | 上传、解析、授权访问并将研究资料加入资料篮 |
| **科研任务** | 从资料篮创建任务，执行资料处理、结果审核、重试/驳回并导出成果 |
| **数据处理** | 采集结果进入 PostgreSQL `news` schema，由 InsightHub Worker 执行去重、过滤、分类、评分和回写 |
| **模型与 Prompt** | 管理 `data-filter` 等场景的 Prompt、模型和路由；实际外部来源处理前必须具备已发布配置 |
| **认证授权** | 基于 JWT 的登录认证、角色-菜单-按钮权限控制、动态路由 |
| **系统管理** | 用户/角色/菜单/字典/参数管理；不包含部门、岗位和通知公告模块 |
| **监控管理** | 在线用户、操作日志、登录日志、定时任务、服务监控、缓存监控 |
| **AI 对话** | 多模型接入的 AI 对话助手界面 |

### 当前边界与后续工作

- 本仓库提供采集任务、PostgreSQL 持久化、交接队列和处理 Worker；具体爬虫脚本、来源授权和生产级来源接入仍需按来源逐一验收。
- 当前默认检索使用 PostgreSQL 查询能力；Elasticsearch、Milvus 等外部基础设施不是默认运行时，不能在未完成数据一致性、权限和运维验收前作为已交付能力宣称。
- MinIO/S3、Embedding 回填和语义检索属于可选能力，只有启用对应 Compose profile、密钥和验收数据后才生效。
- 生产化仍需补齐备份恢复、容量压测、网络/模型/Redis/数据库故障演练和告警接入。
- 证据词严格过滤依赖领域规则文件（如 `*_proofwords.txt`）；当前仓库未内置业务词表，未提供词表时不能把严格证据词过滤视为已启用。
- 知识问答功能、Kafka Dashboard 和独立 `insighthub/` 运行目录不属于当前交付范围；InsightHub Worker 已并入 `backend/src/app/intelligence/processing/`。
- 后端不再维护全局 `backend/utils/` 或 `module_*` 业务包；新的公共能力按职责进入 `common/`、`app.infrastructure` 或所属业务模块。

## 快速开始

### 环境要求

- **Node.js** >= 18
- **Python** >= 3.10
- **uv**（后端虚拟环境与依赖安装）
- **PostgreSQL** 16 + **pgvector**（推荐使用 Docker Compose）
- **Redis** >= 6
- **Docker Desktop**（推荐；提供 PostgreSQL、pgvector 和 Redis）

### 1. 一键启动（推荐）

在 Windows PowerShell 或 CMD 中执行：

```powershell
cd PipeSight
.\start-dev.cmd
```

脚本会依次完成以下工作：

1. 检查 `uv`、Node.js 与 npm；首次运行时自动创建 `backend/.venv` 并安装 PostgreSQL 专用依赖 `requirements-pg.txt`，同时按需执行 `npm ci`。
2. 优先使用本机 PostgreSQL 和 Redis；本机基础设施没有同时就绪时，使用根目录 `docker-compose.pg.yml` 启动统一的 PostgreSQL + pgvector + Redis。
3. 数据库不存在时自动创建；若缺少若依基础表则导入 `ruoyi-fastapi-pg.sql`，并幂等补齐 PostgreSQL 版管网业务表与 InsightHub `news` schema。
4. 检查 `9099`/`5173` 端口。仅当监听进程能够明确识别为当前 PipeSight 项目时才会停止旧进程；不会直接终止无关程序。若端口被无法确认归属的旧服务占用，会自动为本次前端会话选择下一个可用端口。
5. 使用 uv 启动后端、使用 Vite 启动前端，并等待健康检查通过后输出访问地址。

启动成功后访问：

- 用户端：脚本最后输出的 `Frontend` 地址（默认 `http://127.0.0.1:5173/portal`）
- 后端接口文档：脚本最后输出的 `Backend` 地址（默认 `http://127.0.0.1:9099/docs`）
- 启动日志：项目根目录 `.runtime\pipesight-dev\`

停止本次启动的前后端（不会停止 PostgreSQL/Redis）：

```powershell
.\stop-dev.cmd
```

常用启动选项：

```powershell
# 强制使用 Docker 中的 PostgreSQL + pgvector 和 Redis
.\start-dev.cmd -Infrastructure Docker

# 强制使用 backend/.env.dev 指向的本地 PostgreSQL 和 Redis
.\start-dev.cmd -Infrastructure Local

# 禁止自动安装依赖（依赖缺失或过期时直接报错）
.\start-dev.cmd -SkipInstall

# requirements-pg.txt 或 package-lock.json 变更后强制重装
.\start-dev.cmd -ForceDependencyInstall
```

### 2. 手动启动基础设施

#### 方式 A：使用本地安装的服务

确保 PostgreSQL 和 Redis 已在本地运行，然后配置 `backend/.env.dev` 中的连接信息（默认配置见下文）。

#### 方式 B：使用 Docker 启动服务

```bash
# PostgreSQL + pgvector 版本
docker compose -p pipesight-pg -f docker-compose.pg.yml up -d ruoyi-pg ruoyi-redis
```

> Docker 启动后，PostgreSQL 端口映射为 `15432`，Redis 端口映射为 `16379`。请确保 `backend/.env.dev` 中的数据库连接信息与 Docker 端口一致。

新建 Docker 数据卷时，Compose 会按顺序自动导入：

- `10-ruoyi-fastapi-pg.sql`：若依基础表和种子数据
- `20-pipeline-domain-pg.sql`：知识文件与切块、资料篮、模板与 Prompt、生成任务、报告版本、引用和导出表
- `30-pipeline-domain-enhancement-pg.sql`：数据来源、采集运行、原始记录、资讯、论文和分类标签表

Docker 已存在旧数据卷时，入口初始化脚本不会再次运行；执行 `.\start-dev.cmd -Infrastructure Docker` 会额外执行一次幂等的管网业务表初始化。

### 3. 手动启动后端

```powershell
cd backend

# 创建 uv 虚拟环境并安装完整运行依赖
uv venv
uv pip install -r requirements-pg.txt

# 设置编码并启动
$env:PYTHONIOENCODING='utf-8'
uv run --project . --no-sync python -m app.entrypoints.api --env=dev
```

后端默认运行在 `http://127.0.0.1:9099`，Swagger 文档地址为 `http://127.0.0.1:9099/docs`。

> `backend/pyproject.toml` 现在同时声明可安装的 `app` 包、API 入口和锁定运行依赖；`requirements-pg.txt` 仍作为 Docker/传统环境的兼容安装清单保留。全新环境推荐在 `backend/` 下执行 `uv sync --no-dev`，或直接使用根目录的一键启动脚本。

开发环境需要页面有可演示数据时，可幂等执行一次最小种子脚本（不会写入生产迁移）：

```powershell
cd backend
uv run --no-sync python scripts/seed_dev_data.py --env=dev
```

初始化真实公开来源并执行一次采集：

```bash
cd backend
uv run --no-sync python scripts/bootstrap_real_pipeline.py
```

该脚本默认保留管理员对内置来源的启用/停用状态，并逐个来源执行、逐个报告失败。只有确认需要恢复已停用内置来源时，才显式增加 `--reactivate`。外部来源执行前还必须在管理端完成已发布 `data-filter` Prompt、可用模型和场景路由配置。

如果本地 `.env` 已配置 `INSIGHTHUB_LLM_MODEL`、`INSIGHTHUB_LLM_BASE_URL` 和 `INSIGHTHUB_LLM_API_KEYS`，可以将 DeepSeek 安全注册到 PostgreSQL 的管理模型表，并启用 `data-filter` 路由：

```bash
cd backend
DB_HOST=127.0.0.1 DB_PORT=15432 DB_USERNAME=postgres DB_PASSWORD=root DB_DATABASE=ruoyi-fastapi \
  uv run --no-sync python scripts/bootstrap_deepseek_route.py --env=dockerpg
```

脚本只创建缺失的模型和路由，API Key 会按平台密钥格式加密保存且不会打印；已有管理端路由不会被脚本覆盖。执行后仍可在“模型与 Prompt → 场景路由”中查看和维护配置。

### 4. 手动启动前端

```powershell
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

前端开发服务器运行在 `http://127.0.0.1:5173/`，并通过 Vite proxy 将 `/dev-api` 代理到后端 `http://127.0.0.1:9099`。

## 项目级验证

PipeSight API、任务 Worker 和 InsightHub 处理 Worker 统一使用 `backend/` 的 Python 项目环境；InsightHub 的测试已经归入 `backend/tests/intelligence/processing/`，不能再切换到已移除的独立 `insighthub/` 目录。建议按项目级脚本执行：

```bash
# 一键执行全部本地验证
./scripts/verify_project.sh

# 也可以按组件分别执行：

# PipeSight 后端
cd backend
uv run pytest tests -q

# InsightHub Worker（已包含在 backend/tests/intelligence/processing/）
cd ../backend
uv run pytest tests/intelligence/processing -q

# 前端行为测试
cd ../frontend
npm test

# 前端生产构建检查
npm run check
```

后端测试覆盖 API、数据访问、权限、任务和报告逻辑；InsightHub 测试覆盖处理器、Kafka/Redis 适配、数据库边界和端到端模拟流程。需要真实数据库、Kafka 或外部模型的用例会明确标记为集成/跳过，不以单元测试通过替代运行态验收。

### 5. 初始化菜单数据

首次启动后，需要导入管网情报菜单种子数据：

```sql
-- 执行 docs/plans/2026-07-13-pipeline-menu-seed.sql
```

该 SQL 会向数据库中插入管网情报相关的目录和菜单项，包含以下页面路径：

- `pipeline/dashboard/index` — 情报工作台
- `pipeline/intelligence/index` — 情报检索
- `pipeline/intelligence/detail` — 情报详情
- `pipeline/source/index` — 数据源管理
- `pipeline/task/index` — 采集任务
- `pipeline/report/index` — 报告管理
- `pipeline/knowledge/index` — 内部资料管理

### 6. 登录

| 账号 | 密码 |
|------|------|
| `admin` | `admin123` |
| `niangao` | `admin123` |

> 新建用户的默认初始密码为 `123456`。

## 配置说明

### 后端配置 (`backend/.env.dev`)

```ini
# 数据库（统一使用 PostgreSQL）
DB_TYPE = 'postgresql'
DB_HOST = '127.0.0.1'
# 本机直连 PostgreSQL 使用 5432；根 Compose 对宿主机映射为 15432
DB_PORT = 5432
DB_USERNAME = 'postgres'
DB_PASSWORD = 'root'
DB_DATABASE = 'ruoyi-fastapi'

# Redis
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379                 # Docker: 16379
REDIS_DATABASE = 2

# JWT
JWT_SECRET_KEY = '<your-secret-key>'
JWT_EXPIRE_MINUTES = 1440
```

> 多环境配置文件：`.env.dev`（开发，默认 PostgreSQL）、`.env.dockermy`（旧版 Docker+MySQL，仅迁移参考）、`.env.dockerpg`（Docker+PostgreSQL）、`.env.prod`（生产）。线上和本地默认运行链路均使用 PostgreSQL；MySQL 配置仅保留用于历史数据迁移。

### 前端配置

前端通过 `.env.*` 文件配置不同环境的 API 地址：

| 文件 | 环境 |
|------|------|
| `.env.development` | 本地开发（代理到 `http://127.0.0.1:9099`） |
| `.env.docker` | Docker 部署 |
| `.env.production` | 生产构建 |
| `.env.staging` | 预发布环境 |

## Docker 部署

### 全栈 Docker 部署（PostgreSQL + pgvector）

```bash
docker compose -p pipesight-pg -f docker-compose.pg.yml up -d --build
```

| 服务 | 端口 |
|------|------|
| 前端 (Nginx) | `12580` |
| 后端 (FastAPI) | `19099` |
| PostgreSQL + pgvector | `15432` |
| Redis | `16379` |

## 生产构建

### 前端

```powershell
cd frontend
npm run build:prod
```

构建产物输出到 `frontend/dist/`，可直接部署至 Nginx 或其他 Web 服务器。

### 后端

```powershell
cd backend
uv venv
uv pip install -r requirements-pg.txt
uv run --project . --no-sync python -m app.entrypoints.api --env=prod
```

生产环境建议配合 Gunicorn + Uvicorn workers 运行：

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker 'app.bootstrap:create_app()'
```

## API 文档

后端启动后访问：

- **Swagger UI**: `http://127.0.0.1:9099/docs`
- **ReDoc**: `http://127.0.0.1:9099/redoc`

## 管网情报 API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/pipeline/dashboard` | 获取情报工作台数据 |
| `GET` | `/pipeline/intelligence/list` | 查询情报列表（支持分类/关键词/来源过滤） |
| `GET` | `/pipeline/intelligence/{id}` | 获取情报详情 |
| `GET` | `/pipeline/sources` | 查询数据源列表 |
| `GET` | `/pipeline/tasks` | 查询采集任务列表 |
| `POST` | `/pipeline/tasks/{id}/run` | 手动运行采集任务 |
| `GET` | `/pipeline/reports` | 查询报告草稿列表 |
| `GET` | `/pipeline/reports/{id}/export` | 导出报告（Markdown/DOCX/PDF，按格式参数选择） |
| `GET` | `/pipeline/knowledge/documents` | 查询内部资料 |
| `POST` | `/pipeline/knowledge/documents` | 上传内部资料 |
| `POST` | `/pipeline/reviews/{content_type}/{content_id}/reprocess` | 重新处理被驳回或达到重试上限的资讯 |
| `POST` | `/pipeline/tasks/runs/{run_id}/handoff` | 将采集结果交接给 InsightHub Worker |
| `POST` | `/pipeline/tasks/runs/{run_id}/handoff/sync` | 同步交接处理结果 |

## 数据库迁移 (Alembic)

```bash
cd backend

# 生成迁移文件
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

本项目已提供首个管网领域增强迁移：

```powershell
cd backend
uv run alembic upgrade head
```

设计说明见 [PipeSight 全系统数据库设计](docs/plans/2026-08-14-full-system-database-design.md)。最终结构共 23 张表：平台 14 张、采集与内容 4 张、知识与报告 5 张。部门、岗位、通知公告、代码生成持久化及未落地的预建业务表均不进入新库；数据权限仅保留“全部数据 / 仅本人”。历史未知试验表不会被自动删除，曾预建的业务表只有在空表时才由迁移清理。

InsightHub 已作为同仓库子系统归入 [`backend/src/app/intelligence/processing/`](backend/src/app/intelligence/processing/)：新闻处理 Worker 源码、测试、PostgreSQL 设计和 pgvector 结构统一由后端项目交付。仓库不再把独立 `insighthub/` 目录作为运行时入口。PipeSight 与 InsightHub 共用根 Compose 中的 `ruoyi-pg` PostgreSQL 实例，PipeSight 使用 `public` schema，InsightHub 使用 `news` schema，不再依赖外部数据库。

默认启动会创建 PostgreSQL + pgvector，并初始化 `ruoyi-fastapi.news` schema；需要真实新闻处理 Worker 时，先配置 LLM/Embedding 密钥，再运行：

```bash
docker compose -p pipesight-pg -f docker-compose.pg.yml up -d --build
```

Compose 会先运行一次性的 `pipesight-db-migrate` 完成 `alembic upgrade head`，成功后才启动 PipeSight API、`pipesight-task-worker` 和 `insighthub-worker`。其中 `pipesight-task-worker` 负责数据源采集、交接回执、科研生成、报告导出和资料解析持久队列；`insighthub-worker` 负责从 `news` schema 领取交接资讯，执行领域过滤/分类/评分并把处理结果写回 PostgreSQL。API 通过 `PIPELINE_TASK_SCHEDULER_ENABLED=false` 不再重复调度。采集来源和 InsightHub 交接均使用 PostgreSQL 数据库租约，多个 Worker 实例不会同时领取同一个来源或交接任务。手工运行后端任务进程可使用 `cd backend && uv run pipesight-task-worker`。本地端口：PostgreSQL `15432`、PipeSight API `19099`、InsightHub 健康检查 `18000`。MinIO/S3 为可选对象存储 profile（预留 `19000/19001`）；启用图片缓存时必须配置 `INSIGHTHUB_MINIO_PASSWORD` 和浏览器可访问的 `INSIGHTHUB_MINIO_PUBLIC_BASE_URL`，Worker 不会再使用历史硬编码域名。若启用百度翻译，配置 `INSIGHTHUB_BAIDU_TRANSLATE_APPID`、`INSIGHTHUB_BAIDU_TRANSLATE_APPKEY`，可用 `INSIGHTHUB_BAIDU_TRANSLATE_URL` 覆盖服务地址；若启用本地小模型翻译，再配置 `INSIGHTHUB_TRANSLATION_SMALL_MODEL_URL`；翻译请求超时可用 `INSIGHTHUB_TRANSLATION_REQUEST_TIMEOUT_SECONDS` 调整。若启用生物安全分析上报，再配置 `INSIGHTHUB_THREAT_ANALYSIS_URL`，并按需调整 `INSIGHTHUB_THREAT_ANALYSIS_TIMEOUT_SECONDS`；未配置时均跳过外部调用并保留现有数据。完整边界和配置见 [PipeSight-InsightHub 数据交接适配说明](docs/handover/PipeSight-InsightHub-数据交接适配说明.md) 与 [InsightHub Worker 归并说明](docs/architecture/insighthub-processing-migration.md)。生产环境必须覆盖示例密码并使用密钥注入。

## CLI 命令行工具

```bash
cd backend
pip install -e .
ruoyi --help
```

## 技术特性

- **前后端分离**：Vue 3 独立部署 + FastAPI RESTful API
- **JWT 认证**：基于 Redis 的 Token 黑名单机制，支持单设备/多设备登录控制
- **RBAC 权限**：用户-角色-菜单-按钮四级权限控制，动态路由加载
- **数据权限**：仅支持全部数据与仅本人两级范围，不依赖部门树
- **异步支持**：后端全面使用 async/await，SQLAlchemy 异步引擎
- **传输加密**：可选的 RSA_OAEP + AES_256_GCM 传输层加解密
- **日志系统**：基于 Redis Stream 的分布式日志聚合，支持日志脱敏
- **操作日志**：通过装饰器切面自动记录操作日志
- **定时任务**：基于 APScheduler 的任务调度
- **AI 集成**：支持 OpenAI、Anthropic、Gemini、Groq、Ollama、LiteLLM 等多种 LLM 后端
- **数据库运行时**：统一使用 PostgreSQL + pgvector；保留 MySQL 兼容配置用于历史数据迁移

## 开发约定

- **代码风格**：后端使用 Ruff 进行 linting 和格式化（配置见 `backend/ruff.toml`）
- **命名规范**：后端 API 路径使用 kebab-case，前端组件使用 PascalCase
- **API 响应格式**：统一使用 `{ code, msg, data }` 结构
- **前端路径别名**：`@` 映射到 `frontend/src/`
- **权限指令**：Vue 组件中使用 `v-hasPermi` 和 `v-hasRole` 进行按钮级权限控制

## 相关文档

- [设计方案](docs/requirements/设计方案.docx)
- [平台功能需求分析与进度规划](docs/requirements/平台功能需求分析与进度规划.pdf)
- [平台设计文档](docs/plans/2026-07-13-pipeline-intelligence-platform-design.md)
- [平台实施计划](docs/plans/2026-07-13-pipeline-intelligence-platform-implementation.md)
- [菜单种子 SQL](docs/plans/2026-07-13-pipeline-menu-seed.sql)
- [CLI 使用指南](backend/docs/cli_usage.md)
- [传输加密配置](backend/docs/transport_crypto_config.md)

## License

MIT License — 详见 [frontend/LICENSE](frontend/LICENSE)
