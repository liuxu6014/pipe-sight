# 本地 Docker 数据库

当前开发环境使用独立的 `docker-compose.local.yml`。API 和 Task Worker 在宿主机运行，业务库和 InsightHub 库均连接本机 PostgreSQL，不依赖远程数据库或 VPN。

| 服务 | 地址 | 配置 |
| --- | --- | --- |
| 门户 | http://127.0.0.1:12580/portal | `frontend/.env.development.local` |
| API | http://127.0.0.1:9099 | `backend/.env.dev` |
| PostgreSQL 18 + pgvector | `127.0.0.1:25432`，库 `pipesight` | `backend/.env.dev` 中的 `DB_*` |
| InsightHub 数据库 | 同一 PostgreSQL，schema `news` | `backend/.env.dev` 中的 `INSIGHTHUB_DB_*` |
| Redis | `127.0.0.1:26379`，API 使用 DB 3 | `backend/.env.dev` 中的 `REDIS_*` |

数据库密码保存在 Git 忽略的本地环境文件中，Compose 从该文件读取。PostgreSQL 和 Redis 仅绑定回环地址，数据分别保存在 `pipesight-local_postgres-data`、`pipesight-local_redis-data` 命名卷。

## 启动

在项目根目录启动数据库和 Redis：

```sh
docker compose --env-file backend/.env.dev -f docker-compose.local.yml up -d --wait
```

API、Worker、前端分别在独立终端启动；已有进程运行时不必重复启动：

```sh
# API，工作目录 backend
PYTHONPATH=src .venv/bin/python -m app.entrypoints.api --env=dev

# Task Worker，工作目录 backend
PYTHONPATH=src .venv/bin/python -m app.entrypoints.task_worker --env=dev

# 前端，工作目录 frontend
npm run dev -- --host 127.0.0.1 --port 12580 --strictPort
```

停止容器并保留数据：

```sh
docker compose --env-file backend/.env.dev -f docker-compose.local.yml stop
```

需要保留当前数据库时不要使用 `down -v`。当前本地开发使用上述独立 Compose 文件；既有 `docker-compose.pg.yml` 保留原部署用途。

## 2026-10-25 切换记录

- 使用本地已有的 14:36 数据库备份，核对 SHA-256 后，在新命名卷中事务恢复；保留原 PostgreSQL 16 容器及数据。
- 从备份版本 `20261025_business_consistency` 迁移到 `20261025_beijing_audit_time`，迁移校验通过，public schema 共 29 张表。
- 同时切换根目录 `.env` 的处理库地址以及 `backend/.env.dev` 的业务库、处理库和 Redis 地址。
- 根据本地保存的 DeepSeek 配置记录，使用本地 `.env` 已有密钥重建加密模型凭证，并恢复 6 个模板的模型绑定。没有读取远程数据库，也没有调用外部模型；不能据此确认密钥与远程最新配置相同或模型生成可用。
- 数据为备份时点快照，之后的远程变更未同步。本地数据库后续独立运行，不自动同步远程。
- 原环境文件备份、迁移日志和验收结果保存在 `.runtime/local-docker-s1v7anfw/`；该目录含敏感配置，已限制权限并由 Git 忽略。
- 已通过本地前端代理验证验证码 PNG、真实表单登录、用户信息、菜单、门户概览、新闻/公众号/论文列表、模板列表、工作区和退出登录。验收临时账号已删除。

Compose 首次创建空卷时只初始化 PostgreSQL 实例，不会自动导入业务数据。当前机器的命名卷已经恢复并迁移；换机或新建空卷需要另行恢复匹配当前代码的备份，不能只启动容器就视为业务库初始化完成。
