import hashlib
from enum import StrEnum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict


def _generate_hash(text: str | None) -> str:
    normalized = (text or "").strip().lower()
    encoded = normalized.encode("utf-8")
    hash_bytes = hashlib.sha256(encoded).digest()
    return hash_bytes.hex()


# TODO: Remove this when minimum supported version becomes >=3.12
T = TypeVar("T", bound=Any)
E = TypeVar("E", bound=Any)


class ResultStatusEnum(StrEnum):
    OK = "ok"
    ERR = "err"


# TODO: Replace class definition to 'class Ok[T](BaseModel):' when minimum supported version becomes >=3.12
class Ok(BaseModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: Literal[ResultStatusEnum.OK] = ResultStatusEnum.OK
    value: T


# TODO: Replace class definition to 'class Err[E](BaseModel):' when minimum supported version becomes >=3.12
class Err(BaseModel, Generic[E]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: Literal[ResultStatusEnum.ERR] = ResultStatusEnum.ERR
    error: E


# Discriminated union
# TODO: Replace type definition to 'type Result[T, E] = Ok[T] | Err[E]' when minimum supported version becomes >=3.12
Result = Ok[T] | Err[E]
