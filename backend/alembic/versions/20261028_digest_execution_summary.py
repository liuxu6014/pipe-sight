"""Add nullable dispatch summary; never fabricate or backfill historical state."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = '20261028_digest_execution_summary'
down_revision = '20261025_beijing_audit_time'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('digest_schedules', sa.Column('last_run_at', TIMESTAMP(precision=0, timezone=False), nullable=True, comment='最近派发检查时间；北京时间Asia/Shanghai，timestamp(0)无时区，精度到秒，YYYY-MM-DD HH:mm:ss；历史为空不回填'))
    op.add_column('digest_schedules', sa.Column('last_status', sa.String(16), nullable=True, comment='最近派发结果：queued入队、no_data无匹配、skipped节假日跳过、failed失败；历史为空；生成进度读取关联任务'))
    op.add_column('digest_schedules', sa.Column('last_error', sa.Text(), nullable=True, comment='最近派发失败原因，脱敏后保存；成功或跳过时清空，不包含模型密钥或内部堆栈'))
    op.create_check_constraint('ck_digest_schedules_last_status', 'digest_schedules', "last_status IS NULL OR last_status IN ('queued','no_data','skipped','failed')")
    op.create_index('idx_generation_tasks_schedule_id', 'generation_tasks', ['schedule_id','id'])


def downgrade():
    raise RuntimeError('Restore the verified backup; downgrading would discard execution summaries.')
