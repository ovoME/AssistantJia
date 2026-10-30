# 小嘉前端 · 后端联调清单

> 前端：Vue3 + Vite + TypeScript + Pinia。本文档是前端（B）与后端（A）联调的对照依据。
> 最后更新：PR #2 迭代。

---

## 1. 环境与开关

| 项 | 值 / 说明 |
|---|---|
| Mock 开关 | `VITE_USE_MOCK`（环境变量，见 `frontend/.env.example`） |
| 默认值 | `true`：走 `src/mock/data.ts`，无需后端即可跑通全部动线 |
| 切真实后端 | 在 `frontend/.env.local` 设 `VITE_USE_MOCK=false`，**无需改任何源码** |
| 后端地址 | Vite dev proxy 把 `/api` 转发到 `http://localhost:8000`（FastAPI） |
| 统一响应 | `{ code: number, message: string, data: T }`；`code !== 0` 视为业务错误，前端弹错并 reject |

`.env.local` 不提交 git（`.gitignore` 已忽略 `*.local`）。

---

## 2. 已实现接口对照表

前端函数均在 `src/api/index.ts`；HTTP 层在 `src/api/request.ts`（axios 实例 + SSE fetch）。

| 前端函数 | 方法 | 路径 | 请求参数 | 响应 data | 调用页面 | 状态 |
|---|---|---|---|---|---|---|
| `sendChat` | POST | `/api/chat` (SSE) | `{message, session_id, reader_id}` | SSE 事件流：`thought/content/card/done/error` | 读者端对话 | ✅ |
| `searchBooks` | GET | `/api/books/search` | `query, limit` | `Book[]` | （预留） | ✅ |
| `getMyBorrows` | GET | `/api/reader/{readerId}/borrows` | path: readerId | `BorrowRecord[]` | 我的借阅模态 | ✅ |
| `renewBook` | POST | `/api/renew` | `{reader_id, book_id}` | `RenewResult{new_due_date, renew_count}` | 我的借阅 | ✅ |
| `reserveBook` | POST | `/api/reserve` | `{reader_id, isbn}` | `ReserveResult{queue_position, notify_channel}` | 图书卡片 | ✅ |
| `getRecommend` | GET | `/api/recommend` | `reader_id, limit` | `RecommendBook[]` | （已封装，暂未接页面） | ✅ |
| `getAdminSummary` | GET | `/api/admin/stats/summary` | — | `AdminSummary{...}` | 管理端 | ✅ |
| `getHotBooks` | GET | `/api/admin/stats/hot-books` | `limit` | `BookStat[]{title, author, count}` | 管理端 TOP8 | ✅ |
| `getCategories` | GET | `/api/admin/stats/categories` | — | `CategoryStat[]{category, category_name, count}` | 管理端环形图 | ✅ |
| `getPublishers` | GET | `/api/admin/stats/publishers` | `limit=10` | `BookStat[]{title, count}` | 管理端出版社TOP10 | ✅ mock |
| `getBorrowTrend` | GET | `/api/admin/stats/trend` | `days=30` | `BorrowTrendPoint[]{date, count}` | 管理端趋势折线图 | ✅ mock |
| `getPurchaseAdvice` | POST | `/api/admin/purchase-advice` | — | `string`（建议正文，前端打字机展示） | 管理端 AI 建议 | ✅ |

### SSE 事件约定（`/api/chat`）

后端按 `data: <json>\n\n` 逐事件推送；前端分隔兼容 `\r\n\r\n` 并在流结束 flush 尾包。事件类型：

| type | 字段 | 说明 |
|---|---|---|
| `thought` | `content` | 思考过程（灰色小字，可空） |
| `content` | `token` | 正文片段，逐字追加 |
| `card` | `card_type:'book', data:Book` | 图书卡片，可多条 |
| `done` | — | 结束 |
| `error` | `message` | 业务错误（标记消息失败，前端显示重发按钮） |

---

## 3. 数据结构（与 `src/types/index.ts` 一致）

- `Book{title, author, isbn, call_number, location, available, status}`
- `BorrowRecord{book_id, title, borrow_date, due_date, renew_count, is_overdue}`
- `AdminSummary{total_borrows, total_readers, total_titles, avg_borrow_per_reader}`
- `BookStat{title, author?, count}` / `CategoryStat{category, category_name?, count}`
- `BorrowTrendPoint{date, count}`（近N天每日借阅量）

---

## 4. 待后端补齐的接口

| 优先级 | 接口 | 说明 | 前端状态 |
|---|---|---|---|
| 高 | `GET /api/chat/history/{session_id}` | 对话历史，刷新页面不丢消息（契约 1.2） | 未实现，需留 session 持久化 |
| 中 | `GET /api/hot-books` | 读者侧热门图书推荐位 | 未接页面 |
| 中 | `GET /api/admin/stats/trend` | 近30天每日借阅量趋势折线图 | 前端已接 mock，待真实接口 |
| 低 | `POST /api/admin/book-review` | 书评生成 | 需先补契约 |

---

## 5. 联调步骤

1. 后端起 FastAPI（:8000），确认 `/api/docs` 可访问。
2. 前端根目录 `cp .env.example .env.local`，把里面 `VITE_USE_MOCK` 改为 `false`。
3. `npm run dev`，打开 `http://localhost:5173`：
   - 读者端：发消息 → 应收到真实 SSE 流；我的借阅 → 调 `getMyBorrows`；续借/预约 → 对应 POST。
   - 管理端 `/admin`：统计卡 / 两张图表 / 采购建议生成，分别对应 4 个 admin 接口。
4. 网络异常 / 后端 500 时，前端各入口均有「加载失败 + 重新加载」兜底，不会白屏。

---

## 6. 待对齐口径（答辩前确认）

- `total_readers`：mock 用 **3580**，契约示例写 **5120**——联调时以后端真实数据为准，前端 mock 数字仅演示。
- 热门图书条数：当前取 8 条；如需 10 条，改 `getHotBooks(10)` 一处即可。
