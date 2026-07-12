from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MindMapResponse(BaseModel):
    id: str
    document_id: str

    # {"title": str, "children": [...]}, recursively. Typed as a plain
    # dict rather than a recursive Pydantic model: the tree shape is
    # already validated in mindmap_service.py before it's ever saved,
    # so re-validating it here would be redundant, not protective.
    structure: dict[str, Any]

    created_at: datetime

    model_config = {"from_attributes": True}
