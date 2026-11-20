"""Document classification comments and canonical second precision, without data replay."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '20261120_material_comments'
down_revision = '20261120_material_classification'
branch_labels = None
depends_on = None

# Frozen comments for this revision; future runtime comment edits must not alter it.
COMMENTS = {
    (
        'categories',
        'applies_to',
    ): '适用内容类型：news新闻、paper论文、document上传资料、all全部三者；默认all，不改变历史归类',
    (
        'knowledge_files',
        'category_id',
    ): '资料唯一类别ID，关联categories.id；未分类、未配置或未唯一命中为空；BIGINT数值外键，引用业务表数值主键，API使用十进制字符串',
    (
        'knowledge_files',
        'classification_status',
    ): '资料分类状态：queued待分类、running分类中、completed已完成、failed失败、not_configured未配置；历史资料不自动发起模型调用',
    (
        'knowledge_files',
        'classification_error',
    ): '资料分类失败或未配置的脱敏说明；保留可重试原因，不保存密钥、原文或供应商响应',
    (
        'knowledge_files',
        'classification_token',
    ): '资料分类单次执行的普通不透明随机令牌；UUID不包含业务ID，只用于隔离旧结果回写，不向接口输出',
    (
        'knowledge_files',
        'classification_updated_at',
    ): '资料分类任务最近认领或结束时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；用于识别中断，不触发自动付费重试',
    (
        'knowledge_files',
        'updated_at',
    ): '资料编辑、解析或分类状态最近更新时间；北京时间Asia/Shanghai本地墙钟，timestamp(0)无时区，精度到秒；API/页面格式YYYY-MM-DD HH:mm:ss',
}


def upgrade() -> None:
    op.alter_column(
        'knowledge_files',
        'classification_updated_at',
        type_=postgresql.TIMESTAMP(precision=0, timezone=False),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="date_trunc('second', classification_updated_at)",
    )
    for (table, column), comment in COMMENTS.items():
        op.alter_column(table, column, comment=comment)


def downgrade() -> None:
    raise RuntimeError('Restore the verified backup; classification comments and timestamp precision are preserved.')
