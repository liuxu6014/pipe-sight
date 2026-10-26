# 数据库表命名规范

应用业务表采用小写英文与下划线，保留「业务对象＋用途」；删除冗余系统前缀，不删除必要含义。不强制20字符上限，不为达成长度指标制造缩写或合并不同用途的数据。若依原生 `sys_*`、`ai_*` 与框架基础设施表保持兼容。

## 本轮简化映射

| 原应用表名 | 新表名 | 含义 |
| --- | --- | --- |
| pipeline_content_review_events | content_review_events | 内容审核事件 |
| pipeline_duplicate_group_events | duplicate_group_events | 重复组治理事件 |
| pipeline_duplicate_groups | duplicate_groups | 疑似重复内容组 |
| pipeline_duplicate_members | duplicate_members | 重复组成员 |
| pipeline_model_call_audits | model_calls | 单次模型调用审计 |
| pipeline_model_route_usage | model_route_usage | 场景模型路由每日用量 |
| pipeline_model_routes | model_routes | 场景模型路由 |
| pipeline_prompt_versions | prompt_versions | 业务提示词版本 |
| pipeline_quality_issue_events | quality_issue_events | 质量问题治理事件 |
| pipeline_quality_issues | quality_issues | 质量问题 |
| pipeline_template_versions | template_versions | 报告与简报模板版本 |

先前过度简化的 `review_events`、`duplicate_events`、`route_usage`、`quality_events` 分别更正为上述名称。修改采用追加迁移，不重建表；不改业务字段、主键值或类型，保留表和字段注释。模型配置继续统一复用 `ai_models`，不再另建模型与凭据库。

`public.prompt_versions` 是应用侧场景提示词，`news.prompt_versions` 是历史处理侧提示词版本和血缘。跨域SQL必须显式写schema；两者名称相同不等于职责已经统一，实际执行边界与后续收敛见 [配置主来源与处理边界](configuration-ownership.md)。

## 初始化与升级

`pipeline-domain*.sql` 是历史基础结构，保留原名以保证已有迁移顺序可复现；不能对已升级的数据库反复裸执行这些基础SQL。新库先导入基础结构，再执行 `alembic upgrade head` 得到最终短表名；已有库只执行迁移。启动脚本在已有基础库上跳过旧结构导入，Compose仅在空卷首次导入基础SQL。

`sql/legacy/application-comments-20261014.pg.sql` 固定首次迁移的旧名注释，`application-comments-short-20261014.pg.sql` 固定过渡短名阶段的注释；当前规范注释位于 `sql/application-comments-pg.sql`。历史迁移不能依赖随业务修改的当前注释文件，后续调整追加迁移。

应用内部表不新增旧名兼容视图；运行代码统一使用短名，API路径、权限编码和Python业务类名保持不变。若有仓库之外直接查询这11张表的脚本，需要按映射更新。2026年10月25日通过迁移 `20261025_retire_processing_views` 移除了处理域9个旧名称兼容视图；新环境初始化也不再创建这些视图。`public.list_table` 和 `public.list_column` 是结构查询视图，保留使用。

完整字段说明见 [PostgreSQL数据字典](database-dictionary.md)。

## 运行核验（2026-10-14）

原短名阶段迁移为 `20261014_short_business_table_names`；本轮追加 `20261014_semantic_business_names`，恢复4处必要业务语义。部署验证以本轮迁移后检查和最新数据字典为准，不以旧阶段记录代替。

迁移前已完成自定义格式备份并验证归档目录。迁移前后逐表数据摘要、行数、表OID、列定义、约束关系与OID、索引OID和有效性、表权限均一致，迁移版本值按预期更新。隔离旧库和新库初始化均通过，重复初始化未产生旧名表；本次QA库已移除，原本地业务库保留。

37张ORM表全部在远程库读取成功。后端、独立任务Worker已重启，直接及前端代理健康检查正常；浏览器模型配置页和科研报告页读取正常，无服务端500。检查不包含真实模型生成或爬虫验收。

此前短名阶段相关后端测试115项、启动脚本测试3项通过。测试中有6条已知SQLite表达式索引反射警告；既有模型审计测试文件还存在4处数字常量风格告警，与表名改动无关，未扩展修改。本轮验证另行记录，不能用此前测试结果代替。

### 本轮最终核验

远程库已升级至 `20261014_semantic_business_names`。47张物理表、11个视图、914个字段，表及字段注释缺失数均为0。迁移前后47张表的行数、数据摘要、列定义、表与约束及索引OID、表权限一致，仅迁移版本值按预期更新。备份保留于本地忽略目录，未执行远程恢复演练。

本轮相关后端测试116项通过，启动脚本测试3项通过，指定修改文件Ruff检查通过；旧库、新库和重复初始化在隔离PG验证通过。37张ORM表在远程读取成功，API及前端代理健康检查通过；浏览器模型配置页、科研报告页读取正常，无服务端500。仅删除本轮创建的两个隔离QA数据库，原本地业务库和历史数据均保留。

取消了20字符硬限制。本轮未合并提示词表、未迁移分类与评分提示词执行逻辑、未改变日期字段类型；这些事项的实际状态和后续实施边界在配置主来源文档中明确列出。
