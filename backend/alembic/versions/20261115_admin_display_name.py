"""Use the administrator display name while preserving custom names and permissions."""

from alembic import op
from sqlalchemy import text

revision = '20261115_admin_display_name'
down_revision = '20261115_template_defaults'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text(
        "UPDATE sys_user SET nickname = '管理员' "
        "WHERE id = 1 AND username = 'admin' AND nickname = '超级管理员'"
    ))
    op.execute(text(
        "UPDATE sys_role SET name = '管理员' "
        "WHERE code = 'admin' AND name = '超级管理员'"
    ))
    op.execute(text(
        "UPDATE sys_role SET remark = '管理员' "
        "WHERE code = 'admin' AND remark = '超级管理员'"
    ))


def downgrade() -> None:
    # Keep display names chosen after the upgrade; restore the recorded backup if needed.
    pass
