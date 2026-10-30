# 小嘉 C1 数据清洗统计、C2 推荐与 C3 本地书目检索

团队联调可直接使用已提交的[模拟数据与真实资料导入脚本](../docs/c-shared-data.md)，不再依赖作者本机桌面。真实资料包从团队共享盘获取，不进入Git。显式运行`python -m data.scripts.run_integration`使用模拟批次；管理和个人接口保持鉴权。

这是 C 负责的数据模块。C1 把借阅 Excel 或 CSV 转成统一的借阅流水、图书主数据、读者列表、质量报告及看板统计；C2 基于这些输出提供热门、分类偏好、协同过滤及内容融合推荐；C3 提供可查询的本地只读书目检索库。仓库测试数据由程序生成；外部提供的真实数据仅在本地验证，汇总见 [C2 优化评估](../docs/c2-optimization.md)。

## 运行

需要 Python 3.11 或更高版本。在仓库根目录打开 PowerShell：

```powershell
python -m pip install -r data/requirements.txt
python -m data.scripts.generate_demo --rows 36908
python -m data.scripts.clean_data --input data/demo/borrow_records_demo.csv --dataset-label simulated
python -m data.scripts.analyze
python -W error -m unittest discover -s data/tests -v
```

运行后查看 `data/processed/quality_report.md`、`summary.json` 和 `dashboard.json`。四份 `api_*.json` 保留为离线响应文件；HTTP 服务现已从同批借阅数据计算统计，字段对齐既有前端约定。所有命令从仓库根目录运行。

真实数据到位后，原文件放到 `data/raw/`，替换输入路径即可：

```powershell
python -m data.scripts.clean_data --input "data/raw/图书借阅数据.xlsx" --dataset-label real
python -m data.scripts.analyze
```

默认读取第一个工作表、第一行表头。其他工作表可加 `--sheet "工作表名称"`。旧版 `.xls` 请先另存为 `.xlsx`。不要把多行说明放在表头上方。程序不会修改源文件。

## 输入与清洗规则

| 原始字段 | 标准字段 | 处理 |
| --- | --- | --- |
| 证件号 | reader_id | 按文本读取，保留已有前导零 |
| 索书号 | call_number | 全半角统一，转大写，清除空白 |
| 财产号或条码号 | book_id | 按文本读取，表示副本标识 |
| 题名或书名 | title | 全半角统一，压缩多余空白 |
| 责任者或作者 | author | 保留内容，规范空白 |
| ISBN 或 IISSBN | isbn | 清除 ISBN 前缀、分隔符，检查 10/13 位校验码 |
| 出版社或出版者 | publisher | 保留内容，规范空白 |

必须有证件号和题名两列表头。其余列缺失时会补空列并写入报告。缺少读者或题名的行转入待核查文件；不猜测身份或补造书名。相同标准字段的流水只报告疑似重复并保留，因为当前没有日期或流水号判断它是否是真实复借。

图书主键 `book_key` 优先使用通过校验的 ISBN13，将等价的 ISBN10 合并。没有合法 ISBN 时，先查同一财产号在其他有效流水中是否唯一对应某个合法 ISBN；可确认就关联，但不改写原始 ISBN 字段。不能确认时使用财产号；财产号也缺失时使用题名、作者、出版社的精确组合哈希。完全缺少有效关联的不同副本仍可能分开计算，需结合质量报告看待书种数。一个财产号对应多个合法 ISBN 时报告冲突，不据此补做关联。同一 ISBN 出现冲突题名、作者、出版社时，报告冲突组数，主数据显示最常见非空值，流水仍保留原信息。books.csv 的 ISBN 只输出经过校验的标准 ISBN13，其余留空。

## 输出

默认输出到 `data/processed/`，重复运行覆盖同名生成文件，不追加：

