-- compact-v6中文注释；12业务PK及引用FK为BIGINT，共享business_id_seq；若依表字段不变。
-- 27个业务created_at/updated_at为北京时间timestamp(0)无时区；其他运行时间字段保持原类型。
-- 普通不透明令牌保留；系统幂等键内嵌ID、显式JSON引用及语义指纹按实体映射核验。
-- 27张基线表320字段，2张保留功能表23字段；共29张物理表343字段。
-- 仅COMMENT及存在性保护块；调用方管理事务，不修改字段、约束或业务数据。

COMMENT ON TABLE public."news_articles" IS '网站与公众号新闻原文及中文译文；每篇最多关联一个类别，无人工审核流程';
COMMENT ON COLUMN public."news_articles"."id" IS '新闻数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
COMMENT ON COLUMN public."news_articles"."source_id" IS '必填来源ID，关联data_sources.id；仅允许website或wechat来源，删除受限；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."news_articles"."title" IS '原文新闻标题；必填且禁止空白文本';
COMMENT ON COLUMN public."news_articles"."url" IS '规范化原文地址；用于新闻去重，不代表平台入库页面地址';
COMMENT ON COLUMN public."news_articles"."author" IS '原作者名单文本；未知时为空，不以来源网站名称冒充作者';
COMMENT ON COLUMN public."news_articles"."published_at" IS '原文发布时间，保留到秒；由旧published_time迁入，非平台审核或入库时间；带时区';
COMMENT ON COLUMN public."news_articles"."content" IS '抓取的原文正文；未取得正文时允许为空，不以导读摘要冒充全文';
COMMENT ON COLUMN public."news_articles"."content_zh" IS '中文正文或译文；为空时展示回退content，不重复复制中文原文';
COMMENT ON COLUMN public."news_articles"."category_id" IS '唯一类别ID，关联categories.id；未分类或未命中为空，不以空值推断审核失败；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."news_articles"."is_pushed" IS '推送成功标志；true仅表示收到真实渠道成功回执，默认false';
COMMENT ON COLUMN public."news_articles"."created_at" IS '新闻平台入库时间，不代替原文发表时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."news_articles"."updated_at" IS '新闻正文或关联资料最近更新时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."papers" IS '论文文献信息及中英文摘要；保留真实发表日期精度，不保存论文全文';
COMMENT ON COLUMN public."papers"."id" IS '论文数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
COMMENT ON COLUMN public."papers"."source_id" IS '论文来源ID，关联data_sources.id；可空，来源删除后置空；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."papers"."title" IS '论文原始标题；必填且禁止空白文本';
COMMENT ON COLUMN public."papers"."title_zh" IS '论文中文标题；与原题相同时无需重复展示';
COMMENT ON COLUMN public."papers"."url" IS '论文来源页面地址；与DOI至少一个非空，不表示拥有论文全文';
COMMENT ON COLUMN public."papers"."doi" IS '规范化DOI，不带https://doi.org/前缀；非空时唯一';
COMMENT ON COLUMN public."papers"."authors" IS '原始作者名单文本；不自动用机构或来源名称替代';
COMMENT ON COLUMN public."papers"."journal" IS '论文期刊或会议名称；保留原始文献信息';
COMMENT ON COLUMN public."papers"."published_date" IS '真实发表日期及精度：YYYY、YYYY-MM或YYYY-MM-DD；未知月日不补造，非入库或审核日期';
COMMENT ON COLUMN public."papers"."abstract" IS '原文摘要或已明确标识的历史导读摘要；不存论文全文';
COMMENT ON COLUMN public."papers"."abstract_zh" IS '中文摘要；与原文摘要分别保存，不作为论文全文存储';
COMMENT ON COLUMN public."papers"."category_id" IS '唯一类别ID，关联categories.id；未分类或未命中为空，类别删除受限；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."papers"."is_pushed" IS '论文推送成功标志；真实渠道成功后为true，默认false，不表示审核结果';
COMMENT ON COLUMN public."papers"."created_at" IS '论文平台入库时间，不能代替真实发表日期；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."papers"."updated_at" IS '论文文献信息或摘要最近更新时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."categories" IS '管理员维护的单类别及过滤分类提示词；停用不清除历史文章归类';
COMMENT ON COLUMN public."categories"."id" IS '类别数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
COMMENT ON COLUMN public."categories"."name" IS '管理员设置的唯一类别名称；必填且禁止空白文本';
COMMENT ON COLUMN public."categories"."prompt" IS '管理员编写的过滤分类标准；保留原提示语及变量，修改仅影响后续处理';
COMMENT ON COLUMN public."categories"."model_id" IS '分类文本模型ID，关联ai_models.id；暂未配置时为空，启用分类前必须配置';
COMMENT ON COLUMN public."categories"."applies_to" IS '适用内容类型：news新闻、paper论文、all两者；默认all';
COMMENT ON COLUMN public."categories"."is_enabled" IS '是否参加后续分类；true启用、false停用，停用不清除历史关联';
COMMENT ON COLUMN public."categories"."sort_order" IS '前台类别排序值；整数，默认0';
COMMENT ON COLUMN public."categories"."created_at" IS '类别创建时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."categories"."updated_at" IS '类别名称、提示词或模型配置最近修改时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."data_sources" IS '新闻网站、公众号与论文来源及采集配置；来源开关与单次采集状态分别维护';
COMMENT ON COLUMN public."data_sources"."id" IS '采集来源数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
COMMENT ON COLUMN public."data_sources"."name" IS '真实网站、公众号或论文库名称；必填，不虚构采集来源';
COMMENT ON COLUMN public."data_sources"."type" IS '来源类型：website新闻网站、wechat公众号、paper论文库';
COMMENT ON COLUMN public."data_sources"."url" IS '真实来源入口或历史文章来源地址；可空，不自动把推测主页当采集入口';
COMMENT ON COLUMN public."data_sources"."adapter" IS '受控采集器注册标识；不是任意命令或可执行代码，启用前核对实现';
COMMENT ON COLUMN public."data_sources"."cron" IS '来源定时采集表达式；为空仅允许手动触发，不在config重复保存周期';
COMMENT ON COLUMN public."data_sources"."timezone" IS '采集计划IANA时区名；默认Asia/Shanghai，决定cron的当地时间语义';
COMMENT ON COLUMN public."data_sources"."next_run_at" IS '下次采集调度时间点，带时区；仅is_enabled=true且cron非空时非空';
COMMENT ON COLUMN public."data_sources"."config" IS '采集参数JSON对象；保存分页、限速、超时、增量及重试策略，凭证仅存引用';
COMMENT ON COLUMN public."data_sources"."model_id" IS '自动翻译模型ID，关联ai_models.id；为空不自动翻译，不静默换用其他模型';
COMMENT ON COLUMN public."data_sources"."is_enabled" IS '来源入队及启动开关；true启用、false停用，停用不等于当前运行已停止';
COMMENT ON COLUMN public."data_sources"."created_at" IS '来源建档时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."data_sources"."updated_at" IS '来源名称、采集配置或开关最近修改时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."knowledge_files" IS '用户私有上传资料；原文件存储键、系统提取文本与用户编辑文本分别保存';
COMMENT ON COLUMN public."knowledge_files"."id" IS '上传资料数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
COMMENT ON COLUMN public."knowledge_files"."user_id" IS '资料所有者ID，关联sys_user.id；默认私有，访问由服务端校验所有权';
COMMENT ON COLUMN public."knowledge_files"."name" IS '用户可修改的资料展示名称；不改变原始上传文件名';
COMMENT ON COLUMN public."knowledge_files"."filename" IS '上传时原始文件名；与可编辑资料名称name分开保存';
COMMENT ON COLUMN public."knowledge_files"."storage_key" IS '原文件稳定存储键；用于受控读取，不能只保存临时过期URL';
COMMENT ON COLUMN public."knowledge_files"."mime_type" IS '服务端检测出的文件MIME类型；不只信上传后缀';
COMMENT ON COLUMN public."knowledge_files"."size" IS '原始文件大小，单位字节；整数且非负';
COMMENT ON COLUMN public."knowledge_files"."hash" IS '原始文件SHA-256摘要；用于完整性核对及同用户重复上传提示';
COMMENT ON COLUMN public."knowledge_files"."extracted_text" IS '系统提取的正文；解析重试仅更新提取结果，不覆盖用户编辑文本';
COMMENT ON COLUMN public."knowledge_files"."edited_text" IS '用户编辑正文；NULL表示未编辑，空字符串也是有效编辑，不能按真值回退';
COMMENT ON COLUMN public."knowledge_files"."version" IS '资料编辑并发控制版本；从1开始，每次编辑递增';
COMMENT ON COLUMN public."knowledge_files"."status" IS '解析状态：queued排队、parsing解析中、ready就绪、failed失败；非人工审核状态';
COMMENT ON COLUMN public."knowledge_files"."error" IS '解析失败的脱敏简短原因；不保存密钥或完整堆栈';
COMMENT ON COLUMN public."knowledge_files"."created_at" IS '上传资料保存时间，不表示解析已成功；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."knowledge_files"."updated_at" IS '资料编辑或解析状态最近更新时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."templates" IS '文章、科研报告与简报生成模板；正文及图片模型由管理员配置，可暂未配置';
COMMENT ON COLUMN public."templates"."id" IS '生成模板数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
COMMENT ON COLUMN public."templates"."name" IS '用户选择模板时显示的名称；必填且禁止空白文本';
COMMENT ON COLUMN public."templates"."purpose" IS '模板用途：article生成文章、research科研报告、digest周期简报';
COMMENT ON COLUMN public."templates"."description" IS '模板用途及适用范围说明；可空，不冒充正文生成结果';
COMMENT ON COLUMN public."templates"."prompt" IS '正文生成提示词；无独立旧提示词时明确保留原模板名称、说明及章节结构';
COMMENT ON COLUMN public."templates"."model_id" IS '正文模型ID，关联ai_models.id；迁移后允许NULL，提交生成时必须配置真实文本模型';
COMMENT ON COLUMN public."templates"."image_model_id" IS '配图模型ID，关联ai_models.id；可空，请求配图时须具备image_generate能力';
COMMENT ON COLUMN public."templates"."sections" IS '章节顺序及必填要求的JSON数组；保留章节标题和结构约束；明确的平台业务引用按实体映射，章节正文与普通外部参数不改写';
COMMENT ON COLUMN public."templates"."image_config" IS '配图数量、位置、风格和提示词模板的JSON对象；不保存调用凭证；明确的平台业务引用按实体映射，供应商模型标识、提示词及普通外部参数原样保留';
COMMENT ON COLUMN public."templates"."is_enabled" IS '模板选择开关；true可用于新任务、false停用，历史任务快照不受修改影响';
COMMENT ON COLUMN public."templates"."created_at" IS '模板创建时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."templates"."updated_at" IS '模板内容或模型配置最近修改时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."ai_models" IS '后台统一管理的文本和图片模型配置；能力明确登记，凭证只保存安全引用';
COMMENT ON COLUMN public."ai_models"."id" IS '后台模型自增ID；文本与图片模型统一登记在本表';
COMMENT ON COLUMN public."ai_models"."name" IS '管理员界面显示的模型名称；不是供应商请求中的模型代码';
COMMENT ON COLUMN public."ai_models"."provider" IS '模型服务提供方名称；与实际调用适配器对应';
COMMENT ON COLUMN public."ai_models"."code" IS '提供方实际模型标识；随请求发送给供应商，不使用展示名替代';
COMMENT ON COLUMN public."ai_models"."base_url" IS '经后台校验的模型服务API基础地址；请求时遵守服务端访问限制';
COMMENT ON COLUMN public."ai_models"."credential_ref" IS '密钥管理或本地加密凭证的安全引用；不得向普通接口或日志明文返回';
COMMENT ON COLUMN public."ai_models"."capabilities" IS '模型能力JSON数组，如text_generate、image_generate、image_input；图片输入不等于图片生成';
COMMENT ON COLUMN public."ai_models"."parameters" IS '模型默认参数JSON对象；保存采样、输出限制和超时等，不保存明文凭证';
COMMENT ON COLUMN public."ai_models"."is_enabled" IS '模型调用开关；true可调用、false停用，历史引用保留且禁止任意替换';
COMMENT ON COLUMN public."ai_models"."created_at" IS '模型配置创建时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."ai_models"."updated_at" IS '模型能力、参数或开关最近修改时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."reports" IS '用户可编辑的生成文章、科研报告和周期简报正文；执行状态由生成任务维护';
COMMENT ON COLUMN public."reports"."id" IS '生成成果数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
COMMENT ON COLUMN public."reports"."user_id" IS '成果所有者ID，关联sys_user.id；任务和资源权限通过本成果判断';
COMMENT ON COLUMN public."reports"."title" IS '用户可编辑的成果标题；必填且禁止空白文本';
COMMENT ON COLUMN public."reports"."type" IS '成果类型：article文章、research科研报告、daily日报、weekly周报、monthly月报';
COMMENT ON COLUMN public."reports"."template_id" IS '当前成果关联模板ID，关联templates.id；可空，历史使用内容由任务快照保留；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."reports"."content" IS '用户当前可编辑的Markdown正文；默认空文本，生成结果不能直接覆盖后续人工修改';
COMMENT ON COLUMN public."reports"."version" IS '成果乐观锁版本；至少1，每次修改递增，不代替历史正文版本表';
COMMENT ON COLUMN public."reports"."created_at" IS '成果草稿创建时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."reports"."updated_at" IS '成果标题或正文最近保存时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."generation_tasks" IS '单次生成任务及冻结选材快照；支持幂等提交、租约执行、取消和失败重试';
COMMENT ON COLUMN public."generation_tasks"."id" IS '单次生成任务数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
COMMENT ON COLUMN public."generation_tasks"."report_id" IS '成果ID，关联reports.id；所有者从成果取得，不重复保存user_id；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."generation_tasks"."schedule_id" IS '周期计划ID，关联digest_schedules.id；手动任务为空，计划删除受限；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."generation_tasks"."request_id" IS '全局唯一幂等键，varchar(128)；普通客户端键及manual:随机UUID原样保留；系统schedule:计划ID:触发UTC时刻仅按实际schedule_id映射内嵌计划ID，UTC后缀不变，映射后仍须全局唯一';
COMMENT ON COLUMN public."generation_tasks"."status" IS '执行状态：queued排队、running执行中、completed完成、failed失败、cancelled取消';
COMMENT ON COLUMN public."generation_tasks"."progress" IS '任务进度百分比；整数0至100，默认0';
COMMENT ON COLUMN public."generation_tasks"."config_snapshot" IS '任务配置JSON对象快照；保存模板、提示词、模型标识、参数及成果起始版本，不含密钥或重复材料正文；显式平台业务引用按实体映射为十进制字符串，普通参数和提示词不改写；request_fingerprint须由映射后的request及materials按应用规范重新计算核验';
COMMENT ON COLUMN public."generation_tasks"."materials" IS '最多50项的有序选材JSON数组快照；每项含type、id、title、content、source，论文仅用摘要及文献信息；依据type或明确实体上下文映射id为十进制字符串，保留顺序、标题、正文及来源文本；缺失或歧义引用在写入前拒绝';
COMMENT ON COLUMN public."generation_tasks"."result_content" IS '本次任务生成的原始正文；与用户当前编辑的reports.content分别保存';
COMMENT ON COLUMN public."generation_tasks"."error" IS '生成失败的脱敏简短原因；不保存调用凭证或完整供应商响应';
COMMENT ON COLUMN public."generation_tasks"."attempts" IS '自动重试次数；整数且非负，默认0，重试沿用冻结选材快照';
COMMENT ON COLUMN public."generation_tasks"."lease_expires_at" IS '当前执行租约截止时间；带时区，过期后才允许隔离旧执行器并恢复';
COMMENT ON COLUMN public."generation_tasks"."execution_token" IS '本次执行尝试的唯一令牌；完成回写须匹配，阻止旧执行器覆盖新尝试；varchar(64)执行令牌，非数值主键，保留原业务字符串';
COMMENT ON COLUMN public."generation_tasks"."started_at" IS '本次任务实际开始执行时间；带时区，尚未开始时为空';
COMMENT ON COLUMN public."generation_tasks"."finished_at" IS '任务完成、失败或取消的时间；带时区，不早于非空started_at';
COMMENT ON COLUMN public."generation_tasks"."created_at" IS '任务提交保存时间，与首次创建成果同事务保存；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."generation_tasks"."updated_at" IS '任务状态、进度或执行信息最近更新时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."report_assets" IS '成果的生成图片及导出文件；每项资源独立保存存储键、执行状态和失败原因';
COMMENT ON COLUMN public."report_assets"."id" IS '图片或导出资源数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
COMMENT ON COLUMN public."report_assets"."report_id" IS '所属成果ID，关联reports.id；独立导出无任务时仍必须关联成果；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."report_assets"."task_id" IS '可空生成任务ID；与report_id复合引用generation_tasks.(id,report_id)，防止跨成果关联；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."report_assets"."type" IS '资源类型：image生成图片、export导出文件';
COMMENT ON COLUMN public."report_assets"."storage_key" IS '资源文件稳定存储键；queued时可空，completed时必须非空，不只保存临时URL';
COMMENT ON COLUMN public."report_assets"."mime_type" IS '提交时选定的输出MIME类型；必填，完成后核对实际文件类型';
COMMENT ON COLUMN public."report_assets"."prompt" IS '图片实际生成提示词；image需要非空，export为空';
COMMENT ON COLUMN public."report_assets"."model_id" IS '实际图片模型ID，关联ai_models.id；image必须配置，export为空';
COMMENT ON COLUMN public."report_assets"."config_snapshot" IS '资源配置JSON对象快照；图片保存模型标识及配图参数，导出保存正文版本及快照，不含凭证；显式成果、任务、模板及资源引用随实体映射，供应商模型标识、正文及普通参数原样保留';
COMMENT ON COLUMN public."report_assets"."position" IS '图片所在章节或占位符标识；独立导出文件为空';
COMMENT ON COLUMN public."report_assets"."status" IS '资源执行状态：queued排队、running执行中、completed完成、failed失败；失败可独立重试';
COMMENT ON COLUMN public."report_assets"."error" IS '图片生成或文件导出失败的脱敏简短原因';
COMMENT ON COLUMN public."report_assets"."created_at" IS '资源生成或导出请求保存时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."report_assets"."updated_at" IS '资源状态或文件存储结果最近更新时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."digest_schedules" IS '用户周期简报计划；支持每日、指定星期和每月日期，选材配置与生成配置分开';
COMMENT ON COLUMN public."digest_schedules"."id" IS '周期简报计划数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
COMMENT ON COLUMN public."digest_schedules"."user_id" IS '计划所有者ID，关联sys_user.id；周期生成的成果必须属于同一用户';
COMMENT ON COLUMN public."digest_schedules"."name" IS '用户维护的周期计划名称；用于计划选择和管理';
COMMENT ON COLUMN public."digest_schedules"."template_id" IS '简报模板ID，关联templates.id；必填且模板purpose必须为digest；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."digest_schedules"."frequency" IS '生成周期：daily每日、weekly每周、monthly每月';
COMMENT ON COLUMN public."digest_schedules"."weekday" IS '每周执行星期；0周一至6周日，仅weekly填写，其他周期为空';
COMMENT ON COLUMN public."digest_schedules"."month_day" IS '每月执行日；1至31，仅monthly填写，短月按当月末日执行';
COMMENT ON COLUMN public."digest_schedules"."run_time" IS '当地固定执行时分秒；与timezone共同解释，不是某天的绝对时间点';
COMMENT ON COLUMN public."digest_schedules"."timezone" IS '计划采用的IANA时区名；默认Asia/Shanghai，用于当地时间转UTC调度';
COMMENT ON COLUMN public."digest_schedules"."selection_config" IS '选材条件JSON对象；包含日期窗口、类别、来源、关键词、去重及最多50篇的自动选材策略；显式类别、来源及资料ID或ID数组按实体映射为十进制字符串，关键词和日期窗口原样保留';
COMMENT ON COLUMN public."digest_schedules"."generation_config" IS '生成设置JSON对象；保存摘要长度和配图等参数，不重复整段材料正文；显式平台业务引用按实体映射，供应商模型标识、提示词及普通参数原样保留';
COMMENT ON COLUMN public."digest_schedules"."is_enabled" IS '计划开关；true启用、false停用，启用前校验真实文本模型及资料条件';
COMMENT ON COLUMN public."digest_schedules"."next_run_at" IS '下次触发的带时区时间点；启用时必填，原子认领后推进调度游标';
COMMENT ON COLUMN public."digest_schedules"."last_run_at" IS '最近派发检查时间；北京时间Asia/Shanghai，timestamp(0)无时区，精度到秒，YYYY-MM-DD HH:mm:ss；历史为空不回填';
COMMENT ON COLUMN public."digest_schedules"."last_status" IS '最近派发结果：queued入队、no_data无匹配、skipped节假日跳过、failed失败；历史为空；生成进度读取关联任务';
COMMENT ON COLUMN public."digest_schedules"."last_error" IS '最近派发失败原因，脱敏后保存；成功或跳过时清空，不包含模型密钥或内部堆栈';
COMMENT ON COLUMN public."digest_schedules"."created_at" IS '周期计划创建时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."digest_schedules"."updated_at" IS '周期计划配置或调度游标最近更新时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."basket_items" IS '用户资料篮及收藏关系；每条只引用一项原资料，不复制正文作为权威内容';
COMMENT ON COLUMN public."basket_items"."id" IS '资料篮或收藏关系自增ID；迁移沿用原saved_item_id的值';
COMMENT ON COLUMN public."basket_items"."user_id" IS '关系所属用户ID，关联sys_user.id；仅允许操作本人的保存关系';
COMMENT ON COLUMN public."basket_items"."action" IS '保存动作：basket加入资料篮、favorite收藏';
COMMENT ON COLUMN public."basket_items"."article_id" IS '新闻来源ID，关联news_articles.id；与paper_id、file_id、report_id恰一非空；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."basket_items"."paper_id" IS '论文来源ID，关联papers.id；与article_id、file_id、report_id恰一非空；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."basket_items"."file_id" IS '上传资料来源ID，关联knowledge_files.id；仍须校验文件所有权，四种来源恰一非空；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."basket_items"."report_id" IS '成果收藏来源ID，关联reports.id；仍须校验成果权限，四种来源恰一非空；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."basket_items"."created_at" IS '加入资料篮或收藏时间，取消仅删除关系不删除原文；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."collection_runs" IS '单次来源采集的排队、执行、停止及失败重试记录；保存独立计数和配置快照';
COMMENT ON COLUMN public."collection_runs"."id" IS '单次采集运行数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
COMMENT ON COLUMN public."collection_runs"."source_id" IS '来源ID，关联data_sources.id；历史运行引用时禁止直接删除来源；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."collection_runs"."parent_id" IS '失败父运行ID；与source_id复合自关联，仅retry填写，防止跨来源、自指和重复直接重试；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
COMMENT ON COLUMN public."collection_runs"."trigger_type" IS '触发类型：manual手动、schedule定时、retry失败重试；非retry的parent_id为空';
COMMENT ON COLUMN public."collection_runs"."request_id" IS '全局唯一运行幂等键，varchar(128)；普通请求键原样保留；系统定时schedule:来源ID:计划触发UTC时刻按实际source_id映射，重试retry:父运行ID按实际parent_id映射，其余字节不变；映射后仍须全局唯一';
COMMENT ON COLUMN public."collection_runs"."status" IS '采集状态：queued排队、running执行中、stopping正在停止、success成功、failed失败、cancelled取消';
COMMENT ON COLUMN public."collection_runs"."available_at" IS '允许认领运行的最早时间；带时区，失败重试的退避截止时间也写入此字段';
COMMENT ON COLUMN public."collection_runs"."config_snapshot" IS '本次采集配置JSON对象快照；重试沿用父记录配置，不回写后来修改的来源参数；明确的平台来源、类别等引用按实体映射，外部采集参数、普通请求键及执行令牌原样保留';
COMMENT ON COLUMN public."collection_runs"."checkpoint" IS '已提交采集边界及受限失败标识的JSON对象；不保存材料正文，不跨过未处理失败项';
COMMENT ON COLUMN public."collection_runs"."fetched_count" IS '本次已读取候选条目数；非负整数，不是请求次数或全库总量';
COMMENT ON COLUMN public."collection_runs"."saved_count" IS '本次成功提交的新建或更新条目数；非负，与failed_count之和不超过fetched_count';
COMMENT ON COLUMN public."collection_runs"."failed_count" IS '本次处理失败的候选条目数；非负，success状态必须为0，不重复累计父运行';
COMMENT ON COLUMN public."collection_runs"."error" IS '执行失败或异常的脱敏简短原因；failed必须非空，success为空，不保存Cookie、密钥或堆栈';
COMMENT ON COLUMN public."collection_runs"."stop_requested_at" IS '收到停止请求的带时区时间点；重复点击不重写，stopping或cancelled必须存在';
COMMENT ON COLUMN public."collection_runs"."execution_token" IS '执行认领令牌；保存、心跳和结束回写须匹配，终态清空以隔离旧执行器；varchar(64)执行令牌，非数值主键，保留原业务字符串';
COMMENT ON COLUMN public."collection_runs"."lease_expires_at" IS '当前执行租约截止时间；带时区，失联恢复前核对，终态清空';
COMMENT ON COLUMN public."collection_runs"."started_at" IS '实际开始采集的带时区时间点；排队即取消时可空';
COMMENT ON COLUMN public."collection_runs"."finished_at" IS '确认成功、失败或取消的带时区时间点；stopping不得提前填写';
COMMENT ON COLUMN public."collection_runs"."created_at" IS '运行记录创建时间，不晚于available_at；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
COMMENT ON COLUMN public."collection_runs"."updated_at" IS '运行状态、计数或已提交断点最近更新时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';

