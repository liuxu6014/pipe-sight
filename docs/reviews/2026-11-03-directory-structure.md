# main 目录整理验证

整理前基线：`79c3bc7dcc18fbe32bdd65a063ea9eb7ca4782d5`。

## 整理范围

- 迁移 32 个文件：镜像和代理配置集中到 `deploy/`；仓库级开发及检查脚本归入 `scripts/dev/`、`scripts/checks/`；后端维护工具按用途分组；设计、指南、交接和文档图片归入 `docs/`。
- 同步更新测试夹具路径、脚本根目录定位、Compose 引用和文档链接。每个移除的旧路径均已核对对应新文件，没有保留重复入口。
- 应用业务包、若依模块、Alembic 历史和运行数据路径保持原位。本次未执行数据库维护、迁移、采集或生成任务，未重启服务。

当前结构与放置规则见 [项目结构](../project-structure.md)。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| 前端生产构建 `npm run build:prod` | 通过 |
| Windows 开发脚本回归 `node --test tests/pipeline-dev-runtime.test.js` | 3 项通过；未在 Windows 实机启动 |
| 迁移后的 16 个 Python 脚本语法解析 | 通过 |
| 仓库验证脚本 `bash -n` | 通过 |
| local、PostgreSQL、MySQL 三套 Compose 解析对比 | 仅文件位置引用变化；其余解析后的配置一致 |
| Dockerfile 和 Nginx 文件内容对比 | 搬迁前后逐字节一致；未重新构建镜像 |
| 迁移清单、新文档相对链接、`git diff --check` | 通过 |
| 相关后端测试 | 109 项通过、2 项跳过、4 项既有失败 |

后端测试范围：`test_authorized_article_full_text.py`、`test_curated_content_import.py`、`test_prepare_licensed_papers.py`、`test_publisher_text_extraction.py`、`test_system_schema_rollout.py` 和 `architecture/test_app_package_layout.py`。从 `backend/` 使用 `PYTHONPATH=src:. .venv/bin/python -m pytest` 执行这些文件。

4 项失败集中在 `test_system_schema_rollout.py`：`SysUser` 字段附录、外键关系、冻结结构契约和用户持久化夹具未与恢复部门管理后的 `sys_dept` / `dept_id` 对应。用整理前提交的独立源码快照、同一 Python 环境和同一测试命令复核，结果同为 109 项通过、2 项跳过、4 项失败。本次未修改这些业务契约或测试预期。

以上为目录移动的针对性验证，不代表全量测试、真实登录页面或容器部署验收已全部通过。
