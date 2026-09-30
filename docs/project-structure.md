# 项目结构整理

本文用于管网项目设计管理、开发交接和后续模块扩展。说明以当前仓库为准，并刻意排除了依赖、构建产物、缓存和运行日志目录。

## 1. 项目总览

`pipeSight` 是一个前后端分离项目，主体基于 `RuoYi-Vue3-FastAPI` 扩展，当前业务聚焦“国家管网科技情报与科研辅助平台”。

| 层级 | 目录 | 职责 |
| --- | --- | --- |
| 前端 | `frontend/` | Vue 3 管理端、管网用户门户、页面路由、API 封装和 UI 组件 |
| 后端 | `backend/` | FastAPI 应用、系统管理、管网业务 API、AI 模块、代码生成、调度和 CLI |
| 文档 | `docs/` | 项目方案、需求、实施计划、菜单种子 SQL 和结构说明 |
| 图片资产 | `images/` | 项目展示、方案或文档配图 |
| 容器编排 | `docker-compose.my.yml`、`docker-compose.pg.yml` | MySQL/PostgreSQL 两套 Docker Compose 部署入口 |

顶层结构：

```text
pipeSight/
|-- backend/
|-- frontend/
|-- docs/
|-- images/
|-- docker-compose.my.yml
|-- docker-compose.pg.yml
`-- README.md
```

## 2. 后端结构

后端是 FastAPI 应用。`backend/app.py` 是本地启动入口，调用 `server:create_app`；`backend/server.py` 中创建应用、挂载子应用、中间件、异常处理，并通过 `common/router.py` 自动扫描各模块的 `controller` 路由。

```text
backend/
|-- app.py                         # Uvicorn 启动入口
|-- server.py                      # FastAPI 应用工厂和生命周期
|-- config/                        # 环境、数据库、Redis、调度器配置
|-- common/                        # 路由扩展、通用 VO、常量、切面、注解
|-- middlewares/                   # CORS、GZip、上下文、传输加密、响应头等中间件
|-- exceptions/                    # 全局异常定义和处理
|-- utils/                         # 响应、日志、文件、加密、Excel、服务信息等工具
|-- module_admin/                  # 登录、用户、角色、菜单、字典、参数、日志、监控等后台能力
|-- module_pipeline/               # 管网科技情报与科研辅助业务模块
|-- module_ai/                     # AI 模型配置和对话接口
|-- module_generator/              # 代码生成器及模板
|-- module_task/                   # 调度任务相关代码
|-- cli/                           # ruoyi 命令行工具
|-- sql/                           # MySQL/PostgreSQL 初始化 SQL
|-- alembic/                       # 数据库迁移
|-- tests/                         # 后端与 CLI 测试
|-- docs/                          # 后端专项文档
`-- vf_admin/                      # 上传、下载、代码生成等运行期文件目录
```

后端请求流：

```text
frontend axios
  -> Vite/Nginx /dev-api
  -> backend app.py / server.create_app()
  -> middlewares
  -> exceptions handlers
  -> common.router 自动注册 module_*/controller
  -> controller
  -> service
  -> dao / db / redis / external service
  -> ResponseUtil / DataResponseModel
```

主要后端模块边界：

| 模块 | 说明 |
| --- | --- |
| `module_pipeline/` | 管网业务 API，包含工作台、情报列表/详情、数据源、采集任务、报告、知识库问答 |
| `module_admin/` | RuoYi 后台基础能力，包括认证、RBAC、菜单、部门、岗位、字典、参数、日志、在线用户、缓存和服务监控 |
| `module_ai/` | 多模型配置和 AI 对话能力 |
| `module_generator/` | 数据库表反向生成前后端 CRUD 代码 |
| `common/` | 项目通用基础设施，包括增强路由、权限切面、缓存/限流/日志注解、统一响应模型 |
| `config/` | `.env.*` 配置加载、数据库连接、Redis 连接、APScheduler 调度器 |
| `cli/` | `ruoyi` 命令入口，覆盖应用、数据库、缓存、代码生成、运维和向导能力 |

## 3. 管网业务模块

管网业务后端集中在 `backend/module_pipeline/`：

