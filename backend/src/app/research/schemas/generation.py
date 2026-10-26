from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApplyGenerationResultModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    expected_version: int = Field(ge=1)
