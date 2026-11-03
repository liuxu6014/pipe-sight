# 国家管网科技情报与科研辅助平台

面向国家管网科技创新的"科技情报与科研辅助平台"，基于 **RuoYi-Vue3-FastAPI** 全栈底座构建，提供情报采集、智能检索、资料管理与科研报告生成等核心能力。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3.5 + Vite 6 + Element Plus 2 + Pinia + Vue Router 4 |
| **后端** | FastAPI 0.128 + SQLAlchemy 2.0 (async) + Pydantic v2 |
| **数据库** | PostgreSQL（统一使用 `172.16.4.183` 的 `pipesight` 库） |
| **缓存** | Redis 7 |
| **AI / LLM** | 多模型接入（OpenAI、Anthropic、Gemini、Groq、Ollama、LiteLLM 等） |
| **容器化** | Docker + Docker Compose |
| **构建工具** | Vite 6 + Rollup |

## 项目结构

```text
PipeSight/
├── backend/                    # Python 后端工程
│   ├── src/app/                # 正式应用包：system / intelligence / library / research 等
│   ├── cli/                    # ruoyi 命令与启动入口
│   ├── common/                 # HTTP 契约、注解、枚举等跨切面支持
│   ├── config/                 # 环境、数据库、调度配置
│   ├── alembic/                # 正式数据库迁移记录
│   ├── sql/                    # 数据库初始化与配套 SQL
│   ├── data/                   # 受控数据清单和冻结结构契约
│   ├── scripts/                # 按用途分组的维护脚本
│   └── tests/                  # 业务及架构测试
├── frontend/                   # Vue 3 + Element Plus 前端工程
│   ├── src/                    # api / store / router / views / components / assets
│   ├── tests/                  # 回归测试与 UI 预览夹具
│   ├── public/                 # 静态资源
│   ├── bin/                    # 前端 Windows 辅助命令
│   └── vite/                   # Vite 插件配置
├── deploy/                     # Docker 镜像定义及 Nginx 配置
│   ├── docker/
│   └── nginx/
├── scripts/                    # 仓库级命令
│   ├── dev/                    # Windows 开发服务启动、停止
│   └── checks/                 # 项目验证入口
├── docs/                       # 架构、使用指南、需求、交接与评审记录
├── docker-compose.local.yml    # 本地 Redis
├── docker-compose.pg.yml       # PostgreSQL 部署入口
└── docker-compose.my.yml       # 历史 MySQL 迁移验证入口
```

详细目录与新增文件约定见 [当前项目结构](docs/project-structure.md)。
部署文件见 [部署目录说明](deploy/README.md)，维护工具见 [后端脚本说明](backend/scripts/README.md)。

## 业务功能

### 当前范围 (MVP)

| 功能模块 | 说明 |
|----------|------|
| **情报工作台** | 有效资讯统计、采集状态、热点主题、待审核报告概览 |
| **情报检索** | 按新闻/公众号/论文类别查看和检索管网相关内容，支持关键词搜索和分页 |
| **数据源管理** | 新增/启停采集源、添加公众号 RSS 链接、设置采集周期，查看类型、运行状态和成功率 |
| **采集任务** | 查看任务列表、运行状态、进度，支持手动触发/停止采集任务 |
| **报告管理** | 查看科研报告与科技情报简报（日报/周报/月报），支持导出 Markdown、DOCX、PDF |
| **内部资料** | 上传、解析、授权访问并将研究资料加入资料篮 |
| **科研任务** | 从资料篮创建任务，执行资料处理、结果审核、重试/驳回并导出成果 |
| **数据处理** | 采集内容经 Kafka 统一接入后进入 `public.news_articles`，支持翻译、分类、有效性校验与去重 |
| **模型与 Prompt** | 管理 `data-filter` 等场景的 Prompt、模型和路由；实际外部来源处理前必须具备已发布配置 |
| **认证授权** | 基于 JWT 的登录认证、角色-菜单-按钮权限控制、动态路由 |
| **系统管理** | 用户/角色/菜单/字典/参数管理；不包含部门、岗位和通知公告模块 |
| **监控管理** | 在线用户、操作日志、登录日志、定时任务、服务监控、缓存监控 |
| **业务 AI 生成** | 管理员配置文本与图片模型，用于报告、简报及分类；未使用的个人聊天功能已移除 |

### 当前边界与后续工作

