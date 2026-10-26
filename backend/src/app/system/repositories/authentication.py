"""Authentication persistence queries owned by the system bounded context."""

from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.system.models.user import SysUser


async def login_by_account(db: AsyncSession, user_name: str) -> Row[tuple[SysUser]] | None:
    """根据账号查询可登录用户。"""
    user = (
        await db.execute(select(SysUser).where(SysUser.username == user_name, SysUser.del_flag == '0').distinct())
    ).first()
    return user
