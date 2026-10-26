"""在线会话监控 API 契约。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class OnlineModel(BaseModel):
    """在线用户会话信息。"""

    model_config = ConfigDict(alias_generator=to_camel)

    token_id: str | None = Field(default=None, description='会话编号')
    user_name: str | None = Field(default=None, description='登录名称')
    ipaddr: str | None = Field(default=None, description='主机')
    login_location: str | None = Field(default=None, description='登录地点')
    browser: str | None = Field(default=None, description='浏览器类型')
    os: str | None = Field(default=None, description='操作系统')
    login_time: datetime | None = Field(default=None, description='登录时间')


class OnlineQueryModel(OnlineModel):
    """在线会话筛选条件。"""

    begin_time: str | None = Field(default=None, description='开始时间')
    end_time: str | None = Field(default=None, description='结束时间')


class OnlinePageResponseModel(BaseModel):
    """在线会话分页响应。"""

    model_config = ConfigDict(alias_generator=to_camel)

    rows: list[OnlineModel] = Field(description='在线用户记录列表')
    total: int = Field(description='总记录数')


class DeleteOnlineModel(BaseModel):
    """强制结束在线会话的请求。"""

    model_config = ConfigDict(alias_generator=to_camel)

    token_ids: str = Field(description='需要强退的会话编号')


__all__ = [
    'DeleteOnlineModel',
    'OnlineModel',
    'OnlinePageResponseModel',
    'OnlineQueryModel',
]
