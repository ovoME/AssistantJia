# 📑 AssistantJia 前后端 API 接口契约规范 (Draft v1.1)

> **数据来源**：模拟联调夹具随仓库提供（`data/fixtures/integration/`）；**真实资料包不进入 Git**，需从团队共享盘获取后放到 `data/shared/`，见 [C 模块共享数据指南](c-shared-data.md)。显式 `DATA_PROFILE=integration` 时提供带模拟标签的库存、日期和编号对照；`local` 档位下真实源缺失字段保持未知，身份检查不变。

> **后端框架**：FastAPI  
> **前端框架**：Vue 3 + Axios + EventSource / fetch ReadableStream  
> **统一响应规范**：非流式接口统一采用 `{ "code": 0, "message": "success", "data": ... }`

**v1.1 修订（2026-10-25）**：同步 C4/C5 接入后的实际实现。补充鉴权与数据标注总则、新增第 6/7 章（规则检索、数据状态、健康检查）、第 5.5 节（资源统计）、第 2.3 节（馆藏预留），修正示例中"在馆可借 / available: 2"等与实现不符的伪造状态，更新采购建议语义。已有接口的字段名未做破坏性变更。

---

## 0. 通用约定（所有接口适用）

### 0.1 响应信封与数据标注

所有非流式接口返回同一信封。除 `code/message/data` 外，**数据来源标注字段**用于区分"真实样本 / 模拟数据 / 未标明"，前端必须据此显示来源标签，不得把 `simulated` 数据当作真实馆情展示。

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "dataset_label": "real",
  "scope": "historical_borrow_records",
  "is_live": false,
  "built_at": "2026-10-25T02:00:00+08:00",
  "limitations": ["数据仅代表历史借阅样本，不代表馆藏全量或当前在借状态。"]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | int | `0` 成功；非 0 见 0.4 |
| `dataset_label` | `"real"` \| `"simulated"` \| `"unknown"` \| `null` | 数据来源。`simulated` 表示虚构演示数据 |
| `scope` | string \| null | 统计口径，如 `historical_borrow_records`、`static_snapshot`、`library_rules_snapshot` |
| `is_live` | bool \| null | **恒为 `false`**。当前所有数据均为离线快照，无实时业务 |
| `built_at` | string \| null | 数据批次构建时间 |
| `limitations` | string[] | 该接口的适用边界，前端应展示或至少在详情中可见 |

### 0.2 鉴权

| 范围 | 方式 | 说明 |
|---|---|---|
| 匿名可访问 | 无 | `/chat`、`/books/search`、`/books/{isbn}`、`/books/holdings/*`、`/hot-books`、`/recommend`（仅热门兜底）、`/knowledge/search`、`/data/status`、`/health` |
| 管理端 | `X-Admin-Token: <token>` | `/api/admin/*` 全部接口。服务端未配置密钥时返回 `503`，密钥错误返回 `401` |
| 读者个人数据 | `Authorization: Bearer <token>` | 令牌由运维/登录端用 `READER_TOKEN_SECRET` 签发（HMAC-SHA256），不可由浏览器自行构造 |

**读者令牌规则**

- 请求体或路径中的 `reader_id` 只接受 `me`（取令牌身份）或与令牌 `sub` 完全一致的值。
- 未带令牌却指定具体 `reader_id` → `401`；带了 A 的令牌却请求 B 的数据 → `403`。
- 令牌有效期上限 31 天，过期或签名不符 → `401`。
- 前端不得把任意读者号拼进 URL 来"查别人的数据"，这不是权限问题而是接口语义不允许。

### 0.3 分页与数量限制

`limit` 参数均有上界（见各接口），超出由服务端拒绝（`422`），不会静默截断。

### 0.4 错误码

| code | HTTP | 含义 |
|---|---|---|
| `0` | 200 | 成功 |
| `4000` | 422 | 参数或数据格式无效 |
| `4001` | 200 | 业务拒绝（如续借超限、财产号不存在） |
| `4002` | 200 | 服务未接入（如尚未对接馆方续借） |
| `4003` | 403 | 身份不匹配，禁止访问他人数据 |
| `4004` | 200 | 资源未找到 |
| `5001` | 503 | 本地数据未初始化或批次不一致 |

