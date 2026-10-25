from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: Optional[T] = None
    dataset_label: Optional[str] = None
    scope: Optional[str] = None
    is_live: Optional[bool] = None
    built_at: Optional[str] = None
    limitations: list[str] = []

    @classmethod
    def ok(cls, data: Optional[T] = None, message: str = "success", **metadata) -> "ApiResponse[T]":
        return cls(code=0, message=message, data=data, **metadata)

    @classmethod
    def fail(cls, code: int = 4000, message: str = "error") -> "ApiResponse[T]":
        return cls(code=code, message=message, data=None)
