from datetime import datetime

from pydantic import BaseModel


class SummaryResponse(BaseModel):
    id: str
    document_id: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
