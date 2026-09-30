-- pipeline_news.news 字段注释补充（一次性迁移）
-- PostgreSQL 18.4 / pipeline_news / news schema
-- 已于 2026-08-18 执行成功；重复执行仅会覆盖相同备注，不修改结构或数据。
-- 只补充 COMMENT，不修改字段、索引、分区或数据。

\set ON_ERROR_STOP on

COMMENT ON COLUMN news.hp_news.prompt_trace_id IS
    '提示词处理血缘批次 ULID；同一新闻处理过程的详细 Prompt 使用记录见 news.news_prompt_usage';

COMMENT ON COLUMN news.sys_prompt_version.prompt_version_id IS
    '提示词版本主键';
COMMENT ON COLUMN news.sys_prompt_version.parent_prompt_version_id IS
    '直接派生来源的提示词版本 ID；为空表示根版本；允许跨 prompt_key 派生';
COMMENT ON COLUMN news.sys_prompt_version.prompt_key IS
    '提示词稳定业务键，例如 politics.filter 或 common.entity_extract';
COMMENT ON COLUMN news.sys_prompt_version.prompt_name IS
    '提示词展示名称';
COMMENT ON COLUMN news.sys_prompt_version.prompt_type IS
    '提示词处理类型，例如 FILTER、CLASSIFY、CLASSIFY_CRITERION、SCORE、WARNING、ENTITY_EXTRACT';
COMMENT ON COLUMN news.sys_prompt_version.domain_id IS
    '适用领域 ID；为空表示全局提示词';
COMMENT ON COLUMN news.sys_prompt_version.category_id IS
    '适用分类 ID；为空表示非分类专属提示词';
COMMENT ON COLUMN news.sys_prompt_version.version_no IS
    '同一 prompt_key 下的递增版本号';
COMMENT ON COLUMN news.sys_prompt_version.system_prompt IS
    'System Prompt 模板正文';
COMMENT ON COLUMN news.sys_prompt_version.user_prompt IS
    'User Prompt 模板正文';
COMMENT ON COLUMN news.sys_prompt_version.template_variables IS
    '模板所需变量名称及变量说明，JSONB 格式';
COMMENT ON COLUMN news.sys_prompt_version.content_hash IS
    '规范化 Prompt 内容的 SHA-256 小写十六进制摘要';
COMMENT ON COLUMN news.sys_prompt_version.status IS
    '提示词状态：draft 草稿、published 已发布、retired 已退役';
COMMENT ON COLUMN news.sys_prompt_version.derivation_note IS
    '从父版本派生时的改动说明和原因';
COMMENT ON COLUMN news.sys_prompt_version.created_by IS
    '提示词版本创建人';
COMMENT ON COLUMN news.sys_prompt_version.created_at IS
    '提示词版本创建时间';
COMMENT ON COLUMN news.sys_prompt_version.updated_at IS
    '提示词版本最后修改时间；由更新时间触发器维护';
COMMENT ON COLUMN news.sys_prompt_version.published_at IS
    '提示词版本正式发布时间；published 状态必须有值';

COMMENT ON COLUMN news.news_prompt_usage.usage_id IS
    '新闻提示词使用记录主键';
COMMENT ON COLUMN news.news_prompt_usage.prompt_trace_id IS
    '提示词处理血缘批次 ULID，关联 news.hp_news.prompt_trace_id';
COMMENT ON COLUMN news.news_prompt_usage.news_id IS
    '新闻主表 ID，配合 news_create_time 定位分区新闻行';
COMMENT ON COLUMN news.news_prompt_usage.news_create_time IS
    '新闻主表 create_time 分区键，配合 news_id 和 prompt_trace_id 建立复合外键';
COMMENT ON COLUMN news.news_prompt_usage.prompt_version_id IS
    '本次新闻处理实际使用的提示词版本 ID';
COMMENT ON COLUMN news.news_prompt_usage.stage IS
    '提示词执行阶段，例如 FILTER、CLASSIFY、SCORE、WARNING、ENTITY_EXTRACT';
COMMENT ON COLUMN news.news_prompt_usage.sequence_no IS
    '本次新闻处理过程中提示词的执行顺序号';
COMMENT ON COLUMN news.news_prompt_usage.model_name IS
    '实际调用的模型名称';
COMMENT ON COLUMN news.news_prompt_usage.created_at IS
    '提示词使用记录创建时间';

COMMENT ON COLUMN news.act_domain_topic_actions.domain_id IS
    '领域 ID';
