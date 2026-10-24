// 全局类型定义，严格对照 docs/api-contract.md

/** 统一响应格式 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  dataset_label?: string
  is_live?: boolean
  scope?: string
  limitations?: string[]
}

/** 馆藏图书（检索/卡片） */
export interface Book {
  title: string
  author: string
  isbn: string
  call_number: string
  location: string | null
  available: number | null
  status: string
  book_key?: string
  reason?: string
  dataset_label?: string
  is_live?: boolean
  reservation_supported?: boolean
}

/** 借阅记录 */
export interface BorrowRecord {
  book_id: string
  title: string
  borrow_date: string
  due_date: string
  renew_count: number
  is_overdue: boolean
  can_renew?: boolean
  dataset_label?: string
}

/** 个性化推荐图书 */
export interface RecommendBook {
  book_key?: string
  title: string
  author: string
  isbn: string
  call_number: string
  reason: string
}

/** 续借结果 */
export interface RenewResult {
  new_due_date: string
  renew_count: number
  can_renew?: boolean
}

/** 预约结果 */
export interface ReserveResult {
  queue_position: number
  notify_channel: string
}

/** 对话消息（UI用） */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  thought?: string
  cards?: Book[]
  streaming?: boolean
  /** 该条回复是否因网络/服务错误而失败（用于展示“重新发送”） */
  error?: boolean
  /** 对应的用户问题，失败重发时使用 */
  retryText?: string
  timestamp?: string
}

/** 后端 SSE 事件类型（对照接口契约 1.1） */
export type SseEvent =
  | { type: 'thought'; content: string }
  | { type: 'tool_call'; tool: string; args: Record<string, unknown> }
  | { type: 'content'; token: string }
  | { type: 'card'; card_type: 'book'; data: Book }
  | { type: 'done' }
  | { type: 'error'; message: string }

/** 管理端概览统计 */
export interface AdminSummary {
  total_borrows: number
  total_readers: number
  total_titles: number
  avg_borrow_per_reader: number | null
  dataset_label?: string
}

/** 分类统计项 */
export interface CategoryStat {
  category: string
  category_name?: string
  count: number
}

/** 简单榜单项 */
export interface BookStat {
  title: string
  author?: string
  count: number
}

/** 借阅趋势数据点 */
export interface BorrowTrendPoint {
  date: string
  count: number
}

export interface PublisherStat { publisher: string; count: number; publisher_missing?: boolean }