```text
backend/module_pipeline/
|-- controller/
|   `-- pipeline_controller.py     # /pipeline 路由组
|-- service/
|   `-- pipeline_service.py        # 管网业务数据和操作逻辑
`-- entity/
    `-- vo/
        `-- pipeline_vo.py         # Pydantic 请求/响应模型
```

接口与前端调用关系：

| 功能 | 前端 API | HTTP 路径 | 后端入口 |
| --- | --- | --- | --- |
| 工作台概览 | `getPipelineDashboard` | `GET /pipeline/dashboard` | `pipeline_controller.py` |
| 情报列表 | `listPipelineIntelligence` | `GET /pipeline/intelligence/list` | `pipeline_controller.py` |
| 情报详情 | `getPipelineIntelligenceDetail` | `GET /pipeline/intelligence/{itemId}` | `pipeline_controller.py` |
| 数据源列表 | `listPipelineSources` | `GET /pipeline/sources` | `pipeline_controller.py` |
| 采集任务列表 | `listPipelineTasks` | `GET /pipeline/tasks` | `pipeline_controller.py` |
| 手动运行任务 | `runPipelineTask` | `POST /pipeline/tasks/{taskId}/run` | `pipeline_controller.py` |
| 报告列表 | `listPipelineReports` | `GET /pipeline/reports` | `pipeline_controller.py` |
| 报告导出 | `exportPipelineReport` | `GET /pipeline/reports/{reportId}/export` | `pipeline_controller.py` |
| 知识库文档 | `listPipelineKnowledgeDocuments` | `GET /pipeline/knowledge/documents` | `pipeline_controller.py` |
| 知识库问答 | `askPipelineKnowledge` | `POST /pipeline/knowledge/ask` | `pipeline_controller.py` |

管网业务前端集中在：

```text
frontend/src/api/pipeline/
`-- intelligence.js                # 管网业务 API 封装

frontend/src/views/pipeline/
|-- dashboard/index.vue            # 管理端工作台
|-- intelligence/index.vue         # 情报检索
|-- intelligence/detail.vue        # 情报详情
|-- source/index.vue               # 数据源管理
|-- task/index.vue                 # 采集任务监控
|-- report/index.vue               # 报告管理
`-- knowledge/index.vue            # 知识库

frontend/src/views/portal/
|-- index.vue                      # 用户端门户
`-- components/NewsSidebar.vue     # 门户侧栏组件
```

## 4. 前端结构

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

## 5. 配置与部署

后端配置：

| 文件 | 用途 |
| --- | --- |
| `backend/.env.dev` | 本地开发默认配置 |
| `backend/.env.dockermy` | Docker + MySQL 配置 |
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
| `docker-compose.my.yml` | MySQL 8.0 | `12580` | `19099` | `13306` | `16379` |
| `docker-compose.pg.yml` | PostgreSQL 14 | `12580` | `19099` | `15432` | `16379` |

数据库初始化脚本在 `backend/sql/`，迁移目录在 `backend/alembic/`。

## 6. 文档与设计资料

```text
docs/
|-- plans/
|   |-- 2026-07-13-pipeline-intelligence-platform-design.md
|   |-- 2026-07-13-pipeline-intelligence-platform-implementation.md
|   |-- 2026-07-13-pipeline-menu-seed.sql
|   |-- 2026-07-13-pipeline-mvp-completion-plan.md
|   |-- 2026-07-13-pipeline-portal-ui.md
|   |-- 2026-07-14-pipeline-user-portal-consolidation.md
|   |-- 2026-07-15-pipesight-development-flow-and-resume-state.md
|   `-- 2026-07-23-pipeline-requirements-list.md
|-- 2026-07-10-pg-hot-cold-design/
|-- 设计方案.docx
|-- 平台功能需求分析与进度规划.pdf
`-- project-structure.md
```

设计、需求、计划和菜单种子 SQL 都建议继续放在 `docs/plans/`。`docs/project-structure.md` 用于维护当前代码结构，不替代业务设计文档。

## 7. 生成目录与不建议纳入结构说明的内容

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
| `backend/vf_admin/` | 上传、下载、代码生成等运行期文件 |

## 8. 后续新增模块建议

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
