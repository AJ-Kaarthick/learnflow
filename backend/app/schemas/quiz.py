from datetime import datetime

from pydantic import BaseModel


class QuizQuestionResponse(BaseModel):
    id: str
    document_id: str
    question: str
    options: list[str]
    correct_answer_index: int
    position: int
    created_at: datetime

    model_config = {"from_attributes": True}
