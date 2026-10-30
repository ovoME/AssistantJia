"""本地书目内容索引：无需分词服务，且不使用读者或借阅次数作为文本特征。"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict


def features(book):
    """题名字双元组、完整责任者、索书号分类段；不使用种次号或出版社。"""
    title = unicodedata.normalize("NFKC", book["title"]).casefold()
    tokens = {}
    for part in re.findall(r"[\w]+", title):
        for index in range(len(part) - 1):
            tokens["title:" + part[index:index + 2]] = 1.0
    author = "".join(unicodedata.normalize("NFKC", book["author"]).casefold().split())
    if author and author not in {"未知", "佚名", "不详", "无", "unknown"}:
        tokens["author:" + author] = 2.0
    call = unicodedata.normalize("NFKC", book["call_number"]).upper().strip()
    match = re.match(r"([A-Z]{1,2})(\d+(?:\.\d+)*)", call)
    if match:
        letters, digits = match.groups()
        tokens["class:" + letters + digits[:1]] = 0.5
        tokens["class:" + letters + digits[:3]] = 1.0
        tokens["class:" + letters + digits] = 1.5
    return tokens


class ContentIndex:
    """稀疏 TF-IDF 余弦索引，静态书目也可含没有训练借阅的新书。"""

    def __init__(self, books):
        raw = {key: features(book) for key, book in books.items()}
        frequencies = Counter(token for tokens in raw.values() for token in tokens)
        size = len(raw)
        self.vectors = {}
        self.postings = defaultdict(list)
        for key, tokens in raw.items():
            # 单例无法产生相似关系；过于普遍的词/责任者/分类不提供区分度。
            vector = {token: weight * math.log((size + 1) / (frequencies[token] + 1))
                      for token, weight in sorted(tokens.items())
                      if 2 <= frequencies[token] < size and frequencies[token] <= max(2, size * 0.15)}
            norm = math.sqrt(sum(weight * weight for weight in vector.values()))
            vector = {token: weight / norm for token, weight in vector.items()} if norm else {}
            self.vectors[key] = vector
            for token, weight in vector.items():
                self.postings[token].append((key, weight))

    def scores(self, history):
        profile = Counter()
        for key in sorted(history):
            profile.update(self.vectors[key])
        norm = math.sqrt(sum(weight * weight for weight in profile.values()))
        result = Counter()
        if norm:
            for token, weight in sorted(profile.items()):
                for key, candidate_weight in self.postings[token]:
                    if key not in history:
                        result[key] += weight / norm * candidate_weight
        return result
