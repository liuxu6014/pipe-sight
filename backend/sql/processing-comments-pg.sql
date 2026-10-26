-- 处理库规范物理表的完整中文注释；列名沿用 insighthub-schema.pg.sql。
-- 在主迁移完成物理表命名规范化后应用；兼容视图的注释由主迁移复制。
-- 语义核对：processing/db/postgres.py、db/pgvector.py、services/domain_config_service.py、
-- domain/database.py、integrations/insighthub.py 及历史数据库交接说明。

COMMENT ON SCHEMA news IS
    '资讯处理数据域：保存来源、领域、分类、处理收件箱与结果、提示词血缘及语义向量；与平台用户侧目录、审核和收藏数据分开管理。';

COMMENT ON TABLE news.data_sources IS
    '处理库来源和机构主数据，原 hp_data_source；Worker 按不区分大小写的 web_name 识别来源，交接适配器可用平台来源编码建档；不等同平台采集任务配置表。';
COMMENT ON COLUMN news.data_sources.web_source_id IS
    '来源主键，bigint 身份列；现有接入端也可在事务锁保护下显式分配编号；由 news.articles.web_source_id 逻辑引用，该引用没有数据库外键。';
COMMENT ON COLUMN news.data_sources.web_name IS
    '来源识别名称或编码，varchar(255)，非空；Worker 使用站点名称，平台交接优先使用 processor_source_code；lower(web_name) 唯一，不要求一定是网站展示名。';
COMMENT ON COLUMN news.data_sources.web_name_cn IS
    '来源中文展示名称，varchar(255)，可空；平台交接写入采集来源 name，与用于识别来源的 web_name 分开保存。';
COMMENT ON COLUMN news.data_sources.url IS
    '来源地址，varchar(512)，非空；Worker 通常保存文章 URL 的协议和主机部分，平台交接保存 endpoint，未配置时使用 pipeSight://来源编码，不保证都是 HTTP 地址。';
COMMENT ON COLUMN news.data_sources.description IS
    '来源描述，text，可空；用于保留来源说明，当前 Worker 和交接适配器不读取或填充本列。';
COMMENT ON COLUMN news.data_sources.category IS
    '历史来源类别标识，char(1)，可空；当前接入和处理路径不读取，数据库未限定编码；与 data_source_classify 的数据源／机构分类不是同一字段。';
COMMENT ON COLUMN news.data_sources.data_source_classify IS
    '来源主体分类，char(1)，非空且默认 ''1''；CHECK 只允许 ''1'' 数据源、''2'' 机构；Worker 按 NewsBase.data_source_classify 写入，平台交接新建来源时写 ''1''。';
COMMENT ON COLUMN news.data_sources.content_type IS
    '来源内容格式，news.content_type 枚举，非空且默认 Other；枚举值 HTML、RSS、JSON、Other，平台交接按来源类型字符串映射；不表示文章审核或处理状态。';
COMMENT ON COLUMN news.data_sources.authentication_required IS
    '历史认证需求标志，char(1)，非空且默认 ''0''；没有编码 CHECK，当前 Worker 和交接适配器不读取本列，不能据此认定已实现来源认证或凭证管理。';
COMMENT ON COLUMN news.data_sources.last_crawled_timestamp IS
    '来源最近抓取／接入更新时间，timestamp without time zone，可空；现有来源被 Worker 再次匹配或被平台交接更新时写 now()，不代表抓取全站完成或采集任务成功。';
COMMENT ON COLUMN news.data_sources.next_crawl_priority IS
    '历史下次抓取优先级，char(1)，非空且默认 ''0''；没有优先级编码或高低顺序 CHECK，当前 Worker 和交接适配器未用于调度。';
COMMENT ON COLUMN news.data_sources.is_crawled IS
    '历史抓取完成标记，char(1)，非空且默认 ''0''；数据库未限定其他编码，当前 Worker 和交接适配器不维护本列，不能替代真实采集任务状态。';
COMMENT ON COLUMN news.data_sources.logo_path IS
    '历史来源标识图片的文件路径，varchar(512)，可空；当前处理和交接路径不填充，不等同可公开访问的 logo_url。';
COMMENT ON COLUMN news.data_sources.logo_url IS
    '历史来源标识图片的访问地址，varchar(512)，可空；当前处理和交接路径不填充，保存地址不自动保证文件可访问。';
COMMENT ON COLUMN news.data_sources.other IS
    '来源扩展元数据，jsonb，非空且默认空对象；平台交接写入 pipesight_source_id、pipesight_source_code 以定位平台来源，数据库未限定 JSON 形状或键集合。';
COMMENT ON COLUMN news.data_sources.tag IS
    '历史来源标签文本，varchar(1000)，可空；当前处理和交接路径不解析本列，未约定为 JSON 数组或固定分隔格式。';
