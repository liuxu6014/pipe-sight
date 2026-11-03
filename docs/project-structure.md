# 当前代码目录结构

本文件对应当前 `main` 的实际目录。历史方案见 [目标结构与分层规范](architecture/project-structure-and-layering.md)，新增代码的具体落点见 [代码地图](architecture/code-map.md)。

```text
pipe-sight/
├── backend/                     # Python 后端工程
│   ├── src/app/                 # 正式应用包
│   │   ├── entrypoints/         # API、任务进程入口
│   │   ├── system/              # 若依身份、权限及系统管理
│   │   ├── intelligence/        # 采集、内容处理与情报
│   │   ├── library/             # 上传资料和解析
│   │   ├── research/            # 报告、简报及生成
│   │   ├── infrastructure/      # 数据访问、日志等基础能力
│   │   ├── health/              # 健康检查
│   │   └── tooling/             # 应用工具
│   ├── common/                 # 公共 HTTP 契约等支持模块
│   ├── config/                 # 配置和模型发现
│   ├── cli/                    # 命令行入口
│   ├── middlewares/            # 中间件适配
│   ├── exceptions/             # 异常适配
│   ├── alembic/                # 按历史顺序保留的正式迁移
│   ├── sql/                    # 初始化 SQL
│   ├── scripts/                # 按用途分组的维护脚本
│   ├── tests/                  # 后端测试及架构约束
│   ├── data/                   # 受版本控制的资源与冻结结构快照
│   ├── pyproject.toml          # Python 依赖及打包配置
│   └── uv.lock                 # 依赖锁定
├── frontend/                    # Vue 3 + Element Plus 前端工程
│   ├── src/
│   │   ├── api/                # 请求封装
│   │   ├── router/             # 路由
│   │   ├── store/              # 状态管理
│   │   ├── views/              # 管理端及用户门户页面
│   │   ├── components/         # 共用 UI 组件
│   │   ├── utils/              # 通用工具
│   │   └── assets/             # 样式、图标等资源
│   ├── public/                 # 静态公共资源
│   ├── tests/                  # 行为检查及 UI 预览
│   ├── bin/                    # 前端独立工程的辅助命令
│   └── package.json
├── deploy/
│   ├── docker/                 # 前后端 Dockerfile
│   └── nginx/                  # PostgreSQL/MySQL 部署的代理配置
├── scripts/
│   ├── dev/                    # 跨服务开发环境启动、停止
│   └── checks/                 # 跨工程验证入口
├── docs/                       # 项目文档、设计和交接资料
├── docker-compose.local.yml    # 本地基础设施
├── docker-compose.pg.yml       # PostgreSQL 部署入口
├── docker-compose.my.yml       # 历史 MySQL 部署入口
└── README.md                   # 项目介绍及启动指南
```

树中省略不影响分层说明的文件；后端现有时间、业务 ID、结构迁移模块仍保留在 `app` 包内。

## 放置规则

| 内容 | 位置 | 约定 |
| --- | --- | --- |
| 运行中的业务逻辑 | `backend/src/app/` 对应业务域 | 保持现有 API、Service、Repository 等分层；不放入维护脚本 |
| 路由页面及共用组件 | `frontend/src/views/`、`frontend/src/components/` | 门户局部复用组件留在 `views/portal/components/` |
| 后端批量维护工具 | `backend/scripts/` | 分为 `bootstrap`、`imports`、`backfills`、`checks`、`migrations`、`papers`，见[脚本清单](../backend/scripts/README.md) |
| 联合启动和验证 | `scripts/dev/`、`scripts/checks/` | 根据脚本位置定位仓库根目录，不依赖调用者工作目录 |
| 镜像与代理配置 | `deploy/docker/`、`deploy/nginx/` | 构建上下文仍为后端或前端工程，见[部署说明](../deploy/README.md) |
| 设计与操作说明 | `docs/architecture/`、`docs/guides/` | 面向当前代码；历史交接和验收记录分别放 `handover/`、`reviews/` |
| 文档图片 | `docs/assets/` | 与前端运行资源分开 |

## 稳定入口与数据边界

- Compose 文件保留在仓库根目录，维持环境文件、项目名和挂载路径的解析方式。只调整 Dockerfile 与 Nginx 配置的引用。
- 后端启动入口、Python 包名、数据库迁移历史、环境文件和附件路径不随本次整理改变。
- `.runtime/`、`logs/`、`output/`、`node_modules/`、`.venv/` 和构建产物不作为业务源码目录；本次不清理本地运行数据。
- 数据库设计文档现位于 [精简数据库设计](architecture/compact-database-design.md)。`backend/data/schema/` 冻结快照中的旧 `source` 路径保留为生成时的溯源信息，不用于定位当前文档，也不因文件搬迁修改快照。
- 移动文件应同步修改代码导入、测试夹具、脚本根目录计算、部署引用及文档链接；不得通过复制旧文件维持两套入口。

## 验证入口

从仓库根目录执行 `bash scripts/checks/verify_project.sh`，依次运行后端测试、前端测试和前端构建。开发环境启动方式见 [根目录说明](../README.md) 及 [开发脚本说明](../scripts/README.md)。维护脚本中的导入、回填和迁移命令可能写入数据，不能作为无副作用的目录检查执行。
