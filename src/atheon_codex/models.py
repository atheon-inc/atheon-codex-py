from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class AtheonUnitCreateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, Field(min_length=2)]
    base_content: Annotated[str, Field(min_length=10)]
