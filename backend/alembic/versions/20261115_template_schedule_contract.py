"""Explicit digest cadence and bounded schedule retries."""

import sqlalchemy as sa
from alembic import op

revision = '20261115_template_schedule_contract'
down_revision = '20261115_admin_display_name'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'templates',
        sa.Column(
            'digest_cadence',
            sa.String(16),
            nullable=True,
            comment='简报适用周期：weekly周报、monthly月报、all通用；daily仅兼容历史，与名称无关',
        ),
    )
    # A one-time compatibility conversion; subsequent edits never infer cadence from names.
    templates = sa.table(
        'templates', sa.column('purpose'), sa.column('name'), sa.column('preset_key'), sa.column('digest_cadence')
    )
    op.execute(templates.update().where(templates.c.purpose == 'digest').values(digest_cadence='all'))
    for label, cadence in (('日报', 'daily'), ('周报', 'weekly'), ('月报', 'monthly')):
        names = [f'{prefix}{label}{suffix}' for prefix in ('', '科技情报', '管网科技情报') for suffix in ('', '模板')]
        if cadence == 'weekly':
            names.append('检测技术专题周报')
        op.execute(
            templates.update()
            .where(templates.c.purpose == 'digest', templates.c.name.in_(names))
            .values(digest_cadence=cadence)
        )
    for preset, cadence in (('digest-v1-weekly', 'weekly'), ('digest-v1-monthly', 'monthly')):
        op.execute(
            templates.update()
            .where(templates.c.purpose == 'digest', templates.c.preset_key == preset)
            .values(digest_cadence=cadence)
        )
    op.create_check_constraint(
        'ck_templates_digest_cadence',
        'templates',
        "digest_cadence IS NULL OR (purpose='digest' AND digest_cadence IN ('weekly','monthly','all','daily'))",
    )
    op.add_column(
        'digest_schedules',
        sa.Column(
            'next_retry_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='瞬时派发失败后的最早重试时间，不推进原业务周期',
        ),
    )
    op.add_column(
        'digest_schedules',
        sa.Column(
            'retry_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='当前业务周期连续派发失败次数；成功或手动恢复后清零',
        ),
    )


def downgrade() -> None:
    raise RuntimeError('Restore the verified backup; downgrade would discard explicit cadence and retry state.')
