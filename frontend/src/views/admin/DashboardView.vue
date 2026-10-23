<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { NButton, NCard, NSpin, useMessage } from 'naive-ui'
import { getAdminSummary, getHotBooks, getCategories } from '@/api'
import type { AdminSummary, BookStat, CategoryStat } from '@/types'

const router = useRouter()
const message = useMessage()

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

async function loadData() {
  loading.value = true
  try {
    const [s, h, c] = await Promise.all([
      getAdminSummary(),
      getHotBooks(8),
      getCategories(),
    ])
    summary.value = s
    hotBooks.value = h
    categories.value = c
    renderCharts()
  } finally {
    loading.value = false
  }
}

function renderCharts() {
  if (hotChartRef.value) {
    hotChart = echarts.init(hotChartRef.value)
    const names = hotBooks.value.map((b) => b.title.slice(0, 14))
    const counts = hotBooks.value.map((b) => b.count)
    hotChart.setOption({
      grid: { left: 10, right: 30, top: 20, bottom: 10, containLabel: true },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: names.reverse(), axisLabel: { fontSize: 11 } },
      series: [
        {
          type: 'bar',
          data: counts.reverse(),
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: '#14b8a6' },
              { offset: 1, color: '#0f9d8f' },
            ]),
            borderRadius: [0, 4, 4, 0],
          },
          label: { show: true, position: 'right', fontSize: 11 },
        },
      ],
    })
  }

  if (pieChartRef.value) {
    pieChart = echarts.init(pieChartRef.value)
    pieChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, textStyle: { fontSize: 11 } },
      series: [
        {
          type: 'pie',
          radius: ['40%', '68%'],
          center: ['50%', '45%'],
          data: categories.value.map((c) => ({
            name: c.category_name || c.category,
            value: c.count,
          })),
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { fontSize: 11 },
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
  try {
    // 真实接口为 POST /api/admin/purchase-advice（流式）；当前 mock
    const text = mockAdvice
    // 打字机效果
    for (const ch of text) {
      advice.value += ch
      await new Promise((r) => setTimeout(r, 12))
    }
    message.success('采购建议已生成')
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
})
</script>

<template>
  <div class="admin-page">
    <header class="topbar">
      <div class="t">
        <span class="logo">小嘉</span>
        <span class="sep">|</span>
        <span>馆藏管理数据看板</span>
      </div>
      <NButton size="small" @click="router.push('/')">返回读者端</NButton>
    </header>

    <NSpin :show="loading">
      <div class="content">
        <!-- 概览卡片 -->
        <div class="stat-row">
          <NCard class="stat-card">
            <div class="stat-num teal">{{ summary.total_borrows.toLocaleString() }}</div>
            <div class="stat-label">总借阅量</div>
          </NCard>
          <NCard class="stat-card">
            <div class="stat-num blue">{{ summary.total_readers.toLocaleString() }}</div>
            <div class="stat-label">活跃读者</div>
          </NCard>
          <NCard class="stat-card">
            <div class="stat-num orange">{{ summary.total_titles.toLocaleString() }}</div>
            <div class="stat-label">图书种数</div>
          </NCard>
          <NCard class="stat-card">
            <div class="stat-num green">{{ summary.avg_borrow_per_reader }}</div>
            <div class="stat-label">人均借阅（册）</div>
          </NCard>
        </div>

        <div class="chart-row">
          <NCard title="热门图书 TOP8" class="chart-card wide">
            <div ref="hotChartRef" class="chart tall"></div>
          </NCard>
          <NCard title="借阅分类占比" class="chart-card">
            <div ref="pieChartRef" class="chart tall"></div>
          </NCard>
        </div>

        <!-- AI 采购建议 -->
        <NCard class="advice-card">
          <template #header>
            <div class="advice-head">
              <span>🤖 AI 智能采购建议</span>
              <NButton type="primary" size="small" :loading="adviceLoading" @click="genAdvice">
                {{ advice ? '重新生成' : '生成采购建议' }}
              </NButton>
            </div>
          </template>
          <div v-if="!advice && !adviceLoading" class="advice-empty">
            点击右上角按钮，小嘉将基于借阅数据自动生成复购、剔旧与学科缺口建议。
          </div>
          <pre v-if="advice" class="advice-text">{{ advice }}</pre>
        </NCard>
      </div>
    </NSpin>
  </div>
</template>

<style scoped>
.admin-page {
  min-height: 100vh;
  background: #f0f3f8;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  background: #fff;
  border-bottom: 1px solid #e8eef5;
  position: sticky;
  top: 0;
  z-index: 10;
}
.t {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 8px;
}
.logo {
  color: #0f9d8f;
}
.sep {
  color: #cbd5e1;
}
.content {
  padding: 22px 24px;
  max-width: 1200px;
  margin: 0 auto;
}
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
}
.stat-num {
  font-size: 28px;
  font-weight: 800;
}
.teal { color: #0f9d8f; }
.blue { color: #4f8cff; }
.orange { color: #f59e0b; }
.green { color: #22c55e; }
.stat-label {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}
.chart-row {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.chart {
  width: 100%;
  height: 320px;
}
.chart.tall {
  height: 360px;
}
.advice-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.advice-empty {
  color: #94a3b8;
  font-size: 13px;
  padding: 16px 0;
}
.advice-text {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.9;
  color: #334155;
  margin: 0;
}
@media (max-width: 760px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .chart-row { grid-template-columns: 1fr; }
}
</style>