| 文件 | 内容 |
| --- | --- |
| borrow_records.csv | 接受的借阅流水，含源行号、book_key、分类 |
| books.csv | 按 book_key 汇总的图书主数据、借阅次数、出现过的副本数 |
| readers.csv | 读者列表、借阅次数、借过的不同 book_key 数 |
| rejected_records.csv | 待核查流水及原因，源行号可追溯至原文件 |
| quality_report.json 和 .md | 缺失率、疑似重复、错号、分类及主数据冲突 |
| summary.csv 和 .json | 总借阅、读者、图书标识、题名、副本数、人均借阅 |
| hot_books.csv 和 .json | 热门图书 TOP100，以借阅次数排序 |
| categories.csv 和 .json | 中图法大类借阅次数及占比，包含未知分类 |
| publishers.csv 和 .json | 出版社 TOP20，空白出版社以缺失标志区分 |
| reader_distribution.csv 和 .json | 每种借阅次数对应的读者人数 |
| reader_preferences.csv 和 .json | 每位读者的分类次数和占比 |
| dashboard.json | 给 B 对接的数据结构示例，不含读者标识或逐人偏好 |
| api_summary.json 等四份 api_*.json | 按既有契约封装的概览、热门图书、分类、出版社响应 |

所有统计基于接受的流水。图书数是借阅样本内的 `book_key` 数，并非方案按唯一题名统计的 22,318；另有 `unique_title_count` 可做同口径比较。副本数只代表数据里出现过的副本，不能当作馆藏复本总量。出版社、未知类别均保留实际缺失语义。

输入没有借阅日期、架位、读者年级或专业，首版不生成趋势、实时馆藏状态和这些属性画像。“读者画像”只指历史借阅分类偏好。采购复购率还需要馆藏总量、复本和可用状态数据。

## 测试数据

模拟 CSV 固定随机种子为 20261023，默认包含 36,908 行模拟流水，候选池为 358 个虚构读者和 200 本虚构图书，并注入缺失、错误 ISBN、未知分类及相同流水。规模与方案相同仅用于测试程序，不复现真实读者数或真实书种数。仓库保存生成脚本，生成的数据留在本地。

可重新生成 CSV：

```powershell
python -m data.scripts.generate_demo --rows 36908 --output data/demo/borrow_records_demo.csv
```

## C2 推荐

先完成上面的 C1 清洗，再从仓库根目录运行：

```powershell
# 交互探索推荐可按书名、作者或主题筛选；模拟资料无需真实文件
python -m data.scripts.recommend --data-dir data/fixtures/integration --query Python
# 显式查看热门基线；分类支持 T 大类和 TP 等字母前缀
python -m data.scripts.recommend --strategy popular --category TP --limit 10
# 探索推荐会过滤完整已读集合，结合内容、相似读者和分类偏好
python -m data.scripts.recommend --reader-id 000002 --limit 5
# 原有可复现排名保留为显式基线，可单独运行分类偏好或协同过滤
python -m data.scripts.recommend --reader-id 000002 --strategy hybrid --limit 5
python -m data.scripts.recommend --reader-id 000002 --strategy category --category I
python -m data.scripts.recommend --reader-id 000002 --strategy collaborative --data-dir data/processed
# 可选写入本地文件；默认只向终端输出 JSON
python -m data.scripts.recommend --reader-id 000002 --output data/processed/private/recommendations.json
# 对全部读者运行四种策略，并做固定抽样留出评估；仅保存汇总，不导出逐人结果
python -m data.scripts.validate_recommendations --limit 20 --holdout-readers 200 --output data/processed/recommendation_validation.json
```

`hybrid`、`popular`、`category`、`collaborative` 四种策略均过滤该读者的全部已借书籍；无历史或无相似读者时使用可用的分类偏好或热门度，不补回已读书。缺 ISBN 的不同副本在完整题名、作者、出版社精确一致，且不涉及多个 ISBN 时可合并为同一推荐候选。仅从历史借阅中出现过的书目推荐，不能表示全馆书目或实时可借书。

聊天、HTTP 推荐和 CLI 默认使用 `discovery`：按用户主题筛选，在符合条件的候选中结合兴趣抽样，不按借阅次数排序；同一服务进程内的同一会话会优先避开上一批书。明确要求“热门”时，先筛选历史借阅较多的候选，再换批抽样，不能代表实时热度。匿名用户不推断个人兴趣；候选不足时可能重复。原有四种确定性策略保留供基线对比。细节及真实样本离线对照见 [探索推荐说明](../docs/c2-discovery-evaluation.md)。