COMMENT ON COLUMN news.data_sources.create_by IS
    '来源记录创建人标识，varchar(255)，可空；没有用户表外键，当前 Worker 和交接适配器新建来源时不填充本列。';
COMMENT ON COLUMN news.data_sources.create_time IS
    '来源建档时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；平台交接显式写 now()，无时区值受写入端和数据库会话时区约定影响。';
COMMENT ON COLUMN news.data_sources.remark IS
    '来源人工备注，text，可空；当前 Worker 和交接适配器不读取或维护，用于保留来源说明而非处理错误。';

COMMENT ON TABLE news.domains IS
    '资讯领域定义与处理器配置；配置服务直接读取 domains 中未删除记录，内嵌过滤和评分提示词由当前动态领域处理器使用。';
COMMENT ON COLUMN news.domains.domain_id IS
    '领域主键，bigint 身份列；由提示词版本和领域分类规则通过外键引用，资讯及向量领域字段仅逻辑关联；内置领域也可显式指定编号。';
COMMENT ON COLUMN news.domains.domain_name IS
    '领域名称，varchar(255)，非空且全表唯一；用于领域名称与编号映射、处理器注册及分类结果展示，逻辑删除记录仍占用该唯一名称。';
COMMENT ON COLUMN news.domains.remark IS
    '领域说明或备注，varchar(2000)，可空；配置服务将其作为领域配置的一部分读取，不是过滤提示词正文。';
COMMENT ON COLUMN news.domains.user_id IS
    '历史关联用户编号，bigint，可空且没有用户表外键；当前领域配置查询未以本列进行账号权限过滤，不应解释为已生效的领域访问授权。';
COMMENT ON COLUMN news.domains.create_time IS
    '领域记录创建时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；保存无时区时间，不是事件发生时间。';
COMMENT ON COLUMN news.domains.create_by IS
    '领域创建人标识，varchar(255)，可空；没有用户表外键，当前领域配置服务只读取配置，不自动填写创建人。';
COMMENT ON COLUMN news.domains.other IS
    '历史领域扩展文本，varchar(255)，可空；不是 jsonb，当前领域配置服务未解析本列，也未定义固定 JSON 结构。';
COMMENT ON COLUMN news.domains.del_flag IS
    '领域逻辑删除标志，char(1)，非空且默认 ''0''；CHECK 只允许 ''0'' 有效、''2'' 已删除，正常领域配置和编号映射只读取 ''0''。';
COMMENT ON COLUMN news.domains.update_time IS
    '领域最后修改时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；原建表脚本未为本列配置自动更新时间触发器，后续修改需由写入端维护。';
COMMENT ON COLUMN news.domains.update_by IS
    '领域最后修改人标识，varchar(255)，可空且没有用户表外键；由领域配置的写入端维护，读取服务不自动变更。';
COMMENT ON COLUMN news.domains.filter_prompts IS
    '动态领域的大模型过滤提示词，text，可空；处理器将其按含 systemPrompts、userPrompts 键的 JSON 文本解析，解析失败兼容为用户提示词全文；不是 jsonb，也不是版本外键。';
COMMENT ON COLUMN news.domains.score_prompts IS
    '动态领域的评分提示词，text，可空；按 systemPrompts、userPrompts JSON 文本解析，解析失败兼容为用户提示词全文；当前动态处理器仍读取本列，不保证引用 prompt_versions。';
COMMENT ON COLUMN news.domains.return_flag IS
    '领域处理器来源标志，integer，非空且默认 0；0 标识本地／文件处理器，非 0 用于数据库领域处理器识别，混合处理还受处理器工厂配置影响；没有固定非零值枚举 CHECK。';

COMMENT ON TABLE news.topics IS
    '资讯分类定义和分类树，原 hp_topic；当前配置服务读取未删除且启用的分类，并通过领域分类规则取得对应领域的非空分类标准，分类树字段未用于递归查询。';
COMMENT ON COLUMN news.topics.category_id IS
    '分类主键，bigint 身份列；由领域分类规则和提示词版本通过外键引用，资讯 classify 与向量 category_id 仅逻辑关联本编号。';
COMMENT ON COLUMN news.topics.category_name IS
    '分类名称，varchar(255)，非空；用于构造模型候选类别及名称到编号的映射，原结构未设置分类名称唯一约束。';
COMMENT ON COLUMN news.topics.category_description IS
    '分类业务说明，text，可空；配置服务把该说明拼入分类提示词，帮助模型区分候选类别。';
COMMENT ON COLUMN news.topics.parent_category_id IS
    '历史分类树父节点编号，bigint，可空，逻辑指向 news.topics.category_id 但没有自引用外键；当前领域分类查询不按父子关系递归展开。';
COMMENT ON COLUMN news.topics.ancestors IS
    '历史分类树祖先路径文本，varchar(255)，可空；未由数据库限定路径编码或分隔符，当前领域分类配置查询不解析本列。';
