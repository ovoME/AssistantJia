import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { ChatMessage, Book, SseEvent } from '@/types'
import { sendChat } from '@/api'

const STORAGE_KEY = 'xiaojia.chat.v1'

/** 从 localStorage 恢复会话（刷新不丢）；恢复时把进行中的 streaming 标记为结束 */
function loadSession(): { messages: ChatMessage[]; sessionId: string } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      const messages: ChatMessage[] = (parsed.messages || []).map((m: ChatMessage) => ({
        ...m,
        streaming: false,
      }))
      return { messages, sessionId: parsed.sessionId || `session_${Date.now()}` }
    }
  } catch {
    // 损坏缓存忽略
  }
  return { messages: [], sessionId: `session_${Date.now()}` }
}

let msgId = 0
const nextId = () => `m${Date.now()}_${msgId++}`

/**
 * 对话状态：消息列表、流式处理、停止生成、续借/预约动作。
 * 会话持久化到 localStorage（等后端 /api/chat/history 就绪后可切换为服务端恢复）。
 */
export const useChatStore = defineStore('chat', () => {
  const initial = loadSession()
  const messages = ref<ChatMessage[]>(initial.messages)
  const loading = ref(false)
  const readerId = ref('demo-reader') // 仅模拟业务使用；真实个性化身份由已验证令牌确定
  const sessionId = ref(initial.sessionId)
  let abortController: AbortController | null = null

  // 持久化（跳过正在流式的中间态，仅在 idle 时写回）
  watch(
    [messages, sessionId],
    () => {
      if (loading.value) return
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ messages: messages.value, sessionId: sessionId.value }),
        )
      } catch {
        // 存储满/隐私模式忽略
      }
    },
    { deep: true },
  )

  function now(): string {
    const d = new Date()
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }

  function pushAssistantPlaceholder(): ChatMessage {
    const m: ChatMessage = {
      id: nextId(),
      role: 'assistant',
      content: '',
      thought: '',
      cards: [],
      streaming: true,
      timestamp: now(),
    }
    messages.value.push(m)
    // 返回数组中真正的响应式代理（直接返回 m 会丢失响应式，修改不刷新）
    return messages.value[messages.value.length - 1]
  }

  async function send(text: string) {
    const content = text.trim()
    if (!content || loading.value) return

    messages.value.push({ id: nextId(), role: 'user', content, timestamp: now() })
    const assistant = pushAssistantPlaceholder()
    assistant.retryText = content
    await runStream(content, assistant)
  }

  /** 对一条失败的助手消息重新发起请求（不重复插入用户消息） */
  async function retry(assistantId: string) {
    if (loading.value) return
    const assistant = messages.value.find((m) => m.id === assistantId)
    const text = assistant?.retryText
    if (!assistant || !text) return
    assistant.content = ''
    assistant.thought = ''
    assistant.cards = []
    assistant.error = false
    await runStream(text, assistant)
  }

  async function runStream(content: string, assistant: ChatMessage) {
    loading.value = true
    assistant.streaming = true
    abortController = new AbortController()

    const handle = (e: SseEvent) => {
      switch (e.type) {
        case 'thought':
          assistant.thought = e.content
          break
        case 'content':
          assistant.content += e.token
          break
        case 'card':
          if (e.card_type === 'book') {
            assistant.cards = [...(assistant.cards || []), e.data as Book]
          }
          break
        case 'error':
          assistant.error = true
          assistant.content += `${assistant.content ? '\n' : ''}（出错了：${e.message}）`
          break
        case 'done':
          assistant.thought = ''
          break
      }
    }

    try {
      await sendChat(
        { message: content, session_id: sessionId.value, reader_id: readerId.value },
        handle,
        abortController.signal,
      )
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        assistant.error = true
        if (!assistant.content) assistant.content = '消息发送失败，请检查网络后重试。'
      }
    } finally {
      assistant.streaming = false
      loading.value = false
      abortController = null
    }
  }

  function stop() {
    abortController?.abort()
    loading.value = false
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant') last.streaming = false
  }

  function reset() {
    messages.value = []
    sessionId.value = `session_${Date.now()}`
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
  }

  return { messages, loading, readerId, sessionId, send, retry, stop, reset }
})
