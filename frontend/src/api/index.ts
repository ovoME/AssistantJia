/**
 * 业务接口统一出口。
 * 后端未就绪时走 mock（VITE_USE_MOCK=true，默认开启）；
 * A 的后端好了之后在 .env.local 设 VITE_USE_MOCK=false，无需改源码。
 */
import { http, streamChat } from './request'
import type {
  Book,
  BorrowRecord,
  RecommendBook,
  RenewResult,
  ReserveResult,
  SseEvent,
  AdminSummary,
  CategoryStat,
  BookStat,
  BorrowTrendPoint,
  PublisherStat,
} from '@/types'
import {
  USE_MOCK,
  mockBooks,
  mockBorrows,
  mockRecommend,
  mockSummary,
  mockHotBooks,
  mockCategories,
  mockPublishers,
  mockBorrowTrend,
  mockSseChunks,
  mockAdvice,
} from '@/mock/data'

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

export interface UsageReport {
  dataset_label: string
  datasets: Record<string, { source_file: string; rows: number; distinct_source_readers: number | null; observed_date_min: string | null; observed_date_max: string | null }>
  limitations: string[]
}
export async function getUsage(): Promise<UsageReport> {
  if (USE_MOCK) return { dataset_label: 'simulated', datasets: {}, limitations: ['前端模拟模式未提供资源使用统计'] }
  return http.get<unknown, UsageReport>('/admin/stats/usage')
}

/* ---------- 对话（流式） ---------- */
export async function sendChat(
  payload: { message: string; session_id: string; reader_id?: string },
  onEvent: (e: SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (USE_MOCK) {
    // 模拟流式：简单意图命中返回不同内容
    const q = payload.message
    let reply = '你好呀，我是小嘉！我可以帮你查馆藏、找架位、续借、预约，也可以回答借阅规则问题。'
    let cards: Book[] = []
    if (q.includes('三体') || q.includes('找书') || q.includes('架位') || q.includes('借')) {
      reply = '帮你查到啦！下面是相关馆藏，包含索书号和具体架位，点击卡片可以直接预约哦～'
      cards = mockBooks
    } else if (q.includes('续借') || q.includes('还')) {
      reply = '续借可以在「我的借阅」里点按钮办理，每本书最多续借1次，被预约或超期的书不能续借哦。'
    } else if (q.includes('借') && q.includes('几天')) {
      reply = '普通图书借期30天，可续借1次（30天），具体以系统显示为准。'
    }
    const chunks = mockSseChunks(reply, cards)
    for (const c of chunks) {
      if (signal?.aborted) break
      await delay(60)
      onEvent(JSON.parse(c) as SseEvent)
    }
    return
  }
  return streamChat({ ...payload, reader_id: undefined }, onEvent, signal)
}

/* ---------- 馆藏检索 ---------- */
export async function searchBooks(query: string, limit = 5): Promise<Book[]> {
  if (USE_MOCK) {
    await delay(300)
    const hit = mockBooks.filter(
      (b) => b.title.includes(query) || b.author.includes(query) || b.call_number.includes(query),
    )
    // 命中为空时回退到前 limit 本，避免搜不到直接返回空数组
    return (hit.length ? hit : mockBooks.slice(0, limit)).slice(0, limit)
  }
  return http.get<unknown, Book[]>('/books/search', { params: { query, limit } })
}

/* ---------- 借阅 ---------- */
export async function getMyBorrows(_readerId: string): Promise<BorrowRecord[]> {
  if (USE_MOCK) {
    await delay(200)
    return mockBorrows
  }
  const target = sessionStorage.getItem('xiaojia.readerToken') ? 'me' : 'demo-reader'
  return http.get<unknown, BorrowRecord[]>(`/reader/${target}/borrows`)
}

export async function renewBook(_readerId: string, bookId: string): Promise<RenewResult> {
  if (USE_MOCK) {
    await delay(400)
    return { new_due_date: '2026-12-01', renew_count: 1 }
  }
  return http.post<unknown, RenewResult>('/renew', { reader_id: sessionStorage.getItem('xiaojia.readerToken') ? 'me' : 'demo-reader', book_id: bookId })
}

export async function reserveBook(_readerId: string, isbn: string): Promise<ReserveResult> {
  if (USE_MOCK) {
    await delay(400)
    return { queue_position: 1, notify_channel: '站内消息' }
  }
  return http.post<unknown, ReserveResult>('/reserve', { reader_id: sessionStorage.getItem('xiaojia.readerToken') ? 'me' : 'demo-reader', isbn })
}

/* ---------- 推荐 ---------- */
export async function getRecommend(_readerId: string, limit = 5): Promise<RecommendBook[]> {
  if (USE_MOCK) {
    await delay(200)
    return mockRecommend.slice(0, limit)
  }
  return http.get<unknown, RecommendBook[]>('/recommend', { params: { limit } })
}

/* ---------- 管理端 ---------- */
export async function getAdminSummary(): Promise<AdminSummary> {
  if (USE_MOCK) {
    await delay(200)
    return mockSummary
  }
  return http.get<unknown, AdminSummary>('/admin/stats/summary')
}

export async function getHotBooks(limit = 10): Promise<BookStat[]> {
  if (USE_MOCK) {
    await delay(200)
    return mockHotBooks.slice(0, limit)
  }
  return http.get<unknown, BookStat[]>('/admin/stats/hot-books', { params: { limit } })
}

export async function getCategories(): Promise<CategoryStat[]> {
  if (USE_MOCK) {
    await delay(200)
    return mockCategories
  }
  return http.get<unknown, CategoryStat[]>('/admin/stats/categories')
}

/** 出版社 TOP10（待后端契约：GET /api/admin/stats/publishers） */
export async function getPublishers(limit = 10): Promise<PublisherStat[]> {
  if (USE_MOCK) {
    await delay(200)
    return mockPublishers.slice(0, limit).map((row) => ({ publisher: row.title, count: row.count }))
  }
  return http.get<unknown, PublisherStat[]>('/admin/stats/publishers', { params: { limit } })
}

/** 借阅趋势：近N天每日借阅量（待后端契约：GET /api/admin/stats/trend） */
export async function getBorrowTrend(days = 30): Promise<BorrowTrendPoint[]> {
  if (USE_MOCK) {
    await delay(200)
    return mockBorrowTrend.slice(-days)
  }
  return http.get<unknown, BorrowTrendPoint[]>('/admin/stats/trend', { params: { days } })
}

/** AI 智能采购建议（契约 5.3：POST /api/admin/purchase-advice） */
export async function getPurchaseAdvice(): Promise<string> {
  if (USE_MOCK) {
    await delay(300)
    return mockAdvice
  }
  const result = await http.post<unknown, { report: string }>('/admin/purchase-advice')
  return result.report
}
