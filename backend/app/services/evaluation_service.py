import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import RevisionAttempt, RevisionQuestion, RevisionSession
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.structured_output import extract_json

logger = logging.getLogger(__name__)


def evaluate_mcq_answer(
    question: RevisionQuestion,
    submitted_answer: str,
) -> tuple[bool, float, str, dict[str, Any]]:
    """
    Deterministically evaluates a multiple-choice question submission in Python.
    Does NOT call the AI provider.

    Normalizes options and submitted answers:
    - Direct string equality (case-insensitive, whitespace-trimmed)
    - Option index / letter prefix matching (e.g. 'A', 'B', '1', '2', 'A) ...')
    - Returns (is_correct, score, feedback, evaluation_metadata).
    """
    clean_sub = (submitted_answer or "").strip()
    correct_target = (question.correct_answer or "").strip()
    options: list[str] = [str(opt).strip() for opt in (question.options or []) if str(opt).strip()]

    if not clean_sub:
        return (
            False,
            0.0,
            f"No answer selected. The correct answer is: {correct_target}."
            + (f" {question.explanation}" if question.explanation else ""),
            {"evaluation_type": "deterministic_mcq", "normalized_submission": "", "reason": "empty_submission"},
        )

    is_correct = False

    # 1. Exact or case-insensitive match against correct_answer
    if clean_sub.lower() == correct_target.lower():
        is_correct = True
    else:
        # 2. Check if submitted answer matches an option index or letter ('A' -> 0, 'B' -> 1, ...)
        letter_match = re.match(r"^([A-Da-d1-4])(?:\)|\.|\:)?(?:\s+(.*))?$", clean_sub)
        matched_option_index: Optional[int] = None

        if letter_match:
            lead = letter_match.group(1).upper()
            if lead in "ABCD":
                matched_option_index = ord(lead) - ord("A")
            elif lead in "1234":
                matched_option_index = int(lead) - 1

        if matched_option_index is not None and 0 <= matched_option_index < len(options):
            chosen_opt = options[matched_option_index]
            if chosen_opt.lower() == correct_target.lower():
                is_correct = True
        else:
            # 3. Match against options text list directly
            for opt in options:
                if opt.lower() == clean_sub.lower() and opt.lower() == correct_target.lower():
                    is_correct = True
                    break

    score = 1.0 if is_correct else 0.0

    if is_correct:
        feedback = f"Correct! {question.explanation or 'Well done.'}".strip()
    else:
        feedback = (
            f"Incorrect. The correct answer is: {correct_target}."
            + (f" {question.explanation}" if question.explanation else "")
        ).strip()

    metadata = {
        "evaluation_type": "deterministic_mcq",
        "normalized_submission": clean_sub,
        "correct_target": correct_target,
    }

    return is_correct, score, feedback, metadata


async def evaluate_open_ended_answer(
    question: RevisionQuestion,
    submitted_answer: str,
    ai_provider: AIProvider,
) -> tuple[bool, float, str, dict[str, Any]]:
    """
    Evaluates an open-ended / conceptual recall question submission using AIProvider.
    Uses structured evaluation rubrics and clamps scores between 0.0 and 1.0.

    Empty or trivial submissions are handled deterministically without invoking the AI.
    """
    clean_sub = (submitted_answer or "").strip()

    # Deterministic short-circuit for empty submissions
    if not clean_sub:
        return (
            False,
            0.0,
            "No answer was provided. Please write an explanation or response to receive feedback.",
            {"evaluation_type": "deterministic_empty", "reasoning": "Empty submission"},
        )

    # Deterministic short-circuit for purely trivial non-words (e.g. single punctuation)
    if len(clean_sub) < 2 and not clean_sub.isalnum():
        return (
            False,
            0.0,
            "The submitted answer was too short or lacked meaningful content to evaluate.",
            {"evaluation_type": "deterministic_trivial", "reasoning": "Sub-threshold input"},
        )

    # AI evaluation prompt
    prompt = (
        "You are an expert academic evaluator. Assess the student's answer to this revision question.\n\n"
        f"Question:\n{question.question_text}\n\n"
        f"Reference Model Answer:\n{question.correct_answer}\n\n"
        f"Supporting Evidence from Source Text:\n{question.evidence_snippet or 'None provided.'}\n\n"
        f"Explanation / Evaluation Rubric:\n{question.explanation or 'None provided.'}\n\n"
        f"Student's Submitted Answer:\n{clean_sub}\n\n"
        "Evaluation Guidelines:\n"
        "- Assess conceptual accuracy, completeness, and reasoning based on the reference answer and evidence.\n"
        "- Assign a score strictly from 0.0 to 1.0:\n"
        "  - 1.0: Thoroughly accurate and complete response.\n"
        "  - 0.7 to 0.9: Conceptually sound with minor omissions.\n"
        "  - 0.4 to 0.6: Partial understanding with notable gaps.\n"
        "  - 0.0 to 0.3: Incorrect, irrelevant, or critically flawed.\n"
        "- Set 'is_correct' to true if score >= 0.7, otherwise false.\n"
        "- Provide concise, constructive feedback highlighting what was correct and what was missing.\n\n"
        "Respond with ONLY a JSON object — no markdown code fences, no commentary:\n"
        "{\n"
        '  "score": 0.85,\n'
        '  "is_correct": true,\n'
        '  "feedback": "Your answer accurately captures...",\n'
        '  "reasoning": "Identified the primary mechanism."\n'
        "}"
    )

    raw_text = await ai_provider.generate_text(prompt)
    data = extract_json(raw_text)

    if not isinstance(data, dict):
        raise AIProviderError("Expected a JSON object from evaluation AI.")

    raw_score = data.get("score")
    try:
        score = float(raw_score if raw_score is not None else 0.0)
    except (ValueError, TypeError):
        score = 0.0
    score = max(0.0, min(1.0, score))

    raw_is_correct = data.get("is_correct")
    if isinstance(raw_is_correct, bool):
        is_correct = raw_is_correct
    else:
        is_correct = score >= 0.7

    feedback = str(data.get("feedback") or "Evaluation complete.").strip()
    reasoning = str(data.get("reasoning") or "").strip()

    metadata = {
        "evaluation_type": "ai_assisted",
        "score": score,
        "reasoning": reasoning,
    }

    return is_correct, score, feedback, metadata


