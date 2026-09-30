from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from module_admin.entity.do.user_do import SysUser


async def login_by_account(db: AsyncSession, user_name: str) -> Row[tuple[SysUser]] | None:
    """
    根据用户名查询用户信息

    :param db: orm对象
    :param user_name: 用户名
    :return: 用户对象
    """
    user = (
        await db.execute(
            select(SysUser).where(SysUser.user_name == user_name, SysUser.del_flag == '0').distinct()
        )
    ).first()

    return user
