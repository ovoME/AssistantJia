<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getAdminSummary, getHotBooks, getCategories } from '@/api'
import type { AdminSummary, BookStat, CategoryStat } from '@/types'
import { useToast } from '@/composables/useToast'

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

const hotChartRef = ref<HTMLElement | null>(null)
const pieChartRef = ref<HTMLElement | null>(null)
let hotChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null

const adviceLoading = ref(false)
const advice = ref('')

const palette = ['#14b8a6', '#007aff', '#f59e0b', '#a78bfa', '#f472b6', '#34d399', '#60a5fa', '#fb923c']

async function loadData() {
  loading.value = true
  try {
    const [s, h, c] = await Promise.all([getAdminSummary(), getHotBooks(8), getCategories()])
    summary.value = s
    hotBooks.value = h
    categories.value = c
    await nextTick()
    renderCharts()
  } finally {
    loading.value = false
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
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: '#2dd4bf' },
              { offset: 1, color: '#0f9d8f' },
            ]),
          },
          label: { show: true, position: 'right', fontSize: 11, color: '#42545e' },
        },
      ],
    })
  }
  if (pieChartRef.value) {
    pieChart = echarts.init(pieChartRef.value)
    pieChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, icon: 'circle', textStyle: { color: '#42545e', fontSize: 11 } },
      series: [
        {
          type: 'pie',
          radius: ['42%', '68%'],
          center: ['50%', '44%'],
          data: categories.value.map((c, i) => ({
            name: c.category_name || c.category,
            value: c.count,
            itemStyle: { color: palette[i % palette.length], borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          })),
          label: { fontSize: 11, color: '#42545e' },
        },
      ],
    })
  }
}

function resize() {
  hotChart?.resize()
  pieChart?.resize()
}

const mockAdvice = `【小嘉智能采购建议 · 基于36,908条借阅数据】

1. 复购建议：建筑/土木类（TU、U类）借阅高度集中，其中《聚丙烯纤维混凝土抗裂防渗性能研究与施工工法》《砌筑工》等热门书借阅量达30+次且可借副本不足，建议各增购3-5本，缓解排队。

2. 学科缺口：物流管理（F252/F253）相关图书借阅集中且复借率高，说明该专业课程需求旺盛，建议围绕冷链物流、仓储管理、物流装备补充新版教材与实务类图书。

3. 冷门调架：部分文学旧书（I类早期版本）借阅量为0，建议结合馆藏年限评估剔旧或移至密集书库，释放黄金架位。

4. 馆藏结构：文学类（I）占比最高，工业技术（T）次之，建议保持工程类新书采购节奏，并增加计算机（TP311/TP312）类前沿图书以匹配学生技术学习需求。`

async function genAdvice() {
  adviceLoading.value = true
  advice.value = ''
  const text = mockAdvice
  for (const ch of text) {
    if (!adviceLoading.value) break
    advice.value += ch
    await new Promise((r) => setTimeout(r, 10))
  }
  adviceLoading.value = false
  toast.success('采购建议已生成')
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', resize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  hotChart?.dispose()
  pieChart?.dispose()
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
      <button class="cu-btn cu-btn-plain" @click="router.push('/')">返回读者端</button>
    </header>

    <div class="content">
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

      <div class="chart-row">
        <div class="lg-panel chart-card cu-pop" style="animation-delay:0.12s">
          <h3>热门图书 TOP8</h3>
          <div ref="hotChartRef" class="chart tall"></div>
        </div>
        <div class="lg-panel chart-card cu-pop" style="animation-delay:0.2s">
          <h3>借阅分类占比</h3>
          <div ref="pieChartRef" class="chart tall"></div>
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
.chart { width: 100%; height: 320px; }
.chart.tall { height: 340px; }

.advice-card { padding: 18px 22px; }
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

@media (max-width: 760px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .chart-row { grid-template-columns: 1fr; }
}
</style>
