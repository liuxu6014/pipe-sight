"""HTTP 相关枚举。"""

from enum import Enum


class HttpMethod(str, Enum):
    """HTTP 请求方法。"""

    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'
    PATCH = 'PATCH'
    HEAD = 'HEAD'
    OPTIONS = 'OPTIONS'
    TRACE = 'TRACE'
    CONNECT = 'CONNECT'
