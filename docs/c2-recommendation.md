# C2 推荐交付约定

交付日期：2026 年 10 月 24 日。输入为 C1 输出，回归测试使用虚构记录，并已在本地使用提供的真实借阅表做功能和离线效果验证。C2 交付历史借阅推荐算法、Python 调用及 CLI；现有 HTTP 路由的数据切换与鉴权需 A、D 接入。

## 输入和生命周期

从同一轮 C1 清洗输出目录读取 `books.csv` 和完整 `borrow_records.csv`，不使用截断后的热门 TOP100。`quality_report.json` 存在时读取 `dataset_label`（simulated、real、unknown），缺少时标记 unknown，不猜测数据来源。表头、唯一 book_key、关联完整性、每个 book_key 的流水数与 books.borrow_count、质量报告接受行数均检查；空数据返回空书单，数据文件不一致会报错。

`data.recommendation` 只依赖标准库。实例在初始化时建立内存索引，后续查询不会写文件或修改索引。每个 worker 在启动时加载；C1 重跑后由服务端重新建实例并替换，不能在写入中途加载一半新文件。当前计数校验不能识别“行数及各书次数相同、读者关系不同”的混合快照，部署时需用独立目录生成完整批次后切换。

## 算法

| 策略 | 规则 |
| --- | --- |
| popular | 按历史借阅次数降序，同频按 book_key 排序 |
| category | 从读者借过的不同书种计算中图大类偏好，再结合热门度 |
| collaborative | 二元读者-书种集合，余弦相似度计算读者邻居；取相似度最高的 30 位，累加其候选贡献 |
| hybrid（默认） | 内容相似度与协同、分类偏好及热门的基础分融合；缺少内容证据时使用基础分 |

重复借阅仍计入热门度，与 C1 保留流水的口径一致。分类偏好与协同过滤使用去重书种，避免同一人反复借同一本书膨胀偏好或相似度。没有日期，不使用“近期”或时间衰减。

邻居相似度为 `|H(u) ∩ H(v)| / sqrt(|H(u)| * |H(v)|)`。候选协同分数为借过该候选的前 30 位邻居相似度之和，除以这些邻居的相似度总和。分类分数为该读者借过的此大类不同书种数，除以其全部已识别大类不同书种数；UNKNOWN 不作为兴趣证据。热门分数为候选借阅次数除以本次候选最大次数。

基础分保持首版规则：同时有协同与分类信号时权重为 `0.6/0.3/0.1`；只有协同时为 `0.9/0.1`；只有分类时为 `0.8/0.2`；两者都没有时仅按热门度。`category` 和 `collaborative` 策略只启用各自的个性化信号及热门兜底，`popular` 只按热门度。

默认 hybrid 新增静态书目内容索引。题名经 NFKC、大小写规范化后，在连续文字片段内取相邻两个字符；完整责任者作为单个特征；索书号仅解析分类段（如 TP311.1），使用首位数字、前三字符和完整分类，不用斜线后的种次号。题名、作者、粗/中/细分类特征权重分别为 1、2、0.5/1/1.5，同一分类特征重合时保留较细层级的权重。不使用出版社、读者身份或借阅次数作为内容特征；不跨不同责任者字符串猜测同一作者。

仅保留至少出现于两本书、少于全部书目、且文档频次不超过 `max(2, 书目数×15%)` 的特征，排除无区分度的常见词；未知、佚名等责任者不建特征。特征乘以 `log((N+1)/(df+1))` 后做 L2 归一化。读者画像为不同已读书向量之和再归一化，倒排索引计算候选与画像的余弦相似度。静态书目中零训练借阅次数的书也可通过内容进入候选；词面相似不代表深层语义理解。

有内容匹配时，基础分和内容分各除以本次过滤后候选中的最大值，最终为 `0.75×内容分 + 0.25×基础分`。0.75 从预设的 0、0.25、0.5、0.75、1 五个值中由 600 人验证集选择，另有互斥的 600 人测试集，详见 [优化评估](c2-optimization.md)。所有候选都没有内容匹配时，直接保留原基础分和回退逻辑。分数相同按借阅次数、book_key 排序，使用堆选择前 limit 项以减少全量排序。score 是排序分数，不是命中概率。

所有策略在排名前过滤完整已读集合和指定分类；候选不足时返回少于 limit 的书单，全部读过则返回空列表。新读者、未知读者、不传读者时均回退热门度。category 支持 C1 中图大类及索书号字母前缀，例如 `I`、`T`、`TP`、`UNKNOWN`；`T` 含 TP、TU 等，TP 根据实际索书号前缀筛选。筛选无结果时不会换成其他类别。limit 范围为 1 到 100。

