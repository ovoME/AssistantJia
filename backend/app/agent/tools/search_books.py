import json
from typing import List, Dict, Any
from langchain_core.tools import tool
from app.agent.tools.data_client import data_client

@tool
def search_books(query: str, limit: int = 5) -> str:
    """
    查询嘉庚学院图书馆馆藏图书、精确索书号、立体架位位置及在馆可借状态。
    当用户需要查找某本书、询问某本书在几楼哪个书架、查索书号、或者看某本书能不能借时调用此工具。
    :param query: 书名、责任者/作者或索书号关键词
    :param limit: 返回的最大图书数量，默认为 5
    :return: 包含图书列表、索书号和立体架位描述的 JSON 字符串
    """
    try:
        results = data_client.search_books_opac(query=query, limit=limit)
        if not results:
            return json.dumps({
                "status": "not_found",
                "message": f"抱歉，在馆藏系统中未检索到与“{query}”相关的图书，建议更换关键词或至服务台咨询。"
            }, ensure_ascii=False)
        return json.dumps({
            "status": "success",
            "count": len(results),
            "books": results
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"馆藏检索服务暂时异常: {str(e)}"
        }, ensure_ascii=False)
