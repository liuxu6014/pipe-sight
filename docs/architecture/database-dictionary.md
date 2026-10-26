# PipeSight PostgreSQL 数据字典

数据库：`pipesight`。导出时间：2026-10-25T10:17:03.499434+08:00。

本文件由 `backend/scripts/export_database_dictionary.py` 从实际 catalog 生成，不包含业务记录或连接凭据。

共 49 个表/视图、751 个字段。
缺失对象注释 0 个，缺失字段注释 0 个。

## 命名与兼容规则

- 若依原生 `sys_*`、`ai_*` 及框架基础设施名称保留兼容。
- `public` 保存应用配置及业务数据，`news` 保存处理收件箱、规则和向量投影。
- 旧处理表名兼容视图已退役；运行代码直接使用规范物理表。现存视图按用途单独列出，不计为额外业务数据副本。
- 应用业务表去掉冗余 `pipeline_` 前缀，使用 `model_routes`、`prompt_versions`、`quality_issues` 等短名称。
- 视图上的主键/非空约束标记不代表底层表没有约束，请按对应物理表核对。
- `timestamp without time zone` 不擅自解释为 UTC，业务时间遵循现有来源/应用约定；`with time zone` 为绝对时间。

## 对象总览

| 对象 | 类型 | 说明 | 字段数 |
| --- | --- | --- | --- |
| `news.articles` | 物理表 | 资讯处理收件箱及处理结果事实表，原 hp_news；以 news_id、create_time 组成复合主键，uuid 可重复；completed 表示处理完成，不等于平台人工审核通过或正式发布。 | 49 |
| `news.data_sources` | 物理表 | 处理库来源和机构主数据，原 hp_data_source；Worker 按不区分大小写的 web_name 识别来源，交接适配器可用平台来源编码建档；不等同平台采集任务配置表。 | 19 |
| `news.domain_topic_rules` | 物理表 | 领域与分类的分类标准绑定，原 act_domain_topic_actions；复合主键为 domain_id、category_id；文本或版本引用至少一个非空，当前配置服务仍只消费非空内嵌分类标准。 | 6 |
| `news.domains` | 物理表 | 资讯领域定义与处理器配置；配置服务直接读取 domains 中未删除记录，内嵌过滤和评分提示词由当前动态领域处理器使用。 | 13 |
| `news.embeddings` | 物理表 | 资讯 1024 维语义向量及检索投影快照，原 news_embedding；以 news_id、news_create_time 复合主键和外键绑定资讯行，删除资讯级联删除向量；相同资讯行采用幂等覆盖写入。 | 20 |
| `news.prompt_usages` | 物理表 | 资讯处理使用的提示词版本、阶段和顺序血缘，原 news_prompt_usage；复合外键定位原资讯行，删除资讯级联删除血缘；当前 Worker 生成血缘入口但尚未写入本表，不能假定已有完整调用记录。 | 9 |
| `news.prompt_versions` | 物理表 | 提示词版本及单父派生关系，原 sys_prompt_version；保存内容、发布状态和内容摘要，已发布或已使用版本受不可变触发器保护；当前动态领域处理仍读取领域与规则中的内嵌文本。 | 18 |
| `news.topics` | 物理表 | 资讯分类定义和分类树，原 hp_topic；当前配置服务读取未删除且启用的分类，并通过领域分类规则取得对应领域的非空分类标准，分类树字段未用于递归查询。 | 16 |
| `public.ai_chat_config` | 物理表 | 用户AI对话偏好配置表 | 11 |
| `public.ai_models` | 物理表 | AI模型表 | 19 |
| `public.alembic_version` | 物理表 | Alembic数据库迁移版本记录表；记录已应用的迁移头版本 | 1 |
| `public.apscheduler_jobs` | 物理表 | APScheduler 持久化任务存储表，由若依调度器维护，不是业务任务执行记录 | 3 |
| `public.collection_runs` | 物理表 | 采集运行记录表 | 27 |
| `public.content_review_events` | 物理表 | 管网内容审核事件表 | 11 |
| `public.data_sources` | 物理表 | 数据来源配置表 | 22 |
| `public.digest_schedules` | 物理表 | 周期情报简报自动生成计划表 | 21 |
| `public.duplicate_group_events` | 物理表 | 管网情报重复组治理事件表 | 11 |
| `public.duplicate_groups` | 物理表 | 管网情报疑似重复组 | 11 |
| `public.duplicate_members` | 物理表 | 管网情报重复组成员关系 | 7 |
| `public.generation_tasks` | 物理表 | 报告生成任务表 | 24 |
| `public.knowledge_files` | 物理表 | 知识库文件表 | 31 |
| `public.list_column` | 视图 | 公共库字段信息兼容视图；按系统目录汇总列定义及关联约束标记 | 8 |
| `public.list_table` | 视图 | 公共库表信息兼容视图；列出表名及目录注释，时间列为查询事务时间 | 4 |
| `public.model_calls` | 物理表 | 管网模型单次调用审计表 | 22 |
| `public.model_route_usage` | 物理表 | 管网场景模型路由每日调用计数表 | 5 |
| `public.model_routes` | 物理表 | 管网业务场景模型路由配置表 | 14 |
| `public.news_articles` | 物理表 | 科技资讯文章表 | 36 |
| `public.papers` | 物理表 | 论文资料表 | 41 |
| `public.prompt_versions` | 物理表 | 管网模型提示词版本表 | 16 |
| `public.quality_issue_events` | 物理表 | 管网情报质量问题治理事件表 | 10 |
| `public.quality_issues` | 物理表 | 管网情报质量问题登记表 | 17 |
| `public.report_exports` | 物理表 | 报告导出任务和文件审计表 | 22 |
| `public.report_publications` | 物理表 | 报告正式发布与撤销发布审计记录表 | 8 |
| `public.report_versions` | 物理表 | 报告版本表 | 13 |
| `public.reports` | 物理表 | 科研报告与周期情报简报当前状态表 | 16 |
| `public.sys_config` | 物理表 | 参数配置表 | 10 |
| `public.sys_dict_data` | 物理表 | 字典数据表 | 14 |
| `public.sys_dict_type` | 物理表 | 字典类型表 | 9 |
| `public.sys_job` | 物理表 | 定时任务调度表 | 16 |
| `public.sys_job_log` | 物理表 | 定时任务调度日志表 | 13 |
| `public.sys_logininfor` | 物理表 | 系统访问记录 | 9 |
| `public.sys_menu` | 物理表 | 菜单权限表 | 20 |
| `public.sys_oper_log` | 物理表 | 操作日志记录 | 16 |
| `public.sys_role` | 物理表 | 角色信息表 | 13 |
| `public.sys_role_menu` | 物理表 | 角色和菜单关联表 | 2 |
| `public.sys_user` | 物理表 | 用户信息表 | 19 |
| `public.sys_user_role` | 物理表 | 用户和角色关联表 | 2 |
| `public.template_versions` | 物理表 | 管网科研与情报模板版本表 | 19 |
| `public.user_saved_items` | 物理表 | 用户收藏与资料篮表 | 8 |

## news.articles

