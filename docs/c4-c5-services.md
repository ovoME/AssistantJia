# C4/C5 与数据服务接入

交付日期：2026-10-25。C1–C3 已合并，本次把规则知识库、统计、推荐和静态书目查询接入现有 FastAPI/Vue 页面。原始文件及逐人借阅不进入 Git 或镜像；真实资料包由授权成员从团队共享盘获取，data/shared只保留校验清单，模拟联调源在data/fixtures/integration，详见[共享说明](c-shared-data.md)。

## 完成范围

| 模块 | 行为 |
| --- | --- |
| C4 规则 | 六个馆方公开页面，十二个主题切块；TF-IDF 稀疏向量、余弦检索、主题约束、来源链接和修订/采集时间 |
| C5 统计 | 概览、热门、分类、出版社及需求参考，从同批 C1 流水计算，不再返回固定数字 |
| C2 接入 | 探索推荐结合主题与个人兴趣，匿名不推断个人偏好；个人推荐只接受已验证身份 |
| C3 接入 | 读取只读 SQLite 目录；空结果不补演示书单，架位和可借量缺失保持 null |
| 资源统计 | 座位、研讨室、门禁事件/汇总、读者和学者库分别聚合，管理端展示，不推测跨表关联 |
| OPAC 适配 | LibraryProvider 契约及 disabled/demo 实现，预留当前借阅、续借、预约和馆藏状态入口 |

## 馆方规则来源与更新

人工核对日期为 2026-10-24，摘要在 `data/knowledge/rules.json`：

