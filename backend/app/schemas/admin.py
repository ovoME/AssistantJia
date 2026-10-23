from typing import List, Optional
from pydantic import BaseModel, Field

class AdminSummary(BaseModel):
    total_borrows: int = Field(default=36908, description="总借阅人次")
    total_readers: int = Field(default=5120, description="持证读者数")
    total_titles: int = Field(default=22318, description="馆藏图书种数")
    avg_borrow_per_reader: float = Field(default=7.2, description="人均借阅册数")

class CategoryStat(BaseModel):
    code: str = Field(..., description="中图分类大类号，如 I, TP, F")
    name: str = Field(..., description="分类名称")
    count: int = Field(..., description="借阅册次")
    ratio: float = Field(..., description="占比，如 0.28")

class BookStat(BaseModel):
    title: str
    author: str
    call_number: str
    borrow_count: int

class PublisherStat(BaseModel):
    publisher: str
    count: int

class PurchaseAdviceRequest(BaseModel):
    focus_category: Optional[str] = None
    target_budget: Optional[float] = None

class BookReviewRequest(BaseModel):
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
