from typing import Optional
from pydantic import BaseModel, Field

class Book(BaseModel):
    title: str = Field(..., description="书名")
    author: str = Field(..., description="责任者/作者")
    isbn: str = Field(..., description="ISBN编号")
    call_number: str = Field(..., description="索书号")
    location: Optional[str] = None
    available: Optional[int] = None
    status: str = "unknown"
    book_key: Optional[str] = None
    publisher: str = ""
    is_live: bool = False
    dataset_label: Optional[str] = None
    holdings_snapshot: Optional[dict] = None
    reason: Optional[str] = None
    reservation_supported: bool = False

class BorrowRecord(BaseModel):
    book_id: str = Field(..., description="图书条码号/财产号")
    title: str = Field(..., description="题名")
    borrow_date: str = Field(..., description="借阅日期 YYYY-MM-DD")
    due_date: str = Field(..., description="应还日期 YYYY-MM-DD")
    renew_count: int = Field(default=0, description="已续借次数")
    is_overdue: bool = Field(default=False, description="是否已超期")
    can_renew: bool = False
    dataset_label: str = "unknown"
    is_live: bool = False

class RenewRequest(BaseModel):
    reader_id: str = Field(..., description="读者证件号")
    book_id: str = Field(..., description="图书财产号")

class RenewResult(BaseModel):
    new_due_date: str
    renew_count: int
    can_renew: bool = False

class ReserveRequest(BaseModel):
    reader_id: str = Field(..., description="读者证件号")
    isbn: str = Field(..., description="ISBN")

class ReserveResult(BaseModel):
    queue_position: int = Field(default=1, description="排队位置")
    notify_channel: str = Field(default="站内消息", description="通知渠道")

class RecommendBook(BaseModel):
    title: str
    author: str
    isbn: str
    call_number: str
    reason: str
    book_key: str
    publisher: str = ""
    category: str = "UNKNOWN"
    count: int = 0
    score: float = 0
    strategy: str = "popular"
