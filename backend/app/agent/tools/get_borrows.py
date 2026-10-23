import json
from langchain_core.tools import tool
from app.agent.tools.data_client import data_client

@tool
def get_user_borrows(reader_id: str) -> str:
    """
    查询读者当前在借图书列表、应还日期及是否即将逾期。
    当读者询问“我借了哪些书”、“我的书什么时候到期”、“查一下我的借阅”时调用。
    :param reader_id: 读者证件号
    :return: 包含在借图书、借阅时间与应还日期的 JSON 字符串
    """
    try:
        records = data_client.get_user_borrows(reader_id=reader_id)
        return json.dumps({
            "status": "success",
            "reader_id": reader_id,
            "borrows": records
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"借阅记录查询失败: {str(e)}"
        }, ensure_ascii=False)
