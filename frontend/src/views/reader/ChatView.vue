<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import CuSheet from '@/components/cu/CuSheet.vue'
import CuState from '@/components/cu/CuState.vue'
import { getMyBorrows, renewBook } from '@/api'
import type { BorrowRecord } from '@/types'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const chat = useChatStore()
const toast = useToast()

const sheetShow = ref(false)
const borrows = ref<BorrowRecord[]>([])
const borrowLoading = ref(false)
const borrowError = ref('')

const quickQuestions = ['帮我找《三体》', '图书能借多少天？', '怎么续借？', '我想找物流相关的书']
const messagesEl = ref<HTMLElement | null>(null)

async function scrollToBottom() {
  await nextTick()
  const el = messagesEl.value
  if (el) el.scrollTop = el.scrollHeight
}
watch(
  () => chat.messages.map((m) => m.content).join('') + chat.messages.length,
  scrollToBottom,
)

async function onSend(text: string) {
  await chat.send(text)
  scrollToBottom()
}

async function openBorrows() {
  sheetShow.value = true
  borrowLoading.value = true
  borrowError.value = ''
  try {
    borrows.value = await getMyBorrows(chat.readerId)
  } catch (e) {
    borrowError.value = (e as Error).message || '借阅记录加载失败，请稍后重试'
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
    toast.success(`续借成功，新到期日 ${r.new_due_date}`)
  } catch (e) {
    toast.error((e as Error).message || '续借失败')
  }
}
</script>

<template>
  <div class="reader-page">
    <!-- 悬浮液态玻璃导航栏 -->
    <header class="topbar lg lg-r22">
      <span class="lg-inner"></span>
      <div class="brand">
        <div class="avatar">嘉</div>
        <div class="brand-text">
          <div class="brand-name">小嘉 · 图书馆智能馆员</div>
          <div class="brand-sub"><span class="dot"></span>在线 · 有问题尽管问</div>
        </div>
      </div>
      <div class="actions">
        <button class="cu-btn cu-btn-plain" @click="openBorrows">我的借阅</button>
        <button class="cu-btn cu-btn-plain" @click="router.push('/admin')">管理端</button>
      </div>
    </header>

    <main ref="messagesEl" class="messages">
      <!-- 欢迎页 -->
      <div v-if="chat.messages.length === 0" class="welcome">
        <div class="hello cu-fade-in">
          <div class="logo">📚</div>
          <h1>你好，我是小嘉！</h1>
          <p>能帮你查馆藏、找架位、续借、预约，也懂借阅规则。</p>
        </div>
        <div class="quick">
          <button
            v-for="(q, i) in quickQuestions"
            :key="q"
            class="lg lg-tap chip cu-pop"
            :style="{ animationDelay: 0.08 * i + 0.1 + 's', '--lg-tr': '18%' }"
            @click="onSend(q)"
          >
            <span class="lg-inner"></span>{{ q }}
          </button>
        </div>
      </div>

      <!-- 消息流 -->
      <MessageBubble
        v-for="m in chat.messages"
        :key="m.id"
        :message="m"
        :reader-id="chat.readerId"
        @retry="chat.retry"
      />
    </main>

    <!-- 悬浮液态玻璃输入栏 -->
    <div class="input-dock">
      <ChatInput :loading="chat.loading" @send="onSend" @stop="chat.stop" />
    </div>

    <!-- 我的借阅 -->
    <CuSheet v-model="sheetShow" title="我的借阅">
      <CuState v-if="borrowLoading" type="loading" message="正在加载借阅记录…" />
      <CuState v-else-if="borrowError" type="error" :message="borrowError" @retry="openBorrows" />
      <div v-else-if="borrows.length" class="borrow-list">
        <div v-for="b in borrows" :key="b.book_id" class="borrow-item lg-panel">
          <div class="b-title">{{ b.title }}</div>
          <div class="b-meta">
            <span>应还：{{ b.due_date }}</span>
            <span class="cu-tag" :class="b.is_overdue ? 'cu-tag-red' : 'cu-tag-green'">
              {{ b.is_overdue ? '已逾期' : '借阅中' }}
            </span>
          </div>
          <div class="b-meta">已续借 {{ b.renew_count }} 次</div>
          <button
            class="cu-btn cu-btn-teal cu-btn-sm"
            :disabled="b.renew_count >= 1"
            @click="onRenew(b)"
          >
            {{ b.renew_count >= 1 ? '不可再续' : '一键续借' }}
          </button>
        </div>
      </div>
      <CuState v-else type="empty" message="暂无借阅记录，问问小嘉找本书吧～" />
    </CuSheet>
  </div>
</template>

<style scoped>
.reader-page {
  position: relative;
  z-index: 2;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  max-width: 768px;
  margin: 0 auto;
}

.topbar {
  position: sticky;
  top: 12px;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 12px 12px 4px;
  padding: 10px 14px;
  min-height: 62px;
}
.brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
.avatar {
  width: 42px; height: 42px; border-radius: 50%;
  background: linear-gradient(135deg, #14b8a6, #0f6e7c);
  color: #fff; font-weight: 700; font-size: 18px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 10px rgba(15, 157, 143, 0.4);
}
.brand-text { min-width: 0; }
.brand-name { font-size: 16px; font-weight: 700; color: var(--ink); }
.brand-sub {
  font-size: 12px; color: var(--ink-3); margin-top: 2px;
  display: flex; align-items: center; gap: 6px;
}
.dot { width: 7px; height: 7px; border-radius: 50%; background: #18a058; box-shadow: 0 0 0 3px rgba(24, 160, 88, 0.18); }
.actions { display: flex; gap: 2px; flex-shrink: 0; }

.messages {
  flex: 1;
  width: 100%;
  padding: 22px 16px 120px;
  display: flex;
  flex-direction: column;
}

.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 34px;
  text-align: center;
}
.hello .logo { font-size: 58px; }
.hello h1 { font-size: 27px; font-weight: 700; margin: 16px 0 10px; color: var(--ink); }
.hello p { color: var(--ink-2); font-size: 14.5px; line-height: 1.7; }
.quick { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; }
.chip { font-size: 14px; font-weight: 600; color: var(--ink); padding: 11px 18px; }

.input-dock {
  position: fixed;
  bottom: 18px;
  left: 50%;
  transform: translateX(-50%);
  width: min(94vw, 768px);
  z-index: 30;
}

.loading-line { display: flex; align-items: center; gap: 10px; color: var(--ink-3); padding: 12px 0; }
.borrow-list { display: flex; flex-direction: column; gap: 12px; }
.borrow-item { padding: 14px 16px; border-radius: 16px; }
.b-title { font-size: 15px; font-weight: 600; margin-bottom: 8px; color: var(--ink); }
.b-meta { display: flex; align-items: center; gap: 10px; color: var(--ink-3); font-size: 13px; margin-bottom: 8px; }
.empty { text-align: center; color: var(--ink-3); padding: 26px 0; }
</style>
