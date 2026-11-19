# 本地开发运行

API、Worker 和前端应从同一 Git 提交的源码目录启动。当前本机使用 `/Users/liuxu/Documents/ChatGPT/管网` 的 `main`；开发 worktree 的修改通过合并、测试和同步后再切换运行，不能只复制个别页面。数据库和密钥以 Git 忽略的 `backend/.env.dev` 为准，不能从另一份 checkout 的示例环境覆盖。

当前本机验收使用原有 PostgreSQL 快照与 Redis 容器，保留已有数据卷。`docker-compose.local.yml` 仅管理 Redis；已有 PostgreSQL 容器不随此文件重建。

| 服务 | 地址 | 配置 |
| --- | --- | --- |
| 门户 | http://127.0.0.1:12580/portal | `frontend/.env.development.local` |
| API | http://127.0.0.1:9099 | `backend/.env.dev` |
| Redis | `127.0.0.1:26379`，API 使用 DB 3 | `backend/.env.dev` 中的 `REDIS_*` |
| PostgreSQL | 当前本机为 `127.0.0.1:25432`，库 `pipesight` | `backend/.env.dev` 中的 `DB_*`；部署环境可使用独立数据库 |

Redis 密码保存在 Git 忽略的本地环境文件中；Redis 仅绑定回环地址，数据保存在 `pipesight-local_redis-data` 命名卷。

## 启动

在项目根目录启动 Redis：

```sh
docker compose --env-file backend/.env.dev -f docker-compose.local.yml up -d --wait
```

API、Worker、前端分别在同一源码目录的独立终端启动；已有进程运行时先核对进程工作目录与 Git 提交，不重复启动不同版本：

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

保留原有 PostgreSQL 和 Redis 数据卷，不使用 `down -v`。切换版本前备份源码改动和数据库，执行适用迁移，再用当前版本的只读 schema 契约检查确认结构一致。既有 `docker-compose.pg.yml` 保留部署用途。