资讯处理收件箱及处理结果事实表，原 hp_news；以 news_id、create_time 组成复合主键，uuid 可重复；completed 表示处理完成，不等于平台人工审核通过或正式发布。

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `news_id` | bigint | 是 | 是 | — | 资讯事实编号，bigint 身份列，与 create_time 共同组成主键；交接适配器也可显式分配编号，不能仅凭本列认定数据库行唯一。 | — |
| `create_time` | timestamp without time zone | 是 | 是 | CURRENT_TIMESTAMP | 资讯入库／交接建行时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；与 news_id 共同定位记录，关联血缘和向量时须携带本值，重处理既有行不改该键。 | — |
| `uuid` | character varying(255) | 否 | 否 | — | 上游业务资讯标识，varchar(255)，可空且不唯一；平台交接写 article_id，Worker 写 NewsBase.id；相同标识可有多次处理行，读写通常取 create_time 最新记录。 | — |
| `prompt_trace_id` | character varying(26) | 否 | 否 | — | 成功处理后的提示词血缘入口，varchar(26)，可空；当前 Worker 使用 uuid4().hex[:26]，不是 ULID；空值参与待处理筛选，与 news_id、create_time 共同被 news.prompt_usages 复合外键引用。 | — |
| `web_source_id` | bigint | 否 | 否 | — | 处理库来源编号，bigint，可空，逻辑关联 news.data_sources.web_source_id，没有外键；Worker 未取得来源名称时可返回 -1，不能默认所有非空值均有对应主数据。 | — |
| `domain_id` | bigint | 否 | 否 | — | 处理得到的领域编号，bigint，可空，逻辑关联 news.domains.domain_id，没有外键；由 Worker 的领域处理结果写入，与领域名称快照 domain 分开保存。 | — |
| `classify` | integer | 否 | 否 | — | 处理得到的分类编号，integer，可空，逻辑关联 news.topics.category_id，没有外键；写入 NewsBase.category_id，不能改释为原始来源类别或布尔分类结果。 | — |
| `original_title` | character varying(512) | 否 | 否 | — | 资讯原始标题，varchar(512)，可空；平台交接和 Worker 写入来源标题，区别于翻译标题 translated_title 和模型生成标题 ai_title。 | — |
| `original_text` | text | 否 | 否 | — | 资讯原始正文，text，可空；平台交接写 article.body，Worker 优先写 content_md、否则写 content，可能是 Markdown 文本而非固定 HTML 或 JSON。 | — |
| `translated_title` | character varying(512) | 否 | 否 | — | 处理产生的翻译标题，varchar(512)，可空；来自 NewsBase.translated_title，未翻译时可以为空，不覆盖 original_title。 | — |
| `translated_text` | text | 否 | 否 | — | 处理产生的翻译正文，text，可空；来自 NewsBase.translated_text，未启用或未完成翻译时可以为空，不代表另存的原始正文版本。 | — |
| `summary` | text | 否 | 否 | — | 资讯摘要，text，可空；交接阶段可带入平台已有摘要，处理完成后 Worker 写 NewsBase.abstract，不保证始终是原站原始摘要。 | — |
| `ai_title` | text | 否 | 否 | — | 模型提炼的资讯标题，text，可空；Worker 写 NewsBase.ai_title，向量输入优先采用本标题，不能当作原始来源标题。 | — |
| `source` | character varying(255) | 否 | 否 | — | 来源名称文本快照，varchar(255)，可空；Worker 写站点名称，交接写平台来源 name，与数值来源编号 web_source_id 分开保存。 | — |
| `cover_image_url` | character varying(4096) | 否 | 否 | — | 来源封面图片地址，varchar(4096)，可空；Worker 写 NewsBase.cover_image_url，仅保存链接，不说明已缓存图片或已取得图片使用授权。 | — |
| `external_link` | character varying(4096) | 否 | 否 | — | 资讯原始出处链接，varchar(4096)，可空；交接写 canonical_url、Worker 写 NewsBase.url，与 url 保留兼容性，不保证外链始终可访问。 | — |
| `url` | character varying(4096) | 否 | 否 | — | 兼容保留的资讯链接，varchar(4096)，可空；当前交接和 Worker 与 external_link 写同一地址，下游转换在 external_link 缺失时回退读取本列。 | — |
| `author_id` | bigint | 否 | 否 | — | 历史资讯作者编号，bigint，可空；原结构没有作者表外键，当前 Worker 和交接适配器不填充本列，不能解释为平台上传者或登录账号。 | — |
| `platform` | integer | 否 | 否 | — | 来源平台识别编码，integer，可空；当前处理器将微信公众号识别为 1，交接及 Worker 对普通或未设置平台写 0；其他历史编码没有数据库 CHECK。 | — |
| `score` | real | 否 | 否 | — | 领域模型评估分数，real，可空，单位为分；当前评分逻辑钳制到 0–100 并保留一位小数，模型缺省也可写 0；数据库没有分数范围 CHECK，不等同概率或人工审核结论。 | — |
| `warning_grade` | character varying(255) | 否 | 否 | — | 预警等级文本，varchar(255)，可空；当前 Worker 将数字等级转为字符串：'0' 无、'1' 低、'2' 中、'3' 高；数据库未对历史文本设枚举 CHECK。 | — |
| `warning_cause` | character varying(500) | 否 | 否 | — | 预警原因，varchar(500)，可空；Worker 写模型评估的 risk_reason，与 warning_grade 配套，不是处理异常 processing_error。 | — |
| `domain` | character varying(255) | 否 | 否 | — | 处理领域名称快照，varchar(255)，可空；Worker 把本地域编码转换为数据库领域名称后写入，领域名称查询会排除 unknown。 | — |
| `content_extraction` | text | 否 | 否 | — | 事件和实体提取结果的 JSON 文本，text，可空；Worker 将字典序列化，模型字段可含 event_time、location、background、entities、insight；不是 jsonb，数据库不校验 JSON 格式。 | — |
| `event_keywords` | text | 否 | 否 | — | 处理提取的事件搜索关键词，text，可空；NewsBase 约定把关键词列表转为逗号拼接字符串，向量 key_words 保存其文本快照，不是 JSON 数组。 | — |
| `other` | text | 否 | 否 | — | 处理扩展特征的 JSON 文本，text，可空；Worker 序列化 NewsBase.features，可包含实体、地点及 pipesight_filter 等元数据；不是 jsonb，数据库不限定键或校验 JSON。 | — |
| `other_cn` | text | 否 | 否 | — | 历史中文扩展标签文本，text，可空；当前 Worker 入库和交接适配器不填充或解析本列，不能解释为已生成的中文翻译正文。 | — |
| `filter_result` | text | 否 | 否 | — | 过滤判定或说明，text，可空；当前处理链路序列化 pipesight_filter 对象，可含 decision、workerExecution 等证据；拒绝和成功均可保留，历史值也可为说明文本，不是单一布尔值。 | — |
| `background` | text | 否 | 否 | — | 历史背景说明正文，text，可空；当前 Worker 入库不单独填充本列，结构化提取中的 background 保存在 content_extraction 内，不保证两者同步。 | — |
| `focus_risk` | character varying(500) | 否 | 否 | — | 历史提请关注的风险说明，varchar(500)，可空；当前 Worker 入库不填充，交接回执在已有值时读取，不等同当前风险原因 warning_cause。 | — |
| `suggestion` | text | 否 | 否 | — | 历史对策建议正文，text，可空；当前 Worker 入库不填充，交接回执在已有值时读取，不保证每次处理都会生成建议。 | — |
| `judgment_opinion` | text | 否 | 否 | — | 历史研判意见正文，text，可空；当前 Worker 和交接适配器不维护本列，不能据此认定已完成人工研判或审核。 | — |
| `publish_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 业务发布时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；Worker 默认从 ctime 按 Asia/Shanghai 生成并钳制未来时间，交接缺失时回填发现时间，不保证均为已核实的原站发布日期。 | — |
| `timestamp` | timestamp without time zone | 否 | 否 | — | 历史时间戳字段，timestamp without time zone，可空；不是 Unix 秒或毫秒整数，当前 Worker 和交接适配器不维护本列，不替代 create_time 或 publish_time。 | — |
| `del_flag` | character(1) | 是 | 否 | '0'::bpchar | 资讯逻辑删除标志，char(1)，非空且默认 '0'；CHECK 只允许 '0' 存在、'2' 已删除；平台交接重置未完成记录时恢复为 '0'，回执把 '2' 视为拒绝结果。 | — |
| `is_featured` | smallint | 是 | 否 | 0 | 历史是否推荐标志，smallint，非空且默认 0；原结构没有编码 CHECK，当前 Worker 和交接适配器不读写，不等同模型评分达到推荐阈值。 | — |
| `is_top` | character(1) | 否 | 否 | — | 历史是否置顶标志，char(1)，可空；原结构未限定编码，当前 Worker 和交接适配器不维护，不能推断已有置顶排序逻辑。 | — |
| `type` | character(10) | 否 | 否 | — | 交接资讯类型编码，char(10)，可空；当前平台交接写 'W' 微信公众号、'N' 普通资讯，Worker 原位完成时保留本列；没有固定值 CHECK，不能据此扩展为论文类型。 | — |
| `favorites` | integer | 是 | 否 | 0 | 历史收藏次数，integer，非空且默认 0，单位为次；没有非负 CHECK，当前 Worker 和交接适配器不维护，不能替代平台用户收藏记录。 | — |
| `likes` | integer | 是 | 否 | 0 | 历史点赞次数，integer，非空且默认 0，单位为次；没有非负 CHECK，当前处理和交接路径不更新，不保证与来源站点或平台用户互动一致。 | — |
| `shares` | integer | 是 | 否 | 0 | 历史分享次数，integer，非空且默认 0，单位为次；没有非负 CHECK，当前处理和交接路径不更新，不代表真实外发次数。 | — |
| `bad` | integer | 是 | 否 | 0 | 历史不感兴趣次数，integer，非空且默认 0，单位为次；没有非负 CHECK，当前处理和交接路径不维护，不代表处理失败或被过滤的次数。 | — |
| `tags` | text | 否 | 否 | — | 上游资讯标签，text，可空；当前平台交接把 article.tags 序列化为 JSON 数组文本，Worker 原位完成不重写本列；数据库不校验 JSON，不等同 event_keywords 的逗号文本。 | — |
| `news_all_info` | text | 否 | 否 | — | 上游附加信息，text，可空；当前平台交接仅序列化 article.metadata_json，并非完整原始新闻快照；Worker 兼容读取其中 processing.filter 过滤证据，数据库不校验 JSON。 | — |
| `processing_status` | character varying(20) | 是 | 否 | 'pending'::character varying | 处理收件箱状态，varchar(20)，非空且默认 pending；CHECK 枚举为 pending 待处理、processing 处理中、completed 已完成、rejected 过滤拒绝、failed 可重试失败、dead_letter 次数耗尽需人工重试；不是平台审核状态。 | — |
| `processing_attempts` | integer | 是 | 否 | 0 | 累计处理领取次数，integer，非空且默认 0，单位为次；每次领取任务加 1，亦作为过期 Worker 结果的租约校验编号；最大次数取运行配置，数据库未设置非负或上限 CHECK。 | — |
| `processing_started_at` | timestamp with time zone | 否 | 否 | — | 当前处理租约开始时刻，timestamp with time zone，可空；领取时写 now()，按配置的秒数判断超时，处理结束或租约回收时清空，不是永久保存的首次处理时间。 | — |
| `processing_completed_at` | timestamp with time zone | 否 | 否 | — | 处理完成或过滤拒绝时刻，timestamp with time zone，可空；成功及 rejected 路径写 now()，交接重置和失败路径清空，不能单独用本列判断任务成功。 | — |
| `processing_error` | text | 否 | 否 | — | 最近处理错误、过滤拒绝原因或租约超时说明，text，可空；当前失败写入逻辑最多保存 2000 个字符，数据库 text 本身无此长度限制；领取、重置或成功后清空。 | — |

## news.data_sources

处理库来源和机构主数据，原 hp_data_source；Worker 按不区分大小写的 web_name 识别来源，交接适配器可用平台来源编码建档；不等同平台采集任务配置表。

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `web_source_id` | bigint | 是 | 是 | — | 来源主键，bigint 身份列；现有接入端也可在事务锁保护下显式分配编号；由 news.articles.web_source_id 逻辑引用，该引用没有数据库外键。 | — |
| `web_name` | character varying(255) | 是 | 否 | — | 来源识别名称或编码，varchar(255)，非空；Worker 使用站点名称，平台交接优先使用 processor_source_code；lower(web_name) 唯一，不要求一定是网站展示名。 | — |
| `web_name_cn` | character varying(255) | 否 | 否 | — | 来源中文展示名称，varchar(255)，可空；平台交接写入采集来源 name，与用于识别来源的 web_name 分开保存。 | — |
| `url` | character varying(512) | 是 | 否 | — | 来源地址，varchar(512)，非空；Worker 通常保存文章 URL 的协议和主机部分，平台交接保存 endpoint，未配置时使用 pipeSight://来源编码，不保证都是 HTTP 地址。 | — |
| `description` | text | 否 | 否 | — | 来源描述，text，可空；用于保留来源说明，当前 Worker 和交接适配器不读取或填充本列。 | — |
| `category` | character(1) | 否 | 否 | — | 历史来源类别标识，char(1)，可空；当前接入和处理路径不读取，数据库未限定编码；与 data_source_classify 的数据源／机构分类不是同一字段。 | — |
| `data_source_classify` | character(1) | 是 | 否 | '1'::bpchar | 来源主体分类，char(1)，非空且默认 '1'；CHECK 只允许 '1' 数据源、'2' 机构；Worker 按 NewsBase.data_source_classify 写入，平台交接新建来源时写 '1'。 | — |
| `content_type` | news.content_type | 是 | 否 | 'Other'::news.content_type | 来源内容格式，news.content_type 枚举，非空且默认 Other；枚举值 HTML、RSS、JSON、Other，平台交接按来源类型字符串映射；不表示文章审核或处理状态。 | — |
| `authentication_required` | character(1) | 是 | 否 | '0'::bpchar | 历史认证需求标志，char(1)，非空且默认 '0'；没有编码 CHECK，当前 Worker 和交接适配器不读取本列，不能据此认定已实现来源认证或凭证管理。 | — |
| `last_crawled_timestamp` | timestamp without time zone | 否 | 否 | — | 来源最近抓取／接入更新时间，timestamp without time zone，可空；现有来源被 Worker 再次匹配或被平台交接更新时写 now()，不代表抓取全站完成或采集任务成功。 | — |
| `next_crawl_priority` | character(1) | 是 | 否 | '0'::bpchar | 历史下次抓取优先级，char(1)，非空且默认 '0'；没有优先级编码或高低顺序 CHECK，当前 Worker 和交接适配器未用于调度。 | — |
| `is_crawled` | character(1) | 是 | 否 | '0'::bpchar | 历史抓取完成标记，char(1)，非空且默认 '0'；数据库未限定其他编码，当前 Worker 和交接适配器不维护本列，不能替代真实采集任务状态。 | — |
| `logo_path` | character varying(512) | 否 | 否 | — | 历史来源标识图片的文件路径，varchar(512)，可空；当前处理和交接路径不填充，不等同可公开访问的 logo_url。 | — |
| `logo_url` | character varying(512) | 否 | 否 | — | 历史来源标识图片的访问地址，varchar(512)，可空；当前处理和交接路径不填充，保存地址不自动保证文件可访问。 | — |
| `other` | jsonb | 是 | 否 | '{}'::jsonb | 来源扩展元数据，jsonb，非空且默认空对象；平台交接写入 pipesight_source_id、pipesight_source_code 以定位平台来源，数据库未限定 JSON 形状或键集合。 | — |
| `tag` | character varying(1000) | 否 | 否 | — | 历史来源标签文本，varchar(1000)，可空；当前处理和交接路径不解析本列，未约定为 JSON 数组或固定分隔格式。 | — |
| `create_by` | character varying(255) | 否 | 否 | — | 来源记录创建人标识，varchar(255)，可空；没有用户表外键，当前 Worker 和交接适配器新建来源时不填充本列。 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 来源建档时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；平台交接显式写 now()，无时区值受写入端和数据库会话时区约定影响。 | — |
| `remark` | text | 否 | 否 | — | 来源人工备注，text，可空；当前 Worker 和交接适配器不读取或维护，用于保留来源说明而非处理错误。 | — |

## news.domain_topic_rules

领域与分类的分类标准绑定，原 act_domain_topic_actions；复合主键为 domain_id、category_id；文本或版本引用至少一个非空，当前配置服务仍只消费非空内嵌分类标准。

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `domain_id` | bigint | 是 | 是 | — | 规则所属领域编号，bigint，非空且为复合主键一部分；外键指向 news.domains.domain_id，ON DELETE CASCADE；当前配置服务按此字段选择领域对应分类标准。 | FOREIGN KEY (domain_id) REFERENCES news.domains(domain_id) ON DELETE CASCADE |
| `category_id` | bigint | 是 | 是 | — | 规则绑定的分类编号，bigint，非空且为复合主键一部分；外键指向 news.topics.category_id，ON DELETE CASCADE；与领域编号共同保证每对领域分类最多一条规则。 | FOREIGN KEY (category_id) REFERENCES news.topics(category_id) ON DELETE CASCADE |
| `category_prompts` | text | 否 | 否 | — | 内嵌分类标准正文，text，可空；当前配置服务将非空正文直接拼入分类提示词，尚不回退读取版本内容；CHECK 只要求本列或 prompt_version_id 非空，不会拒绝空字符串。 | — |
| `prompt_version_id` | bigint | 否 | 否 | — | 分类标准提示词版本编号，bigint，可空；外键指向 news.prompt_versions.prompt_version_id，ON DELETE RESTRICT；与内嵌文本至少一个非空，但当前配置服务尚未解引用本列生成分类提示词。 | FOREIGN KEY (prompt_version_id) REFERENCES news.prompt_versions(prompt_version_id) ON DELETE RESTRICT |
| `created_at` | timestamp with time zone | 是 | 否 | now() | 领域分类规则创建时刻，timestamp with time zone，非空且默认 now()；与提示词版本的创建时间分别记录。 | — |
| `updated_at` | timestamp with time zone | 是 | 否 | now() | 领域分类规则最后修改时刻，timestamp with time zone，非空且默认 now()；原结构由 set_updated_at 更新时间触发器维护。 | — |

## news.domains

资讯领域定义与处理器配置；配置服务直接读取 domains 中未删除记录，内嵌过滤和评分提示词由当前动态领域处理器使用。

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `domain_id` | bigint | 是 | 是 | — | 领域主键，bigint 身份列；由提示词版本和领域分类规则通过外键引用，资讯及向量领域字段仅逻辑关联；内置领域也可显式指定编号。 | — |
| `domain_name` | character varying(255) | 是 | 否 | — | 领域名称，varchar(255)，非空且全表唯一；用于领域名称与编号映射、处理器注册及分类结果展示，逻辑删除记录仍占用该唯一名称。 | — |
| `remark` | character varying(2000) | 否 | 否 | — | 领域说明或备注，varchar(2000)，可空；配置服务将其作为领域配置的一部分读取，不是过滤提示词正文。 | — |
| `user_id` | bigint | 否 | 否 | — | 历史关联用户编号，bigint，可空且没有用户表外键；当前领域配置查询未以本列进行账号权限过滤，不应解释为已生效的领域访问授权。 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 领域记录创建时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；保存无时区时间，不是事件发生时间。 | — |
| `create_by` | character varying(255) | 否 | 否 | — | 领域创建人标识，varchar(255)，可空；没有用户表外键，当前领域配置服务只读取配置，不自动填写创建人。 | — |
| `other` | character varying(255) | 否 | 否 | — | 历史领域扩展文本，varchar(255)，可空；不是 jsonb，当前领域配置服务未解析本列，也未定义固定 JSON 结构。 | — |
| `del_flag` | character(1) | 是 | 否 | '0'::bpchar | 领域逻辑删除标志，char(1)，非空且默认 '0'；CHECK 只允许 '0' 有效、'2' 已删除，正常领域配置和编号映射只读取 '0'。 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 领域最后修改时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；原建表脚本未为本列配置自动更新时间触发器，后续修改需由写入端维护。 | — |
| `update_by` | character varying(255) | 否 | 否 | — | 领域最后修改人标识，varchar(255)，可空且没有用户表外键；由领域配置的写入端维护，读取服务不自动变更。 | — |
| `filter_prompts` | text | 否 | 否 | — | 动态领域的大模型过滤提示词，text，可空；处理器将其按含 systemPrompts、userPrompts 键的 JSON 文本解析，解析失败兼容为用户提示词全文；不是 jsonb，也不是版本外键。 | — |
| `score_prompts` | text | 否 | 否 | — | 动态领域的评分提示词，text，可空；按 systemPrompts、userPrompts JSON 文本解析，解析失败兼容为用户提示词全文；当前动态处理器仍读取本列，不保证引用 prompt_versions。 | — |
| `return_flag` | integer | 是 | 否 | 0 | 领域处理器来源标志，integer，非空且默认 0；0 标识本地／文件处理器，非 0 用于数据库领域处理器识别，混合处理还受处理器工厂配置影响；没有固定非零值枚举 CHECK。 | — |

## news.embeddings

资讯 1024 维语义向量及检索投影快照，原 news_embedding；以 news_id、news_create_time 复合主键和外键绑定资讯行，删除资讯级联删除向量；相同资讯行采用幂等覆盖写入。

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `news_id` | bigint | 是 | 是 | — | 向量所属资讯事实编号，bigint，非空且为复合主键一部分；与 news_create_time 外键关联 news.articles(news_id, create_time)，ON DELETE CASCADE。 | FOREIGN KEY (news_id, news_create_time) REFERENCES news.articles(news_id, create_time) ON DELETE CASCADE |
| `news_create_time` | timestamp without time zone | 是 | 是 | — | 向量所属资讯行的 create_time，timestamp without time zone，非空且为复合主键一部分；与 news_id 建立到 news.articles 的复合外键，当前向量客户端按该编号最新 create_time 行写入。 | FOREIGN KEY (news_id, news_create_time) REFERENCES news.articles(news_id, create_time) ON DELETE CASCADE |
| `uuid` | character varying(255) | 是 | 否 | — | 上游业务资讯标识快照，varchar(255)，非空但未限制非空白或唯一；客户端写入向量数据的 uuid，不能用本列替代复合主键。 | — |
| `embedding` | news.vector(1024) | 是 | 否 | — | 资讯标题与摘要的语义向量，pgvector vector(1024)，非空，维数为 1024；原结构建立 vector_cosine_ops HNSW 索引，采用余弦距离，不是评分概率或原文内容。 | — |
| `embedding_model` | text | 是 | 否 | — | 生成语义向量的模型名称快照，text，非空；由运行配置 embedding_model 写入，模型可配置，不应将某一模型名称固定为表结构枚举。 | — |
| `embedding_version` | integer | 是 | 否 | 1 | 向量输入拼接／清洗规则版本，integer，非空且默认 1，CHECK 大于 0；当前客户端新建时写 1、冲突更新不改本列，没有实现规则变更后自动重建的保证。 | — |
| `source_hash` | character(64) | 是 | 否 | — | 客户端向量来源文本摘要，char(64)，非空且 CHECK 为 64 位小写十六进制 SHA-256；当前对 UTF-8 文本“标题: 标题值 摘要: 摘要值”计算，标题优先取 AI 标题、否则原题，再去首尾空白；独立重建输入，不保证等同模型端预处理文本，不是原文文件哈希。 | — |
| `domain_id` | bigint | 否 | 否 | — | 资讯领域编号的检索投影，bigint，可空，对应 news.articles.domain_id 并逻辑关联 news.domains.domain_id；本列没有领域外键，不由数据库自动随主表更新。 | — |
| `category_id` | bigint | 否 | 否 | — | 资讯分类编号的检索投影，bigint，可空，写入处理结果 classify，对应 news.articles.classify 和 news.topics.category_id；本列没有分类外键。 | — |
| `published_at` | timestamp without time zone | 否 | 否 | — | 资讯发布时间的检索投影，timestamp without time zone，可空；当前客户端从被引用资讯行的 publish_time 读取，不是向量生成时间，也不是可自动补出的原站发布日期。 | — |
| `key_words` | text | 是 | 否 | ''::text | 事件关键词文本快照，text，非空且默认空字符串；当前处理链路传入 event_keywords 的逗号拼接文本，不是 JSON 数组或另行计算的向量关键词。 | — |
| `title` | character varying(512) | 是 | 否 | — | 资讯原始标题的轻量检索快照，varchar(512)，非空但没有非空白 CHECK；来自处理结果 title，与向量输入优先使用的 ai_title 分开保存。 | — |
| `ai_title` | text | 是 | 否 | ''::text | 模型提炼标题的轻量检索快照，text，非空且默认空字符串；有值时优先参与向量输入标题选择，不代表原始标题被替换。 | — |
| `source` | character varying(255) | 否 | 否 | — | 资讯来源名称的轻量检索快照，varchar(255)，可空；由处理结果复制，不是来源编号，也不由数据库自动与来源主数据同步。 | — |
| `domain` | character varying(255) | 否 | 否 | — | 资讯领域名称的轻量检索快照，varchar(255)，可空；用于展示，与领域编号 domain_id 分开保存，不是领域表外键。 | — |
| `external_link` | character varying(4096) | 否 | 否 | — | 资讯原始出处链接快照，varchar(4096)，可空；由处理结果复制，仅保存 URL，不保证原站可用或已取得全文访问权限。 | — |
| `cover_image_url` | character varying(4096) | 否 | 否 | — | 资讯封面图片地址快照，varchar(4096)，可空；由处理结果复制，不包含图片二进制内容或图片缓存状态。 | — |
| `producer` | character varying(100) | 是 | 否 | 'insight_hub'::character varying | 向量记录生产者标识，varchar(100)，非空且默认 insight_hub；当前客户端可读取传入 producer，原结构没有非空白或固定生产者枚举 CHECK。 | — |
| `created_at` | timestamp with time zone | 是 | 否 | now() | 向量记录首次创建时刻，timestamp with time zone，非空且默认 now()；冲突覆盖写入保留本值，与资讯 create_time 分开记录。 | — |
| `updated_at` | timestamp with time zone | 是 | 否 | now() | 向量记录最后更新时刻，timestamp with time zone，非空且默认 now()；原结构由 set_updated_at 更新时间触发器维护，幂等覆盖写入也会刷新。 | — |

## news.prompt_usages

资讯处理使用的提示词版本、阶段和顺序血缘，原 news_prompt_usage；复合外键定位原资讯行，删除资讯级联删除血缘；当前 Worker 生成血缘入口但尚未写入本表，不能假定已有完整调用记录。

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `usage_id` | bigint | 是 | 是 | — | 提示词版本使用记录主键，bigint 身份列；用于定位单条使用关系，不是资讯主键或模型调用次数。 | — |
| `prompt_trace_id` | character varying(26) | 是 | 否 | — | 资讯处理血缘批次标识，varchar(26)，非空；与 news_id、news_create_time 共同外键关联 news.articles(prompt_trace_id, news_id, create_time)，ON DELETE CASCADE；与 sequence_no 联合唯一。 | FOREIGN KEY (prompt_trace_id, news_id, news_create_time) REFERENCES news.articles(prompt_trace_id, news_id, create_time) ON DELETE CASCADE |
| `news_id` | bigint | 是 | 否 | — | 使用提示词的资讯事实编号，bigint，非空；须与 prompt_trace_id、news_create_time 一起匹配 news.articles 的复合外键，不能单独定位可能重复编号的资讯行。 | FOREIGN KEY (prompt_trace_id, news_id, news_create_time) REFERENCES news.articles(prompt_trace_id, news_id, create_time) ON DELETE CASCADE |
| `news_create_time` | timestamp without time zone | 是 | 否 | — | 被引用资讯行的 create_time，timestamp without time zone，非空；必须保留 news.articles.create_time 原值，与资讯编号和血缘批次共同建立复合外键，不是本使用记录的创建时刻。 | FOREIGN KEY (prompt_trace_id, news_id, news_create_time) REFERENCES news.articles(prompt_trace_id, news_id, create_time) ON DELETE CASCADE |
| `prompt_version_id` | bigint | 是 | 否 | — | 该处理阶段使用的提示词版本编号，bigint，非空；外键指向 news.prompt_versions.prompt_version_id，ON DELETE RESTRICT；一旦被使用，原结构触发器保护版本内容不被覆盖。 | FOREIGN KEY (prompt_version_id) REFERENCES news.prompt_versions(prompt_version_id) ON DELETE RESTRICT |
| `stage` | character varying(50) | 是 | 否 | — | 提示词使用阶段，varchar(50)，非空；历史约定示例 FILTER、CLASSIFY、SCORE、WARNING、ENTITY_EXTRACT，同阶段可有多条标准；原结构未设置阶段枚举或非空白 CHECK。 | — |
| `sequence_no` | integer | 是 | 否 | — | 血缘批次内提示词使用顺序号，integer，非空且 CHECK 大于 0，单位为序号；与 prompt_trace_id 联合唯一，原结构不保证顺序连续或自动分配。 | — |
| `model_name` | character varying(255) | 否 | 否 | — | 该阶段实际调用模型的名称，varchar(255)，可空；属于血缘记录的模型快照，不是模型配置主键、向量模型名称或固定枚举。 | — |
| `created_at` | timestamp with time zone | 是 | 否 | now() | 提示词使用关系记录创建时刻，timestamp with time zone，非空且默认 now()；不提供单次调用的开始、结束、耗时或 token 用量。 | — |

## news.prompt_versions

提示词版本及单父派生关系，原 sys_prompt_version；保存内容、发布状态和内容摘要，已发布或已使用版本受不可变触发器保护；当前动态领域处理仍读取领域与规则中的内嵌文本。

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `prompt_version_id` | bigint | 是 | 是 | — | 提示词版本主键，bigint 身份列；可被派生版本、领域分类规则及实际提示词使用记录引用，删除受这些外键的 RESTRICT 规则保护。 | — |
| `parent_prompt_version_id` | bigint | 否 | 否 | — | 直接派生来源版本编号，bigint，可空；外键指向 news.prompt_versions.prompt_version_id，ON DELETE RESTRICT；空值表示根版本，可跨 prompt_key 派生，CHECK 仅禁止直接自指，不负责阻止多节点环。 | FOREIGN KEY (parent_prompt_version_id) REFERENCES news.prompt_versions(prompt_version_id) ON DELETE RESTRICT |
| `prompt_key` | character varying(150) | 是 | 否 | — | 提示词稳定业务键，varchar(150)，非空，例如 politics.filter；与 version_no、content_hash 分别组成唯一约束，同一键最多一个 published 版本，由部分唯一索引保证。 | — |
| `prompt_name` | character varying(255) | 是 | 否 | — | 提示词版本展示名称，varchar(255)，非空；区别于稳定业务键 prompt_key，原结构未设置名称唯一或非空白文本 CHECK。 | — |
| `prompt_type` | character varying(50) | 是 | 否 | — | 提示词处理用途，varchar(50)，非空；历史约定示例 FILTER、CLASSIFY、CLASSIFY_CRITERION、SCORE、WARNING、ENTITY_EXTRACT；不是数据库枚举，原结构未约束用途值域。 | — |
| `domain_id` | bigint | 否 | 否 | — | 提示词适用领域编号，bigint，可空；外键指向 news.domains.domain_id，ON DELETE RESTRICT；空值表示全局提示词，不自动授予领域访问权限。 | FOREIGN KEY (domain_id) REFERENCES news.domains(domain_id) ON DELETE RESTRICT |
| `category_id` | bigint | 否 | 否 | — | 提示词适用分类编号，bigint，可空；外键指向 news.topics.category_id，ON DELETE RESTRICT；空值表示非分类专属提示词，不等同领域分类绑定本身。 | FOREIGN KEY (category_id) REFERENCES news.topics(category_id) ON DELETE RESTRICT |
| `version_no` | integer | 是 | 否 | — | 同一 prompt_key 内的版本编号，integer，非空且 CHECK 大于 0；与 prompt_key 联合唯一，版本分配由写入端维护，数据库不保证自动或连续递增。 | — |
| `system_prompt` | text | 是 | 否 | ''::text | 系统提示词模板正文，text，非空且默认空字符串；与 user_prompt 分开保存，已发布或已使用版本的正文受不可变触发器保护。 | — |
| `user_prompt` | text | 是 | 否 | — | 用户提示词模板正文，text，非空但未设置非空白 CHECK；保存模板而非某次调用渲染后的输入，已发布或已使用版本的正文受不可变触发器保护。 | — |
| `template_variables` | jsonb | 否 | 否 | — | 模板变量名称及说明的 JSONB 元数据，可空；原结构未限定数组或对象形状，当前 Worker 未从本版本表读取变量渲染，不能视为已实现的动态变量验证规则。 | — |
| `content_hash` | character(64) | 是 | 否 | — | 提示词内容的 SHA-256 摘要，char(64)，非空且 CHECK 为 64 位小写十六进制；与 prompt_key 联合唯一，具体内容规范化和摘要计算由写入端约定。 | — |
| `status` | character varying(20) | 是 | 否 | 'draft'::character varying | 版本状态，varchar(20)，非空且默认 draft；CHECK 只允许 draft 草稿、published 已发布、retired 已退役；同一业务键最多一个 published，离开草稿或被使用后不能修改受保护内容或回退为草稿。 | — |
| `derivation_note` | character varying(1000) | 否 | 否 | — | 版本派生的改动说明及原因，varchar(1000)，可空；属于不可变内容，已发布或已使用版本不能覆盖该说明。 | — |
| `created_by` | character varying(255) | 否 | 否 | — | 提示词版本创建人标识，varchar(255)，可空；原结构没有用户表外键，不是调用模型名称或提示词使用记录的执行人。 | — |
| `created_at` | timestamp with time zone | 是 | 否 | now() | 提示词版本创建时刻，timestamp with time zone，非空且默认 now()；记录数据库时间点，不等同首次调用或发布时间。 | — |
| `updated_at` | timestamp with time zone | 是 | 否 | now() | 提示词版本最后修改时刻，timestamp with time zone，非空且默认 now()；原结构由 set_updated_at 更新时间触发器在更新时维护。 | — |
| `published_at` | timestamp with time zone | 否 | 否 | — | 版本正式发布时间点，timestamp with time zone，可空；CHECK 要求 published 状态时非空，已发布或已使用版本的此时间受不可变触发器保护。 | — |

## news.topics

资讯分类定义和分类树，原 hp_topic；当前配置服务读取未删除且启用的分类，并通过领域分类规则取得对应领域的非空分类标准，分类树字段未用于递归查询。

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `category_id` | bigint | 是 | 是 | — | 分类主键，bigint 身份列；由领域分类规则和提示词版本通过外键引用，资讯 classify 与向量 category_id 仅逻辑关联本编号。 | — |
| `category_name` | character varying(255) | 是 | 否 | — | 分类名称，varchar(255)，非空；用于构造模型候选类别及名称到编号的映射，原结构未设置分类名称唯一约束。 | — |
| `category_description` | text | 否 | 否 | — | 分类业务说明，text，可空；配置服务把该说明拼入分类提示词，帮助模型区分候选类别。 | — |
| `parent_category_id` | bigint | 否 | 否 | — | 历史分类树父节点编号，bigint，可空，逻辑指向 news.topics.category_id 但没有自引用外键；当前领域分类查询不按父子关系递归展开。 | — |
| `ancestors` | character varying(255) | 否 | 否 | — | 历史分类树祖先路径文本，varchar(255)，可空；未由数据库限定路径编码或分隔符，当前领域分类配置查询不解析本列。 | — |
| `domain_id` | integer | 否 | 否 | — | 历史分类归属领域编号，integer，可空，逻辑关联 news.domains.domain_id 但没有外键；当前配置查询按 news.domain_topic_rules.domain_id 关联，不以本列筛选领域。 | — |
| `return_flag` | integer | 是 | 否 | 0 | 历史分类返回标志，integer，非空且默认 0；原结构没有编码 CHECK，当前分类提示词构建和分类名称映射不读取本列。 | — |
| `is_active` | character(1) | 是 | 否 | '0'::bpchar | 分类启停标志，char(1)，非空且默认 '0'；CHECK 只允许 '0' 启用、'1' 禁用，当前领域分类查询只读取 '0'，不是布尔值 true 表示启用。 | — |
| `del_flag` | character(1) | 是 | 否 | '0'::bpchar | 分类逻辑删除标志，char(1)，非空且默认 '0'；CHECK 只允许 '0' 存在、'2' 已删除，当前领域分类查询只读取 '0'。 | — |
| `sort_order` | integer | 否 | 否 | — | 分类显示和提示词候选顺序，integer，可空且没有正数 CHECK；配置服务按本列升序、再按 category_id 升序读取。 | — |
| `other` | jsonb | 是 | 否 | '{}'::jsonb | 历史分类扩展元数据，jsonb，非空且默认空对象；原结构未限定 JSON 形状，当前领域分类配置服务不读取或解释其键。 | — |
| `remark` | text | 否 | 否 | — | 分类人工备注，text，可空；与实际拼入模型提示词的 category_description 分开保存，当前领域分类配置查询未读取本列。 | — |
| `create_by` | character varying(255) | 否 | 否 | — | 分类创建人标识，varchar(255)，可空且没有用户表外键；由分类维护端填写，不是分类处理模型名称。 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 分类定义创建时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；保存无时区时间，与资讯发布时间无关。 | — |
| `update_by` | character varying(255) | 否 | 否 | — | 分类最后修改人标识，varchar(255)，可空且没有用户表外键；由分类维护端填写，当前读取服务不自动变更。 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 分类定义最后修改时间，timestamp without time zone，可空；原建表脚本未设置本列默认值或自动更新时间触发器，由写入端维护。 | — |

## public.ai_chat_config

用户AI对话偏好配置表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `chat_config_id` | bigint | 是 | 是 | nextval('ai_chat_config_chat_config_id_seq'::regclass) | 配置主键 | — |
| `user_id` | bigint | 是 | 否 | — | 用户ID | FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE CASCADE |
| `temperature` | double precision | 否 | 否 | — | 对话默认采样温度配置 | — |
| `add_history_to_context` | character(1) | 否 | 否 | '0'::bpchar | 历史对话上下文开关（0携带 1不携带） | — |
| `num_history_runs` | integer | 否 | 否 | — | 携带到上下文的历史对话轮数 | — |
| `system_prompt` | text | 否 | 否 | — | 系统提示词 | — |
| `metrics_default_visible` | character(1) | 否 | 否 | '0'::bpchar | 对话指标默认显示配置（0显示 1隐藏） | — |
| `vision_enabled` | character(1) | 否 | 否 | '1'::bpchar | 图片输入开关配置（0开启 1关闭） | — |
| `image_max_size_mb` | integer | 否 | 否 | — | 单张图片大小配置上限（MiB，按1024×1024字节换算） | — |
| `create_time` | timestamp(0) without time zone | 否 | 否 | — | 创建时间 | — |
| `update_time` | timestamp(0) without time zone | 否 | 否 | — | 更新时间 | — |

## public.ai_models

AI模型表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `model_id` | bigint | 是 | 是 | nextval('ai_models_model_id_seq'::regclass) | 模型主键 | — |
| `model_code` | character varying(100) | 是 | 否 | — | 模型编码 | — |
| `model_name` | character varying(100) | 否 | 否 | NULL::character varying | 模型名称 | — |
| `provider` | character varying(50) | 是 | 否 | — | 提供商 | — |
| `model_sort` | integer | 是 | 否 | — | 显示顺序 | — |
| `api_key` | character varying(255) | 否 | 否 | NULL::character varying | 模型服务调用凭证；敏感字段，不应在普通列表或日志中明文返回 | — |
| `base_url` | character varying(255) | 否 | 否 | NULL::character varying | 模型服务API基础地址 | — |
| `model_type` | character varying(50) | 否 | 否 | NULL::character varying | 模型类型 | — |
| `max_tokens` | integer | 否 | 否 | — | 模型单次最大输出Token数；非空时须大于0 | — |
| `temperature` | double precision | 否 | 否 | — | 默认采样温度；非空时取值0至2 | — |
| `support_reasoning` | character(1) | 否 | 否 | 'N'::bpchar | 模型推理能力标记（Y支持 N不支持） | — |
| `support_images` | character(1) | 否 | 否 | 'N'::bpchar | 模型图片输入能力标记（Y支持 N不支持） | — |
| `status` | character(1) | 否 | 否 | '0'::bpchar | 模型启停状态（0正常 1停用） | — |
| `user_id` | bigint | 是 | 否 | — | 用户ID | FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE CASCADE |
| `create_by` | character varying(64) | 否 | 否 | ''::character varying | 创建者 | — |
| `create_time` | timestamp(0) without time zone | 否 | 否 | — | 创建时间 | — |
| `update_by` | character varying(64) | 否 | 否 | ''::character varying | 更新者 | — |
| `update_time` | timestamp(0) without time zone | 否 | 否 | — | 更新时间 | — |
| `remark` | character varying(500) | 否 | 否 | NULL::character varying | 备注 | — |

## public.alembic_version

Alembic数据库迁移版本记录表；记录已应用的迁移头版本

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `version_num` | character varying(64) | 是 | 是 | — | 已应用的Alembic迁移头版本标识；多分支迁移可存在多条记录 | — |

## public.apscheduler_jobs

APScheduler 持久化任务存储表，由若依调度器维护，不是业务任务执行记录

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | character varying(191) | 是 | 是 | — | 调度任务唯一标识，由 APScheduler 分配，与 sys_job 的业务任务编号不是同一字段 | — |
| `next_run_time` | double precision | 否 | 否 | — | 下次调度的 Unix 时间戳，单位秒，空值表示任务暂停或尚无下次执行时间 | — |
| `job_state` | bytea | 是 | 否 | — | APScheduler 序列化任务状态，二进制 Pickle 数据，仅由可信调度器写入和反序列化 | — |

## public.collection_runs

采集运行记录表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `run_id` | character varying(64) | 是 | 是 | — | 运行ID | — |
| `source_id` | character varying(64) | 是 | 否 | — | 数据源ID | FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE RESTRICT |
| `scheduler_job_id` | bigint | 否 | 否 | — | 调度任务ID | FOREIGN KEY (scheduler_job_id) REFERENCES sys_job(job_id) ON DELETE SET NULL |
| `trigger_type` | character varying(32) | 是 | 否 | 'schedule'::character varying | 采集触发类型（schedule计划 manual手动 retry重试） | — |
| `status` | character varying(32) | 是 | 否 | 'queued'::character varying | 采集运行状态（queued排队 running执行中 success成功 failed失败 cancelled取消） | — |
| `config_snapshot` | json | 是 | 否 | — | 本次采集执行的来源配置JSON对象快照 | — |
| `started_at` | timestamp without time zone | 否 | 否 | — | 开始时间 | — |
| `finished_at` | timestamp without time zone | 否 | 否 | — | 结束时间 | — |
| `fetched_count` | integer | 是 | 否 | 0 | 抓取条数 | — |
| `inserted_count` | integer | 是 | 否 | 0 | 新增条数 | — |
| `updated_count` | integer | 是 | 否 | 0 | 更新条数 | — |
| `duplicate_count` | integer | 是 | 否 | 0 | 去重条数 | — |
| `failed_count` | integer | 是 | 否 | 0 | 失败条数 | — |
| `handoff_status` | character varying(32) | 是 | 否 | 'pending'::character varying | 批次交接状态（pending待交接 dispatched已派发 processing处理中 completed完成 partial部分完成 failed失败） | — |
| `handoff_batch_id` | character varying(64) | 否 | 否 | — | 外部处理批次ID | — |
| `handoff_count` | integer | 是 | 否 | 0 | 提交外部处理条数 | — |
| `handoff_processed_count` | integer | 是 | 否 | 0 | 外部处理完成条数 | — |
| `handoff_failed_count` | integer | 是 | 否 | 0 | 外部处理失败条数 | — |
| `handoff_time` | timestamp without time zone | 否 | 否 | — | 最近一次外部处理回执时间 | — |
| `handoff_error` | text | 否 | 否 | — | 外部处理错误摘要 | — |
| `error_message` | text | 否 | 否 | — | 错误信息 | — |
| `checkpoint_json` | json | 是 | 否 | — | 运行断点与处理汇总JSON对象；可含重试关联及processing计数 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |
| `handoff_rejected_count` | integer | 是 | 否 | 0 | 外部处理业务拒绝条数 | — |
| `handoff_lease_owner` | character varying(128) | 否 | 否 | — | 交接执行器租约持有者 | — |
| `handoff_lease_until` | timestamp without time zone | 否 | 否 | — | 交接执行器租约到期时间 | — |

## public.content_review_events

管网内容审核事件表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `event_id` | character varying(64) | 是 | 是 | — | 审核事件ID | — |
| `content_type` | character varying(16) | 是 | 否 | — | 审核对象类型（article资讯文章 paper论文） | — |
| `content_id` | character varying(64) | 是 | 否 | — | 内容ID | — |
| `from_status` | character varying(32) | 否 | 否 | — | 变更前内容审核状态；采用pending、approved或rejected编码 | — |
| `to_status` | character varying(32) | 是 | 否 | — | 变更后内容审核状态；采用pending、approved或rejected编码 | — |
| `action` | character varying(32) | 是 | 否 | — | 审核动作（approve通过 reject拒绝 withdraw撤回 reprocess重处理） | — |
| `reason` | text | 否 | 否 | — | 审核意见 | — |
| `operator_id` | bigint | 否 | 否 | — | 操作人ID | FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `operator_name` | character varying(64) | 是 | 否 | ''::character varying | 操作人名称快照 | — |
| `snapshot_json` | json | 是 | 否 | '{}'::json | 审核动作发生时的内容及处理状态JSON对象快照 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 事件时间 | — |

## public.data_sources

数据来源配置表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `source_id` | character varying(64) | 是 | 是 | — | 数据源ID | — |
| `source_code` | character varying(100) | 是 | 否 | — | 稳定的数据源编码 | — |
| `name` | character varying(255) | 是 | 否 | — | 数据源名称 | — |
| `source_type` | character varying(32) | 是 | 否 | — | 采集内容类型编码；现有适配器使用news新闻、wechat公众号或paper论文 | — |
| `endpoint` | character varying(1000) | 否 | 否 | — | 数据源入口地址 | — |
| `adapter_key` | character varying(128) | 是 | 否 | — | 采集适配器标识 | — |
| `schedule_cron` | character varying(100) | 否 | 否 | — | 调度表达式 | — |
| `status` | character varying(32) | 是 | 否 | 'active'::character varying | 来源生命周期状态（active有效 inactive停用） | — |
| `enabled` | boolean | 是 | 否 | true | 是否允许执行采集 | — |
| `config_json` | json | 是 | 否 | — | 来源采集规则与增量配置JSON对象；参数由适配器解释 | — |
| `handoff_mode` | character varying(16) | 是 | 否 | 'external'::character varying | 内容处理模式（local本地处理 external交接外部处理系统） | — |
| `processor_source_code` | character varying(128) | 否 | 否 | — | 外部处理系统来源编码 | — |
| `last_run_time` | timestamp without time zone | 否 | 否 | — | 最近采集时间 | — |
| `last_run_status` | character varying(32) | 否 | 否 | — | 最近采集运行状态快照；采用collection_runs.status的状态编码 | — |
| `success_count` | integer | 是 | 否 | 0 | 累计成功次数 | — |
| `failure_count` | integer | 是 | 否 | 0 | 累计失败次数 | — |
| `consecutive_failures` | integer | 是 | 否 | 0 | 连续失败次数 | — |
| `owner_id` | bigint | 否 | 否 | — | 负责人ID | FOREIGN KEY (owner_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |
| `collection_lease_owner` | character varying(128) | 否 | 否 | — | 采集执行器租约持有者 | — |
| `collection_lease_until` | timestamp without time zone | 否 | 否 | — | 采集执行器租约到期时间 | — |

## public.digest_schedules

周期情报简报自动生成计划表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `schedule_id` | character varying(64) | 是 | 是 | — | 计划ID | — |
| `user_id` | bigint | 是 | 否 | — | 创建用户ID | FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE CASCADE |
| `request_id` | character varying(128) | 否 | 否 | — | 客户端幂等请求标识 | — |
| `owner_name` | character varying(64) | 是 | 否 | — | 创建用户名称快照 | — |
| `name` | character varying(255) | 是 | 否 | — | 计划名称 | — |
| `report_type` | character varying(32) | 是 | 否 | — | 自动简报周期类型（daily日报 weekly周报 monthly月报） | — |
| `template_id` | character varying(64) | 是 | 否 | — | 已发布模板编码 | — |
| `template_version` | character varying(32) | 否 | 否 | — | 模板版本快照 | — |
| `schedule_time` | character varying(5) | 是 | 否 | '08:00'::character varying | 本地执行时间HH:MM | — |
| `config` | json | 是 | 否 | — | 计划的筛选条件、内容生成及节假日策略JSON对象快照 | — |
| `enabled` | boolean | 是 | 否 | true | 是否启用 | — |
| `next_run_time` | timestamp without time zone | 是 | 否 | — | 下次执行时间 | — |
| `last_run_time` | timestamp without time zone | 否 | 否 | — | 最近一次调度时间 | — |
| `last_task_id` | character varying(64) | 否 | 否 | — | 最近生成任务ID | FOREIGN KEY (last_task_id) REFERENCES generation_tasks(task_id) ON DELETE SET NULL |
| `last_status` | character varying(32) | 否 | 否 | — | 最近调度结果（queued已入队 no_data无数据 skipped已跳过 failed失败；未调度时为空） | — |
| `last_error` | text | 否 | 否 | — | 最近一次失败说明 | — |
| `failure_count` | integer | 是 | 否 | 0 | 连续失败次数 | — |
| `lease_owner` | character varying(128) | 否 | 否 | — | 调度执行器租约持有者 | — |
| `lease_until` | timestamp without time zone | 否 | 否 | — | 调度执行器租约到期时间 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |

## public.duplicate_group_events

管网情报重复组治理事件表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `event_id` | character varying(64) | 是 | 是 | — | 事件ID | — |
| `group_id` | character varying(64) | 是 | 否 | — | 重复组ID | FOREIGN KEY (group_id) REFERENCES duplicate_groups(group_id) ON DELETE CASCADE |
| `from_status` | character varying(16) | 否 | 否 | — | 变更前重复组状态；采用candidate、merged、split或dismissed编码 | — |
| `to_status` | character varying(16) | 是 | 否 | — | 变更后重复组状态（candidate待确认 merged已合并 split已拆分 dismissed已排除） | — |
| `action` | character varying(16) | 是 | 否 | — | 重复组治理动作（merge合并 split拆分 dismiss排除 reopen重新打开） | — |
| `master_content_id` | character varying(64) | 否 | 否 | — | 当时确认的主记录ID | — |
| `reason` | text | 是 | 否 | — | 处理说明 | — |
| `operator_id` | bigint | 否 | 否 | — | 操作人ID | FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `operator_name` | character varying(64) | 是 | 否 | ''::character varying | 操作人名称快照 | — |
| `snapshot_json` | json | 是 | 否 | '{}'::json | 治理动作发生时的重复组及成员关系JSON对象快照 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 事件时间 | — |

## public.duplicate_groups

管网情报疑似重复组

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `group_id` | character varying(64) | 是 | 是 | — | 重复组ID | — |
| `content_type` | character varying(16) | 是 | 否 | — | 内容类型：article或paper | — |
| `group_key` | character varying(255) | 是 | 否 | — | 规范化重复键 | — |
| `status` | character varying(16) | 是 | 否 | 'candidate'::character varying | 重复组状态（candidate待确认 merged已合并 split已拆分 dismissed已排除） | — |
| `master_content_id` | character varying(64) | 否 | 否 | — | 确认后的主记录ID | — |
| `similarity` | double precision | 否 | 否 | — | 相似度，0到1 | — |
| `decision_reason` | text | 否 | 否 | — | 治理决定说明 | — |
| `operator_id` | bigint | 否 | 否 | — | 决定人ID | FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `operator_name` | character varying(64) | 是 | 否 | ''::character varying | 决定人名称快照 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |

## public.duplicate_members

管网情报重复组成员关系

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `member_id` | bigint | 是 | 是 | nextval('pipeline_duplicate_members_member_id_seq'::regclass) | 成员关系ID | — |
| `group_id` | character varying(64) | 是 | 否 | — | 重复组ID | FOREIGN KEY (group_id) REFERENCES duplicate_groups(group_id) ON DELETE CASCADE |
| `content_type` | character varying(16) | 是 | 否 | — | 内容类型：article或paper | — |
| `content_id` | character varying(64) | 是 | 否 | — | 内容ID | — |
| `relation_type` | character varying(16) | 是 | 否 | 'candidate'::character varying | 组内成员关系（candidate候选 master主记录 duplicate重复记录） | — |
| `similarity` | double precision | 否 | 否 | — | 与主记录的相似度（0至1；未计算时为空） | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |

## public.generation_tasks

报告生成任务表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `task_id` | character varying(64) | 是 | 是 | — | 生成任务ID | — |
| `user_id` | bigint | 是 | 否 | — | 创建用户ID | FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE RESTRICT |
| `owner_name` | character varying(64) | 是 | 否 | — | 创建用户名称快照 | — |
| `title` | character varying(500) | 是 | 否 | — | 任务名称 | — |
| `report_type` | character varying(64) | 是 | 否 | — | 生成任务的科研报告或周期简报业务类型编码 | — |
| `template_id` | character varying(64) | 否 | 否 | — | 前端或代码内置模板编码快照 | — |
| `template_version` | character varying(32) | 否 | 否 | — | 模板版本显示值快照 | — |
| `status` | character varying(32) | 是 | 否 | 'queued'::character varying | 生成状态（queued排队 running执行中 completed完成 failed失败 dead_letter死信 cancelled取消） | — |
| `current_stage` | character varying(64) | 是 | 否 | 'validating'::character varying | 当前生成阶段编码；初始validating表示输入校验 | — |
| `progress` | integer | 是 | 否 | 0 | 生成进度百分比（0至100） | — |
| `config` | json | 是 | 否 | — | 任务提交时的生成输入与参数JSON对象快照 | — |
| `selected_items` | json | 是 | 否 | — | 任务启动时选定证据资料的权威JSON数组快照 | — |
| `outline` | json | 是 | 否 | — | 任务报告大纲及章节定义JSON数组 | — |
| `stages` | json | 是 | 否 | — | 生成阶段进度及状态JSON数组 | — |
| `logs` | json | 是 | 否 | — | 生成任务执行过程日志JSON数组 | — |
| `error_message` | text | 否 | 否 | — | 错误信息 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |
| `request_id` | character varying(128) | 否 | 否 | — | 客户端幂等请求标识 | — |
| `attempt_count` | integer | 是 | 否 | 0 | 执行尝试次数 | — |
| `lease_owner` | character varying(128) | 否 | 否 | — | 当前执行器租约持有者 | — |
| `lease_until` | timestamp without time zone | 否 | 否 | — | 当前执行器租约到期时间 | — |
| `next_retry_at` | timestamp without time zone | 否 | 否 | — | 下次重试时间 | — |
| `cancel_requested_at` | timestamp without time zone | 否 | 否 | — | 用户请求取消时间 | — |

## public.knowledge_files

知识库文件表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `file_id` | character varying(64) | 是 | 是 | — | 知识文件ID | — |
| `name` | character varying(255) | 是 | 否 | — | 资料名称 | — |
| `category` | character varying(64) | 是 | 否 | '内部文献'::character varying | 资料分类 | — |
| `file_name` | character varying(255) | 否 | 否 | — | 存储文件名 | — |
| `file_path` | character varying(500) | 否 | 否 | — | 对象存储键或本地映射路径 | — |
| `file_url` | character varying(1000) | 否 | 否 | — | 受控文件访问地址 | — |
| `mime_type` | character varying(128) | 否 | 否 | — | 文件MIME类型 | — |
| `file_size` | bigint | 是 | 否 | 0 | 原始资料文件大小（字节，非负） | — |
| `file_hash` | character varying(128) | 否 | 否 | — | 文件SHA-256 | — |
| `permission_scope` | character varying(32) | 是 | 否 | 'private'::character varying | 资料共享范围（private私有 public公共；下载及AI使用另行控制） | — |
| `allow_download` | boolean | 是 | 否 | true | 是否允许下载 | — |
| `allow_ai_use` | boolean | 是 | 否 | true | 是否允许用于AI | — |
| `parse_status` | character varying(32) | 是 | 否 | 'queued'::character varying | 文本解析状态（queued排队 parsing解析中 indexed已索引 failed失败） | — |
| `parse_message` | character varying(500) | 否 | 否 | — | 解析说明 | — |
| `summary` | text | 否 | 否 | — | 资料摘要 | — |
| `extracted_text` | text | 否 | 否 | — | 完整提取文本 | — |
| `tags` | json | 是 | 否 | — | 资料分类与检索标签JSON数组 | — |
| `metadata_json` | json | 是 | 否 | — | 资料解析与安全扫描元数据JSON对象；可含解析尝试和扫描器结果 | — |
| `version_no` | integer | 是 | 否 | 1 | 资料版本号 | — |
| `owner_id` | bigint | 是 | 否 | — | 所有者ID | FOREIGN KEY (owner_id) REFERENCES sys_user(user_id) ON DELETE RESTRICT |
| `owner_name` | character varying(64) | 是 | 否 | — | 所有者名称快照 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |
| `scan_status` | character varying(32) | 是 | 否 | 'pending'::character varying | 文件安全扫描状态（pending待扫描 clean通过 quarantined已隔离 failed扫描失败） | — |
| `scan_message` | character varying(500) | 否 | 否 | — | 安全扫描说明 | — |
| `scan_time` | timestamp without time zone | 否 | 否 | — | 安全扫描完成时间 | — |
| `scanner_name` | character varying(128) | 否 | 否 | — | 扫描器名称 | — |
| `parse_attempt_count` | integer | 是 | 否 | 0 | 解析尝试次数 | — |
| `parse_lease_owner` | character varying(128) | 否 | 否 | — | 解析执行器租约持有者 | — |
| `parse_lease_until` | timestamp without time zone | 否 | 否 | — | 解析执行器租约到期时间 | — |
| `parse_next_retry_at` | timestamp without time zone | 否 | 否 | — | 下次解析重试时间 | — |

## public.list_column

公共库字段信息兼容视图；按系统目录汇总列定义及关联约束标记

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `table_name` | name | 否 | 否 | — | 字段所属公共库源表名称 | — |
| `column_name` | name | 否 | 否 | — | 源表字段名称；取自pg_attribute.attname | — |
| `column_comment` | text | 否 | 否 | — | 源字段目录注释；取自pg_description，无注释时为空 | — |
| `is_required` | text | 否 | 否 | — | 兼容必填标记（1为非空且无关联约束，0为其他）；按当前视图口径计算 | — |
| `is_pk` | text | 否 | 否 | — | 兼容主键标记（1有关联约束 0无）；当前视图可能同时标记非主键约束 | — |
| `sort` | smallint | 否 | 否 | — | 源表字段物理序号；取自pg_attribute.attnum | — |
| `is_increment` | text | 否 | 否 | — | 兼容自增标记（1默认表达式包含约定序列名 0未匹配）；按当前视图口径计算 | — |
| `column_type` | text | 否 | 否 | — | 源字段类型名称；数组显示ARRAY，域类型显示基础类型 | — |

## public.list_table

公共库表信息兼容视图；列出表名及目录注释，时间列为查询事务时间

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `table_name` | name | 否 | 否 | — | 公共库源表名称；取自pg_class.relname | — |
| `table_comment` | text | 否 | 否 | — | 源表目录注释；取自obj_description，无注释时为空 | — |
| `create_time` | timestamp with time zone | 否 | 否 | — | 当前查询事务时间的兼容列；不是源表真实创建时间 | — |
| `update_time` | timestamp with time zone | 否 | 否 | — | 当前查询事务时间的兼容列；不是源表最近结构变更时间 | — |

## public.model_calls

管网模型单次调用审计表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `call_id` | character varying(64) | 是 | 是 | — | 调用审计ID | — |
| `task_id` | character varying(64) | 否 | 否 | — | 关联科研或业务任务ID | — |
| `user_id` | bigint | 否 | 否 | — | 发起用户ID | FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `scene` | character varying(32) | 是 | 否 | — | 业务场景 | — |
| `route_id` | character varying(64) | 否 | 否 | — | 路由ID | FOREIGN KEY (route_id) REFERENCES model_routes(route_id) ON DELETE SET NULL |
| `route_version_no` | integer | 否 | 否 | — | 路由版本号 | — |
| `prompt_version_id` | character varying(64) | 否 | 否 | — | 提示词版本ID | — |
| `template_version_id` | character varying(64) | 否 | 否 | — | 模板版本ID | — |
| `model_id` | bigint | 否 | 否 | — | 模型ID | FOREIGN KEY (model_id) REFERENCES ai_models(model_id) ON DELETE SET NULL |
| `model_code` | character varying(100) | 否 | 否 | — | 模型编码 | — |
| `provider` | character varying(50) | 否 | 否 | — | 模型服务商 | — |
| `attempt_no` | integer | 是 | 否 | 0 | 本次调用尝试序号 | — |
| `fallback_used` | boolean | 是 | 否 | false | 是否使用备用模型 | — |
| `status` | character varying(20) | 是 | 否 | — | 调用结果状态（success成功 failed失败 limit_exceeded超出调用限额） | — |
| `latency_ms` | integer | 否 | 否 | — | 本次模型调用耗时（毫秒，非负；未测得时为空） | — |
| `input_char_count` | integer | 是 | 否 | 0 | 输入字符数 | — |
| `output_char_count` | integer | 是 | 否 | 0 | 输出字符数 | — |
| `input_tokens` | integer | 否 | 否 | — | 输入Token数，供应商未返回时为空 | — |
| `output_tokens` | integer | 否 | 否 | — | 输出Token数，供应商未返回时为空 | — |
| `error_code` | character varying(64) | 否 | 否 | — | 安全错误编码 | — |
| `error_message` | character varying(1000) | 否 | 否 | — | 清洗后的错误摘要 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 调用时间 | — |

## public.model_route_usage

管网场景模型路由每日调用计数表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `route_id` | character varying(64) | 是 | 是 | — | 路由配置ID | FOREIGN KEY (route_id) REFERENCES model_routes(route_id) ON DELETE CASCADE |
| `usage_date` | timestamp without time zone | 是 | 是 | — | 统计日期（当天零点） | — |
| `call_count` | integer | 是 | 否 | 0 | 已占用调用次数 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |

## public.model_routes

管网业务场景模型路由配置表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `route_id` | character varying(64) | 是 | 是 | — | 路由配置ID | — |
| `scene` | character varying(32) | 是 | 否 | — | 模型路由业务场景（research科研报告 digest周期简报 data-filter数据过滤） | — |
| `primary_model_id` | bigint | 否 | 否 | — | 主模型ID | FOREIGN KEY (primary_model_id) REFERENCES ai_models(model_id) ON DELETE RESTRICT |
| `fallback_model_id` | bigint | 否 | 否 | — | 备用模型ID | FOREIGN KEY (fallback_model_id) REFERENCES ai_models(model_id) ON DELETE RESTRICT |
| `timeout_seconds` | integer | 是 | 否 | 30 | 单次模型调用超时时间（秒，1至120） | — |
| `max_tokens` | integer | 是 | 否 | 2048 | 单次模型最大输出Token数（1至32768） | — |
| `temperature` | double precision | 是 | 否 | 0.2 | 模型调用采样温度（0至2） | — |
| `daily_limit` | integer | 是 | 否 | 0 | 每日调用上限，0表示不限制 | — |
| `enabled` | boolean | 是 | 否 | false | 是否启用该场景路由 | — |
| `version_no` | integer | 是 | 否 | 1 | 路由配置版本 | — |
| `operator_id` | bigint | 否 | 否 | — | 最近操作人ID | FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `operator_name` | character varying(64) | 是 | 否 | ''::character varying | 最近操作人名称快照 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |

## public.news_articles

科技资讯文章表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `article_id` | character varying(64) | 是 | 是 | — | 文章ID | — |
| `article_type` | character varying(32) | 是 | 否 | — | 资讯来源类型（news新闻网站 wechat微信公众号） | — |
| `title` | character varying(500) | 是 | 否 | — | 标题 | — |
| `canonical_url` | character varying(1500) | 否 | 否 | — | 规范化地址 | — |
| `url_hash` | character varying(128) | 否 | 否 | — | 规范化地址指纹 | — |
| `source_id` | character varying(64) | 否 | 否 | — | 数据源ID | FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE SET NULL |
| `source_name` | character varying(255) | 否 | 否 | — | 数据源名称快照 | — |
| `collection_run_id` | character varying(64) | 否 | 否 | — | 采集运行ID | FOREIGN KEY (collection_run_id) REFERENCES collection_runs(run_id) ON DELETE SET NULL |
| `author_text` | character varying(500) | 否 | 否 | — | 作者 | — |
| `published_time` | timestamp without time zone | 否 | 否 | — | 来源站点原文发布时间；区别于平台审核发布时刻published_at | — |
| `discovered_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 发现时间 | — |
| `language` | character varying(16) | 是 | 否 | 'zh-CN'::character varying | 语言 | — |
| `summary` | text | 否 | 否 | — | 摘要 | — |
| `body` | text | 否 | 否 | — | 正文 | — |
| `article_hash` | character varying(128) | 否 | 否 | — | 正文指纹 | — |
| `relevance_score` | integer | 是 | 否 | 0 | 管网技术相关性评分（0至100；不是置信度或准确率） | — |
| `review_status` | character varying(32) | 是 | 否 | 'pending'::character varying | 内容审核状态（pending待审核 approved通过 rejected拒绝） | — |
| `permission_scope` | character varying(32) | 是 | 否 | 'public'::character varying | 内容可见范围（private私有 public公共；访问仍须执行授权检查） | — |
| `tags` | json | 是 | 否 | — | 文章分类与检索标签JSON数组 | — |
| `metadata_json` | json | 是 | 否 | — | 文章扩展元数据JSON对象；保留采集、分析及人工维护信息 | — |
| `analysis_version` | character varying(64) | 否 | 否 | — | 当前分析版本 | — |
| `handoff_status` | character varying(32) | 是 | 否 | 'pending'::character varying | 内容交接状态（pending待交接 dispatched已派发 processing处理中 completed完成 partial部分完成 failed失败 rejected业务拒绝） | — |
| `handoff_batch_id` | character varying(64) | 否 | 否 | — | 外部处理批次ID | — |
| `handoff_record_id` | character varying(128) | 否 | 否 | — | 外部处理记录ID | — |
| `handoff_trace_id` | character varying(64) | 否 | 否 | — | 外部Prompt血缘或处理追踪ID | — |
| `handoff_version` | character varying(64) | 否 | 否 | — | 外部处理版本 | — |
| `handoff_result_json` | json | 是 | 否 | '{}'::json | 外部处理返回的结果JSON对象快照；保留过滤判断与处理依据 | — |
| `handoff_time` | timestamp without time zone | 否 | 否 | — | 外部处理回执时间 | — |
| `handoff_error` | text | 否 | 否 | — | 外部处理错误摘要 | — |
| `version_no` | integer | 是 | 否 | 1 | 内容版本号 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |
| `reviewed_by` | bigint | 否 | 否 | — | 审核人ID | — |
| `reviewed_at` | timestamp without time zone | 否 | 否 | — | 审核时间 | — |
| `review_reason` | text | 否 | 否 | — | 审核意见 | — |
| `published_at` | timestamp without time zone | 否 | 否 | — | 平台审核通过并发布的时间；撤回或拒绝后清空 | — |

