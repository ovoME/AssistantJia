"""
RAG 检索接口，默认复用 C4 本地稀疏向量索引，不下载嵌入模型。
"""

from typing import List, Dict, Any, Optional
from app.services.local_data import knowledge

class RAGRetriever:
    """规章制度与图书馆知识库检索器"""

    def __init__(self, persist_directory: Optional[str] = None):
        self.persist_directory = persist_directory

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        返回相关切块、官网地址、修订与采集时间，未命中时返回空列表。
        """
        return knowledge().retrieve(query, top_k)

retriever = RAGRetriever()
