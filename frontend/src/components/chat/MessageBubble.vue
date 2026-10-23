<script setup lang="ts">
import type { ChatMessage } from '@/types'
import BookCard from './BookCard.vue'

defineProps<{ message: ChatMessage; readerId?: string }>()
</script>

<template>
  <div class="row" :class="message.role">
    <!-- 助手 -->
    <template v-if="message.role === 'assistant'">
      <div class="avatar">嘉</div>
      <div class="col">
        <div v-if="message.thought && !message.content" class="thought">
          <span class="cu-spinner"><span></span><span></span><span></span></span>
          <span class="thought-text">{{ message.thought }}</span>
        </div>
        <div v-if="message.thought && message.content" class="thought mini">{{ message.thought }}</div>

        <div v-if="message.content" class="lg bubble-b cu-bubble-in">
          <span class="lg-inner"></span>
          <span class="content-text">{{ message.content }}</span>
          <span v-if="message.streaming" class="cursor">▍</span>
        </div>
        <div v-else-if="message.streaming && !message.thought" class="lg bubble-b think cu-bubble-in">
          <span class="lg-inner"></span>
          <span class="cu-spinner"><span></span><span></span><span></span></span>
        </div>

        <div v-if="message.cards && message.cards.length" class="cards">
          <BookCard v-for="(b, i) in message.cards" :key="i" :book="b" :reader-id="readerId" />
        </div>
      </div>
    </template>

    <!-- 用户 -->
    <template v-else>
      <div class="col user-col">
        <div class="bubble-u cu-bubble-in">{{ message.content }}</div>
      </div>
      <div class="avatar user">我</div>
    </template>
  </div>
</template>

<style scoped>
.row { display: flex; gap: 10px; align-items: flex-start; margin-bottom: 16px; }
.row.user { justify-content: flex-end; }
.avatar {
  flex: 0 0 36px; width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, #14b8a6, #0f6e7c);
  color: #fff; font-size: 14px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 10px rgba(15, 157, 143, 0.35);
}
.avatar.user { background: linear-gradient(135deg, #2f93ff, #007aff); box-shadow: 0 4px 10px rgba(0, 122, 255, 0.35); }
.col { display: flex; flex-direction: column; min-width: 0; max-width: 80%; }
.user-col { align-items: flex-end; }

.bubble-b {
  align-self: flex-start;
  padding: 11px 15px;
  border-radius: 20px 20px 20px 6px;
  font-size: 15px;
  line-height: 1.7;
  color: var(--ink);
  white-space: pre-wrap;
  word-break: break-word;
}
.think { display: flex; align-items: center; padding: 14px 18px; }

.bubble-u {
  padding: 11px 15px;
  border-radius: 20px 20px 6px 20px;
  font-size: 15px;
  line-height: 1.7;
  color: #fff;
  background: linear-gradient(180deg, #2f93ff, #007aff);
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.3), 0 6px 16px rgba(0, 122, 255, 0.32);
  white-space: pre-wrap;
  word-break: break-word;
}

.cursor { animation: blink 1s steps(2) infinite; color: var(--ios-teal); margin-left: 1px; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

.thought {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--ink-3);
  margin-bottom: 8px;
}
.thought.mini { font-size: 11px; font-style: italic; opacity: 0.7; }

.cards { display: flex; flex-direction: column; gap: 10px; margin-top: 8px; width: 100%; min-width: 290px; }
</style>
