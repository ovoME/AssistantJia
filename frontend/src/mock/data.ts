import type {
  Book,
  BorrowRecord,
  RecommendBook,
  AdminSummary,
  CategoryStat,
  BookStat,
} from '../types'

/**
 * Mock 数据：后端（A）还没写好前，前端用它独立开发。
 * 后端接口就绪后，在 `.env.local` 里设 VITE_USE_MOCK=false 即可关闭，无需改源码。
 */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

export const mockBooks: Book[] = [
  {
    title: '三体',
    author: '刘慈欣',
    isbn: '9787536692930',
    call_number: 'I247.55/123',
    location: '主楼三层中文社科借阅区 302架A面03层',
    available: 2,
    status: '在馆',
  },
  {
    title: '深入理解计算机系统',
    author: 'Randal E. Bryant',
    isbn: '9787111544937',
    call_number: 'TP3/288',
    location: '主楼四层理工科借阅区 410架B面',
    available: 1,
    status: '在馆',
  },
  {
    title: '区域果蔬外贸冷链物流模式及其机制创新研究',
    author: '李红著',
    isbn: '9787511649973',
    call_number: 'F252.8/11',
    location: '主楼三层经济管理借阅区 315架C面',
    available: 0,
    status: '借出',
  },
]

export const mockBorrows: BorrowRecord[] = [
  {
    book_id: 'B20230911001',
    title: 'Python编程：从入门到实践',
    borrow_date: '2026-10-01',
    due_date: '2026-11-01',
    renew_count: 0,
    is_overdue: false,
  },
  {
    book_id: 'B20230912002',
    title: '算法图解',
    borrow_date: '2026-09-20',
    due_date: '2026-10-20',
    renew_count: 1,
    is_overdue: true,
  },
]

export const mockRecommend: RecommendBook[] = [
  {
    title: '算法导论',
    author: 'Thomas H. Cormen',
    isbn: '9787111407010',
    call_number: 'TP301.6/12',
    reason: '根据你近期对计算机科学类图书的借阅偏好推荐',
  },
  {
    title: '代码整洁之道',
    author: 'Robert C. Martin',
    isbn: '9787115215700',
    call_number: 'TP311.5/120',
    reason: '借过《算法图解》的同学也在借',
  },
]

export const mockSummary: AdminSummary = {
  total_borrows: 36908,
  total_readers: 3580,
  total_titles: 22318,
  avg_borrow_per_reader: 10.3,
}

export const mockHotBooks: BookStat[] = [
  { title: '聚丙烯纤维混凝土抗裂防渗性能研究与施工工法', author: '', count: 32 },
  { title: '国际桥梁与结构工程协会桥梁方案设计竞选指南', author: '', count: 31 },
  { title: '砌筑工', author: '', count: 30 },
  { title: '云边有个小卖部', author: '张嘉佳', count: 28 },
  { title: '钢筋混凝土简支梁加载试验辅助教学软件', author: '', count: 27 },
  { title: '美国公路桥梁加固设计与实例', author: '', count: 27 },
  { title: '福建省市政工程预算定额（第七册）', author: '', count: 27 },
  { title: '屋顶绿化技术与建筑节能应用', author: '', count: 26 },
]

export const mockCategories: CategoryStat[] = [
  { category: 'I', category_name: '文学', count: 4213 },
  { category: 'T', category_name: '工业技术', count: 2890 },
  { category: 'F', category_name: '经济', count: 1640 },
  { category: 'B', category_name: '哲学/心理', count: 1180 },
  { category: 'H', category_name: '语言文字', count: 960 },
  { category: 'C', category_name: '社会科学', count: 834 },
  { category: 'J', category_name: '艺术', count: 620 },
]

export const mockPublishers: BookStat[] = [
  { title: '机械工业出版社', author: '', count: 1820 },
  { title: '高等教育出版社', author: '', count: 1560 },
  { title: '电子工业出版社', author: '', count: 1240 },
  { title: '人民邮电出版社', author: '', count: 980 },
  { title: '清华大学出版社', author: '', count: 860 },
  { title: '商务印书馆', author: '', count: 720 },
  { title: '科学出版社', author: '', count: 640 },
  { title: '中信出版社', author: '', count: 520 },
  { title: '人民文学出版社', author: '', count: 480 },
  { title: '上海译文出版社', author: '', count: 410 },
]

/** 模拟 SSE 流式回复（把一段文字逐段返回，模拟打字机） */
export function mockSseChunks(fullText: string, cards: Book[] = []): string[] {
  const chunks: string[] = []
  chunks.push(JSON.stringify({ type: 'thought', content: '正在理解你的需求并检索馆藏…' }))
  const tokens = fullText.match(/[\s\S]{1,3}/g) || []
  for (const t of tokens) {
    chunks.push(JSON.stringify({ type: 'content', token: t }))
  }
  for (const c of cards) {
    chunks.push(JSON.stringify({ type: 'card', card_type: 'book', data: c }))
  }
  chunks.push(JSON.stringify({ type: 'done' }))
  return chunks
}

/** AI 智能采购建议（对应 POST /api/admin/purchase-advice，契约 5.3） */
export const mockAdvice = `【小嘉智能采购建议 · 基于36,908条借阅数据】

1. 复购建议：建筑/土木类（TU、U类）借阅高度集中，其中《聚丙烯纤维混凝土抗裂防渗性能研究与施工工法》《砌筑工》等热门书借阅量达30+次且可借副本不足，建议各增购3-5本，缓解排队。

2. 学科缺口：物流管理（F252/F253）相关图书借阅集中且复借率高，说明该专业课程需求旺盛，建议围绕冷链物流、仓储管理、物流装备补充新版教材与实务类图书。

3. 冷门调架：部分文学旧书（I类早期版本）借阅量为0，建议结合馆藏年限评估剔旧或移至密集书库，释放黄金架位。

4. 馆藏结构：文学类（I）占比最高，工业技术（T）次之，建议保持工程类新书采购节奏，并增加计算机（TP311/TP312）类前沿图书以匹配学生技术学习需求。`
