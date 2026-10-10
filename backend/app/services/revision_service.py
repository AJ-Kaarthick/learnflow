import json
import logging
import re
import unicodedata
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import Document, RevisionQuestion, RevisionSession, RevisionSessionDocument
from app.schemas.identity import Identity
from app.schemas.revision import RevisionSessionCreateRequest
from app.services import ownership_service
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.structured_output import extract_json

logger = logging.getLogger(__name__)

# Bounded context limit for question generation across all selected documents.
# Guarantees the prompt stays safely within model context limits for 1-10 documents.
MAX_REVISION_TOTAL_CHARS = 16000

GENERIC_TOPIC_PLACEHOLDERS = {
    "general",
    "n/a",
    "na",
    "none",
    "topic",
    "document",
    "introduction",
    "overview",
    "untitled",
    "unknown",
}


class UnsupportedTopicError(Exception):
    """
    Raised when the selected document excerpts do not contain sufficient
    substantive content for the requested topic focus.
    """

    pass


def clean_and_normalize_topic(raw_value: Any) -> Optional[tuple[str, str]]:
    """
    Normalizes a topic string and returns (display_label, topic_key) if valid,
    or None if missing, blank, generic, or invalid.
    """
    if not raw_value or not isinstance(raw_value, str):
        return None
    if any(unicodedata.category(c).startswith("C") for c in raw_value):
        return None
    normalized = unicodedata.normalize("NFKC", raw_value)
    cleaned = re.sub(r"\s+", " ", normalized).strip()
    cleaned = cleaned.strip("\"'`[]{}()")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) < 2 or len(cleaned) > 100:
        return None
    key = cleaned.casefold()
    if key in GENERIC_TOPIC_PLACEHOLDERS:
        return None
    return cleaned, key


def verify_evidence_in_document(evidence: Optional[str], document_text: Optional[str]) -> bool:
    """
    Verifies that an evidence snippet is non-empty and actually appears in the referenced
    document text, allowing safe whitespace normalization, quote stripping, and casing tolerance.
    """
    if not evidence or not document_text:
        return False

    def _normalize(s: str) -> str:
        s = unicodedata.normalize("NFKC", s)
        s = " ".join(s.split())
        s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        return s.strip()

    norm_evidence = _normalize(evidence).strip("\"'`")
    norm_doc = _normalize(document_text)

    if len(norm_evidence) < 5:
        return False

    return norm_evidence.casefold() in norm_doc.casefold()


