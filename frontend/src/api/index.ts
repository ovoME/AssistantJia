/**
 * 业务接口统一出口。
 * 后端未就绪时走 mock（USE_MOCK=true）；A 的后端好了之后把 mock/data.ts 的 USE_MOCK 改成 false。
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
} from '@/types'
import {
  USE_MOCK,
  mockBooks,
  mockBorrows,
  mockRecommend,
  mockSummary,
  mockHotBooks,
  mockCategories,
  mockSseChunks,
} from '@/mock/data'

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

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
  return streamChat(payload, onEvent, signal)
}

/* ---------- 馆藏检索 ---------- */
export async function searchBooks(query: string, limit = 5): Promise<Book[]> {
  if (USE_MOCK) {
    await delay(300)
    return mockBooks.filter(
      (b) => b.title.includes(query) || b.author.includes(query) || b.call_number.includes(query),
    ).slice(0, limit) || mockBooks.slice(0, limit)
  }
  const r = await http.get('/books/search', { params: { query, limit } })
  return (r as any).data
}

/* ---------- 借阅 ---------- */
export async function getMyBorrows(readerId: string): Promise<BorrowRecord[]> {
  if (USE_MOCK) {
    await delay(200)
    return mockBorrows
  }
  const r = await http.get(`/reader/${readerId}/borrows`)
  return (r as any).data
}

export async function renewBook(readerId: string, bookId: string): Promise<RenewResult> {
  if (USE_MOCK) {
    await delay(400)
    return { new_due_date: '2026-12-01', renew_count: 1 }
  }
  const r = await http.post('/renew', { reader_id: readerId, book_id: bookId })
  return (r as any).data
}

export async function reserveBook(readerId: string, isbn: string): Promise<ReserveResult> {
  if (USE_MOCK) {
    await delay(400)
    return { queue_position: 1, notify_channel: '站内消息' }
  }
  const r = await http.post('/reserve', { reader_id: readerId, isbn })
  return (r as any).data
}

/* ---------- 推荐 ---------- */
export async function getRecommend(readerId: string, limit = 5): Promise<RecommendBook[]> {
  if (USE_MOCK) {
    await delay(200)
    return mockRecommend.slice(0, limit)
  }
  const r = await http.get('/recommend', { params: { reader_id: readerId, limit } })
  return (r as any).data
}

/* ---------- 管理端 ---------- */
export async function getAdminSummary(): Promise<AdminSummary> {
  if (USE_MOCK) {
    await delay(200)
    return mockSummary
  }
  const r = await http.get('/admin/stats/summary')
  return (r as any).data
}

export async function getHotBooks(limit = 10): Promise<BookStat[]> {
  if (USE_MOCK) {
    await delay(200)
    return mockHotBooks.slice(0, limit)
  }
  const r = await http.get('/admin/stats/hot-books', { params: { limit } })
  return (r as any).data
}

export async function getCategories(): Promise<CategoryStat[]> {
  if (USE_MOCK) {
    await delay(200)
    return mockCategories
  }
  const r = await http.get('/admin/stats/categories')
  return (r as any).data
}
