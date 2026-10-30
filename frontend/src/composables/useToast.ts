import { reactive } from 'vue'

export type ToastType = 'success' | 'error' | 'info'
export interface Toast {
  id: number
  type: ToastType
  text: string
}

export const toasts = reactive<Toast[]>([])
let seq = 1

function push(type: ToastType, text: string) {
  const id = seq++
  toasts.push({ id, type, text })
  window.setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i >= 0) toasts.splice(i, 1)
  }, 2600)
}

export function useToast() {
  return {
    success: (text: string) => push('success', text),
    error: (text: string) => push('error', text),
    info: (text: string) => push('info', text),
  }
}
