from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Document, MindMap
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.structured_output import extract_json

MAX_CHARACTERS_FOR_PROMPT = 15000

# A soft cap matching what the prompt asks for. Also a safety valve
# against validating an unreasonably deep tree if a model ignores the
# instruction — not a hard error, just where we stop checking further.
MAX_TREE_DEPTH = 4


def build_mindmap_prompt(document_text: str) -> str:
    truncated = document_text[:MAX_CHARACTERS_FOR_PROMPT]
    return (
        "Create a mind map that organizes the key concepts in the "
        "document below into a hierarchy, from the single most central "
        "topic down to specific supporting details. Use at most 3 levels "
        "of nesting below the central topic, and keep each title short "
        "(a few words).\n\n"
        "Respond with ONLY a JSON object — no markdown code fences, no "
        "commentary before or after it. It must look exactly like this "
        'shape: {"title": "Central Topic", "children": [{"title": '
        '"Subtopic", "children": [{"title": "Detail", "children": []}]}]}'
        "\n\n"
        f"Document:\n{truncated}"
    )


def _validate_mindmap_node(node: Any, depth: int = 0) -> None:
    if not isinstance(node, dict):
        raise AIProviderError("Each mind map node must be a JSON object.")
    if not isinstance(node.get("title"), str) or not node["title"].strip():
        raise AIProviderError("Each mind map node needs a non-empty 'title'.")

    children = node.get("children", [])
    if not isinstance(children, list):
        raise AIProviderError("A mind map node's 'children' must be a list.")

    if depth >= MAX_TREE_DEPTH:
        return

    for child in children:
        _validate_mindmap_node(child, depth + 1)


async def generate_mindmap_for_document(
    document: Document, db: Session, provider: AIProvider
) -> MindMap:
    existing = db.query(MindMap).filter(MindMap.document_id == document.id).first()
    if existing is not None:
        return existing

    prompt = build_mindmap_prompt(document.extracted_text or "")
    raw_text = await provider.generate_text(prompt)

    structure = extract_json(raw_text)
    _validate_mindmap_node(structure)

    mindmap = MindMap(document_id=document.id, structure=structure)
    db.add(mindmap)
    db.commit()
    db.refresh(mindmap)
    return mindmap
