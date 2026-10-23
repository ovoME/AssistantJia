import axios from 'axios'
import type { ApiResponse } from '@/types'

/**
 * 普通 HTTP 请求实例（非流式接口用）。
 * 拦截器统一解包 { code, message, data }：业务错误 reject，成功直接返回 data。
 * 调用处通过 axios 第二泛型声明返回类型，无需再 .data / as any。
 */
export const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

http.interceptors.response.use(
  (resp) => {
    const body = resp.data as ApiResponse
    // 业务层错误（code 非 0）直接 reject，调用处走 catch
    if (body && typeof body.code === 'number' && body.code !== 0) {
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    // 直接解包 data：调用处拿到的就是业务数据本身
    // （axios 拦截器类型声明仍为 AxiosResponse，这里用 never 断言绕过，运行时即 body.data）
    return body.data as never
  },
  (error) => {
    return Promise.reject(error)
  },
)

/** 解析一个 SSE 事件块，取出 data: JSON 并回调；非法块忽略。 */
function dispatchEvent(block: string, onEvent: (e: import('@/types').SseEvent) => void) {
  const line = block.split(/\r?\n/).find((l) => l.startsWith('data:'))
  if (!line) return
  const jsonStr = line.slice(5).trim()
  if (!jsonStr) return
  try {
    onEvent(JSON.parse(jsonStr))
  } catch {
    // 忽略半包/坏包
  }
}

/**
 * 流式对话：POST /api/chat，SSE 用 fetch ReadableStream 解析
 * （EventSource 只支持 GET，这里是 POST，所以用 fetch）。
 * 分隔符兼容 \n\n 与 \r\n\r\n；流结束时 flush 一次残留 buffer，避免尾部 done 事件丢失。
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

    // SSE 以空行（\n\n 或 \r\n\r\n）分隔多个事件
    const parts = buffer.split(/\r?\n\r?\n/)
    buffer = parts.pop() || ''
    for (const part of parts) {
      dispatchEvent(part, onEvent)
    }
  }

  // 流结束：flush 最后一个未以空行结尾的事件块
  const tail = buffer.trim()
  if (tail) dispatchEvent(tail, onEvent)
}
