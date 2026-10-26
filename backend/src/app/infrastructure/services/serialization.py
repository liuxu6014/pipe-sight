import re
from collections.abc import Sequence
from typing import Any, Literal, overload

from sqlalchemy.engine.row import Row
from sqlalchemy.orm.collections import InstrumentedList
from sqlalchemy.sql.expression import TextClause, null

from app.infrastructure.services.persistence_mapping import PersistenceMapping
from config.database import Base


class SqlalchemyUtil:
    """
    sqlalchemy工具类
    """

    @classmethod
    def base_to_dict(
        cls, obj: Base | dict, transform_case: Literal['no_case', 'snake_to_camel', 'camel_to_snake'] = 'no_case'
    ) -> dict:
        """
        将sqlalchemy模型对象转换为字典

        :param obj: sqlalchemy模型对象或普通字典
        :param transform_case: 转换得到的结果形式，可选的有'no_case'(不转换)、'snake_to_camel'(下划线转小驼峰)、'camel_to_snake'(小驼峰转下划线)，默认为'no_case'
        :return: 字典结果
        """
        if isinstance(obj, Base):
            base_dict = obj.__dict__.copy()
            base_dict.pop('_sa_instance_state', None)
            if transform_case == 'snake_to_camel':
                base_dict = PersistenceMapping.to_api(type(obj), base_dict)
            for name, value in base_dict.items():
                if isinstance(value, InstrumentedList):
                    base_dict[name] = cls.serialize_result(value, 'snake_to_camel')
        elif isinstance(obj, dict):
            base_dict = obj.copy()
        if transform_case == 'snake_to_camel':
            return {CamelCaseUtil.snake_to_camel(k): v for k, v in base_dict.items()}
        if transform_case == 'camel_to_snake':
            return {SnakeCaseUtil.camel_to_snake(k): v for k, v in base_dict.items()}

        return base_dict

    @classmethod
    @overload
    def serialize_result(
        cls, result: Base, transform_case: Literal['no_case', 'snake_to_camel', 'camel_to_snake'] = 'no_case'
    ) -> dict[str, Any]: ...

    @classmethod
    @overload
    def serialize_result(
        cls, result: dict, transform_case: Literal['no_case', 'snake_to_camel', 'camel_to_snake'] = 'no_case'
    ) -> dict[Any, Any]: ...

    @classmethod
    @overload
    def serialize_result(
        cls, result: Row, transform_case: Literal['no_case', 'snake_to_camel', 'camel_to_snake'] = 'no_case'
    ) -> dict[str, Any] | list[dict[Any, Any]]: ...

    @classmethod
    @overload
    def serialize_result(
        cls, result: Sequence[Base], transform_case: Literal['no_case', 'snake_to_camel', 'camel_to_snake'] = 'no_case'
    ) -> list[dict[str, Any]]: ...

    @classmethod
    @overload
    def serialize_result(
        cls, result: Sequence[dict], transform_case: Literal['no_case', 'snake_to_camel', 'camel_to_snake'] = 'no_case'
    ) -> list[dict[Any, Any]]: ...

    @classmethod
    @overload
    def serialize_result(
        cls, result: Sequence[Row], transform_case: Literal['no_case', 'snake_to_camel', 'camel_to_snake'] = 'no_case'
    ) -> list[dict[str, Any] | list[dict[Any, Any]]]: ...

    @classmethod
    @overload
    def serialize_result(
        cls, result: Sequence[Any], transform_case: Literal['no_case', 'snake_to_camel', 'camel_to_snake'] = 'no_case'
    ) -> list[Any]: ...

    @classmethod
    @overload
    def serialize_result(
        cls, result: Any, transform_case: Literal['no_case', 'snake_to_camel', 'camel_to_snake'] = 'no_case'
    ) -> Any: ...

    @classmethod
    def serialize_result(
        cls, result: Any, transform_case: Literal['no_case', 'snake_to_camel', 'camel_to_snake'] = 'no_case'
    ) -> Any:
        """
        将sqlalchemy查询结果序列化

        :param result: sqlalchemy查询结果
        :param transform_case: 转换得到的结果形式，可选的有'no_case'(不转换)、'snake_to_camel'(下划线转小驼峰)、'camel_to_snake'(小驼峰转下划线)，默认为'no_case'
        :return: 序列化结果
        """
        if isinstance(result, (Base, dict)):
            return cls.base_to_dict(result, transform_case)
        if isinstance(result, list):
            return [cls.serialize_result(row, transform_case) for row in result]
        if isinstance(result, Row):
            if all(isinstance(row, Base) for row in result):
                return [cls.base_to_dict(row, transform_case) for row in result]
            if any(isinstance(row, Base) for row in result):
                return [cls.serialize_result(row, transform_case) for row in result]
            result_dict = result._asdict()
            if transform_case == 'snake_to_camel':
                return {CamelCaseUtil.snake_to_camel(k): v for k, v in result_dict.items()}
            if transform_case == 'camel_to_snake':
                return {SnakeCaseUtil.camel_to_snake(k): v for k, v in result_dict.items()}
            return result_dict
        return result

    @classmethod
    def get_server_default_null(cls, dialect_name: str, need_explicit_null: bool = True) -> TextClause | None:
        """
        根据数据库方言动态返回值为null的server_default

        :param dialect_name: 数据库方言名称
        :param need_explicit_null: 是否需要显式DEFAULT NULL
        :return: 不同数据库方言对应的null_server_default
        """
        if need_explicit_null and dialect_name == 'postgresql':
            return null()
        return None


