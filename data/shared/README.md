# 共享真实数据包

真实资料通过团队共享盘提供给授权成员，不进入 Git 或镜像；仓库仅保留导入脚本、校验清单和独立模拟数据。真实源缺少的日期、库存、架位及编号关系保持缺失，模拟字段另放data/fixtures/integration。

| 文件 | 内容 |
| --- | --- |
| library-real-v1.zip | 完整books.csv、borrow_records.csv、quality_report.json、馆藏导出catalog_export.csv及六类资源聚合usage.json |
| library-real-v1.manifest.json | 来源、记录数、文件长度、SHA-256 |
| library-sources-v1.zip | 原始借阅Excel及座位、门禁汇总、研讨室、读者、门禁刷卡、学者库7份原表 |
| library-sources-v1.manifest.json | 原表清单、长度与SHA-256 |

“图书数据.csv”的完整字节已在real包的catalog_export.csv中，未改列、未截断，不重复存储。来源读者编号保留提供方脱敏标识，未构造校园身份映射。

```powershell
python -S -m data.scripts.prepare_shared --dataset real
python -S -m data.scripts.prepare_shared --dataset originals
```

两份压缩包不入库，请从团队共享盘获取后放到data/shared/，脚本会自动校验SHA-256；仓库中的*.manifest.json须保留。尚未取得真实包时可直接使用integration模拟批次，测试和CI不依赖真实资料。

输出data/processed/shared-real及shared-originals。real批次包含36,908条借阅、22,632个C1书目标识和453,232条可查目录（原导出453,233条，1条缺题名跳过）。首次校验、解压并建SQLite库；原表只读。限制解压清单并逐文件校验，不覆盖其他非空批次。压缩包及派生输出均由.gitignore忽略。

使用真实服务时设置DATA_PROFILE=local，将DATA_DIRECTORY、CATALOG_DATABASE、USAGE_REPORT指向shared-real目录内对应文件。真实包不进入Docker镜像，也不会被默认服务自动解压。更多配置见[联调指南](../../docs/c-shared-data.md)。
