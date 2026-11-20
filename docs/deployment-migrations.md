# 部署数据库迁移

部署迁移入口为 `pipesight-safe-migrate`。它只读取显式的 `DB_HOST`、`DB_PORT`、`DB_DATABASE`、`DB_USERNAME`、`DB_PASSWORD`，不加载本地 `.env`。应先备份数据库、上传目录及原密钥，停止写入，并在隔离副本完成迁移与恢复演练。

## 当前版本和常规前向升级

Compose 默认运行：

```sh
pipesight-safe-migrate
```

数据库已在当前迁移头时只核对版本；后续普通前向迁移由 Alembic 执行并复核最终版本。迁移失败时 API 和 Worker 不应启动。

空库、没有 Alembic 版本的旧库或未知版本均明确拒绝。当前历史迁移链包含退役归档、表名、数字编号、业务约束和时间转换，不应对空库直接运行全部历史链，也不能用 `stamp head` 伪装完成。新库初始化需独立设计和验收；本入口不会自动建库、导入或恢复备份。

## 受保护的历史升级

历史转换必须逐阶段执行，每阶段之前均保存**该阶段源版本**的一致性备份。不能在最初取一次快照后跳过后续快照。备份格式复用 [PostgreSQL 演练流程](pg-rehearsal.md)：

- 私有目录权限 `0700`，其中 `database-before.dump`、`database-before.json` 文件权限 `0600`。
- 清单包括 `revision`、完整 `tables`、各表行 `fingerprints` 和 dump 的 `sha256`。
- 先在隔离库恢复并验证清单/全部行指纹；保留恢复证据。
- 正式库必须停止业务写入，保留迁移失败后的回滚材料。

示例：源版本为 `20261025_compact_schema`，本阶段只恢复若依物理表名。将私有材料目录只读挂载到 `/app/migration`，创建私有 `options.json`：

```json
{
  "source_revision": "20261025_compact_schema",
  "target_revision": "20261025_restore_ruoyi_names",
  "x_arguments": {
    "ruoyi_backup": "/app/migration/ruoyi-backup",
    "ruoyi_allow_live": "true"
  }
}
```

由迁移负责人明确执行：

```sh
pipesight-safe-migrate \
  --target 20261025_restore_ruoyi_names \
  --options-file /app/migration/options.json
```

也可为迁移服务设置 `PIPESIGHT_MIGRATION_TARGET`、`PIPESIGHT_MIGRATION_OPTIONS_FILE`。入口不会自动增加任何 `*_allow_live=true`；这些选项仍由原有迁移代码校验。`-x` 值通过参数数组传给 Alembic，不拼接 shell。

完成这一阶段后，先核对表结构与全部行指纹，再为新的源版本生成新快照，分别推进 `numeric_backup`、`business_backup`、`beijing_backup` 对应阶段。compact 阶段另需原有 `compact_archive`、`compact_archive_sha256`、`compact_source_snapshot`、`historical_timezone`；入口保留原有退役归档门槛，不代替迁移负责人选择时区或批准退役。

版本更旧、还未到下一个受保护阶段直接前驱的库，应按既有历史演练方案先准备专门升级计划。本入口拒绝跨多个备份阶段，也不擅自执行旧的破坏性迁移。

## 并行发布保护

所有 PostgreSQL 在线 Alembic 迁移都在读取并执行修订前取得数据库级会话锁。其他进程正在迁移时，本次明确退出，等待其完成后重新规划，不会同时执行 DDL。安全迁移入口把规划时的来源版本交给执行端，在锁内再次核对；若期间版本改变，必须重新核对备份和目标后重跑。异常退出会释放锁并回滚尚未提交的事务；不会自动降级。

生产 Compose 不向宿主机发布后端 9099 端口。外部请求须经 Nginx；公开部署仍需在入口配置 HTTPS 并核对防火墙。
