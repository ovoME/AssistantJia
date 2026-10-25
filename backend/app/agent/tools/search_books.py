import json
from typing import List, Dict, Any
from langchain_core.tools import tool
from app.agent.tools.data_client import data_client
from app.services.local_data import search_books_response

@tool
def search_books(query: str, limit: int = 5) -> str:
    """
    查询已配置书目目录。只有显式模拟模式提供虚构架位和库存，必须保留来源和 is_live。
    当用户需要查找某本书、询问某本书在几楼哪个书架、查索书号、或者看某本书能不能借时调用此工具。
    :param query: 书名、责任者/作者或索书号关键词
    :param limit: 返回的最大图书数量，默认为 5
    :return: 包含图书列表、索书号和立体架位描述的 JSON 字符串
    """
    try:
        payload = search_books_response(query, limit)
        results = payload["data"]
        if not results:
            return json.dumps({
                "status": "not_found",
                "message": f"抱歉，在馆藏系统中未检索到与“{query}”相关的图书，建议更换关键词或至服务台咨询。"
            }, ensure_ascii=False)
        return json.dumps({
            "status": "success",
            "count": len(results),
            "books": results,
            "dataset_label": payload["dataset_label"], "is_live": payload["is_live"], "limitations": payload["limitations"]
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"馆藏检索服务暂时异常: {str(e)}"
        }, ensure_ascii=False)
