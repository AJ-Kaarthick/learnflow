from datetime import datetime

from pydantic import BaseModel


class FlashcardResponse(BaseModel):
    id: str
    document_id: str
    question: str
    answer: str
    position: int
    created_at: datetime

    model_config = {"from_attributes": True}
