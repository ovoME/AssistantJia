<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import echarts from '@/utils/echarts'
import type { ECharts } from '@/utils/echarts'
import { getAdminSummary, getHotBooks, getCategories, getPublishers, getBorrowTrend, getPurchaseAdvice } from '@/api'
import type { AdminSummary, BookStat, CategoryStat, BorrowTrendPoint } from '@/types'
import { useToast } from '@/composables/useToast'
import CuState from '@/components/cu/CuState.vue'

const router = useRouter()
const toast = useToast()

const loading = ref(true)
const summary = ref<AdminSummary>({
  total_borrows: 0,
  total_readers: 0,
  total_titles: 0,
  avg_borrow_per_reader: 0,
})
const hotBooks = ref<BookStat[]>([])
const categories = ref<CategoryStat[]>([])
const publishers = ref<BookStat[]>([])
const trend = ref<BorrowTrendPoint[]>([])

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
    const [s, h, c, p, t] = await Promise.all([getAdminSummary(), getHotBooks(8), getCategories(), getPublishers(10), getBorrowTrend(30)])
    summary.value = s
    hotBooks.value = h
    categories.value = c
    publishers.value = p
    trend.value = t
    // 先关闭 loading，让内容区（含图表容器）真正渲染进 DOM，再 nextTick 初始化图表
    loading.value = false
    await nextTick()
    renderCharts()
  } catch (e) {
    loading.value = false
    error.value = (e as Error).message || '运营数据加载失败，请稍后重试'
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
  // 出版社 TOP10 横条图
  if (publisherChartRef.value) {
    publisherChart = echarts.init(publisherChartRef.value)
    const names = publishers.value.map((p) => p.title)
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
  // 借阅趋势折线图（近30天）
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
  a.download = `热门图书TOP8_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  toast.success('CSV 已导出')
}

async function genAdvice() {
  adviceLoading.value = true
  advice.value = ''
  try {
    // 走 api 层（mock 或真实 POST /api/admin/purchase-advice），保留打字机效果
    const text = await getPurchaseAdvice()
    for (const ch of text) {
      if (!adviceLoading.value) break
      advice.value += ch
      await new Promise((r) => setTimeout(r, 10))
    }
    toast.success('采购建议已生成')
  } catch (e) {
    toast.error((e as Error).message || '采购建议生成失败，请稍后重试')
  } finally {
    adviceLoading.value = false
  }
}

onMounted(() => {
  loadData()
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
          <div class="brand-name">小嘉 · 馆藏运营看板</div>
          <div class="brand-sub">运营数据 · 仅馆员可见</div>
        </div>
      </div>
      <div class="topbar-actions">
        <button class="cu-btn cu-btn-plain" @click="loadData" :disabled="loading">
          {{ loading ? '刷新中…' : '刷新数据' }}
        </button>
        <button class="cu-btn cu-btn-plain" @click="router.push('/')">返回读者端</button>
      </div>
    </header>

    <div class="content">
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
        <div class="lg-panel chart-card skeleton-block">
          <div class="sk sk-title"></div>
          <div class="sk sk-chart"></div>
        </div>
      </template>
      <CuState v-else-if="error" type="error" :message="error" @retry="loadData" />
      <template v-else>
        <div class="stat-row">
          <div
            v-for="(s, i) in [
              { label: '总借阅量', value: summary.total_borrows.toLocaleString(), color: '#0f9d8f', icon: '📚' },
              { label: '活跃读者', value: summary.total_readers.toLocaleString(), color: '#007aff', icon: '👥' },
              { label: '图书种数', value: summary.total_titles.toLocaleString(), color: '#f59e0b', icon: '📖' },
              { label: '人均借阅（册）', value: summary.avg_borrow_per_reader, color: '#a78bfa', icon: '🔄' },
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
          <h3>近30天借阅趋势</h3>
          <div class="chart-wrap">
            <div ref="trendChartRef" class="chart"></div>
            <div v-if="!trend.length" class="chart-empty">暂无趋势数据</div>
          </div>
        </div>

        <div class="chart-row">
          <div class="lg-panel chart-card cu-pop" style="animation-delay:0.12s">
            <div class="card-head">
              <h3>热门图书 TOP8</h3>
              <button class="cu-btn cu-btn-plain cu-btn-sm" @click="exportHotBooks">导出 CSV</button>
            </div>
            <div class="chart-wrap">
              <div ref="hotChartRef" class="chart tall"></div>
              <div v-if="!hotBooks.length" class="chart-empty">暂无热门图书数据</div>
            </div>
          </div>
          <div class="lg-panel chart-card cu-pop" style="animation-delay:0.2s">
            <h3>借阅分类占比</h3>
            <div class="chart-wrap">
              <div ref="pieChartRef" class="chart tall"></div>
              <div v-if="!categories.length" class="chart-empty">暂无分类数据</div>
            </div>
          </div>
        </div>

        <div class="lg-panel chart-card cu-pop" style="animation-delay:0.26s">
          <h3>出版社 TOP10</h3>
          <div class="chart-wrap">
            <div ref="publisherChartRef" class="chart tall"></div>
            <div v-if="!publishers.length" class="chart-empty">暂无出版社数据</div>
          </div>
        </div>

        <div class="lg-panel advice-card cu-pop" style="animation-delay:0.28s">
          <div class="advice-head">
            <h3>🤖 AI 智能采购建议</h3>
            <button
              class="cu-btn cu-btn-teal cu-btn-sm"
              :disabled="adviceLoading"
              @click="genAdvice"
            >
              {{ advice ? '重新生成' : '生成采购建议' }}
            </button>
          </div>
          <div v-if="!advice && !adviceLoading" class="advice-empty">
            点击右上角按钮，小嘉将基于借阅数据自动生成复购、剔旧与学科缺口建议。
          </div>
          <div v-if="adviceLoading && !advice" class="loading-line">
            <span class="cu-spinner"><span></span><span></span><span></span></span>
            小嘉正在分析近期借阅数据…
          </div>
          <pre v-if="advice" class="advice-text">{{ advice }}</pre>
        </div>
      </template>
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
  background: linear-gradient(135deg, #14b8a6, #0f6e7c);
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; box-shadow: 0 4px 10px rgba(15, 157, 143, 0.4);
}
.brand-name { font-size: 16px; font-weight: 700; color: var(--ink); }
.brand-sub { font-size: 12px; color: var(--ink-3); margin-top: 2px; }

.content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px 20px 44px;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.stat-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.stat-ico {
  width: 38px; height: 38px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 19px; margin-bottom: 2px;
}
.stat-num {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.5px;
  font-variant-numeric: tabular-nums;
}
.stat-label { font-size: 13px; color: var(--ink-2); font-weight: 600; }

.chart-row {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 16px;
  margin: 16px 0;
}
.chart-card { padding: 18px 18px 12px; }
.chart-card h3 { font-size: 15px; font-weight: 700; color: var(--ink); margin: 0 0 8px; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.card-head h3 { margin: 0; }
.chart-wrap { position: relative; }
.chart { width: 100%; height: 320px; }
.chart.tall { height: 340px; }
.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-3);
  font-size: 13px;
  text-align: center;
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

@media (max-width: 760px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .chart-row { grid-template-columns: 1fr; }
}
</style>
