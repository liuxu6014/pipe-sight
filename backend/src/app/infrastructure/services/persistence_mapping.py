"""Explicit conversion between API DTO fields and application persistence names.

The mapping is declared on each ORM class. It never creates SQL aliases,
synonyms, legacy columns or compatibility views.
"""

from typing import Any

from sqlalchemy import Column


class PersistenceMapping:
    @staticmethod
    def to_record(model: type, values: dict[str, Any]) -> dict[str, Any]:
        """Convert snake-case DTO input; ignore non-persistent DTO extensions."""
        mapping = getattr(model, '__api_field_map__', {})
        columns = model.__table__.columns
        return {mapping.get(key, key): value for key, value in values.items() if mapping.get(key, key) in columns}

    @staticmethod
    def to_api(model: type, values: dict[str, Any]) -> dict[str, Any]:
        """Convert a canonical record to the existing snake-case API contract."""
        reverse = {value: key for key, value in getattr(model, '__api_field_map__', {}).items()}
        return {reverse.get(key, key): value for key, value in values.items()}

    @staticmethod
    def column(model: type, api_field: str) -> Column[Any] | None:
        """Resolve a DTO sort field to a real mapped column, never arbitrary attributes."""
        name = getattr(model, '__api_field_map__', {}).get(api_field, api_field)
        return model.__table__.columns.get(name)
