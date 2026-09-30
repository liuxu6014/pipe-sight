# 国家管网科技情报与科研辅助平台

面向国家管网科技创新的"科技情报与科研辅助平台"，基于 **RuoYi-Vue3-FastAPI** 全栈底座构建，提供情报采集、智能检索、报告生成与知识库问答等核心能力。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3.5 + Vite 6 + Element Plus 2 + Pinia + Vue Router 4 |
| **后端** | FastAPI 0.128 + SQLAlchemy 2.0 (async) + Pydantic v2 |
| **数据库** | MySQL 8.0（默认）/ PostgreSQL 14 |
| **缓存** | Redis 7 |
| **AI / LLM** | 多模型接入（OpenAI、Anthropic、Gemini、Groq、Ollama、LiteLLM 等） |
| **容器化** | Docker + Docker Compose |
| **构建工具** | Vite 6 + Rollup |

## 项目结构

```
pipeSight/
├── frontend/                    # Vue 3 前端源码
│   ├── src/
│   │   ├── api/                 # API 接口封装
│   │   │   ├── pipeline/        # 管网情报业务接口
│   │   │   ├── system/          # 系统管理接口
│   │   │   ├── monitor/         # 监控管理接口
│   │   │   └── ai/              # AI 对话接口
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
│   │   │   ├── ai/              # AI 对话
│   │   │   └── dashboard/       # 首页工作台
│   │   ├── layout/              # 页面布局组件
│   │   ├── router/              # 动态路由
│   │   ├── store/               # Pinia 状态管理
│   │   ├── components/          # 公共组件
│   │   └── utils/               # 工具函数
│   ├── bin/                     # Nginx 配置文件
│   ├── vite/                    # Vite 插件配置
│   ├── Dockerfile               # 前端 Docker 构建文件
│   └── legacy-static/           # 保留的旧版静态演示产物
│
├── backend/                     # FastAPI 后端源码
│   ├── module_admin/            # 系统管理模块（用户/角色/菜单/字典/参数/日志）
│   ├── module_pipeline/         # 管网情报业务模块
│   │   ├── controller/          # 路由控制器
│   │   ├── service/             # 业务逻辑层
│   │   └── entity/vo/           # 请求/响应模型
│   ├── module_ai/               # AI 多模型对话模块
│   ├── module_task/             # 定时任务模块
│   ├── module_generator/        # 旧代码生成兼容代码（路由和持久化已停用）
│   ├── common/                  # 公共基础设施（路由注册/权限切面/响应模型）
│   ├── config/                  # 数据库/Redis/调度器配置
│   ├── middlewares/             # 中间件
│   ├── exceptions/              # 全局异常处理
│   ├── utils/                   # 工具函数
│   ├── sql/                     # 数据库初始化 SQL
│   ├── tests/                   # 测试用例
│   ├── alembic/                 # 数据库迁移
│   ├── cli/                     # CLI 命令行工具
│   ├── app.py                   # 应用入口
│   ├── server.py                # FastAPI 应用工厂
│   ├── Dockerfile.my            # MySQL 版 Docker 构建
│   └── Dockerfile.pg            # PostgreSQL 版 Docker 构建
│
├── docs/
│   ├── plans/                   # 设计文档与实施计划
│   ├── 设计方案.docx
│   └── 平台功能需求分析与进度规划.pdf
│
├── docker-compose.my.yml        # Docker Compose（MySQL）
└── docker-compose.pg.yml        # Docker Compose（PostgreSQL）
```

## 业务功能

### 当前范围 (MVP)

| 功能模块 | 说明 |
|----------|------|
| **情报工作台** | 有效资讯统计、采集状态、热点主题、待审核报告概览 |
| **情报检索** | 按新闻/公众号/论文类别查看和检索管网相关内容，支持关键词搜索和分页 |
| **数据源管理** | 查看采集源名称、类型、采集频率、运行状态和成功率 |
| **采集任务** | 查看任务列表、运行状态、进度，支持手动触发采集任务 |
| **报告管理** | 查看日报/周报/技术路线报告草稿，支持导出 Markdown 格式报告 |
| **知识库** | 展示已索引的项目文档，支持基于项目资料的简易问答和引用资料展示 |
| **认证授权** | 基于 JWT 的登录认证、角色-菜单-按钮权限控制、动态路由 |
| **系统管理** | 用户/角色/菜单/字典/参数管理；不包含部门、岗位和通知公告模块 |
| **监控管理** | 在线用户、操作日志、登录日志、定时任务、服务监控、缓存监控 |
| **AI 对话** | 多模型接入的 AI 对话助手界面 |

### 后续规划

- 真实采集调度（RSS/API/爬虫）
- 数据清洗与去重流水线
- 全文检索（Elasticsearch）
- MinIO 文档上传与管理
- 向量索引与 RAG 知识库问答
- 报告模板编排与自动生成
- 人工审核工作流
- Kafka/ES/Milvus 基础设施接入
- 任务日志持久化与告警

