# 项目目标结构与分层开发规范

状态：目标架构与实施说明。当前 `src/app` 已是正式应用包，旧 `module_*` 业务包和全局 `utils` Python 模块已退出运行路径；后续工作集中在业务闭环、部署验收和未覆盖的边界能力。

编写日期：2026-10-01。

适用项目：国家管网科技情报与科研辅助平台（PipeSight）。

## 1. 架构决策与适用边界

采用单仓库、模块化单体后端，使用 `backend/src/app/` 作为 Python 源码布局。先按业务划分模块，再在模块内部统一分层。API、Worker、Scheduler、CLI 共用同一个应用包，允许使用不同进程运行。

已确定的约定：

- Python 导入包名为 `app`，不使用 `pipesight` 作为导入包名，也不保留 `module_` 前缀。
- `backend/` 管理后端工程，`src/` 隔离可安装源代码，`app/` 提供统一导入空间。
- 保留 Python/FastAPI、SQLAlchemy、PostgreSQL/pgvector、Redis，以及 Vue 3、Vite、Pinia 的技术方向；结构整理不附带前端 TypeScript 重写。
- InsightHub 的有效处理能力融入后端；最终不再维护第二套后端依赖、配置和处理业务入口。
- 阿里巴巴应用分层用于指导职责和依赖方向；具体包名、Repository 命名与下面的业务边界是本项目约定，不是阿里官方 Python 目录模板。
- 目标目录只在存在实际职责时建立，不批量生成空服务、空接口、空 Manager 或占位测试。
- 本文不重新引入知识问答、独立 InsightHub/Kafka Dashboard，也不把已有管理端业务工作台一并移除。

本文的代码片段、启动命令、任务状态均为目标约定。现阶段仍以实际源代码、Compose 和数据库迁移记录为准，不能直接把示例命令当作已经可用的运行入口。

### 1.1 设计依据

