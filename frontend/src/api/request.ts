import axios from 'axios'
import type { ApiResponse } from '@/types'

/**
 * 普通 HTTP 请求实例（非流式接口用）。
 * 统一返回 data 字段，统一错误提示。
 */
export const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

http.interceptors.response.use(
  (resp) => {
    const body = resp.data as ApiResponse
    // 业务层错误（code 非 0）
    if (body && typeof body.code === 'number' && body.code !== 0) {
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    // 直接返回统一响应体（{ code, message, data }），调用处取 .data
    return body as unknown as typeof resp
  },
  (error) => {
    return Promise.reject(error)
  },
)

/**
 * 流式对话：POST /api/chat，SSE 用 fetch ReadableStream 解析
 * （EventSource 只支持 GET，这里是 POST，所以用 fetch）。
 *
 * @param payload  { message, session_id, reader_id }
 * @param onEvent  每收到一个 SSE 事件回调
 * @param signal   可用于中止（停止生成）
 */
export async function streamChat(
  payload: { message: string; session_id: string; reader_id?: string },
  onEvent: (event: import('@/types').SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })

  if (!resp.ok || !resp.body) {
    throw new Error(`对话服务异常（HTTP ${resp.status}）`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE 以空行分隔多个事件，逐行解析 data:
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      const line = part.split('\n').find((l) => l.startsWith('data:'))
      if (!line) continue
      const jsonStr = line.slice(5).trim()
      if (!jsonStr) continue
      try {
        onEvent(JSON.parse(jsonStr))
      } catch {
        // 忽略半包
      }
    }
  }
}
