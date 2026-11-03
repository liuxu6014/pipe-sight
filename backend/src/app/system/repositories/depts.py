from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.services.persistence_mapping import PersistenceMapping
from app.system.models.dept import SysDept
from app.system.models.user import SysUser
from app.system.schemas.dept import DeptModel
from exceptions.exception import ServiceException


class DeptDao:
    @staticmethod
    def descendant_clause(dept_id: int) -> ColumnElement:
        # Delimiter matching works on PostgreSQL and SQLite and never confuses 1 with 11.
        return (',' + SysDept.ancestors + ',').like(f'%,{int(dept_id)},%')

    @classmethod
    async def lock_depts(cls, db: AsyncSession) -> None:
        # Serialize tree changes in a stable order, including inserts under existing parents.
        await db.execute(select(SysDept.dept_id).order_by(SysDept.dept_id).with_for_update())

    @classmethod
    async def get_dept_by_id(cls, db: AsyncSession, dept_id: int) -> SysDept | None:
        return (
            (
                await db.execute(
                    select(SysDept).where(
                        SysDept.dept_id == dept_id,
                        SysDept.del_flag == '0',
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_dept_detail_by_id(cls, db: AsyncSession, dept_id: int) -> SysDept | None:
        return await cls.get_dept_by_id(db, dept_id)

    @classmethod
    async def get_dept_detail_by_info(cls, db: AsyncSession, dept: DeptModel) -> SysDept | None:
        return (
            (
                await db.execute(
                    select(SysDept).where(
                        SysDept.parent_id == dept.parent_id,
                        SysDept.dept_name == dept.dept_name,
                        SysDept.del_flag == '0',
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_dept_list(
        cls,
        db: AsyncSession,
        page_object: DeptModel,
        data_scope_sql: ColumnElement,
    ) -> Sequence[SysDept]:
        return (
            (
                await db.execute(
                    select(SysDept)
                    .where(
                        SysDept.del_flag == '0',
                        data_scope_sql,
                        SysDept.dept_id == page_object.dept_id if page_object.dept_id is not None else True,
                        SysDept.parent_id == page_object.parent_id if page_object.parent_id is not None else True,
                        SysDept.status == page_object.status if page_object.status is not None else True,
                        SysDept.dept_name.like(f'%{page_object.dept_name}%') if page_object.dept_name else True,
                    )
                    .order_by(SysDept.order_num, SysDept.dept_id)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_dept_list_for_tree(
        cls,
        db: AsyncSession,
        page_object: DeptModel,
        data_scope_sql: ColumnElement,
    ) -> Sequence[SysDept]:
        return await cls.get_dept_list(db, page_object.model_copy(update={'status': '0'}), data_scope_sql)

    @classmethod
    async def get_dept_info_for_edit_option(
        cls,
        db: AsyncSession,
        dept: DeptModel,
        data_scope_sql: ColumnElement,
    ) -> Sequence[SysDept]:
        return (
            (
                await db.execute(
                    select(SysDept)
                    .where(
                        SysDept.del_flag == '0',
                        SysDept.status == '0',
                        data_scope_sql,
                        SysDept.dept_id != dept.dept_id,
                        ~cls.descendant_clause(dept.dept_id),
                    )
                    .order_by(SysDept.order_num, SysDept.dept_id)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_children_dept_dao(cls, db: AsyncSession, dept_id: int) -> Sequence[SysDept]:
        return (
            (
                await db.execute(
                    select(SysDept).where(
                        SysDept.del_flag == '0',
                        cls.descendant_clause(dept_id),
                    )
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def count_children_dept_dao(cls, db: AsyncSession, dept_id: int) -> int:
        return (
            await db.execute(
                select(func.count())
                .select_from(SysDept)
                .where(
                    SysDept.del_flag == '0',
                    SysDept.parent_id == dept_id,
                )
            )
        ).scalar_one()

    @classmethod
    async def count_normal_children_dept_dao(cls, db: AsyncSession, dept_id: int) -> int:
        return (
            await db.execute(
                select(func.count())
                .select_from(SysDept)
                .where(
                    SysDept.del_flag == '0',
                    SysDept.status == '0',
                    cls.descendant_clause(dept_id),
                )
            )
        ).scalar_one()

    @classmethod
    async def count_dept_user_dao(cls, db: AsyncSession, dept_id: int) -> int:
        user_dept = PersistenceMapping.column(SysUser, 'dept_id')
        if user_dept is None:
            # Fail closed until the separately owned user-model integration is installed.
            raise ServiceException(message='用户部门字段尚未接入，无法安全删除部门')
        return (
            await db.execute(
                select(func.count())
                .select_from(SysUser)
                .where(
                    user_dept == dept_id,
                    SysUser.del_flag == '0',
                )
            )
        ).scalar_one()

    @classmethod
    async def add_dept_dao(cls, db: AsyncSession, dept: DeptModel) -> SysDept:
        record = SysDept(**PersistenceMapping.to_record(SysDept, dept.model_dump(exclude_none=True)))
        db.add(record)
        await db.flush()
        return record

    @classmethod
    async def edit_dept_dao(cls, db: AsyncSession, dept: dict) -> None:
        values = PersistenceMapping.to_record(SysDept, dept)
        dept_id = values.pop('dept_id')
        await db.execute(update(SysDept).where(SysDept.dept_id == dept_id).values(**values))

    @classmethod
    async def update_dept_children_dao(cls, db: AsyncSession, children: list[dict]) -> None:
        for child in children:
            await cls.edit_dept_dao(db, child)

    @classmethod
    async def update_dept_status_normal_dao(cls, db: AsyncSession, dept_ids: list[int]) -> None:
        await db.execute(
            update(SysDept)
            .where(
                SysDept.dept_id.in_(dept_ids),
                SysDept.del_flag == '0',
            )
            .values(status='0')
        )

    @classmethod
    async def delete_dept_dao(cls, db: AsyncSession, dept: DeptModel) -> None:
        await cls.edit_dept_dao(
            db,
            {
                'dept_id': dept.dept_id,
                'del_flag': '2',
                'update_by': dept.update_by,
                'update_time': dept.update_time,
            },
        )