- [开馆时间](https://library.xujc.com/kgsj/list.htm)：区分阅览、借还、人工服务及假期例外。
- [借阅权限](https://library.xujc.com/jyqx/list.htm)：区分人群、普通/特殊文献、嘉庚/厦大系统和预约催还。
- [入馆须知](https://library.xujc.com/rgxz/list.htm)：证件、秩序及安全要求。
- [座位管理规则](https://library.xujc.com/2021/1027/c7933a132465/page.htm)：页面发布于 2021-10-27，正文明确修订于 2026-09-08，分别保留两个日期。
- [积分规则](https://library.xujc.com/jfgz/list.htm)：年度起始、兑换及清算；未抄录未核实的图片项目分值。
- [违规及占座物品领取](https://library.xujc.com/2021/1109/c7933a133042/page.htm)：暂存和认领摘要，不替馆方作个体处分决定。

摘要均为转述，不是网页全文镜像。未核实研讨室人数门槛、赔偿金额及特定节日临时公告；检索无充分依据时返回 found=false，不再使用旧演示中的“研讨室三人签到”等固定回答。

构建命令：

```powershell
python -S -m data.scripts.build_knowledge --question "普通图书能借几天，怎么续借？"
```

生成 `data/processed/knowledge-index.json`，含真实稀疏向量、IDF、来源文件 SHA-256 和切块元数据。运行时直接从同一来源清单重建并缓存索引；修改来源文件后会重载，避免旧索引继续使用。更新时应重新阅读官网、修改有依据的主题摘要与采集时间、重建并运行规则测试。未标注发布日的页面保持 null；不能把采集时间当作生效时间。

当前使用字双元组 TF-IDF 本地向量，不依赖网络分词、嵌入模型、LLM 或 Chroma；它不是语义嵌入检索。现有 RAGRetriever 和 search_knowledge 工具已接入。配置模型后先识别意图，再按需查询数据；模型整理结果时，实际数据通过 ToolMessage 传入，规则回答附带来源和核对日期。自动测试使用替身验证证据传入及模型异常回退，不调用真实付费模型。

## 初始化与启动

从仓库根目录执行。虚构服务数据与真实输出分目录，不能覆盖原始资料：

```powershell
python -S -m data.scripts.prepare_demo
python -m pip install -r backend/requirements.txt
Copy-Item .env.example .env  # 仅当没有现有 .env 时执行
# 编辑 .env：设置 ADMIN_TOKEN（至少16字符）及 READER_TOKEN_SECRET（至少32字符）
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# 另一终端进入 frontend，npm ci 后执行 npm run dev
```

前端默认调用后端，不需要另开 mock 开关。`VITE_USE_MOCK=true` 仅用于明确的前端模拟开发。服务 demo 数据为 6 本书、3 位虚构读者、8 条流水，统一标记 simulated。

配置项：

| 配置 | 用途 |
| --- | --- |
| DATA_DIRECTORY | 同一轮 C1 的 books.csv、borrow_records.csv、quality_report.json 目录 |
| CATALOG_DATABASE | C3 构建的 catalog.sqlite3 |
| KNOWLEDGE_SOURCE | 已核对规则摘要，默认 data/knowledge/rules.json |
| USAGE_REPORT | analyze_usage 生成的聚合报告，可选；不存在时明确提示未导入 |
| OPAC_PROVIDER | disabled（默认）或 demo；不会从连接失败自动切到模拟数据 |
| ADMIN_TOKEN | 管理接口的 X-Admin-Token，未设置时拒绝访问 |
| READER_TOKEN_SECRET | 可信登录端的 HMAC-SHA256 签名密钥 |
| COOKIE_SECURE | HTTPS 部署时设 true；本机 HTTP 演示为 false |

使用真实数据时，把 DATA_DIRECTORY 指向已完成的真实清洗批次，把 CATALOG_DATABASE 指向真实导出生成的目录。不需要改变代码；路径从进程启动目录解析。更新数据应先写入新目录并完整验证，再切换配置和重启 worker；不要边查询边逐个覆盖 CSV。

缓存按文件路径、纳秒修改时间和大小识别重载；加载前后变更或计数不一致会失败，不提供模拟结果兜底。这个检查不能证明两个同计数但不同读者关系的文件来自同批，因此仍要求按不可变目录发布。

容器从仓库根构建：`docker build -f backend/Dockerfile -t xiaojia-backend .`。镜像复制运行代码、公开规则摘要及独立小型模拟夹具，`.dockerignore` 排除原始数据、处理结果和凭证；Compose 只读挂载 data/processed。配置路径须适用于容器内的 /app 工作目录。没有数据时健康检查仍成功，具体数据接口明确返回 503，便于运维区分应用存活与数据就绪。

## HTTP 与身份边界

| 接口 | 行为与权限 |
| --- | --- |
| GET /api/books/search | 公开静态书目，保留 dataset_label/scope/built_at/is_live/limitations |
| GET /api/books/{isbn} | 合法 ISBN 精确查询，未命中不返回无关书 |
| GET /api/knowledge/search?question=... | 公开规则摘要与可追溯 sources，未命中明确说明 |
| GET /api/recommend | 匿名探索推荐；Bearer 凭证解析后才按本人历史计算推荐，可选主题 query |
| GET /api/hot-books | 历史样本热门，分类过滤有效，非全馆实时榜 |
| GET /api/admin/stats/summary,hot-books,categories,publishers,trend,usage | 管理密钥保护，缺日期的 trend 返回空列表及原因 |
| POST /api/admin/purchase-advice | 历史高频需求模板，不冒称 AI 分析，不编造复本承载比、长期零借阅或增购数量 |
| GET /api/data/status | 公开能力说明，无路径、凭证或个人数据 |
| GET /api/books/holdings/{book_key} | 预留实时馆藏入口；disabled 返回 503，demo 返回显式虚构状态 |
| GET /api/reader/{reader_id}/borrows、POST /api/renew、POST /api/reserve | 当前业务由 provider 执行；真实个人身份先验证，demo 只开放 demo-reader |

读者凭证由可信登录端或运维签发，不提供“输入任意学号即可签发”的公开 HTTP 接口。现有学校 SSO 仍需后续适配；这套短期凭证不是校园登录系统。运维可在设置密钥后运行 `python -m app.issue_reader_token --reader-id "本人演示编号"`（在 backend 目录执行，或设置 PYTHONPATH），有效期默认60分钟。前端“读者凭证”输入处可使用已签发令牌；不传查询读者号，由服务端验证 sub 和 exp。

传入与身份不一致的 reader_id 返回 401/403；即使模型工具伪造参数也不能读取其他读者历史。管理密钥和读者令牌只保留当前标签页 sessionStorage；HTTPS、凭证签发和密钥轮换由实际部署端管理。

聊天历史按认证读者或随机 HttpOnly 访客 cookie 分区，不再把全站共享 session_id 当作身份。服务端内存最多保留500个会话、每会话40条消息，重启会清空；未加入外部 Redis 持久化。

## 模拟业务与后续馆方接口

OPAC_PROVIDER=demo 时，只生成虚构当前借阅、模拟续借及模拟预约；返回 dataset_label=simulated、is_live=false 和明确提示。模拟续借从原应还日延长30天，演示3次上限，不作为特殊文献真实业务规则。disabled 时不伪造当前在借、排队位置或办理成功。

后续实现 `backend/app/services/provider.py` 中 LibraryProvider 的四个方法，并通过服务工厂显式注册；需馆方提供鉴权、超时、错误码、请求和响应样例。当前没有对不明 OPAC 端点发请求。静态书目与借阅财产号仍无可靠映射，因此书目卡片不会凭空开放真实预约或把演示库存拼到真实图书上。

## 资源统计与实际验证

```powershell
python -m data.scripts.analyze_usage --input-dir "资料目录/图书馆" --dataset-label real --output data/processed/usage.json
```

读取只需 openpyxl（已在 data/requirements.txt 中），CSV 自动验证 UTF-8/GB18030，Excel 只读流式读取。研讨室文件跳过第一行合并标题，用第二行表头；原文件不修改。报告只含聚合及文件摘要，不包含读者编号、组员、论文题名或作者明细。所有流水保留，重复只诊断；分组少于5行的类别名称抑制。

本地真实输入验证：座位49,466行，研讨室17,429行，门禁刷卡165,656行，门禁汇总40,000行，读者导出56,817行，学者库39,861行。门禁刷卡的小数秒格式已支持；学者库保留15,957个日精度、12,346个月精度、11,258个年精度日期，300个不支持格式单独计数。不同来源观察周期不一致，不合并成统一利用率或趋势。

真实 HTTP 检查确认借阅36,908条、不同读者3,580、不同规范化题名22,318、人均10.3095。真实目录查询10条保持实时状态未知；经签名的本人推荐检查已读过滤，未认证请求返回401；规则带官网引用；资源接口返回6类聚合；disabled 续借返回4002，没有执行外部操作。

回归包括76项数据测试、35项后端测试和9项本机实际HTTP端到端测试；前端 TypeScript 检查及构建通过。浏览器检查了规则来源、静态书目未知状态与禁用预约按钮、管理密钥拒绝/放行和模拟来源标签。当前机器没有 Docker，镜像构建交由 PR 的 Docker CI 验证；没有执行生产部署。
