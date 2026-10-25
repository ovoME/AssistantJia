<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listDataFiles, uploadDataFile } from '@/api'
import type { DataFileInfo } from '@/types'
import { useToast } from '@/composables/useToast'
import CuState from '@/components/cu/CuState.vue'

const router = useRouter()
const toast = useToast()

const files = ref<DataFileInfo[]>([])
const loading = ref(true)
const error = ref('')
const dragging = ref(false)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const kindLabel: Record<DataFileInfo['kind'], string> = {
  borrow: '借阅流水',
  catalog: '馆藏目录',
  gate: '门禁',
  seat: '座位',
  room: '研讨室',
  other: '其他',
}
const kindColor: Record<DataFileInfo['kind'], string> = {
  borrow: '#0f9d8f',
  catalog: '#007aff',
  gate: '#f59e0b',
  seat: '#a78bfa',
  room: '#f472b6',
  other: '#6b7d87',
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    files.value = await listDataFiles()
  } catch (e) {
    error.value = (e as Error).message || '数据文件列表加载失败'
  } finally {
    loading.value = false
  }
}

function pick() {
  fileInput.value?.click()
}

function onPick(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (f) doUpload(f)
  input.value = ''
}

async function doUpload(file: File) {
  uploading.value = true
  try {
    const info = await uploadDataFile(file)
    files.value.unshift(info)
    toast.success(`已接收 ${file.name}`)
    // mock 模式下 2 秒后把状态从 processing 变成 ready
    setTimeout(async () => {
      const idx = files.value.findIndex((f) => f.id === info.id)
      if (idx >= 0) {
        files.value[idx] = { ...files.value[idx], status: 'ready', rows: Math.round(2000 + Math.random() * 30000), message: '已入库（演示数据）' }
      }
    }, 2000)
  } catch (e) {
    toast.error((e as Error).message || '上传失败')
  } finally {
    uploading.value = false
  }
}

function onDrop(e: DragEvent) {
  dragging.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) doUpload(f)
}

function fmtDate(iso: string) {
  try {
    const d = new Date(iso)
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return iso
  }
}

onMounted(load)
</script>

<template>
  <div class="admin-page">
    <header class="topbar lg lg-r22">
      <span class="lg-inner"></span>
      <div class="brand">
        <div class="logo">🗂️</div>
        <div class="brand-text">
          <div class="brand-name">小嘉 · 数据管理</div>
          <div class="brand-sub">导入与查看馆方开放数据</div>
        </div>
      </div>
      <div class="topbar-actions">
        <button class="cu-btn cu-btn-plain" @click="router.push('/admin')">返回看板</button>
        <button class="cu-btn cu-btn-plain" @click="router.push('/')">返回读者端</button>
      </div>
    </header>

    <div class="content">
      <!-- 上传区 -->
      <div
        class="upload-zone lg lg-r22 cu-pop"
        :class="{ dragging }"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
        @click="pick"
      >
        <span class="lg-inner"></span>
        <div class="upload-icon">{{ uploading ? '⏳' : '📤' }}</div>
        <div class="upload-title">{{ uploading ? '正在上传…' : dragging ? '松开以上传' : '拖拽数据文件到这里，或点击选择' }}</div>
        <div class="upload-hint">支持 .xlsx / .csv，借阅流水、馆藏目录、门禁等数据</div>
        <input ref="fileInput" type="file" accept=".xlsx,.xls,.csv" hidden @change="onPick" />
      </div>

      <!-- 已上传文件 -->
      <div class="section-head">
        <h3>已接入数据</h3>
        <button class="cu-btn cu-btn-plain cu-btn-sm" @click="load" :disabled="loading">刷新</button>
      </div>

      <template v-if="loading">
        <div v-for="i in 2" :key="i" class="lg lg-r22 skeleton-block">
          <div class="sk sk-row"></div>
        </div>
      </template>
      <CuState v-else-if="error" type="error" :message="error" @retry="load" />
      <div v-else-if="!files.length" class="lg lg-r22 empty-block">
        <span class="lg-inner"></span>
        <div class="empty-icon">📭</div>
        <div class="empty-text">还没有数据文件，先上传一份借阅数据试试</div>
      </div>
      <div v-else class="file-list">
        <div v-for="f in files" :key="f.id" class="lg lg-r22 file-row cu-pop">
          <span class="lg-inner"></span>
          <div class="file-ico" :style="{ background: kindColor[f.kind] + '1e', color: kindColor[f.kind] }">
            {{ f.kind === 'borrow' ? '📚' : f.kind === 'catalog' ? '📖' : f.kind === 'gate' ? '🚪' : f.kind === 'seat' ? '💺' : f.kind === 'room' ? '🚪' : '📄' }}
          </div>
          <div class="file-main">
            <div class="file-name">{{ f.filename }}</div>
            <div class="file-meta">
              <span class="cu-tag" :style="{ background: kindColor[f.kind] + '1e', color: kindColor[f.kind] }">{{ kindLabel[f.kind] }}</span>
              <span v-if="f.rows != null" class="meta">{{ f.rows.toLocaleString() }} 行</span>
              <span class="meta">{{ f.size_kb >= 1024 ? (f.size_kb / 1024).toFixed(1) + ' MB' : f.size_kb + ' KB' }}</span>
              <span class="meta">{{ fmtDate(f.uploaded_at) }}</span>
            </div>
            <div v-if="f.message" class="file-msg">{{ f.message }}</div>
          </div>
          <div class="file-status" :class="f.status">
            <span class="dot"></span>
            {{ f.status === 'ready' ? '已就绪' : f.status === 'processing' ? '处理中' : '失败' }}
          </div>
        </div>
      </div>

      <!-- 说明卡 -->
      <div class="lg lg-r22 note-card">
        <span class="lg-inner"></span>
        <h4>📌 数据接入说明</h4>
        <ul>
          <li>支持的字段：证件号、索书号、财产号、题名、责任者、ISBN、出版社（与馆方开放数据一致）</li>
          <li>上传后会自动去重、分类统计，并用于推荐和采购建议</li>
          <li>借阅流水如果带有借阅日期，趋势图会自动生成</li>
          <li>文件仅用于本项目演示，不会上传到第三方</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-page { position: relative; z-index: 2; min-height: 100vh; }

