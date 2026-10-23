<script setup lang="ts">
import { ref } from 'vue'
import type { Book } from '@/types'
import { reserveBook } from '@/api'
import { useToast } from '@/composables/useToast'

const props = defineProps<{ book: Book; readerId?: string }>()
const toast = useToast()
const reserved = ref(false)
const loading = ref(false)

async function onReserve() {
  if (reserved.value || loading.value) return
  loading.value = true
  try {
    const r = await reserveBook(props.readerId || '2023001', props.book.isbn)
    reserved.value = true
    toast.success(`预约成功，你在排队第 ${r.queue_position} 位，到时${r.notify_channel}通知`)
  } catch (e) {
    toast.error((e as Error).message || '预约失败，请稍后再试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="lg lg-r22 book-card">
    <span class="lg-inner"></span>
    <div class="cover">
      <span class="cover-call">{{ book.call_number.split('/')[0] }}</span>
    </div>
    <div class="info">
      <div class="title">{{ book.title }}</div>
      <div class="meta">{{ book.author }} · {{ book.call_number }}</div>
      <div class="location">
        <span class="loc-icon">📍</span>
        <span>{{ book.location }}</span>
      </div>
      <div class="footer">
        <span class="cu-tag" :class="book.available > 0 ? 'cu-tag-green' : 'cu-tag-gray'">
          {{ book.available > 0 ? `在馆 · 可借 ${book.available} 本` : '已借出' }}
        </span>
        <button
          class="cu-btn cu-btn-sm dark-btn"
          :disabled="reserved || book.available === 0 || loading"
          @click="onReserve"
        >
          {{ reserved ? '已预约' : '预约' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.book-card {
  width: 100%;
  display: flex;
  gap: 12px;
  padding: 13px;
  text-align: left;
}
.cover {
  flex: 0 0 54px;
  width: 54px;
  height: 72px;
  border-radius: 10px;
  background: linear-gradient(160deg, #e6fbf7, #bfeee6);
  border: 1px solid rgba(15, 157, 143, 0.4);
  color: #0b7a6e;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  padding: 4px;
  text-align: center;
}
.info { flex: 1; min-width: 0; }
.title { font-size: 14.5px; font-weight: 700; color: var(--ink); line-height: 1.4; }
.meta { font-size: 12.5px; color: var(--ink-2); margin-top: 3px; }
.location {
  display: flex; align-items: center; gap: 4px;
  font-size: 12.5px; color: #0b7a6e; margin-top: 5px; font-weight: 600;
}
.footer {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 9px;
}
.dark-btn {
  background: #1c1c1c;
  color: #fff;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.4);
}
</style>
