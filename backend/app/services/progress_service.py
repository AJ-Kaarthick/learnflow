from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Document, RevisionAttempt, RevisionQuestion, RevisionSession
from app.schemas.identity import Identity
from app.schemas.progress import (
    ActivityWindowsSchema,
    ActivityWindowSummary,
    DailyActivityItem,
    DifficultyDistributionItem,
    FlashcardMetricsSchema,
    MasteryResultSchema,
    ProgressSummaryResponse,
    TopicMasteryResponseItem,
)
from app.services.mastery_service import (
    calculate_mastery_for_attempts,
    ensure_utc,
    get_completed_sessions_for_identity,
    get_overall_mastery,
)


def _to_mastery_schema(res) -> MasteryResultSchema:
    return MasteryResultSchema(
        score=res.score,
        tier=res.tier,
        is_assessed=res.is_assessed,
        attempted_count=res.attempted_count,
        questions_needed=res.questions_needed,
        last_attempted_at=res.last_attempted_at,
    )


def get_progress_summary(
    db: Session,
    identity: Identity,
    now: Optional[datetime] = None,
) -> ProgressSummaryResponse:
    """
    Computes overall progress metrics, activity timelines, difficulty distributions,
    and flashcard metrics on demand for the requesting identity.
    """
    ref_now = ensure_utc(now) or datetime.now(timezone.utc)
    sessions = get_completed_sessions_for_identity(db, identity)

    total_completed_sessions = len(sessions)
    all_questions = [q for s in sessions for q in s.questions]
    total_questions_generated = len(all_questions)

    attempted_questions = [q for q in all_questions if q.attempts]
    total_attempted_questions = len(attempted_questions)
    total_unanswered_questions = total_questions_generated - total_attempted_questions
    total_attempts = sum(len(q.attempts) for q in all_questions)

    # 1. Overall attempt accuracy based strictly on latest attempt per distinct question
    latest_attempts: list[RevisionAttempt] = [
        max(q.attempts, key=lambda a: a.attempt_number) for q in attempted_questions
    ]
    latest_scores = [float(a.score) for a in latest_attempts]
    overall_attempt_accuracy = (
        round(sum(latest_scores) / len(latest_scores), 4) if latest_scores else 0.0
    )

    # 2. Mean official completed-session score (includes penalty for unanswered questions)
    session_scores = [float(s.score) for s in sessions if s.score is not None]
    mean_session_score = (
        round(sum(session_scores) / len(session_scores), 4) if session_scores else 0.0
    )

    # 3. Overall recency-decayed mastery across all attempted questions
    overall_attempt_tuples = [(float(a.score), a.created_at) for a in latest_attempts]
    overall_mastery_res = calculate_mastery_for_attempts(overall_attempt_tuples, now=ref_now)
    overall_mastery = _to_mastery_schema(overall_mastery_res)

    # 4. Activity timeline & score trends over the last 30, 14, and 7 UTC days
    today_utc = ref_now.date()
    days_30 = [today_utc - timedelta(days=i) for i in range(29, -1, -1)]

    # Bucket attempts and sessions by UTC date
    attempts_by_date: dict[datetime.date, list[RevisionAttempt]] = {}
    for q in attempted_questions:
        for a in q.attempts:
            if a.created_at is not None:
                d = ensure_utc(a.created_at).date()
                attempts_by_date.setdefault(d, []).append(a)

    sessions_by_date: dict[datetime.date, list[RevisionSession]] = {}
    for s in sessions:
        if s.completed_at is not None:
            d = ensure_utc(s.completed_at).date()
            sessions_by_date.setdefault(d, []).append(s)

    daily_items: list[DailyActivityItem] = []
    for d in days_30:
        d_attempts = attempts_by_date.get(d, [])
        d_sessions = sessions_by_date.get(d, [])
        d_q_ids = {a.question_id for a in d_attempts}
        avg_s = (
            round(sum(float(a.score) for a in d_attempts) / len(d_attempts), 4)
            if d_attempts
            else None
        )
        daily_items.append(
            DailyActivityItem(
                date=d.isoformat(),
                total_attempts=len(d_attempts),
                questions_attempted=len(d_q_ids),
                sessions_completed=len(d_sessions),
                average_score=avg_s,
            )
        )

    def _build_window(window_days: list[DailyActivityItem], num_days: int) -> ActivityWindowSummary:
        tot_att = sum(item.total_attempts for item in window_days)
        tot_sess = sum(item.sessions_completed for item in window_days)
        window_q_ids: set[str] = set()
        all_window_scores: list[float] = []
        for item in window_days:
            item_date = datetime.strptime(item.date, "%Y-%m-%d").date()
            for att in attempts_by_date.get(item_date, []):
                window_q_ids.add(att.question_id)
                all_window_scores.append(float(att.score))
        tot_q = len(window_q_ids)
        avg_score = (
            round(sum(all_window_scores) / len(all_window_scores), 4)
            if all_window_scores
            else None
        )
        return ActivityWindowSummary(
            days=num_days,
            total_attempts=tot_att,
            questions_attempted=tot_q,
            sessions_completed=tot_sess,
            average_score=avg_score,
            timeline=window_days,
        )

    windows = ActivityWindowsSchema(
        last_7_days=_build_window(daily_items[-7:], 7),
        last_14_days=_build_window(daily_items[-14:], 14),
        last_30_days=_build_window(daily_items, 30),
    )

    # 5. Difficulty distribution (Beginner, Intermediate, Advanced)
    questions_by_diff: dict[str, list[RevisionQuestion]] = {
        "beginner": [],
        "intermediate": [],
        "advanced": [],
    }
    for q in attempted_questions:
        diff = (q.evidence_metadata or {}).get("difficulty")
        if not diff and q.session and q.session.config:
            diff = q.session.config.get("difficulty")
        if isinstance(diff, str) and diff.lower().strip() in questions_by_diff:
            questions_by_diff[diff.lower().strip()].append(q)

    difficulty_distribution: list[DifficultyDistributionItem] = []
    for diff_name in ["beginner", "intermediate", "advanced"]:
        q_list = questions_by_diff[diff_name]
        d_distinct_q = len(q_list)
        d_total_attempts = sum(len(q.attempts) for q in q_list)
        d_latest_scores = [
            float(max(q.attempts, key=lambda a: a.attempt_number).score)
            for q in q_list
        ]
        d_avg_score = (
            round(sum(d_latest_scores) / len(d_latest_scores), 4)
            if d_latest_scores
            else None
        )
        d_tuples = [
            (
                float(max(q.attempts, key=lambda a: a.attempt_number).score),
                max(q.attempts, key=lambda a: a.attempt_number).created_at,
            )
            for q in q_list
        ]
        d_mastery = _to_mastery_schema(calculate_mastery_for_attempts(d_tuples, now=ref_now))
        difficulty_distribution.append(
            DifficultyDistributionItem(
                difficulty=diff_name,
                distinct_attempted_questions=d_distinct_q,
                total_attempts=d_total_attempts,
                average_score=d_avg_score,
                mastery=d_mastery,
            )
        )

    # 6. Revision flashcard metrics (mode == 'flashcards')
    fc_sessions = [s for s in sessions if (s.config or {}).get("mode") == "flashcards"]
    fc_attempted_questions = [
        q for s in fc_sessions for q in s.questions if q.attempts
    ]
    fc_distinct_reviewed = len(fc_attempted_questions)
    fc_total_attempts = sum(len(q.attempts) for q in fc_attempted_questions)

    if fc_attempted_questions:
        fc_correct = sum(
            1
            for q in fc_attempted_questions
            if max(q.attempts, key=lambda a: a.attempt_number).is_correct
        )
        fc_recall_rate = round(fc_correct / fc_distinct_reviewed, 4)
    else:
        fc_recall_rate = None

    fc_tuples = [
        (
            float(max(q.attempts, key=lambda a: a.attempt_number).score),
            max(q.attempts, key=lambda a: a.attempt_number).created_at,
        )
        for q in fc_attempted_questions
    ]
    fc_mastery = _to_mastery_schema(calculate_mastery_for_attempts(fc_tuples, now=ref_now))

    flashcard_metrics = FlashcardMetricsSchema(
        distinct_questions_reviewed=fc_distinct_reviewed,
        total_attempts=fc_total_attempts,
        recall_rate=fc_recall_rate,
        mastery=fc_mastery,
    )

    return ProgressSummaryResponse(
        overall_mastery=overall_mastery,
        total_completed_sessions=total_completed_sessions,
        total_questions_generated=total_questions_generated,
        total_attempted_questions=total_attempted_questions,
        total_unanswered_questions=total_unanswered_questions,
        total_attempts=total_attempts,
        overall_attempt_accuracy=overall_attempt_accuracy,
        mean_session_score=mean_session_score,
        activity_timeline=daily_items,
        activity_windows=windows,
        difficulty_distribution=difficulty_distribution,
        flashcard_metrics=flashcard_metrics,
    )


def get_progress_topics(
    db: Session,
    identity: Identity,
    now: Optional[datetime] = None,
) -> list[TopicMasteryResponseItem]:
    """
    Returns topic-level mastery items using Phase 1 mastery service,
    preserving composite grouping by (source_document_identity, normalized_topic_key).
    """
    summary = get_overall_mastery(db, identity, now=now)
    items: list[TopicMasteryResponseItem] = []
    for tm in summary.topic_masteries:
        items.append(
            TopicMasteryResponseItem(
                document_id=tm.document_id,
                document_title=tm.document_title,
                is_archived=tm.is_archived,
                topic_key=tm.topic_key,
                topic_display=tm.topic_display,
                mastery_score=tm.mastery.score,
                mastery_tier=tm.mastery.tier,
                is_assessed=tm.mastery.is_assessed,
                distinct_attempted_questions=tm.mastery.attempted_count,
                questions_needed=tm.mastery.questions_needed,
                last_attempted_at=tm.mastery.last_attempted_at,
            )
        )
    return items
