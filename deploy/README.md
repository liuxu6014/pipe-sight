# 部署文件

| 路径 | 用途 |
| --- | --- |
| `docker/backend.pg.Dockerfile` | PostgreSQL 后端镜像；API、Worker、迁移共用 |
| `docker/backend.my.Dockerfile` | 历史 MySQL 迁移验证镜像 |
| `docker/frontend.Dockerfile` | 前端构建与 Nginx 镜像 |
| `nginx/postgres.conf` | PostgreSQL 部署的前端反向代理 |
| `nginx/mysql.conf` | 历史 MySQL 部署的前端反向代理 |

Compose 入口仍位于仓库根目录，保持项目名称、环境文件解析、挂载和网络约定。从仓库根目录执行：

```sh
docker compose -f docker-compose.pg.yml config --quiet
docker compose -f docker-compose.pg.yml build
```

镜像构建上下文仍分别为 `backend/` 和 `frontend/`，各工程的 `.dockerignore` 保留原位置。Compose 的 `dockerfile` 相对构建上下文解析，Nginx 挂载路径相对根目录 Compose 文件解析。

单独构建前端的等价命令：

```sh
docker build -f deploy/docker/frontend.Dockerfile frontend
```

本地 Redis 使用 [docker-compose.local.yml](../docker-compose.local.yml)。历史 MySQL 文件使用 `legacy-migration` profile，不能当成默认启动入口。环境密钥、上传文件、数据库备份和卷数据不放入本目录。