class CamelCaseUtil:
    """
    下划线形式(snake_case)转小驼峰形式(camelCase)工具方法
    """

    @classmethod
    def snake_to_camel(cls, snake_str: str) -> str:
        """
        下划线形式字符串(snake_case)转换为小驼峰形式字符串(camelCase)

        :param snake_str: 下划线形式字符串
        :return: 小驼峰形式字符串
        """
        # 分割字符串
        words = snake_str.split('_')
        # 小驼峰命名，第一个词首字母小写，其余词首字母大写
        return words[0] + ''.join(word.capitalize() for word in words[1:])

    @classmethod
    @overload
    def transform_result(cls, result: Base) -> dict[str, Any]: ...

    @classmethod
    @overload
    def transform_result(cls, result: dict) -> dict[Any, Any]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Row) -> dict[str, Any] | list[dict[Any, Any]]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Sequence[Base]) -> list[dict[str, Any]]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Sequence[dict]) -> list[dict[Any, Any]]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Sequence[Row]) -> list[dict[str, Any] | list[dict[Any, Any]]]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Sequence[Any]) -> list[Any]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Any) -> Any: ...

    @classmethod
    def transform_result(cls, result: Any) -> Any:
        """
        针对不同类型将下划线形式(snake_case)批量转换为小驼峰形式(camelCase)方法

        :param result: 输入数据
        :return: 小驼峰形式结果
        """
        return SqlalchemyUtil.serialize_result(result=result, transform_case='snake_to_camel')


class SnakeCaseUtil:
    """
    小驼峰形式(camelCase)转下划线形式(snake_case)工具方法
    """

    @classmethod
    def camel_to_snake(cls, camel_str: str) -> str:
        """
        小驼峰形式字符串(camelCase)转换为下划线形式字符串(snake_case)

        :param camel_str: 小驼峰形式字符串
        :return: 下划线形式字符串
        """
        # 在大写字母前添加一个下划线，然后将整个字符串转为小写
        words = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', words).lower()

    @classmethod
    @overload
    def transform_result(cls, result: Base) -> dict[str, Any]: ...

    @classmethod
    @overload
    def transform_result(cls, result: dict) -> dict[Any, Any]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Row) -> dict[str, Any] | list[dict[Any, Any]]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Sequence[Base]) -> list[dict[str, Any]]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Sequence[dict]) -> list[dict[Any, Any]]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Sequence[Row]) -> list[dict[str, Any] | list[dict[Any, Any]]]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Sequence[Any]) -> list[Any]: ...

    @classmethod
    @overload
    def transform_result(cls, result: Any) -> Any: ...

    @classmethod
    def transform_result(cls, result: Any) -> Any:
        """
        针对不同类型将小驼峰形式(camelCase)批量转换为下划线形式(snake_case)方法

        :param result: 输入数据
        :return: 下划线形式结果
        """
        return SqlalchemyUtil.serialize_result(result=result, transform_case='camel_to_snake')
