from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Document, RevisionQuestion, RevisionSession, RevisionSessionDocument
from app.schemas.identity import Identity
from app.schemas.progress import RecommendationActionPayload, RecommendationResponseItem
from app.services.mastery_service import ensure_utc, is_document_actionable
from app.services.spaced_repetition_service import get_review_schedules
from app.services.weak_topic_service import detect_weak_topics


def get_recommendations(
    db: Session,
    identity: Identity,
    now: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> list[RecommendationResponseItem]:
    """
    Generates deterministic, on-demand adaptive learning recommendations
    strictly adhering to the M5 priority hierarchy:
    1. Priority 1 (spaced_review): Due active documents (urgency >= 1.0)
    2. Priority 2 (weak_topic_practice): Detected weak topics on active documents
    3. Priority 3 (unrevised_document): Active, ready documents with zero revision history

    Zero LLM calls, zero database mutations, zero AI quota consumption.
    Archived/deleted documents are strictly excluded from actionable recommendations.
    """
    ref_now = ensure_utc(now) or datetime.now(timezone.utc)

    # -----------------------------------------------------------------------
    # Priority 1: Due for Spaced Review
    # -----------------------------------------------------------------------
    priority_1_items: list[RecommendationResponseItem] = []
    # Fetch review schedules (only documents with history)
    schedules = get_review_schedules(
        db,
        identity,
        now=ref_now,
        include_unreviewed_active=False,
    )

    for item in schedules:
        # Strictly active, actionable, with history, and due
        if item.is_archived or not item.is_actionable or not item.has_history:
            continue
        if not item.is_due or not item.document_id or not item.next_review_due:
            continue

        # Urgency: elapsed time since last review / interval in days
        interval = item.interval_days or 1
        last_rev = ensure_utc(item.last_reviewed_at) or item.next_review_due
        elapsed_days = max(0.0, (ref_now - last_rev).total_seconds() / 86400.0)
        urgency = round(max(1.0, elapsed_days / float(interval)), 2)

        rec = RecommendationResponseItem(
            id=f"sr:{item.document_id}",
            type="spaced_review",
            priority=1,
            title=f"Review: {item.document_title}",
            reason=f"Spaced review is due (streak: {item.current_streak}, interval: {interval}d, urgency: {urgency}x).",
            document_id=item.document_id,
            document_title=item.document_title,
            is_archived=False,
            is_actionable=True,
            topic_focus=None,
            urgency=urgency,
            due_date=item.next_review_due,
            struggle_index=None,
            mastery_score=item.latest_review_score,
            action_payload=RecommendationActionPayload(
                document_ids=[item.document_id],
                mode="practice",
                difficulty="intermediate",
                question_count=5,
                question_type="multiple_choice",
                topic_focus=None,
            ),
        )
        priority_1_items.append(rec)

    # Sort Priority 1: highest urgency first, earliest due date first, title, document ID
    priority_1_items.sort(
        key=lambda r: (
            -(r.urgency or 0.0),
            ensure_utc(r.due_date) or datetime.max.replace(tzinfo=timezone.utc),
            r.document_title.casefold(),
            r.document_id,
        )
    )

    # -----------------------------------------------------------------------
    # Priority 2: Weak-Topic Practice
    # -----------------------------------------------------------------------
    priority_2_items: list[RecommendationResponseItem] = []
    weak_topics = detect_weak_topics(db, identity, now=ref_now)

    for wt in weak_topics:
        # Strictly active, actionable documents
        if wt.is_archived or not wt.is_actionable or not wt.document_id:
            continue

        rec = RecommendationResponseItem(
            id=f"wt:{wt.document_id}:{wt.topic_key}",
            type="weak_topic_practice",
            priority=2,
            title=f"Practice Weak Topic: {wt.topic_display}",
            reason=f"Identified as a weak topic in {wt.document_title} (mastery: {int(wt.mastery_score * 100)}%, struggle index: {wt.struggle_index}).",
            document_id=wt.document_id,
            document_title=wt.document_title,
            is_archived=False,
            is_actionable=True,
            topic_focus=wt.topic_display,
            urgency=None,
            due_date=None,
            struggle_index=wt.struggle_index,
            mastery_score=wt.mastery_score,
            action_payload=RecommendationActionPayload(
                document_ids=[wt.document_id],
                mode="practice",
                difficulty="intermediate",
                question_count=5,
                question_type="multiple_choice",
                topic_focus=wt.topic_display,
            ),
        )
        priority_2_items.append(rec)

    # Sort Priority 2: highest struggle index first, lower mastery score first, title, topic
    priority_2_items.sort(
        key=lambda r: (
            -(r.struggle_index or 0.0),
            r.mastery_score if r.mastery_score is not None else 1.0,
            r.document_title.casefold(),
            (r.topic_focus or "").casefold(),
            r.document_id,
        )
    )

    # -----------------------------------------------------------------------
    # Priority 3: Unrevised Documents
    # -----------------------------------------------------------------------
    priority_3_items: list[RecommendationResponseItem] = []

    # 1. Collect all document IDs that have established revision history for this identity
    revised_doc_ids: set[str] = set()

    # Via RevisionSessionDocument join
    session_docs = (
        db.query(RevisionSessionDocument.document_id)
        .join(RevisionSession, RevisionSessionDocument.session_id == RevisionSession.id)
        .filter(
            RevisionSession.owner_type == identity.type.value,
            RevisionSession.owner_id == identity.id,
        )
        .all()
    )
    for row in session_docs:
        if row[0]:
            revised_doc_ids.add(row[0])

    # Via RevisionQuestion source foreign keys
    question_docs = (
        db.query(RevisionQuestion.source_document_id)
        .join(RevisionSession, RevisionQuestion.session_id == RevisionSession.id)
        .filter(
            RevisionSession.owner_type == identity.type.value,
            RevisionSession.owner_id == identity.id,
            RevisionQuestion.source_document_id.isnot(None),
        )
        .all()
    )
    for row in question_docs:
        if row[0]:
            revised_doc_ids.add(row[0])

    # Also inspect evidence_metadata snapshots across questions to avoid misclassifying
    # documents whose FK might be null
    snapshot_questions = (
        db.query(RevisionQuestion.evidence_metadata)
        .join(RevisionSession, RevisionQuestion.session_id == RevisionSession.id)
        .filter(
            RevisionSession.owner_type == identity.type.value,
            RevisionSession.owner_id == identity.id,
        )
        .all()
    )
    for (meta,) in snapshot_questions:
        if isinstance(meta, dict) and meta.get("source_document_id"):
            revised_doc_ids.add(str(meta["source_document_id"]))

    # 2. Query active ready documents owned by identity
    active_ready_docs = (
        db.query(Document)
        .filter(
            Document.owner_type == identity.type.value,
            Document.owner_id == identity.id,
            Document.status == "ready",
        )
        .all()
    )

    for doc in active_ready_docs:
        if doc.id in revised_doc_ids:
            continue
        if not is_document_actionable(doc):
            continue

        rec = RecommendationResponseItem(
            id=f"unrev:{doc.id}",
            type="unrevised_document",
            priority=3,
            title=f"Start Revision: {doc.original_filename}",
            reason="Document has not yet been revised. Start an initial revision session to establish baseline mastery.",
            document_id=doc.id,
            document_title=doc.original_filename,
            is_archived=False,
            is_actionable=True,
            topic_focus=None,
            urgency=None,
            due_date=None,
            struggle_index=None,
            mastery_score=None,
            action_payload=RecommendationActionPayload(
                document_ids=[doc.id],
                mode="practice",
                difficulty="intermediate",
                question_count=5,
                question_type="multiple_choice",
                topic_focus=None,
            ),
        )
        priority_3_items.append(rec)

    # Sort Priority 3: document title alphabetical, document ID
    priority_3_items.sort(
        key=lambda r: (
            r.document_title.casefold(),
            r.document_id,
        )
    )

    # -----------------------------------------------------------------------
    # Aggregate and return
    # -----------------------------------------------------------------------
    all_recommendations = priority_1_items + priority_2_items + priority_3_items

    if limit is not None and limit > 0:
        return all_recommendations[:limit]

    return all_recommendations
