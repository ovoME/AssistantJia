from typing import List, Optional
from pydantic import BaseModel, Field

class AdminSummary(BaseModel):
    total_borrows: int = Field(..., description="历史样本借阅流水数")
    total_readers: int = Field(..., description="历史样本不同读者数")
    total_titles: int = Field(..., description="历史样本规范化题名数")
    avg_borrow_per_reader: Optional[float] = None
    dataset_label: str = "unknown"
    scope: str = "historical_borrow_records"
    is_live: bool = False

class CategoryStat(BaseModel):
    category: str = Field(..., description="中图分类大类号，如 I, TP, F")
    category_name: str = Field(..., description="分类名称")
    count: int = Field(..., description="借阅册次")
    share: float = Field(..., description="占比，如 0.28")

class BookStat(BaseModel):
    title: str = Field(..., description="书名")
    author: Optional[str] = Field(None, description="作者")
    count: int = Field(..., description="借阅册次")
    call_number: Optional[str] = Field(None, description="索书号")
    category: Optional[str] = Field(None, description="中图分类大类号，如 I, TP, F")

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


class DataFileInfo(BaseModel):
    id: str
    filename: str
    kind: str = "other"  # borrow | catalog | gate | seat | room | other
    rows: Optional[int] = None
    size_kb: int = 0
    status: str = "ready"  # ready | processing | error
    uploaded_at: str
    message: Optional[str] = None
