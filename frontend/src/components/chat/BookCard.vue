<script setup lang="ts">
import { ref } from 'vue'
import { NTag, NButton, useMessage } from 'naive-ui'
import type { Book } from '@/types'
import { reserveBook } from '@/api'

const props = defineProps<{ book: Book; readerId?: string }>()
const message = useMessage()
const reserved = ref(false)
const loading = ref(false)

async function onReserve() {
  if (reserved.value) return
  loading.value = true
  try {
    const r = await reserveBook(props.readerId || '2023001', props.book.isbn)
    reserved.value = true
    message.success(`预约成功，你在排队第 ${r.queue_position} 位，到时${r.notify_channel}通知`)
  } catch (e) {
    message.error((e as Error).message || '预约失败，请稍后再试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="book-card">
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
        <NTag :type="book.available > 0 ? 'success' : 'default'" size="small" round>
          {{ book.available > 0 ? `在馆 · 可借 ${book.available} 本` : '已借出' }}
        </NTag>
        <NButton
          size="small"
          type="primary"
          :disabled="reserved || book.available === 0"
          :loading="loading"
          @click="onReserve"
        >
          {{ reserved ? '已预约' : '预约' }}
        </NButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.book-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  margin-top: 8px;
  background: #f7f9fc;
  border: 1px solid #e8eef5;
  border-radius: 12px;
  text-align: left;
}
.cover {
  flex: 0 0 52px;
  height: 68px;
  border-radius: 6px;
  background: linear-gradient(160deg, #0f9d8f, #14b8a6);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  padding: 4px;
  text-align: center;
}
.info {
  flex: 1;
  min-width: 0;
}
.title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.4;
}
.meta {
  font-size: 12px;
  color: #6b7280;
  margin-top: 3px;
}
.location {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #0f766e;
  margin-top: 5px;
}
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
</style>