## public.papers

论文资料表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `paper_id` | character varying(64) | 是 | 是 | — | 论文ID | — |
| `title` | character varying(500) | 是 | 否 | — | 论文标题 | — |
| `canonical_url` | character varying(1500) | 否 | 否 | — | 论文来源地址 | — |
| `source_id` | character varying(64) | 否 | 否 | — | 数据源ID | FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE SET NULL |
| `source_name` | character varying(255) | 否 | 否 | — | 数据源名称快照 | — |
| `collection_run_id` | character varying(64) | 否 | 否 | — | 采集运行ID | FOREIGN KEY (collection_run_id) REFERENCES collection_runs(run_id) ON DELETE SET NULL |
| `authors` | character varying(1000) | 否 | 否 | — | 作者展示文本 | — |
| `authors_json` | json | 是 | 否 | — | 论文作者与机构信息JSON数组；保留采集时的结构 | — |
| `keywords` | json | 是 | 否 | — | 论文关键词JSON数组 | — |
| `doi` | character varying(255) | 否 | 否 | — | 原始DOI | — |
| `doi_normalized` | character varying(255) | 否 | 否 | — | 规范化DOI | — |
| `external_id` | character varying(255) | 否 | 否 | — | 外部数据库ID | — |
| `journal` | character varying(255) | 否 | 否 | — | 期刊或会议 | — |
| `publisher` | character varying(255) | 否 | 否 | — | 出版方 | — |
| `publication_year` | integer | 否 | 否 | — | 论文发表公历年份；非空时不得早于1600年 | — |
| `volume` | character varying(64) | 否 | 否 | — | 卷 | — |
| `issue` | character varying(64) | 否 | 否 | — | 期 | — |
| `pages` | character varying(64) | 否 | 否 | — | 页码 | — |
| `abstract_text` | text | 否 | 否 | — | 论文摘要 | — |
| `full_text_url` | character varying(1500) | 否 | 否 | — | 合法全文地址 | — |
| `citation_count` | integer | 是 | 否 | 0 | 引用次数 | — |
| `open_access_status` | character varying(32) | 是 | 否 | 'unknown'::character varying | 论文开放获取状态编码；unknown表示尚未核实 | — |
| `full_text_status` | character varying(32) | 是 | 否 | 'unknown'::character varying | 合法全文可获取状态编码；unknown表示尚未核实 | — |
| `review_status` | character varying(32) | 是 | 否 | 'pending'::character varying | 内容审核状态（pending待审核 approved通过 rejected拒绝） | — |
| `permission_scope` | character varying(32) | 是 | 否 | 'public'::character varying | 内容可见范围（private私有 public公共；访问仍须执行授权检查） | — |
| `tags` | json | 是 | 否 | — | 论文分类与检索标签JSON数组 | — |
| `metadata_json` | json | 是 | 否 | — | 论文扩展元数据JSON对象；保留来源、分析及人工维护信息 | — |
| `handoff_status` | character varying(32) | 是 | 否 | 'pending'::character varying | 内容交接状态（pending待交接 dispatched已派发 processing处理中 completed完成 partial部分完成 failed失败 rejected业务拒绝） | — |
| `handoff_batch_id` | character varying(64) | 否 | 否 | — | 外部处理批次ID | — |
| `handoff_record_id` | character varying(128) | 否 | 否 | — | 外部处理记录ID | — |
| `handoff_trace_id` | character varying(64) | 否 | 否 | — | 外部Prompt血缘或处理追踪ID | — |
| `handoff_version` | character varying(64) | 否 | 否 | — | 外部处理版本 | — |
| `handoff_result_json` | json | 是 | 否 | '{}'::json | 外部处理返回的结果JSON对象快照；保留过滤判断与处理依据 | — |
| `handoff_time` | timestamp without time zone | 否 | 否 | — | 外部处理回执时间 | — |
| `handoff_error` | text | 否 | 否 | — | 外部处理错误摘要 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |
| `reviewed_by` | bigint | 否 | 否 | — | 审核人ID | — |
| `reviewed_at` | timestamp without time zone | 否 | 否 | — | 审核时间 | — |
| `review_reason` | text | 否 | 否 | — | 审核意见 | — |
| `published_at` | timestamp without time zone | 否 | 否 | — | 平台审核通过并发布的时间；区别于论文原始发表年份 | — |

