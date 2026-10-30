import json
from typing import Optional
from langchain_core.tools import tool
from app.agent.tools.data_client import data_client

@tool
def recommend_books(reader_id: Optional[str] = None, limit: int = 5, query: Optional[str] = None) -> str:
    """
    根据问题主题和可用的读者历史偏好，探索推荐不同图书。
    当用户要求“推荐几本书”、“最近有什么好书推荐”、“按我的兴趣推书”时调用。
    :param reader_id: 可选的读者证件号
    :param limit: 推荐册数，默认 5
    :param query: 读者要求的主题、书名或作者；未提出时可省略
    :return: 包含推荐图书、索书号及推荐理由的 JSON 字符串
    """
    try:
        recs = data_client.get_recommendations(reader_id=reader_id, limit=limit, query=query)
        return json.dumps({
            "status": "success",
            "recommendations": recs
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"推荐算法计算失败: {str(e)}"
        }, ensure_ascii=False)