阿里手册区分 Web、Service、通用处理与 DAO 的职责，并给出分层对象的参考。这里采用职责分离和向下依赖的思想，根据业务复用需要提取组件，不强制每条调用经过全部层级。[阿里巴巴应用分层](https://github.com/alibaba/p3c/blob/master/p3c-gitbook/工程结构/应用分层.md)

`src` 布局把可导入代码与工程文件分开，开发环境需安装项目，生产环境应验证构建后的安装产物。它是本项目的长期选择，并非 Python 唯一合法布局。[Python Packaging 指南](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)

HTTP 路由使用 FastAPI 的 `APIRouter`，由 `app.entrypoints.routes` 显式登记并注册，避免目录名与隐式路由发现机制绑定。[FastAPI 多文件应用说明](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

### 1.2 当前代码的迁移起点

迁移起点的 `pipeline_domain_service.py` 为 2,090 行，集中承担数据源、情报、上传资料、资料篮、科研任务和报告等职责；`pipeline_controller.py` 为 788 行；InsightHub 的 `main.py` 为 940 行。当前科研平台门面已迁移到 `app.research.services.facade`，约 748 行的编排仍保留必要的序列化/事务包装。行数不是质量判定标准，仍需按真实调用链继续验收。

本轮已建立 `backend/src/app` 包、API 入口和安装配置；旧 `backend/app.py` 已删除，避免文件与包同名遮蔽；应用工厂和生命周期已收敛到 `app.bootstrap`，路由已改为 `app.entrypoints.routes` 显式清单。`app.system` 为业务 API 提供认证上下文、登录/注册/验证码、配置、菜单、用户和角色 Controller，及对应的认证/配置/菜单/用户/角色 Service、Repository、ORM 和 API 契约。资料库不再直接调用旧管理模块的上传服务；资料库的 `PipelineMaterial` 已归位到 `app.library.models.materials`，科研过程模型已归位到 `app.research.models.research_models`，情报模型已按采集、配置、内容、治理拆分到独立文件。跨业务 HTTP 响应、请求、Pydantic 契约、客户端地址、请求上下文、路由依赖和路由适配位于 `backend/common/http`，其中 `schemas.py` 负责跨业务响应契约，`responses.py` 负责响应构造，`context.py` 负责请求上下文，`dependencies.py` 负责路由依赖，`routing.py` 只负责路由组件和稳定排序；日志、序列化、文件、加密、分页、导出等技术能力位于 `app.infrastructure.services`；`config/model_discovery.py` 负责 Alembic 模型发现。`server.py` 仅保留启动兼容入口，旧 `common/router.py`、`common/vo.py` 及其通配扫描已移除。架构测试会持续核对打包、导入、路由、任务引用、资源路径和旧路径残留，不能只移动目录。

旧 `module_pipeline/service/pipeline_service.py` 中的内存静态演示服务已删除；当前管网页面的数据路径必须落到 `app` 服务、Repository 和 PostgreSQL，而不是回退到常量样例。

## 2. 项目整体目录

以下是目标结构。省略重复的 `__init__.py`；所有 Python 常规包均应按实际打包配置提供该文件。

```text
pipe-sight/
├── README.md                         # 项目介绍、开发入口、部署入口
├── .gitignore
├── .github/
│   └── workflows/                    # 持续集成、测试、构建
│
├── backend/
│   ├── pyproject.toml                # 依赖、打包、命令入口、质量工具配置
│   ├── uv.lock                       # 唯一后端依赖锁文件
│   ├── .env.example                  # 无真实凭据的配置示例
│   ├── alembic.ini
│   ├── src/
│   │   └── app/
│   │       ├── __init__.py
│   │       ├── bootstrap.py          # 资源和依赖组装
│   │       ├── entrypoints/          # API、Worker、Scheduler、CLI入口
│   │       ├── system/               # 身份、权限和系统管理
│   │       │   ├── api/login_controller.py # 登录/注册 API
│   │       │   ├── api/captcha_controller.py # 图片验证码 API
│   │       │   ├── api/dictionary_controller.py # 字典管理 API
│   │       │   ├── schemas/      # 登录、菜单、用户、角色、配置、字典和当前用户 API 契约
│   │       │   ├── models/           # 用户、角色、菜单、配置和字典 ORM
│   │       │   ├── repositories/     # 认证、用户、角色、菜单、配置和字典查询
│   │       │   └── services/         # 认证、用户、角色、菜单、配置和字典用例
│   │       ├── intelligence/         # 数据源、采集、处理、情报、简报和模型配置
│   │       ├── library/              # 上传资料、解析和受控访问
│   │       ├── research/             # 资料篮、科研任务、证据和报告
│   │       ├── infrastructure/       # 跨业务复用的技术设施
│   │       │   ├── api/cache_controller.py # Redis缓存监控 API
│   │       │   ├── api/server_controller.py # 主机与进程监控 API
│   │       │   ├── api/transport_crypto_controller.py # 传输加密配置与监控 API
│   │       │   ├── api/log_controller.py # 操作日志与登录日志 API
│   │       │   ├── api/job_controller.py # 定时任务与调度日志 API
│   │       │   ├── api/file_controller.py # 通用文件上传与下载 API
│   │       │   ├── api/online_controller.py # Redis在线会话监控 API
│   │       │   ├── schemas/cache.py # 缓存监控 API 契约
│   │       │   ├── schemas/server.py # 服务器监控 API 契约
│   │       │   ├── schemas/transport_crypto.py # 传输加密 API 契约
│   │       │   ├── schemas/log.py # 审计日志 API 契约
│   │       │   ├── schemas/jobs.py # 定时任务与调度日志契约
│   │       │   ├── schemas/files.py # 文件传输 API 契约
│   │       │   ├── schemas/online.py # 在线会话 API 契约
│   │       │   ├── services/cache.py # Redis缓存监控服务
│   │       │   ├── services/server.py # 主机与进程监控服务
│   │       │   ├── services/transport_crypto.py # 传输加密 API 服务
│   │       │   ├── models/audit.py # 登录与操作日志 ORM
│   │       │   ├── models/jobs.py # 定时任务与调度日志 ORM
│   │       │   ├── repositories/audit_logs.py # 审计日志数据访问
│   │       │   ├── repositories/jobs.py # 定时任务数据访问
│   │       │   ├── repositories/job_logs.py # 调度日志数据访问
│   │       │   ├── services/log.py # 日志查询、队列与聚合服务
│   │       │   ├── services/jobs.py # 定时任务管理与执行服务
│   │       │   ├── services/job_logs.py # 调度日志查询与导出服务
│   │       │   ├── services/file_storage.py # 受控文件存储与内容校验
│   │       │   ├── services/file_transfer.py # 通用文件上传、下载与路径校验
│   │       │   └── services/online.py # 在线会话查询与强制下线
│   ├── alembic/
│   │   ├── env.py                    # Alembic环境与模型注册
│   │   ├── script.py.mako
│   │   └── versions/                 # 数据库版本变更
│   ├── scripts/
│   │   ├── imports/                  # 一次性数据导入
│   │   ├── backfills/                # 字段回填和重建
│   │   └── migrations/               # 历史系统数据转换
│   └── tests/
│       ├── conftest.py
│       ├── fixtures/
│       ├── unit/                     # 按业务模块镜像分组
│       ├── integration/              # 数据库、API、任务、外部适配集成
│       ├── architecture/             # 依赖方向、包安装、资源完整性
│       └── cli/                      # 管理命令行为
│
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   ├── index.html
│   ├── .env.example
│   ├── public/                       # 无需构建处理的公开静态文件
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── api/                      # 按业务分组的HTTP请求
│   │   ├── views/                    # 门户、管理端和公共页面
│   │   ├── components/               # 跨页面组件
│   │   ├── composables/              # Vue组合逻辑，按实际需要添加
│   │   ├── layout/                   # 保留既有目录命名
│   │   ├── router/                   # 路由及权限导航
│   │   ├── store/                    # Pinia状态
│   │   ├── directive/                # 保留既有目录命名
│   │   ├── plugins/
│   │   ├── assets/                   # 编译处理的图片、图标和样式
│   │   └── utils/                    # 纯前端通用函数
│   └── tests/
│
├── deploy/
│   ├── docker/
│   │   ├── backend.Dockerfile        # 同一包，支持不同进程入口
│   │   └── frontend.Dockerfile
│   ├── compose/
│   │   ├── compose.yml              # 公共服务定义
│   │   ├── compose.dev.yml          # 开发覆盖配置
│   │   ├── compose.prod.yml         # 生产覆盖配置
│   │   └── .env.example             # 编排变量示例
│   ├── nginx/
│   └── postgres/                    # 实例、角色、扩展的初始化配置
│
├── scripts/                         # 跨工程开发、验证和运维入口
│   ├── dev/                         # 启停本项目服务
│   ├── checks/                      # 聚合质量检查
│   └── ops/                         # 备份、恢复、健康检查
├── tests/
│   └── e2e/                         # 真实用户跨前后端完整流程
├── docs/
│   ├── README.md
│   ├── architecture/                # 结构、数据模型、架构决策
│   ├── requirements/
│   ├── development/                 # 环境、开发规范、接口说明
│   ├── operations/                  # 部署、迁移、恢复和故障处理
│   ├── plans/
│   ├── handover/
│   ├── reference/
│   ├── reports/
│   └── assets/                      # 文档配图
└── var/                             # 本地运行数据；忽略、不打包、不提交
    ├── uploads/
    ├── exports/
    ├── logs/
    └── tmp/
```

`var/` 只表示本地默认目录。生产文件使用受控卷或对象存储；数据库持久卷不放源码目录。现有上传文件迁移须核对数据库引用、权限和可恢复性。业务图片归前端资产，文档截图归 `docs/assets/`，不可整批混搬。

## 3. 后端各模块的职责和数据归属

| 模块 | 负责的业务 | 数据归属与边界 |
| --- | --- | --- |
| `system` | 登录、验证码、用户、角色、菜单、字典、系统参数和审计 | 拥有用户权限及系统管理记录；部门、岗位、通知等未启用的旧模块不再保留运行代码；系统参数不是所有业务配置的集中存放处 |
| `intelligence` | 数据源、采集运行、原始内容、处理任务、过滤配置、新闻、论文、情报检索和简报 | 拥有采集和情报处理事实；简报作为情报产品在此管理 |
| `library` | 个人/共享上传资料、解析、内容读取、下载授权 | 拥有上传资料、可见范围、解析状态；“知识库”页面可继续使用既有产品名称 |
| `research` | 资料篮、科研任务、引用证据、文稿/科研报告、版本、图表和导出 | 拥有研究过程与成果；引用其他模块资料，不取得其他模块的数据写入权 |
| `ai` | 模型注册、供应商配置、模型能力、通用生成/向量调用、调用计量 | 不决定文章是否保留或报告业务状态；业务提示词归所属业务模块 |
| `tooling` | 当前无运行时代码生成能力 | 数据库迁移已移除生成器配置表和 `/tool/gen` 路由；后续如恢复，必须作为独立开发工具重新设计，不得复活旧入口 |
| `infrastructure` | PG、Redis、文件存储、任务机制、消息、日志和外部发送通道 | 持有技术资源，不拥有用户、文章、报告等业务规则；文件存储和通用传输必须复用同一安全实现 |

情报文章、上传文档、科研报告虽然都包含文本，但生命周期、权限和来源不同，不合并成一个无差别的“大文档表”。资料篮保存引用；科研执行保存必要证据快照，保证后续可追溯。

### 3.1 标准业务模块内部结构

以科研模块为例：

```text
research/
├── api/
│   ├── router.py                    # 汇总本模块路由
│   ├── workspace.py
│   ├── tasks.py
│   ├── reports.py
│   └── templates.py
├── services/
│   ├── workspace.py
│   ├── tasks.py
│   ├── evidence.py
│   ├── reports.py
│   └── templates.py
├── repositories/
│   ├── workspace.py
│   ├── tasks.py
│   ├── evidence.py
│   ├── reports.py
│   └── templates.py
├── models/                          # SQLAlchemy持久化模型
│   ├── workspace.py
│   ├── tasks.py
│   ├── evidence.py
│   ├── reports.py
│   └── templates.py
├── schemas/                         # HTTP请求和响应模型
│   ├── workspace.py
│   ├── tasks.py
│   ├── reports.py
│   └── templates.py
├── contracts.py                     # 稳定的服务输入/输出类型
├── policies.py                      # 访问与状态转换规则，复杂时拆文件
├── errors.py                        # 业务异常
├── tasks/
│   └── generate_report.py           # Worker处理函数，调用Service
├── exporters/
│   ├── docx.py
│   └── markdown.py
└── resources/
    ├── prompts/                     # 默认生成提示词
    └── report_templates/            # 报告模板和导出资源
```

其他业务模块复用 `api/services/repositories/models/schemas` 这套职责约定。文件按实际业务对象建立，不要求每层拥有完全相同的文件数量。

`research/tasks/` 是后台任务处理入口；`research/services/tasks.py` 是科研任务的业务服务；`infrastructure/task_queue/` 是通用执行机制。三者不互相代替。

`contracts.py` 在存在跨入口或跨模块的稳定数据契约时使用，可采用 dataclass、Pydantic 或 Protocol。简单输入直接使用明确的类型参数；不为同一组字段机械制造 DO、DTO、BO、AO、VO 五份对象。

### 3.2 情报处理模块的特殊结构

```text
intelligence/
├── api/                             # sources、collection、processing、articles等
├── services/                        # 同名业务用例、提示词版本和简报编排
├── integrations/                    # InsightHub 等外部系统适配器
├── tasks/                           # 来源采集、回执轮询等后台任务入口
├── repositories/                    # 本业务数据访问与向量检索
├── models/
│   ├── collection.py                # 数据源与采集运行模型
│   ├── configuration.py             # Prompt、模型路由与模板模型
│   ├── content.py                   # 资讯、论文与审核事件模型
│   ├── governance.py                # 质量问题与重复内容治理模型
│   └── pipeline_models.py           # 情报域模型聚合导出
├── schemas/
├── contracts.py
├── policies.py
├── errors.py
├── collectors/
│   ├── rss.py
│   ├── http_api.py
│   └── websites/                    # 按实际来源编写具体采集器
├── processors/
│   ├── filter_audit.py              # 过滤结果规范化与审计
│   ├── geocoding.py                 # 地址解析与坐标转换
│   ├── simhash.py                   # 文本指纹与相似度
│   ├── normalization.py
│   ├── deduplication.py
│   ├── filtering.py
│   ├── classification.py
│   ├── extraction.py
│   ├── summarization.py
│   ├── vectorization.py             # 业务切分与向量写入编排
│   └── strategies/                  # InsightHub专题领域处理策略
├── runtime/
│   ├── business_time.py             # 业务时间快照
│   ├── health.py                    # Worker健康状态
│   └── logging_config.py            # Worker日志初始化
├── services/
│   └── model_generation.py          # LLM客户端、密钥轮换与生成重试
├── config/constants/                # 领域分类、坐标和文本替换资源
├── tasks/
│   ├── collect_source.py
│   ├── process_article.py
│   └── generate_digest.py
└── resources/
    ├── prompts/
    └── dictionaries/                # 停用词、主题词、规则资源
```

`services/processing.py` 决定一次处理任务如何执行各阶段；processor 实现具体算法；`ai/services/embeddings.py` 负责通用向量生成；情报 Repository 负责本业务的向量记录和查询；数据库扩展及连接由基础设施负责。

## 4. 层级依赖规则

### 4.1 请求和后台任务的调用关系

```text
HTTP API ─────────────┐
                      ├─> 业务Service ─> 本模块Repository ─> PostgreSQL
Worker任务处理函数 ────┤        │
CLI业务命令 ──────────┘        ├─> Processor / Parser / Exporter
                               ├─> AI公开服务 ─> 模型供应商适配
                               └─> Storage / Cache等基础设施

Scheduler ─> 业务的到期任务调度服务 ─> 创建持久化任务 ─> Worker领取
```

规则中的“依赖”包含直接和间接访问，不能通过包装函数掩盖越层数据库操作。

| 层 | 允许承担的职责 | 禁止或限制 |
| --- | --- | --- |
| API | 参数验证、认证依赖、服务调用、错误与响应转换 | 不写SQL、不做长耗时生成、不把供应商错误原样返回 |
| Service | 业务策略、对象级权限、事务与状态编排 | 不导入FastAPI Request/Response/Depends，不读取任意全局请求 |
| Processor等组件 | 具体算法或格式处理，必要依赖显式传入 | 不控制全局调度，不绕开服务修改其他模块数据 |
| Repository | 受限条件下查询、保存、flush和数据转换 | 不自己决定业务权限、不发送通知、不擅自commit |
| Models | 持久化结构、约束与关联 | 不创建HTTP路由、不调用外部服务 |
| Schemas | 接口字段、格式验证、序列化 | 不查询数据库、不包含业务工作流 |
| Infrastructure | 可复用技术实现与资源管理 | 不导入业务模块；通过注册或注入接受业务处理器 |

数据库 Session/客户端的构建和注入属于应用组装职责。API 可以使用获取资源或服务的依赖函数，但不能因为拿到了 Session 就直接查询数据。

### 4.2 跨模块协作

- `research` 通过 `library`、`intelligence` 的公开服务读取资料，通过 `ai` 获取模型能力。
- `intelligence`、`library` 按需要调用 `ai`，不导入 `research` 的内部实现。
- `ai` 不反向导入科研或情报服务。领域过滤标准由调用方传入。
- 各模块的认证入口可以使用 `system` 的公开认证能力；业务服务使用显式的操作者上下文，避免到处导入用户ORM模型。
- `system` 的运维页面调用通用监控机制，不反向导入每个业务Service。业务任务由所属模块提供管理接口。
- 已退役的代码生成器不参与应用启动和业务运行；业务代码不得重新依赖旧生成器入口。
- 跨模块只导入稳定服务和契约，不导入对方 Repository、API 或内部处理器。确需跨模块报表时，设计明确的只读查询服务，不由调用方直接拼接任意业务表。
- `bootstrap.py` 是集中组装点，可以了解各模块，负责注册路由、处理器和公开服务；不得演变成业务工作流大文件。

通过架构测试检查循环依赖、基础设施反向依赖、服务依赖HTTP框架、跨模块访问Repository等规则。

### 4.3 对象与事务

HTTP Schema 与 ORM 模型分开；跨模块服务不返回需要继续查询的惰性ORM对象。异步边界只传入可序列化标识和数据契约，不传 Session、Request 或数据库连接。

事务由顶层业务操作协调：多个 Repository 在同一事务中工作，内部不各自提交。向量或模型调用等长耗时工作分阶段完成；不跨网络等待长期占用事务。并发任务使用独立的 AsyncSession。

业务对象和对应持久化任务尽可能在同一事务中创建。需要向外部消息系统发布时，采用事务性发件箱或等价可恢复机制，避免业务已提交但任务未投递。

## 5. 入口、安装与生命周期

```text
entrypoints/
├── api.py                           # create_app和API启动函数
├── worker.py                        # Worker启动与优雅退出
├── scheduler.py                     # 定时调度进程
├── http/
│   ├── dependencies.py              # 请求相关依赖与服务注入
│   ├── middleware.py
│   ├── exception_handlers.py
│   └── responses.py                 # 跨业务HTTP响应协议
└── cli/
    ├── main.py                      # 原CLI命令入口的归属
    ├── commands/                    # 应用、数据库、任务和运维命令
    └── presentation/                # 输出、交互、补全和已有TUI适配
```

保留现有CLI行为并按职责逐步迁移，不能把大型CLI直接塞进一个 `cli.py`。各入口显式启动和关闭资源；导入普通业务模块不得自动连数据库、启动调度器、创建线程或执行迁移。

目标安装配置示意（当前正式配置已采用同一 `app` 包和显式包清单）：

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "pipesight-backend"
version = "0.1.0" # 示例；实施时沿用实际版本策略

[project.scripts]
pipesight-api = "app.entrypoints.api:main"
pipesight-worker = "app.entrypoints.worker:main"
pipesight-scheduler = "app.entrypoints.scheduler:main"
pipesight = "app.entrypoints.cli.main:main"

[tool.setuptools.packages.find]
where = ["src"]
include = ["app", "app.*"]
```

正式配置仍需持续补齐运行时Python约束、依赖和资源清单，验证模板、词表、字体、提示词等实际进入wheel。通过 `importlib.resources` 等包资源机制读取，不依赖当前工作目录。

开发使用可编辑安装；生产安装构建产物。完成迁移后的示例API入口为：

```sh
uv run uvicorn app.entrypoints.api:create_app --factory
```

`app` 是已确认的通用包名。每个部署使用独立虚拟环境或镜像，避免与其他同名包混装；当前已移除 `backend/app.py`，由 `src/app/entrypoints/api.py` 作为入口，`app/bootstrap.py` 负责应用组装和生命周期，`server.py` 仅提供旧导入兼容。以非源码工作目录下的安装包导入测试验证结果。

## 6. InsightHub融合与任务处理

### 6.1 迁移归属

| 现有来源 | 目标位置与处理 |
| --- | --- |
| `news_processor/main.py` | 已归并为 `app.intelligence.processing.main`，仍保持独立 Worker 进程入口 |
| `processors/manager.py` | `app.intelligence.processing.processors.manager` |
| `domain/` | `app.intelligence.processing.domain`；这里的 domain 是专题领域，不能直接等同 DDD 领域层 |
| `prompts/`、`supported_text/` | `app.intelligence.processing.prompts` 与 `app.intelligence.processing.supported_text` |
| `db/postgres.py`、`db/pgvector.py` | 连接管理进infrastructure，业务SQL进入情报Repository |
| `db/redis.py`、`db/minio.py` | 缓存、锁、存储基础设施 |
| `runtime/` | 分开消息传输、通用任务运行机制与情报任务契约 |
| `email_support/` | 邮件发送进入notifications；预警触发条件和业务记录归情报服务 |
| `models/news.py` | 区分业务契约与ORM数据模型，分别迁移 |
| `tests/` | 合入后端对应unit/integration测试，跨系统用例进入根目录e2e |
| PostgreSQL初始化SQL | 纳入统一数据库迁移，核对已部署版本 |
| 独立依赖、镜像配置 | 合入backend依赖及deploy；冲突版本需验证后统一 |

MySQL/Milvus历史代码先识别当前调用和迁移用途。只服务于历史导入的逻辑进入迁移脚本及隔离依赖；默认应用运行链不再依赖这些数据库。不因目录整理直接删除未核对的代码或数据。

### 6.2 统一流程

```text
数据源配置 → 手动触发/定时触发 → 采集任务
                                      ↓
                               原始记录与来源追踪
                                      ↓
                          持久化处理任务 → Worker领取
                                      ↓
                    标准化 → 精确去重 → 过滤/分类/提取
                                      ↓
                       摘要 → 向量化 → 按需语义去重
                                      ↓
                        发布可用情报与处理执行记录
                                      ↓
                         检索 / 简报 / 科研证据引用
```

此顺序是默认设计示意。语义去重依赖向量，领域过滤可能依赖其他前置结果，应由明确的阶段配置表达，不在多个入口各写一套流程。

任务采用可重复投递并保证业务幂等的设计，不宣称端到端“恰好一次”。领取需有并发保护、租约及过期恢复；同一逻辑结果应由唯一约束或幂等键防止重复写入。

### 6.3 状态、重试和结果

目标任务状态：`queued → running → succeeded / failed / cancelled`。重试生成新的执行尝试，保留历史错误、阶段结果、操作者和配置快照。业务成果另有状态：例如文章被过滤属于处理决策，不应混同系统执行失败。

必须记录任务ID、对象ID、尝试次数、阶段、起止时间、错误类别、配置版本和关联请求标识。可重试的超时/限流与永久参数错误分开；部分成功须明确哪些成果可用，不能统一标记完成。

API和Scheduler不直接执行长耗时采集或生成；API持久化任务后返回任务标识。Scheduler读取启用规则并提交到期任务，采用领导者租约和调度幂等键防止多实例重复提交。仅把任务放内存中不满足重启恢复要求。

取消操作由处理器在检查点响应；已发布结果不能由迟到的任务覆盖。资料权限在任务执行时按约定复核，服务身份须限定操作范围。

### 6.4 科研流程与证据

```text
情报/上传资料 → 资料篮引用 → 科研任务 → 证据快照
                                      ↓
                           模型生成 → 报告版本
                                      ↓
                         编辑/图表 → 保存版本 → 导出
```

证据快照保存来源标识、取得时间、内容摘要或必要片段、原内容版本及授权范围。原资料删除或权限变化如何影响已有成果，作为明确业务规则实现；不得将文件的永久公开URL作为快照替代品。

## 7. 提示词、模型和配置

| 配置类型 | 所在位置 | 规则 |
| --- | --- | --- |
| 默认过滤/分类提示词 | 情报resources | 随版本交付，作为初始化或显式回退来源 |
| 已发布业务提示词 | 所属业务数据库表 | 支持草稿、发布、版本追踪；执行时固定版本 |
| 报告结构与生成模板 | 科研resources及模板记录 | 和科研成果版本关联 |
| 模型目录、调用参数 | ai模块 | 配置允许的模型、能力、供应商和超时策略 |
| API Key、数据库密码 | 环境注入或受控密钥存储 | API/UI/日志不回显完整密钥 |
| 业务参数 | 所属业务模块 | 领域过滤阈值不挤进全局settings |
| 进程及外部连接配置 | settings | 按数据库、Redis、模型等分组，显式验证 |

管理员提示词页面调用所属业务的提示词服务。`ai` 提供模型调用和模板执行所需通用能力，但不拥有所有业务提示词。

处理记录关联提示词版本、模型标识、关键参数、处理规则版本及输入标识；配置快照排除密钥。无法获得供应商精确模型修订号时记录实际可取得的信息，不声称完全确定性重现。

前端构建变量都是公开配置，不承载后端密钥。关键连接配置缺失应在启动检查中报告，不静默回退到其他数据库或生产地址。

## 8. 数据库、文件与消息边界

- 应用运行数据统一使用 PostgreSQL，向量能力使用 pgvector；Redis承担缓存、锁等明确职责。
- 业务模型和SQL归所属模块；`infrastructure/database/` 只维护连接、会话、基类、通用事务支持。
- 统一Alembic迁移入口。保留现有revision身份与升级链，不能为整理目录修改已执行迁移的含义。
- 现有 `public`、`news` schema可以先兼容保留。统一工程不等于立刻合表；每类数据应明确权威来源及引用方式，逐步消除重复事实和双向同步。
- `deploy/postgres/` 仅负责实例/角色/扩展等基础设置；业务表版本归migrations，避免Compose初始化SQL与Alembic双重维护。
- 普通API或Worker启动不自动执行生产DDL；迁移通过受控部署步骤执行，多个API副本不竞争建表。
- 上传文件保留在私有存储，下载由library服务检查权限。基础设施只读写对象，不决定谁有权访问。
- Kafka按实际输入/输出需要作为消息适配保留，不作为默认启动必须项。PG任务机制与Kafka输入必须共享业务处理服务，并明确消息确认时机。
- 外部消息只在结果或可恢复接收状态持久化后确认；重复消息依靠幂等机制处理。

## 9. 前端详细归属

前端保留既有 Vue 3、JavaScript、Vite、Pinia 和现有UI组件使用情况，不借本次整理重新选择UI库。统一业务术语，但前端目录无需复制后端的全部层级。

```text
frontend/src/
├── api/
│   ├── system/
│   ├── intelligence/
│   ├── library/
│   ├── research/
│   ├── ai/
├── views/
│   ├── portal/                      # 普通用户入口
│   │   ├── home/
│   │   ├── intelligence/            # 新闻、论文、检索
│   │   ├── library/                 # 上传资料、详情、下载
│   │   ├── research/                # 资料篮、任务、报告编辑
│   │   ├── digests/
│   │   └── profile/
│   ├── system/                      # 管理端系统功能
│   ├── intelligence/                # 数据源、处理规则、运行记录等
│   ├── library/                     # 管理端资料管理
│   ├── research/                    # 模板、任务、报告管理
│   ├── ai/                          # 模型管理
│   ├── monitor/                     # 通用运维页面
│   └── error/                       # 401、404等公共错误页
├── components/                      # 真正跨页面的组件
├── composables/                     # 如任务轮询、分页状态
├── router/
├── store/
├── layout/
├── directive/
├── plugins/
├── assets/
└── utils/
```

登录、注册等现有公共页面也保留，按实际页面入口归位。只被单一页面使用的组件放页面附近，避免所有组件进入全局components。

API封装只负责请求和数据协议；页面展示和交互留在views；持久共享状态留在Pinia。前端权限用于交互控制，后端仍必须执行授权。

内部目录重命名不要求同步修改 `/pipeline/*`、`/portal/*` 等外部URL。保持API路径、请求响应字段、权限标识和路由名称的兼容；若修改前端页面位置，必须同步数据库菜单中的组件映射、动态import和导航测试。

## 10. 部署、运行数据与资源管理

目标部署包含前端、API、Worker、Scheduler、PostgreSQL/pgvector、Redis；对象存储和外部消息服务按实际需要启用。

- API负责HTTP请求；Worker处理持久化任务；Scheduler创建到期任务。三个入口使用同一个应用版本，分别配置资源和副本数。
- 根目录为镜像构建上下文时，Dockerfile与`.dockerignore`必须同步；Compose移动后须明确项目目录、相对路径和env文件解析方式，并通过渲染结果核对。
- Compose项目名、卷名、端口和数据库挂载改变前先核对所有权。重构不能新建空卷后误认为旧数据丢失，也不能直接删除旧卷。
- 标准输出记录结构化运行日志；本地文件日志进var或配置位置。日志不进入Git和应用包。
- 健康检查区分进程存活与依赖就绪，避免任何外部模型短暂异常都使所有进程不断重启。
- 关闭Worker时停止领取新任务，限时等待在途任务，释放或使租约可恢复。
- 包内只带运行必需资源；文档、历史导出、上传文件和测试数据不随生产包发布。

## 11. 命名、脚本与代码约定

| 对象 | 规则 | 示例 |
| --- | --- | --- |
| Python包、文件、函数、变量 | 小写snake_case，描述职责 | `generate_report.py`、`normalize_text` |
| Python类 | PascalCase | `ReportService`、`ArticleRepository` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRY_ATTEMPTS` |
| 分层目录 | 固定复数词 | `services`、`repositories`、`schemas` |
| 层内文件 | 业务对象名，避免重复层名 | `services/reports.py` |
| 前端组件 | PascalCase | `ReportEditor.vue` |
| 前端组合函数 | use开头 | `useTaskPolling.js` |
| 脚本 | 动词+具体对象 | `backfill_article_embeddings.py` |
| 测试 | test前缀+行为主题 | `test_report_access.py` |

统一使用Repository作为数据访问层称呼，不同时建立同一职责的dao与repository。保留合理的Python函数，不为所有函数包装无状态类；只有实际替换实现或隔离外部边界时才引入Protocol/接口。

禁止新增含义不明的 `utils2.py`、`new_service.py`、`test1.py`。纯算法按具体职责命名；确需公共工具时，限定在所属业务或技术目录中，不再建立无限扩展的全局common。

脚本示例：

```text
backend/scripts/imports/import_legacy_news.py
backend/scripts/backfills/backfill_article_embeddings.py
backend/scripts/migrations/migrate_legacy_insighthub.py
scripts/dev/start_services.sh
scripts/dev/start_services.ps1
scripts/checks/check_project.sh
scripts/ops/backup_postgres.sh
```

一次性数据脚本需支持明确范围、批次、幂等或断点、执行摘要；有修改风险时提供预览/试运行。脚本调用应用服务或明确的数据迁移接口，不复制一套生产业务逻辑。重复使用的管理能力进入CLI。

## 12. 现有目录迁移映射

| 现有目录或文件 | 目标归属 | 注意事项 |
| --- | --- | --- |
| `src/app/entrypoints/api.py`、`app/bootstrap.py`、`server.py` | entrypoints/api、bootstrap | 应用工厂已归属 `app.bootstrap`；`server.py` 仅保留兼容导入 |
| `module_admin`、`module_pipeline`、`module_manuscript`、`module_ai` | 已退役 | 正式实现已分别归属 `app.system`、`app.infrastructure`、`app.intelligence`、`app.library` 和 `app.research`；旧包目录已删除，避免维护两套导入路径 |
| `module_task` | 已退役 | 原若依示例任务已移除；调度函数统一位于 `app.*`，旧数据库任务由迁移停用 |
| `module_generator` | 已退役 | 代码生成器依赖的数据库表、API、前端页面和 CLI/TUI 入口已清理；数据库迁移历史保留 |
| `backend/cli` | entrypoints/cli及相应服务 | 保留已有命令契约、交互与测试，逐步解除路径注入 |
| `backend/cli/utils.py` | `cli/output.py`、`cli/runtime/nested_cli.py` | 文本格式化与内部 CLI 子进程支持分别归属输出层和 CLI 运行时，不恢复泛化工具文件 |
| `config` | settings、bootstrap和基础设施 | 数据库连接配置不能反向调用业务模块 |
| `common/constant.py` | `common/constants.py`、`common/http/status.py`、`common/http/contracts.py`、`app.system.constants` | 通用运行常量、HTTP 状态/接口契约和系统菜单常量分别归属，不恢复混合常量文件 |
| `common/enums.py` | `common/enums/http.py`、`common/enums/audit.py`、`common/enums/cache.py` | HTTP 方法、审计业务类型和 Redis 键配置分别归属，不恢复混合枚举文件 |
| `common`、`exceptions`、`middlewares` | HTTP入口适配、业务errors或中间件 | `common/http` 承载 HTTP Schema、响应、请求上下文、依赖和路由；全局 `utils` 已清空，不再恢复 |
| `sub_applications` | entrypoints及对应工具集成 | 核对挂载路由、权限与静态资源 |
| `insighthub` | 情报业务、ai、基础设施、后端测试 | 见第6节，不保留第二套应用根 |
| `backend/alembic`、`backend/sql` | migrations及历史迁移脚本 | 保留已部署revision，核对初始化路径 |
| `backend/assets` | 所用业务的resources | 字体等需验证打包、许可与实际引用 |
| `vf_admin`、logs、上传导出目录 | 配置化var/卷/对象存储 | 属于运行数据，单独迁移与校验，不随git移动 |
| 根Compose、各Dockerfile、Nginx配置 | deploy | 同步所有相对路径与启动文档 |
| 根图片目录、backend专项docs | 文档资产或前端资产、统一docs | 逐项识别用途并修复链接 |

## 13. 实施顺序、风险与验收

| 阶段 | 工作与交付 | 必须通过的验证 |
| --- | --- | --- |
| 1. 建立基线 | 记录当前变更、入口、路由、权限、任务函数、数据库版本与文件引用 | 核心现有流程可复现，区分已有失败与迁移回归 |
| 2. 统一安装和入口 | 建立src/app，迁移包配置、资源管理和入口；必要兼容层显式登记 | 构建安装成功；非源码工作目录可导入；旧 app.py 不遮蔽；API/CLI入口可用 |
| 3. 按业务纵向拆分 | 每次完整迁移一组API、服务、Repository、模型和测试 | 旧API契约、鉴权、事务、查询及前端调用不回归 |
| 4. 融合数据处理 | 统一InsightHub配置、算法、任务、模型调用及数据权威来源 | 重复输入、过滤、超时、失败恢复、并发领取和向量写入验证 |
| 5. 统一科研与资料 | 迁移上传权限、资料篮、证据、报告和旧文稿适配 | 普通用户越权检查；创建、取消、重试、编辑、版本与导出闭环 |
| 6. 部署和辅助能力 | 迁移Compose、生成器模板、CLI、菜单组件映射与运行目录 | 配置渲染、资源路径、卷归属、动态菜单和生成代码检查 |
| 7. 清理与交付 | 删除已无调用的兼容入口，整理依赖和文档 | 无旧导入/任务路径遗留；全部适用检查通过；记录未验证项 |

每阶段保持可运行，不能仅为了目录整齐一次性搬完后再修。兼容层有明确调用方和退出条件，不允许复制并长期保留两套业务实现。

数据库变更采用兼容扩展、回填、切换、清理步骤；代码回退依赖数据库仍兼容。涉及不可逆数据变换时先验证备份和恢复，不以git回退代替数据恢复。

## 14. 完成标准

以下是持续验收清单。已标记项目有当前架构测试或运行验证作为依据，其余仍需按真实业务流程补充证据：

- [ ] 后端只维护一套应用依赖锁定；若输出requirements，必须由依赖配置生成。
- [ ] API、Worker、Scheduler、CLI从同一个已安装app包启动。
- [ ] 不需要修改sys.path或依赖源码工作目录；包内资源在wheel安装后可读取。
- [x] 不再依赖module_*扫描；显式注册路由，旧模块目录和导入残留有架构测试约束。
- [x] 全局 `backend/utils/` 不再包含 Python 模块，打包清单和活动代码无 `utils` 导入。
- [ ] 分层依赖和跨模块访问规则有自动检查，现有循环依赖已处理。
- [ ] 采集、清洗、过滤和持久化只有一套业务入口，处理结果可追溯。
- [ ] PG迁移覆盖空库和既有库升级；向量扩展、索引与数据引用有效。
- [ ] 后台任务在重启、超时、重复投递、取消后有可解释的恢复行为。
- [ ] 登录与验证码、普通用户权限、资料授权下载通过实际接口验证。
- [ ] 资料发现、资料篮、科研任务、编辑、历史版本与导出完成浏览器验收。
- [ ] 提示词配置可发布和追溯，密钥不会经接口或日志泄漏。
- [ ] 前端动态菜单、路由、组件路径和构建有效；现有UI功能无意外删除。
- [ ] 如未来恢复代码生成能力，必须单独完成需求、权限、模板版本和输出目录设计后再实现；当前版本不提供该能力。
- [ ] 生产包、镜像和Git不包含上传文件、真实密钥、缓存或本地虚拟环境。
- [ ] 文档标明实际启动命令、部署升级顺序、备份恢复及已知限制。

## 15. 新代码放置速查

| 新需求 | 放置位置 |
| --- | --- |
| 新增一个新闻来源 | intelligence/collectors及数据源配置 |
| 改进过滤或去重算法 | intelligence/processors |
| 新增提示词管理接口 | intelligence/api、services、repositories对应对象 |
| 接入新模型供应商 | ai/providers，通过ai服务提供能力 |
| 新增文件格式解析 | library/parsers |
| 增加报告生成步骤 | research/services和必要处理组件 |
| 增加报告导出格式 | research/exporters |
| 支持另一种文件存储 | infrastructure/storage |
| 增加定时业务 | 所属业务的任务提交服务，注册到Scheduler |
| 新增普通用户页面 | frontend/src/views/portal对应业务目录 |
| 修复公共鉴权行为 | system认证服务与entrypoints/http依赖，按职责划分 |
| 添加一次性数据修复 | backend/scripts/backfills或migrations |

本文定义后续开发和重构的目标。具体迁移提交应说明完成的阶段、验证证据和仍存在的兼容代码，不能把目录创建视为整个架构已经落地。