## public.prompt_versions

管网模型提示词版本表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `prompt_id` | character varying(64) | 是 | 是 | — | 提示词版本ID | — |
| `prompt_key` | character varying(64) | 是 | 否 | — | 稳定提示词编码 | — |
| `scene` | character varying(64) | 是 | 否 | — | 业务场景 | — |
| `name` | character varying(255) | 是 | 否 | — | 提示词名称 | — |
| `description` | character varying(1000) | 是 | 否 | ''::character varying | 用途说明 | — |
| `system_prompt` | text | 是 | 否 | — | 系统提示词 | — |
| `user_prompt` | text | 是 | 否 | — | 用户提示词模板 | — |
| `version_no` | integer | 是 | 否 | 1 | 版本号 | — |
| `status` | character varying(32) | 是 | 否 | 'draft'::character varying | 提示词版本状态（draft草稿 published已发布 retired已退役） | — |
| `test_status` | character varying(32) | 是 | 否 | 'untested'::character varying | 离线测试状态（untested未测试 passed通过 failed失败） | — |
| `test_result` | json | 是 | 否 | — | 最近一次提示词离线结构测试结果JSON对象；不代表真实模型效果评估 | — |
| `operator_id` | bigint | 否 | 否 | — | 操作用户ID | FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `operator_name` | character varying(64) | 是 | 否 | ''::character varying | 操作用户名称快照 | — |
| `published_at` | timestamp without time zone | 否 | 否 | — | 发布时间 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |

