# PostgreSQL 注释演练验收（2026-11-19）

此前按外部环境条件跳过的 `test_comment_only_pg18_updates_preserve_every_business_row` 已在真实 PostgreSQL 18 中执行通过，未删除跳过条件、改用模拟数据库或减少断言。

## 环境与恢复证据

- 代码基线：`d3926cfd80f947033b6151d7272398633075cb10`。
- 已核对专用容器 `pipesight-schema-rehearsal-ythnjxpi` 的标签与 `127.0.0.1:19432` 端口绑定。
- 历史快照 SHA-256：`a5d900188d7f6b0bb5ee7fc0c197fb4b07789d2ddd906afa5ab0113f49a7e538`，恢复前重新校验。
- 新建 `pipesight_compact_pgtest_2c281ba05701`、`pipesight_beijing_pgtest_2c281ba05701`，从同一历史快照恢复，未覆盖已有数据库。
- 当前库经真实 Alembic CLI 逐阶段升级至 `20261118_digest_categories`。受保护迁移前均生成一致性备份、SHA-256 和逐表行指纹。
- 注释测试前另存完整一致性备份，SHA-256 为 `38bfd2d07177685b73e6f64568a634a0c60d4b7a822dd0753f008ecf764c915f`。

## 实际结果

- 独立历史演练：`1 passed`，无跳过。
- 连续两次应用当前注释后，30 张表全部行的指纹保持一致；备份覆盖 244 行、18 张非空表，其余空表也参与比较。
- 30 张表、377 个字段、2 个目录视图的注释均匹配当前规范。
- 对迁移后数据库执行只读结构校验，实际业务结构匹配冻结的 `business-v19`，包含计划用户索引及简报筛选字段。
- 相关回归：`74 passed`，JUnit 记录为失败 0、错误 0、跳过 0。覆盖注释、冻结契约、演练入口、备份前置条件和数据库安全边界。
- Ruff 检查与格式校验通过。本次未修改前端或产品数据库迁移逻辑。

私有证据保留在 `.runtime/pg-comment-acceptance/run-6efdc04a14d7/`，包含各阶段日志、备份、`pytest-comments.xml` 和 `pytest-comment-regression.xml`；连接凭证及原始业务快照不提交 Git。

## 可复现入口

按 [PostgreSQL 回归环境说明](../pg-rehearsal.md) 提供已验证的私有快照与演练连接文件，再执行：

```sh
backend/.venv/bin/python backend/scripts/run_pg_rehearsals.py \
  --comments-only \
  --snapshot-dir /private/path/legacy-snapshot \
  --connection-file /private/path/rehearsal-connection.json \
  --evidence-dir .runtime/pg-comment-acceptance
```

独立入口不要求无关 PDF 材料，仍校验容器、端口和随机演练库名称，测试前备份；测试失败或跳过均使命令失败。完整回归入口继续保留原始 PDF 验证。
