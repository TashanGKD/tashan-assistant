from app.analytics import compute_stats

def test_compute_stats():
    cases = [
        {"匿名学员ID": "a", "状态": "RESOLVED", "一级分类": "环境配置", "对话轮数": 1},
        {"匿名学员ID": "a", "状态": "ANSWERED", "一级分类": "环境配置", "对话轮数": 2},
        {"匿名学员ID": "b", "状态": "FLAGGED", "一级分类": "工具调用", "对话轮数": 3, "AI回答被纠错": True},
        {"匿名学员ID": "c", "状态": "ABANDONED", "一级分类": "Prompt设计", "对话轮数": 1},
    ]
    stats = compute_stats(cases)
    assert stats["participants"] == 3
    assert stats["total_cases"] == 4
    assert stats["resolved"] == 1
    assert stats["resolution_rate"] == 25.0
    assert stats["currently_continuing"] == 1
    assert stats["no_final_feedback"] == 2
    assert stats["flagged_answers"] == 1