.topbar {
  position: sticky;
  top: 12px;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 12px 16px 4px;
  padding: 10px 18px;
  min-height: 60px;
}
.topbar-actions { display: flex; gap: 8px; align-items: center; }
.brand { display: flex; align-items: center; gap: 12px; }
.logo {
  width: 42px; height: 42px; border-radius: 50%;
  background: linear-gradient(135deg, #93c5fd, #007aff);
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; box-shadow: 0 4px 10px rgba(0, 122, 255, 0.3);
}
.brand-name { font-size: 16px; font-weight: 700; color: var(--ink); }
.brand-sub { font-size: 12px; color: var(--ink-3); margin-top: 2px; }

.content {
  max-width: 900px;
  margin: 0 auto;
  padding: 16px 20px 44px;
}

.upload-zone {
  position: relative;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  margin-bottom: 24px;
  transition: transform 0.15s ease, border-color 0.15s ease;
}
.upload-zone:hover { transform: scale(1.005); }
.upload-zone.dragging {
  border-color: var(--blue, #007aff);
  background: rgba(0, 122, 255, 0.08);
}
.upload-icon { font-size: 40px; margin-bottom: 10px; }
.upload-title { font-size: 16px; font-weight: 700; color: var(--ink); margin-bottom: 6px; }
.upload-hint { font-size: 13px; color: var(--ink-3); }

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 8px 0 12px;
}
.section-head h3 { font-size: 15px; font-weight: 700; color: var(--ink); margin: 0; }

.file-list { display: flex; flex-direction: column; gap: 12px; }
.file-row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
}
.file-ico {
  width: 44px; height: 44px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; flex-shrink: 0;
}
.file-main { flex: 1; min-width: 0; }
.file-name {
  font-size: 14px; font-weight: 600; color: var(--ink);
  margin-bottom: 4px; word-break: break-all;
}
.file-meta { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 4px; }
.meta { font-size: 12px; color: var(--ink-3); }
.cu-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}
.file-msg { font-size: 12px; color: var(--ink-2); }

.file-status {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600; flex-shrink: 0;
}
.file-status .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #c7ccd1;
}
.file-status.ready { color: #0f9d8f; }
.file-status.ready .dot { background: #0f9d8f; }
.file-status.processing { color: #f59e0b; }
.file-status.processing .dot { background: #f59e0b; animation: pulse 1.2s ease-in-out infinite; }
.file-status.error { color: #ff3b30; }
.file-status.error .dot { background: #ff3b30; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.empty-block {
  position: relative;
  padding: 40px 20px;
  text-align: center;
}
.empty-icon { font-size: 40px; margin-bottom: 10px; }
.empty-text { font-size: 14px; color: var(--ink-3); }

.note-card {
  position: relative;
  margin-top: 24px;
  padding: 16px 20px;
}
.note-card h4 { font-size: 14px; font-weight: 700; color: var(--ink); margin: 0 0 8px; }
.note-card ul { margin: 0; padding-left: 20px; }
.note-card li { font-size: 13px; color: var(--ink-2); line-height: 1.9; }

.skeleton-block { padding: 18px 20px; }
.sk {
  background: linear-gradient(90deg, rgba(180,195,205,0.25) 25%, rgba(180,195,205,0.45) 50%, rgba(180,195,205,0.25) 75%);
  background-size: 200% 100%;
  animation: sk-shimmer 1.4s ease-in-out infinite;
  border-radius: 8px;
}
.sk-row { width: 100%; height: 60px; }
@keyframes sk-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