## 快速开始

### 环境要求

- **Node.js** >= 18
- **Python** >= 3.10
- **uv**（后端虚拟环境与依赖安装）
- **MySQL** 8.0 或 **PostgreSQL** 14
- **Redis** >= 6
- **Docker Desktop**（可选；本机没有可用的 MySQL/Redis 时，一键脚本会使用）

### 1. 一键启动（推荐）

在 Windows PowerShell 或 CMD 中执行：

```powershell
cd pipeSight
.\start-dev.cmd
```

脚本会依次完成以下工作：

1. 检查 `uv`、Node.js 与 npm；首次运行时自动创建 `backend/.venv` 并安装 `requirements.txt`，同时按需执行 `npm ci`。
2. 优先使用本机 `3306`/`6379` 的 MySQL 和 Redis；两者没有同时就绪时，自动通过 Docker 启动映射到 `13306`/`16379` 的基础设施。
3. 数据库不存在时自动创建；若缺少若依基础表则导入 `ruoyi-fastapi.sql`，并幂等补齐 `pipeline-domain.sql` 与 `pipeline-domain-enhancement.sql` 业务表。
4. 检查 `9099`/`5173` 端口。仅当监听进程能够明确识别为当前 PipeSight 项目时才会停止旧进程；不会直接终止无关程序。若端口被无法确认归属的旧服务占用，会自动为本次前端会话选择下一个可用端口。
5. 使用 uv 启动后端、使用 Vite 启动前端，并等待健康检查通过后输出访问地址。

启动成功后访问：

- 用户端：脚本最后输出的 `Frontend` 地址（默认 `http://127.0.0.1:5173/portal`）
- 后端接口文档：脚本最后输出的 `Backend` 地址（默认 `http://127.0.0.1:9099/docs`）
- 启动日志：项目根目录 `.runtime\pipesight-dev\`

停止本次启动的前后端（不会停止 MySQL/Redis）：

```powershell
.\stop-dev.cmd
```

常用启动选项：

```powershell
# 强制使用 Docker 中的 MySQL 和 Redis
.\start-dev.cmd -Infrastructure Docker

# 强制使用 backend/.env.dev 指向的本地 MySQL 和 Redis
.\start-dev.cmd -Infrastructure Local

# 禁止自动安装依赖（依赖缺失或过期时直接报错）
.\start-dev.cmd -SkipInstall

# requirements.txt 或 package-lock.json 变更后强制重装
.\start-dev.cmd -ForceDependencyInstall
```

### 2. 手动启动基础设施

#### 方式 A：使用本地安装的服务

确保 MySQL 和 Redis 已在本地运行，然后配置 `backend/.env.dev` 中的连接信息（默认配置见下文）。

#### 方式 B：使用 Docker 启动服务

```bash
# MySQL 版本
docker compose -f docker-compose.my.yml up -d ruoyi-mysql ruoyi-redis

# PostgreSQL 版本
docker compose -f docker-compose.pg.yml up -d ruoyi-pg ruoyi-redis
```

> Docker 启动后，MySQL 端口映射为 `13306`，PostgreSQL 端口映射为 `15432`，Redis 端口映射为 `16379`。请确保 `backend/.env.dev` 中的数据库连接信息与 Docker 端口一致。

新建 Docker 数据卷时，Compose 会按顺序自动导入：

- `10-ruoyi-fastapi.sql`：若依基础表和种子数据
- `20-pipeline-domain.sql`：知识文件与切块、资料篮、模板与 Prompt、生成任务、报告版本、引用和导出表
- `30-pipeline-domain-enhancement.sql`：数据来源、采集运行、原始记录、资讯、论文和分类标签表

Docker 已存在旧数据卷时，入口初始化脚本不会再次运行；执行 `.\start-dev.cmd -Infrastructure Docker` 会额外执行一次幂等的管网业务表初始化。

### 3. 手动启动后端

```powershell
cd backend

# 创建 uv 虚拟环境并安装完整运行依赖
uv venv
uv pip install -r requirements.txt

# 设置编码并启动
$env:PYTHONIOENCODING='utf-8'
uv run --no-sync python app.py --env=dev
```

后端默认运行在 `http://127.0.0.1:9099`，Swagger 文档地址为 `http://127.0.0.1:9099/docs`。

> `backend/pyproject.toml` 主要声明若依 CLI 包，完整 Web 运行依赖由 `requirements.txt` 管理。因此全新环境不能直接执行 `uv run --no-sync`；必须先执行一次 `uv pip install -r requirements.txt`，或直接使用根目录的一键启动脚本。

开发环境需要页面有可演示数据时，可幂等执行一次最小种子脚本（不会写入生产迁移）：