COMMENT ON TABLE public."sys_user" IS '系统用户账号及个人资料；保留原账号状态和删除编码，不存明文密码';
COMMENT ON COLUMN public."sys_user"."id" IS '用户自增ID；保留原user_id值和序列语义';
COMMENT ON COLUMN public."sys_user"."username" IS '唯一登录账号；软删除后仍保留且不可复用';
COMMENT ON COLUMN public."sys_user"."nickname" IS '用户展示昵称；与登录账号分别维护';
COMMENT ON COLUMN public."sys_user"."user_type" IS '用户类型编码；00系统用户，保留原账号协议';
COMMENT ON COLUMN public."sys_user"."email" IS '用户电子邮箱地址；沿用历史可空及空字符串语义';
COMMENT ON COLUMN public."sys_user"."phone" IS '用户手机号码；保留原文本格式，不作为用户主键';
COMMENT ON COLUMN public."sys_user"."sex" IS '用户性别编码：0男、1女、2未知；保留原协议';
COMMENT ON COLUMN public."sys_user"."avatar" IS '用户头像地址或存储路径；沿用现有受控访问规则';
COMMENT ON COLUMN public."sys_user"."password_hash" IS '登录密码的bcrypt加盐哈希；不保存明文密码，不向普通接口返回';
COMMENT ON COLUMN public."sys_user"."status" IS '账号状态编码：0正常、1停用；不强转为布尔值';
COMMENT ON COLUMN public."sys_user"."del_flag" IS '账号删除标志：0存在、2已删除；不与账号停用状态合并';
COMMENT ON COLUMN public."sys_user"."login_ip" IS '最近成功登录的IP地址文本；不是用户唯一标识';
COMMENT ON COLUMN public."sys_user"."last_login_at" IS '最近登录时间；沿用timestamp(0)无时区历史语义，精度到秒，不擅自转换时区';
COMMENT ON COLUMN public."sys_user"."password_updated_at" IS '密码最近更新时间；沿用timestamp(0)无时区历史语义，精度到秒';
COMMENT ON COLUMN public."sys_user"."created_by" IS '账号创建者的历史账号文本；不是sys_user.id外键';
COMMENT ON COLUMN public."sys_user"."created_at" IS '账号创建时间；沿用timestamp(0)无时区历史语义，精度到秒';
COMMENT ON COLUMN public."sys_user"."updated_by" IS '账号最近修改者的历史账号文本；不是sys_user.id外键';
COMMENT ON COLUMN public."sys_user"."updated_at" IS '账号最近修改时间；沿用timestamp(0)无时区历史语义，精度到秒';
COMMENT ON COLUMN public."sys_user"."remark" IS '账号管理备注；不保存明文凭证';

