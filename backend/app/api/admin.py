from typing import List
from fastapi import APIRouter, Depends, Query
from app.config import settings
from app.auth import require_admin
from app.schemas.common import ApiResponse
from app.schemas.admin import (
    AdminSummary,
    CategoryStat,
    BookStat,
    PublisherStat,
    PurchaseAdviceRequest,
    BookReviewRequest,
)
from app.services.local_data import borrowing, usage

router = APIRouter(prefix="/admin", tags=["Admin & Analytics"], dependencies=[Depends(require_admin)])


@router.get("/stats/summary", response_model=ApiResponse[AdminSummary])
def get_summary_stats():
    service = borrowing()
    return ApiResponse.ok(data=AdminSummary(**service.summary, **service.metadata()), **service.metadata())


@router.get("/stats/hot-books", response_model=ApiResponse[List[BookStat]])
def get_hot_books_stats(limit: int = Query(10, ge=1, le=100)):
    service = borrowing()
    return ApiResponse.ok(data=service.engine.hot_books(limit=limit), **service.metadata())


@router.get("/stats/categories", response_model=ApiResponse[List[CategoryStat]])
def get_category_stats():
    service = borrowing()
    return ApiResponse.ok(data=service.categories, **service.metadata())


@router.get("/stats/publishers", response_model=ApiResponse[List[PublisherStat]])
def get_publisher_stats(limit: int = Query(10, ge=1, le=100)):
    service = borrowing()
    return ApiResponse.ok(data=service.publishers[:limit], **service.metadata())


@router.get("/stats/trend", response_model=ApiResponse[list])
def get_trend(days: int = Query(30, ge=1, le=366)):
    service = borrowing()
    rows = service.trend(days)
    return ApiResponse.ok(data=rows, message="按样本日期汇总，窗口终点为样本末日。" if rows else "借阅源没有日期，无法生成每日趋势。", **service.metadata())


@router.get("/stats/usage", response_model=ApiResponse[dict])
def get_usage():
    report = usage()
    return ApiResponse.ok(data=report, dataset_label=report["dataset_label"], is_live=False,
                          scope="separate_source_aggregates")


@router.post("/purchase-advice", response_model=ApiResponse[dict])
def generate_purchase_advice(req: PurchaseAdviceRequest = PurchaseAdviceRequest()):
    service = borrowing()
    return ApiResponse.ok(data=service.purchase_advice(req.focus_category), **service.metadata())


@router.post("/book-review", response_model=ApiResponse[dict])
async def generate_book_review(req: BookReviewRequest):
    """
    AI 书评生成接口：
    若配置了大模型密钥，调用大模型生成阅读推广导读；
    若未配置大模型或处于离线环境，根据元数据生成结构化导读书评兜底。
    """
    title = (req.title or "").strip()
    if not title:
        return ApiResponse.fail(code=4000, message="书名不能为空。")

    # 尝试大模型智能生成
    if settings.LLM_API_KEY and not settings.LLM_API_KEY.startswith("sk-your"):
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage

            llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
                temperature=0.7,
                timeout=12,
                max_retries=0
            )
            prompt = (
                f"请为图书《{title}》（作者：{req.author or '馆藏作者'}）写一段针对大学生的阅读推广书评与导读。"
                "字数在150字左右，语言亲切、富有见地，能够激发同学们的研读兴趣。"
            )
            res = await llm.ainvoke([
                SystemMessage(content="你是厦门大学嘉庚学院图书馆资深阅读推广馆员「小嘉」。"),
                HumanMessage(content=prompt)
            ])
            text = res.content if isinstance(res.content, str) else str(res.content)
            if text and text.strip():
                return ApiResponse.ok(data={"title": title, "review": text.strip(), "generated_by": "llm"})
        except Exception:
            pass

    # 高可用结构化模板兜底
    author_str = f"（{req.author} 著）" if req.author else ""
    fallback_review = (
        f"《{title}》{author_str}是嘉庚学院馆藏中备受学子青睐的高价值文献。"
        "该作品立意深刻、论述严谨，既具有宏阔的思想洞察力，又兼具扎实的学术参考意义。"
        "无论是作为专业研读的延伸拓展，还是通识视野的沉浸阅读，都极具研读价值。"
    )
    return ApiResponse.ok(data={"title": title, "review": fallback_review, "generated_by": "template"})
