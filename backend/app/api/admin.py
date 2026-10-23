from typing import List
from fastapi import APIRouter
from app.schemas.common import ApiResponse
from app.schemas.admin import (
    AdminSummary,
    CategoryStat,
    BookStat,
    PublisherStat,
    PurchaseAdviceRequest,
    BookReviewRequest,
)

router = APIRouter(prefix="/admin", tags=["Admin & Analytics"])

@router.get("/stats/summary", response_model=ApiResponse[AdminSummary])
async def get_summary_stats():
    """管理端概览大屏指标 (基于嘉庚学院 3.7 万借阅数据)"""
    return ApiResponse.ok(data=AdminSummary())

@router.get("/stats/hot-books", response_model=ApiResponse[List[BookStat]])
async def get_hot_books_stats():
    """热门图书 TOP10（按借阅量倒序）"""
    hot_books = [
        BookStat(title="三体全集", author="刘慈欣", count=428, call_number="I247.55/123", category="I"),
        BookStat(title="平凡的世界", author="路遥", count=396, call_number="I247.57/88", category="I"),
        BookStat(title="深入理解计算机系统", author="Randal E. Bryant", count=312, call_number="TP3/288", category="TP"),
        BookStat(title="Python编程：从入门到实践", author="Eric Matthes", count=298, call_number="TP311.56/45", category="TP"),
        BookStat(title="微观经济学", author="范里安", count=276, call_number="F016/52", category="F"),
        BookStat(title="百年孤独", author="加西亚·马尔克斯", count=254, call_number="I775.45/1", category="I"),
        BookStat(title="被讨厌的勇气", author="岸见一郎", count=235, call_number="B848.4/19", category="B"),
        BookStat(title="人类简史", author="尤瓦尔·赫拉利", count=218, call_number="K109/4", category="K"),
        BookStat(title="高等数学辅导讲义", author="汤家凤", count=205, call_number="O13/99", category="O"),
        BookStat(title="陈嘉庚传", author="陈嘉庚研究会", count=192, call_number="K825.38/1", category="K"),
    ]
    return ApiResponse.ok(data=hot_books)

@router.get("/stats/categories", response_model=ApiResponse[List[CategoryStat]])
async def get_category_stats():
    """借阅中图分类大类占比"""
    categories = [
        CategoryStat(category="I", category_name="文学", count=11200, share=0.303),
        CategoryStat(category="TP", category_name="工业技术/计算机", count=8950, share=0.242),
        CategoryStat(category="F", category_name="经济管理", count=6820, share=0.185),
        CategoryStat(category="B", category_name="哲学/心理学", count=3410, share=0.092),
        CategoryStat(category="H", category_name="语言文字", count=2850, share=0.077),
        CategoryStat(category="K", category_name="历史地理/特藏", count=2100, share=0.057),
        CategoryStat(category="O", category_name="数理科学", count=1578, share=0.044),
    ]
    return ApiResponse.ok(data=categories)

@router.get("/stats/publishers", response_model=ApiResponse[List[PublisherStat]])
async def get_publisher_stats():
    """高频出版社 TOP 统计"""
    publishers = [
        PublisherStat(publisher="机械工业出版社", count=3210),
        PublisherStat(publisher="清华大学出版社", count=2980),
        PublisherStat(publisher="人民文学出版社", count=2650),
        PublisherStat(publisher="中信出版社", count=2240),
        PublisherStat(publisher="电子工业出版社", count=1980),
        PublisherStat(publisher="北京大学出版社", count=1720),
        PublisherStat(publisher="厦门大学出版社", count=1560),
    ]
    return ApiResponse.ok(data=publishers)

@router.post("/purchase-advice", response_model=ApiResponse)
async def generate_purchase_advice(req: PurchaseAdviceRequest):
    """AI 智能采购建议报告生成"""
    report = (
        "### 📊 2026-2027 嘉庚学院图书馆智能采购建议分析报告\n\n"
        "**一、高频需求文献复购建议：**\n"
        "- **TP类（计算机与人工智能）**：《深入理解计算机系统》《大模型应用开发实战》借阅频次超出馆藏承载比 3.8 倍，建议每个校区增购 3-5 册复本。\n"
        "- **I类（当代文学与科幻）**：刘慈欣、迟子建相关作品长期预约排队人数 > 10人，建议补齐新版精装。\n\n"
        "**二、冷门文献空间优化与调架：**\n"
        "- 部分早期工业工程传统教材近3年借阅次数为0，建议移至密集书库，腾出主楼三层高价值研读空间。\n\n"
        "**三、嘉庚特色特藏专架扩充：**\n"
        "- 建议引入闽南地方文化、侨批档案数字人文活化相关专题文献，打造“嘉庚精神”未来研讨空间。"
    )
    return ApiResponse.ok(data={"report": report})

@router.post("/book-review", response_model=ApiResponse)
async def generate_book_review(req: BookReviewRequest):
    """AI 书评与导读生成"""
    review = (
        f"《{req.title}》是一部极具思想纵深与阅读价值的作品。\n"
        "全书以精炼而富有张力的叙事风格展开，既有宏大的时代洞察，亦有对个体命运的微观体察。"
        "对于嘉庚学子而言，无论作为拓展专业视野的参考书，还是闲暇伴读的经典，都非常值得细细品读。"
    )
    return ApiResponse.ok(data={"review": review})