COMMENT ON TABLE public."sys_role" IS '系统角色及权限范围；保留多角色授权关系和既有角色编码';
COMMENT ON COLUMN public."sys_role"."id" IS '角色自增ID；保留原role_id值和授权关系';
COMMENT ON COLUMN public."sys_role"."name" IS '角色展示名称；不替代权限判断使用的角色编码';
COMMENT ON COLUMN public."sys_role"."code" IS '唯一角色权限编码；保留既有管理员和普通用户编码语义';
COMMENT ON COLUMN public."sys_role"."sort_order" IS '角色显示顺序；整数，沿用现有排序约定';
COMMENT ON COLUMN public."sys_role"."data_scope" IS '数据权限范围编码：1全部、2自定义、3本部门、4本部门及以下、5仅本人';
COMMENT ON COLUMN public."sys_role"."menu_check_strictly" IS '菜单树父子选择关联标记；沿用若依1关联、0不关联协议';
COMMENT ON COLUMN public."sys_role"."status" IS '角色状态编码：0正常、1停用';
COMMENT ON COLUMN public."sys_role"."del_flag" IS '角色删除标志：0存在、2已删除';
COMMENT ON COLUMN public."sys_role"."created_by" IS '角色创建者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_role"."created_at" IS '角色创建时间；timestamp(0)无时区，精度到秒，保留历史语义';
COMMENT ON COLUMN public."sys_role"."updated_by" IS '角色最近修改者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_role"."updated_at" IS '角色最近修改时间；timestamp(0)无时区，精度到秒，保留历史语义';
COMMENT ON COLUMN public."sys_role"."remark" IS '角色用途和管理备注；不承载逐项授权关系';