def record_question_attempt(
    db: Session,
    session: RevisionSession,
    question: RevisionQuestion,
    submitted_answer: str,
    is_correct: bool,
    score: float,
    feedback: str,
    evaluation_metadata: dict[str, Any],
) -> RevisionAttempt:
    """
    Creates and persists a new RevisionAttempt.
    Guarantees sequential attempt numbering (1 -> 2 -> 3) and never mutates
    prior attempts or the RevisionQuestion entity.
    """
    max_att = (
        db.query(func.max(RevisionAttempt.attempt_number))
        .filter(RevisionAttempt.question_id == question.id)
        .scalar()
    )
    attempt_number = (max_att or 0) + 1

    attempt = RevisionAttempt(
        question_id=question.id,
        session_id=session.id,
        attempt_number=attempt_number,
        submitted_answer=submitted_answer,
        is_correct=is_correct,
        score=score,
        feedback=feedback,
        evaluation_metadata=evaluation_metadata,
    )
    db.add(attempt)

    try:
        db.commit()
        db.refresh(attempt)
        return attempt
    except IntegrityError:
        db.rollback()
        # Concurrency safety: if another attempt landed in between, re-query max and retry once
        logger.warning(
            f"Integrity conflict on attempt {attempt_number} for question {question.id}; retrying with next index."
        )
        max_att = (
            db.query(func.max(RevisionAttempt.attempt_number))
            .filter(RevisionAttempt.question_id == question.id)
            .scalar()
        )
        attempt.attempt_number = (max_att or 0) + 1
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        return attempt
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to persist revision attempt: {exc}", exc_info=True)
        raise


def calculate_session_score(session: RevisionSession, db: Session) -> float:
    """
    Calculates the cumulative session score across all questions in the session.

    Attempt-selection rule:
    - Uses the LATEST submitted attempt for each question.
    - Multiple attempts for the same question are never double-counted.
    - Questions without attempts are scored as 0.0.
    - Final score is the mean across all questions in the session, in range 0.0 to 1.0.
    """
    total_questions = session.total_questions if session.total_questions > 0 else len(session.questions)
    if total_questions == 0:
        return 0.0

    sum_scores = 0.0

    for question in session.questions:
        latest_attempt = (
            db.query(RevisionAttempt)
            .filter(RevisionAttempt.question_id == question.id)
            .order_by(RevisionAttempt.attempt_number.desc())
            .first()
        )
        if latest_attempt is not None:
            sum_scores += float(latest_attempt.score)

    final_score = round(sum_scores / total_questions, 4)
    return max(0.0, min(1.0, final_score))


def complete_revision_session(session: RevisionSession, db: Session) -> RevisionSession:
    """
    Finalizes a revision session, records the final score computed from latest attempts,
    and transitions status to 'completed'.
    """
    if session.status == "completed":
        raise ValueError("Cannot complete a revision session that is already completed.")

    final_score = calculate_session_score(session, db)

    session.status = "completed"
    session.score = final_score
    session.completed_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(session)
        return session
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to complete revision session {session.id}: {exc}", exc_info=True)
        raise
