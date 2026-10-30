/**
 * echarts 按需引入：只注册本项目用到的图表与组件，避免全量打包。
 * 用法：`import echarts, { type ECharts } from '@/utils/echarts'`
 */
import * as echarts from 'echarts/core'
import { BarChart, PieChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  PieChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  CanvasRenderer,
])

export default echarts
export type { ECharts, EChartsCoreOption } from 'echarts/core'
