import json
from langchain_core.tools import tool
from app.agent.tools.data_client import data_client

@tool
def search_knowledge(question: str) -> str:
    """
    检索嘉庚学院图书馆规章制度知识库。
    当读者咨询图书馆的规则、借期几天、可以借几本、开馆与闭馆时间、研修室/座位预约制度、违规赔偿等问题时调用。
    :param question: 读者咨询的规章问题
    :return: 制度条目、权威解答与来源出处
    """
    try:
        res = data_client.search_rules_knowledge(question=question)
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "found": False,
            "answer": "规章库检索暂时出现问题，建议直接前往主楼服务台人工咨询。",
            "source": "异常兜底"
        }, ensure_ascii=False)
