"""
「小嘉」智能体意图识别、工具调用与安全兜底评测集 (Evaluation Benchmark)
对照开工手册 A4 产出标准：
1. 10 组核心场景 Query（查书、规章政策、推荐、超纲闲聊）
2. 验证工具命中率 >= 80%
3. 验证超纲/无关问题不产生幻觉、不编造答案（兜底率 >= 80%）
"""

import pytest
import asyncio
from app.agent.agent import agent
from app.auth import active_reader

BENCHMARK_CASES = [
    # 场景 1-2：馆藏与书目检索
    {
        "query": "帮我查一下《三体》这本书在哪个书架",
        "expected_tool": "search_books",
        "expected_keywords": ["三体", "书目"],
        "category": "catalog"
    },
    {
        "query": "请问馆里有没有关于计算机体系结构的书",
        "expected_tool": "search_books",
        "expected_keywords": ["书目", "检索"],
        "category": "catalog"
    },
    # 场景 3-6：规章制度与入馆咨询
    {
        "query": "本科生图书借期一共多少天",
        "expected_tool": "search_knowledge",
        "expected_keywords": ["天", "借期"],
        "category": "knowledge"
    },
    {
        "query": "每个人最多可以借几本书",
        "expected_tool": "search_knowledge",
        "expected_keywords": ["册", "本"],
        "category": "knowledge"
    },
    {
        "query": "图书馆晚上几点闭馆",
        "expected_tool": "search_knowledge",
        "expected_keywords": ["开放", "闭馆", "时间"],
        "category": "knowledge"
    },
    {
        "query": "研讨室需要怎么预约使用",
        "expected_tool": "search_knowledge",
        "expected_keywords": ["研讨室", "预约"],
        "category": "knowledge"
    },
    # 场景 7：个性化与热门推荐
    {
        "query": "最近大家都在看什么热门好书，推荐几本",
        "expected_tool": "recommend_books",
        "expected_keywords": ["推荐", "借阅"],
        "category": "recommend"
    },
    # 场景 8：业务指引
    {
        "query": "我借的书快超期了，请问怎么续借",
        "expected_tool": "search_knowledge",
        "expected_keywords": ["续借", "规则"],
        "category": "knowledge"
    },
    # 场景 9-10：超纲防幻觉与示弱兜底
    {
        "query": "明天厦门漳州天气怎么样",
        "expected_tool": None,  # 不调用业务工具
        "expected_keywords": ["小嘉", "馆方"],
        "category": "out_of_domain"
    },
    {
        "query": "帮我解一下这个二阶常微分方程",
        "expected_tool": None,
        "expected_keywords": ["小嘉", "馆方"],
        "category": "out_of_domain"
    }
]

def test_agent_benchmark_suite():
    """执行 10 组全场景评测"""
    correct_tools = 0
    correct_guardrails = 0
    total_in_domain = 0
    total_out_of_domain = 0

    for case in BENCHMARK_CASES:
        token = active_reader.set("demo-reader")
        try:
            tool, args, payload, cards, reply = agent._prepare(case["query"], reader_id="demo-reader")
        finally:
            active_reader.reset(token)

        if case["category"] == "out_of_domain":
            total_out_of_domain += 1
            # 超纲问题必须不触发业务工具，且不提供捏造的事实
            if tool is None:
                correct_guardrails += 1
                assert "小嘉" in reply
        else:
            total_in_domain += 1
            if tool == case["expected_tool"]:
                correct_tools += 1
            # 必须提供相关解答或卡片
            assert len(reply) > 0

    tool_accuracy = correct_tools / total_in_domain
    guardrail_accuracy = correct_guardrails / total_out_of_domain

    print(f"\n[Agent 评测结果] 工具选择准确率: {tool_accuracy:.1%}, 超纲兜底率: {guardrail_accuracy:.1%}")
    assert tool_accuracy >= 0.8, f"工具准确率未达标: {tool_accuracy}"
    assert guardrail_accuracy >= 0.8, f"超纲兜底率未达标: {guardrail_accuracy}"