> `4001/4002/4004` 走 HTTP 200 + 非零 `code`，前端必须检查 `code` 而不是只看 HTTP 状态。

---

## 1. 对话与智能体接口 (Agent)

### 1.1 发送对话消息 (流式 SSE)
- **Method**: `POST`
- **Path**: `/api/chat`
- **Headers**: `Content-Type: application/json`；可选 `Authorization: Bearer <token>`
- **Request Body**:
```json
{
  "message": "帮我找一下《三体》，现在能借吗？",
  "session_id": "session_user_001"
}
```
- **Response (Server-Sent Events / EventStream)**:

事件类型固定为 `thought` → `tool_call` → `card`（0..n）→ `content`（0..n）→ `done`。

```text
data: {"type": "thought", "content": "正在查询已加载的数据与已核对规则…"}

data: {"type": "tool_call", "tool": "search_books", "args": {"query": "三体"}}

data: {"type": "card", "card_type": "book", "data": {"title": "三体", "author": "刘慈欣", "isbn": "9787536692930", "call_number": "I247.55/123", "location": null, "available": null, "status": "unknown", "dataset_label": "simulated", "reservation_supported": false}}

data: {"type": "content", "token": "本地书目快照中找到该图书，索书号见卡片；"}

data: {"type": "done"}
```

**语义约束（实现已遵守，前端不要违背）**

- 规则类问题（开馆时间、借期、座位规则等）**原样返回人工核对的摘要**，不经 LLM 改写，避免数字被篡改。因此这类回答**不保证有 `card`**。
- `card.data` 中 `location`、`available`、`status` 在未接入实时馆藏时保持 `null` / `"unknown"`，`reservation_supported` 为 `false`。**前端不得把这些字段显示为"在馆"或"可预约"。**
- `reader_id` 字段已废弃：身份一律取自 `Authorization` 令牌，请求体传 `reader_id` 会被忽略或拒绝（越权时 `403`）。

### 1.2 获取会话历史
- **Method**: `GET`
- **Path**: `/api/chat/history/{session_id}`
- **Headers**: 可选 `Authorization: Bearer <token>`
- **会话隔离**：已认证用户按读者身份隔离；匿名用户按 `xiaojia_session` Cookie（HttpOnly，32 位十六进制）隔离。不同访客互不可见。
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    { "role": "user", "content": "查一下三体", "timestamp": "2026-10-23T15:30:00Z" },
    { "role": "assistant", "content": "本地书目快照中找到《三体》，索书号 I247.55/123…", "timestamp": "2026-10-23T15:30:02Z" }
  ]
}
```

> 匿名首次访问若尚未持有 Cookie，`data` 为空数组且不分配身份；发过一次消息后由 `POST /api/chat` 下发 Cookie。

---

## 2. 图书与馆藏检索接口

### 2.1 图书检索
- **Method**: `GET`
- **Path**: `/api/books/search`
- **Query Params**:
  - `query` (string, required): 书名 / 作者 / 索书号 / 关键词
  - `limit` (int, default: 5, 1–20)
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "dataset_label": "simulated",
  "scope": "static_snapshot",
  "is_live": false,
  "data": [
    {
      "title": "深入理解计算机系统",
      "author": "Randal E. Bryant",
      "isbn": "9787111544937",
      "call_number": "TP3/288",
      "publisher": "机械工业出版社",
      "book_key": "isbn:9787111544937",
      "location": null,
      "available": null,
      "status": "unknown",
      "reservation_supported": false
    }
  ]
}
```

> 空结果返回 `data: []`，**不补造推荐书单**。`location/available/status` 为占位字段，接入实时馆藏前恒为 `null`/`"unknown"`。

### 2.2 按 ISBN 查详情
- **Method**: `GET`
- **Path**: `/api/books/{isbn}`
- **Response**: 同上单条 `Book`；未命中返回 `code: 4004`、`data: null`。

