from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class MaterialEditModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    expected_version: int = Field(ge=1)
    edited_text: str | None
    name: str | None = Field(default=None, min_length=1, max_length=255)
