# PostgreSQL 与 PDF 完整回归环境

默认测试保留外部环境开关。完整验收使用专用命令，一次启用所有 PostgreSQL 用例，且 **任何失败、错误或跳过都会使验收失败**。

## 依赖与私有测试材料

在仓库根目录安装锁定的开发依赖（包含 PyMuPDF）：

```sh
uv sync --project backend --group dev --locked
```

需要已验证的旧版数据库快照目录，其中包含 `database-before.dump` 和 `database-before.json`（47 张旧表、行指纹和 dump SHA-256）。这些包含业务数据的文件只在本地保留，不提交 Git。

PDF 用例使用以下两份原始文件，存放于 `output/pdf/paper-fulltext-20261017/`：

- `coatings-14-00358.pdf`
- `pipeline-inspection-review-2024.pdf`

官方来源 URL 和 SHA-256 位于 `backend/data/curated/paper-fulltext-previews.json`。完整命令先验证原件存在且哈希一致，不以伪造 PDF 或减少断言替代真实文档验收。

## 隔离的 PG18 容器

当前专用容器为 `pipesight-schema-rehearsal-ythnjxpi`，镜像 `pgvector/pgvector:pg18`，标签 `pipesight.schema-rollout=ythNjXpI`，端口只绑定 `127.0.0.1:19432`。可以恢复这个已有容器：

```sh
docker start pipesight-schema-rehearsal-ythnjxpi
```

连接 JSON 必须为私有文件（权限 `0600`），字段为 `host`、`port`、`user`、`password`、`dbname`；其中固定 `host=127.0.0.1`、`port=19432`、`dbname=pipesight_rehearsal`。脚本还会检查容器标签和真实端口绑定。不要复用应用的 `.env` 或 `25432` 数据库。

## 准备与运行

本地现有快照可直接使用默认路径：

```sh
backend/.venv/bin/python backend/scripts/run_pg_rehearsals.py
```

指定独立的私有材料路径：

```sh
backend/.venv/bin/python backend/scripts/run_pg_rehearsals.py \
  --snapshot-dir /private/path/legacy-snapshot \
  --connection-file /private/path/rehearsal-connection.json \
  --evidence-dir .runtime/pg-acceptance
```

命令会创建随机后缀的两个新库：`pipesight_compact_pgtest_*` 保留旧结构供迁移、故障注入与回滚测试；`pipesight_beijing_pgtest_*` 从同一快照通过真实 Alembic CLI 完成 compact、若依表名、数字 ID、业务约束、北京时间及最新迁移，供当前 ORM 的集成测试使用。每个受保护迁移前均保存一致性快照、SHA-256 和行指纹。

原 `pipesight_rehearsal` 和已有数据库不会被恢复覆盖或删除。采集、分页、报告保存的测试数据在外层事务结束时回滚；不调用真实采集网站或模型服务。独立库和私有证据保留供复核。

准备成功会输出私有 `manifest.json` 的路径。修复后可以复用该环境：

```sh
backend/.venv/bin/python backend/scripts/run_pg_rehearsals.py \
  --manifest /private/path/run-xxxxxxxxxxxx/manifest.json
```

证据目录包含每步 Alembic 日志、迁移备份及全量 `pytest.xml`。凭证、原始快照和运行产物均不提交仓库。用 `--prepare-only` 可以只准备环境。

## 单独运行数据库注释演练

仅验证历史注释更新时，不需要 PDF 原件或 PDF 解析依赖：

```sh
backend/.venv/bin/python backend/scripts/run_pg_rehearsals.py \
  --comments-only \
  --snapshot-dir /private/path/legacy-snapshot \
  --connection-file /private/path/rehearsal-connection.json \
  --evidence-dir .runtime/pg-comment-acceptance
```

也可用 `--comments-only --manifest /private/path/run-xxxxxxxxxxxx/manifest.json` 复验已经准备好的隔离环境。复用的当前库必须已完成最新迁移；旧结构应从历史快照新建演练库后再测。

该命令保留同一套容器、端口和随机数据库名称校验，不读取应用 `.env`。每次运行前另外保存 `comments-backup-*` 一致性备份，再实际执行 `test_comment_only_pg18_updates_preserve_every_business_row`，不会仅做静态检查或取消跳过条件。

测试连续两次应用当前注释，核对每张表的全部行指纹、表与字段注释、目录视图注释；任何失败或跳过均视为验收失败。结果保存在 `pytest-comments.xml`，完整回归命令仍会校验两份原始 PDF 并要求零跳过。