## 缺 ISBN 和同书识别

C1 已将合法 ISBN10/13 转为 ISBN13 主键，并通过唯一财产号关联缺号流水。C2 进一步对完整题名、作者、出版社做全半角/空白规范化及大小写统一后的精确匹配：同组只有一个 ISBN 主键时，将缺号副本关联过去；没有 ISBN 时，合并为最小 book_key 代表的候选。存在多个不同 ISBN 或缺少完整元数据时不推断跨副本关联。

归并后热门次数相加、读者历史集合合并；代表项保留 ISBN 主键对应的 C1 元数据，否则使用最小 book_key 的元数据。C1 CSV 不会被改写。明确不同 ISBN 的版本保持分开；无法确认的缺号/残缺元数据副本仍可能分开，是数据质量限制。

## Python 调用与 A 的接入

在仓库根目录可直接运行：

```python
from data.recommendation import Recommender

engine = Recommender.from_directory("data/processed")
recommendations = engine.recommend(reader_id="000002", limit=5)
literature_hot = engine.hot_books(category="I", limit=10)
response = engine.response(reader_id="000002", limit=5)
```

`recommend()` 的参数名兼容现有 `DataClient.get_recommendations(reader_id, limit)`；`hot_books(category, limit)` 可供现有 `/api/hot-books` 使用。A 可在数据客户端初始化时加载引擎，再将两个方法的返回列表交给现有响应模型。运行时需能导入仓库的 `data` 包；现有根目录 Compose 已将 `./data` 挂载到 `/app/data`，单独构建后端镜像时则需另配置代码和数据位置。

response 为 `{code: 0, message: "success", data: [...], dataset_label, limitations}`。每本书含原契约要求的 `title/author/isbn/call_number/reason`，以及 `book_key/publisher/category/category_name/count/score/strategy`。ISBN 缺失仍为空字符串，book_key 用于唯一识别；输出 strategy 表示主要依据（content/collaborative/category/popular）。内容分贡献大于基础分贡献时标记 content；这是新增的输出值，输入策略仍只有 hybrid/popular/category/collaborative 四种。冷启动不会伪称个性化。应保留 dataset_label 和历史样本限制，避免模拟数据被展示成馆方实时数据。

响应没有目标读者 ID、邻居 ID 或邻居书单。读者历史和个性化推荐需由服务端按已认证身份读取，不能直接信任公开 query 中的 reader_id；该库和 CLI 不承担 HTTP 身份认证。推荐输出不包含 location、available、status；实时馆藏状态由 C3 的经核实数据源补充。

## 验证

```powershell
python -W error -m unittest discover -s data/tests -v
python -m data.scripts.generate_demo --rows 36908
python -m data.scripts.clean_data --input data/demo/borrow_records_demo.csv --dataset-label simulated
python -m data.scripts.recommend --reader-id 000002 --limit 5
```

自动检查位于 `.github/workflows/data.yml`，在 pandas 2.2.3 与 3.1.0 下运行 C1/C2 全部测试，并跑通 800 条模拟记录的生成、清洗、统计、推荐流程。推荐 CLI 使用 `python -S` 验证不需要第三方依赖。测试覆盖手算协同相似度、偏好排序、重复流水、已读过滤、缺号副本、歧义版本、分类筛选、冷启动、空数据、文件一致性和响应契约。

当前本地验证为 Python 3.12.14：pandas 2.2.3、3.1.0 下各 47 项测试全部通过，警告按错误处理。测试包括内容召回零借阅书、分类与已读过滤、未知责任者、确定性、验证/测试/旧样本互斥、全部复借移除、训练零计数保留及冻结参数检查。首版的 36,908 条模拟流水流程记录保留于此前提交；当前优化验证见下列报告。

已补充外部提供借阅表的验证，见 [C2 真实数据验证](c2-real-validation.md)。`python -S -m data.scripts.validate_recommendations` 对全部读者和四种策略检查已读、重复、字段、分数与来源标签，再做固定哈希抽样的留一法评估；报告只含汇总，不输出读者 ID 或逐人书单。对被留出的书种移除该读者的全部复借流水，重新计算训练借阅次数与邻居关系，不在完整历史模型上计算命中率。

当前没有借阅日期。离线留出结果只反映此次抽样回放，不能替代按时间验证、读者评价或线上效果。
