from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.system.models.dept import SysDept
from app.system.repositories.depts import DeptDao
from app.system.schemas.dept import DeleteDeptModel, DeptModel, DeptTreeModel
from common.http.schemas import CrudResponseModel
from exceptions.exception import ServiceException, ServiceWarning


class DeptService:
    """Native department behavior with explicit all/self scope on public operations.

    Departments have no user owner. Pass DataScopeDependency(SysDept, user_alias=None):
    all/admin can manage the tree; self cannot read or mutate organization data.
    No role-department custom scope or implicit unrestricted fallback is supported.
    """

    @classmethod
    async def get_dept_list_services(
        cls,
        query_db: AsyncSession,
        page_object: DeptModel,
        data_scope_sql: ColumnElement,
    ) -> list[dict[str, Any]]:
        rows = await DeptDao.get_dept_list(query_db, page_object, data_scope_sql)
        return [DeptModel.model_validate(row).model_dump(by_alias=True) for row in rows]

    @classmethod
    async def get_dept_tree_services(
        cls,
        query_db: AsyncSession,
        page_object: DeptModel,
        data_scope_sql: ColumnElement,
    ) -> list[dict[str, Any]]:
        rows = await DeptDao.get_dept_list_for_tree(query_db, page_object, data_scope_sql)
        return [node.model_dump(by_alias=True, exclude_none=True) for node in cls.list_to_tree(rows)]

    @classmethod
    async def get_dept_for_edit_option_services(
        cls,
        query_db: AsyncSession,
        page_object: DeptModel,
        data_scope_sql: ColumnElement,
    ) -> list[dict[str, Any]]:
        rows = await DeptDao.get_dept_info_for_edit_option(query_db, page_object, data_scope_sql)
        return [DeptModel.model_validate(row).model_dump(by_alias=True) for row in rows]

    @classmethod
    async def check_dept_data_scope_services(
        cls,
        query_db: AsyncSession,
        dept_id: int,
        data_scope_sql: ColumnElement,
    ) -> CrudResponseModel:
        if not await DeptDao.get_dept_list(query_db, DeptModel(deptId=dept_id), data_scope_sql):
            raise ServiceException(message='部门不存在或没有权限访问部门数据')
        return CrudResponseModel(is_success=True, message='校验通过')

    @classmethod
    async def _check_management_scope(cls, query_db: AsyncSession, data_scope_sql: ColumnElement) -> None:
        # This receives the existing all/self boolean predicate, including for an empty tree.
        if not (await query_db.execute(select(literal(1)).where(data_scope_sql))).scalar():
            raise ServiceException(message='没有权限访问部门数据')

    @classmethod
    async def check_dept_name_unique_services(cls, query_db: AsyncSession, page_object: DeptModel) -> bool:
        dept = await DeptDao.get_dept_detail_by_info(query_db, page_object)
        return dept is None or dept.dept_id == page_object.dept_id

    @classmethod
    async def _parent_chain(cls, query_db: AsyncSession, parent_id: int, dept_id: int | None) -> list[SysDept]:
        chain = []
        seen = {dept_id}
        while parent_id:
            if parent_id in seen:
                raise ServiceException(message='上级部门不能是自己或子部门，部门层级不能循环')
            seen.add(parent_id)
            parent = await DeptDao.get_dept_by_id(query_db, parent_id)
            if parent is None:
                raise ServiceException(message='上级部门不存在或已删除')
            chain.append(parent)
            parent_id = parent.parent_id
        return list(reversed(chain))

    @staticmethod
    def _ancestors(chain: list[SysDept]) -> str:
        ancestors = ','.join(['0', *(str(dept.dept_id) for dept in chain)])
        if len(ancestors) > SysDept.__table__.c.ancestors.type.length:
            raise ServiceException(message='部门层级过深，祖级列表超过字段长度')
        return ancestors

    @classmethod
    async def add_dept_services(
        cls,
        query_db: AsyncSession,
        page_object: DeptModel,
        data_scope_sql: ColumnElement,
    ) -> CrudResponseModel:
        try:
            await cls._check_management_scope(query_db, data_scope_sql)
            page_object.validate_fields()
            await DeptDao.lock_depts(query_db)
            # IDs, ancestors and deletion flags are server-owned.
            dept = page_object.model_copy(update={'dept_id': None, 'del_flag': '0'})
            dept.dept_name = dept.dept_name.strip()
            dept.status = dept.status or '0'
            chain = await cls._parent_chain(query_db, dept.parent_id, None)
            if any(parent.status != '0' for parent in chain):
                raise ServiceException(message='上级部门停用，不允许新增')
            dept.ancestors = cls._ancestors(chain)
            if not await cls.check_dept_name_unique_services(query_db, dept):
                raise ServiceException(message='新增失败，同一上级部门下部门名称已存在')
            await DeptDao.add_dept_dao(query_db, dept)
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def edit_dept_services(
        cls,
        query_db: AsyncSession,
        page_object: DeptModel,
        data_scope_sql: ColumnElement,
    ) -> CrudResponseModel:
        try:
            await cls._check_management_scope(query_db, data_scope_sql)
            if page_object.dept_id is None:
                raise ServiceException(message='部门id不能为空')
            await DeptDao.lock_depts(query_db)
            await cls.check_dept_data_scope_services(query_db, page_object.dept_id, data_scope_sql)
            old = await DeptDao.get_dept_by_id(query_db, page_object.dept_id)
            values = page_object.model_dump(
                exclude_unset=True,
                exclude={
                    'ancestors',
                    'del_flag',
                    'create_by',
                    'create_time',
                },
            )
            dept = DeptModel.model_validate(old).model_copy(update=values)
            dept.validate_fields()
            if dept.status is None:
                raise ServiceException(message='部门状态不能为空')
            dept.dept_name = dept.dept_name.strip()
            chain = await cls._parent_chain(query_db, dept.parent_id, dept.dept_id)
            if not await cls.check_dept_name_unique_services(query_db, dept):
                raise ServiceException(message='修改失败，同一上级部门下部门名称已存在')
            if dept.status == '1' and await DeptDao.count_normal_children_dept_dao(query_db, dept.dept_id):
                raise ServiceException(message='该部门包含未停用的子部门')
            # Native enable behavior promotes ancestors; an ordinary move must not silently enable a parent.
            enabling = page_object.status == '0'
            if dept.parent_id != old.parent_id and any(parent.status != '0' for parent in chain) and not enabling:
                raise ServiceException(message='上级部门停用，不允许调整到该部门')
            ancestors = cls._ancestors(chain)
            if old.ancestors != ancestors:
                await cls.update_dept_children(query_db, dept.dept_id, ancestors, old.ancestors)
            values.update(dept_name=dept.dept_name, ancestors=ancestors)
            await DeptDao.edit_dept_dao(query_db, values)
            if enabling:
                await DeptDao.update_dept_status_normal_dao(query_db, [parent.dept_id for parent in chain])
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='更新成功')
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def delete_dept_services(
        cls,
        query_db: AsyncSession,
        page_object: DeleteDeptModel,
        data_scope_sql: ColumnElement,
    ) -> CrudResponseModel:
        try:
            await cls._check_management_scope(query_db, data_scope_sql)
            parts = page_object.dept_ids.split(',')
            if not parts or any(not part.isascii() or not part.isdecimal() or int(part) <= 0 for part in parts):
                raise ServiceException(message='部门id必须是逗号分隔的正整数')
            dept_ids = list(dict.fromkeys(map(int, parts)))
            await DeptDao.lock_depts(query_db)
            # Validate the entire batch before deleting, independent of ID order.
            for dept_id in dept_ids:
                await cls.check_dept_data_scope_services(query_db, dept_id, data_scope_sql)
                if await DeptDao.count_children_dept_dao(query_db, dept_id):
                    raise ServiceWarning(message='存在下级部门，不允许删除')
                if await DeptDao.count_dept_user_dao(query_db, dept_id):
                    raise ServiceWarning(message='部门存在用户，不允许删除')
            for dept_id in dept_ids:
                await DeptDao.delete_dept_dao(
                    query_db,
                    DeptModel(
                        deptId=dept_id,
                        updateBy=page_object.update_by,
                        updateTime=page_object.update_time,
                    ),
                )
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def dept_detail_services(
        cls,
        query_db: AsyncSession,
        dept_id: int,
        data_scope_sql: ColumnElement,
    ) -> DeptModel:
        await cls.check_dept_data_scope_services(query_db, dept_id, data_scope_sql)
        return DeptModel.model_validate(await DeptDao.get_dept_by_id(query_db, dept_id))

    @classmethod
    def list_to_tree(cls, departments: Sequence[SysDept]) -> list[DeptTreeModel]:
        mapping = {
            dept.dept_id: DeptTreeModel(
                id=dept.dept_id,
                label=dept.dept_name,
                parentId=dept.parent_id,
            )
            for dept in departments
        }
        roots = []
        for node in mapping.values():
            seen = {node.id}
            parent = mapping.get(node.parent_id)
            while parent is not None:
                if parent.id in seen:
                    raise ServiceException(message='部门层级存在循环，请修复部门数据')
                seen.add(parent.id)
                parent = mapping.get(parent.parent_id)
            parent = mapping.get(node.parent_id)
            if parent is None:
                roots.append(node)
            else:
                if parent.children is None:
                    parent.children = []
                parent.children.append(node)
        return roots

    @classmethod
    async def update_dept_children(
        cls,
        query_db: AsyncSession,
        dept_id: int,
        new_ancestors: str,
        old_ancestors: str,
    ) -> None:
        children = await DeptDao.get_children_dept_dao(query_db, dept_id)
        old_prefix = f'{old_ancestors},{dept_id}'
        new_prefix = f'{new_ancestors},{dept_id}'
        updates = []
        for child in children:
            if child.ancestors != old_prefix and not child.ancestors.startswith(old_prefix + ','):
                raise ServiceException(message='子部门祖级列表不一致，请先修复部门数据')
            ancestors = new_prefix + child.ancestors[len(old_prefix) :]
            if len(ancestors) > SysDept.__table__.c.ancestors.type.length:
                raise ServiceException(message='子部门层级过深，祖级列表超过字段长度')
            updates.append({'dept_id': child.dept_id, 'ancestors': ancestors})
        await DeptDao.update_dept_children_dao(query_db, updates)
