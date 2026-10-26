"""审计日志使用的业务操作类型。"""

from enum import Enum


class BusinessType(Enum):
    """业务操作类型。"""

    OTHER = 0
    INSERT = 1
    UPDATE = 2
    DELETE = 3
    GRANT = 4
    EXPORT = 5
    IMPORT = 6
    FORCE = 7
    GENCODE = 8
    CLEAN = 9
