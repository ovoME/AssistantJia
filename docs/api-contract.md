# 📑 AssistantJia 前后端 API 接口契约规范 (Draft v1.0)

> **后端框架**：FastAPI  
> **前端框架**：Vue 3 + Axios + EventSource / fetch ReadableStream  
> **统一响应规范**：非流式接口统一采用 `{ "code": 0, "message": "success", "data": ... }`

---

## 1. 对话与智能体接口 (Agent)

### 1.1 发送对话消息 (流式 SSE)
- **Method**: `POST`
- **Path**: `/api/chat`
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "message": "帮我找一下《三体》在哪个架位，现在能借吗？",
  "session_id": "session_user_001",
  "reader_id": "2023001"
}
```
- **Response (Server-Sent Events / EventStream)**:
```text
data: {"type": "thought", "content": "正在调用馆藏查询工具检索《三体》..."}

data: {"type": "tool_call", "tool": "search_books", "args": {"query": "三体"}}

data: {"type": "content", "token": "《三体》"}

data: {"type": "content", "token": "目前在馆可借。"}

data: {"type": "card", "card_type": "book", "data": {"title": "三体", "author": "刘慈欣", "isbn": "9787536692930", "call_number": "I247.55/123", "location": "主楼三层中文社科借阅区 302架A面03层", "available": 2, "status": "在馆"}}

data: {"type": "done"}
```

### 1.2 获取会话历史
- **Method**: `GET`
- **Path**: `/api/chat/history/{session_id}`
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "role": "user",
      "content": "查一下三体",
      "timestamp": "2026-10-23T15:30:00Z"
    },
    {
      "role": "assistant",
      "content": "学弟学妹好！《三体》索书号是 I247.55/123，在主楼三层中文区...",
      "timestamp": "2026-10-23T15:30:02Z"
    }
  ]
}
```

---

## 2. 图书与馆藏检索接口

### 2.1 图书检索
- **Method**: `GET`
- **Path**: `/api/books/search`
- **Query Params**:
  - `query` (string, required): 书名 / 作者 / 索书号 / 关键词
  - `limit` (int, default: 5)
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "title": "深入理解计算机系统",
      "author": "Randal E. Bryant",
      "isbn": "9787111544937",
      "call_number": "TP3/288",
      "location": "主楼四层理工科借阅区 410架B面",
      "available": 1,
      "status": "在馆"
    }
  ]
}
```

---

## 3. 借阅服务接口

### 3.1 获取读者当前借阅
- **Method**: `GET`
- **Path**: `/api/reader/{reader_id}/borrows`
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "book_id": "B20230911001",
      "title": "Python编程：从入门到实践",
      "borrow_date": "2026-10-01",
      "due_date": "2026-11-01",
      "renew_count": 0,
      "is_overdue": false
    }
  ]
}
```

### 3.2 一键续借
- **Method**: `POST`
- **Path**: `/api/renew`
- **Request Body**:
```json
{
  "reader_id": "2023001",
  "book_id": "B20230911001"
}
```
- **Response (成功)**:
```json
{
  "code": 0,
  "message": "续借成功",
  "data": {
    "new_due_date": "2026-12-01",
    "renew_count": 1
  }
}
```
- **Response (失败/超限/被预约)**:
```json
{
  "code": 4001,
  "message": "该图书已被其他读者预约，无法办理续借，请于到期日前归还。",
  "data": null
}
```

### 3.3 图书预约
- **Method**: `POST`
- **Path**: `/api/reserve`
- **Request Body**:
```json
{
  "reader_id": "2023001",
  "isbn": "9787111544937"
}
```
- **Response**:
```json
{
  "code": 0,
  "message": "预约成功",
  "data": {
    "queue_position": 1,
    "notify_channel": "站内消息"
  }
}
```

---

## 4. 推荐与个性化接口

### 4.1 读者个性化推荐
- **Method**: `GET`
- **Path**: `/api/recommend`
- **Query Params**: `reader_id=2023001&limit=5`
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "title": "算法导论",
      "author": "Thomas H. Cormen",
      "isbn": "9787111407010",
      "call_number": "TP301.6/12",
      "reason": "根据你近期对计算机科学类图书的借阅偏好推荐"
    }
  ]
}
```

### 4.2 热门借阅榜单
- **Method**: `GET`
- **Path**: `/api/hot-books`
- **Query Params**: `category=I&limit=10`
- **语义**: 按借阅量倒序的全馆热门榜；`category` 过滤生效（如 `I` 只返回文学类）。
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "title": "三体全集", "author": "刘慈欣", "count": 428, "call_number": "I247.55/123", "category": "I" }
  ]
}
```

---

## 5. 管理端统计与决策接口 (Admin)

### 5.1 借阅概览统计
- **Method**: `GET`
- **Path**: `/api/admin/stats/summary`
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_borrows": 36908,
    "total_readers": 3580,
    "total_titles": 22318,
    "avg_borrow_per_reader": 10.31
  }
}
```

### 5.2 热门图书与分类统计
- `GET /api/admin/stats/hot-books?limit=10` → `data: [{title, author?, count, call_number?, category?}]`
- `GET /api/admin/stats/categories` → `data: [{category, category_name, count, share}]`
- `GET /api/admin/stats/publishers`

### 5.3 AI 智能采购建议
- **Method**: `POST`
- **Path**: `/api/admin/purchase-advice`
- **Response**: 流式生成或 JSON 报告，包含超高借阅复购建议、冷门低频图书调架建议、学科文献缺口分析。
