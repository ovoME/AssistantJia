import json
from langchain_core.tools import tool
from app.agent.tools.data_client import data_client

@tool
def reserve_book(reader_id: str, isbn: str) -> str:
    """
    在线预约图书。
    当图书已借出或读者明确要求预约某本图书时调用此工具。
    :param reader_id: 读者的证件号/学号
    :param isbn: 图书的标准 ISBN 编号
    :return: 包含预约结果及排队位置的 JSON 字符串
    """
    try:
        res = data_client.reserve_book(reader_id=reader_id, isbn=isbn)
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"预约服务异常: {str(e)}"
        }, ensure_ascii=False)
