# 2026-11-14 剩余回归失败修复

继续处理此前记录中的前端 16 项、后端 36 项失败。该记录取代同日网页验收记录中关于“仍有基线失败”的当前状态描述；保留此前验收记录作为历史证据。

后续已补齐全部跳过项环境，最新结果见 [PostgreSQL/PDF 完整回归验收](2026-11-14-pg-full-acceptance.md)：1841 通过，0 失败、0 跳过。本页下方保留首次修复时的历史结果。

## 修复

- 历史数值编号迁移原先引用可变的当前表清单，新增部门表后会拒绝旧库的合法备份。固定使用迁移当时的 v3 注释快照和 29 表契约，保留备份校验、保存点、回滚和不提交调用方事务的保护，新增历史清单隔离回归。
- 当前数据库契约已到 v14。重新生成注释 SQL，补齐论文独立摘要、模板报告类型的字段注释；版本和字段总数由当前契约生成。仍逐字段对比 ORM、契约和 SQL，保留历史快照哈希断言。
- 用户 ORM 的部门字段按实际追加顺序定义，补齐设计附录和内存 SQLite 测试的部门表依赖。未删除字段、外键或部门管理功能。
- 迁移测试提供真实调用所需的表反射边界；采集入队测试隔离模型用途快照边界，同时断言快照被校验并传给入队仓库。设置 pytest 本地导入路径，使单独运行用例不依赖其他测试先导入 CLI。
- 报告回归改为当前无井号的章节格式，继续验证原文段落、章节、真实参考资料、保存元数据和幂等性。
- 前端测试对齐已确认的四步报告流程、分类在实体首位、模板报告类型持久化、独立模型/类别导航，以及 Element Plus 操作组件和分页列表；保留权限、路由副本不被修改、来源链接安全及分页断言。
- 目录辅助文字与实体补充标记最小字号调至 13px；日期范围内部输入继续由组件外层统一显示焦点，不增加内框。

## 验证结果

| 验证 | 结果 |
| --- | --- |
| 前端全量 `cd frontend && npm test` | 659 通过，0 失败、0 跳过 |
| 后端全量 `cd backend && .venv/bin/pytest tests -q --tb=short` | 1806 通过，0 失败、30 跳过 |
| 前端生产构建 `cd frontend && npm run build:prod` | 通过，9.71 秒 |
| 本次全部 Python 修改文件 Ruff | 通过 |
| `git diff --check` | 通过 |

当时后端 30 项跳过中，28 项需要显式启用的独立 PostgreSQL 演练/集成环境，2 项缺少 PyMuPDF。本轮未新增跳过或 xfail，也未将旧失败改成跳过。本轮没有对用户业务库执行历史编号迁移、DDL 或资料删除；首次修复阶段的迁移事务保护仅由离线边界与保存点回归验证。后续真实 PostgreSQL 演练结果见上方最新记录。

完整本地日志位于 `.runtime/regression-closure-20261114/`，不提交日志和生成文件。

## 网页复验

用户恢复登录后，使用真实浏览器完成以下复验：

- 论文列表初始 3 条，无“重置筛选”；输入“超声”后匹配 2 条并显示重置，点击后恢复 3 条且重置按钮消失。DOI 原文链接、加入资料库操作和分类在首位的实体区域正常显示。
- 从科研报告列表进入新建流程，基本信息、选择资料、选择模板、确认大纲与写作要求按顺序显示。仅选取新闻 18 和论文 26 两条公开资料；选择科研需求报告中的具体模板后，正文和全部 6 章提示词自动填充，摘要信息中的类型与具体模板分开显示。本轮未提交新生成任务。
- 返回已有报告 169，确认六章、预算表和引用仍正常显示；之前保存的验收原句只出现 1 次。当前窄屏布局中的目录和字号可读。

截图证据：`.runtime/regression-closure-20261114/报告复验.png`。浏览器保留在 `/portal/research/reports/169`。API 就绪检查正常，PostgreSQL、Redis 均可用。

## 原失败项归属

| 前端用例文件 | 原失败数 |
| --- | --- |
| permission-store | 2 |
| pipeline-intellinews-layout | 6 |
| pipeline-manuscript-page | 1 |
| pipeline-portal-real-interactions | 1 |
| processing-prompt | 1 |
| research-workbench-ui | 1 |
| source-list-layout | 1 |
| workspace-design | 3 |
| 合计 | 16 |

| 后端用例文件 | 原失败数 |
| --- | --- |
| test_application_schema_comments | 6 |
| test_business_schema_models | 1 |
| test_filter_audit_migration_identity | 1 |
| test_numeric_id_transactions | 11 |
| test_pipeline_domain_service | 1 |
| test_portal_article_cover_and_filters | 2 |
| test_report_content_normalization | 5 |
| test_research_report_functional_integration | 1 |
| test_research_report_metadata | 2 |
| test_scheduler_chat_canonical | 1 |
| test_short_table_names | 1 |
| test_system_schema_rollout | 4 |
| 合计 | 36 |

上述用例均参加最终全量执行并通过。后端总数较此前增加 1 项，来自新加的历史迁移清单隔离回归；其余原测试没有删除或跳过。
