import json
from typing import Optional
from langchain_core.tools import tool
from app.auth import active_reader
from app.agent.tools.data_client import data_client

@tool
def get_user_borrows(reader_id: Optional[str] = None) -> str:
    """
    查询读者当前在借图书列表、应还日期及是否即将逾期。
    当读者询问“我借了哪些书”、“我的书什么时候到期”、“查一下我的借阅”时调用。
    :param reader_id: 可省略，默认使用已认证的本人身份；不能指定其他读者
    :return: 包含在借图书、借阅时间与应还日期的 JSON 字符串
    """
    try:
        reader_id = reader_id or active_reader.get()
        if not reader_id:
            return json.dumps({"status": "error", "message": "请先登录后查询本人的借阅记录。"}, ensure_ascii=False)
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
