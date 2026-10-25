<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import echarts from '@/utils/echarts'
import type { ECharts } from '@/utils/echarts'
import {
  getAdminSummary,
  getHotBooks,
  getCategories,
  getPublishers,
  getBorrowTrend,
  getPurchaseAdvice,
  getUsage,
  getDataSources,
  uploadDataset,
  quickSyncDataset,
  quickSyncAllDatasets,
  type UsageReport,
  type DataSourceItem
} from '@/api'
import type { AdminSummary, BookStat, CategoryStat, BorrowTrendPoint, PublisherStat } from '@/types'
import { useToast } from '@/composables/useToast'
import CuState from '@/components/cu/CuState.vue'

const router = useRouter()
const toast = useToast()
const adminToken = ref(sessionStorage.getItem('xiaojia.adminToken') || 'admin-secret-token')
if (!sessionStorage.getItem('xiaojia.adminToken')) {
  sessionStorage.setItem('xiaojia.adminToken', adminToken.value)
}

function applyAdminToken() {
  if (adminToken.value) sessionStorage.setItem('xiaojia.adminToken', adminToken.value)
  else sessionStorage.removeItem('xiaojia.adminToken')
  loadData()
}

// 页面 Tab: 看板大屏 vs 多源数据导入
const currentTab = ref<'dashboard' | 'data_import'>('dashboard')

const loading = ref(true)
const summary = ref<AdminSummary>({
  total_borrows: 0,
  total_readers: 0,
  total_titles: 0,
  avg_borrow_per_reader: 0,
})
const hotBooks = ref<BookStat[]>([])
const categories = ref<CategoryStat[]>([])
const publishers = ref<PublisherStat[]>([])
const trend = ref<BorrowTrendPoint[]>([])
const usage = ref<UsageReport>({ dataset_label: 'unknown', datasets: {}, limitations: [] })

// 多源数据源状态
const dataSources = ref<DataSourceItem[]>([])
const dataLoading = ref(false)
const syncingAll = ref(false)
const operatingId = ref<string | null>(null)

const hotChartRef = ref<HTMLElement | null>(null)
const pieChartRef = ref<HTMLElement | null>(null)
const publisherChartRef = ref<HTMLElement | null>(null)
const trendChartRef = ref<HTMLElement | null>(null)
let hotChart: ECharts | null = null
let pieChart: ECharts | null = null
let publisherChart: ECharts | null = null
let trendChart: ECharts | null = null

const adviceLoading = ref(false)
const advice = ref('')
const error = ref('')

const palette = ['#14b8a6', '#007aff', '#f59e0b', '#a78bfa', '#f472b6', '#34d399', '#60a5fa', '#fb923c']

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [s, h, c, p, t, u] = await Promise.all([
      getAdminSummary(),
      getHotBooks(10),
      getCategories(),
      getPublishers(10),
      getBorrowTrend(30),
      getUsage()
    ])
    summary.value = s
    hotBooks.value = h
    categories.value = c
    publishers.value = p
    trend.value = t
    usage.value = u
    loading.value = false
    await nextTick()
    renderCharts()
  } catch (e) {
    loading.value = false
    error.value = (e as Error).message || '运营数据加载失败，请稍后重试'
  }
}

async function loadDataSources() {
  dataLoading.value = true
  try {
    dataSources.value = await getDataSources()
  } catch (e: any) {
    console.error('加载数据源失败', e)
  } finally {
    dataLoading.value = false
  }
}

async function handleFileUpload(categoryId: string, event: Event) {
  const target = event.target as HTMLInputElement
  if (!target.files || !target.files[0]) return
  const file = target.files[0]
  operatingId.value = categoryId
  try {
    const res = await uploadDataset(categoryId, file)
    toast.success(res.message || '上传并解析成功！')
    await loadDataSources()
  } catch (e: any) {
    toast.error('上传失败：' + (e.message || '格式不支持'))
  } finally {
    operatingId.value = null
    target.value = ''
  }
}

