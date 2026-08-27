from typing import Literal
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=30000)

class ChatRequest(BaseModel):
    lesson_id: int = Field(ge=1, le=9)
    client_id: str = Field(min_length=6, max_length=100)
    message: str = Field(min_length=1, max_length=30000)
    case_id: str | None = None
    record_id: str | None = None
    history: list[ChatMessage] = []
    interaction_type: Literal["normal", "unresolved_followup", "flagged_followup"] = "normal"

class ChatResponse(BaseModel):
    case_id: str
    record_id: str | None = None
    answer: str

class FeedbackRequest(BaseModel):
    lesson_id: int = Field(ge=1, le=9)
    client_id: str = Field(min_length=6, max_length=100)
    case_id: str
    record_id: str | None = None
    feedback_type: Literal["resolved", "unresolved", "flagged", "abandoned"]
    text: str = Field(default="", max_length=10000)
    history: list[ChatMessage] = []