### 2.3 馆藏状态（预留）
- **Method**: `GET`
- **Path**: `/api/books/holdings/{book_key}`
- **语义**: 为馆方实时馆藏预留。默认 `OPAC_PROVIDER=disabled` 时返回 `503`（明确告知未接入），不会返回伪造的在馆数量。
- **Response (demo 模式)**:
```json
{
  "code": 0,
  "message": "success",
  "dataset_label": "simulated",
  "is_live": false,
  "data": { "book_key": "isbn:9787111544937", "location": "虚构示范书库 A 架", "available": 2, "status": "模拟在馆" }
}
```

> `available` 非空**仅在 `dataset_label: "simulated"` 时出现**，前端必须同时展示"模拟"标签。

---

## 3. 借阅服务接口

### 3.1 获取读者当前借阅
- **Method**: `GET`
- **Path**: `/api/reader/{reader_id}/borrows`
- **Headers**: `Authorization: Bearer <token>`
- **Path Params**: `reader_id` 只接受 `me` 或令牌本人 ID。
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "dataset_label": "simulated",
  "scope": "demo_business",
  "is_live": false,
  "data": [
    {
      "book_id": "DEMO-COPY-001",
      "title": "虚构图书：海风与星光",
      "borrow_date": "2026-10-15",
      "due_date": "2026-12-14",
      "renew_count": 0,
      "is_overdue": false,
      "can_renew": true,
      "dataset_label": "simulated",
      "is_live": false
    }
  ]
}
```

> `OPAC_PROVIDER=disabled` 时该接口返回 `503`（历史借阅数据不能当作当前在借记录）。这是有意为之，不是故障。

### 3.2 一键续借
- **Method**: `POST`
- **Path**: `/api/renew`
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
```json
{ "reader_id": "me", "book_id": "DEMO-COPY-001" }
```
- **Response (成功)**:
```json
{
  "code": 0,
  "message": "模拟续借完成，未向馆方提交任何操作。",
  "dataset_label": "simulated",
  "is_live": false,
  "data": { "new_due_date": "2027-01-13", "renew_count": 1, "can_renew": true }
}
```
- **Response (失败/超限/未接入)**:
```json
{ "code": 4002, "message": "尚未接入馆方续借接口，请在官方系统办理。", "data": null }
```

> 已知限制：失败响应目前不带 `dataset_label`（`ApiResponse.fail` 不透传标注字段）。前端在失败态不要依赖该字段判断来源，应直接展示 `message`。

### 3.3 图书预约
- **Method**: `POST`
- **Path**: `/api/reserve`
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
```json
{ "reader_id": "me", "isbn": "9787111544937" }
```
- **Response (成功)**:
```json
{
  "code": 0,
  "message": "模拟预约完成，未产生真实排队或借阅。",
  "dataset_label": "simulated",
  "is_live": false,
  "data": { "queue_position": 1, "notify_channel": "模拟通知" }
}
```
- **Response (ISBN 非法)**:
```json
{ "code": 4001, "message": "模拟预约需要合法 ISBN；没有 ISBN 的书目请去馆方系统查询。", "data": null }
```

---

## 4. 推荐与个性化接口

### 4.1 读者个性化推荐
- **Method**: `GET`
- **Path**: `/api/recommend`
- **Query Params**: `limit` (default 5, 1–20)
- **Headers**: 可选 `Authorization: Bearer <token>`
- **语义**:
  - **匿名**：返回全馆热门兜底，不含任何个人偏好推断。
  - **已认证**：按令牌身份返回个性化推荐，并过滤已读。
  - 匿名传 `reader_id` → `401`；令牌与 `reader_id` 不一致 → `403`。
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "dataset_label": "real",
  "scope": "historical_borrow_records",
  "is_live": false,
  "data": [
    {
      "title": "算法导论",
      "author": "Thomas H. Cormen",
      "isbn": "9787111407010",
      "call_number": "TP301.6/12",
      "reason": "基于历史借阅的内容相似度推荐",
      "book_key": "isbn:9787111407010",
      "category": "TP",
      "count": 12,
      "score": 0.83,
      "strategy": "content"
    }
  ]
}
```