COMMENT ON COLUMN news.topics.domain_id IS
    '历史分类归属领域编号，integer，可空，逻辑关联 news.domains.domain_id 但没有外键；当前配置查询按 news.domain_topic_rules.domain_id 关联，不以本列筛选领域。';
COMMENT ON COLUMN news.topics.return_flag IS
    '历史分类返回标志，integer，非空且默认 0；原结构没有编码 CHECK，当前分类提示词构建和分类名称映射不读取本列。';
COMMENT ON COLUMN news.topics.is_active IS
    '分类启停标志，char(1)，非空且默认 ''0''；CHECK 只允许 ''0'' 启用、''1'' 禁用，当前领域分类查询只读取 ''0''，不是布尔值 true 表示启用。';
COMMENT ON COLUMN news.topics.del_flag IS
    '分类逻辑删除标志，char(1)，非空且默认 ''0''；CHECK 只允许 ''0'' 存在、''2'' 已删除，当前领域分类查询只读取 ''0''。';
COMMENT ON COLUMN news.topics.sort_order IS
    '分类显示和提示词候选顺序，integer，可空且没有正数 CHECK；配置服务按本列升序、再按 category_id 升序读取。';
COMMENT ON COLUMN news.topics.other IS
    '历史分类扩展元数据，jsonb，非空且默认空对象；原结构未限定 JSON 形状，当前领域分类配置服务不读取或解释其键。';
COMMENT ON COLUMN news.topics.remark IS
    '分类人工备注，text，可空；与实际拼入模型提示词的 category_description 分开保存，当前领域分类配置查询未读取本列。';
COMMENT ON COLUMN news.topics.create_by IS
    '分类创建人标识，varchar(255)，可空且没有用户表外键；由分类维护端填写，不是分类处理模型名称。';
COMMENT ON COLUMN news.topics.create_time IS
    '分类定义创建时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；保存无时区时间，与资讯发布时间无关。';
COMMENT ON COLUMN news.topics.update_by IS
    '分类最后修改人标识，varchar(255)，可空且没有用户表外键；由分类维护端填写，当前读取服务不自动变更。';
COMMENT ON COLUMN news.topics.update_time IS
    '分类定义最后修改时间，timestamp without time zone，可空；原建表脚本未设置本列默认值或自动更新时间触发器，由写入端维护。';

COMMENT ON TABLE news.articles IS
    '资讯处理收件箱及处理结果事实表，原 hp_news；以 news_id、create_time 组成复合主键，uuid 可重复；completed 表示处理完成，不等于平台人工审核通过或正式发布。';
COMMENT ON COLUMN news.articles.news_id IS
    '资讯事实编号，bigint 身份列，与 create_time 共同组成主键；交接适配器也可显式分配编号，不能仅凭本列认定数据库行唯一。';
COMMENT ON COLUMN news.articles.create_time IS
    '资讯入库／交接建行时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；与 news_id 共同定位记录，关联血缘和向量时须携带本值，重处理既有行不改该键。';
COMMENT ON COLUMN news.articles.uuid IS
    '上游业务资讯标识，varchar(255)，可空且不唯一；平台交接写 article_id，Worker 写 NewsBase.id；相同标识可有多次处理行，读写通常取 create_time 最新记录。';
COMMENT ON COLUMN news.articles.prompt_trace_id IS
    '成功处理后的提示词血缘入口，varchar(26)，可空；当前 Worker 使用 uuid4().hex[:26]，不是 ULID；空值参与待处理筛选，与 news_id、create_time 共同被 news.prompt_usages 复合外键引用。';
COMMENT ON COLUMN news.articles.web_source_id IS
    '处理库来源编号，bigint，可空，逻辑关联 news.data_sources.web_source_id，没有外键；Worker 未取得来源名称时可返回 -1，不能默认所有非空值均有对应主数据。';
COMMENT ON COLUMN news.articles.domain_id IS
    '处理得到的领域编号，bigint，可空，逻辑关联 news.domains.domain_id，没有外键；由 Worker 的领域处理结果写入，与领域名称快照 domain 分开保存。';
COMMENT ON COLUMN news.articles.classify IS
    '处理得到的分类编号，integer，可空，逻辑关联 news.topics.category_id，没有外键；写入 NewsBase.category_id，不能改释为原始来源类别或布尔分类结果。';
COMMENT ON COLUMN news.articles.original_title IS
    '资讯原始标题，varchar(512)，可空；平台交接和 Worker 写入来源标题，区别于翻译标题 translated_title 和模型生成标题 ai_title。';
COMMENT ON COLUMN news.articles.original_text IS
    '资讯原始正文，text，可空；平台交接写 article.body，Worker 优先写 content_md、否则写 content，可能是 Markdown 文本而非固定 HTML 或 JSON。';
