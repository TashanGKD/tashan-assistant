import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analytics import compute_stats, generate_report
from .config import BASE_DIR, settings
from .llm import LLMClient
from .feishu import CaseStore
from .models import ChatRequest, ChatResponse, FeedbackRequest
from .prompts import EXTRACTOR_PROMPT, tutor_instructions
from .sanitize import sanitize_text

app = FastAPI(title=settings.app_name, version=settings.app_version)

origins = [x.strip() for x in settings.allowed_origins.split(",") if x.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )

llm = LLMClient()
store = CaseStore()

lessons = json.loads(
    (BASE_DIR / "knowledge" / "lessons.json").read_text(encoding="utf-8")
)

def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def case_id() -> str:
    return "TS-" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6].upper()

def safe_history(history):
    return [
        {"role": item.role, "content": sanitize_text(item.content)}
        for item in history[-24:]
    ]

def build_input(history, message: str):
    items = safe_history(history)
    items.append({"role": "user", "content": sanitize_text(message)})
    return items

def transcript_from(history, user_message: str, assistant_answer: str) -> str:
    parts = [f"{x['role']}: {x['content']}" for x in safe_history(history)]
    parts.append(f"user: {sanitize_text(user_message)}")
    parts.append(f"assistant: {sanitize_text(assistant_answer)}")
    return "\n".join(parts)

async def extract_and_update(record_id: str, transcript: str) -> None:
    try:
        data = await llm.extract_case(transcript, EXTRACTOR_PROMPT)
        fields = {
            "一级分类": data.get("category", "未分类"),
            "二级分类": data.get("subcategory", ""),
            "问题摘要": data.get("problem_summary", ""),
            "根因": data.get("root_cause", ""),
            "解决方案": data.get("solution_summary", ""),
            "FAQ候选": bool(data.get("faq_candidate", False)),
            "更新时间": iso_now(),
        }
        await store.update_case(record_id, fields)
    except Exception as exc:
        print("case extraction failed:", repr(exc))

def require_admin(token: str | None) -> None:
    if not settings.admin_token or settings.admin_token == "change-me-before-production":
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN is not configured")
    if token != settings.admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")

@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "version": settings.app_version,
        "model": settings.llm_model,
        "llm": llm.enabled,
        "feishu": store.enabled,
    }

@app.get("/api/lessons")
async def get_lessons():
    return lessons

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    if not llm.enabled:
        raise HTTPException(status_code=503, detail="LLM is not configured")

    current_case_id = req.case_id or case_id()
    record_id = req.record_id
    sanitized_message = sanitize_text(req.message)

    if not record_id:
        record_id = await store.create_case(
            {
                "Case ID": current_case_id,
                "匿名学员ID": req.client_id,
                "课次": req.lesson_id,
                "课程版本": settings.course_version,
                "原始问题": sanitized_message[:5000],
                "问题摘要": sanitized_message[:300],
                "状态": "NEW",
                "对话轮数": 1,
                "首次回答解决": False,
                "AI回答被纠错": False,
                "FAQ候选": False,
                "创建时间": iso_now(),
                "更新时间": iso_now(),
            }
        )

    state_hints = {
        "normal": "正常答疑。最终是否解决由学员按钮确认。",
        "unresolved_followup": (
            "用户明确点击了“还没解决”。上一轮方案未解决问题。"
            "禁止原样重复上一轮方案；根据新增信息重新判断根因。"
        ),
        "flagged_followup": (
            "用户明确点击了“回答有问题”。先复核上一轮事实、命令、版本与假设。"
            "如果上一轮有错，直接纠正，不辩护，再给新方案。"
        ),
    }

    answer = await llm.respond(
        tutor_instructions(
            req.lesson_id,
            state_hints.get(req.interaction_type, state_hints["normal"]),
        ),
        build_input(req.history, req.message),
        max_output_tokens=1600,
    )

    user_turns = sum(1 for item in req.history if item.role == "user") + 1
    transcript = transcript_from(req.history, req.message, answer)

    fields = {
        "状态": "ANSWERED",
        "对话轮数": user_turns,
        "最新进展": sanitized_message[-2500:],
        "最新回答": sanitize_text(answer)[-6000:],
        "更新时间": iso_now(),
    }
    if settings.feishu_store_transcript:
        fields["对话记录"] = transcript[-20000:]

    await store.update_case(record_id, fields)
    background_tasks.add_task(extract_and_update, record_id, transcript)

    return ChatResponse(
        case_id=current_case_id,
        record_id=record_id,
        answer=answer,
    )

@app.post("/api/feedback")
async def feedback(req: FeedbackRequest, background_tasks: BackgroundTasks):
    status_map = {
        "resolved": "RESOLVED",
        "unresolved": "CONTINUING",
        "flagged": "FLAGGED",
        "abandoned": "ABANDONED",
    }

    fields = {
        "状态": status_map[req.feedback_type],
        "最近反馈类型": req.feedback_type,
        "更新时间": iso_now(),
    }

    clean_text = sanitize_text(req.text)

    if req.feedback_type == "resolved":
        user_turns = sum(1 for item in req.history if item.role == "user")
        fields["首次回答解决"] = user_turns <= 1
        fields["解决时间"] = iso_now()
    elif req.feedback_type == "unresolved":
        fields["最新进展"] = clean_text[:5000]
    elif req.feedback_type == "flagged":
        fields["AI回答被纠错"] = True
        fields["反馈意见"] = clean_text[:5000]
    elif req.feedback_type == "abandoned":
        fields["反馈意见"] = "用户主动开启新对话"

    await store.update_case(req.record_id, fields)

    if clean_text:
        transcript = "\n".join(
            f"{x['role']}: {x['content']}" for x in safe_history(req.history)
        )
        transcript += f"\nfeedback({req.feedback_type}): {clean_text}"
        background_tasks.add_task(extract_and_update, req.record_id, transcript)

    return {"ok": True, "status": status_map[req.feedback_type]}

@app.get("/api/admin/lessons/{lesson_id}/stats")
async def admin_stats(
    lesson_id: int,
    x_admin_token: str | None = Header(default=None),
):
    require_admin(x_admin_token)
    cases = await store.list_cases(lesson_id)
    return {"lesson_id": lesson_id, "stats": compute_stats(cases)}

@app.post("/api/admin/lessons/{lesson_id}/report")
async def admin_report(
    lesson_id: int,
    x_admin_token: str | None = Header(default=None),
):
    require_admin(x_admin_token)
    if not llm.enabled:
        raise HTTPException(status_code=503, detail="LLM is not configured")
    cases = await store.list_cases(lesson_id)
    stats = compute_stats(cases)
    report = await generate_report(lesson_id, cases, stats)

    report_id = await store.save_report(
        {
            "课次": lesson_id,
            "课程版本": settings.course_version,
            "生成时间": iso_now(),
            "参与学员数": stats["participants"],
            "Case数": stats["total_cases"],
            "确认解决率": stats["resolution_rate"],
            "AI回答被纠错数": stats["flagged_answers"],
            "报告正文": report,
        }
    )
    return {
        "lesson_id": lesson_id,
        "report_id": report_id,
        "stats": stats,
        "report": report,
    }

frontend_dir = BASE_DIR / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
async def index():
    return FileResponse(frontend_dir / "index.html")