## public.quality_issue_events

管网情报质量问题治理事件表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `event_id` | character varying(64) | 是 | 是 | — | 治理事件ID | — |
| `issue_id` | character varying(64) | 是 | 否 | — | 质量问题ID | FOREIGN KEY (issue_id) REFERENCES quality_issues(issue_id) ON DELETE CASCADE |
| `from_status` | character varying(16) | 否 | 否 | — | 变更前质量问题状态；采用open、resolved或ignored编码 | — |
| `to_status` | character varying(16) | 是 | 否 | — | 变更后质量问题状态（open待处理 resolved已解决 ignored已忽略） | — |
| `action` | character varying(16) | 是 | 否 | — | 质量治理动作（resolve解决 ignore忽略 reopen重新打开） | — |
| `reason` | text | 是 | 否 | — | 处理说明 | — |
| `operator_id` | bigint | 否 | 否 | — | 处理人ID | FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `operator_name` | character varying(64) | 是 | 否 | ''::character varying | 处理人名称快照 | — |
| `snapshot_json` | json | 是 | 否 | '{}'::json | 质量问题变更前后状态及处理依据JSON对象快照 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 事件时间 | — |

## public.quality_issues

管网情报质量问题登记表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `issue_id` | character varying(64) | 是 | 是 | — | 质量问题ID | — |
| `content_type` | character varying(16) | 是 | 否 | — | 内容类型：article或paper | — |
| `content_id` | character varying(64) | 是 | 否 | — | 内容ID | — |
| `issue_code` | character varying(32) | 是 | 否 | — | 质量问题编码（duplicate重复 missing字段缺失 tag标签异常 parse处理失败 review待审核） | — |
| `severity` | character varying(16) | 是 | 否 | 'warning'::character varying | 问题严重级别（error错误 warning警告 info提示） | — |
| `evidence` | json | 是 | 否 | '{}'::json | 检测到问题时的证据JSON对象快照 | — |
| `description` | text | 是 | 否 | — | 问题描述 | — |
| `suggestion` | text | 是 | 否 | ''::text | 建议动作 | — |
| `status` | character varying(16) | 是 | 否 | 'open'::character varying | 质量问题状态（open待处理 resolved已解决 ignored已忽略） | — |
| `resolution` | text | 否 | 否 | — | 处理说明 | — |
| `operator_id` | bigint | 否 | 否 | — | 处理人ID | FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `operator_name` | character varying(64) | 是 | 否 | ''::character varying | 处理人名称快照 | — |
| `first_seen_at` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 首次发现时间 | — |
| `last_seen_at` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 最近发现时间 | — |
| `resolved_at` | timestamp without time zone | 否 | 否 | — | 处理时间 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |

## public.report_exports

报告导出任务和文件审计表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `export_id` | character varying(64) | 是 | 是 | — | 导出任务ID | — |
| `report_id` | character varying(64) | 是 | 否 | — | 报告ID | FOREIGN KEY (report_id) REFERENCES reports(report_id) ON DELETE CASCADE |
| `user_id` | bigint | 是 | 否 | — | 导出用户ID | FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE RESTRICT |
| `report_version_no` | integer | 是 | 否 | — | 报告版本号快照 | — |
| `report_revision` | timestamp without time zone | 是 | 否 | — | 报告修订时间快照 | — |
| `format` | character varying(16) | 是 | 否 | — | 成果文件导出格式（docx或pdf） | — |
| `template_version` | character varying(64) | 否 | 否 | — | 模板版本快照 | — |
| `file_name` | character varying(500) | 是 | 否 | — | 导出文件名 | — |
| `file_key` | character varying(500) | 是 | 否 | — | 受控存储键 | — |
| `content_type` | character varying(128) | 是 | 否 | — | 文件媒体类型 | — |
| `file_size` | bigint | 是 | 否 | '0'::bigint | 导出文件大小（字节，非负） | — |
| `file_hash` | character varying(128) | 否 | 否 | — | 文件SHA-256 | — |
| `snapshot` | json | 是 | 否 | — | 导出时冻结的成果正文、元数据及修订信息JSON对象快照 | — |
| `status` | character varying(32) | 是 | 否 | 'queued'::character varying | 导出任务状态（queued排队 running执行中 completed完成 failed失败） | — |
| `error_message` | text | 否 | 否 | — | 失败说明 | — |
| `create_time` | timestamp without time zone | 是 | 否 | — | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | — | 更新时间 | — |
| `completed_time` | timestamp without time zone | 否 | 否 | — | 完成时间 | — |
| `attempt_count` | integer | 是 | 否 | 0 | 执行尝试次数 | — |
| `lease_owner` | character varying(128) | 否 | 否 | — | 当前执行器租约持有者 | — |
| `lease_until` | timestamp without time zone | 否 | 否 | — | 当前执行器租约到期时间 | — |
| `next_retry_at` | timestamp without time zone | 否 | 否 | — | 下次重试时间 | — |