COMMENT ON COLUMN news.articles.translated_title IS
    '处理产生的翻译标题，varchar(512)，可空；来自 NewsBase.translated_title，未翻译时可以为空，不覆盖 original_title。';
COMMENT ON COLUMN news.articles.translated_text IS
    '处理产生的翻译正文，text，可空；来自 NewsBase.translated_text，未启用或未完成翻译时可以为空，不代表另存的原始正文版本。';
COMMENT ON COLUMN news.articles.summary IS
    '资讯摘要，text，可空；交接阶段可带入平台已有摘要，处理完成后 Worker 写 NewsBase.abstract，不保证始终是原站原始摘要。';
COMMENT ON COLUMN news.articles.ai_title IS
    '模型提炼的资讯标题，text，可空；Worker 写 NewsBase.ai_title，向量输入优先采用本标题，不能当作原始来源标题。';
COMMENT ON COLUMN news.articles.source IS
    '来源名称文本快照，varchar(255)，可空；Worker 写站点名称，交接写平台来源 name，与数值来源编号 web_source_id 分开保存。';
COMMENT ON COLUMN news.articles.cover_image_url IS
    '来源封面图片地址，varchar(4096)，可空；Worker 写 NewsBase.cover_image_url，仅保存链接，不说明已缓存图片或已取得图片使用授权。';
COMMENT ON COLUMN news.articles.external_link IS
    '资讯原始出处链接，varchar(4096)，可空；交接写 canonical_url、Worker 写 NewsBase.url，与 url 保留兼容性，不保证外链始终可访问。';
COMMENT ON COLUMN news.articles.url IS
    '兼容保留的资讯链接，varchar(4096)，可空；当前交接和 Worker 与 external_link 写同一地址，下游转换在 external_link 缺失时回退读取本列。';
COMMENT ON COLUMN news.articles.author_id IS
    '历史资讯作者编号，bigint，可空；原结构没有作者表外键，当前 Worker 和交接适配器不填充本列，不能解释为平台上传者或登录账号。';
COMMENT ON COLUMN news.articles.platform IS
    '来源平台识别编码，integer，可空；当前处理器将微信公众号识别为 1，交接及 Worker 对普通或未设置平台写 0；其他历史编码没有数据库 CHECK。';
COMMENT ON COLUMN news.articles.score IS
    '领域模型评估分数，real，可空，单位为分；当前评分逻辑钳制到 0–100 并保留一位小数，模型缺省也可写 0；数据库没有分数范围 CHECK，不等同概率或人工审核结论。';
COMMENT ON COLUMN news.articles.warning_grade IS
    '预警等级文本，varchar(255)，可空；当前 Worker 将数字等级转为字符串：''0'' 无、''1'' 低、''2'' 中、''3'' 高；数据库未对历史文本设枚举 CHECK。';
COMMENT ON COLUMN news.articles.warning_cause IS
    '预警原因，varchar(500)，可空；Worker 写模型评估的 risk_reason，与 warning_grade 配套，不是处理异常 processing_error。';
COMMENT ON COLUMN news.articles.domain IS
    '处理领域名称快照，varchar(255)，可空；Worker 把本地域编码转换为数据库领域名称后写入，领域名称查询会排除 unknown。';
COMMENT ON COLUMN news.articles.content_extraction IS
    '事件和实体提取结果的 JSON 文本，text，可空；Worker 将字典序列化，模型字段可含 event_time、location、background、entities、insight；不是 jsonb，数据库不校验 JSON 格式。';
COMMENT ON COLUMN news.articles.event_keywords IS
    '处理提取的事件搜索关键词，text，可空；NewsBase 约定把关键词列表转为逗号拼接字符串，向量 key_words 保存其文本快照，不是 JSON 数组。';
COMMENT ON COLUMN news.articles.other IS
    '处理扩展特征的 JSON 文本，text，可空；Worker 序列化 NewsBase.features，可包含实体、地点及 pipesight_filter 等元数据；不是 jsonb，数据库不限定键或校验 JSON。';
COMMENT ON COLUMN news.articles.other_cn IS
    '历史中文扩展标签文本，text，可空；当前 Worker 入库和交接适配器不填充或解析本列，不能解释为已生成的中文翻译正文。';
COMMENT ON COLUMN news.articles.filter_result IS
    '过滤判定或说明，text，可空；当前处理链路序列化 pipesight_filter 对象，可含 decision、workerExecution 等证据；拒绝和成功均可保留，历史值也可为说明文本，不是单一布尔值。';
COMMENT ON COLUMN news.articles.background IS
    '历史背景说明正文，text，可空；当前 Worker 入库不单独填充本列，结构化提取中的 background 保存在 content_extraction 内，不保证两者同步。';
COMMENT ON COLUMN news.articles.focus_risk IS
    '历史提请关注的风险说明，varchar(500)，可空；当前 Worker 入库不填充，交接回执在已有值时读取，不等同当前风险原因 warning_cause。';
