from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_validation_decorator import Network

from exceptions.exception import ServiceException


class DeptModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)

    dept_id: int | None = Field(default=None, gt=0)
    parent_id: int | None = Field(default=None, ge=0)
    ancestors: str | None = Field(default=None, max_length=500)
    dept_name: str | None = Field(default=None, max_length=30)
    order_num: int | None = Field(default=None, ge=0)
    leader: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=11)
    email: str | None = Field(default=None, max_length=50)
    status: Literal['0', '1'] | None = None
    del_flag: Literal['0', '2'] | None = None
    create_by: str | None = None
    create_time: datetime | None = None
    update_by: str | None = None
    update_time: datetime | None = None

    @Network(field_name='email', field_type='EmailStr', message='邮箱格式不正确')
    def get_email(self) -> str | None:
        return self.email

    def validate_fields(self) -> None:
        if not self.dept_name or not self.dept_name.strip():
            raise ServiceException(message='部门名称不能为空')
        if self.order_num is None:
            raise ServiceException(message='显示顺序不能为空')
        if self.parent_id is None:
            raise ServiceException(message='上级部门不能为空')
        self.get_email()


class DeptQueryModel(DeptModel):
    begin_time: str | None = None
    end_time: str | None = None


class DeptTreeModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: int
    label: str
    parent_id: int
    children: list['DeptTreeModel'] | None = None


class DeleteDeptModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    dept_ids: str
    update_by: str | None = None
    update_time: datetime | None = None
