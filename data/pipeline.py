"""借阅流水清洗和统计。保留流水粒度，不推断馆藏、日期或真实可借状态。"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

FIELDS = ["reader_id", "call_number", "book_id", "title", "author", "isbn", "publisher"]
ALIASES = {
    "reader_id": ["reader_id", "证件号", "读者证号", "读者编号", "读者ID"],
    "call_number": ["call_number", "索书号"],
    "book_id": ["book_id", "财产号", "条码号", "图书条码"],
    "title": ["title", "题名", "书名"],
    "author": ["author", "责任者", "作者"],
    "isbn": ["isbn", "iissbn", "issbn", "国际标准书号"],
    "publisher": ["publisher", "出版社", "出版者"],
}
# 中图法大类；不从题名猜分类。
CATEGORIES = {
    "A": "马克思主义 列宁主义 毛泽东思想 邓小平理论",
    "B": "哲学 宗教", "C": "社会科学总论", "D": "政治 法律",
    "E": "军事", "F": "经济", "G": "文化 科学 教育 体育",
    "H": "语言 文字", "I": "文学", "J": "艺术", "K": "历史 地理",
    "N": "自然科学总论", "O": "数理科学和化学", "P": "天文学 地球科学",
    "Q": "生物科学", "R": "医药 卫生", "S": "农业科学", "T": "工业技术",
    "U": "交通运输", "V": "航空 航天", "X": "环境科学 安全科学", "Z": "综合性图书",
    "UNKNOWN": "未识别分类",
}


def text(value) -> str:
    """保留字符串标识符；仅做全半角和空白规范化。"""
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip()


def header_key(value) -> str:
    return re.sub(r"[\s_]+", "", text(value)).casefold()


def normalize_isbn(value) -> str:
    value = re.sub(r"^ISBN(?:-1[03])?\s*[:：]?\s*", "", text(value), flags=re.I)
    return re.sub(r"[\s\-‐‑–—]", "", value).upper()


def canonical_isbn(value: str) -> str:
    """合法 ISBN 返回 ISBN13；错误号码返回空串，不把错号当图书主键。"""
    if re.fullmatch(r"\d{9}[\dX]", value):
        digits = [int(c) if c != "X" else 10 for c in value]
        if sum((10 - i) * d for i, d in enumerate(digits)) % 11:
            return ""
        base = "978" + value[:9]
        check = (-sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(base))) % 10
        return base + str(check)
    if re.fullmatch(r"97[89]\d{10}", value):
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value))
        return value if total % 10 == 0 else ""
    return ""


def category_for(call_number: str) -> str:
    match = re.match(r"([A-Z])(?=[\dA-Z.(]|$)", call_number)
    return match[1] if match and match[1] in CATEGORIES else "UNKNOWN"


def read_source(path: Path, sheet: str | int = 0) -> pd.DataFrame:
    """CSV UTF-8（含 BOM）/GB18030，XLSX 首行表头。所有字段按字符串读取。"""
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return pd.read_excel(path, sheet_name=sheet, dtype=str, keep_default_na=False, engine="openpyxl")
    if suffix == ".csv":
        try:
            return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="gb18030")
    raise ValueError("目前支持 .xlsx 和 .csv；旧版 .xls 请另存为 .xlsx。")


def stable_value(values: pd.Series) -> str:
    """主数据选择最常见的非空值；同频时按文字排序，保证复跑一致。"""
    counts = values[values != ""].value_counts()
    return sorted(counts[counts == counts.max()].index)[0] if len(counts) else ""


def make_book_key(row: pd.Series) -> str:
    isbn13 = canonical_isbn(row["isbn"])
    if isbn13:
        return "isbn:" + isbn13
    if row["book_id"]:
        return "copy:" + row["book_id"]
    # 没有可靠书号和财产号时用精确元数据作临时标识，不做模糊合并。
    payload = json.dumps([row[c] for c in ("title", "author", "publisher")], ensure_ascii=False)
    return "metadata:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def clean_frame(raw: pd.DataFrame, dataset_label: str = "unknown"):
    """返回清洗流水、图书、读者、待核查流水、质量报告。"""
    if dataset_label not in {"simulated", "real", "unknown"}:
        raise ValueError("dataset_label 只能为 simulated、real 或 unknown。")
    if not raw.columns.is_unique:
        raise ValueError("源表存在重复列名，请先确认表头。")
    lookup = {header_key(alias): field for field, aliases in ALIASES.items() for alias in aliases}
    mapping = {}
    for col in raw.columns:
        dest = lookup.get(header_key(col))
        if dest:
            if dest in mapping.values():
                raise ValueError(f"多列映射到 {dest}，请先确认并合并对应源列。")
            mapping[col] = dest
    missing_columns = [c for c in FIELDS if c not in mapping.values()]
    if {"reader_id", "title"} & set(missing_columns):
        raise ValueError("源表必须包含证件号/reader_id 和题名/title 两列表头。")
    normalized = raw[list(mapping)].rename(columns=mapping).reset_index(drop=True)
    for field in FIELDS:
        if field not in normalized:
            normalized[field] = ""
        normalized[field] = normalized[field].map(text)
    normalized = normalized[FIELDS].copy()
    normalized["isbn"] = normalized["isbn"].map(normalize_isbn)
    normalized["call_number"] = normalized["call_number"].str.upper().str.replace(r"\s+", "", regex=True)
    normalized["source_row"] = range(2, len(normalized) + 2)
    normalized["category_code"] = normalized["call_number"].map(category_for)
    normalized["category_name"] = normalized["category_code"].map(CATEGORIES)
    normalized["book_key"] = normalized.apply(make_book_key, axis=1) if len(normalized) else pd.Series(dtype=str)
    reasons = normalized.apply(
        lambda r: ";".join(c + "_missing" for c in ("reader_id", "title") if not r[c]), axis=1
    ) if len(normalized) else pd.Series(dtype=str)
    # 同一财产号在其他有效流水中只有一个合法 ISBN 时，可以精确关联。
    # 只修复 book_key，不填造原始 isbn；冲突财产号不用于关联。
    canonical = normalized["isbn"].map(canonical_isbn)
    links = pd.DataFrame({"book_id": normalized["book_id"], "isbn13": canonical})
    links = links[(reasons == "") & (links["book_id"] != "") & (links["isbn13"] != "")]
    copy_isbns = links.groupby("book_id")["isbn13"].agg(lambda values: sorted(set(values)))
    unique_links = {copy: values[0] for copy, values in copy_isbns.items() if len(values) == 1}
    recovered = normalized["book_id"].map(unique_links).fillna("")
    resolve_mask = (canonical == "") & (recovered != "")
    if resolve_mask.any():
        normalized.loc[resolve_mask, "book_key"] = "isbn:" + recovered[resolve_mask]
    rejected = normalized[reasons != ""].copy()
    rejected["reject_reason"] = reasons[reasons != ""]
    clean = normalized[reasons == ""].copy().reset_index(drop=True)
    book_columns = ["book_key", "title", "author", "isbn", "call_number", "publisher",
                    "category_code", "category_name", "borrow_count", "observed_copy_count"]
    book_rows, metadata_conflicts = [], 0
    for key, group in clean.groupby("book_key", sort=True):
        item = {c: stable_value(group[c]) for c in ("title", "author", "isbn", "call_number", "publisher")}
        item["isbn"] = key.removeprefix("isbn:") if key.startswith("isbn:") else ""
        item.update(book_key=key, category_code=category_for(item["call_number"]),
                    borrow_count=len(group), observed_copy_count=group.loc[group["book_id"] != "", "book_id"].nunique())
        item["category_name"] = CATEGORIES[item["category_code"]]
        book_rows.append(item)
        metadata_conflicts += int(any(group.loc[group[c] != "", c].nunique() > 1 for c in ("title", "author", "publisher")))
    books = pd.DataFrame(book_rows, columns=book_columns)
    readers = clean.groupby("reader_id", sort=True).agg(
        borrow_count=("book_key", "size"), unique_book_count=("book_key", "nunique")
    ).reset_index()
    missing = {c: int((normalized[c] == "").sum()) for c in FIELDS}
    report = {
        "dataset_label": dataset_label,
        "input_rows": len(raw), "accepted_rows": len(clean), "rejected_rows": len(rejected),
        "missing_columns": missing_columns,
        "unmapped_columns": [str(c) for c in raw.columns if c not in mapping],
        "missing_counts": missing,
        "missing_rates": {c: round(v / len(raw), 6) if len(raw) else 0 for c, v in missing.items()},
        "normalized_duplicate_excess_rows": int(normalized.duplicated(subset=FIELDS).sum()),
        "duplicate_policy": "preserved_no_event_id_or_borrow_date",
        "invalid_isbn_rows": int(normalized["isbn"].map(lambda s: bool(s) and not bool(canonical_isbn(s))).sum()),
        "unknown_category_rows": int((normalized["category_code"] == "UNKNOWN").sum()),
        "book_metadata_conflict_groups": metadata_conflicts,
        "copy_isbn_conflict_groups": int(copy_isbns.map(len).gt(1).sum()),
        "book_key_resolved_by_copy_rows": int(resolve_mask.sum()),
        "books_by_key": len(books), "readers": len(readers),
        "warnings": [
            "相同的七字段记录可能是重复导出或真实复借，已保留，需日期或流水号判定。",
            "book_key 优先合法 ISBN13；缺失或错误 ISBN 可通过唯一财产号与合法 ISBN 的映射关联，再回退财产号或精确元数据哈希。",
            "缺少读者或题名的行已转入 rejected_records.csv，待核查后重跑，未补造内容。",
            "Excel 中已丢失的前导零或超过数字精度的编号无法恢复，源数据的编号应存为文本。",
        ],
    }
    return clean, books, readers, rejected, report


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def records(frame: pd.DataFrame):
    return json.loads(frame.to_json(orient="records", force_ascii=False))


def save_table(folder: Path, name: str, frame: pd.DataFrame, with_json: bool = True):
    frame.to_csv(folder / f"{name}.csv", index=False, encoding="utf-8-sig")
    if with_json:
        write_json(folder / f"{name}.json", records(frame))


def clean_file(path: Path, output: Path, dataset_label: str = "unknown", sheet: str | int = 0):
    output.mkdir(parents=True, exist_ok=True)
    clean, books, readers, rejected, report = clean_frame(read_source(path, sheet), dataset_label)
    report["source_file"] = path.name
    for name, frame in [("borrow_records", clean), ("books", books), ("readers", readers), ("rejected_records", rejected)]:
        save_table(output, name, frame, with_json=False)
    write_json(output / "quality_report.json", report)
    report_lines = ["# 借阅数据质量报告", "", f"数据标识：{dataset_label}",
                    f"输入 {len(clean) + len(rejected):,} 行，接受 {len(clean):,} 行，待核查 {len(rejected):,} 行。",
                    f"规范化后疑似重复的多余行 {report['normalized_duplicate_excess_rows']:,} 行，全部保留。",
                    f"非空但无效的 ISBN {report['invalid_isbn_rows']:,} 行，未识别分类 {report['unknown_category_rows']:,} 行。", "",
                    "| 字段 | 缺失数 | 缺失率 |", "| --- | ---: | ---: |"]
    report_lines += [f"| {c} | {missing} | {report['missing_rates'][c]:.2%} |" for c, missing in report["missing_counts"].items()]
    report_lines += ["", *report["warnings"], ""]
    (output / "quality_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    return report


def analyze_frame(clean: pd.DataFrame):
    needed = {*FIELDS, "book_key", "category_code", "category_name"}
    if not needed.issubset(clean.columns):
        raise ValueError("请先运行 clean_data，统计输入应为生成的 borrow_records.csv。")
    _, books, readers, _, _ = clean_frame(clean[FIELDS])
    n = len(clean)
    summary = {
        "borrow_count": n, "reader_count": len(readers), "book_count": len(books),
        "unique_title_count": int(clean["title"].nunique()),
        "observed_copy_count": int(clean.loc[clean["book_id"] != "", "book_id"].nunique()),
        "borrows_per_reader": round(n / len(readers), 4) if len(readers) else None,
        "scope": "historical_borrow_records",
    }
    hot = books.sort_values(["borrow_count", "book_key"], ascending=[False, True]).head(100).reset_index(drop=True)
    hot.insert(0, "rank", range(1, len(hot) + 1))
    categories = clean.groupby(["category_code", "category_name"], sort=True).size().reset_index(name="borrow_count")
    categories["share"] = categories["borrow_count"] / n if n else pd.Series(dtype=float)
    categories = categories.sort_values(["borrow_count", "category_code"], ascending=[False, True]).reset_index(drop=True)
    publisher_source = clean[["publisher"]].copy()
    publisher_source["publisher_missing"] = publisher_source["publisher"] == ""
    publishers = publisher_source.groupby(["publisher", "publisher_missing"]).size().reset_index(name="borrow_count")
    publishers = publishers.sort_values(["borrow_count", "publisher"], ascending=[False, True]).head(20).reset_index(drop=True)
    distribution = readers.groupby("borrow_count", sort=True).size().reset_index(name="reader_count")
    preferences = clean.groupby(["reader_id", "category_code", "category_name"], sort=True).size().reset_index(name="borrow_count")
    totals = preferences.groupby("reader_id")["borrow_count"].transform("sum")
    preferences["share"] = preferences["borrow_count"] / totals
    preferences = preferences.sort_values(["reader_id", "borrow_count", "category_code"], ascending=[True, False, True]).reset_index(drop=True)
    return summary, {
        "hot_books": hot, "categories": categories, "publishers": publishers,
        "reader_distribution": distribution, "reader_preferences": preferences,
    }


def api_data(summary: dict, tables: dict[str, pd.DataFrame]) -> dict:
    """映射现有接口契约和前端 AdminSummary/BookStat/CategoryStat，保留原生统计表。"""
    return {
        "summary": {
            "total_borrows": summary["borrow_count"],
            "total_readers": summary["reader_count"],
            "total_titles": summary["unique_title_count"],
            "avg_borrow_per_reader": summary["borrows_per_reader"],
        },
        "hot_books": records(tables["hot_books"].rename(columns={"borrow_count": "count"})),
        "categories": records(tables["categories"].rename(columns={"category_code": "category", "borrow_count": "count"})),
        "publishers": records(tables["publishers"].rename(columns={"borrow_count": "count"})),
    }


def analyze_file(path: Path, output: Path):
    clean = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    summary, tables = analyze_frame(clean)
    output.mkdir(parents=True, exist_ok=True)
    quality_path = path.parent / "quality_report.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.exists() else {}
    label = quality.get("dataset_label", "unknown")
    summary["dataset_label"] = label
    write_json(output / "summary.json", summary)
    save_table(output, "summary", pd.DataFrame([summary]), with_json=False)
    for name, frame in tables.items():
        save_table(output, name, frame)
    mapped = api_data(summary, tables)
    for name, payload in mapped.items():
        write_json(output / f"api_{name}.json", {
            "code": 0, "message": "success", "data": payload, "dataset_label": label,
        })
    dashboard = {
        "code": 0, "message": "success", "dataset_label": label,
        "data": {**mapped, "reader_distribution": records(tables["reader_distribution"])},
        "limitations": ["数据仅代表历史借阅样本，不代表馆藏全量或实时可借状态。",
                        "没有借阅日期，未生成趋势；没有架位信息，未生成架位。",
                        "未识别分类保留在分类分母；读者分布和平均值只计算接受的流水。"],
    }
    write_json(output / "dashboard.json", dashboard)
    return summary