## public.report_publications

报告正式发布与撤销发布审计记录表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `publication_id` | character varying(64) | 是 | 是 | — | 发布记录ID | — |
| `report_id` | character varying(64) | 是 | 否 | — | 报告ID | FOREIGN KEY (report_id) REFERENCES reports(report_id) ON DELETE CASCADE |
| `report_version_no` | integer | 是 | 否 | — | 发布时的报告版本号 | — |
| `action` | character varying(16) | 是 | 否 | — | 发布操作（publish正式发布 unpublish撤销发布） | — |
| `operator_id` | bigint | 否 | 否 | — | 操作用户ID | FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `operator_name` | character varying(64) | 是 | 否 | — | 操作用户名称快照 | — |
| `note` | text | 否 | 否 | — | 发布或撤销说明 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 操作时间 | — |

## public.report_versions

报告版本表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `report_version_id` | bigint | 是 | 是 | nextval('report_versions_report_version_id_seq'::regclass) | 成果历史修订记录自增ID | — |
| `report_id` | character varying(64) | 是 | 否 | — | 报告ID | FOREIGN KEY (report_id) REFERENCES reports(report_id) ON DELETE CASCADE |
| `version_no` | integer | 是 | 否 | — | 版本号 | — |
| `title` | character varying(500) | 是 | 否 | — | 版本标题 | — |
| `content` | text | 是 | 否 | — | 版本正文 | — |
| `sections` | json | 是 | 否 | — | 该历史修订的结构化章节JSON数组快照 | — |
| `citations` | json | 是 | 否 | — | 该历史修订引用证据的权威JSON数组快照 | — |
| `quality_issues` | json | 是 | 否 | — | 该历史修订的质量检查问题JSON数组快照 | — |
| `model_snapshot` | json | 是 | 否 | — | 历史修订使用的模型、提示词及模板配置JSON对象快照 | — |
| `source` | character varying(32) | 是 | 否 | 'manual'::character varying | 修订来源（generated生成 retry重试 manual手工 autosave自动保存 publish发布 restored恢复） | — |
| `operator_id` | bigint | 否 | 否 | — | 操作用户ID | FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `operator_name` | character varying(64) | 是 | 否 | — | 操作用户名称快照 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |

## public.reports

科研报告与周期情报简报当前状态表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `report_id` | character varying(64) | 是 | 是 | — | 报告ID | — |
| `source_task_id` | character varying(64) | 否 | 否 | — | 来源任务ID；任务与报告关系的唯一权威字段 | FOREIGN KEY (source_task_id) REFERENCES generation_tasks(task_id) ON DELETE SET NULL |
| `user_id` | bigint | 是 | 否 | — | 所有者ID | FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE RESTRICT |
| `owner_name` | character varying(64) | 是 | 否 | — | 所有者名称快照 | — |
| `title` | character varying(500) | 是 | 否 | — | 报告标题 | — |
| `report_type` | character varying(64) | 是 | 否 | — | 成果业务类型编码；daily、weekly、monthly分别表示日报、周报、月报 | — |
| `status` | character varying(32) | 是 | 否 | 'draft'::character varying | 成果状态（draft草稿 reviewing审核中 completed完成 published已发布 archived已归档） | — |
| `version_no` | integer | 是 | 否 | 1 | 成果当前修订版本号（从1开始） | — |
| `content` | text | 是 | 否 | — | Markdown正文 | — |
| `sections` | json | 是 | 否 | — | 当前修订的结构化章节JSON数组 | — |
| `citations` | json | 是 | 否 | — | 当前修订引用证据的权威JSON数组快照 | — |
| `quality_issues` | json | 是 | 否 | — | 当前成果的质量检查问题JSON数组 | — |
| `metadata_json` | json | 是 | 否 | — | 成果扩展元数据JSON对象；可含审核要求、图形及生成配置 | — |
| `word_count` | integer | 是 | 否 | 0 | 成果字数（非负，按服务正文统计口径计算） | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |

## public.sys_config

参数配置表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `config_id` | integer | 是 | 是 | nextval('sys_config_config_id_seq'::regclass) | 参数主键 | — |
| `config_name` | character varying(100) | 否 | 否 | ''::character varying | 参数名称 | — |
| `config_key` | character varying(100) | 否 | 否 | ''::character varying | 参数键名 | — |
| `config_value` | character varying(500) | 否 | 否 | ''::character varying | 参数键值 | — |
| `config_type` | character(1) | 否 | 否 | 'N'::bpchar | 系统内置（Y是 N否） | — |
| `create_by` | character varying(64) | 否 | 否 | ''::character varying | 创建者 | — |
| `create_time` | timestamp(0) without time zone | 否 | 否 | — | 创建时间 | — |
| `update_by` | character varying(64) | 否 | 否 | ''::character varying | 更新者 | — |
| `update_time` | timestamp(0) without time zone | 否 | 否 | — | 更新时间 | — |
| `remark` | character varying(500) | 否 | 否 | NULL::character varying | 备注 | — |

## public.sys_dict_data

字典数据表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `dict_code` | bigint | 是 | 是 | nextval('sys_dict_data_dict_code_seq'::regclass) | 字典编码 | — |
| `dict_sort` | integer | 否 | 否 | 0 | 字典排序 | — |
| `dict_label` | character varying(100) | 否 | 否 | ''::character varying | 字典标签 | — |
| `dict_value` | character varying(100) | 否 | 否 | ''::character varying | 字典键值 | — |
| `dict_type` | character varying(100) | 否 | 否 | ''::character varying | 字典类型 | FOREIGN KEY (dict_type) REFERENCES sys_dict_type(dict_type) ON UPDATE CASCADE ON DELETE CASCADE |
| `css_class` | character varying(100) | 否 | 否 | NULL::character varying | 样式属性（其他样式扩展） | — |
| `list_class` | character varying(100) | 否 | 否 | NULL::character varying | 表格回显样式 | — |
| `is_default` | character(1) | 否 | 否 | 'N'::bpchar | 是否默认（Y是 N否） | — |
| `status` | character(1) | 否 | 否 | '0'::bpchar | 状态（0正常 1停用） | — |
| `create_by` | character varying(64) | 否 | 否 | ''::character varying | 创建者 | — |
| `create_time` | timestamp(0) without time zone | 否 | 否 | — | 创建时间 | — |
| `update_by` | character varying(64) | 否 | 否 | ''::character varying | 更新者 | — |
| `update_time` | timestamp(0) without time zone | 否 | 否 | — | 更新时间 | — |
| `remark` | character varying(500) | 否 | 否 | NULL::character varying | 备注 | — |

## public.sys_dict_type

字典类型表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `dict_id` | bigint | 是 | 是 | nextval('sys_dict_type_dict_id_seq'::regclass) | 字典主键 | — |
| `dict_name` | character varying(100) | 否 | 否 | ''::character varying | 字典名称 | — |
| `dict_type` | character varying(100) | 否 | 否 | ''::character varying | 字典类型 | — |
| `status` | character(1) | 否 | 否 | '0'::bpchar | 状态（0正常 1停用） | — |
| `create_by` | character varying(64) | 否 | 否 | ''::character varying | 创建者 | — |
| `create_time` | timestamp(0) without time zone | 否 | 否 | — | 创建时间 | — |
| `update_by` | character varying(64) | 否 | 否 | ''::character varying | 更新者 | — |
| `update_time` | timestamp(0) without time zone | 否 | 否 | — | 更新时间 | — |
| `remark` | character varying(500) | 否 | 否 | NULL::character varying | 备注 | — |

## public.sys_job

定时任务调度表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `job_id` | bigint | 是 | 是 | nextval('sys_job_job_id_seq'::regclass) | 任务ID | — |
| `job_name` | character varying(64) | 否 | 否 | ''::character varying | 任务名称 | — |
| `job_group` | character varying(64) | 否 | 否 | 'default'::character varying | 任务组名 | — |
| `job_executor` | character varying(64) | 否 | 否 | 'default'::character varying | 任务执行器 | — |
| `invoke_target` | character varying(500) | 是 | 否 | — | 调用目标字符串 | — |
| `job_args` | character varying(255) | 否 | 否 | ''::character varying | 调用位置参数文本；按英文逗号分隔后传给执行函数 | — |
| `job_kwargs` | character varying(255) | 否 | 否 | ''::character varying | 调用关键字参数的JSON对象文本 | — |
| `cron_expression` | character varying(255) | 否 | 否 | ''::character varying | cron执行表达式 | — |
| `misfire_policy` | character varying(20) | 否 | 否 | '3'::character varying | 错过触发策略编码；当前实现中2合并补跑，3使用超长宽限期，其他不合并且不限制宽限期 | — |
| `concurrent` | character(1) | 否 | 否 | '1'::bpchar | 是否并发执行（0允许 1禁止） | — |
| `status` | character(1) | 否 | 否 | '0'::bpchar | 状态（0正常 1暂停） | — |
| `create_by` | character varying(64) | 否 | 否 | ''::character varying | 创建者 | — |
| `create_time` | timestamp(0) without time zone | 否 | 否 | — | 创建时间 | — |
| `update_by` | character varying(64) | 否 | 否 | ''::character varying | 更新者 | — |
| `update_time` | timestamp(0) without time zone | 否 | 否 | — | 更新时间 | — |
| `remark` | character varying(500) | 否 | 否 | ''::character varying | 备注信息 | — |

