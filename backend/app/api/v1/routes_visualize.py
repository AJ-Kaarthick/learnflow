from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_identity
from app.db.database import get_db
from app.db.models import Document
from app.schemas.identity import Identity
from app.schemas.visualize import VisualizeGraphRequest, VisualizeGraphResponse
from app.services import guest_limit_service, ownership_service
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider
from app.services.guest_limit_service import GuestLimitExceededError, GuestLimitType
from app.services.visualize_service import generate_visualize_graph

router = APIRouter(prefix="/study/visualize", tags=["visualize"])


def _resolve_visualize_documents(
    document_ids: list[str],
    db: Session,
    identity: Identity,
) -> tuple[list[Document], list[tuple[Document, str]]]:
    """
    Validates ownership and readiness across the requested document IDs for Visualize Mode.

    - Every document must exist and be accessible to the requesting identity (404 if not).
    - For single-document selections:
        - Must be 'ready' (400 if processing, uploading, or failed).
        - Must have non-blank extracted text (422 if empty/whitespace-only).
    - For multi-document selections:
        - Filters documents into contributing (ready + readable) and excluded (unready/empty).
        - If zero documents are readable, rejects with 400.
    """
    documents: list[Document] = []
    for doc_id in document_ids:
        document = db.query(Document).filter(Document.id == doc_id).first()
        if document is None or not ownership_service.is_owned_by(document, identity):
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}.")
        documents.append(document)

    if len(documents) == 1:
        doc = documents[0]
        if doc.status != "ready":
            raise HTTPException(
                status_code=400,
                detail=f"Document is not ready for study (status: {doc.status}).",
            )
        if not (doc.extracted_text or "").strip():
            raise HTTPException(
                status_code=422,
                detail="No readable text was detected in this document. LearnFlow needs extractable text to generate visualization.",
            )
        return [doc], []

    contributing: list[Document] = []
    excluded: list[tuple[Document, str]] = []

    for doc in documents:
        if doc.status != "ready":
            excluded.append((doc, f"status_{doc.status}"))
        elif not (doc.extracted_text or "").strip():
            excluded.append((doc, "no_readable_text"))
        else:
            contributing.append(doc)

    if not contributing:
        raise HTTPException(
            status_code=400,
            detail="No readable documents available for study. Please select at least one ready document with readable text.",
        )

    return contributing, excluded


@router.post("/graph", response_model=VisualizeGraphResponse)
async def create_visualize_graph(
    payload: VisualizeGraphRequest,
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    identity: Identity = Depends(get_current_identity),
) -> VisualizeGraphResponse:
    """
    Generates a structured concept network graph across 1 to 10 selected documents.
    Enforces server-side document ownership, document readiness, and guest AI quotas.
    """
    contributing, excluded = _resolve_visualize_documents(payload.document_ids, db, identity)

    try:
        guest_limit_service.enforce_limit(db, identity, GuestLimitType.AI_GENERATION)
    except GuestLimitExceededError as error:
        raise guest_limit_service.to_http_exception(error)

    try:
        response = await generate_visualize_graph(
            requested_document_ids=payload.document_ids,
            contributing_documents=contributing,
            excluded_documents=excluded,
            db=db,
            ai_provider=ai_provider,
            embedding_provider=embedding_provider,
            depth=payload.depth,
        )
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    guest_limit_service.record_usage(db, identity, GuestLimitType.AI_GENERATION)
    return response
