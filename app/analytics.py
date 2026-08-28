from collections import Counter

from .llm import LLMClient
from .prompts import REPORT_PROMPT

def truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "是"}

def compute_stats(cases: list[dict]) -> dict:
    total = len(cases)
    statuses = Counter(str(x.get("状态") or "NO_FEEDBACK") for x in cases)
    categories = Counter(str(x.get("一级分类") or "未分类") for x in cases)
    clients = {str(x.get("匿名学员ID")) for x in cases if x.get("匿名学员ID")}

    resolved = statuses.get("RESOLVED", 0)
    flagged = sum(1 for x in cases if truthy(x.get("AI回答被纠错")))

    turns = []
    for case in cases:
        try:
            turns.append(int(case.get("对话轮数") or 0))
        except (TypeError, ValueError):
            pass

    return {
        "participants": len(clients),
        "total_cases": total,
        "resolved": resolved,
        "resolution_rate": round((resolved / total) * 100, 1) if total else 0.0,
        "currently_continuing": statuses.get("CONTINUING", 0) + statuses.get("FLAGGED", 0),
        "no_final_feedback": (
            statuses.get("ANSWERED", 0)
            + statuses.get("ABANDONED", 0)
            + statuses.get("NO_FEEDBACK", 0)
        ),
        "flagged_answers": flagged,
        "avg_turns": round(sum(turns) / len(turns), 2) if turns else 0.0,
        "status_counts": dict(statuses),
        "category_counts": dict(categories.most_common()),
    }

async def generate_report(lesson_id: int, cases: list[dict], stats: dict) -> str:
    compact = []
    for case in cases[:400]:
        compact.append(
            {
                "问题": case.get("问题摘要") or case.get("原始问题", ""),
                "分类": case.get("一级分类", ""),
                "根因": case.get("根因", ""),
                "方案": case.get("解决方案", ""),
                "状态": case.get("状态", ""),
                "最近反馈": case.get("最近反馈类型", ""),
                "AI被纠错": truthy(case.get("AI回答被纠错")),
            }
        )

    prompt = f"课次：{lesson_id}\n程序统计：{stats}\nCase摘要：{compact}"
    client = LLMClient()

    return await client.respond(
        REPORT_PROMPT,
        prompt,
        max_output_tokens=2600,
    )
