<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import { NButton, NTag, NDrawer, NDrawerContent, NSpin, useMessage } from 'naive-ui'
import { getMyBorrows, renewBook } from '@/api'
import type { BorrowRecord } from '@/types'

const router = useRouter()
const chat = useChatStore()
const message = useMessage()

const drawerShow = ref(false)
const borrows = ref<BorrowRecord[]>([])
const borrowLoading = ref(false)

const quickQuestions = ['帮我找《三体》', '图书能借多少天？', '怎么续借？', '我想找物流相关的书']

const messagesEl = ref<HTMLElement | null>(null)

async function scrollToBottom() {
  await nextTick()
  const el = messagesEl.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(
  () => chat.messages.map((m) => m.content).join(''),
  scrollToBottom,
)

async function onSend(text: string) {
  await chat.send(text)
  scrollToBottom()
}

async function openBorrows() {
  drawerShow.value = true
  borrowLoading.value = true
  try {
    borrows.value = await getMyBorrows(chat.readerId)
  } finally {
    borrowLoading.value = false
  }
}

async function onRenew(book: BorrowRecord) {
  try {
    const r = await renewBook(chat.readerId, book.book_id)
    book.due_date = r.new_due_date
    book.renew_count = r.renew_count
    book.is_overdue = false
    message.success(`续借成功，新到期日 ${r.new_due_date}`)
  } catch (e) {
    message.error((e as Error).message)
  }
}
</script>

<template>
  <div class="reader-page">
    <div class="phone">
      <!-- 顶部标题栏 -->
      <header class="topbar">
        <div class="left">
          <div class="avatar">嘉</div>
          <div>
            <div class="name">小嘉 · 图书馆智能馆员</div>
            <div class="status"><span class="dot"></span>在线 · 有问题尽管问</div>
          </div>
        </div>
        <div class="actions">
          <NButton size="tiny" quaternary @click="openBorrows">我的借阅</NButton>
          <NButton size="tiny" quaternary @click="router.push('/admin')">管理端</NButton>
        </div>
      </header>

      <!-- 消息流 -->
      <div ref="messagesEl" class="messages">
        <div v-if="chat.messages.length === 0" class="welcome">
          <div class="welcome-emoji">📚</div>
          <div class="welcome-title">你好，我是小嘉！</div>
          <div class="welcome-sub">能帮你查馆藏、找架位、续借、预约，也懂借阅规则。</div>
          <div class="quick">
            <NTag
              v-for="q in quickQuestions"
              :key="q"
              class="quick-tag"
              round
              checkable
              @click="onSend(q)"
            >
              {{ q }}
            </NTag>
          </div>
        </div>
        <MessageBubble
          v-for="m in chat.messages"
          :key="m.id"
          :message="m"
          :reader-id="chat.readerId"
        />
      </div>

      <!-- 输入 -->
      <ChatInput :loading="chat.loading" @send="onSend" @stop="chat.stop" />
    </div>

    <!-- 我的借阅抽屉 -->
    <NDrawer v-model:show="drawerShow" :width="360" placement="right">
      <NDrawerContent title="我的借阅" closable>
        <NSpin :show="borrowLoading">
          <div v-for="b in borrows" :key="b.book_id" class="borrow-item">
            <div class="b-title">{{ b.title }}</div>
            <div class="b-meta">
              应还：{{ b.due_date }}
              <NTag v-if="b.is_overdue" type="error" size="tiny">已逾期</NTag>
              <NTag v-else type="success" size="tiny">借阅中</NTag>
            </div>
            <div class="b-meta">已续借 {{ b.renew_count }} 次</div>
            <NButton
              size="tiny"
              type="primary"
              :disabled="b.renew_count >= 1"
              @click="onRenew(b)"
            >
              {{ b.renew_count >= 1 ? '不可再续' : '一键续借' }}
            </NButton>
          </div>
        </NSpin>
      </NDrawerContent>
    </NDrawer>
  </div>
</template>

<style scoped>
.reader-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #e6f7f4 0%, #eef2f7 100%);
  display: flex;
  justify-content: center;
  padding: 20px 12px;
}
.phone {
  width: 100%;
  max-width: 760px;
  height: calc(100vh - 40px);
  background: #f4f7fb;
  border-radius: 16px;
  box-shadow: 0 8px 40px rgba(15, 118, 110, 0.12);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #eef2f7;
}
.left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #14b8a6;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}
.name {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
}
.status {
  font-size: 12px;
  color: #6b7280;
  display: flex;
  align-items: center;
  gap: 5px;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22c55e;
  display: inline-block;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 18px 16px;
}
.welcome {
  text-align: center;
  padding: 50px 20px;
}
.welcome-emoji {
  font-size: 44px;
}
.welcome-title {
  font-size: 19px;
  font-weight: 700;
  color: #1f2937;
  margin-top: 12px;
}
.welcome-sub {
  font-size: 13px;
  color: #6b7280;
  margin-top: 6px;
}
.quick {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-top: 22px;
}
.quick-tag {
  cursor: pointer;
}
.borrow-item {
  padding: 12px 0;
  border-bottom: 1px dashed #e5e7eb;
}
.b-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
}
.b-meta {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
