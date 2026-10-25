"""只测试已核对的官网摘要与检索边界，不把猜测写成馆方规则。"""
import json
import tempfile
import unittest
from pathlib import Path
from data.knowledge import KnowledgeBase, DEFAULT_SOURCE

CASES = [
    ("几点开馆？", "hours/normal"), ("周三能还书吗", "hours/normal"),
    ("前台几点上班", "hours/normal"), ("暑假开馆时间", "hours/holiday"),
    ("国庆开放吗", "hours/holiday"), ("本科普通图书能借几天", "borrowing/ordinary"),
    ("老师的借期多久", "borrowing/ordinary"), ("续借可以延长多少天", "borrowing/ordinary"),
    ("学生能借多少本", "borrowing/limits"), ("借书册数上限", "borrowing/limits"),
    ("欠款会停借吗", "borrowing/limits"), ("嘉庚系统能预约吗", "borrowing/reservation"),
    ("收到催还通知怎么办", "borrowing/reservation"), ("普通图书和现刊权限", "borrowing/special"),
    ("日文文献借阅", "borrowing/special"), ("特藏和报纸能外借吗", "borrowing/special"),
    ("校外人员入馆", "entry/conduct"), ("可以给充电宝充电吗", "entry/conduct"),
    ("座位签到时间", "seats/checkin"), ("每天选座几次", "seats/checkin"),
    ("午餐暂离保留多久", "seats/absence"), ("返回后如何回座", "seats/absence"),
    ("座位违规几次黑名单", "seats/violations"), ("备考期间违规", "seats/violations"),
    ("积分会跨年累加吗", "points/annual"), ("积分起始多少", "points/annual"),
    ("占座物品怎么领回", "items/claim"), ("被收物品暂存多久", "items/claim"),
]


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase()

    def test_official_questions_retrieve_expected_sections(self):
        for question, expected in CASES:
            with self.subTest(question=question):
                result = self.kb.answer(question)
                self.assertTrue(result["found"])
                self.assertIn(expected, [row["chunk_id"] for row in result["sources"]])
                self.assertTrue(all(row["url"].startswith("https://library.xujc.com/") for row in result["sources"]))

    def test_no_support_is_not_a_fabricated_answer(self):
        for question in ("", "北京天气如何", "帮我写Python爬虫", "未来金价预测", "研讨室必须几个人签到", "图书馆"):
            self.assertFalse(self.kb.answer(question)["found"], question)

    def test_scope_and_revision_are_retained(self):
        result = self.kb.answer("普通图书续借")
        self.assertIn("3 次", result["answer"])
        self.assertIn("60 天", result["answer"])
        self.assertIn("180 天", result["answer"])
        self.assertFalse(result["is_live"])
        self.assertTrue(all(row["chunk_id"].startswith("borrowing/")
                            for row in self.kb.retrieve("普通图书借几天续借几次")))
        seats = self.kb.retrieve("座位黑名单")
        self.assertEqual(seats[0]["revised_at"], "2026-09-08")

    def test_export_has_real_vectors_and_fingerprint(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp) / "index.json"
            report = self.kb.export(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(report["chunks"], 12)
            self.assertEqual(len(payload["vectors"]), 12)
            self.assertTrue(all(payload["vectors"]))
            self.assertEqual(payload["source_sha256"], self.kb.source_sha256)

    def test_invalid_source_and_queries_rejected(self):
        with self.assertRaises(ValueError):
            self.kb.retrieve("书" * 501)
        with self.assertRaises(ValueError):
            self.kb.retrieve("开馆", 0)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            payload = json.loads(DEFAULT_SOURCE.read_text(encoding="utf-8"))
            payload["documents"][0]["url"] = "https://example.com/rules"
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                KnowledgeBase(path)
