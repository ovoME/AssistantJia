# 虚构联调源数据

20本书、40册副本、12位虚构读者、180条带日期借阅。日期固定为2026-09-01至09-30，as_of为9月30日23时。书名用于常见查询示例；作者、ISBN、身份、日期、库存及物理位置均为模拟值。

| 文件 | 用途 |
| --- | --- |
| books.csv | C1/C2兼容书目及次数 |
| borrow_records.csv | 借阅日期、归还日期、date_source=simulated |
| copies.csv | 唯一book_id、catalog_id、book_key、模拟状态/位置/更新时间 |
| book_crosswalk.csv | 完整模拟财产号与书目ID对照 |
| holdings.csv | 与副本状态相符的汇总模拟库存 |
| readers.csv | 独立虚构身份，无真实读者映射 |
| current_borrows.json | 与on_loan副本对应的当前模拟借阅 |
| usage.json | 六类模拟资源统计 |
| manifest.json、quality_report.json | 模拟来源、固定时点和规模 |

支持“三体”“物流”“Python”“F252.8/11”。示例读者demo-reader、财产号DEMO-JGG-000001、馆藏ID DEMO-CAT-0001。

运行`python -S -m data.scripts.prepare_shared --dataset integration`生成派生目录。DATA_PROFILE=integration显式选择此批次，管理及个人接口仍须有效凭证。维护者用data/scripts/create_integration_fixture.py重建并提交源文件；更新后用新输出目录准备，不能只在作者本机生成数据。
