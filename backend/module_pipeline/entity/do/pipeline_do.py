from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from config.database import Base


class PipelineSource(Base):
    """可独立配置和执行的数据采集来源。"""

    __tablename__ = 'data_sources'
    __table_args__ = (
        UniqueConstraint('source_code', name='uk_data_sources_code'),
        CheckConstraint("status IN ('active', 'inactive')", name='ck_data_sources_status'),
        CheckConstraint(
            'success_count >= 0 AND failure_count >= 0 AND consecutive_failures >= 0',
            name='ck_data_sources_counters',
        ),
        CheckConstraint(
            "handoff_mode IN ('local', 'external')",
            name='ck_data_sources_handoff_mode',
        ),
        Index('idx_data_sources_type_status', 'source_type', 'status'),
        Index('idx_data_sources_owner', 'owner_id'),
        {'comment': '数据来源配置表'},
    )

    source_id = Column(String(64), primary_key=True, nullable=False, comment='数据源ID')
    source_code = Column(String(100), nullable=False, comment='稳定的数据源编码')
    name = Column(String(255), nullable=False, comment='数据源名称')
    source_type = Column(String(32), nullable=False, comment='数据源类型')
    endpoint = Column(String(1000), nullable=True, comment='数据源入口地址')
    adapter_key = Column(String(128), nullable=False, comment='采集适配器标识')
    schedule_cron = Column(String(100), nullable=True, comment='调度表达式')
    status = Column(String(32), nullable=False, server_default='active', comment='生命周期状态')
    enabled = Column(Boolean, nullable=False, server_default='1', comment='是否允许执行采集')
    config_json = Column(JSON, nullable=False, default=dict, comment='采集规则与增量配置')
    handoff_mode = Column(String(16), nullable=False, server_default='external', comment='处理模式：local或external')
    processor_source_code = Column(String(128), nullable=True, comment='外部处理系统来源编码')
    last_run_time = Column(DateTime, nullable=True, comment='最近采集时间')
    last_run_status = Column(String(32), nullable=True, comment='最近采集状态')
    success_count = Column(Integer, nullable=False, server_default='0', comment='累计成功次数')
    failure_count = Column(Integer, nullable=False, server_default='0', comment='累计失败次数')
    consecutive_failures = Column(Integer, nullable=False, server_default='0', comment='连续失败次数')
    owner_id = Column(
        BigInteger, ForeignKey('sys_user.user_id', ondelete='SET NULL'), nullable=True, comment='负责人ID'
    )
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PipelinePromptVersion(Base):
    """可审计的模型提示词版本，只有测试通过的版本才能发布。"""

    __tablename__ = 'pipeline_prompt_versions'
    __table_args__ = (
        UniqueConstraint('prompt_key', 'version_no', name='uk_pipeline_prompt_key_version'),
        CheckConstraint("status IN ('draft', 'published', 'retired')", name='ck_pipeline_prompt_status'),
        CheckConstraint("test_status IN ('untested', 'passed', 'failed')", name='ck_pipeline_prompt_test_status'),
        CheckConstraint('version_no >= 1', name='ck_pipeline_prompt_version_no'),
        Index('idx_pipeline_prompt_scene_status', 'scene', 'status'),
        Index('idx_pipeline_prompt_key_time', 'prompt_key', 'update_time'),
        {'comment': '管网模型提示词版本表'},
    )

    prompt_id = Column(String(64), primary_key=True, nullable=False, comment='提示词版本ID')
    prompt_key = Column(String(64), nullable=False, comment='稳定提示词编码')
    scene = Column(String(64), nullable=False, comment='业务场景')
    name = Column(String(255), nullable=False, comment='提示词名称')
    description = Column(String(1000), nullable=False, default='', comment='用途说明')
    system_prompt = Column(Text, nullable=False, comment='系统提示词')
    user_prompt = Column(Text, nullable=False, comment='用户提示词模板')
    version_no = Column(Integer, nullable=False, server_default='1', comment='版本号')
    status = Column(String(32), nullable=False, server_default='draft', comment='版本状态')
    test_status = Column(String(32), nullable=False, server_default='untested', comment='离线测试状态')
    test_result = Column(JSON, nullable=False, default=dict, comment='最近一次测试结果')
    operator_id = Column(
        BigInteger, ForeignKey('sys_user.user_id', ondelete='SET NULL'), nullable=True, comment='操作用户ID'
    )
    operator_name = Column(String(64), nullable=False, default='', comment='操作用户名称快照')
    published_at = Column(DateTime, nullable=True, comment='发布时间')
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PipelineTemplateVersion(Base):
    """可发布的科研报告和情报简报模板版本。"""

    __tablename__ = 'pipeline_template_versions'
    __table_args__ = (
        UniqueConstraint('template_key', 'version_no', name='uk_pipeline_template_key_version'),
        CheckConstraint("status IN ('draft', 'published', 'retired')", name='ck_pipeline_template_status'),
        CheckConstraint('version_no >= 1', name='ck_pipeline_template_version_no'),
        Index('idx_pipeline_template_category_status', 'category', 'status'),
        Index('idx_pipeline_template_key_time', 'template_key', 'update_time'),
        {'comment': '管网科研与情报模板版本表'},
    )

    template_id = Column(String(64), primary_key=True, nullable=False, comment='模板版本ID')
    template_key = Column(String(64), nullable=False, comment='稳定模板编码')
    code = Column(String(32), nullable=False, comment='模板展示编码')
    category = Column(String(32), nullable=False, comment='模板分类')
    report_type = Column(String(64), nullable=False, comment='报告类型')
    name = Column(String(255), nullable=False, comment='模板名称')
    description = Column(String(1000), nullable=False, default='', comment='模板说明')
    color = Column(String(32), nullable=False, default='#2764e7', comment='展示颜色')
    version_label = Column(String(32), nullable=False, comment='展示版本号')
    version_no = Column(Integer, nullable=False, server_default='1', comment='版本序号')
    status = Column(String(32), nullable=False, server_default='draft', comment='版本状态')
    formats = Column(JSON, nullable=False, default=list, comment='支持的输出格式')
    sections = Column(JSON, nullable=False, default=list, comment='章节结构')
    usage_count = Column(Integer, nullable=False, server_default='0', comment='使用次数快照')
    operator_id = Column(
        BigInteger, ForeignKey('sys_user.user_id', ondelete='SET NULL'), nullable=True, comment='操作用户ID'
    )
    operator_name = Column(String(64), nullable=False, default='', comment='操作用户名称快照')
    published_at = Column(DateTime, nullable=True, comment='发布时间')
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PipelineCrawlRun(Base):
    """一次可追溯的采集执行。"""

    __tablename__ = 'collection_runs'
    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('schedule', 'manual', 'retry')",
            name='ck_collection_runs_trigger_type',
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'success', 'failed', 'cancelled')",
            name='ck_collection_runs_status',
        ),
        CheckConstraint(
            'fetched_count >= 0 AND inserted_count >= 0 AND updated_count >= 0 '
            'AND duplicate_count >= 0 AND failed_count >= 0 AND handoff_count >= 0 '
            'AND handoff_processed_count >= 0 AND handoff_failed_count >= 0',
            name='ck_collection_runs_counters',
        ),
        CheckConstraint(
            "handoff_status IN ('pending', 'dispatched', 'processing', 'completed', 'partial', 'failed')",
            name='ck_collection_runs_handoff_status',
        ),
        Index('idx_collection_runs_source_time', 'source_id', 'create_time'),
        Index('idx_collection_runs_status_time', 'status', 'create_time'),
        {'comment': '采集运行记录表'},
    )

    run_id = Column(String(64), primary_key=True, nullable=False, comment='运行ID')
    source_id = Column(
        String(64), ForeignKey('data_sources.source_id', ondelete='RESTRICT'), nullable=False, comment='数据源ID'
    )
    scheduler_job_id = Column(
        BigInteger, ForeignKey('sys_job.job_id', ondelete='SET NULL'), nullable=True, comment='调度任务ID'
    )
    trigger_type = Column(String(32), nullable=False, server_default='schedule', comment='触发类型')
    status = Column(String(32), nullable=False, server_default='queued', comment='运行状态')
    config_snapshot = Column(JSON, nullable=False, default=dict, comment='本次执行配置快照')
    started_at = Column(DateTime, nullable=True, comment='开始时间')
    finished_at = Column(DateTime, nullable=True, comment='结束时间')
    fetched_count = Column(Integer, nullable=False, server_default='0', comment='抓取条数')
    inserted_count = Column(Integer, nullable=False, server_default='0', comment='新增条数')
    updated_count = Column(Integer, nullable=False, server_default='0', comment='更新条数')
    duplicate_count = Column(Integer, nullable=False, server_default='0', comment='去重条数')
    failed_count = Column(Integer, nullable=False, server_default='0', comment='失败条数')
    handoff_status = Column(String(32), nullable=False, server_default='pending', comment='外部处理状态')
    handoff_batch_id = Column(String(64), nullable=True, comment='外部处理批次ID')
    handoff_count = Column(Integer, nullable=False, server_default='0', comment='提交外部处理条数')
    handoff_processed_count = Column(Integer, nullable=False, server_default='0', comment='外部处理完成条数')
    handoff_failed_count = Column(Integer, nullable=False, server_default='0', comment='外部处理失败条数')
    handoff_time = Column(DateTime, nullable=True, comment='最近一次外部处理回执时间')
    handoff_error = Column(Text, nullable=True, comment='外部处理错误摘要')
    error_message = Column(Text, nullable=True, comment='错误信息')
    checkpoint_json = Column(JSON, nullable=False, default=dict, comment='断点信息')
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PipelineArticle(Base):
    """新闻与公众号文章。"""

    __tablename__ = 'news_articles'
    __table_args__ = (
        UniqueConstraint('article_hash', name='uk_news_articles_hash'),
        UniqueConstraint('url_hash', name='uk_news_articles_url_hash'),
        CheckConstraint("article_type IN ('news', 'wechat')", name='ck_news_articles_type'),
        CheckConstraint('relevance_score BETWEEN 0 AND 100', name='ck_news_articles_relevance'),
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name='ck_news_articles_review_status',
        ),
        CheckConstraint(
            "permission_scope IN ('private', 'public')",
            name='ck_news_articles_permission_scope',
        ),
        CheckConstraint(
            "handoff_status IN ('pending', 'dispatched', 'processing', 'completed', 'partial', 'failed', 'rejected')",
            name='ck_news_articles_handoff_status',
        ),
        Index('idx_news_articles_type_time', 'article_type', 'published_time'),
        Index('idx_news_articles_source_time', 'source_id', 'published_time'),
        Index('idx_news_articles_review_time', 'review_status', 'published_time'),
        {'comment': '科技资讯文章表'},
    )

    article_id = Column(String(64), primary_key=True, nullable=False, comment='文章ID')
    article_type = Column(String(32), nullable=False, comment='文章类型：news或wechat')
    title = Column(String(500), nullable=False, comment='标题')
    canonical_url = Column(String(1500), nullable=True, comment='规范化地址')
    url_hash = Column(String(128), nullable=True, comment='规范化地址指纹')
    source_id = Column(
        String(64), ForeignKey('data_sources.source_id', ondelete='SET NULL'), nullable=True, comment='数据源ID'
    )
    source_name = Column(String(255), nullable=True, comment='数据源名称快照')
    collection_run_id = Column(
        String(64), ForeignKey('collection_runs.run_id', ondelete='SET NULL'), nullable=True, comment='采集运行ID'
    )
    author_text = Column(String(500), nullable=True, comment='作者')
    published_time = Column(DateTime, nullable=True, comment='发布时间')
    discovered_time = Column(DateTime, nullable=False, default=datetime.now, comment='发现时间')
    language = Column(String(16), nullable=False, server_default='zh-CN', comment='语言')
    summary = Column(Text, nullable=True, comment='摘要')
    body = Column(Text, nullable=True, comment='正文')
    article_hash = Column(String(128), nullable=True, comment='正文指纹')
    relevance_score = Column(Integer, nullable=False, server_default='0', comment='相关性评分')
    review_status = Column(String(32), nullable=False, server_default='pending', comment='审核状态')
    permission_scope = Column(String(32), nullable=False, server_default='public', comment='可见范围')
    tags = Column(JSON, nullable=False, default=list, comment='标签')
    metadata_json = Column(JSON, nullable=False, default=dict, comment='扩展元数据')
    analysis_version = Column(String(64), nullable=True, comment='当前分析版本')
    handoff_status = Column(String(32), nullable=False, server_default='pending', comment='外部处理状态')
    handoff_batch_id = Column(String(64), nullable=True, comment='外部处理批次ID')
    handoff_record_id = Column(String(128), nullable=True, comment='外部处理记录ID')
    handoff_trace_id = Column(String(64), nullable=True, comment='外部Prompt血缘或处理追踪ID')
    handoff_version = Column(String(64), nullable=True, comment='外部处理版本')
    handoff_result_json = Column(JSON, nullable=False, default=dict, comment='外部处理结果快照')
    handoff_time = Column(DateTime, nullable=True, comment='外部处理回执时间')
    handoff_error = Column(Text, nullable=True, comment='外部处理错误摘要')
    version_no = Column(Integer, nullable=False, server_default='1', comment='内容版本号')
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PipelinePaper(Base):
    """论文元数据与合法全文状态。"""

    __tablename__ = 'papers'
    __table_args__ = (
        UniqueConstraint('doi_normalized', name='uk_papers_doi_normalized'),
        CheckConstraint('publication_year IS NULL OR publication_year >= 1600', name='ck_papers_publication_year'),
        CheckConstraint('citation_count >= 0', name='ck_papers_citation_count'),
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name='ck_papers_review_status',
        ),
        CheckConstraint(
            "permission_scope IN ('private', 'public')",
            name='ck_papers_permission_scope',
        ),
        CheckConstraint(
            "handoff_status IN ('pending', 'dispatched', 'processing', 'completed', 'partial', 'failed', 'rejected')",
            name='ck_papers_handoff_status',
        ),
        Index('idx_papers_year', 'publication_year'),
        Index('idx_papers_journal', 'journal'),
        Index('idx_papers_source_time', 'source_id', 'create_time'),
        {'comment': '论文资料表'},
    )

    paper_id = Column(String(64), primary_key=True, nullable=False, comment='论文ID')
    title = Column(String(500), nullable=False, comment='论文标题')
    canonical_url = Column(String(1500), nullable=True, comment='论文来源地址')
    source_id = Column(
        String(64), ForeignKey('data_sources.source_id', ondelete='SET NULL'), nullable=True, comment='数据源ID'
    )
    source_name = Column(String(255), nullable=True, comment='数据源名称快照')
    collection_run_id = Column(
        String(64), ForeignKey('collection_runs.run_id', ondelete='SET NULL'), nullable=True, comment='采集运行ID'
    )
    authors = Column(String(1000), nullable=True, comment='作者展示文本')
    authors_json = Column(JSON, nullable=False, default=list, comment='结构化作者与机构')
    keywords = Column(JSON, nullable=False, default=list, comment='论文关键词')
    doi = Column(String(255), nullable=True, comment='原始DOI')
    doi_normalized = Column(String(255), nullable=True, comment='规范化DOI')
    external_id = Column(String(255), nullable=True, comment='外部数据库ID')
    journal = Column(String(255), nullable=True, comment='期刊或会议')
    publisher = Column(String(255), nullable=True, comment='出版方')
    publication_year = Column(Integer, nullable=True, comment='发表年份')
    volume = Column(String(64), nullable=True, comment='卷')
    issue = Column(String(64), nullable=True, comment='期')
    pages = Column(String(64), nullable=True, comment='页码')
    abstract_text = Column(Text, nullable=True, comment='论文摘要')
    full_text_url = Column(String(1500), nullable=True, comment='合法全文地址')
    citation_count = Column(Integer, nullable=False, server_default='0', comment='引用次数')
    open_access_status = Column(String(32), nullable=False, server_default='unknown', comment='开放获取状态')
    full_text_status = Column(String(32), nullable=False, server_default='unknown', comment='全文状态')
    review_status = Column(String(32), nullable=False, server_default='pending', comment='审核状态')
    permission_scope = Column(String(32), nullable=False, server_default='public', comment='可见范围')
    tags = Column(JSON, nullable=False, default=list, comment='标签')
    metadata_json = Column(JSON, nullable=False, default=dict, comment='扩展元数据')
    handoff_status = Column(String(32), nullable=False, server_default='pending', comment='外部处理状态')
    handoff_batch_id = Column(String(64), nullable=True, comment='外部处理批次ID')
    handoff_record_id = Column(String(128), nullable=True, comment='外部处理记录ID')
    handoff_trace_id = Column(String(64), nullable=True, comment='外部Prompt血缘或处理追踪ID')
    handoff_version = Column(String(64), nullable=True, comment='外部处理版本')
    handoff_result_json = Column(JSON, nullable=False, default=dict, comment='外部处理结果快照')
    handoff_time = Column(DateTime, nullable=True, comment='外部处理回执时间')
    handoff_error = Column(Text, nullable=True, comment='外部处理错误摘要')
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PipelineMaterial(Base):
    """用户上传并可进入知识检索的文件。"""

    __tablename__ = 'knowledge_files'
    __table_args__ = (
        CheckConstraint(
            "permission_scope IN ('private', 'public')",
            name='ck_knowledge_files_permission_scope',
        ),
        CheckConstraint(
            "parse_status IN ('queued', 'parsing', 'indexed', 'failed')",
            name='ck_knowledge_files_parse_status',
        ),
        CheckConstraint('file_size >= 0', name='ck_knowledge_files_file_size'),
        CheckConstraint('version_no >= 1', name='ck_knowledge_files_version_no'),
        Index('idx_knowledge_files_owner_time', 'owner_id', 'update_time'),
        Index('idx_knowledge_files_scope', 'permission_scope', 'update_time'),
        Index('idx_knowledge_files_status_time', 'parse_status', 'update_time'),
        Index('idx_knowledge_files_hash', 'file_hash'),
        {'comment': '知识库文件表'},
    )

    file_id = Column(String(64), primary_key=True, nullable=False, comment='知识文件ID')
    name = Column(String(255), nullable=False, comment='资料名称')
    category = Column(String(64), nullable=False, server_default='内部文献', comment='资料分类')
    file_name = Column(String(255), nullable=True, comment='存储文件名')
    file_path = Column(String(500), nullable=True, comment='对象存储键或本地映射路径')
    file_url = Column(String(1000), nullable=True, comment='受控文件访问地址')
    mime_type = Column(String(128), nullable=True, comment='文件MIME类型')
    file_size = Column(BigInteger, nullable=False, server_default='0', comment='文件大小')
    file_hash = Column(String(128), nullable=True, comment='文件SHA-256')
    permission_scope = Column(String(32), nullable=False, server_default='private', comment='可见范围')
    allow_download = Column(Boolean, nullable=False, server_default='1', comment='是否允许下载')
    allow_ai_use = Column(Boolean, nullable=False, server_default='1', comment='是否允许用于AI')
    parse_status = Column(String(32), nullable=False, server_default='queued', comment='解析状态')
    parse_message = Column(String(500), nullable=True, comment='解析说明')
    summary = Column(Text, nullable=True, comment='资料摘要')
    extracted_text = Column(Text, nullable=True, comment='完整提取文本')
    tags = Column(JSON, nullable=False, default=list, comment='标签')
    metadata_json = Column(JSON, nullable=False, default=dict, comment='扩展元数据')
    version_no = Column(Integer, nullable=False, server_default='1', comment='资料版本号')
    owner_id = Column(
        BigInteger, ForeignKey('sys_user.user_id', ondelete='RESTRICT'), nullable=False, comment='所有者ID'
    )
    owner_name = Column(String(64), nullable=False, comment='所有者名称快照')
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PipelineWorkspaceItem(Base):
    """用户对业务资料的收藏或资料篮状态。"""

    __tablename__ = 'user_saved_items'
    __table_args__ = (
        UniqueConstraint('user_id', 'item_type', 'item_id', 'action', name='uk_user_saved_items_target_action'),
        CheckConstraint(
            "item_type IN ('material', 'article', 'paper', 'report')",
            name='ck_user_saved_items_item_type',
        ),
        CheckConstraint("action IN ('favorite', 'basket')", name='ck_user_saved_items_action'),
        Index('idx_user_saved_items_user_action_time', 'user_id', 'action', 'create_time'),
        Index('idx_user_saved_items_target', 'item_type', 'item_id'),
        {'comment': '用户收藏与资料篮表'},
    )

    saved_item_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='收藏记录ID')
    user_id = Column(BigInteger, ForeignKey('sys_user.user_id', ondelete='CASCADE'), nullable=False, comment='用户ID')
    item_id = Column(String(64), nullable=False, comment='业务条目ID')
    item_type = Column(String(32), nullable=False, comment='material、article、paper或report')
    action = Column(String(16), nullable=False, comment='favorite或basket')
    title = Column(String(500), nullable=False, comment='标题快照')
    snapshot = Column(JSON, nullable=False, default=dict, comment='条目快照')
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')


