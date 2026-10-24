# C1 数据交付约定

此文件描述 C1 已导出的文件，以及对仓库 `docs/api-contract.md` 和 `frontend/src/types/index.ts` 的字段映射。HTTP 统计路由已接入同批借阅数据计算，原 api_*.json 保留供离线使用；管理端采用访问密钥，详细接入见 [C4/C5 服务说明](c4-c5-services.md)。C2 推荐另见 [C2 推荐交付约定](c2-recommendation.md)。

## 统计字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| borrow_count | integer | 接受的借阅流水行数，疑似重复已保留 |
| reader_count | integer | 接受流水中的不同 reader_id 数 |
| book_count | integer | 接受流水中的不同 book_key 数 |
| unique_title_count | integer | 接受流水中的不同规范化题名数 |
| observed_copy_count | integer | 接受流水中的不同非空财产号数 |
| borrows_per_reader | number 或 null | 借阅次数除以读者数；没有读者时为 null |
| share | number | 0 到 1 的比例，前端格式化成百分比 |
| dataset_label | string | simulated、real、unknown |

热门图书按 borrow_count 降序，同频按 book_key 排序。分类占比分母包括未知类别。reader_distribution 的 borrow_count 是横轴借阅次数，reader_count 是对应人数。出版社表保留空字符串并通过 publisher_missing 表示缺失，前端可显示“出版社未提供”。

`book_key` 是数据内部标识，ISBN 本身可能缺失或不合法，不能单独作为所有书单项的唯一键。`book_id` 是副本财产号，与书种层级的 `book_key` 不同。

## 给 A 和 B 的对接位置

| 既有或后续只读接口 | 已实现的数据来源 |
| --- | --- |
| GET /api/admin/stats/summary | api_summary.json |
| GET /api/admin/stats/hot-books?limit=10 | api_hot_books.json，按 limit 截取 data，最多已有 TOP100 |
| GET /api/admin/stats/categories | api_categories.json |
| GET /api/admin/stats/publishers | api_publishers.json |
| 后续 GET /api/admin/stats/reader-profile/{reader_id} | readers.csv 与 reader_preferences.json，需在服务端确认身份后过滤 |

`api_*.json` 使用现有 `{code: 0, message: "success", data}` 响应封装，并提供 dataset_label。`dashboard.json` 合并相同的已映射 data，再附带读者次数分布和 limitations；它不包含逐人画像。原生 CSV/JSON 字段仍保留，供推荐与数据核查使用。

| 现有前端或接口字段 | 原生统计字段或规则 |
| --- | --- |
| summary.total_borrows | summary.json 的 borrow_count |
| summary.total_readers | reader_count |
| summary.total_titles | unique_title_count，按规范化题名去重，不是 book_count |
| summary.avg_borrow_per_reader | borrows_per_reader |
| hot_books[].count | hot_books.json 的 borrow_count |
| categories[].category | categories.json 的 category_code |
| categories[].count | categories.json 的 borrow_count |
| publishers[].count | publishers.json 的 borrow_count |

`category_name`、`share` 及图书 ISBN 等可选信息会随对应结果保留。没有读者时平均值为 null；前后端已允许平均值为 null，页面显示为空值状态；前端默认访问后端，没有补造日期、架位或实时状态。

统计明细 CSV 和逐人偏好 JSON 应由后端按权限读取，不作为公开静态资源。实际读者 ID 由认证层确定，接入时不能让任意访客传一个 ID 就读取其他人的画像。

## 后续输入

C2 已使用完整 borrow_records.csv 和 books.csv 实现热门、分类偏好和协同过滤推荐，并从完整已读集合过滤历史。ISBN 缺失时使用无歧义的完整精确元数据归并候选，不改写 C1 输出；C2 count 因跨副本归并可能与单个 C1 book_key 的次数不同。C3 的 location、available、status 均须来自实时 OPAC 或已核实馆藏映射；C1/C2 没有生成这些字段。C4 不使用团队计划当作馆方规则，需另收集正式规章、数据库导航及 FAQ。