async function handleQuickSync(categoryId: string) {
  operatingId.value = categoryId
  try {
    const res = await quickSyncDataset(categoryId)
    toast.success(res.message || '一键同步解析完成！')
    await loadDataSources()
  } catch (e: any) {
    toast.error('同步失败：' + (e.message || '文件不存在'))
  } finally {
    operatingId.value = null
  }
}

async function handleQuickSyncAll() {
  syncingAll.value = true
  try {
    await quickSyncAllDatasets()
    toast.success('全量 8 项官方数据源已全部同步并构建知识索引！')
    await loadDataSources()
  } catch (e: any) {
    toast.error('全量同步失败：' + (e.message || '网络异常'))
  } finally {
    syncingAll.value = false
  }
}

function triggerUpload(id: string) {
  document.getElementById('file-' + id)?.click()
}

function switchTab(tab: 'dashboard' | 'data_import') {
  currentTab.value = tab
  if (tab === 'data_import') {
    loadDataSources()
  } else {
    nextTick(() => {
      renderCharts()
    })
  }
}

function renderCharts() {
  if (hotChartRef.value) {
    hotChart = echarts.init(hotChartRef.value)
    const names = hotBooks.value.map((b) => b.title.slice(0, 12))
    const counts = hotBooks.value.map((b) => b.count)
    hotChart.setOption({
      grid: { left: 10, right: 36, top: 16, bottom: 10, containLabel: true },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(20,40,55,0.08)' } },
        axisLabel: { color: '#6b7d87' },
      },
      yAxis: {
        type: 'category',
        data: names.slice().reverse(),
        axisLine: { lineStyle: { color: '#c2ccd2' } },
        axisLabel: { color: '#42545e', fontSize: 11 },
      },
      series: [
        {
          type: 'bar',
          data: counts.slice().reverse(),
          barWidth: '58%',
          itemStyle: {
            borderRadius: [0, 8, 8, 0],
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 1, y2: 0,
              colorStops: [
                { offset: 0, color: '#2dd4bf' },
                { offset: 1, color: '#0f9d8f' },
              ],
            },
          },
          label: { show: true, position: 'right', fontSize: 11, color: '#42545e' },
        },
      ],
    })
  }
  if (pieChartRef.value) {
    pieChart = echarts.init(pieChartRef.value)
    const totalCats = categories.value.reduce((s, c) => s + c.count, 0)
    pieChart.setOption({
      legend: { bottom: 0, icon: 'circle', textStyle: { color: '#42545e', fontSize: 11 } },
      title: {
        text: totalCats.toLocaleString(),
        subtext: '总借阅',
        left: 'center',
        top: '34%',
        textAlign: 'center',
        textStyle: { fontSize: 20, fontWeight: 700, color: '#16262e' },
        subtextStyle: { fontSize: 11, color: '#6b7d87' },
      },
      series: [
        {
          type: 'pie',
          radius: ['48%', '70%'],
          center: ['50%', '44%'],
          data: categories.value.map((c, i) => ({
            name: c.category_name || c.category,
            value: c.count,
            itemStyle: { color: palette[i % palette.length], borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          })),
          label: { fontSize: 11, color: '#42545e', overflow: 'none', width: 80 },
        },
      ],
    })
  }
  if (publisherChartRef.value) {
    publisherChart = echarts.init(publisherChartRef.value)
    const names = publishers.value.map((p) => p.publisher || '出版社未提供')
    const counts = publishers.value.map((p) => p.count)
    publisherChart.setOption({
      grid: { left: 10, right: 36, top: 16, bottom: 10, containLabel: true },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(20,40,55,0.08)' } },
        axisLabel: { color: '#6b7d87' },
      },
      yAxis: {
        type: 'category',
        data: names.slice().reverse(),
        axisLine: { lineStyle: { color: '#c2ccd2' } },
        axisLabel: { color: '#42545e', fontSize: 11 },
      },
      series: [
        {
          type: 'bar',
          data: counts.slice().reverse(),
          barWidth: '58%',
          itemStyle: {
            borderRadius: [0, 8, 8, 0],
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 1, y2: 0,
              colorStops: [
                { offset: 0, color: '#93c5fd' },
                { offset: 1, color: '#007aff' },
              ],
            },
          },
          label: { show: true, position: 'right', fontSize: 11, color: '#42545e' },
        },
      ],
    })
  }
  if (trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value)
    trendChart.setOption({
      grid: { left: 10, right: 20, top: 20, bottom: 10, containLabel: true },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: trend.value.map((p) => p.date),
        axisLine: { lineStyle: { color: '#c2ccd2' } },
        axisLabel: { color: '#6b7d87', fontSize: 10, interval: 4 },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(20,40,55,0.08)' } },
        axisLabel: { color: '#6b7d87', fontSize: 11 },
      },
      series: [
        {
          type: 'line',
          data: trend.value.map((p) => p.count),
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 2.5, color: '#0f9d8f' },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(20,184,166,0.25)' },
                { offset: 1, color: 'rgba(20,184,166,0)' },
              ],
            },
          },
        },
      ],
    })
  }
}