COMMENT ON COLUMN news.act_domain_topic_actions.category_id IS
    '分类 ID';
COMMENT ON COLUMN news.act_domain_topic_actions.category_prompts IS
    '迁移兼容字段：历史内嵌分类提示词；切换到 prompt_version_id 后应删除';
COMMENT ON COLUMN news.act_domain_topic_actions.prompt_version_id IS
    '分类标准提示词版本 ID；最终分类 Prompt 内容来源';
COMMENT ON COLUMN news.act_domain_topic_actions.created_at IS
    '领域分类绑定创建时间';
COMMENT ON COLUMN news.act_domain_topic_actions.updated_at IS
    '领域分类绑定最后修改时间；由更新时间触发器维护';

COMMENT ON COLUMN news.news_embedding.news_id IS
    '新闻主表 ID，配合 news_create_time 定位分区新闻行';
COMMENT ON COLUMN news.news_embedding.news_create_time IS
    '新闻主表 create_time 分区键；向量表复合主键第二列';
COMMENT ON COLUMN news.news_embedding.uuid IS
    '业务新闻 UUID 快照；不保证唯一';
COMMENT ON COLUMN news.news_embedding.embedding IS
    '新闻语义向量；当前模型输出为 1024 维，使用 cosine 距离';
COMMENT ON COLUMN news.news_embedding.embedding_model IS
    '生成该向量的 Embedding 模型名称';
COMMENT ON COLUMN news.news_embedding.embedding_version IS
    '向量输入拼接和清洗规则版本；规则变化时触发重建';
COMMENT ON COLUMN news.news_embedding.source_hash IS
    '实际向量输入文本的 SHA-256 小写十六进制摘要，用于幂等和陈旧检测';
COMMENT ON COLUMN news.news_embedding.domain_id IS
    '领域过滤投影，对应 news.hp_news.domain_id';
COMMENT ON COLUMN news.news_embedding.category_id IS
    '分类过滤投影，对应 news.hp_news.classify';
COMMENT ON COLUMN news.news_embedding.published_at IS
    '发布时间过滤投影，对应 news.hp_news.publish_time';
COMMENT ON COLUMN news.news_embedding.key_words IS
    '新闻关键词轻量快照';
COMMENT ON COLUMN news.news_embedding.title IS
    '新闻标题轻量快照';
COMMENT ON COLUMN news.news_embedding.ai_title IS
    'AI 标题轻量快照';
COMMENT ON COLUMN news.news_embedding.source IS
    '新闻来源名称轻量快照';
COMMENT ON COLUMN news.news_embedding.domain IS
    '领域名称轻量快照';
COMMENT ON COLUMN news.news_embedding.external_link IS
    '新闻外部链接轻量快照';
COMMENT ON COLUMN news.news_embedding.cover_image_url IS
    '新闻封面 URL 轻量快照';
COMMENT ON COLUMN news.news_embedding.producer IS
    '向量数据生产者标识，默认 insight_hub';
COMMENT ON COLUMN news.news_embedding.created_at IS
    '向量记录创建时间';
COMMENT ON COLUMN news.news_embedding.updated_at IS
    '向量记录最后修改时间；由更新时间触发器维护';

COMMENT ON COLUMN news.sys_domain.domain_id IS
    '领域 ID，来源于 news.hp_domain.domain_id';
COMMENT ON COLUMN news.sys_domain.domain_name IS
    '领域名称，来源于 news.hp_domain.domain_name';
COMMENT ON COLUMN news.sys_domain.remark IS
    '领域备注';
COMMENT ON COLUMN news.sys_domain.user_id IS
    '关联用户 ID';
COMMENT ON COLUMN news.sys_domain.create_time IS
    '领域创建时间';
COMMENT ON COLUMN news.sys_domain.create_by IS
    '领域创建人';
COMMENT ON COLUMN news.sys_domain.other IS
    '领域扩展字段';
COMMENT ON COLUMN news.sys_domain.del_flag IS
    '删除标志：0 有效，2 已删除';
COMMENT ON COLUMN news.sys_domain.update_time IS
    '领域最后修改时间';
COMMENT ON COLUMN news.sys_domain.update_by IS
    '领域最后修改人';
COMMENT ON COLUMN news.sys_domain.filter_prompts IS
    '领域过滤提示词兼容字段';
COMMENT ON COLUMN news.sys_domain.score_prompts IS
    '领域评分提示词兼容字段';
COMMENT ON COLUMN news.sys_domain.return_flag IS
    '领域处理器类型标志；0 表示本地处理器';

COMMIT;