COMMENT ON TABLE public."sys_menu" IS '系统菜单、页面路由及接口权限；根节点父级为0，保留显隐与状态编码';
COMMENT ON COLUMN public."sys_menu"."id" IS '菜单或权限节点自增ID；保留原menu_id值';
COMMENT ON COLUMN public."sys_menu"."name" IS '菜单或接口权限节点名称；用于后台授权界面显示';
COMMENT ON COLUMN public."sys_menu"."parent_id" IS '父菜单ID；0表示根节点，不对不存在的id=0建立外键';
COMMENT ON COLUMN public."sys_menu"."sort_order" IS '同层菜单显示顺序；整数，沿用历史排序值';
COMMENT ON COLUMN public."sys_menu"."path" IS '页面路由或外链地址；保留既有实际路由，不由重命名自动改写';
COMMENT ON COLUMN public."sys_menu"."component" IS '前端页面组件路径；由现有路由加载器解释';
COMMENT ON COLUMN public."sys_menu"."query" IS '路由默认查询参数的JSON文本；空值表示无默认参数';
COMMENT ON COLUMN public."sys_menu"."route_name" IS '前端路由名称；保留原页面标识及缓存引用';
COMMENT ON COLUMN public."sys_menu"."is_frame" IS '外链标志编码：0是外链、1非外链；保留原协议';
COMMENT ON COLUMN public."sys_menu"."is_cache" IS '页面缓存标志编码：0缓存、1不缓存；保留原协议';
COMMENT ON COLUMN public."sys_menu"."type" IS '菜单节点类型：M目录、C菜单、F按钮或接口权限';
COMMENT ON COLUMN public."sys_menu"."visible" IS '菜单可见性编码：0显示、1隐藏；不等同于权限启停';
COMMENT ON COLUMN public."sys_menu"."status" IS '菜单状态编码：0正常、1停用；与可见性分别维护';
COMMENT ON COLUMN public."sys_menu"."permissions" IS '接口或操作权限标识文本；供现有权限校验器匹配';
COMMENT ON COLUMN public."sys_menu"."icon" IS '菜单图标名称；由前端既有图标系统解析';
COMMENT ON COLUMN public."sys_menu"."created_by" IS '菜单创建者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_menu"."created_at" IS '菜单创建时间；timestamp(0)无时区，精度到秒';
COMMENT ON COLUMN public."sys_menu"."updated_by" IS '菜单最近修改者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_menu"."updated_at" IS '菜单最近修改时间；timestamp(0)无时区，精度到秒';
COMMENT ON COLUMN public."sys_menu"."remark" IS '菜单配置管理备注；不替代权限标识';

