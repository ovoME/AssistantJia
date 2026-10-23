<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import CuSheet from '@/components/cu/CuSheet.vue'
import CuState from '@/components/cu/CuState.vue'
import BookCard from '@/components/chat/BookCard.vue'
import { getMyBorrows, renewBook, getRecommend, searchBooks } from '@/api'
import type { BorrowRecord, RecommendBook, Book } from '@/types'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const chat = useChatStore()
const toast = useToast()

const sheetShow = ref(false)
const borrows = ref<BorrowRecord[]>([])
const borrowLoading = ref(false)
const borrowError = ref('')
const recommends = ref<RecommendBook[]>([])

// 馆藏搜索
const searchShow = ref(false)
const searchQuery = ref('')
const searchResults = ref<Book[]>([])
const searchLoading = ref(false)
const searchSearched = ref(false)

const quickQuestions = ['帮我找《三体》', '图书能借多少天？', '怎么续借？', '我想找物流相关的书']
const messagesEl = ref<HTMLElement | null>(null)

onMounted(async () => {
  try {
    recommends.value = await getRecommend(chat.readerId, 4)
  } catch {
    // 推荐位加载失败静默忽略
  }
})

async function doSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  searchLoading.value = true
  searchSearched.value = true
  try {
    searchResults.value = await searchBooks(q, 8)
  } catch (e) {
    toast.error((e as Error).message || '搜索失败，请稍后重试')
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

// 搜索模态打开时自动聚焦输入框
watch(searchShow, async (v) => {
  if (v) {
    await nextTick()
    document.querySelector<HTMLInputElement>('.search-input')?.focus()
  }
})

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
function isDueSoon(b: BorrowRecord): boolean {
  if (b.is_overdue) return false
  const days = Math.ceil((new Date(b.due_date).getTime() - Date.now()) / 86400000)
  return days <= 7
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
        <button class="cu-btn cu-btn-plain search-btn" @click="searchShow = true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/>
            <path d="m20 20-3.5-3.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          搜书
        </button>
        <button v-if="chat.messages.length" class="cu-btn cu-btn-plain" @click="chat.reset()">新对话</button>
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

        <!-- 个性化推荐（仅在欢迎页展示） -->
        <div v-if="recommends.length" class="recommend cu-fade-in" style="animation-delay: 0.5s">
          <div class="rec-title">✨ 为你推荐</div>
          <div class="rec-row">
            <button
              v-for="r in recommends"
              :key="r.isbn"
              class="lg lg-tap rec-card"
              @click="onSend(`我想找《${r.title}》`)"
            >
              <span class="lg-inner"></span>
              <div class="rec-book">{{ r.title }}</div>
              <div class="rec-author">{{ r.author }}</div>
              <div class="rec-reason">{{ r.reason }}</div>
            </button>
          </div>
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
            <span class="cu-tag" :class="b.is_overdue ? 'cu-tag-red' : isDueSoon(b) ? 'cu-tag-orange' : 'cu-tag-green'">
              {{ b.is_overdue ? '已逾期' : isDueSoon(b) ? '即将到期' : '借阅中' }}
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

    <!-- 馆藏搜索 -->
    <CuSheet v-model="searchShow" title="馆藏搜索">
      <div class="search-box lg lg-r14">
        <span class="lg-inner"></span>
        <input
          v-model="searchQuery"
          class="search-input"
          placeholder="输入书名 / 作者 / 关键词…"
          @keydown.enter="doSearch"
        />
        <button class="cu-btn cu-btn-teal cu-btn-sm" @click="doSearch" :disabled="!searchQuery.trim()">搜索</button>
      </div>

      <CuState v-if="searchLoading" type="loading" message="正在检索馆藏…" />
      <template v-else-if="searchSearched">
        <div v-if="searchResults.length" class="search-results">
          <BookCard v-for="b in searchResults" :key="b.isbn" :book="b" :reader-id="chat.readerId" />
        </div>
        <CuState v-else type="empty" message="没找到相关图书，换个关键词试试，或直接问小嘉～" />
      </template>
      <CuState v-else type="empty" message="输入关键词开始检索馆藏" />
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

/* 个性化推荐位 */
.recommend { width: 100%; max-width: 560px; }
.rec-title { font-size: 14px; font-weight: 700; color: var(--ink-2); margin-bottom: 12px; }
.rec-row {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 6px;
  scroll-snap-type: x mandatory;
}
.rec-card {
  flex: 0 0 200px;
  scroll-snap-align: start;
  padding: 14px 16px;
  border-radius: 18px;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: inset 0 1.5px 1px rgba(255,255,255,1), 0 4px 12px rgba(20,50,60,0.08);
}
.rec-book { font-size: 14px; font-weight: 700; color: var(--ink); line-height: 1.4; }
.rec-author { font-size: 12px; color: var(--ink-3); }
.rec-reason { font-size: 12px; color: var(--ink-2); line-height: 1.5; margin-top: 4px; }

.quick-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }

/* 馆藏搜索 */
.search-btn { display: inline-flex; align-items: center; gap: 4px; }
.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 6px 16px;
  margin-bottom: 16px;
}
.search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: var(--ink);
  padding: 8px 0;
}
.search-input::placeholder { color: var(--ink-3); }
.search-results { display: flex; flex-direction: column; gap: 12px; }
</style>
