<script setup lang="ts">
import type { ChatMessage } from '@/types'
import BookCard from './BookCard.vue'

defineProps<{ message: ChatMessage; readerId?: string }>()
</script>

<template>
  <div class="row" :class="message.role">
    <div v-if="message.role === 'assistant'" class="avatar">嘉</div>
    <div class="bubble">
      <div v-if="message.thought && !message.content" class="thought">{{ message.thought }}</div>
      <div v-else-if="message.thought" class="thought mini">{{ message.thought }}</div>
      <div class="content">
        <span>{{ message.content }}</span>
        <span v-if="message.streaming" class="cursor">▍</span>
      </div>
      <div v-if="message.cards && message.cards.length" class="cards">
        <BookCard v-for="(b, i) in message.cards" :key="i" :book="b" :reader-id="readerId" />
      </div>
    </div>
    <div v-if="message.role === 'user'" class="avatar user">我</div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
  align-items: flex-start;
}
.row.user {
  flex-direction: row-reverse;
}
.avatar {
  flex: 0 0 36px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #14b8a6;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
}
.avatar.user {
  background: #4f8cff;
}
.bubble {
  max-width: 76%;
}
.row.user .bubble {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.thought {
  font-size: 12px;
  color: #94a3b8;
  font-style: italic;
  margin-bottom: 6px;
}
.thought.mini {
  font-size: 11px;
  opacity: 0.7;
}
.content {
  display: inline-block;
  padding: 10px 14px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #eef2f7;
  color: #1f2937;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.row.user .content {
  background: #4f8cff;
  color: #fff;
  border-color: #4f8cff;
}
.cursor {
  animation: blink 1s steps(2) infinite;
  color: #14b8a6;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.cards {
  width: 100%;
  min-width: 280px;
}
</style>