COMMENT ON COLUMN news.articles.suggestion IS
    '历史对策建议正文，text，可空；当前 Worker 入库不填充，交接回执在已有值时读取，不保证每次处理都会生成建议。';
COMMENT ON COLUMN news.articles.judgment_opinion IS
    '历史研判意见正文，text，可空；当前 Worker 和交接适配器不维护本列，不能据此认定已完成人工研判或审核。';
COMMENT ON COLUMN news.articles.publish_time IS
    '业务发布时间，timestamp without time zone，非空且默认 CURRENT_TIMESTAMP；Worker 默认从 ctime 按 Asia/Shanghai 生成并钳制未来时间，交接缺失时回填发现时间，不保证均为已核实的原站发布日期。';
COMMENT ON COLUMN news.articles."timestamp" IS
    '历史时间戳字段，timestamp without time zone，可空；不是 Unix 秒或毫秒整数，当前 Worker 和交接适配器不维护本列，不替代 create_time 或 publish_time。';
COMMENT ON COLUMN news.articles.del_flag IS
    '资讯逻辑删除标志，char(1)，非空且默认 ''0''；CHECK 只允许 ''0'' 存在、''2'' 已删除；平台交接重置未完成记录时恢复为 ''0''，回执把 ''2'' 视为拒绝结果。';
COMMENT ON COLUMN news.articles.is_featured IS
    '历史是否推荐标志，smallint，非空且默认 0；原结构没有编码 CHECK，当前 Worker 和交接适配器不读写，不等同模型评分达到推荐阈值。';
COMMENT ON COLUMN news.articles.is_top IS
    '历史是否置顶标志，char(1)，可空；原结构未限定编码，当前 Worker 和交接适配器不维护，不能推断已有置顶排序逻辑。';
COMMENT ON COLUMN news.articles.type IS
    '交接资讯类型编码，char(10)，可空；当前平台交接写 ''W'' 微信公众号、''N'' 普通资讯，Worker 原位完成时保留本列；没有固定值 CHECK，不能据此扩展为论文类型。';
COMMENT ON COLUMN news.articles.favorites IS
    '历史收藏次数，integer，非空且默认 0，单位为次；没有非负 CHECK，当前 Worker 和交接适配器不维护，不能替代平台用户收藏记录。';
COMMENT ON COLUMN news.articles.likes IS
    '历史点赞次数，integer，非空且默认 0，单位为次；没有非负 CHECK，当前处理和交接路径不更新，不保证与来源站点或平台用户互动一致。';
COMMENT ON COLUMN news.articles.shares IS
    '历史分享次数，integer，非空且默认 0，单位为次；没有非负 CHECK，当前处理和交接路径不更新，不代表真实外发次数。';
COMMENT ON COLUMN news.articles.bad IS
    '历史不感兴趣次数，integer，非空且默认 0，单位为次；没有非负 CHECK，当前处理和交接路径不维护，不代表处理失败或被过滤的次数。';
COMMENT ON COLUMN news.articles.tags IS
    '上游资讯标签，text，可空；当前平台交接把 article.tags 序列化为 JSON 数组文本，Worker 原位完成不重写本列；数据库不校验 JSON，不等同 event_keywords 的逗号文本。';
COMMENT ON COLUMN news.articles.news_all_info IS
    '上游附加信息，text，可空；当前平台交接仅序列化 article.metadata_json，并非完整原始新闻快照；Worker 兼容读取其中 processing.filter 过滤证据，数据库不校验 JSON。';
COMMENT ON COLUMN news.articles.processing_status IS
    '处理收件箱状态，varchar(20)，非空且默认 pending；CHECK 枚举为 pending 待处理、processing 处理中、completed 已完成、rejected 过滤拒绝、failed 可重试失败、dead_letter 次数耗尽需人工重试；不是平台审核状态。';
COMMENT ON COLUMN news.articles.processing_attempts IS
    '累计处理领取次数，integer，非空且默认 0，单位为次；每次领取任务加 1，亦作为过期 Worker 结果的租约校验编号；最大次数取运行配置，数据库未设置非负或上限 CHECK。';
COMMENT ON COLUMN news.articles.processing_started_at IS
    '当前处理租约开始时刻，timestamp with time zone，可空；领取时写 now()，按配置的秒数判断超时，处理结束或租约回收时清空，不是永久保存的首次处理时间。';
COMMENT ON COLUMN news.articles.processing_completed_at IS
    '处理完成或过滤拒绝时刻，timestamp with time zone，可空；成功及 rejected 路径写 now()，交接重置和失败路径清空，不能单独用本列判断任务成功。';
COMMENT ON COLUMN news.articles.processing_error IS
    '最近处理错误、过滤拒绝原因或租约超时说明，text，可空；当前失败写入逻辑最多保存 2000 个字符，数据库 text 本身无此长度限制；领取、重置或成功后清空。';

