# 文档目录

项目文档按用途归类，运行代码位于根目录的 `backend/` 和 `frontend/`；InsightHub 处理 Worker 已归入 `backend/src/app/intelligence/processing/`。

长期重构以 [项目目标结构与分层开发规范](architecture/project-structure-and-layering.md) 为依据：后端包名为 `app`，目标源码布局为 `backend/src/app/`。当前已建立可安装包和 API 入口，业务模块仍按迁移阶段逐步移动。该文档说明目标目录、分层、InsightHub融合及迁移验收；不代表全部代码已经迁移。

| 目录 | 内容 |
| --- | --- |
| `architecture/` | 系统架构、数据库技术说明、PostgreSQL 环境和冷热数据设计 |
| `requirements/` | 需求规格、原型、客户确认表和设计方案 |
| `reference/` | 模板、示例文件和撰写指南 |
| `plans/` | 开发计划、实施方案、菜单种子 SQL 和阶段性设计 |
| `handover/` | 交接说明、数据库设计和部署适配资料 |
| `reports/` | 项目进度汇报及双周汇报材料 |
| `project-structure.md` | 当前代码、部署和文档结构说明 |

## 全量功能需求核对

- [全量功能需求逐项核对文档 V0.6（2026-10-12）](requirements/2026-10-12-全量功能需求逐项核对文档.md)：按用户功能与管理员功能分两部分，以功能名称为标题。用户侧7项；管理员侧按管理首页、用户管理、采集管理、过滤管理、数据管理、资料库管理、报告管理、简报管理、模板管理、系统配置、运行日志这11项展开。涵盖107项功能说明、45个需求问题和22个业务场景；不保留重复功能编号、核对记录、填写栏和登记表，功能关联使用名称。仅有管理员和用户两种角色，具体权限和功能规则继续逐项讨论，不包含人力取舍、开发分期或排期；需求确认不代表功能已完成。
- [可编辑Word需求核对文档](requirements/2026-10-12-全量功能需求逐项核对文档.docx)：与Markdown同内容，便于阅读和批注。

## 历史开发范围讨论稿

以下V0.1保留用于追溯，不作为本轮全量需求核对的分期依据。

- [功能开发范围与逐项确认讨论稿（2026-10-12）](requirements/2026-10-12-功能开发范围与逐项确认讨论稿.md)：用于与领导和业务人员确认开发范围，包含95个功能确认项、30个关键决策问题、14个业务验收场景及会议记录模板；建议不等于已确认需求，也不代表当前功能已经完成。
- [可编辑Word讨论稿](requirements/2026-10-12-功能开发范围与逐项确认讨论稿.docx)：适合会议批注和逐项记录。

## 当前功能核对

- [报告正文与引用格式](architecture/report-format.md)：新报告生成入库、页面和 Word、PDF 共用的缩进、句末角标和引用去重规则。

- [项目功能说明与逐项核对清单（2026-10-12）](requirements/2026-10-12-项目功能说明与逐项核对清单.md)：按当前源码梳理门户、管理、采集处理、资料库、科研报告、简报、权限及运维能力，附实现边界和全流程验收步骤；不是全部功能已经通过运行验收的证明。

## 数据库规范与字段说明

- [PostgreSQL 数据字典](architecture/database-dictionary.md)：由实际数据库目录导出，列出全部表、视图及字段的中文说明、类型、默认值和外键。
- [简短表名规范](architecture/table-naming.md)：11张应用业务表的简化映射、历史SQL与迁移维护边界。
- [配置主来源与处理边界](architecture/configuration-ownership.md)：区分已经接入的提示词快照路径与尚待整合的领域分类、评分及历史配置。
- [命名与注释规范化方案](plans/2026-10-14-database-naming-and-comments.md)：表名映射、兼容边界和迁移验证。
- 新字段必须在 ORM 或处理域建表 SQL 中声明，并同步补充 `backend/sql/application-comments-pg.sql` 或 `backend/sql/processing-comments-pg.sql` 及新的迁移；禁止仅在数据库客户端手工改注释。
- 新环境完成基础 SQL 初始化后必须执行 `alembic upgrade head`。运行 `backend/scripts/export_database_dictionary.py --env dev --check` 可检查当前配置库；缺少注释或仍存在历史物理表时返回失败。该检查不导出业务记录。

## 代码入口

- `backend/`：FastAPI 后端及管网业务模块。
- `frontend/`：Vue 3 管理端和用户门户。
- `backend/src/app/intelligence/processing/`：PostgreSQL Worker、领域处理器、Prompt、向量写入和运行时。

根目录的 `docker-compose.pg.yml` 是默认 PostgreSQL 运行入口；`docker-compose.my.yml` 仅用于历史 MySQL 迁移验证。
