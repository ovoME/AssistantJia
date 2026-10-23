from typing import Optional
from pydantic import BaseModel, Field

class Book(BaseModel):
    title: str = Field(..., description="书名")
    author: str = Field(..., description="责任者/作者")
    isbn: str = Field(..., description="ISBN编号")
    call_number: str = Field(..., description="索书号")
    location: str = Field(..., description="馆藏地与立体架位描述")
    available: int = Field(default=1, description="可借数量")
    status: str = Field(default="在馆", description="状态：在馆 / 借出")

class BorrowRecord(BaseModel):
    book_id: str = Field(..., description="图书条码号/财产号")
    title: str = Field(..., description="题名")
    borrow_date: str = Field(..., description="借阅日期 YYYY-MM-DD")
    due_date: str = Field(..., description="应还日期 YYYY-MM-DD")
    renew_count: int = Field(default=0, description="已续借次数")
    is_overdue: bool = Field(default=False, description="是否已超期")

class RenewRequest(BaseModel):
    reader_id: str = Field(..., description="读者证件号")
    book_id: str = Field(..., description="图书财产号")

class RenewResult(BaseModel):
    new_due_date: str
    renew_count: int

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
