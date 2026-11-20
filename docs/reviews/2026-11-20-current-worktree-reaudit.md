# PipeSight 当前工作区复审

基线为 `5b21f60` 加当前未提交改动。本轮 OCR 本地预览识别 96 个变更文件条目，其中 58 个符合工具的审查规则。实际判断来自本地源码和隔离验证。当前工作区与上一轮修复验收时有差异，以下记录本轮实际观察。

## P0

1. **API 和任务 Worker 都无法启动。** [调度器](../../backend/src/app/research/tasks/research_job_scheduler.py#L12) 导入 `queue_scan_result`，[心跳模块](../../backend/src/app/health/worker.py#L19) 缺少该符号。分别导入 API [启动模块](../../backend/src/app/bootstrap.py#L21) 和 [Worker 入口](../../backend/src/app/entrypoints/task_worker.py#L18)，均得到同一个 `ImportError`；全量后端测试因此在收集阶段报 5 处错误。应同时恢复队列状态写入和健康检查读取逻辑，并用 API/Worker 入口导入检查拦截部分回退。

## P1

2. **退出后旧会话可被并发请求恢复。** [认证续期](../../backend/src/app/system/services/authentication.py#L215) 当前重新使用分开的 Redis `GET` 和 `SET`。隔离测试分别在两步之间执行退出、写入新登录令牌，两种情况都观察到旧令牌被写回。应恢复原子的比较并续期，并覆盖两种时序。
3. **私有资料自动分类重新启用，缺少所有者的明确确认。** [资料入库](../../backend/src/app/library/services/materials.py#L394) 默认排队；[分类 Worker](../../backend/src/app/library/tasks/material_parse_scheduler.py#L93) 提交标题和正文；[模型网关](../../backend/src/app/research/services/model_generation.py#L130) 向所配置端点发送正文。[分类入口](../../backend/src/app/library/api/controller.py#L154) 当前也没有同意字段。启用适用类别且模型端点属于外部供应商时，新资料解析后可自动出站。实际供应商调用未执行。应恢复所有者确认，并阻止没有确认记录的旧队列任务出站。

## P2

4. **拒绝上传后留下原始文件。** [上传入口](../../backend/src/app/library/api/controller.py#L65) 先写入共享卷，资料服务随后拒绝不支持的公开共享参数。用真实入口和临时目录复现，接口拒绝后合成 TXT 仍在磁盘。应在落盘前验证共享范围，并为后续拒绝路径补偿清理。
5. **删除报告仍遗漏导出和配图文件。** [报告删除](../../backend/src/app/research/services/reports.py#L89) 删除资源记录后直接提交。[Worker 清理器](../../backend/src/app/research/tasks/research_job_scheduler.py#L194) 只处理已有标记，但当前报告删除入口没有为相关文件写入标记。用隔离数据库和临时卷复现，报告资源记录删除成功，合成导出文件仍可从卷读取，也没有待清理标记。应在事务提交前记录待清理资源，提交后回收，并验证失败后的重试路径。
6. **生产 Compose 再次对宿主机发布明文 API。** [Compose](../../docker-compose.pg.yml#L76) 关闭应用传输加密并发布 `19099:9099`。渲染配置确认端口映射存在。宿主网络放行时可以绕过 Nginx 代理；公网是否可达取决于防火墙和拓扑。生产默认应只通过内部网络连接 API。
7. **部署迁移缺少整个运行周期的互斥。** [迁移入口](../../backend/src/app/entrypoints/safe_migrate.py#L240) 先读当前版本，再通过独立进程运行 Alembic，中间未建立数据库级迁移互斥。若两个环境或发布任务对同一目标库同时启动，可能基于同一旧修订发起相同 DDL，导致一个发布失败。此项为并发风险推断，未在数据库执行双迁移。应在同一互斥范围内重新读取版本、执行并复核迁移，增加两个进程争用同一隔离库的测试。

## 验证范围

- 审查覆盖认证、资料上传与分类、报告删除与存储、Worker 和部署配置及迁移路径。项目全量后端回归受 P0 阻断，不能沿用上一轮的绿色结果。
- 隔离复核覆盖退出后旧会话恢复、旧会话覆盖新令牌及拒绝上传遗留文件，三种行为均观察到。另跑分类、密码会话、迁移规划和报告文件复现用例，共 77 项通过，其中覆盖了分类编辑期间仍保留并发名额的行为。前端 760 项测试及 Docker 模式构建通过。
- 本轮未修改业务代码，也未连接真实模型、真实客户库或生产站点。外部 TLS、真实部署和全站浏览器验收未覆盖。