COMMENT ON TABLE public."sys_user_role" IS '用户与角色的多对多授权关系；用户ID与角色ID组成复合主键';
COMMENT ON COLUMN public."sys_user_role"."user_id" IS '获授权用户ID，关联sys_user.id；与role_id组成复合主键，用户删除时级联清理关系';
COMMENT ON COLUMN public."sys_user_role"."role_id" IS '被授予角色ID，关联sys_role.id；与user_id组成复合主键，角色删除时级联清理关系';

COMMENT ON TABLE public."sys_role_menu" IS '角色与菜单权限的多对多关系；角色ID与菜单ID组成复合主键';
COMMENT ON COLUMN public."sys_role_menu"."role_id" IS '获授权角色ID，关联sys_role.id；与menu_id组成复合主键，角色删除时级联清理关系';
COMMENT ON COLUMN public."sys_role_menu"."menu_id" IS '菜单或权限节点ID，关联sys_menu.id；与role_id组成复合主键，节点删除时级联清理关系';

COMMENT ON TABLE public."sys_config" IS '系统通用参数；参数键保持唯一，不承载文章正文或业务资料副本';
COMMENT ON COLUMN public."sys_config"."id" IS '系统参数自增ID；保留原config_id值';
COMMENT ON COLUMN public."sys_config"."name" IS '系统参数展示名称；与程序读取使用的参数键分开';
COMMENT ON COLUMN public."sys_config"."key" IS '唯一系统参数键；保留原配置读取协议';
COMMENT ON COLUMN public."sys_config"."value" IS '系统参数值文本；具体格式由对应参数校验器解释，不存业务正文';
COMMENT ON COLUMN public."sys_config"."type" IS '系统内置参数标志：Y内置、N非内置';
COMMENT ON COLUMN public."sys_config"."created_by" IS '参数创建者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_config"."created_at" IS '参数创建时间；timestamp(0)无时区，精度到秒';
COMMENT ON COLUMN public."sys_config"."updated_by" IS '参数最近修改者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_config"."updated_at" IS '参数最近修改时间；timestamp(0)无时区，精度到秒';
COMMENT ON COLUMN public."sys_config"."remark" IS '参数用途或取值说明；不保存明文密钥';

