"""Canonical collected content: news, paper abstracts, and one category each."""

from datetime import datetime, timezone

from sqlalchemy import (
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
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.business_ids import business_pk
from app.business_time import BeijingAuditTime, audit_now, server_now
from config.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PipelineCategory(Base):
    __tablename__ = 'categories'
    __table_args__ = (
        UniqueConstraint('name', name='uk_categories_name'),
        CheckConstraint("applies_to IN ('news','paper','all')", name='ck_categories_applies_to'),
        CheckConstraint('NOT is_enabled OR model_id IS NOT NULL', name='ck_categories_enabled_model'),
        CheckConstraint('length(trim(name)) > 0 AND length(trim(prompt)) > 0', name='ck_categories_name_prompt'),
        {'comment': '管理员定义的单类别及大模型过滤提示词'},
    )
    id = business_pk(comment='类别ID')
    name = Column(String(100), nullable=False, comment='类别名称')
    prompt = Column(Text, nullable=False, comment='过滤及分类提示词')
    model_id = Column(
        BigInteger, ForeignKey('ai_models.id', ondelete='RESTRICT'), nullable=True, comment='分类文本模型ID'
    )
    applies_to = Column(
        String(16), nullable=False, default='all', server_default='all', comment='适用内容：news/paper/all'
    )
    is_enabled = Column(Boolean, nullable=False, default=True, server_default='true', comment='是否用于新分类')
    sort_order = Column(Integer, nullable=False, default=0, server_default='0', comment='显示顺序')
    created_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        comment='创建时间',
    )
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
        comment='更新时间',
    )


class PipelineArticle(Base):
    __tablename__ = 'news_articles'
    __table_args__ = (
        CheckConstraint('length(trim(title)) > 0 AND length(trim(url)) > 0', name='ck_news_articles_title_url'),
        {'comment': '新闻网站与公众号的文章，不包含人工审核或交接字段'},
    )

    id = business_pk(comment='文章ID')
    source_id = Column(
        BigInteger, ForeignKey('data_sources.id', ondelete='RESTRICT'), nullable=False, comment='来源ID；类型在来源表'
    )
    title = Column(String(1000), nullable=False, comment='原文标题')
    url = Column(Text, nullable=False, comment='规范化原文地址')
    author = Column(Text, nullable=True, comment='原始作者，未知时为空')
    published_at = Column(DateTime(timezone=True), nullable=True, comment='来源原文发布时间，不是平台入库时间')
    content = Column(Text, nullable=True, comment='原文正文')
    content_zh = Column(Text, nullable=True, comment='中文译文，原文已中文则无需重复保存')
    category_id = Column(
        BigInteger,
        ForeignKey('categories.id', ondelete='RESTRICT'),
        nullable=True,
        comment='唯一类别ID；未分类或未命中为空',
    )
    is_pushed = Column(Boolean, nullable=False, default=False, server_default='false', comment='是否已成功推送')
    created_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        comment='平台入库时间',
    )
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
        comment='更新时间',
    )
    source = relationship('PipelineSource', lazy='selectin')
    category = relationship('PipelineCategory', lazy='selectin')


Index('uk_news_articles_url', func.md5(PipelineArticle.url), unique=True)
Index('idx_news_articles_published_at', PipelineArticle.published_at.desc(), PipelineArticle.id)
Index(
    'idx_news_articles_source_id',
    PipelineArticle.source_id,
    PipelineArticle.published_at.desc(),
    PipelineArticle.id,
)
Index(
    'idx_news_articles_category_id',
    PipelineArticle.category_id,
    PipelineArticle.published_at.desc(),
    PipelineArticle.id,
)


class PipelinePaper(Base):
    __tablename__ = 'papers'
    __table_args__ = (
        CheckConstraint('length(trim(title)) > 0', name='ck_papers_title'),
        CheckConstraint(
            "nullif(trim(doi), '') IS NOT NULL OR nullif(trim(url), '') IS NOT NULL", name='ck_papers_source_link'
        ),
        CheckConstraint(
            "published_date IS NULL OR CASE WHEN published_date ~ '^[0-9]{4}(-[0-9]{2}){0,2}$' "
            'THEN make_date(substring(published_date, 1, 4)::integer, '
            "coalesce(nullif(substring(published_date, 6, 2), '')::integer, 1), "
            "coalesce(nullif(substring(published_date, 9, 2), '')::integer, 1)) IS NOT NULL ELSE false END",
            name='ck_papers_published_date',
        ).ddl_if(dialect='postgresql'),
        {'comment': '论文文献信息及中英文摘要，不保存全文'},
    )
    id = business_pk(comment='论文ID')
    source_id = Column(
        BigInteger, ForeignKey('data_sources.id', ondelete='SET NULL'), nullable=True, comment='论文来源ID'
    )
    title = Column(String(1000), nullable=False, comment='原始论文标题')
    title_zh = Column(String(1000), nullable=True, comment='中文论文标题')
    url = Column(Text, nullable=True, comment='论文来源页面，不表示平台拥有全文')
    doi = Column(String(255), nullable=True, comment='不含URL前缀的规范化DOI')
    authors = Column(Text, nullable=True, comment='原始作者名单')
    journal = Column(String(255), nullable=True, comment='期刊或会议名称')
    published_date = Column(String(10), nullable=True, comment='真实发表日期：YYYY或YYYY-MM或YYYY-MM-DD')
    abstract = Column(Text, nullable=True, comment='原文摘要')
    abstract_zh = Column(Text, nullable=True, comment='中文摘要')
    category_id = Column(
        BigInteger, ForeignKey('categories.id', ondelete='RESTRICT'), nullable=True, comment='唯一类别ID'
    )
    is_pushed = Column(Boolean, nullable=False, default=False, server_default='false', comment='是否已成功推送')
    created_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        comment='平台入库时间',
    )
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
        comment='更新时间',
    )
    source = relationship('PipelineSource', lazy='selectin')
    category = relationship('PipelineCategory', lazy='selectin')


Index('uk_papers_doi', PipelinePaper.doi, unique=True, postgresql_where=text('doi IS NOT NULL'))
Index(
    'uk_papers_url', func.md5(PipelinePaper.url), unique=True, postgresql_where=text('doi IS NULL AND url IS NOT NULL')
)
# Match the existing PostgreSQL partial-date ordering expression, not lexical YYYY[-MM[-DD]].
paper_date = func.rpad(PipelinePaper.published_date, 10, '-01')
Index('idx_papers_date', paper_date.desc(), PipelinePaper.id).ddl_if(dialect='postgresql')
Index('idx_papers_category_id', PipelinePaper.category_id, paper_date.desc(), PipelinePaper.id).ddl_if(
    dialect='postgresql'
)