### 4.2 热门借阅榜单
- **Method**: `GET`
- **Path**: `/api/hot-books`
- **Query Params**: `category`（中图法**大类**首字母，如 `I`、`T`、`F`；传子类 `TP` 会无匹配）, `limit` (default 10, 1–50)
- **语义**: 按借阅量倒序；`category` 过滤生效。
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "dataset_label": "real",
  "is_live": false,
  "data": [
    { "title": "三体全集", "author": "刘慈欣", "count": 428, "call_number": "I247.55/123", "category": "I" }
  ]
}
```

---

## 5. 管理端统计与决策接口 (Admin)

> **本章全部接口需要 `X-Admin-Token`**。未配置密钥 → `503`；密钥错误 → `401`。

### 5.1 借阅概览统计
- **Method**: `GET`
- **Path**: `/api/admin/stats/summary`
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "dataset_label": "real",
  "scope": "historical_borrow_records",
  "is_live": false,
  "data": {
    "total_borrows": 36908,
    "total_readers": 3580,
    "total_titles": 22318,
    "avg_borrow_per_reader": 10.31
  }
}
```

> `total_readers` 是**样本内不同读者数**，不是全馆注册读者数；`avg_borrow_per_reader` 分母同为样本读者。前端文案不要写"活跃读者"。

### 5.2 热门图书与分类统计
- `GET /api/admin/stats/hot-books?limit=10` → `data: [{title, author?, count, call_number?, category?}]`
- `GET /api/admin/stats/categories` → `data: [{category, category_name, count, share}]`（`share` 为 0–1 小数，如 `0.225`）
- `GET /api/admin/stats/publishers?limit=10` → `data: [{publisher, count}]`（`publisher` 可能为空字符串，前端显示"出版社未提供"）
- `GET /api/admin/stats/trend?days=30` → `data: []` + `message` 说明原因。**借阅源无日期字段，趋势恒为空**，前端必须显示"无日期，无法绘制趋势"，不要画空折线。

