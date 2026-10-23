import json
from langchain_core.tools import tool
from app.agent.tools.data_client import data_client

@tool
def renew_book(reader_id: str, book_id: str) -> str:
    """
    为读者办理图书自助一键续借。
    当读者表示需要续借某一本书、或者请求延长借阅期限时调用此工具。
    必须向读者明确告知续借结果或失败的具体原因（如超期、达续借上限等）。
    :param reader_id: 读者的证件号/学号（如 2023001）
    :param book_id: 所借图书的财产号/条码号（如 B20230911001）
    :return: 包含续借结果及新归还日期的 JSON 字符串
    """
    try:
        res = data_client.renew_book(reader_id=reader_id, book_id=book_id)
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"续借接口调用失败: {str(e)}"
        }, ensure_ascii=False)