COMMENT ON TABLE public."sys_dict_type" IS '系统字典类型及唯一编码；字典项通过类型编码引用，不作为文章类别';
COMMENT ON COLUMN public."sys_dict_type"."id" IS '字典类型自增ID；保留原dict_id值';
COMMENT ON COLUMN public."sys_dict_type"."name" IS '系统字典类型名称；用于后台字典管理';
COMMENT ON COLUMN public."sys_dict_type"."code" IS '唯一字典类型编码；由sys_dict_data.type_code引用，不用整数ID替代';
COMMENT ON COLUMN public."sys_dict_type"."status" IS '字典类型状态编码：0正常、1停用';
COMMENT ON COLUMN public."sys_dict_type"."created_by" IS '字典类型创建者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_dict_type"."created_at" IS '字典类型创建时间；timestamp(0)无时区，精度到秒';
COMMENT ON COLUMN public."sys_dict_type"."updated_by" IS '字典类型最近修改者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_dict_type"."updated_at" IS '字典类型最近修改时间；timestamp(0)无时区，精度到秒';
COMMENT ON COLUMN public."sys_dict_type"."remark" IS '字典类型适用范围及管理备注';

COMMENT ON TABLE public."sys_dict_data" IS '系统字典选项及界面展示配置；通过type_code关联字典类型编码';
COMMENT ON COLUMN public."sys_dict_data"."id" IS '字典选项自增ID；保留原dict_code值';
COMMENT ON COLUMN public."sys_dict_data"."sort_order" IS '同一字典类型内的选项排序值；整数';
COMMENT ON COLUMN public."sys_dict_data"."label" IS '字典选项展示标签；用于界面显示，不代替存储值';
COMMENT ON COLUMN public."sys_dict_data"."value" IS '字典选项实际取值文本；沿用现有业务编码';
COMMENT ON COLUMN public."sys_dict_data"."type_code" IS '所属字典类型编码，关联sys_dict_type.code；编码更新或类型删除时级联处理';
COMMENT ON COLUMN public."sys_dict_data"."css_class" IS '字典选项展示的CSS类名；沿用现有前端渲染约定';
COMMENT ON COLUMN public."sys_dict_data"."list_class" IS '字典选项的列表样式标识；不表示业务状态';
COMMENT ON COLUMN public."sys_dict_data"."is_default" IS '是否默认选项编码：Y是、N否；保留原字符串协议';
COMMENT ON COLUMN public."sys_dict_data"."status" IS '字典选项状态编码：0正常、1停用';
COMMENT ON COLUMN public."sys_dict_data"."created_by" IS '字典选项创建者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_dict_data"."created_at" IS '字典选项创建时间；timestamp(0)无时区，精度到秒';
COMMENT ON COLUMN public."sys_dict_data"."updated_by" IS '字典选项最近修改者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_dict_data"."updated_at" IS '字典选项最近修改时间；timestamp(0)无时区，精度到秒';
COMMENT ON COLUMN public."sys_dict_data"."remark" IS '字典选项用途或取值管理备注';

COMMENT ON TABLE public."sys_logininfor" IS '登录成功及失败事件；用户名为事件发生时文本，失败账号允许不存在';
COMMENT ON COLUMN public."sys_logininfor"."id" IS '登录事件自增ID；保留原info_id值';
COMMENT ON COLUMN public."sys_logininfor"."username" IS '事件发生时的登录账号文本；失败登录允许账号不存在，不设用户外键';
COMMENT ON COLUMN public."sys_logininfor"."ip" IS '本次登录请求的IP地址文本';
COMMENT ON COLUMN public."sys_logininfor"."location" IS '登录IP解析的位置说明；未知时允许为空';
COMMENT ON COLUMN public."sys_logininfor"."browser" IS '登录请求解析出的浏览器名称或版本';
COMMENT ON COLUMN public."sys_logininfor"."os" IS '登录请求解析出的操作系统名称';
COMMENT ON COLUMN public."sys_logininfor"."status" IS '登录结果编码：0成功、1失败；不是用户账号状态';
COMMENT ON COLUMN public."sys_logininfor"."message" IS '登录结果的脱敏说明；不包含密码或令牌';
COMMENT ON COLUMN public."sys_logininfor"."logged_at" IS '登录事件时间；timestamp(0)无时区，精度到秒，保留历史语义';

