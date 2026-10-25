# 团队共享数据与DS工具联调

2026-10-25。此前真实清洗输出与目录库只在作者本机data/processed，被Git忽略；其他成员没有数据时接口返回503。本次提供导入脚本与模拟夹具；真实资料包不入库，由授权成员从团队共享盘获取。

## 数据来源

| 选择 | 内容及边界 |
| --- | --- |
| local＋真实包 | 完整36,908条借阅、453,233条原始目录（453,232条可导入）及原表和聚合；缺日期、状态及对照保持未知 |
| integration | 20本书、40册、12人、180条模拟借阅，完整模拟日期/库存/位置/编号对照及六类资源汇总 |

真实包的校验清单在[data/shared](../data/shared/README.md)。从团队共享盘取得两份压缩包（约56MiB）后，放到data/shared/，保留原文件名；导入脚本按清单检查逐文件SHA-256及大小。八份源表包含在这两包中，目录CSV不重复存储。压缩包和解压输出均不进入Git。模拟源在[data/fixtures/integration](../data/fixtures/integration/README.md)。未给真实流水随机补日期，也不把真实财产号随意对到模拟ID。索书号不能单独证明楼层和物理架位。

## 从新电脑启动

从仓库根目录执行：

```powershell
python -m pip install -r backend/requirements.txt
python -m data.scripts.run_integration
```

只绑定127.0.0.1:8000，首次从已提交源文件准备数据，不依赖桌面文件。该命令只选择模拟数据，不生成或打印管理密钥、不放宽身份检查。管理和个人接口继续使用现有ADMIN_TOKEN、READER_TOKEN_SECRET配置及可信端签发的凭证；未配置时公开目录/规则可查，受保护请求明确拒绝。

也可设置DATA_PROFILE=integration按原方式启动。默认仍为local，普通部署不自动切换模拟。容器包含并预构建小型模拟数据，但须显式选择integration；真实资料从镜像上下文排除。

仅准备模拟数据，无需后端依赖或真实资料：

```powershell
python -S -m data.scripts.prepare_shared --dataset integration
```

取得真实包并放到data/shared/后，再按需导入：

```powershell
python -S -m data.scripts.prepare_shared --dataset real
python -S -m data.scripts.prepare_shared --dataset originals
```

默认输出shared-integration-v1、shared-real、shared-originals，均在data/processed。同版本可重复准备；不同来源非空目录拒绝覆盖，可用--output指定新目录。

CI只使用模拟数据和程序内生成的测试压缩包。真实包完整性测试在本地取得对应压缩包时运行，未取得时明确跳过，不从共享盘自动下载资料。

## 查询示例

```text
GET /api/books/search?query=三体&limit=5
GET /api/books/search?query=物流
GET /api/books/search?query=F252.8%2F11
GET /api/books/holdings/DEMO-JGG-000001
GET /api/books/holdings/DEMO-CAT-0001
GET /api/data/status
```

模拟结果包含dataset_label=simulated、is_live=false、as_of/updated_at，以及与副本一致的available/status/location。不认识的模拟编号返回明确错误，不默认编造库存。

有本人Bearer凭证后，可请求/api/recommend?reader_id=demo-reader、/api/reader/me/borrows，并POST /api/renew，body为`{"reader_id":"me","book_id":"DEMO-JGG-000001"}`。可信登录端或运维按原方式签发demo-reader短期令牌；不提供按任意学号公开签发的接口，模型参数不代表认证身份。

管理接口仍用X-Admin-Token。integration下概览为180条借阅、12名读者、20个题名；/api/admin/stats/trend为2026-09-01至09-30每天6条，days=7取样本末日之前7天，来源明确模拟。切回local真实批次后，源无日期则仍为空。模拟usage始终读取模拟汇总，不读取作者本机真实统计。

## DS如何读取

search_books工具与HTTP使用同一准备目录，返回来源标签、is_live和限制。实际结果通过ToolMessage传入已配置的DS兼容模型，不把整份压缩包发给模型，也不让模型凭记忆生成库存。模拟模式聊天会提示架位/数量均为模拟。

测试以模型替身验证常见书名/索书号查询、库存和实际证据传入；不消耗DS额度，也不声称验证了每个成员的API密钥或网络。若目录接口成功而DS失败，应再查模型连接、工具绑定和读者上下文。

## 之后换真数据

准备real批次后设DATA_PROFILE=local，将DATA_DIRECTORY、CATALOG_DATABASE、USAGE_REPORT指向shared-real并重启worker。真实OPAC继续通过LibraryProvider适配；真实财产号对照、物理架位和更新时间仍需核实。copies.csv与book_crosswalk.csv只定义样例结构，不替真实数据建立猜测关系。