function resize() {
  hotChart?.resize()
  pieChart?.resize()
  publisherChart?.resize()
  trendChart?.resize()
}

function exportHotBooks() {
  if (!hotBooks.value.length) return
  const header = '排名,书名,作者,借阅次数\n'
  const rows = hotBooks.value
    .map((b, i) => `${i + 1},"${b.title}","${b.author || ''}",${b.count}`)
    .join('\n')
  const csv = '\uFEFF' + header + rows
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `热门图书TOP10_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  toast.success('CSV 已导出')
}

async function genAdvice() {
  adviceLoading.value = true
  advice.value = ''
  try {
    const text = await getPurchaseAdvice()
    for (const ch of text) {
      if (!adviceLoading.value) break
      advice.value += ch
      await new Promise((r) => setTimeout(r, 12))
    }
  } catch (e) {
    advice.value = '采购建议生成失败，请重试'
  } finally {
    adviceLoading.value = false
  }
}

onMounted(() => {
  loadData()
  loadDataSources()
  window.addEventListener('resize', resize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  hotChart?.dispose()
  pieChart?.dispose()
  publisherChart?.dispose()
  trendChart?.dispose()
})
</script>

<template>
  <div class="admin-page">
    <header class="topbar lg lg-r22">
      <span class="lg-inner"></span>
      <div class="brand">
        <div class="logo">📊</div>
        <div class="brand-text">
          <div class="brand-name">小嘉 · 智慧图书馆综合管理中心</div>
          <div class="brand-sub">数据中台与智能决策 · 仅馆员可见</div>
        </div>
      </div>

      <!-- Tab 切换 -->
      <div class="tab-pill">
        <button
          :class="['tab-item', { active: currentTab === 'dashboard' }]"
          @click="switchTab('dashboard')"
        >
          📊 借阅运营大屏
        </button>
        <button
          :class="['tab-item', { active: currentTab === 'data_import' }]"
          @click="switchTab('data_import')"
        >
          📁 多源数据导入中心 (8类)
        </button>
      </div>

      <div class="topbar-actions">
        <button class="cu-btn cu-btn-plain" @click="router.push('/admin/data')">📁 文件管理页</button>
        <input
          v-model="adminToken"
          type="password"
          aria-label="管理端访问密钥"
          placeholder="管理密钥"
          autocomplete="off"
          style="max-width:110px"
          @keyup.enter="applyAdminToken"
        />
        <button
          v-if="currentTab === 'dashboard'"
          class="cu-btn cu-btn-plain"
          @click="loadData"
          :disabled="loading"
        >
          {{ loading ? '刷新中…' : '刷新看板' }}
        </button>
        <button
          v-else
          class="cu-btn cu-btn-accent"
          @click="handleQuickSyncAll"
          :disabled="syncingAll"
        >
          {{ syncingAll ? '全量同步解析中…' : '⚡ 一键同步8项官方数据' }}
        </button>
        <button class="cu-btn cu-btn-plain" @click="router.push('/')">返回读者端</button>
      </div>
    </header>

    <div class="content">
      <!-- 视图 A：原有借阅运营看板 -->
      <div v-show="currentTab === 'dashboard'">
        <!-- 骨架屏加载 -->
        <template v-if="loading">
          <div class="stat-row">
            <div v-for="i in 4" :key="i" class="lg lg-r22 skeleton-card">
              <div class="sk sk-ico"></div>
              <div class="sk sk-num"></div>
              <div class="sk sk-label"></div>
            </div>
          </div>
          <div class="lg-panel chart-card skeleton-block">
            <div class="sk sk-title"></div>
            <div class="sk sk-chart"></div>
          </div>
          <div class="chart-row">
            <div class="lg-panel chart-card skeleton-block">
              <div class="sk sk-title"></div>
              <div class="sk sk-chart"></div>
            </div>
            <div class="lg-panel chart-card skeleton-block">
              <div class="sk sk-title"></div>
              <div class="sk sk-chart"></div>
            </div>
          </div>
        </template>
        <CuState v-else-if="error" type="error" :message="error" @retry="loadData" />
        <template v-else>
          <p class="data-badge">
            数据来源：{{ summary.dataset_label === 'real' ? '真实历史借阅样本' : (summary.dataset_label === 'simulated' ? '虚构模拟样本' : '嘉庚学院开放借阅样本') }}。统计范围为当前批次，非全馆实时数据。
          </p>
          <div class="stat-row">
            <div
              v-for="(s, i) in [
                { label: '总借阅量', value: summary.total_borrows.toLocaleString(), color: '#0f9d8f', icon: '📚' },
                { label: '持证读者数', value: summary.total_readers.toLocaleString(), color: '#007aff', icon: '👥' },
                { label: '馆藏题名数', value: summary.total_titles.toLocaleString(), color: '#f59e0b', icon: '📖' },
                { label: '人均借阅（册）', value: summary.avg_borrow_per_reader ?? '—', color: '#a78bfa', icon: '🔄' },
              ]"
              :key="s.label"
              class="lg lg-r22 stat-card cu-pop"
              :style="{ animationDelay: i * 0.07 + 's', '--lg-tr': '18%' }"
            >
              <span class="lg-inner"></span>
              <div class="stat-ico" :style="{ background: s.color + '22', color: s.color }">{{ s.icon }}</div>
              <div class="stat-num" :style="{ color: s.color }">{{ s.value }}</div>
              <div class="stat-label">{{ s.label }}</div>
            </div>
          </div>

          <div class="lg-panel chart-card cu-pop" style="animation-delay:0.08s">
            <h3>借阅趋势</h3>
            <div class="chart-wrap">
              <div ref="trendChartRef" class="chart"></div>
              <div v-if="!trend.length" class="chart-empty">当前借阅数据没有日期，无法绘制趋势</div>
            </div>
          </div>

          <div class="chart-row">
            <div class="lg-panel chart-card cu-pop" style="animation-delay:0.12s">
              <div class="card-head">
                <h3>热门借阅图书 TOP10</h3>
                <button class="cu-btn cu-btn-plain cu-btn-sm" @click="exportHotBooks">导出 CSV</button>
              </div>
              <div class="chart-wrap">
                <div ref="hotChartRef" class="chart"></div>
              </div>
            </div>
            <div class="lg-panel chart-card cu-pop" style="animation-delay:0.16s">
              <div class="card-head">
                <h3>借阅中图分类分布</h3>
              </div>
              <div class="chart-wrap">
                <div ref="pieChartRef" class="chart"></div>
              </div>
            </div>
          </div>

          <div class="lg-panel chart-card cu-pop" style="animation-delay:0.2s">
            <div class="card-head">
              <h3>高频出版社分布 TOP10</h3>
            </div>
            <div class="chart-wrap">
              <div ref="publisherChartRef" class="chart"></div>
            </div>
          </div>

          <div class="lg-panel advice-card cu-pop" style="animation-delay:0.24s">
            <div class="advice-head">
              <h3>🤖 AI 智能采购与典藏决策建议</h3>
              <button class="cu-btn cu-btn-accent" :disabled="adviceLoading" @click="genAdvice">
                {{ adviceLoading ? '思考分析中…' : '生成采购决策报告' }}
              </button>
            </div>
            <div v-if="!advice && !adviceLoading" class="advice-empty">
              点击上方按钮，小嘉将基于全馆历史借阅与超额预约需求，自动生成智能增购与复本调整分析报告。
            </div>
            <div v-else class="advice-body">
              <div v-if="adviceLoading" class="loading-line">
                <span class="spinner"></span> 正在深度分析中图分类借阅频次与复本利用率…
              </div>
              <pre class="advice-text">{{ advice }}</pre>
            </div>
          </div>
        </template>
      </div>

      <!-- 视图 B：新增的多源数据导入中心 (8类数据) -->
      <div v-show="currentTab === 'data_import'" class="data-import-view">
        <div class="intro-bar lg lg-r22">
          <span class="lg-inner"></span>
          <div class="intro-content">
            <div class="intro-title">📥 嘉庚学院智慧图书馆开放数据管理中台</div>
            <div class="intro-desc">
              管理员可在此处上传与维护主办方开放的 8 大维度业务数据。数据导入后将自动进行脱敏、清洗与特征索引，读者端智能体将即时获得针对
              <strong>备考指导、学者成果、自习选座、客流错峰与研讨室</strong> 的专业问答能力！
            </div>
          </div>
          <button class="cu-btn cu-btn-accent" @click="handleQuickSyncAll" :disabled="syncingAll">
            {{ syncingAll ? '正在全量解析中…' : '⚡ 一键同步全部 8 项官方数据' }}
          </button>
        </div>

        <div class="source-grid">
          <div
            v-for="item in dataSources"
            :key="item.id"
            class="source-card lg lg-r22 cu-pop"
          >
            <span class="lg-inner"></span>
            <div class="sc-header">
              <div class="sc-icon">{{ item.icon }}</div>
              <div class="sc-title-wrap">
                <div class="sc-name">{{ item.name }}</div>
                <div class="sc-folder">目录映射: {{ item.folder_name }}</div>
              </div>
              <div :class="['sc-badge', item.is_imported ? 'badge-success' : 'badge-idle']">
                {{ item.is_imported ? '已就绪' : '未导入' }}
              </div>
            </div>

            <div class="sc-desc">{{ item.desc }}</div>

            <div class="sc-meta">
              <div class="meta-row">
                <span class="meta-label">数据规模:</span>
                <span class="meta-val highlight">{{ item.row_count ? item.row_count.toLocaleString() + ' 条' : '—' }}</span>
              </div>
              <div class="meta-row">
                <span class="meta-label">解析摘要:</span>
                <span class="meta-val">{{ item.summary }}</span>
              </div>
              <div v-if="item.imported_at" class="meta-row">
                <span class="meta-label">更新时间:</span>
                <span class="meta-val time">{{ item.imported_at }}</span>
              </div>
            </div>

            <div class="sc-actions">
              <!-- 文件上传隐藏 input -->
              <input
                :id="'file-' + item.id"
                type="file"
                accept=".xlsx,.csv"
                style="display: none"
                @change="handleFileUpload(item.id, $event)"
              />
              <button
                class="cu-btn cu-btn-plain cu-btn-sm"
                :disabled="operatingId === item.id"
                @click="triggerUpload(item.id)"
              >
                {{ operatingId === item.id ? '解析中…' : '📤 上传本地文件' }}
              </button>
              <button
                class="cu-btn cu-btn-accent cu-btn-sm"
                :disabled="operatingId === item.id"
                @click="handleQuickSync(item.id)"
              >
                {{ operatingId === item.id ? '同步中…' : '⚡ 载入样例' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-page {
  min-height: 100vh;
  background: var(--bg);
  padding: 18px 22px 40px;
  box-sizing: border-box;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}
.brand { display: flex; align-items: center; gap: 12px; }
.logo { font-size: 26px; }
.brand-name { font-size: 16px; font-weight: 700; color: var(--ink); }
.brand-sub { font-size: 11px; color: var(--ink-3); }

/* Tab 切换胶囊 */
.tab-pill {
  display: flex;
  background: rgba(0, 0, 0, 0.06);
  padding: 4px;
  border-radius: 999px;
  gap: 4px;
}
.tab-item {
  border: none;
  background: transparent;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
  cursor: pointer;
  transition: all 0.2s ease;
}
.tab-item.active {
  background: #ffffff;
  color: var(--primary, #0f9d8f);
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.data-badge {
  font-size: 12px;
  color: var(--ink-3);
  margin-bottom: 12px;
}

.content {
  max-width: 1280px;
  margin: 0 auto;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 16px;
}
.stat-card {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
}
.stat-ico {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  margin-bottom: 12px;
}
.stat-num {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.5px;
  margin-bottom: 4px;
}
.stat-label { font-size: 12px; color: var(--ink-3); }

.chart-card {
  padding: 18px 22px;
  margin-bottom: 16px;
}
.chart-card h3 {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  margin: 0 0 12px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.card-head h3 { margin: 0; }
.chart-wrap {
  width: 100%;
  height: 260px;
  position: relative;
}
.chart { width: 100%; height: 100%; }
.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-3);
  font-size: 13px;
}
.chart-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.advice-card { padding: 18px 22px; margin-top: 16px; }
.advice-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.advice-head h3 { font-size: 15px; font-weight: 700; color: var(--ink); }
.advice-empty { color: var(--ink-3); font-size: 13px; padding: 14px 0; }
.loading-line { display: flex; align-items: center; gap: 10px; color: var(--ink-3); font-size: 14px; }
.advice-text {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.9;
  color: var(--ink);
  margin: 0;
}

/* 多源数据导入界面样式 */
.data-import-view {
  animation: fadeIn 0.3s ease;
}
.intro-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  margin-bottom: 20px;
  gap: 20px;
  flex-wrap: wrap;
}
.intro-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 6px;
}
.intro-desc {
  font-size: 13px;
  color: var(--ink-2);
  line-height: 1.6;
  max-width: 820px;
}

.source-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.source-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 250px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.source-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.06);
}

.sc-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.sc-icon { font-size: 24px; }
.sc-title-wrap { flex: 1; min-width: 0; }
.sc-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sc-folder {
  font-size: 11px;
  color: var(--ink-3);
  margin-top: 2px;
}
.sc-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}
.badge-success { background: #dcfce7; color: #15803d; }
.badge-idle { background: #f3f4f6; color: #6b7280; }

.sc-desc {
  font-size: 12px;
  color: var(--ink-2);
  line-height: 1.5;
  margin-bottom: 12px;
}
.sc-meta {
  background: rgba(0, 0, 0, 0.02);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 14px;
}
.meta-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 11px;
  line-height: 1.5;
  margin-bottom: 4px;
}
.meta-row:last-child { margin-bottom: 0; }
.meta-label { color: var(--ink-3); flex-shrink: 0; }
.meta-val { color: var(--ink); }
.meta-val.highlight { font-weight: 700; color: #0f9d8f; font-size: 13px; }
.meta-val.time { font-family: monospace; color: var(--ink-3); }

.sc-actions {
  display: flex;
  gap: 8px;
}
.sc-actions button { flex: 1; }

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 骨架屏 */
.skeleton-card { padding: 18px 20px; }
.skeleton-block { padding: 18px 22px; }
.sk {
  background: linear-gradient(90deg, rgba(180,195,205,0.25) 25%, rgba(180,195,205,0.45) 50%, rgba(180,195,205,0.25) 75%);
  background-size: 200% 100%;
  animation: sk-shimmer 1.4s ease-in-out infinite;
  border-radius: 8px;
}
.sk-ico { width: 38px; height: 38px; border-radius: 12px; margin-bottom: 12px; }
.sk-num { width: 60%; height: 28px; margin-bottom: 8px; }
.sk-label { width: 40%; height: 14px; }
.sk-title { width: 35%; height: 18px; margin-bottom: 16px; }
.sk-chart { width: 100%; height: 240px; }
@keyframes sk-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@media (prefers-reduced-motion: reduce) {
  .sk { animation: none; }
}

@media (max-width: 1100px) {
  .source-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 760px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .chart-row { grid-template-columns: 1fr; }
  .source-grid { grid-template-columns: 1fr; }
}
</style>
