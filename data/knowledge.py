"""C4 可追溯规则检索：主题切块、稀疏 TF-IDF 向量及可重建的本地索引。"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_SOURCE = Path(__file__).parent / "knowledge" / "rules.json"
STOP = {"图书", "书馆", "图书馆", "一下", "什么", "可以", "多少", "怎么", "如何", "请问", "能否", "是否"}
SCOPES = {"研讨室": ("研讨室",), "研修室": ("研修室",), "座位": ("座位", "选座"),
          "积分": ("积分",), "现刊": ("现刊",), "日文": ("日文",),
          "续借": ("借阅权限",), "借期": ("借阅权限",)}


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def tokens(text):
    result = []
    for part in re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", normalize(text)):
        if re.fullmatch(r"[a-z0-9]+", part):
            result.append(part)
        else:
            result.extend(part[i:i + 2] for i in range(len(part) - 1))
    return Counter(token for token in result if token not in STOP)


class KnowledgeBase:
    def __init__(self, source=DEFAULT_SOURCE):
        raw = Path(source).read_bytes()
        payload = json.loads(raw)
        if payload.get("schema_version") != 1 or not isinstance(payload.get("documents"), list):
            raise ValueError("规则来源清单格式无效。")
        retrieved = datetime.fromisoformat(payload["retrieved_at"])
        if retrieved.tzinfo is None:
            raise ValueError("采集时间必须包含时区。")
        self.source_sha256 = hashlib.sha256(raw).hexdigest()
        self.retrieved_at = payload["retrieved_at"]
        self.chunks = []
        ids = set()
        for document in payload["documents"]:
            url = urlparse(document["url"])
            if url.scheme != "https" or url.hostname != "library.xujc.com":
                raise ValueError("当前规则来源必须是馆方公开 HTTPS 页面。")
            for section in document["sections"]:
                key = document["id"] + "/" + section["id"]
                if key in ids or not section["text"].strip() or len(section["text"]) > 1200:
                    raise ValueError("规则切块须唯一、非空且不超过 1200 字符。")
                ids.add(key)
                self.chunks.append({"chunk_id": key, "title": document["title"],
                                    "section": section["title"], "text": section["text"],
                                    "keywords": section["keywords"], "url": document["url"],
                                    "published_at": document.get("published_at"),
                                    "revised_at": document.get("revised_at"),
                                    "retrieved_at": self.retrieved_at})
        raw_vectors = [tokens(chunk["section"] + " " + chunk["text"] + " " + " ".join(chunk["keywords"]))
                       for chunk in self.chunks]
        df = Counter(term for vector in raw_vectors for term in vector)
        self.idf = {term: 1 + math.log((len(raw_vectors) + 1) / (count + 1)) for term, count in df.items()}
        self.vectors = [self._vector(vector) for vector in raw_vectors]

    def _vector(self, counts):
        vector = {term: (1 + math.log(count)) * self.idf[term] for term, count in counts.items() if term in self.idf}
        norm = math.sqrt(sum(value ** 2 for value in vector.values()))
        return {term: value / norm for term, value in vector.items()} if norm else {}

    def retrieve(self, query, top_k=3):
        if not isinstance(query, str) or len(query) > 500:
            raise ValueError("规则问题必须为不超过 500 字符的文本。")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 10:
            raise ValueError("top_k 必须为 1 到 10 的整数。")
        q = normalize(query)
        vector = self._vector(tokens(q))
        scored = []
        for chunk, candidate in zip(self.chunks, self.vectors):
            anchors = chunk["title"] + " " + " ".join(chunk["keywords"])
            if any(topic in q and not any(alias in anchors for alias in aliases)
                   for topic, aliases in SCOPES.items()):
                continue
            cosine = sum(weight * candidate.get(term, 0) for term, weight in vector.items())
            matched = [keyword for keyword in chunk["keywords"] if normalize(keyword) in q]
            # 主题锚点必需，普通中文词重叠不当作找到了制度答案。
            if matched and cosine >= 0.04:
                score = min(1.0, cosine + 0.12 * min(3, len(matched)))
                scored.append({**chunk, "score": round(score, 6)})
        scored.sort(key=lambda row: (-row["score"], row["chunk_id"]))
        return scored[:top_k]

    def answer(self, question):
        matches = self.retrieve(question)
        if not matches:
            return {"found": False, "answer": "现有已核对规则中未找到足够依据，请查看馆方公告或咨询总服务台。",
                    "source": "未命中已核对规则", "sources": [], "is_live": False,
                    "retrieved_at": self.retrieved_at}
        answer = "\n\n".join(f"[{i}] {row['section']}：{row['text']}" for i, row in enumerate(matches, 1))
        return {"found": True, "answer": answer,
                "source": "、".join(dict.fromkeys(row["title"] for row in matches)),
                "sources": [{key: value for key, value in row.items() if key != "keywords"} for row in matches],
                "is_live": False, "retrieved_at": self.retrieved_at,
                "notice": "馆方网页的已核对摘要；临时调整、个体业务资格以最新公告和馆方系统为准。"}

    def export(self, output):
        """保存可审计稀疏向量；运行时按来源重新构建，避免过期索引被静默使用。"""
        payload = {"schema_version": 1, "algorithm": "character_bigram_tfidf_cosine_v1",
                   "source_sha256": self.source_sha256, "retrieved_at": self.retrieved_at,
                   "chunks": self.chunks, "idf": self.idf, "vectors": self.vectors}
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
        return {"chunks": len(self.chunks), "source_sha256": self.source_sha256}