def build_revision_prompt(
    documents: list[Document],
    question_count: int,
    difficulty: str = "intermediate",
    mode: str = "practice",
    question_type: str = "multiple_choice",
    topic_focus: Optional[str] = None,
) -> str:
    """
    Builds the bounded-context prompt for generating grounded revision questions.
    Distributes available character budget proportionally across selected documents.
    Safely encodes and delimits untrusted topic_focus input when present.
    """
    if not documents:
        raise ValueError("At least one document is required to build a revision prompt.")

    chars_per_doc = max(1000, MAX_REVISION_TOTAL_CHARS // len(documents))

    doc_sections = []
    for doc in documents:
        text = (doc.extracted_text or "").strip()[:chars_per_doc]
        doc_sections.append(
            f"### Document ID: {doc.id} | Filename: {doc.original_filename}\n{text}"
        )

    context_str = "\n\n".join(doc_sections)

    # 1. Difficulty instruction
    if difficulty == "beginner":
        difficulty_instruction = (
            "Difficulty Level: BEGINNER.\n"
            "- Focus on fundamental definitions, core concepts, and direct recall of primary facts explicitly stated in the texts.\n"
            "- Questions should be straightforward, testing introductory comprehension."
        )
    elif difficulty == "advanced":
        difficulty_instruction = (
            "Difficulty Level: ADVANCED.\n"
            "- Focus on deep analysis, complex problem solving, subtle nuances, synthesis across concepts, and edge cases.\n"
            "- Questions should challenge the student with rigorous reasoning and detailed evaluation."
        )
    else:  # intermediate
        difficulty_instruction = (
            "Difficulty Level: INTERMEDIATE.\n"
            "- Focus on conceptual understanding, comparisons, practical applications, and cause-and-effect reasoning.\n"
            "- Questions should test whether the student understands how concepts function and relate."
        )

    # 2. Mode instruction
    if mode == "quiz":
        mode_instruction = (
            "Revision Mode: QUIZ ASSESSMENT.\n"
            "- Design questions as an objective knowledge check or exam-style assessment."
        )
    elif mode == "flashcards":
        mode_instruction = (
            "Revision Mode: FLASHCARD ACTIVE RECALL.\n"
            "- Design questions focused on prompt-and-recall memory pairs, key terms, and concise definitional answers."
        )
    else:  # practice
        mode_instruction = (
            "Revision Mode: PRACTICE STUDY.\n"
            "- Design questions for learning by doing, paired with rich explanatory feedback that guides the learner."
        )

    # 3. Question type instruction
    if question_type == "open_ended":
        type_instruction = (
            f"Generate exactly {question_count} OPEN-ENDED conceptual recall questions.\n"
            "- For each question, set 'question_type': 'open_ended'.\n"
            "- Set 'options': null.\n"
            "- In 'correct_answer', provide a concise, accurate model answer explaining the key concept."
        )
    elif question_type == "mixed":
        type_instruction = (
            f"Generate exactly {question_count} questions with a balanced combination of multiple-choice and open-ended questions.\n"
            "- For multiple choice questions, set 'question_type': 'multiple_choice', provide exactly 4 options in 'options', and set 'correct_answer' to one of the options verbatim.\n"
            "- For open-ended questions, set 'question_type': 'open_ended', set 'options': null, and provide a model answer in 'correct_answer'."
        )
    else:  # multiple_choice
        type_instruction = (
            f"Generate exactly {question_count} MULTIPLE-CHOICE questions.\n"
            "- For each question, set 'question_type': 'multiple_choice'.\n"
            "- Include an 'options' array containing exactly 4 plausible choices.\n"
            "- Set 'correct_answer' to match one of the 4 options verbatim."
        )

    # 4. Target topic focus and format instructions
    if topic_focus:
        safe_topic_raw = re.sub(r"[\r\n\x00-\x1f\x7f-\x9f]", "", topic_focus).strip()
        encoded_topic = json.dumps(safe_topic_raw)
        target_topic_instruction = (
            f"TARGET TOPIC FOCUS:\n"
            f"The learner specifically requested questions assessing the topic/concept: {encoded_topic}\n\n"
            f"GROUNDING & TARGETED PRACTICE CONSTRAINTS:\n"
            f"- Evaluate whether the provided document excerpts directly contain sufficient evidence to generate questions specifically assessing {encoded_topic} (or legitimate subtopics thereof).\n"
            f"- If the provided document excerpts DO NOT contain sufficient evidence for {encoded_topic}, you MUST explicitly confirm the topic is unsupported by returning 'topic_supported': false and an empty 'questions': [] array. DO NOT invent facts, hallucinate evidence, or generate questions on unrelated topics.\n"
            f"- If the excerpts DO contain sufficient evidence for {encoded_topic}, confirm 'topic_supported': true and create grounded questions.\n\n"
        )
        format_instruction = (
            "Respond with ONLY a JSON object — no markdown code fences, no commentary before or after.\n"
            "If the topic is supported by the excerpts, respond with this exact shape:\n"
            "{\n"
            '  "topic_supported": true,\n'
            f'  "topic": {encoded_topic},\n'
            '  "questions": [\n'
            "    {\n"
            '      "question_text": "What is the primary function of ...?",\n'
            '      "question_type": "multiple_choice",\n'
            '      "options": ["Option A", "Option B", "Option C", "Option D"],\n'
            '      "correct_answer": "Option A",\n'
            '      "explanation": "Option A is correct because...",\n'
            '      "source_document_id": "<exact_document_id_from_below>",\n'
            '      "evidence_snippet": "Verbatim quote from the document text proving this answer.",\n'
            '      "subtopic": "Concise subtopic name if applicable (or omit/null)"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "If the topic is NOT supported by the excerpts, respond with this exact shape:\n"
            "{\n"
            '  "topic_supported": false,\n'
            f'  "reason": "The document excerpts do not contain sufficient content for {encoded_topic}.",\n'
            '  "questions": []\n'
            "}"
        )
    else:
        target_topic_instruction = ""
        format_instruction = (
            "Respond with ONLY a JSON array of objects — no markdown code fences, no commentary before or after.\n"
            "Each JSON object must follow this exact shape:\n"
            "[\n"
            "  {\n"
            '    "question_text": "What is the primary function of ...?",\n'
            '    "question_type": "multiple_choice",\n'
            '    "options": ["Option A", "Option B", "Option C", "Option D"],\n'
            '    "correct_answer": "Option A",\n'
            '    "explanation": "Option A is correct because...",\n'
            '    "source_document_id": "<document_id_from_above>",\n'
            '    "evidence_snippet": "Verbatim quote from the document text proving this answer.",\n'
            '    "topic": "Photosynthesis Reactions"\n'
            "  }\n"
            "]"
        )

    return (
        "You are an expert tutor and exam creator. Based on the provided document excerpts below, "
        f"create exactly {question_count} high-quality revision questions for a student.\n\n"
        f"{target_topic_instruction}"
        f"{difficulty_instruction}\n\n"
        f"{mode_instruction}\n\n"
        f"{type_instruction}\n\n"
        "Grounding and Evidence Requirements:\n"
        "- Every question MUST be grounded strictly in the provided document excerpts.\n"
        "- In 'source_document_id', specify the exact Document ID where the supporting evidence appears.\n"
        "- In 'evidence_snippet', quote the exact sentence or passage from that document that proves the correct answer.\n"
        "- In 'explanation', explain clearly why the correct answer is right and why distractors are wrong (if multiple-choice).\n"
        f"{format_instruction}\n\n"
        f"Source Documents:\n{context_str}"
    )


def parse_and_validate_questions(
    raw_text: str,
    documents: list[Document],
    target_count: int,
    requested_type: str,
    difficulty: str,
    mode: str,
    topic_focus: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Parses raw LLM text into a validated list of revision question dictionaries.
    Ensures correct types, valid source document references, evidence snippets,
    and topic attribution.
    """
    data = extract_json(raw_text)

    docs_by_id = {doc.id: doc for doc in documents}
    default_doc = documents[0]

    if topic_focus:
        # TARGETED GENERATION PATH
        # 1. Reject malformed responses (must be a JSON dict, not bare list or primitive)
        if not isinstance(data, dict):
            if not data:
                raise UnsupportedTopicError(
                    f"The selected document(s) do not contain sufficient content for the requested topic '{topic_focus}'."
                )
            raise AIProviderError(
                "Targeted revision response must be a JSON object with explicit topic support confirmation."
            )

        # 2. Check explicit unsupported indicators
        # Even if questions array is non-empty, an explicit unsupported confirmation must be rejected
        topic_supported = data.get("topic_supported")
        if topic_supported is None and "supported" in data:
            topic_supported = data.get("supported")

        is_explicitly_unsupported = (
            topic_supported is False
            or (isinstance(topic_supported, str) and topic_supported.lower() == "false")
            or data.get("unsupported") is True
            or (isinstance(data.get("unsupported"), str) and data.get("unsupported").lower() == "true")
            or data.get("error") == "unsupported_topic"
        )
        if is_explicitly_unsupported:
            raise UnsupportedTopicError(
                f"The selected document(s) do not contain sufficient content for the requested topic '{topic_focus}'."
            )

        # 3. For targeted generation to succeed, topic_supported must be explicitly true
        is_explicitly_supported = (
            topic_supported is True
            or (isinstance(topic_supported, str) and topic_supported.lower() == "true")
        )
        if not is_explicitly_supported:
            raise AIProviderError(
                "Targeted revision response must explicitly confirm 'topic_supported': true."
            )

        # 4. Extract questions list and validate non-emptiness
        raw_items = data.get("questions")
        if not isinstance(raw_items, list):
            raise AIProviderError(
                "Targeted revision response must contain a 'questions' list."
            )

        if not raw_items:
            raise AIProviderError(
                "Targeted revision response indicated topic was supported but provided an empty questions list."
            )

        items = raw_items

    else:
        # ORDINARY GENERATION PATH (unchanged behavior)
        items: list[Any] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "questions" in data and isinstance(data["questions"], list):
                items = data["questions"]
            elif "items" in data and isinstance(data["items"], list):
                items = data["items"]
            elif not data:
                items = []
            else:
                items = [data]
        else:
            raise AIProviderError("AI did not return a valid list of questions.")

        if not items:
            raise AIProviderError("AI response contained an empty questions list.")

    valid_questions: list[dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        q_text = str(item.get("question_text") or item.get("question") or "").strip()
        if not q_text:
            continue

        # Resolve question type
        raw_type = str(item.get("question_type") or "").strip().lower()
        if requested_type == "multiple_choice":
            q_type = "multiple_choice"
        elif requested_type == "open_ended":
            q_type = "open_ended"
        elif raw_type in ("multiple_choice", "mcq"):
            q_type = "multiple_choice"
        elif raw_type in ("open_ended", "open", "free_response"):
            q_type = "open_ended"
        else:
            q_type = "multiple_choice" if isinstance(item.get("options"), list) and len(item.get("options")) >= 2 else "open_ended"

        # Resolve options and correct answer
        raw_options = item.get("options")
        correct_answer = str(item.get("correct_answer") or item.get("answer") or "").strip()

        if q_type == "multiple_choice":
            if not isinstance(raw_options, list) or len(raw_options) < 2:
                if requested_type == "multiple_choice":
                    logger.warning("MCQ item missing options; attempting fallback.")
                    continue
                q_type = "open_ended"
                options = None
            else:
                options = [str(opt).strip() for opt in raw_options if str(opt).strip()]
                if len(options) < 2:
                    continue

                raw_idx = item.get("correct_answer_index")
                if raw_idx is not None and isinstance(raw_idx, int) and 0 <= raw_idx < len(options):
                    correct_answer = options[raw_idx]
                elif correct_answer.isdigit() and 0 <= int(correct_answer) < len(options):
                    correct_answer = options[int(correct_answer)]
                elif correct_answer not in options:
                    matched = False
                    for opt in options:
                        if opt.lower() == correct_answer.lower():
                            correct_answer = opt
                            matched = True
                            break
                    if not matched and options:
                        correct_answer = options[0]
        else:
            options = None
            if not correct_answer:
                correct_answer = "Model answer not provided."

        explanation = str(item.get("explanation") or "").strip() or None

        # Resolve source document ID
        raw_doc_id = str(item.get("source_document_id") or "").strip()
        matched_doc = docs_by_id.get(raw_doc_id)
        if matched_doc is None:
            if topic_focus:
                logger.warning(
                    f"Targeted question cited unrecognized source_document_id '{raw_doc_id}'; rejecting question."
                )
                continue
            matched_doc = default_doc

        source_doc_id = matched_doc.id

        # Resolve evidence snippet
        evidence = str(
            item.get("evidence_snippet")
            or item.get("evidence")
            or item.get("source_quote")
            or ""
        ).strip()

        if topic_focus:
            # Targeted generation: strictly require non-empty verifiable evidence
            if not evidence:
                logger.warning("Targeted question missing evidence snippet; rejecting question.")
                continue
            if not verify_evidence_in_document(evidence, matched_doc.extracted_text):
                logger.warning(
                    "Targeted question evidence snippet could not be verified in referenced document; rejecting question."
                )
                continue
        else:
            # Ordinary generation: fallback to representative excerpt from matched document
            if not evidence:
                doc_text = (matched_doc.extracted_text or "").strip()
                evidence = doc_text[:250] if doc_text else f"Excerpt from {matched_doc.original_filename}"

        # Resolve evidence metadata & topic attribution
        evidence_meta: dict[str, Any] = {
            "source_document_id": matched_doc.id,
            "document_title": matched_doc.original_filename,
            "difficulty": difficulty,
            "mode": mode,
        }

        if topic_focus:
            norm_focus = clean_and_normalize_topic(topic_focus)
            if norm_focus:
                evidence_meta["topic"] = norm_focus[0]
                evidence_meta["topic_key"] = norm_focus[1]
            else:
                evidence_meta["topic"] = topic_focus.strip()
                evidence_meta["topic_key"] = topic_focus.strip().casefold()

            sub_item = item.get("subtopic") or item.get("topic")
            sub_norm = clean_and_normalize_topic(sub_item)
            if sub_norm and sub_norm[1] != evidence_meta["topic_key"]:
                evidence_meta["subtopic"] = sub_norm[0]
                evidence_meta["subtopic_key"] = sub_norm[1]
        else:
            item_topic = item.get("topic") or item.get("subtopic")
            norm_topic = clean_and_normalize_topic(item_topic)
            if norm_topic:
                evidence_meta["topic"] = norm_topic[0]
                evidence_meta["topic_key"] = norm_topic[1]

        valid_questions.append(
            {
                "question_text": q_text,
                "question_type": q_type,
                "options": options,
                "correct_answer": correct_answer,
                "explanation": explanation,
                "source_document_id": source_doc_id,
                "source_chunk_id": None,
                "evidence_snippet": evidence,
                "evidence_metadata": evidence_meta,
            }
        )

        if len(valid_questions) >= target_count:
            break

    if not valid_questions:
        if topic_focus:
            raise AIProviderError(
                f"AI did not produce valid, grounded questions for topic '{topic_focus}' with verifiable document evidence."
            )
        raise AIProviderError("AI did not produce any valid revision questions.")

    return valid_questions


async def generate_revision_session(
    db: Session,
    identity: Identity,
    documents: list[Document],
    payload: RevisionSessionCreateRequest,
    ai_provider: AIProvider,
) -> RevisionSession:
    """
    Coordinates question generation across documents and persists the session,
    document associations, and generated questions in an atomic transaction.
    """
    # 1. Determine title
    if payload.title:
        title = payload.title
    else:
        mode_suffix = payload.mode.capitalize()
        if len(documents) == 1:
            title = f"{documents[0].original_filename} {mode_suffix}"
        else:
            title = f"{documents[0].original_filename} + {len(documents) - 1} more ({mode_suffix})"

    # 2. Build prompt and generate
    prompt = build_revision_prompt(
        documents=documents,
        question_count=payload.question_count,
        difficulty=payload.difficulty,
        mode=payload.mode,
        question_type=payload.question_type,
        topic_focus=payload.topic_focus,
    )

    raw_text = await ai_provider.generate_text(prompt)

    # 3. Parse and validate questions
    parsed_questions = parse_and_validate_questions(
        raw_text=raw_text,
        documents=documents,
        target_count=payload.question_count,
        requested_type=payload.question_type,
        difficulty=payload.difficulty,
        mode=payload.mode,
        topic_focus=payload.topic_focus,
    )

    # 4. Atomically persist session, associations, and questions
    try:
        session = RevisionSession(
            title=title,
            owner_type=identity.type.value,
            owner_id=identity.id,
            status="in_progress",
            config={
                "difficulty": payload.difficulty,
                "mode": payload.mode,
                "question_type": payload.question_type,
                "question_count": payload.question_count,
                "topic_focus": payload.topic_focus,
            },
            total_questions=len(parsed_questions),
            score=None,
            completed_at=None,
        )
        ownership_service.assign_owner(session, identity)
        db.add(session)
        db.flush()

        for doc in documents:
            rsd = RevisionSessionDocument(
                session_id=session.id,
                document_id=doc.id,
            )
            db.add(rsd)

        for idx, q_data in enumerate(parsed_questions, start=1):
            question = RevisionQuestion(
                session_id=session.id,
                position=idx,
                question_type=q_data["question_type"],
                question_text=q_data["question_text"],
                options=q_data["options"],
                correct_answer=q_data["correct_answer"],
                explanation=q_data["explanation"],
                source_document_id=q_data["source_document_id"],
                source_chunk_id=q_data.get("source_chunk_id"),
                evidence_snippet=q_data["evidence_snippet"],
                evidence_metadata=q_data["evidence_metadata"],
            )
            db.add(question)

        db.commit()
        db.refresh(session)
        return session
    except (UnsupportedTopicError, AIProviderError):
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to persist revision session: {exc}", exc_info=True)
        raise
