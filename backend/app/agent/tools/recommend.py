import json
from typing import Optional
from langchain_core.tools import tool
from app.agent.tools.data_client import data_client

@tool
def recommend_books(reader_id: Optional[str] = None, limit: int = 5, query: Optional[str] = None,
                    popular: Optional[bool] = None) -> str:
    """
    根据问题主题和可用的读者历史偏好，探索推荐不同图书。
    当用户要求“推荐几本书”、“最近有什么好书推荐”、“按我的兴趣推书”时调用。
    :param reader_id: 可选的读者证件号
    :param limit: 推荐册数，默认 5
    :param query: 仅填用户明确提出的主题、书名或作者，例如 Python；没有具体主题时省略
    :param popular: 用户明确希望热门或受欢迎的书时为 true，未提出或否定热门时省略或为 false
    :return: 包含推荐图书、索书号及推荐理由的 JSON 字符串
    """
    try:
        recs = data_client.get_recommendations(reader_id=reader_id, limit=limit, query=query, popular=popular)
        return json.dumps({
            "status": "success",
            "recommendations": recs
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"推荐算法计算失败: {str(e)}"
        }, ensure_ascii=False)