- 本仓库提供采集任务、PostgreSQL 持久化和任务 Worker；具体爬虫脚本、来源授权和生产级来源接入仍需按来源逐一验收。
- 当前内置采集适配器支持国家管网新闻（`pipechina_group_news`）、Crossref 论文（`crossref_works`）与公众号 RSS（`wechat_rss`，管理员在来源管理中添加公众号 feed 链接即可采集）。其余生产级来源仍需按来源逐一验收。
- 当前默认检索使用 PostgreSQL 查询能力；Elasticsearch、Milvus 等外部基础设施不是默认运行时，不能在未完成数据一致性、权限和运维验收前作为已交付能力宣称。
- MinIO/S3、Embedding 回填和语义检索属于可选能力，只有启用对应 Compose profile、密钥和验收数据后才生效。
- 生产化仍需补齐备份恢复、容量压测、网络/模型/Redis/数据库故障演练和告警接入。
- 证据词严格过滤依赖领域规则文件（如 `*_proofwords.txt`）；当前仓库未内置业务词表，未提供词表时不能把严格证据词过滤视为已启用。
- 知识问答功能和 Kafka Dashboard 不属于当前交付范围；统一采集由 `pipesight-kafka-consumer` 常驻消费端处理（订阅爬虫侧 `news_pipeline` 主题，统一 envelope + 爬虫历史格式兼容），采集后处理由后端任务 Worker 承担。
- 后端不再维护全局 `backend/utils/` 或 `module_*` 业务包；新的公共能力按职责进入 `common/`、`app.infrastructure` 或所属业务模块。

## 快速开始

### 环境要求

- **Node.js** >= 18
- **Python** >= 3.10
- **uv**（后端虚拟环境与依赖安装）
- **PostgreSQL**（统一使用 `172.16.4.183` 的 `pipesight` 库）
- **Redis** >= 6
- **Docker Desktop**（可选；仅用于本机 Redis）

### 1. 一键启动（推荐）

在 Windows PowerShell 或 CMD 中执行：

```powershell
cd PipeSight
.\scripts\dev\start-dev.cmd
```

脚本会依次完成以下工作：

1. 检查 `uv`、Node.js 与 npm；首次运行时自动创建 `backend/.venv` 并安装 PostgreSQL 专用依赖 `requirements-pg.txt`，同时按需执行 `npm ci`。
2. 数据库统一连 `172.16.4.183`；Redis 优先使用本机，未就绪时用根目录 `docker-compose.pg.yml` 启动 Redis。
3. 数据库不存在时自动创建；若缺少若依基础表则导入 `ruoyi-fastapi-pg.sql`，并幂等补齐 PostgreSQL 版管网业务表。
4. 检查 `9099`/`5173` 端口。仅当监听进程能够明确识别为当前 PipeSight 项目时才会停止旧进程；不会直接终止无关程序。若端口被无法确认归属的旧服务占用，会自动为本次前端会话选择下一个可用端口。
5. 使用 uv 启动后端、使用 Vite 启动前端，并等待健康检查通过后输出访问地址。

启动成功后访问：

- 用户端：脚本最后输出的 `Frontend` 地址（默认 `http://127.0.0.1:5173/portal`）
- 后端接口文档：脚本最后输出的 `Backend` 地址（默认 `http://127.0.0.1:9099/docs`）
- 启动日志：项目根目录 `.runtime\pipesight-dev\`

停止本次启动的前后端（不会停止 PostgreSQL/Redis）：

```powershell
.\scripts\dev\stop-dev.cmd
```

常用启动选项：

```powershell
# 强制使用 Docker 中的 Redis
.\scripts\dev\start-dev.cmd -Infrastructure Docker

# 使用本机 Redis（数据库统一连 183）
.\scripts\dev\start-dev.cmd -Infrastructure Local

# 禁止自动安装依赖（依赖缺失或过期时直接报错）
.\scripts\dev\start-dev.cmd -SkipInstall

# requirements-pg.txt 或 package-lock.json 变更后强制重装
.\scripts\dev\start-dev.cmd -ForceDependencyInstall
```

### 2. 手动启动基础设施

#### 方式 A：使用本地安装的 Redis

确保 Redis 已在本地运行；数据库统一连 `172.16.4.183`，在 `backend/.env.dev` 配置 `DB_*`。

#### 方式 B：使用 Docker 启动 Redis

```bash
docker compose -p pipesight-pg -f docker-compose.pg.yml up -d ruoyi-redis
```

> Docker 启动后，Redis 端口映射为 `16379`；数据库统一连 `172.16.4.183`，不随 Docker 启动本地 PostgreSQL。

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
uv run --no-sync python scripts/bootstrap/seed_dev_data.py --env=dev
```

初始化真实公开来源并执行一次采集：

```bash
cd backend
uv run --no-sync python scripts/bootstrap/bootstrap_real_pipeline.py
```

该脚本默认保留管理员对内置来源的启用/停用状态，并逐个来源执行、逐个报告失败。只有确认需要恢复已停用内置来源时，才显式增加 `--reactivate`。外部来源执行前还必须在管理端完成已发布 `data-filter` Prompt、可用模型和场景路由配置。

如果本地 `.env` 已配置 `INSIGHTHUB_LLM_MODEL`、`INSIGHTHUB_LLM_BASE_URL` 和 `INSIGHTHUB_LLM_API_KEYS`（或对应的 `PIPELINE_DEEPSEEK_*`），可以将 DeepSeek 安全注册到管理模型表，并启用 `data-filter` 路由：

