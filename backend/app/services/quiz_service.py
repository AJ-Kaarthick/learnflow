from sqlalchemy.orm import Session

from app.db.models import Document, QuizQuestion
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.structured_output import parse_json_array

MAX_CHARACTERS_FOR_PROMPT = 15000
DEFAULT_QUESTION_COUNT = 10
OPTIONS_PER_QUESTION = 4


def build_quiz_prompt(document_text: str, count: int) -> str:
    truncated = document_text[:MAX_CHARACTERS_FOR_PROMPT]
    return (
        f"Create exactly {count} multiple-choice quiz questions for a "
        "student studying the document below. Each question must have "
        f"exactly {OPTIONS_PER_QUESTION} answer options, with exactly one "
        "correct answer.\n\n"
        "Respond with ONLY a JSON array — no markdown code fences, no "
        "commentary before or after it. Each item must look exactly like "
        'this: {"question": "...", "options": ["...", "...", "...", "..."], '
        '"correct_answer_index": 0}\n\n'
        "correct_answer_index is the zero-based index into options of the "
        "correct choice.\n\n"
        f"Document:\n{truncated}"
    )


def _validate_quiz_question(item: dict) -> None:
    """
    parse_json_array already confirmed each item has 'question',
    'options', and 'correct_answer_index' present — this checks the
    parts that are specific to what a quiz question actually needs,
    which a generic structured-output parser has no business knowing.
    """
    options = item["options"]
    correct_index = item["correct_answer_index"]

    if not isinstance(options, list) or len(options) < 2:
        raise AIProviderError("Each quiz question needs a list of at least 2 options.")
    if not isinstance(correct_index, int) or not (0 <= correct_index < len(options)):
        raise AIProviderError("correct_answer_index must be a valid index into options.")


async def generate_quiz_for_document(
    document: Document,
    db: Session,
    provider: AIProvider,
    count: int = DEFAULT_QUESTION_COUNT,
) -> list[QuizQuestion]:
    existing = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.document_id == document.id)
        .order_by(QuizQuestion.position)
        .all()
    )
    if existing:
        return existing

    prompt = build_quiz_prompt(document.extracted_text or "", count)
    raw_text = await provider.generate_text(prompt)
    questions_data = parse_json_array(
        raw_text, required_keys={"question", "options", "correct_answer_index"}
    )
    for item in questions_data:
        _validate_quiz_question(item)

    quiz_questions = [
        QuizQuestion(
            document_id=document.id,
            question=item["question"],
            options=item["options"],
            correct_answer_index=item["correct_answer_index"],
            position=index,
        )
        for index, item in enumerate(questions_data)
    ]
    db.add_all(quiz_questions)
    db.commit()
    for question in quiz_questions:
        db.refresh(question)
    return quiz_questions