## public.sys_job_log

定时任务调度日志表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `job_log_id` | bigint | 是 | 是 | nextval('sys_job_log_job_log_id_seq'::regclass) | 任务日志ID | — |
| `job_id` | bigint | 否 | 否 | — | 任务ID | FOREIGN KEY (job_id) REFERENCES sys_job(job_id) ON DELETE SET NULL |
| `job_name` | character varying(64) | 是 | 否 | — | 任务名称 | — |
| `job_group` | character varying(64) | 是 | 否 | — | 任务组名 | — |
| `job_executor` | character varying(64) | 是 | 否 | — | 任务执行器 | — |
| `invoke_target` | character varying(500) | 是 | 否 | — | 调用目标字符串 | — |
| `job_args` | character varying(255) | 否 | 否 | ''::character varying | 执行时的位置参数快照；英文逗号分隔文本 | — |
| `job_kwargs` | character varying(255) | 否 | 否 | ''::character varying | 执行时的关键字参数快照；JSON对象文本 | — |
| `job_trigger` | character varying(255) | 否 | 否 | ''::character varying | 任务触发器 | — |
| `job_message` | character varying(500) | 否 | 否 | — | 日志信息 | — |
| `status` | character(1) | 否 | 否 | '0'::bpchar | 执行状态（0正常 1失败） | — |
| `exception_info` | character varying(2000) | 否 | 否 | ''::character varying | 异常信息 | — |
| `create_time` | timestamp(0) without time zone | 否 | 否 | — | 创建时间 | — |

## public.sys_logininfor

系统访问记录

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `info_id` | bigint | 是 | 是 | nextval('sys_logininfor_info_id_seq'::regclass) | 访问ID | — |
| `user_name` | character varying(50) | 否 | 否 | ''::character varying | 用户账号 | — |
| `ipaddr` | character varying(128) | 否 | 否 | ''::character varying | 登录IP地址 | — |
| `login_location` | character varying(255) | 否 | 否 | ''::character varying | 登录地点 | — |
| `browser` | character varying(50) | 否 | 否 | ''::character varying | 浏览器类型 | — |
| `os` | character varying(50) | 否 | 否 | ''::character varying | 操作系统 | — |
| `status` | character(1) | 否 | 否 | '0'::bpchar | 登录状态（0成功 1失败） | — |
| `msg` | character varying(255) | 否 | 否 | ''::character varying | 提示消息 | — |
| `login_time` | timestamp(0) without time zone | 否 | 否 | — | 访问时间 | — |

## public.sys_menu

菜单权限表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `menu_id` | bigint | 是 | 是 | nextval('sys_menu_menu_id_seq'::regclass) | 菜单ID | — |
| `menu_name` | character varying(50) | 是 | 否 | — | 菜单名称 | — |
| `parent_id` | bigint | 否 | 否 | 0 | 父菜单ID | — |
| `order_num` | integer | 否 | 否 | 0 | 显示顺序 | — |
| `path` | character varying(200) | 否 | 否 | ''::character varying | 路由地址 | — |
| `component` | character varying(255) | 否 | 否 | NULL::character varying | 组件路径 | — |
| `query` | character varying(255) | 否 | 否 | NULL::character varying | 路由默认查询参数的JSON文本；空值表示无默认参数 | — |
| `route_name` | character varying(50) | 否 | 否 | ''::character varying | 路由名称 | — |
| `is_frame` | integer | 否 | 否 | 1 | 是否为外链（0是 1否） | — |
| `is_cache` | integer | 否 | 否 | 0 | 是否缓存（0缓存 1不缓存） | — |
| `menu_type` | character(1) | 否 | 否 | ''::bpchar | 菜单类型（M目录 C菜单 F按钮） | — |
| `visible` | character(1) | 否 | 否 | '0'::bpchar | 菜单状态（0显示 1隐藏） | — |
| `status` | character(1) | 否 | 否 | '0'::bpchar | 菜单状态（0正常 1停用） | — |
| `perms` | character varying(100) | 否 | 否 | NULL::character varying | 权限标识 | — |
| `icon` | character varying(100) | 否 | 否 | '#'::character varying | 菜单图标 | — |
| `create_by` | character varying(64) | 否 | 否 | ''::character varying | 创建者 | — |
| `create_time` | timestamp(0) without time zone | 否 | 否 | — | 创建时间 | — |
| `update_by` | character varying(64) | 否 | 否 | ''::character varying | 更新者 | — |
| `update_time` | timestamp(0) without time zone | 否 | 否 | — | 更新时间 | — |
| `remark` | character varying(500) | 否 | 否 | ''::character varying | 备注 | — |

## public.sys_oper_log

操作日志记录

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `oper_id` | bigint | 是 | 是 | nextval('sys_oper_log_oper_id_seq'::regclass) | 日志主键 | — |
| `title` | character varying(50) | 否 | 否 | ''::character varying | 模块标题 | — |
| `business_type` | integer | 否 | 否 | 0 | 业务操作类型（0其他 1新增 2修改 3删除 4授权 5导出 6导入 7强退 8生成代码 9清空） | — |
| `method` | character varying(100) | 否 | 否 | ''::character varying | 方法名称 | — |
| `request_method` | character varying(10) | 否 | 否 | ''::character varying | 请求方式 | — |
| `operator_type` | integer | 否 | 否 | 0 | 操作类别（0其它 1后台用户 2手机端用户） | — |
| `oper_name` | character varying(50) | 否 | 否 | ''::character varying | 操作人员 | — |
| `oper_url` | character varying(255) | 否 | 否 | ''::character varying | 请求URL | — |
| `oper_ip` | character varying(128) | 否 | 否 | ''::character varying | 主机地址 | — |
| `oper_location` | character varying(255) | 否 | 否 | ''::character varying | 操作地点 | — |
| `oper_param` | character varying(2000) | 否 | 否 | ''::character varying | 经日志清洗及长度限制后的请求参数文本 | — |
| `json_result` | character varying(2000) | 否 | 否 | ''::character varying | 经日志清洗及长度限制后的响应结果文本 | — |
| `status` | integer | 否 | 否 | 0 | 操作状态（0正常 1异常） | — |
| `error_msg` | character varying(2000) | 否 | 否 | ''::character varying | 错误消息 | — |
| `oper_time` | timestamp(0) without time zone | 否 | 否 | — | 操作时间 | — |
| `cost_time` | bigint | 否 | 否 | 0 | 本次操作处理耗时（毫秒） | — |

## public.sys_role

角色信息表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `role_id` | bigint | 是 | 是 | nextval('sys_role_role_id_seq'::regclass) | 角色ID | — |
| `role_name` | character varying(30) | 是 | 否 | — | 角色名称 | — |
| `role_key` | character varying(100) | 是 | 否 | — | 角色权限字符串 | — |
| `role_sort` | integer | 是 | 否 | — | 显示顺序 | — |
| `data_scope` | character(1) | 否 | 否 | '1'::bpchar | 数据范围（1全部数据 5仅本人） | — |
| `menu_check_strictly` | smallint | 否 | 否 | 1 | 菜单树选择项是否关联显示 | — |
| `status` | character(1) | 是 | 否 | — | 角色状态（0正常 1停用） | — |
| `del_flag` | character(1) | 否 | 否 | '0'::bpchar | 删除标志（0代表存在 2代表删除） | — |
| `create_by` | character varying(64) | 否 | 否 | ''::character varying | 创建者 | — |
| `create_time` | timestamp(0) without time zone | 否 | 否 | — | 创建时间 | — |
| `update_by` | character varying(64) | 否 | 否 | ''::character varying | 更新者 | — |
| `update_time` | timestamp(0) without time zone | 否 | 否 | — | 更新时间 | — |
| `remark` | character varying(500) | 否 | 否 | NULL::character varying | 备注 | — |

## public.sys_role_menu

角色和菜单关联表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `role_id` | bigint | 是 | 是 | — | 角色ID | FOREIGN KEY (role_id) REFERENCES sys_role(role_id) ON DELETE CASCADE |
| `menu_id` | bigint | 是 | 是 | — | 菜单ID | FOREIGN KEY (menu_id) REFERENCES sys_menu(menu_id) ON DELETE CASCADE |

## public.sys_user

用户信息表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `user_id` | bigint | 是 | 是 | nextval('sys_user_user_id_seq'::regclass) | 用户ID | — |
| `user_name` | character varying(30) | 是 | 否 | — | 用户账号；软删除后仍保留且不可复用 | — |
| `nick_name` | character varying(30) | 是 | 否 | — | 用户昵称 | — |
| `user_type` | character varying(2) | 否 | 否 | '00'::character varying | 用户类型（00系统用户） | — |
| `email` | character varying(50) | 否 | 否 | ''::character varying | 用户邮箱 | — |
| `phonenumber` | character varying(11) | 否 | 否 | ''::character varying | 手机号码 | — |
| `sex` | character(1) | 否 | 否 | '0'::bpchar | 用户性别（0男 1女 2未知） | — |
| `avatar` | character varying(100) | 否 | 否 | ''::character varying | 头像地址 | — |
| `password` | character varying(100) | 否 | 否 | ''::character varying | 登录密码的bcrypt加盐哈希；不存储明文密码 | — |
| `status` | character(1) | 否 | 否 | '0'::bpchar | 帐号状态（0正常 1停用） | — |
| `del_flag` | character(1) | 否 | 否 | '0'::bpchar | 删除标志（0代表存在 2代表删除） | — |
| `login_ip` | character varying(128) | 否 | 否 | ''::character varying | 最后登录IP | — |
| `login_date` | timestamp(0) without time zone | 否 | 否 | — | 最后登录时间 | — |
| `pwd_update_date` | timestamp(0) without time zone | 否 | 否 | — | 密码最后更新时间 | — |
| `create_by` | character varying(64) | 否 | 否 | ''::character varying | 创建者 | — |
| `create_time` | timestamp(0) without time zone | 否 | 否 | — | 创建时间 | — |
| `update_by` | character varying(64) | 否 | 否 | ''::character varying | 更新者 | — |
| `update_time` | timestamp(0) without time zone | 否 | 否 | — | 更新时间 | — |
| `remark` | character varying(500) | 否 | 否 | NULL::character varying | 备注 | — |

## public.sys_user_role

用户和角色关联表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `user_id` | bigint | 是 | 是 | — | 用户ID | FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE CASCADE |
| `role_id` | bigint | 是 | 是 | — | 角色ID | FOREIGN KEY (role_id) REFERENCES sys_role(role_id) ON DELETE CASCADE |

## public.template_versions

管网科研与情报模板版本表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `template_id` | character varying(64) | 是 | 是 | — | 模板版本ID | — |
| `template_key` | character varying(64) | 是 | 否 | — | 稳定模板编码 | — |
| `code` | character varying(32) | 是 | 否 | — | 模板展示编码 | — |
| `category` | character varying(32) | 是 | 否 | — | 模板分类 | — |
| `report_type` | character varying(64) | 是 | 否 | — | 报告类型 | — |
| `name` | character varying(255) | 是 | 否 | — | 模板名称 | — |
| `description` | character varying(1000) | 是 | 否 | ''::character varying | 模板说明 | — |
| `color` | character varying(32) | 是 | 否 | '#2764e7'::character varying | 展示颜色 | — |
| `version_label` | character varying(32) | 是 | 否 | — | 展示版本号 | — |
| `version_no` | integer | 是 | 否 | 1 | 版本序号 | — |
| `status` | character varying(32) | 是 | 否 | 'draft'::character varying | 模板版本状态（draft草稿 published已发布 retired已退役） | — |
| `formats` | json | 是 | 否 | — | 模板支持的输出格式编码JSON数组 | — |
| `sections` | json | 是 | 否 | — | 模板章节定义JSON数组；保存章节顺序及结构配置 | — |
| `usage_count` | integer | 是 | 否 | 0 | 使用次数快照 | — |
| `operator_id` | bigint | 否 | 否 | — | 操作用户ID | FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL |
| `operator_name` | character varying(64) | 是 | 否 | ''::character varying | 操作用户名称快照 | — |
| `published_at` | timestamp without time zone | 否 | 否 | — | 发布时间 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
| `update_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 更新时间 | — |

## public.user_saved_items

用户收藏与资料篮表

| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |
| --- | --- | --- | --- | --- | --- | --- |
| `saved_item_id` | bigint | 是 | 是 | nextval('user_saved_items_saved_item_id_seq'::regclass) | 收藏记录ID | — |
| `user_id` | bigint | 是 | 否 | — | 用户ID | FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE CASCADE |
| `item_id` | character varying(64) | 是 | 否 | — | 业务条目ID | — |
| `item_type` | character varying(32) | 是 | 否 | — | 条目类型（material资料文件 article资讯 paper论文 report报告） | — |
| `action` | character varying(16) | 是 | 否 | — | 用户保存动作（favorite收藏 basket加入资料篮） | — |
| `title` | character varying(500) | 是 | 否 | — | 标题快照 | — |
| `snapshot` | json | 是 | 否 | — | 收藏或加入资料篮时的条目信息JSON对象快照 | — |
| `create_time` | timestamp without time zone | 是 | 否 | CURRENT_TIMESTAMP | 创建时间 | — |
