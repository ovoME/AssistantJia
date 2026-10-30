"""
多源数据管理服务 (Data Management Hub)
支持 8 类图书馆核心数据的上传、自动清洗、结构化解析与智能问答检索：
1. 备考联盟数据 (exam)
2. 读者数据 (reader)
3. 借阅数据 (borrow)
4. 门禁入馆数据 (gate_flow)
5. 门禁刷卡数据 (gate_swipe)
6. 学者库数据 (scholars)
7. 研讨室数据 (seminar)
8. 座位系统数据 (seats)
"""

import os
import csv
import json
import logging
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from zipfile import BadZipFile, ZipFile
import openpyxl
from app.config import PROJECT_ROOT, settings

IMPORTED_DIR = PROJECT_ROOT / "data" / "imported"
MANIFEST_FILE = IMPORTED_DIR / "data_manifest.json"
logger = logging.getLogger(__name__)
MAX_IMPORT_ROWS = 500_000
MAX_XLSX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_XLSX_ARCHIVE_MEMBERS = 10_000


def _validate_xlsx_archive(path: Path) -> None:
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_XLSX_ARCHIVE_MEMBERS:
                raise ValueError("XLSX 工作簿包含过多内部文件。")
            uncompressed_bytes = sum(member.file_size for member in members if not member.is_dir())
            if uncompressed_bytes > MAX_XLSX_UNCOMPRESSED_BYTES:
                raise ValueError("XLSX 解压后数据超过允许上限。")
    except BadZipFile as exc:
        raise ValueError("XLSX 文件不是有效的工作簿。") from exc


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.",
            suffix=".tmp", delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(value, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise

# 8 类数据元信息定义
DATA_CATEGORIES = {
    "exam": {
        "id": "exam",
        "name": "备考联盟数据",
        "folder_name": "备考联盟数据",
        "filename": "备考联盟.xlsx",
        "desc": "考研、考公、考证等备考群体的专业与年级预约画像",
        "icon": "🎓",
    },
    "reader": {
        "id": "reader",
        "name": "读者数据",
        "folder_name": "读者数据",
        "filename": "读者数据.csv",
        "desc": "持证读者院系、年级、学历与身份分类画像",
        "icon": "👤",
    },
    "borrow": {
        "id": "borrow",
        "name": "借阅数据",
        "folder_name": "借阅数据",
        "filename": "图书数据.csv",
        "desc": "馆藏中外文书目、索书号及出版信息明细库",
        "icon": "📚",
    },
    "gate_flow": {
        "id": "gate_flow",
        "name": "门禁入馆数据",
        "folder_name": "门禁入馆数据",
        "filename": "门禁入馆人次.xlsx",
        "desc": "各院系读者的入馆频次统计与活跃度排行",
        "icon": "🚪",
    },
    "gate_swipe": {
        "id": "gate_swipe",
        "name": "门禁刷卡数据",
        "folder_name": "门禁刷卡数据",
        "filename": "门禁刷卡.xlsx",
        "desc": "通道刷卡时段流水，用于分析开馆到闭馆各时段在馆客流与峰值",
        "icon": "⏱️",
    },
    "scholars": {
        "id": "scholars",
        "name": "学者库数据",
        "folder_name": "学者库数据",
        "filename": "学者库数据.xlsx",
        "desc": "校内学者、导师发表学术论文、期刊与学术课题数据库",
        "icon": "🔬",
    },
    "seminar": {
        "id": "seminar",
        "name": "研讨室数据",
        "folder_name": "研讨室数据",
        "filename": "研讨室预约.xlsx",
        "desc": "研修室/研讨室预约流水、借用时段与团队研学记录",
        "icon": "👥",
    },
    "seats": {
        "id": "seats",
        "name": "座位系统数据",
        "folder_name": "座位系统数据",
        "filename": "座位预约.csv",
        "desc": "各楼层阅览区自习座位预约、签到与使用时段记录",
        "icon": "🪑",
    },
}

class DataManager:
    def __init__(self):
        IMPORTED_DIR.mkdir(parents=True, exist_ok=True)
        self.manifest_file = MANIFEST_FILE
        self._load_manifest()

    def _load_manifest(self):
        if self.manifest_file.exists():
            try:
                loaded = json.loads(self.manifest_file.read_text(encoding="utf-8"))
                self.manifest = loaded if isinstance(loaded, dict) else {}
            except Exception:
                self.manifest = {}
        else:
            self.manifest = {}

    def _save_manifest(self):
        _atomic_write_json(self.manifest_file, self.manifest)

    def get_sources_status(self) -> List[Dict[str, Any]]:
        """获取 8 大数据源的最新导入状态与摘要"""
        self._load_manifest()
        result = []
        for cat_id, meta in DATA_CATEGORIES.items():
            record = self.manifest.get(cat_id, {
                "is_imported": False,
                "row_count": 0,
                "summary": "尚未导入数据",
                "imported_at": None,
                "source_file": None
            })
            result.append({
                **meta,
                **record
            })
        return result

    def sync_from_official_source(self, cat_id: str) -> Dict[str, Any]:
        """一键从桌面主办方数据目录同步并解析指定分类"""
        if cat_id not in DATA_CATEGORIES:
            raise ValueError(f"未知的数据分类: {cat_id}")
        meta = DATA_CATEGORIES[cat_id]
        source_root = Path(settings.DATA_SOURCE_DIRECTORY).resolve()
        src_path = (source_root / meta["folder_name"] / meta["filename"]).resolve()
        if not src_path.is_relative_to(source_root):
            raise ValueError("配置的数据源路径无效。")
        if not src_path.is_file():
            raise FileNotFoundError(f"官方数据源未找到: {src_path}")

        dest_dir = IMPORTED_DIR / cat_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / meta["filename"]
        if dest_file.exists():
            dest_file = dest_dir / f"{dest_file.stem}_{uuid.uuid4().hex[:8]}{dest_file.suffix}"
        shutil.copy2(src_path, dest_file)
        try:
            return self.process_file(cat_id, dest_file)
        except Exception:
            dest_file.unlink(missing_ok=True)
            raise

    def sync_all(self) -> Dict[str, Any]:
        """一键同步所有 8 项官方数据源"""
        results = {}
        for cat_id in DATA_CATEGORIES.keys():
            try:
                res = self.sync_from_official_source(cat_id)
                results[cat_id] = {"success": True, "count": res.get("row_count", 0)}
            except FileNotFoundError:
                results[cat_id] = {"success": False, "error": "source_not_found"}
            except Exception:
                logger.exception("Data source sync failed (category=%s)", cat_id)
                results[cat_id] = {"success": False, "error": "sync_failed"}
        return results

    def process_file(self, cat_id: str, file_path: Path) -> Dict[str, Any]:
        """解析上传的文件并提取摘要"""
        if cat_id not in DATA_CATEGORIES:
            raise ValueError(f"未知的数据分类: {cat_id}")
        self._load_manifest()
        fp = Path(file_path)
        row_count = 0
        summary_info = ""
        cached_data: Any = None

        if fp.suffix.lower() == ".xlsx":
            _validate_xlsx_archive(fp)
            wb = openpyxl.load_workbook(fp, read_only=True, data_only=True)
            ws = wb.active
            rows = []
            for i, r in enumerate(ws.iter_rows(values_only=True)):
                if i > MAX_IMPORT_ROWS:
                    wb.close()
                    raise ValueError("XLSX 行数超过允许上限。")
                if i == 0:
                    headers = [str(c or "") for c in r]
                else:
                    if any(r):
                        row_count += 1
                        if len(rows) < 500:  # 缓存前500条结构化用于检索
                            rows.append(dict(zip(headers, [str(c or "") for c in r])))
            wb.close()

            if cat_id == "exam":
                types = {}
                for item in rows:
                    t = item.get("备考类型", "其他")
                    types[t] = types.get(t, 0) + 1
                top_types = sorted(types.items(), key=lambda x: -x[1])[:3]
                summary_info = f"共 {row_count} 位备考学子登记，热门方向：{', '.join(f'{k}({v}人)' for k, v in top_types)}"
                cached_data = {"top_types": top_types, "sample": rows[:100]}

            elif cat_id == "scholars":
                authors = set()
                for item in rows:
                    if item.get("作者"):
                        authors.add(item["作者"].split(";")[0])
                summary_info = f"共收录 {row_count} 篇学术成果，覆盖约 {len(authors)} 位学者/导师"
                cached_data = {"papers": rows[:200]}

            elif cat_id == "gate_flow":
                summary_info = f"收录 {row_count} 名读者的入馆频次总览"
                cached_data = {"flow": rows[:100]}

            elif cat_id == "gate_swipe":
                summary_info = f"收录 {row_count} 条门禁刷卡流水记录"
                cached_data = {"swipes": rows[:100]}

            elif cat_id == "seminar":
                summary_info = f"收录 {row_count} 条研讨室与研修空间使用记录"
                cached_data = {"seminars": rows[:100]}

            else:
                summary_info = f"成功解析 {row_count} 条记录"

        elif fp.suffix.lower() == ".csv":
            # 尝试常见编码 (GBK / UTF-8)
            encoding = "utf-8"
            try:
                with fp.open("r", encoding="utf-8") as test_f:
                    test_f.read(1024)
            except Exception:
                encoding = "gbk"

            rows = []
            with fp.open("r", encoding=encoding, errors="ignore") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                for row in reader:
                    if row_count >= MAX_IMPORT_ROWS:
                        raise ValueError("CSV 行数超过允许上限。")
                    row_count += 1
                    if len(rows) < 500:
                        rows.append(row)

            if cat_id == "seats":
                summary_info = f"收录 {row_count} 次阅览区自习座位预约记录"
                cached_data = {"seats": rows[:100]}
            elif cat_id == "reader":
                summary_info = f"收录 {row_count} 位读者学号、院系与读者身份信息"
                cached_data = {"readers": rows[:100]}
            elif cat_id == "borrow":
                summary_info = f"收录 {row_count} 种馆藏图书条目"
                cached_data = {"books": rows[:100]}
            else:
                summary_info = f"成功解析 {row_count} 条记录"

        old_record = self.manifest.get(cat_id, {})
        cached_file = None
        if cached_data is not None:
            cached_file = f"{cat_id}_parsed_{uuid.uuid4().hex}.json"
            _atomic_write_json(IMPORTED_DIR / cached_file, cached_data)

        dest_meta = {
            "is_imported": True,
            "row_count": row_count,
            "summary": summary_info,
            "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_file": fp.name,
            "cached_file": cached_file,
        }
        updated_manifest = {**self.manifest, cat_id: dest_meta}
        try:
            _atomic_write_json(self.manifest_file, updated_manifest)
        except Exception:
            if cached_file:
                (IMPORTED_DIR / cached_file).unlink(missing_ok=True)
            raise

        self.manifest = updated_manifest
        old_cache = old_record.get("cached_file")
        if old_cache and old_cache != cached_file and Path(old_cache).name == old_cache:
            try:
                (IMPORTED_DIR / old_cache).unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove superseded cache file for %s", cat_id)
        return dest_meta

    def _cached_data(self, category: str):
        self._load_manifest()
        record = self.manifest.get(category)
        if not record or not record.get("is_imported"):
            return record, None
        cached_file = record.get("cached_file")
        if not cached_file or Path(cached_file).name != cached_file:
            return record, None
        root = IMPORTED_DIR.resolve()
        cache_path = (root / cached_file).resolve()
        if not cache_path.is_relative_to(root) or not cache_path.is_file():
            return record, None
        try:
            return record, json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.exception("Could not read parsed data cache (category=%s)", category)
            return record, None

    def _domain_status(self, category: str, domain: str, limitation: str):
        record = self.manifest.get(category) or {}
        if not record.get("is_imported"):
            return {
                "domain": domain,
                "available": False,
                "row_count": 0,
                "source_file": None,
                "imported_at": None,
                "reply": f"目前没有已导入、可核验的{domain}数据，因此我不能提供相关统计。请管理员先导入数据；{limitation}",
            }
        source_file = record.get("source_file") or "未记录文件名"
        imported_at = record.get("imported_at") or "未记录导入时间"
        row_count = int(record.get("row_count") or 0)
        return {
            "domain": domain,
            "available": True,
            "row_count": row_count,
            "source_file": source_file,
            "imported_at": imported_at,
            "reply": (
                f"当前导入的{domain}来源文件为“{source_file}”，共 {row_count} 条记录，"
                f"导入时间：{imported_at}。这是静态历史样本，{limitation}"
            ),
        }

    def query_multimodal_knowledge(self, query: str) -> Optional[Dict[str, Any]]:
        """为小嘉提供针对 8 大多源数据的自然语言检索解答"""
        q = query.lower()
        self._load_manifest()

        # 1. 备考联盟问答
        if any(w in q for w in ["考研", "考公", "备考", "考证", "四六级", "专升本"]):
            record, data = self._cached_data("exam")
            if not record or not record.get("is_imported") or data is None:
                return self._domain_status(
                    "exam", "备考联盟", "具体安排请以馆方公告为准。"
                )
            top_types = data.get("top_types", [])
            top_str = "、".join(f"{name}（{count}条）" for name, count in top_types)
            sampled = min(500, int(record.get("row_count") or 0))
            detail = f"最多前 {sampled} 条缓存样本中的方向为：{top_str}。" if top_str else "缓存样本中没有可显示的方向分类。"
            return {
                "domain": "备考联盟数据",
                "available": True,
                "row_count": int(record.get("row_count") or 0),
                "source_file": record.get("source_file"),
                "imported_at": record.get("imported_at"),
                "reply": (
                    f"已导入备考联盟数据 {int(record.get('row_count') or 0)} 条。{detail}"
                    f"来源文件：{record.get('source_file') or '未记录'}；导入时间：{record.get('imported_at') or '未记录'}。"
                    "以上是静态导入样本，不代表实时登记人数。"
                ),
            }

        # 2. 学者库问答 (学术、导师、论文)
        if any(w in q for w in ["学者", "导师", "论文", "教授", "学术", "发表", "课题", "研究方向"]):
            record, data = self._cached_data("scholars")
            if not record or not record.get("is_imported") or data is None:
                return self._domain_status("scholars", "学者库", "请管理员先导入学者数据。")
            papers = data.get("papers", [])
            search_text = q
            for phrase in ["有哪些", "请问", "帮我查", "帮我", "查一下", "查询", "查", "学者", "导师", "论文", "教授", "学术", "发表", "课题", "研究方向", "研究", "成果"]:
                search_text = search_text.replace(phrase, " ")
            terms = [term for term in re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]{2,}", search_text)]
            matched = [
                paper for paper in papers
                if not terms or any(
                    term in f"{paper.get('论文题名', '')} {paper.get('作者', '')}".lower()
                    for term in terms
                )
            ]
            if not matched:
                reply = "在已导入的缓存样本中没有找到与该关键词匹配的学者成果；缓存最多包含前 200 条记录。"
            else:
                sample_papers = matched[:2]
                paper_lines = "\n".join(
                    f"• 《{paper.get('论文题名', '')}》（作者：{paper.get('作者', '未记录')}；期刊：{paper.get('期刊名称', '未记录')}）"
                    for paper in sample_papers
                )
                reply = f"导入的缓存样本中匹配到 {len(matched)} 条记录，以下最多展示 2 条：\n{paper_lines}"
            return {
                "domain": "学者库数据",
                "available": True,
                "row_count": int(record.get("row_count") or 0),
                "source_file": record.get("source_file"),
                "imported_at": record.get("imported_at"),
                "reply": (
                    f"{reply}\n来源文件：{record.get('source_file') or '未记录'}；"
                    f"导入时间：{record.get('imported_at') or '未记录'}。该结果只覆盖缓存样本，不代表完整数据库。"
                ),
            }

        # 3. 门禁与客流问答 (人多不多、几点人少、高峰期)
        if any(w in q for w in ["人多", "人少", "高峰", "客流", "几点去", "挤不挤", "空闲", "安静"]):
            category = "gate_swipe" if self.manifest.get("gate_swipe", {}).get("is_imported") else "gate_flow"
            return self._domain_status(
                category,
                "门禁与客流",
                "这些静态记录不能确认当前在馆人数、空位或峰值时段；实时情况请以馆方系统为准。",
            )

        # 4. 座位系统问答
        if any(w in q for w in ["选座", "插座", "靠窗", "找座位", "自习区"]):
            return self._domain_status(
                "seats",
                "座位预约",
                "这些静态记录不能说明当前空位、设施或预约规则；请以馆方座位系统为准。",
            )

        # 5. 研讨室问答
        if any(w in q for w in ["小组讨论", "开会", "多功能", "小组研学"]):
            return self._domain_status(
                "seminar",
                "研讨室预约",
                "这些静态记录不能确认场地规格、可预约时段或预约规则；请以馆方预约系统为准。",
            )

        return None

data_manager = DataManager()
