"""
数据访问层 (Data Access Layer)
统一封装所有向底层 OPAC、知识库与算法服务的访问。
当前版本内置高质量真实感 Mock 数据，等角色 C 的真实数据与向量库就绪后，仅需更新此文件。
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# 初始精选图书库 (贴合嘉庚学院图书馆场景)
MOCK_BOOKS = [
    {
        "title": "三体",
        "author": "刘慈欣",
        "isbn": "9787536692930",
        "call_number": "I247.55/123",
        "location": "主楼三层中文借阅区 302架A面03层",
        "available": 2,
        "status": "在馆"
    },
    {
        "title": "深入理解计算机系统 (原书第3版)",
        "author": "Randal E. Bryant",
        "isbn": "9787111544937",
        "call_number": "TP3/288",
        "location": "主楼四层理工科借阅区 410架B面02层",
        "available": 1,
        "status": "在馆"
    },
    {
        "title": "嘉庚精神与华侨华人",
        "author": "陈嘉庚研究会",
        "isbn": "9787561588210",
        "call_number": "K825.38/10",
        "location": "主楼五层嘉庚特藏专区 501架A面",
        "available": 3,
        "status": "在馆"
    },
    {
        "title": "Python深度学习",
        "author": "François Chollet",
        "isbn": "9787115488763",
        "call_number": "TP18/66",
        "location": "主楼四层计算机科学区 408架A面01层",
        "available": 0,
        "status": "已借出"
    },
    {
        "title": "微观经济学：现代观点",
        "author": "范里安 (Hal R. Varian)",
        "isbn": "9787543224971",
        "call_number": "F016/52",
        "location": "主楼三层经管借阅区 315架C面04层",
        "available": 4,
        "status": "在馆"
    }
]

# 模拟借阅记录
MOCK_BORROWS: Dict[str, List[Dict[str, Any]]] = {
    "2023001": [
        {
            "book_id": "B20230911001",
            "title": "Python编程：从入门到实践",
            "borrow_date": (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d"),
            "due_date": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"),
            "renew_count": 0,
            "is_overdue": False
        },
        {
            "book_id": "B20230911002",
            "title": "人工智能导论",
            "borrow_date": (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d"),
            "due_date": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
            "renew_count": 1,
            "is_overdue": False
        }
    ]
}

class DataClient:
    """数据客户端接口封装"""

    @staticmethod
    def search_books_opac(query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """查馆藏与架位"""
        q = query.strip().lower()
        if not q:
            return MOCK_BOOKS[:limit]
        matched = [
            b for b in MOCK_BOOKS
            if q in b["title"].lower() or q in b["author"].lower() or q in b["call_number"].lower()
        ]
        return (matched or MOCK_BOOKS)[:limit]

    @staticmethod
    def get_user_borrows(reader_id: str) -> List[Dict[str, Any]]:
        """获取读者当前在借记录"""
        return MOCK_BORROWS.get(reader_id, [
            {
                "book_id": "B20239999001",
                "title": "读者测试借阅示例图书",
                "borrow_date": datetime.now().strftime("%Y-%m-%d"),
                "due_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                "renew_count": 0,
                "is_overdue": False
            }
        ])

    @staticmethod
    def renew_book(reader_id: str, book_id: str) -> Dict[str, Any]:
        """办理续借业务（带完整异常与规则判定）"""
        borrows = MOCK_BORROWS.get(reader_id, [])
        record = next((b for b in borrows if b["book_id"] == book_id), None)
        if not record:
            return {
                "success": False,
                "message": f"未找到该图书财产号（{book_id}）的借阅记录，请核对后再试。"
            }
        if record["is_overdue"]:
            return {
                "success": False,
                "message": "该图书已超过归还期限，无法自助续借，请尽快前往服务台办理还书。"
            }
        if record["renew_count"] >= 1:
            return {
                "success": False,
                "message": "该图书已达到最大续借上限（限续借1次），请于到期日前归还。"
            }
        
        # 续借成功，延长30天
        new_due = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        record["due_date"] = new_due
        record["renew_count"] += 1
        return {
            "success": True,
            "new_due_date": new_due,
            "renew_count": record["renew_count"],
            "message": f"续借成功！新的应还日期为 {new_due}。"
        }

    @staticmethod
    def reserve_book(reader_id: str, isbn: str) -> Dict[str, Any]:
        """在线预约图书"""
        book = next((b for b in MOCK_BOOKS if b["isbn"] == isbn), None)
        title = book["title"] if book else "指定图书"
        return {
            "success": True,
            "queue_position": 1,
            "notify_channel": "嘉庚学院站内通知/微信企业号",
            "message": f"已成功预约《{title}》，当前排队位置为第 1 位。到馆后系统将通过站内信通知你取书。"
        }

    @staticmethod
    def get_recommendations(reader_id: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """获取个性化推荐书单"""
        return [
            {
                "title": "深入理解计算机系统",
                "author": "Randal E. Bryant",
                "isbn": "9787111544937",
                "call_number": "TP3/288",
                "reason": "根据你近期对工科与计算机大类（TP类）的借阅偏好推荐"
            },
            {
                "title": "三体",
                "author": "刘慈欣",
                "isbn": "9787536692930",
                "call_number": "I247.55/123",
                "reason": "全校借阅榜 TOP10 热门科幻经典文学"
            },
            {
                "title": "微观经济学：现代观点",
                "author": "范里安",
                "isbn": "9787543224971",
                "call_number": "F016/52",
                "reason": "经管大类高分必读书籍"
            }
        ][:limit]

    @staticmethod
    def search_rules_knowledge(question: str) -> Dict[str, Any]:
        """查阅借阅规章制度 (知识库)"""
        q = question.lower()
        if "借" in q and ("天" in q or "期" in q or "多久" in q):
            return {
                "found": True,
                "answer": "根据嘉庚学院图书馆规章，本科生普通中文图书借期为 30 天，在到期前未被他人预约的情况下可自助续借 1 次（延长 30 天）。",
                "source": "厦门大学嘉庚学院图书馆读者借阅规则·第二章"
            }
        elif "册" in q or "本数" in q or "几本" in q:
            return {
                "found": True,
                "answer": "本科生读者证借阅上限为 15 册，研究生上限为 20 册，教工上限为 30 册。",
                "source": "读者手册·借阅权限表"
            }
        elif "时间" in q or "开馆" in q or "闭馆" in q:
            return {
                "found": True,
                "answer": "主楼图书馆日常开放时间为周一至周日 08:00 - 22:30；期末考试周会延长至 23:00。法定节假日安排请见图书馆首页公告。",
                "source": "嘉庚学院图书馆日常开闭馆服务时间公示"
            }
        elif "座位" in q or "研讨室" in q:
            return {
                "found": True,
                "answer": "图书馆研修室与研讨室需通过“嘉庚图书馆研修室预约系统”或微信小程序提前预约，研讨室需满 3 人及以上方可签到使用。",
                "source": "研修室与空间管理办法"
            }
        return {
            "found": False,
            "answer": "如需了解更多具体规章或办理人工业务，请前往主楼总服务台咨询，或致电服务热线 0596-6288455。",
            "source": "人工服务台"
        }

data_client = DataClient()