class PipelineResearchJob(Base):
    """科研报告和周期报告生成任务。"""

    __tablename__ = 'generation_tasks'
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name='ck_generation_tasks_status',
        ),
        CheckConstraint('progress BETWEEN 0 AND 100', name='ck_generation_tasks_progress'),
        Index('idx_generation_tasks_user_status_time', 'user_id', 'status', 'update_time'),
        {'comment': '报告生成任务表'},
    )

    task_id = Column(String(64), primary_key=True, nullable=False, comment='生成任务ID')
    user_id = Column(
        BigInteger, ForeignKey('sys_user.user_id', ondelete='RESTRICT'), nullable=False, comment='创建用户ID'
    )
    owner_name = Column(String(64), nullable=False, comment='创建用户名称快照')
    title = Column(String(500), nullable=False, comment='任务名称')
    report_type = Column(String(64), nullable=False, comment='报告类型')
    template_id = Column(String(64), nullable=True, comment='前端或代码内置模板编码快照')
    template_version = Column(String(32), nullable=True, comment='模板版本显示值快照')
    status = Column(String(32), nullable=False, server_default='queued', comment='任务状态')
    current_stage = Column(String(64), nullable=False, server_default='validating', comment='当前阶段')
    progress = Column(Integer, nullable=False, server_default='0', comment='进度')
    config = Column(JSON, nullable=False, default=dict, comment='任务输入和参数快照')
    selected_items = Column(JSON, nullable=False, default=list, comment='任务启动时的资料权威快照')
    outline = Column(JSON, nullable=False, default=list, comment='报告大纲')
    stages = Column(JSON, nullable=False, default=list, comment='阶段状态')
    logs = Column(JSON, nullable=False, default=list, comment='任务日志')
    error_message = Column(Text, nullable=True, comment='错误信息')
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PipelineReport(Base):
    """报告当前可编辑状态。"""

    __tablename__ = 'reports'
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'reviewing', 'completed', 'published', 'archived')",
            name='ck_reports_status',
        ),
        CheckConstraint('version_no >= 1', name='ck_reports_version_no'),
        CheckConstraint('word_count >= 0', name='ck_reports_word_count'),
        Index('idx_reports_user_type_time', 'user_id', 'report_type', 'update_time'),
        Index('idx_reports_user_status_time', 'user_id', 'status', 'update_time'),
        {'comment': '科研报告表'},
    )

    report_id = Column(String(64), primary_key=True, nullable=False, comment='报告ID')
    source_task_id = Column(
        String(64),
        ForeignKey('generation_tasks.task_id', ondelete='SET NULL'),
        nullable=True,
        unique=True,
        comment='来源任务ID；任务与报告关系的唯一权威字段',
    )
    user_id = Column(
        BigInteger, ForeignKey('sys_user.user_id', ondelete='RESTRICT'), nullable=False, comment='所有者ID'
    )
    owner_name = Column(String(64), nullable=False, comment='所有者名称快照')
    title = Column(String(500), nullable=False, comment='报告标题')
    report_type = Column(String(64), nullable=False, comment='报告类型')
    status = Column(String(32), nullable=False, server_default='draft', comment='报告状态')
    version_no = Column(Integer, nullable=False, server_default='1', comment='当前版本')
    content = Column(Text, nullable=False, comment='Markdown正文')
    sections = Column(JSON, nullable=False, default=list, comment='当前结构化章节')
    citations = Column(JSON, nullable=False, default=list, comment='当前版本引用的权威快照')
    quality_issues = Column(JSON, nullable=False, default=list, comment='质量问题')
    metadata_json = Column(JSON, nullable=False, default=dict, comment='报告与图形元数据')
    word_count = Column(Integer, nullable=False, server_default='0', comment='字数')
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PipelineReportVersion(Base):
    """不可变的报告历史版本。"""

    __tablename__ = 'report_versions'
    __table_args__ = (
        UniqueConstraint('report_id', 'version_no', name='uk_report_versions_report_version'),
        CheckConstraint('version_no >= 1', name='ck_report_versions_version_no'),
        CheckConstraint(
            "source IN ('generated', 'retry', 'manual', 'autosave', 'publish', 'restored')",
            name='ck_report_versions_source',
        ),
        Index('idx_report_versions_report_time', 'report_id', 'create_time'),
        {'comment': '报告版本表'},
    )

    report_version_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='主键')
    report_id = Column(
        String(64), ForeignKey('reports.report_id', ondelete='CASCADE'), nullable=False, comment='报告ID'
    )
    version_no = Column(Integer, nullable=False, comment='版本号')
    title = Column(String(500), nullable=False, comment='版本标题')
    content = Column(Text, nullable=False, comment='版本正文')
    sections = Column(JSON, nullable=False, default=list, comment='版本章节')
    citations = Column(JSON, nullable=False, default=list, comment='该版本引用的权威快照')
    quality_issues = Column(JSON, nullable=False, default=list, comment='版本质量问题')
    model_snapshot = Column(JSON, nullable=False, default=dict, comment='模型、Prompt和模板快照')
    source = Column(String(32), nullable=False, server_default='manual', comment='版本来源')
    operator_id = Column(
        BigInteger, ForeignKey('sys_user.user_id', ondelete='SET NULL'), nullable=True, comment='操作用户ID'
    )
    operator_name = Column(String(64), nullable=False, comment='操作用户名称快照')
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')


# 旧类名仅作为导入兼容，不会额外注册表。
PipelineContent = PipelineArticle