COMMENT ON TABLE news.prompt_versions IS
    '提示词版本及单父派生关系，原 sys_prompt_version；保存内容、发布状态和内容摘要，已发布或已使用版本受不可变触发器保护；当前动态领域处理仍读取领域与规则中的内嵌文本。';
COMMENT ON COLUMN news.prompt_versions.prompt_version_id IS
    '提示词版本主键，bigint 身份列；可被派生版本、领域分类规则及实际提示词使用记录引用，删除受这些外键的 RESTRICT 规则保护。';
COMMENT ON COLUMN news.prompt_versions.parent_prompt_version_id IS
    '直接派生来源版本编号，bigint，可空；外键指向 news.prompt_versions.prompt_version_id，ON DELETE RESTRICT；空值表示根版本，可跨 prompt_key 派生，CHECK 仅禁止直接自指，不负责阻止多节点环。';
COMMENT ON COLUMN news.prompt_versions.prompt_key IS
    '提示词稳定业务键，varchar(150)，非空，例如 politics.filter；与 version_no、content_hash 分别组成唯一约束，同一键最多一个 published 版本，由部分唯一索引保证。';
COMMENT ON COLUMN news.prompt_versions.prompt_name IS
    '提示词版本展示名称，varchar(255)，非空；区别于稳定业务键 prompt_key，原结构未设置名称唯一或非空白文本 CHECK。';
COMMENT ON COLUMN news.prompt_versions.prompt_type IS
    '提示词处理用途，varchar(50)，非空；历史约定示例 FILTER、CLASSIFY、CLASSIFY_CRITERION、SCORE、WARNING、ENTITY_EXTRACT；不是数据库枚举，原结构未约束用途值域。';
COMMENT ON COLUMN news.prompt_versions.domain_id IS
    '提示词适用领域编号，bigint，可空；外键指向 news.domains.domain_id，ON DELETE RESTRICT；空值表示全局提示词，不自动授予领域访问权限。';
COMMENT ON COLUMN news.prompt_versions.category_id IS
    '提示词适用分类编号，bigint，可空；外键指向 news.topics.category_id，ON DELETE RESTRICT；空值表示非分类专属提示词，不等同领域分类绑定本身。';
COMMENT ON COLUMN news.prompt_versions.version_no IS
    '同一 prompt_key 内的版本编号，integer，非空且 CHECK 大于 0；与 prompt_key 联合唯一，版本分配由写入端维护，数据库不保证自动或连续递增。';
COMMENT ON COLUMN news.prompt_versions.system_prompt IS
    '系统提示词模板正文，text，非空且默认空字符串；与 user_prompt 分开保存，已发布或已使用版本的正文受不可变触发器保护。';
COMMENT ON COLUMN news.prompt_versions.user_prompt IS
    '用户提示词模板正文，text，非空但未设置非空白 CHECK；保存模板而非某次调用渲染后的输入，已发布或已使用版本的正文受不可变触发器保护。';
COMMENT ON COLUMN news.prompt_versions.template_variables IS
    '模板变量名称及说明的 JSONB 元数据，可空；原结构未限定数组或对象形状，当前 Worker 未从本版本表读取变量渲染，不能视为已实现的动态变量验证规则。';
COMMENT ON COLUMN news.prompt_versions.content_hash IS
    '提示词内容的 SHA-256 摘要，char(64)，非空且 CHECK 为 64 位小写十六进制；与 prompt_key 联合唯一，具体内容规范化和摘要计算由写入端约定。';
COMMENT ON COLUMN news.prompt_versions.status IS
    '版本状态，varchar(20)，非空且默认 draft；CHECK 只允许 draft 草稿、published 已发布、retired 已退役；同一业务键最多一个 published，离开草稿或被使用后不能修改受保护内容或回退为草稿。';
COMMENT ON COLUMN news.prompt_versions.derivation_note IS
    '版本派生的改动说明及原因，varchar(1000)，可空；属于不可变内容，已发布或已使用版本不能覆盖该说明。';
COMMENT ON COLUMN news.prompt_versions.created_by IS
    '提示词版本创建人标识，varchar(255)，可空；原结构没有用户表外键，不是调用模型名称或提示词使用记录的执行人。';
COMMENT ON COLUMN news.prompt_versions.created_at IS
    '提示词版本创建时刻，timestamp with time zone，非空且默认 now()；记录数据库时间点，不等同首次调用或发布时间。';
COMMENT ON COLUMN news.prompt_versions.updated_at IS
    '提示词版本最后修改时刻，timestamp with time zone，非空且默认 now()；原结构由 set_updated_at 更新时间触发器在更新时维护。';
COMMENT ON COLUMN news.prompt_versions.published_at IS
    '版本正式发布时间点，timestamp with time zone，可空；CHECK 要求 published 状态时非空，已发布或已使用版本的此时间受不可变触发器保护。';

