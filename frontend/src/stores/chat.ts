import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage, Book, SseEvent } from '@/types'
import { sendChat } from '@/api'

let msgId = 0
const nextId = () => `m${Date.now()}_${msgId++}`

/**
 * 对话状态：消息列表、流式处理、停止生成、续借/预约动作。
 */
export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)
  const readerId = ref('2023001') // 演示用，登录接入后替换
  const sessionId = ref(`session_${Date.now()}`)
  let abortController: AbortController | null = null

  function pushAssistantPlaceholder(): ChatMessage {
    const m: ChatMessage = {
      id: nextId(),
      role: 'assistant',
      content: '',
      thought: '',
      cards: [],
      streaming: true,
    }
    messages.value.push(m)
    // 返回数组中真正的响应式代理（直接返回 m 会丢失响应式，修改不刷新）
    return messages.value[messages.value.length - 1]
  }

  async function send(text: string) {
    const content = text.trim()
    if (!content || loading.value) return

    messages.value.push({ id: nextId(), role: 'user', content })
    const assistant = pushAssistantPlaceholder()
    loading.value = true
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
          assistant.content += `\n（出错了：${e.message}）`
          break
        case 'done':
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
        assistant.content += '\n（网络异常，请稍后重试，或咨询人工服务台）'
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
  }

  return { messages, loading, readerId, sessionId, send, stop, reset }
})