COMMENT ON TABLE public."sys_oper_log" IS '管理操作日志及脱敏请求响应摘要；操作人名称保留事件发生时文本';
COMMENT ON COLUMN public."sys_oper_log"."id" IS '管理操作事件自增ID；保留原oper_id值';
COMMENT ON COLUMN public."sys_oper_log"."title" IS '管理操作所属模块或操作标题';
COMMENT ON COLUMN public."sys_oper_log"."business_type" IS '业务操作类型编码：0其他、1新增、2修改、3删除、4授权、5导出、6导入、7强退、8生成代码、9清空';
COMMENT ON COLUMN public."sys_oper_log"."method" IS '被调用后端方法名称的事件快照';
COMMENT ON COLUMN public."sys_oper_log"."request_method" IS '本次HTTP请求方法，如GET、POST、PUT或DELETE';
COMMENT ON COLUMN public."sys_oper_log"."operator_type" IS '操作终端类型编码：0其他、1后台用户、2手机端用户';
COMMENT ON COLUMN public."sys_oper_log"."username" IS '事件发生时的操作账号文本；不随用户改名回写，不强加用户外键';
COMMENT ON COLUMN public."sys_oper_log"."url" IS '本次管理操作请求地址；不作为新闻原文来源';
COMMENT ON COLUMN public."sys_oper_log"."ip" IS '本次管理操作来源IP地址文本';
COMMENT ON COLUMN public."sys_oper_log"."location" IS '操作IP解析的位置说明；未知时允许为空';
COMMENT ON COLUMN public."sys_oper_log"."request_data" IS '经过脱敏及长度限制的请求参数文本；不保存密码或调用密钥';
COMMENT ON COLUMN public."sys_oper_log"."response_data" IS '经过脱敏及长度限制的响应摘要文本；不保存访问令牌';
COMMENT ON COLUMN public."sys_oper_log"."status" IS '操作结果编码：0正常、1异常';
COMMENT ON COLUMN public."sys_oper_log"."error" IS '管理操作异常的脱敏说明；不保存完整敏感堆栈';
COMMENT ON COLUMN public."sys_oper_log"."operated_at" IS '管理操作发生时间；timestamp(0)无时区，精度到秒';
COMMENT ON COLUMN public."sys_oper_log"."duration_ms" IS '本次管理操作耗时，单位毫秒；不是时间戳';

COMMENT ON TABLE public."sys_job" IS '系统调度任务配置；负责扫描器及执行器唤醒，不重复保存来源或简报计划';
COMMENT ON COLUMN public."sys_job"."id" IS '系统任务自增ID；保留原job_id值，不替代业务计划ID';
COMMENT ON COLUMN public."sys_job"."name" IS '系统调度任务名称；用于任务管理界面显示';
COMMENT ON COLUMN public."sys_job"."group_key" IS '系统调度任务分组标识；沿用既有调度配置';
COMMENT ON COLUMN public."sys_job"."executor" IS '系统任务执行器标识；由受控任务注册机制解释';
COMMENT ON COLUMN public."sys_job"."invoke_target" IS '系统任务调用目标标识；由现有受控调度器解析，非任意外部命令';
COMMENT ON COLUMN public."sys_job"."args" IS '任务位置参数文本；沿用现有英文逗号分隔格式';
COMMENT ON COLUMN public."sys_job"."kwargs" IS '任务关键字参数的JSON对象文本；由现有调用适配器解析';
COMMENT ON COLUMN public."sys_job"."cron_expression" IS '系统任务cron表达式；负责扫描器唤醒，不复制来源或简报业务周期';
COMMENT ON COLUMN public."sys_job"."misfire_policy" IS '错过触发策略编码：2合并补跑、3超长宽限期，其他值不合并且不限制宽限期；沿用现实现';
COMMENT ON COLUMN public."sys_job"."concurrent" IS '并发执行标志编码：0允许、1禁止';
COMMENT ON COLUMN public."sys_job"."status" IS '系统任务状态编码：0正常、1暂停';
COMMENT ON COLUMN public."sys_job"."created_by" IS '系统任务创建者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_job"."created_at" IS '系统任务创建时间；timestamp(0)无时区，精度到秒';
COMMENT ON COLUMN public."sys_job"."updated_by" IS '系统任务最近修改者的历史账号文本；不是用户ID外键';
COMMENT ON COLUMN public."sys_job"."updated_at" IS '系统任务最近修改时间；timestamp(0)无时区，精度到秒';
COMMENT ON COLUMN public."sys_job"."remark" IS '系统任务用途及运维说明；不承载业务材料正文';

COMMENT ON TABLE public."sys_job_log" IS '系统调度任务执行日志；调用目标、参数及任务名称均为执行时快照';
COMMENT ON COLUMN public."sys_job_log"."id" IS '系统任务执行日志自增ID；保留原job_log_id值';
COMMENT ON COLUMN public."sys_job_log"."job_id" IS '系统任务ID，关联sys_job.id；任务删除后置空，仍保留本次执行快照';
COMMENT ON COLUMN public."sys_job_log"."name" IS '执行时的系统任务名称快照；不随任务改名更新';
COMMENT ON COLUMN public."sys_job_log"."group_key" IS '执行时的任务分组标识快照';
COMMENT ON COLUMN public."sys_job_log"."executor" IS '执行时的任务执行器标识快照';
COMMENT ON COLUMN public."sys_job_log"."invoke_target" IS '执行时的受控任务调用目标快照';
COMMENT ON COLUMN public."sys_job_log"."args" IS '执行时的位置参数快照；英文逗号分隔文本';
COMMENT ON COLUMN public."sys_job_log"."kwargs" IS '执行时关键字参数的JSON对象文本快照；不随后续任务配置更新';
COMMENT ON COLUMN public."sys_job_log"."trigger" IS '本次任务触发器说明；保留原job_trigger文本语义';
COMMENT ON COLUMN public."sys_job_log"."message" IS '本次任务执行结果的脱敏说明';
COMMENT ON COLUMN public."sys_job_log"."status" IS '系统任务执行结果编码：0正常、1失败';
COMMENT ON COLUMN public."sys_job_log"."error" IS '本次执行异常的脱敏说明；不保存明文凭证';
COMMENT ON COLUMN public."sys_job_log"."created_at" IS '任务执行日志记录时间；timestamp(0)无时区，精度到秒';

DO $pipesight_apscheduler_jobs_comments$
BEGIN
    IF to_regclass('public.apscheduler_jobs') IS NOT NULL THEN
        COMMENT ON TABLE public."apscheduler_jobs" IS 'APScheduler持久化任务表；框架管理运行时间和序列化任务，不存业务正文';
        COMMENT ON COLUMN public."apscheduler_jobs"."id" IS 'APScheduler分配的持久化任务唯一标识；与sys_job的业务任务编号区分';
        COMMENT ON COLUMN public."apscheduler_jobs"."next_run_time" IS '下次调度的Unix时间戳，单位秒；空值表示暂停或尚无下次执行时间，保留框架浮点类型';
        COMMENT ON COLUMN public."apscheduler_jobs"."job_state" IS 'APScheduler任务的二进制Pickle序列化状态；仅由可信调度器写入和反序列化，不是JSON';
    END IF;
END;
$pipesight_apscheduler_jobs_comments$;

DO $pipesight_alembic_version_comments$
BEGIN
    IF to_regclass('public.alembic_version') IS NOT NULL THEN
        COMMENT ON TABLE public."alembic_version" IS 'Alembic数据库迁移版本记录；由迁移工具维护已应用的迁移头版本';
        COMMENT ON COLUMN public."alembic_version"."version_num" IS '已应用的Alembic迁移头版本标识；多分支迁移允许多条版本记录';
    END IF;