C2 运行时仅依赖 Python 标准库，读入 `books.csv`、完整 `borrow_records.csv` 和可选的 `quality_report.json`，不依赖 LLM、向量库或 pandas。清洗仍使用 C1 的 pandas/openpyxl 依赖。输入缺失或不同批次的文件计数不匹配时明确报错。

返回现有 `{code, message, data}` 封装及 `dataset_label`，书单保留 `title/author/isbn/call_number/reason`，另外提供 `book_key/count/category/score/strategy`。结果没有读者标识、邻居明细或臆造的架位、可借数量。算法、Python 调用和 A 的接入说明见 [C2 推荐交付约定](../docs/c2-recommendation.md)。

## C3 本地书目检索

C3 支持馆藏书目 CSV 导出与 C1 books.csv 两种输入，使用 SQLite 和 Python 标准库，无需联网或额外检索服务。

```powershell
# 馆藏导出：ID/TITLE/AUTHOR/PUBLISHER/YEAR/CALLNO/LANGUAGE/DOCTYPE
python -m data.scripts.build_catalog --input "数据目录/图书数据.csv" --dataset-label real
# 或者从 C1 的历史借阅样本书目建库
python -m data.scripts.build_catalog --data-dir data/processed
# 上面两种命令默认覆盖同一个 catalog.sqlite3；用 --database 可分别保存
python -m data.scripts.search_catalog --query "计算机" --limit 5
python -m data.scripts.search_catalog --query "TP311" --limit 10
python -S -W error -m unittest discover -s data/tests -p test_catalog.py -v
```

支持书名、作者、出版社、索书号与合法 ISBN10/13 检索，空白分隔的多个词均需匹配；无结果返回空列表。缺 ISBN 的馆藏导出保留空值，不从 ID 生成 ISBN。馆藏导出 ID 使用 `catalog:` 命名空间，与借阅流水财产号分开。

本地目录不会生成实时馆藏信息。未提供馆藏快照时，`location/available` 为 null，`status` 为 unknown；可选快照需来源和时间，数量只放在 `holdings_snapshot`，不会提升为当前可借状态。原始文件不修改，数据库、来源摘要和缺失记录计数留在本地被忽略的输出目录。字段、快照格式及后端接入说明见 [C3 检索交付约定](../docs/c3-catalog.md)。

## 团队对接

模块位于 `data/`，测试位于 `data/tests/`，轻量依赖位于 `data/requirements.txt`，与现有后端依赖下限保持一致。前端和现有后端服务入口由各自负责人接入。`docs/c-data-contract.md` 说明原生统计字段与现有接口字段的映射；`total_titles` 使用规范化题名数，和 `book_key` 数分开。

本地raw/processed/demo输出和data/shared/*.zip均由.gitignore忽略。原始文件及逐人借阅不进入Git或镜像；授权成员从团队共享盘取得真实资料后，使用data/shared中的清单校验并导入。独立模拟源提交到data/fixtures/integration，同事无需真实资料即可联调。

C1–C5 的本地数据、推荐、规则检索和统计接口已实现并接入后端与页面。馆方实时业务预留 disabled/demo provider，当前没有执行真实 OPAC 写操作；编号映射和学校 SSO 仍需馆方适配。运行、权限、来源与边界见 [C4/C5 服务说明](../docs/c4-c5-services.md)。

## C4/C5 与资源统计

规则来源为已核对的图书馆官网摘要，支持带引用的本地稀疏向量检索。统计、推荐和目录接口已接入，前端默认访问后端。管理接口需配置访问密钥，个人推荐使用可信签发的读者令牌；无凭证提供非个性化探索推荐。

```powershell
python -S -m data.scripts.build_knowledge --question "普通图书续借几次"
python -S -m data.scripts.prepare_demo
python -m data.scripts.analyze_usage --input-dir "资料目录/图书馆" --dataset-label real --output data/processed/usage.json
```

资源统计分别处理座位、研讨室、门禁、读者和学者库；不推断跨表编号关系，不生成无依据的利用率。`OPAC_PROVIDER=demo` 才提供显式虚构的当前借阅、续借与预约流程；默认 disabled 不伪造办理成功。详见 [启动与验收](../docs/c4-c5-services.md)。
