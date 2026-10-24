# C3 本地书目检索交付约定

按团队手册“对接 OPAC 馆藏数据源（或构建本地检索库）”交付本地检索路径。构建、查询均只依赖 Python 3.11+ 标准库和 SQLite，支持大规模 CSV 流式导入。

## 输入与来源

| 输入方式 | 标识与范围 | 规则 |
| --- | --- | --- |
| `build_catalog(data_dir, database)` | C1 的 book_key；historical_borrow_sample | 读取同目录 books.csv、可选 quality_report.json，不读取逐人流水；来源标签从质量报告读取，缺少时为 unknown |
| `build_library_catalog(source, database, dataset_label=...)` | `catalog:` 加源 ID；catalog_export | 读取馆藏导出 CSV，来源标签需显式声明，默认 unknown；ID 不等于 ISBN 或副本财产号 |

馆藏导出表头使用 `ID/TITLE/AUTHOR/PUBLISHER/YEAR/CALLNO/LANGUAGE/DOCTYPE`。ID、TITLE 必须存在；缺少其他列时补空值。额外列不进入检索库。保留文本编号和已有前导零；规范全半角和空白，索书号转大写并去空白。题名或 ID 为空的导出记录跳过并计数，元数据最多保留 20 条拒绝样本的逻辑记录序号（第一条数据序号为 2）与原因；重复 ID、重复表头、列数不一致则中止建库，保留旧库。

输出书目字段为 `book_key/title/author/isbn/call_number/publisher/category_code/category_name/publication_year/language/document_type`。馆藏导出没有 ISBN，留空；分类大类只由索书号前缀解析，不从题名推断。源表没有分类名称时 category_name 留空。C1 输入中的合法 ISBN 保持校验并支持 ISBN10/13 等价查询。

数据库元数据包括 source_file、source_sha256、built_at、dataset_label、scope、input_rows、book_count、rejected_rows 和 snapshot_count。真实导出与模拟数据的来源标签由调用者声明；`real` 不代表实时。独立生成临时库并提交完整事务后替换目标文件；失败清理临时库，旧库继续保留。查询连接使用 SQLite `mode=ro`，不会创建缺失数据库或写入当前目录。

## 查询

```powershell
python -S -m data.scripts.build_catalog --input "数据目录/图书数据.csv" --dataset-label real --database data/processed/catalog.sqlite3
python -S -m data.scripts.search_catalog --database data/processed/catalog.sqlite3 --query "计算机" --limit 5
python -S -m data.scripts.search_catalog --query "作者 关键词" --limit 10
```

`--input` 与 `--data-dir` 互斥；省略两者则从 data/processed/books.csv 建库。两个模式默认写入 data/processed/catalog.sqlite3，重复执行会覆盖，请用不同 --database 路径保存不同来源。数据文件和生成数据库不提交到仓库。

```python
from data.catalog import Catalog

catalog = Catalog("data/processed/catalog.sqlite3")
rows = catalog.search("计算机", limit=5)
response = catalog.response("TP311", limit=10)
book = catalog.get_book("catalog:源书目ID")
isbn_matches = catalog.lookup_isbn("0-306-40615-2")
metadata = catalog.info()
```

查询按规范化后的字面子串匹配书名、作者、出版社、索书号；空白分隔关键词之间为 AND。精确题名、索书号、作者匹配优先，同级按 book_key 排序，不按借阅次数排序。完整合法 ISBN 使用 ISBN 索引精确查找；非法 ISBN 的专用 lookup_isbn 返回空列表。空白查询、无结果均返回空列表，不补无关或模拟书单。limit 为 1 到 100，query 最多 200 字符和 10 个词。SQL 使用参数绑定，`%/_/\` 按字面内容匹配。

响应封装为 `{code: 0, message: "success", data, dataset_label, scope, built_at, is_live: false, limitations}`。没有读者 ID、读者属性或借阅流水。目录为导入时的静态快照，不保证覆盖全馆；通用子串查询会扫描本地目录，未实现分页或语义检索。

## 馆藏快照与未知状态

可选 `--holdings` 指定 UTF-8 CSV，表头为 `book_key,location,available,status,checked_at,source`。book_key 必须唯一且存在于本次目录。checked_at 为不晚于当前时间、包含时区的 ISO 8601 时间；source 必填；available 为空或非负整数。原始资料应由馆方提供，程序校验结构和关联，不替来源做真实性认证。

无快照时，书目结果的 location/available 为 null、status 为 unknown、holdings_snapshot 为 null。有快照时，仅将其 location 展示为有来源的位置，完整数量、状态、来源和时间保留在 holdings_snapshot 中。顶层 available 仍为 null、status 仍为 unknown，不把导出的某时刻数量宣称为当前可借状态。所有结果 is_live 均为 false。

## A、B、D 的接入边界

A 可在数据客户端调用 Catalog.search/response，按 book_key 获取详情，ISBN 查询使用 lookup_isbn，不能在未命中时返回其他书。后端 Book 模型与前端类型现已允许 location、available 为 null，并在界面显示未提供或待查询。应保留来源和 is_live，聊天话术不能把本地查询描述成“最新 OPAC 状态”。数据层与 CLI 后续已接入 HTTP 与聊天卡片，见 [C4/C5 服务说明](c4-c5-services.md)。

导出文件 ID 与借阅流水的财产号尚无可靠编号映射。不能按数值相似、前后位置或猜测匹配；书目查找可独立使用，但不能据此把未读过滤和实时可借量连接到所有推荐候选。后续需编号对照表或一致的脱敏规则。

官网 https://library.xujc.com/ 链接到 https://catalog.xujc.com/ 的 OPAC 页面，说明了访问入口；目前尚未取得可核实的搜索/馆藏 API 文档或响应样例，代码不会猜测端点、爬取登录后的页面或调用借阅写操作。真实接口接入仍待馆方资料。

## 验证

`python -S -W error -m unittest discover -s data/tests -p test_catalog.py -v` 覆盖 C3 全部 21 项测试，包括两个输入模式、ISBN 等价、字面检索、多词组合、无关查询、未知状态、快照时间和来源、只读连接、失败保留旧库和 CLI。`.github/workflows/catalog.yml` 在 Windows/Ubuntu 与 Python 3.11/3.12 组合运行，不安装任何第三方依赖。C1 原测试用于共享 ISBN 校验抽取后的回归检查。

2026 年 10 月 24 日本地验证：C1/C3 共 35 项测试，在 pandas 2.2.3、3.1.0 下分别全部通过，警告按错误处理。外部提供的书目导出共 453,233 条，导入 453,232 条，1 条因题名缺失跳过，原因及记录序号保留在数据库元数据中。23 条按间隔抽取的源 ID 查询、5 类关键词查询与无结果查询均通过；本机这 6 次通用查询耗时约 0.27–0.60 秒，不作为服务性能保证。未导入任何馆藏快照，查询中的架位、可借量均为 null。原始数据和生成目录未纳入 Git。