END;
$pipesight_alembic_version_comments$;

DO $pipesight_model_calls_comments$
BEGIN
    IF to_regclass('public.model_calls') IS NOT NULL THEN
        COMMENT ON TABLE public."model_calls" IS '实际供应商模型调用的用量和排障记录；不保存提示词、原始正文、凭证或响应原文';
        COMMENT ON COLUMN public."model_calls"."id" IS '实际供应商调用记录数值主键；BIGINT正整数，由12张业务表共享序列business_id_seq分配；API以十进制字符串返回，旧字符串ID通过迁移映射保留对应关系';
        COMMENT ON COLUMN public."model_calls"."task_id" IS '可空生成任务ID，关联generation_tasks.id；任务删除后置空，权限仍须服务端校验；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
        COMMENT ON COLUMN public."model_calls"."model_id" IS '实际调用模型ID，关联ai_models.id；必填，被引用模型禁止直接删除';
        COMMENT ON COLUMN public."model_calls"."capability" IS '实际调用能力：text_generate正文生成、image_generate图片生成；不以图片输入能力替代';
        COMMENT ON COLUMN public."model_calls"."status" IS '供应商调用结果：success成功、failed失败；不是人工审核或整份成果状态';
        COMMENT ON COLUMN public."model_calls"."duration_ms" IS '实际供应商请求耗时，单位毫秒；整数且非负';
        COMMENT ON COLUMN public."model_calls"."input_tokens" IS '供应商返回的输入Token用量；可空且非负，未返回时不假记为0';
        COMMENT ON COLUMN public."model_calls"."output_tokens" IS '供应商返回的输出Token用量；可空且非负，未返回时不假记为0';
        COMMENT ON COLUMN public."model_calls"."error" IS '调用失败的脱敏简短原因；不保存供应商响应原文、密钥或用户正文';
        COMMENT ON COLUMN public."model_calls"."created_at" IS '模型调用记录保存时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
    END IF;
END;
$pipesight_model_calls_comments$;

DO $pipesight_report_versions_comments$
BEGIN
    IF to_regclass('public.report_versions') IS NOT NULL THEN
        COMMENT ON TABLE public."report_versions" IS '成果编辑及恢复历史；同一成果与版本号唯一，历史正文不由并发版本字段替代';
        COMMENT ON COLUMN public."report_versions"."id" IS '成果历史版本自增ID；不等于同一成果内的version序号';
        COMMENT ON COLUMN public."report_versions"."report_id" IS '所属成果ID，关联reports.id；成果删除时级联删除对应历史；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串';
        COMMENT ON COLUMN public."report_versions"."version" IS '成果历史版本号；整数且至少1，与report_id组成唯一键';
        COMMENT ON COLUMN public."report_versions"."title" IS '此历史版本的成果标题快照；不随当前成果标题修改';
        COMMENT ON COLUMN public."report_versions"."content" IS '此历史版本的正文快照；用于历史查看或明确恢复，不自动覆盖当前编辑稿';
        COMMENT ON COLUMN public."report_versions"."sections" IS '此历史版本结构化章节的JSON数组快照；默认空数组；显式平台引用按实体映射为十进制字符串，章节顺序、标题和正文原样保留';
        COMMENT ON COLUMN public."report_versions"."citations" IS '此历史版本引用资料的JSON数组快照；默认空数组；依据资料类型映射显式引用ID，保留引文文本与顺序；类型化引文source_id表示被引用资料而非采集来源，缺失或歧义引用在写入前拒绝';
        COMMENT ON COLUMN public."report_versions"."quality_issues" IS '此历史版本自动质量提示的JSON数组快照；不是人工审批事件';
        COMMENT ON COLUMN public."report_versions"."model_snapshot" IS '此历史版本模型标识与参数的JSON对象快照；不含调用凭证；模型标识维持原ai_models编号域，普通参数不改写，明确的平台业务引用须按所属实体映射';
        COMMENT ON COLUMN public."report_versions"."source" IS '版本来源标识，如manual手动编辑、生成或恢复；默认manual，保留实际来源值';
        COMMENT ON COLUMN public."report_versions"."operator_id" IS '可空操作者ID，关联sys_user.id；用户删除后置空';
        COMMENT ON COLUMN public."report_versions"."operator_name" IS '版本保存时的操作者名称快照；必填可为空字符串，不随用户改名更新';
        COMMENT ON COLUMN public."report_versions"."created_at" IS '成果历史版本保存时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss';
    END IF;
END;
$pipesight_report_versions_comments$;

DO $pipesight_list_table_comments$
BEGIN
    IF to_regclass('public.list_table') IS NOT NULL THEN
        COMMENT ON VIEW public."list_table" IS '公共库表目录视图；显示表名与目录注释，时间列为当前查询事务时间';
        COMMENT ON COLUMN public."list_table"."table_name" IS '公共库源表名称；取自pg_class.relname';
        COMMENT ON COLUMN public."list_table"."table_comment" IS '源表目录注释；取自obj_description，未注释时为空';
        COMMENT ON COLUMN public."list_table"."create_time" IS '当前查询事务时间的目录兼容列；不是源表真实创建时间';
        COMMENT ON COLUMN public."list_table"."update_time" IS '当前查询事务时间的目录兼容列；不是源表最近结构变更时间';
    END IF;
END;
$pipesight_list_table_comments$;

DO $pipesight_list_column_comments$
BEGIN
    IF to_regclass('public.list_column') IS NOT NULL THEN
        COMMENT ON VIEW public."list_column" IS '公共库列目录视图；按系统目录汇总字段、类型、注释及约束标记';
        COMMENT ON COLUMN public."list_column"."table_name" IS '字段所属公共库源表名称';
        COMMENT ON COLUMN public."list_column"."column_name" IS '源表字段名称；取自pg_attribute.attname';
        COMMENT ON COLUMN public."list_column"."column_comment" IS '源字段目录注释；取自pg_description，未注释时为空';
        COMMENT ON COLUMN public."list_column"."is_required" IS '目录兼容必填标记：1非空且无关联约束、0其他；保留当前视图口径';
        COMMENT ON COLUMN public."list_column"."is_pk" IS '目录兼容约束标记：1有关联约束、0无；当前口径可能同时标记非主键约束';
        COMMENT ON COLUMN public."list_column"."sort" IS '源字段物理序号；取自pg_attribute.attnum';
        COMMENT ON COLUMN public."list_column"."is_increment" IS '目录兼容自增标记：1默认表达式匹配约定序列名、0未匹配；保留当前视图口径';
        COMMENT ON COLUMN public."list_column"."column_type" IS '源字段类型名称；数组显示ARRAY，域类型显示基础类型';
    END IF;
END;
$pipesight_list_column_comments$;

