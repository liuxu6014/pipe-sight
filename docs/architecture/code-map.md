# PipeSight 代码地图

这份地图记录当前项目的源码边界。整理代码时优先在既有边界内归类，避免为了目录形状而移动运行时入口。

## 前端

`frontend/src/` 是 Vue 应用源码，按“请求、状态、路由页面、页面组件”分层：

- `api/`：后端请求封装。`api/pipeline/` 按业务域拆分情报、文章类别、素材和简报接口。
- `store/modules/`：Pinia 状态模块；跨页面共享的数据和会话状态放在这里。
- `router/`、`permission.js`：路由定义与登录、管理权限守卫。
- `views/portal/pages/`：门户路由页面，一个文件对应一个页面职责。
- `views/portal/components/`：门户页面之间复用的展示和交互组件。
- `views/portal/utils/`：只服务于门户页面的辅助逻辑。
- `utils/portal/`：跨门户页面复用的业务工具，例如身份、证据和业务 ID 处理。
- `assets/styles/`：全局样式和门户工作区样式；页面专属样式保留在页面文件附近。

## 后端

`backend/src/app/` 是当前后端应用的主源码入口，业务代码、路由和基础设施优先在这里查找。

- `backend/src/app/`：应用配置、领域模型、服务、控制器和 API 路由。
- `backend/common/`：兼容旧入口或跨模块共享的公共定义，不与具体业务目录混放。
- `backend/config/`、`backend/middlewares/`、`backend/exceptions/`：运行时配置、中间件和异常适配层。
- `backend/alembic/`、`backend/sql/`、`backend/scripts/`：迁移、初始化 SQL 和运维脚本，不作为业务模块导入。
- `backend/cli/`：命令行入口；启动脚本通过它或 `backend/src/app/entrypoints/` 进入应用。

新增后端业务时，默认放入 `backend/src/app/` 对应领域目录；只有在确认兼容调用方后，才调整根目录下的历史支持模块。

## 部署、维护与文档

- `deploy/docker/` 和 `deploy/nginx/` 集中保存镜像与代理配置，Compose 入口保留在仓库根目录。
- `scripts/dev/` 提供联合启动与停止，`scripts/checks/` 提供工程验证。
- `backend/scripts/` 按初始化、导入、回填、检查、迁移辅助和论文工具分组，具体文件见[维护脚本清单](../../backend/scripts/README.md)。正式数据库迁移仍在 `backend/alembic/`。
- `docs/guides/` 保存操作指南，`docs/handover/` 保存交接说明；文档图片位于 `docs/assets/`。

## 不属于源码主干的目录

`.runtime/`、`logs/`、`output/`、`dist/`、`node_modules/` 和 `vf_admin/` 是运行时、构建产物、依赖或外部管理资源。它们可以用于诊断或交付，但不应成为新的业务代码落点。

## 整理约定

1. 新接口先加到对应的 `api/` 模块，再由页面或 store 调用，避免在页面内直接拼接请求。
2. 新的跨页面状态放入 `store/modules/`；仅当前页面使用的状态留在页面 `script setup` 中。
3. 组件达到复用条件后再抽取；抽取时保留页面的公开状态和测试契约，避免无收益的大范围搬迁。
4. 目录移动需要同时检查路由、别名导入、启动脚本和测试夹具，并在构建后再提交。