```powershell
cd backend
uv run --no-sync python scripts/seed_dev_data.py --env=dev
```

### 4. 手动启动前端

```powershell
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

前端开发服务器运行在 `http://127.0.0.1:5173/`，并通过 Vite proxy 将 `/dev-api` 代理到后端 `http://127.0.0.1:9099`。

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
- `pipeline/knowledge/index` — 知识库

### 6. 登录

| 账号 | 密码 |
|------|------|
| `admin` | `admin123` |
| `niangao` | `admin123` |

> 新建用户的默认初始密码为 `123456`。

## 配置说明

### 后端配置 (`backend/.env.dev`)

```ini
# 数据库（默认 MySQL）
DB_TYPE = 'mysql'                 # 可选 'postgresql'
DB_HOST = '127.0.0.1'
DB_PORT = 3306                    # Docker: 13306
DB_USERNAME = 'root'
DB_PASSWORD = '123456'            # Docker: root
DB_DATABASE = 'ruoyi-fastapi'

# Redis
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379                 # Docker: 16379
REDIS_DATABASE = 2

# JWT
JWT_SECRET_KEY = '<your-secret-key>'
JWT_EXPIRE_MINUTES = 1440
```

> 多环境配置文件：`.env.dev`（开发）、`.env.dockermy`（Docker+MySQL）、`.env.dockerpg`（Docker+PostgreSQL）、`.env.prod`（生产）。

### 前端配置

前端通过 `.env.*` 文件配置不同环境的 API 地址：

| 文件 | 环境 |
|------|------|
| `.env.development` | 本地开发（代理到 `http://127.0.0.1:9099`） |
| `.env.docker` | Docker 部署 |
| `.env.production` | 生产构建 |
| `.env.staging` | 预发布环境 |

## Docker 部署

### 全栈 Docker 部署（MySQL）

```bash
docker compose -f docker-compose.my.yml up -d
```

| 服务 | 端口 |
|------|------|
| 前端 (Nginx) | `12580` |
| 后端 (FastAPI) | `19099` |
| MySQL | `13306` |
| Redis | `16379` |

### 全栈 Docker 部署（PostgreSQL）

```bash
docker compose -f docker-compose.pg.yml up -d
```

| 服务 | 端口 |
|------|------|
| 前端 (Nginx) | `12580` |
| 后端 (FastAPI) | `19099` |
| PostgreSQL | `15432` |
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
uv pip install -r requirements.txt
uv run --no-sync python app.py
```

生产环境建议配合 Gunicorn + Uvicorn workers 运行：

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker server:create_app
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
| `GET` | `/pipeline/reports/{id}/export` | 导出报告 Markdown |
| `GET` | `/pipeline/knowledge/documents` | 查询知识库文档 |
| `POST` | `/pipeline/knowledge/ask` | 知识库问答 |

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

采集后的资讯和论文先写入 PipeSight，再交给外部 InsightHub 处理。双方不复制对方的 `hp_*`、Prompt 或向量表；PipeSight 通过 `handoff_*` 字段记录批次、回执、处理版本和结果快照。适配说明见 [PipeSight-InsightHub 数据交接适配说明](docs/交接文档/PipeSight-InsightHub-数据交接适配说明.md)，增量迁移为 `backend/alembic/versions/20260824_external_processing_handoff.py`。

外部新闻入库适配器位于 `backend/module_pipeline/integration/insighthub_adapter.py`，默认关闭；启用时通过 `INSIGHTHUB_*` 环境变量配置，不把数据库密码写入仓库。

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
- **多数据库**：同时支持 MySQL 和 PostgreSQL，通过配置切换

## 开发约定

- **代码风格**：后端使用 Ruff 进行 linting 和格式化（配置见 `backend/ruff.toml`）
- **命名规范**：后端 API 路径使用 kebab-case，前端组件使用 PascalCase
- **API 响应格式**：统一使用 `{ code, msg, data }` 结构
- **前端路径别名**：`@` 映射到 `frontend/src/`
- **权限指令**：Vue 组件中使用 `v-hasPermi` 和 `v-hasRole` 进行按钮级权限控制

## 相关文档

- [设计方案](docs/设计方案.docx)
- [平台功能需求分析与进度规划](docs/平台功能需求分析与进度规划.pdf)
- [平台设计文档](docs/plans/2026-07-13-pipeline-intelligence-platform-design.md)
- [平台实施计划](docs/plans/2026-07-13-pipeline-intelligence-platform-implementation.md)
- [菜单种子 SQL](docs/plans/2026-07-13-pipeline-menu-seed.sql)
- [CLI 使用指南](backend/docs/cli_usage.md)
- [传输加密配置](backend/docs/transport_crypto_config.md)

## License

MIT License — 详见 [frontend/LICENSE](frontend/LICENSE)
