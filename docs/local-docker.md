# 本地 Docker（仅 Redis）

本地开发不再随 Docker 启动 PostgreSQL：数据库统一连 `172.16.4.183` 的 `pipesight` 库（在 `backend/.env.dev` 配置 `DB_*`）。`docker-compose.local.yml` 只负责本机 Redis。

| 服务 | 地址 | 配置 |
| --- | --- | --- |
| 门户 | http://127.0.0.1:12580/portal | `frontend/.env.development.local` |
| API | http://127.0.0.1:9099 | `backend/.env.dev` |
| Redis | `127.0.0.1:26379`，API 使用 DB 3 | `backend/.env.dev` 中的 `REDIS_*` |
| PostgreSQL | `172.16.4.183:5432`，库 `pipesight` | `backend/.env.dev` 中的 `DB_*` |

Redis 密码保存在 Git 忽略的本地环境文件中；Redis 仅绑定回环地址，数据保存在 `pipesight-local_redis-data` 命名卷。

## 启动

在项目根目录启动 Redis：

```sh
docker compose --env-file backend/.env.dev -f docker-compose.local.yml up -d --wait
```

API、Worker、前端分别在独立终端启动，数据库无需本地启动、直连 183；已有进程运行时不必重复启动：

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

需要保留当前 Redis 数据时不要使用 `down -v`。既有 `docker-compose.pg.yml` 保留部署用途（同样连 183）。