COMMENT ON TABLE news.domain_topic_rules IS
    '领域与分类的分类标准绑定，原 act_domain_topic_actions；复合主键为 domain_id、category_id；文本或版本引用至少一个非空，当前配置服务仍只消费非空内嵌分类标准。';
COMMENT ON COLUMN news.domain_topic_rules.domain_id IS
    '规则所属领域编号，bigint，非空且为复合主键一部分；外键指向 news.domains.domain_id，ON DELETE CASCADE；当前配置服务按此字段选择领域对应分类标准。';
COMMENT ON COLUMN news.domain_topic_rules.category_id IS
    '规则绑定的分类编号，bigint，非空且为复合主键一部分；外键指向 news.topics.category_id，ON DELETE CASCADE；与领域编号共同保证每对领域分类最多一条规则。';
COMMENT ON COLUMN news.domain_topic_rules.category_prompts IS
    '内嵌分类标准正文，text，可空；当前配置服务将非空正文直接拼入分类提示词，尚不回退读取版本内容；CHECK 只要求本列或 prompt_version_id 非空，不会拒绝空字符串。';
COMMENT ON COLUMN news.domain_topic_rules.prompt_version_id IS
    '分类标准提示词版本编号，bigint，可空；外键指向 news.prompt_versions.prompt_version_id，ON DELETE RESTRICT；与内嵌文本至少一个非空，但当前配置服务尚未解引用本列生成分类提示词。';
COMMENT ON COLUMN news.domain_topic_rules.created_at IS
    '领域分类规则创建时刻，timestamp with time zone，非空且默认 now()；与提示词版本的创建时间分别记录。';
COMMENT ON COLUMN news.domain_topic_rules.updated_at IS
    '领域分类规则最后修改时刻，timestamp with time zone，非空且默认 now()；原结构由 set_updated_at 更新时间触发器维护。';

COMMENT ON TABLE news.prompt_usages IS
    '资讯处理使用的提示词版本、阶段和顺序血缘，原 news_prompt_usage；复合外键定位原资讯行，删除资讯级联删除血缘；当前 Worker 生成血缘入口但尚未写入本表，不能假定已有完整调用记录。';
COMMENT ON COLUMN news.prompt_usages.usage_id IS
    '提示词版本使用记录主键，bigint 身份列；用于定位单条使用关系，不是资讯主键或模型调用次数。';
COMMENT ON COLUMN news.prompt_usages.prompt_trace_id IS
    '资讯处理血缘批次标识，varchar(26)，非空；与 news_id、news_create_time 共同外键关联 news.articles(prompt_trace_id, news_id, create_time)，ON DELETE CASCADE；与 sequence_no 联合唯一。';
COMMENT ON COLUMN news.prompt_usages.news_id IS
    '使用提示词的资讯事实编号，bigint，非空；须与 prompt_trace_id、news_create_time 一起匹配 news.articles 的复合外键，不能单独定位可能重复编号的资讯行。';
COMMENT ON COLUMN news.prompt_usages.news_create_time IS
    '被引用资讯行的 create_time，timestamp without time zone，非空；必须保留 news.articles.create_time 原值，与资讯编号和血缘批次共同建立复合外键，不是本使用记录的创建时刻。';
COMMENT ON COLUMN news.prompt_usages.prompt_version_id IS
    '该处理阶段使用的提示词版本编号，bigint，非空；外键指向 news.prompt_versions.prompt_version_id，ON DELETE RESTRICT；一旦被使用，原结构触发器保护版本内容不被覆盖。';
COMMENT ON COLUMN news.prompt_usages.stage IS
    '提示词使用阶段，varchar(50)，非空；历史约定示例 FILTER、CLASSIFY、SCORE、WARNING、ENTITY_EXTRACT，同阶段可有多条标准；原结构未设置阶段枚举或非空白 CHECK。';
COMMENT ON COLUMN news.prompt_usages.sequence_no IS
    '血缘批次内提示词使用顺序号，integer，非空且 CHECK 大于 0，单位为序号；与 prompt_trace_id 联合唯一，原结构不保证顺序连续或自动分配。';
COMMENT ON COLUMN news.prompt_usages.model_name IS
    '该阶段实际调用模型的名称，varchar(255)，可空；属于血缘记录的模型快照，不是模型配置主键、向量模型名称或固定枚举。';
COMMENT ON COLUMN news.prompt_usages.created_at IS
    '提示词使用关系记录创建时刻，timestamp with time zone，非空且默认 now()；不提供单次调用的开始、结束、耗时或 token 用量。';

COMMENT ON TABLE news.embeddings IS
    '资讯 1024 维语义向量及检索投影快照，原 news_embedding；以 news_id、news_create_time 复合主键和外键绑定资讯行，删除资讯级联删除向量；相同资讯行采用幂等覆盖写入。';