### 5.3 历史借阅需求参考（原"AI 智能采购建议"）
- **Method**: `POST`
- **Path**: `/api/admin/purchase-advice`
- **Request Body**:
```json
{ "focus_category": "TP", "target_budget": null }
```
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "dataset_label": "real",
  "is_live": false,
  "data": {
    "report": "历史借阅需求参考\n本批包含 36908 条借阅流水。\n《…》：历史借阅 428 次。\n以上仅用于馆员核查需求，不等同于增购结论。",
    "generated_by": "historical_statistics_template",
    "is_ai_generated": false
  }
}
```

> **语义变更**：不再是"AI 生成复购/剔旧建议"。缺少统计时间、馆藏复本、利用率与预约排队数据时，无法计算复购率或判断长期零借阅，因此只输出历史高频需求，并明确声明"不等同于增购结论"。`generated_by` 用于区分模板生成与模型生成。

### 5.4 书评生成（未接入）
- **Method**: `POST`
- **Path**: `/api/admin/book-review`
- **Response**: 恒返回 `code: 4002`，说明"尚无可核实的书评来源"。前端不应把它当作可用功能入口。

### 5.5 资源使用统计
- **Method**: `GET`
- **Path**: `/api/admin/stats/usage`
- **语义**: 对座位、研讨室、门禁事件、门禁汇总、读者、学者库**逐表独立聚合**；不推断跨表读者/书目编号关联。
- **Response**:
```json
{
  "code": 0,
  "message": "success",
  "dataset_label": "unknown",
  "scope": "separate_source_aggregates",
  "is_live": false,
  "data": {
    "dataset_label": "unknown",
    "built_at": "2026-10-25T02:00:00+00:00",
    "is_live": false,
    "datasets": {
      "seats": {
        "source_file": "座位预约.csv",
        "rows": 12345,
        "distinct_source_readers": 890,
        "duplicate_excess_rows": 3,
        "invalid_date_rows": 0,
        "date_precision_counts": { "day": 12345 },
        "observed_date_min": "2026-03-01",
        "observed_date_max": "2026-06-30",
        "dimensions": { "楼层": [{ "name": "2", "count": 4321 }] },
        "suppressed_dimension_rows": { "楼层": 12 }
      }
    },
    "limitations": ["各表单独统计，不推断不同脱敏读者或书目编号的关联。"]
  }
}
```

**隐私约束（实现已遵守）**

- 分组计数 **< 5 的项不输出名称**，只计入 `suppressed_dimension_rows`。
- 不输出任何身份明细、学号、论文全文。
- 日期只保留原始精度（年 / 月 / 日），**不补造**成当月 1 日或当年 1 月 1 日。
- 未导入统计时返回 `dataset_label: "unknown"` + `datasets: {}` + 说明性 `limitations`，不报错。

---

## 6. 规则与数据来源接口

### 6.1 馆方规则检索
- **Method**: `GET`
- **Path**: `/api/knowledge/search`
- **Query Params**: `question` (required, 1–500)
- **语义**: 基于人工核对的六个馆方公开页面摘要（12 个主题切块）做稀疏 TF-IDF 检索。**不是**语义嵌入检索，也不调用 LLM。
- **Response (命中)**:
```json
{
  "code": 0,
  "message": "success",
  "dataset_label": "official_summary",
  "scope": "library_rules_snapshot",
  "is_live": false,
  "data": {
    "found": true,
    "answer": "[1] 普通图书借期与续借：…嘉庚系统借期为 180 天…最多续借 3 次，每次 30 天…",
    "source": { "title": "借阅权限", "url": "https://library.xujc.com/jyqx/list.htm" },
    "retrieved_at": "2026-10-24T23:33:24+08:00"
  }
}
```
- **Response (无充分依据)**:
```json
{ "code": 0, "message": "success", "data": { "found": false, "answer": "…未找到明确依据…" } }
```

> 规则摘要是**转述而非网页全文镜像**，含采集/发布/修订日期。未标注发布日的页面 `published_at` 为 `null`，不得把采集时间当作生效时间。

### 6.2 数据来源状态
- **Method**: `GET`
- **Path**: `/api/data/status`
- **语义**: 供前端判断各能力是否可用，决定是否显示"未接入"提示。
- **Response（默认，`DATA_PROFILE=local`）**:
```json
{
  "code": 0,
  "message": "success",
  "is_live": false,
  "data": {
    "catalog": "static_snapshot",
    "recommendations": "historical_sample",
    "rules": "official_summary",
    "business": "disabled",
    "data_profile": "local",
    "personalization_requires_auth": true,
    "admin_requires_auth": true
  }
}
```

- **Response（显式 `DATA_PROFILE=integration`，模拟联调）**:
```json
{
  "code": 0,
  "message": "success",
  "is_live": false,
  "data": {
    "catalog": "synthetic_fixture",
    "recommendations": "historical_sample",
    "rules": "official_summary",
    "business": "integration_demo",
    "data_profile": "integration",
    "personalization_requires_auth": true,
    "admin_requires_auth": true
  }
}
```

| 字段 | 取值 | 含义 |
|---|---|---|
| `catalog` | `static_snapshot` \| `synthetic_fixture` | 目录数据来源。`synthetic_fixture` 仅在 `integration` 档位出现 |
| `recommendations` | `historical_sample` | 历史借阅样本，非实时 |
| `rules` | `official_summary` | 人工核对的馆方规则摘要 |
| `business` | `disabled` \| `demo` \| `integration_demo` | 实时业务适配层状态 |
| `data_profile` | `local` \| `integration` | 当前数据档位 |

> `business` 为 `disabled` 时前端必须禁用"续借/预约"按钮。`demo` / `integration_demo` 只演示虚构记录，响应必带 `dataset_label: "simulated"`，前端必须同时显示"模拟"标签。`integration` 档位需先执行 `python -S -m data.scripts.prepare_shared --dataset integration`。

---

## 7. 健康检查

- **Method**: `GET`
- **Path**: `/health`
- **Response**:
```json
{ "code": 0, "message": "success", "data": { "status": "healthy", "service": "AssistantJia Backend" } }
```

---

## 8. 契约维护约定

1. 本文件是前后端接口的**唯一事实来源**。新增/修改接口必须先改这里，再改代码。
2. 新增接口必须同时写明：路径、方法、鉴权要求、字段表、`dataset_label` 取值、错误码。
3. **禁止在示例中写入未实现的实时状态**（如"在馆 2 册"）。示例必须与真实响应一致，否则前端会按示例做出错误 UI。
4. 字段新增必须向后兼容（可选、有默认值）；删除或改名需要同步通知 A/B/D 三方。