```bash
cd backend
uv run --no-sync python scripts/bootstrap/bootstrap_deepseek_route.py --env=dockerpg
```

数据库连接由 `--env=dockerpg` 对应的环境文件提供，统一指向 `172.16.4.183` 的 `pipesight` 库。

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

PipeSight API 和任务 Worker 统一使用 `backend/` 的 Python 项目环境。建议按项目级脚本执行：

```bash
# 一键执行全部本地验证
./scripts/checks/verify_project.sh

# 也可以按组件分别执行：

# PipeSight 后端
cd backend
uv run pytest tests -q

# 前端行为测试
cd ../frontend
npm test

# 前端生产构建检查
npm run check
```

后端测试覆盖 API、数据访问、权限、任务和报告逻辑；需要真实数据库、Kafka 或外部模型的用例会明确标记为集成/跳过，不以单元测试通过替代运行态验收。

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
DB_HOST = '172.16.4.183'
DB_PORT = 5432
DB_USERNAME = 'postgres'
DB_PASSWORD = '<数据库密码>'
DB_DATABASE = 'pipesight'

# Redis
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379                 # Docker: 16379
REDIS_DATABASE = 2

# JWT
JWT_SECRET_KEY = '<your-secret-key>'
JWT_EXPIRE_MINUTES = 1440
```

> 多环境配置文件：`.env.dev`（开发）、`.env.dockermy`（旧版 Docker+MySQL，仅迁移参考）、`.env.dockerpg`（连接 183 的 PostgreSQL 环境）、`.env.prod`（生产）。线上和本地默认运行链路均使用 PostgreSQL；MySQL 配置仅保留用于历史数据迁移。

### 前端配置

前端通过 `.env.*` 文件配置不同环境的 API 地址：

| 文件 | 环境 |
|------|------|
| `.env.development` | 本地开发（代理到 `http://127.0.0.1:9099`） |
| `.env.docker` | Docker 部署 |
| `.env.production` | 生产构建 |
| `.env.staging` | 预发布环境 |

## Docker 部署

### 全栈 Docker 部署

```bash
docker compose -p pipesight-pg -f docker-compose.pg.yml up -d --build
```

| 服务 | 端口 |
|------|------|
| 前端 (Nginx) | `12580` |
| 后端 (FastAPI) | `19099` |
| Redis | `16379` |

数据库统一使用 `172.16.4.183` 的 `pipesight` 库（不随 Compose 启动）。

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

数据库统一使用 `172.16.4.183` 上的 `pipesight` 库（`public` schema），项目不再随 Compose 启动本地 PostgreSQL。根 Compose 只编排 `pipesight-db-migrate`（先执行 `alembic upgrade head`）、`ruoyi-backend-pg`、`ruoyi-frontend`、`pipesight-task-worker` 和 `ruoyi-redis`：

```bash
docker compose -p pipesight-pg -f docker-compose.pg.yml up -d --build
```

其中 `pipesight-task-worker` 负责数据源采集、科研生成、报告导出和资料解析持久队列；API 通过 `PIPELINE_TASK_SCHEDULER_ENABLED=false` 不再重复调度。采集来源使用 PostgreSQL 数据库租约，多个 Worker 实例不会同时领取同一个来源。手工运行后端任务进程可使用 `cd backend && uv run pipesight-task-worker`。本地端口：PipeSight API `19099`、前端 `12580`、Redis `16379`。数据库连接凭据经 `DATA_DB_PASSWORD` 注入，生产环境必须覆盖示例密码并使用密钥注入。

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
- **数据库运行时**：统一使用 `172.16.4.183` 的 PostgreSQL；保留 MySQL 兼容配置用于历史数据迁移

## 开发约定

- **代码风格**：后端使用 Ruff 进行 linting 和格式化（配置见 `backend/ruff.toml`）
- **命名规范**：后端 API 路径使用 kebab-case，前端组件使用 PascalCase
- **API 响应格式**：统一使用 `{ code, msg, data }` 结构
- **前端路径别名**：`@` 映射到 `frontend/src/`
- **权限指令**：Vue 组件中使用 `v-hasPermi` 和 `v-hasRole` 进行按钮级权限控制

## 相关文档

- [项目全流程说明（面向领导）](docs/项目全流程说明.md)
- [PipeSight 全流程（技术版）](docs/architecture/pipeline-flow.md)
- [设计方案](docs/requirements/设计方案.docx)
- [平台功能需求分析与进度规划](docs/requirements/平台功能需求分析与进度规划.pdf)
- [平台设计文档](docs/plans/2026-07-13-pipeline-intelligence-platform-design.md)
- [平台实施计划](docs/plans/2026-07-13-pipeline-intelligence-platform-implementation.md)
- [菜单种子 SQL](docs/plans/2026-07-13-pipeline-menu-seed.sql)
- [CLI 使用指南](docs/guides/cli-usage.md)
- [传输加密配置](docs/guides/transport-crypto-config.md)

## License

MIT License — 详见 [frontend/LICENSE](frontend/LICENSE)