COMMENT ON COLUMN news.embeddings.news_id IS
    '向量所属资讯事实编号，bigint，非空且为复合主键一部分；与 news_create_time 外键关联 news.articles(news_id, create_time)，ON DELETE CASCADE。';
COMMENT ON COLUMN news.embeddings.news_create_time IS
    '向量所属资讯行的 create_time，timestamp without time zone，非空且为复合主键一部分；与 news_id 建立到 news.articles 的复合外键，当前向量客户端按该编号最新 create_time 行写入。';
COMMENT ON COLUMN news.embeddings.uuid IS
    '上游业务资讯标识快照，varchar(255)，非空但未限制非空白或唯一；客户端写入向量数据的 uuid，不能用本列替代复合主键。';
COMMENT ON COLUMN news.embeddings.embedding IS
    '资讯标题与摘要的语义向量，pgvector vector(1024)，非空，维数为 1024；原结构建立 vector_cosine_ops HNSW 索引，采用余弦距离，不是评分概率或原文内容。';
COMMENT ON COLUMN news.embeddings.embedding_model IS
    '生成语义向量的模型名称快照，text，非空；由运行配置 embedding_model 写入，模型可配置，不应将某一模型名称固定为表结构枚举。';
COMMENT ON COLUMN news.embeddings.embedding_version IS
    '向量输入拼接／清洗规则版本，integer，非空且默认 1，CHECK 大于 0；当前客户端新建时写 1、冲突更新不改本列，没有实现规则变更后自动重建的保证。';
COMMENT ON COLUMN news.embeddings.source_hash IS
    '客户端向量来源文本摘要，char(64)，非空且 CHECK 为 64 位小写十六进制 SHA-256；当前对 UTF-8 文本“标题: 标题值 摘要: 摘要值”计算，标题优先取 AI 标题、否则原题，再去首尾空白；独立重建输入，不保证等同模型端预处理文本，不是原文文件哈希。';
COMMENT ON COLUMN news.embeddings.domain_id IS
    '资讯领域编号的检索投影，bigint，可空，对应 news.articles.domain_id 并逻辑关联 news.domains.domain_id；本列没有领域外键，不由数据库自动随主表更新。';
COMMENT ON COLUMN news.embeddings.category_id IS
    '资讯分类编号的检索投影，bigint，可空，写入处理结果 classify，对应 news.articles.classify 和 news.topics.category_id；本列没有分类外键。';
COMMENT ON COLUMN news.embeddings.published_at IS
    '资讯发布时间的检索投影，timestamp without time zone，可空；当前客户端从被引用资讯行的 publish_time 读取，不是向量生成时间，也不是可自动补出的原站发布日期。';
COMMENT ON COLUMN news.embeddings.key_words IS
    '事件关键词文本快照，text，非空且默认空字符串；当前处理链路传入 event_keywords 的逗号拼接文本，不是 JSON 数组或另行计算的向量关键词。';
COMMENT ON COLUMN news.embeddings.title IS
    '资讯原始标题的轻量检索快照，varchar(512)，非空但没有非空白 CHECK；来自处理结果 title，与向量输入优先使用的 ai_title 分开保存。';
COMMENT ON COLUMN news.embeddings.ai_title IS
    '模型提炼标题的轻量检索快照，text，非空且默认空字符串；有值时优先参与向量输入标题选择，不代表原始标题被替换。';
COMMENT ON COLUMN news.embeddings.source IS
    '资讯来源名称的轻量检索快照，varchar(255)，可空；由处理结果复制，不是来源编号，也不由数据库自动与来源主数据同步。';
COMMENT ON COLUMN news.embeddings.domain IS
    '资讯领域名称的轻量检索快照，varchar(255)，可空；用于展示，与领域编号 domain_id 分开保存，不是领域表外键。';
COMMENT ON COLUMN news.embeddings.external_link IS
    '资讯原始出处链接快照，varchar(4096)，可空；由处理结果复制，仅保存 URL，不保证原站可用或已取得全文访问权限。';
COMMENT ON COLUMN news.embeddings.cover_image_url IS
    '资讯封面图片地址快照，varchar(4096)，可空；由处理结果复制，不包含图片二进制内容或图片缓存状态。';
COMMENT ON COLUMN news.embeddings.producer IS
    '向量记录生产者标识，varchar(100)，非空且默认 insight_hub；当前客户端可读取传入 producer，原结构没有非空白或固定生产者枚举 CHECK。';
COMMENT ON COLUMN news.embeddings.created_at IS
    '向量记录首次创建时刻，timestamp with time zone，非空且默认 now()；冲突覆盖写入保留本值，与资讯 create_time 分开记录。';
COMMENT ON COLUMN news.embeddings.updated_at IS
    '向量记录最后更新时刻，timestamp with time zone，非空且默认 now()；原结构由 set_updated_at 更新时间触发器维护，幂等覆盖写入也会刷新。';
