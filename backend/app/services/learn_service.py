from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk
from app.schemas.learn import (
    LearnContributingDocument,
    LearnExcludedDocument,
    LearnKeyTerm,
    LearnOutlineProvenance,
    LearnOutlineResponse,
    LearnSourceCitation,
    LearnSubtopic,
    LearnTopic,
    LearnTopicGroundingMetadata,
    LearnTopicResponse,
)
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.structured_output import extract_json
from app.services.rag.embedding_service import index_document
from app.services.rag.retrieval_service import ScoredChunk, retrieve_relevant_chunks

# Bounded context limit for outline generation across all selected documents.
# Guarantees the prompt stays safely within model context limits for 1-10 documents.
MAX_OUTLINE_TOTAL_CHARS = 16000


def build_outline_prompt(documents: list[Document], depth: str = "standard") -> str:
    """
    Builds the bounded-context prompt for curriculum / learning outline generation.
    Distributes available character budget proportionally across the selected documents.
    """
    if not documents:
        raise ValueError("At least one document is required to build an outline prompt.")

    chars_per_doc = max(1000, MAX_OUTLINE_TOTAL_CHARS // len(documents))

    doc_sections = []
    for doc in documents:
        text = (doc.extracted_text or "").strip()[:chars_per_doc]
        doc_sections.append(f"### Document: {doc.original_filename}\n{text}")

    context_str = "\n\n".join(doc_sections)

    if depth == "overview":
        depth_instruction = (
            "Design a high-level overview curriculum focusing on essential foundational "
            "concepts, big-picture themes, and core principles."
        )
    elif depth == "in-depth":
        depth_instruction = (
            "Design an extensive, rigorous curriculum with comprehensive topic coverage, "
            "granular subtopics, and detailed learning objectives."
        )
    else:  # standard
        depth_instruction = (
            "Design a balanced, structured curriculum covering main concepts, key subtopics, "
            "and practical learning objectives."
        )

    return (
        "You are an expert curriculum designer. Based on the document excerpts provided below, "
        "create a structured study outline / curriculum for a student.\n\n"
        f"{depth_instruction}\n\n"
        "Guidelines:\n"
        "- Represent the documents as a coherent learning journey, not arbitrary extracted headers.\n"
        "- Provide stable, clean string identifiers for topics ('topic-1', 'topic-2', etc.) and "
        "subtopics ('topic-1-1', 'topic-1-2', etc.).\n"
        "- Include actionable learning objectives for the curriculum and for each topic.\n\n"
        "Respond with ONLY a JSON object — no markdown code fences, no commentary before or after it.\n"
        "The JSON object must look exactly like this shape:\n"
        "{\n"
        '  "title": "Curriculum Title",\n'
        '  "description": "Short overview of what the student will learn",\n'
        '  "learning_objectives": ["Objective 1", "Objective 2"],\n'
        '  "topics": [\n'
        "    {\n"
        '      "id": "topic-1",\n'
        '      "title": "First Topic Title",\n'
        '      "description": "Brief summary of what is covered in this topic",\n'
        '      "learning_objectives": ["Topic Objective 1"],\n'
        '      "subtopics": [\n'
        "        {\n"
        '          "id": "topic-1-1",\n'
        '          "title": "Subtopic Title",\n'
        '          "summary": "Brief summary of this subtopic"\n'
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Source Documents:\n{context_str}"
    )


async def generate_learn_outline(
    requested_document_ids: list[str],
    contributing_documents: list[Document],
    excluded_documents: list[tuple[Document, str]],
    ai_provider: AIProvider,
    depth: str = "standard",
) -> LearnOutlineResponse:
    """
    Generates a structured learning curriculum across the contributing documents.
    """
    prompt = build_outline_prompt(contributing_documents, depth)
    raw_text = await ai_provider.generate_text(prompt)

    try:
        data = extract_json(raw_text)
    except AIProviderError:
        raise
    except Exception as error:
        raise AIProviderError(f"Could not parse outline JSON: {error}") from error

    if not isinstance(data, dict):
        raise AIProviderError("Expected a JSON object for curriculum outline.")

    raw_topics = data.get("topics")
    if not isinstance(raw_topics, list):
        raise AIProviderError("Curriculum outline must include a 'topics' list.")

    topics: list[LearnTopic] = []
    for idx, raw_topic in enumerate(raw_topics):
        if not isinstance(raw_topic, dict):
            continue
        topic_id = str(raw_topic.get("id") or f"topic-{idx + 1}")
        topic_title = str(raw_topic.get("title") or f"Topic {idx + 1}").strip()
        topic_desc = str(raw_topic.get("description") or "").strip()
        raw_objs = raw_topic.get("learning_objectives")
        learning_objs = [str(o) for o in raw_objs if str(o).strip()] if isinstance(raw_objs, list) else []

        raw_subtopics = raw_topic.get("subtopics")
        subtopics: list[LearnSubtopic] = []
        if isinstance(raw_subtopics, list):
            for s_idx, raw_sub in enumerate(raw_subtopics):
                if isinstance(raw_sub, dict):
                    sub_id = str(raw_sub.get("id") or f"{topic_id}-{s_idx + 1}")
                    sub_title = str(raw_sub.get("title") or f"Subtopic {s_idx + 1}").strip()
                    sub_summary = str(raw_sub.get("summary") or "").strip() or None
                    subtopics.append(LearnSubtopic(id=sub_id, title=sub_title, summary=sub_summary))

        topics.append(
            LearnTopic(
                id=topic_id,
                title=topic_title,
                description=topic_desc,
                learning_objectives=learning_objs,
                subtopics=subtopics,
            )
        )

    if not topics:
        raise AIProviderError("AI did not produce any valid topics in the outline.")

    title = str(data.get("title") or "Curriculum Outline").strip()
    description = str(data.get("description") or "Curriculum generated for study.").strip()
    raw_global_objs = data.get("learning_objectives")
    global_objs = (
        [str(o) for o in raw_global_objs if str(o).strip()]
        if isinstance(raw_global_objs, list)
        else []
    )

    provenance = LearnOutlineProvenance(
        document_ids=requested_document_ids,
        contributing_documents=[
            LearnContributingDocument(
                id=doc.id,
                original_filename=doc.original_filename,
                character_count=len(doc.extracted_text or ""),
            )
            for doc in contributing_documents
        ],
        excluded_documents=[
            LearnExcludedDocument(
                id=doc.id,
                original_filename=doc.original_filename,
                reason=reason,
            )
            for doc, reason in excluded_documents
        ],
        total_topics=len(topics),
        depth=depth,
    )

    return LearnOutlineResponse(
        document_ids=requested_document_ids,
        title=title,
        description=description,
        topics=topics,
        learning_objectives=global_objs,
        grounding_metadata=provenance,
    )


def build_topic_prompt(
    topic_title: str,
    chunks: list[ScoredChunk],
    documents_by_id: dict[str, Document],
    action: Optional[str] = None,
    depth: str = "standard",
    parent_topic_title: Optional[str] = None,
    context: Optional[str] = None,
) -> str:
    """
    Builds the grounded prompt for topic deep dive generation and contextual actions.
    """
    topic_heading = (
        f"{parent_topic_title} > {topic_title}" if parent_topic_title else topic_title
    )

    if action == "simplify":
        action_instruction = (
            "Explain this topic in simple, intuitive terms suitable for a beginner or student "
            "seeking clarity. Avoid unnecessary jargon or define it clearly when essential. "
            "Preserve factual grounding strictly in the provided excerpts."
        )
    elif action == "elaborate":
        action_instruction = (
            "Provide a deep, detailed, and comprehensive explanation of this topic. "
            "Explore technical nuances, underlying mechanics, and specific details grounded "
            "in the source excerpts."
        )
    elif action == "example":
        action_instruction = (
            "Provide a concrete, realistic example illustrating this topic clearly. "
            "Demonstrate how the concept works in practice while ensuring the principles and "
            "mechanics remain strictly consistent with the source excerpts."
        )
    else:
        action_instruction = (
            "Provide a clear, engaging, and thorough explanation of this topic grounded "
            "strictly in the source material."
        )

    if depth == "overview":
        depth_instruction = "Keep the explanation concise and focused on high-level core principles."
    elif depth == "in-depth":
        depth_instruction = (
            "Provide an extensive and thorough explanation covering detailed aspects and implications."
        )
    else:  # standard
        depth_instruction = "Provide a balanced, thorough explanation with key concepts and details."

    refinement_block = ""
    if context:
        refinement_block = (
            f"Previous Explanation:\n{context}\n\n"
            "Apply the requested action to adapt, expand, or simplify this existing explanation "
            "while maintaining strict source grounding.\n\n"
        )

    excerpts_list = []
    for scored in chunks:
        doc = documents_by_id.get(scored.chunk.document_id)
        doc_name = doc.original_filename if doc else "Document"
        excerpts_list.append(
            f"[Source: {doc_name} (Chunk {scored.chunk.chunk_index})]:\n{scored.chunk.content}"
        )
    excerpts_str = "\n\n".join(excerpts_list) if excerpts_list else "No excerpts available."

    return (
        f"You are a knowledgeable tutor explaining the topic: '{topic_heading}'.\n\n"
        f"{action_instruction}\n"
        f"{depth_instruction}\n\n"
        f"{refinement_block}"
        "Grounding Rules:\n"
        "- Base your explanation ONLY on the facts directly mentioned in the source excerpts below.\n"
        "- Do NOT assume, extrapolate, or invent details not directly supported by the text.\n"
        "- If the excerpts do not contain enough information to cover an aspect, briefly state that "
        "the source material does not cover it.\n\n"
        "Respond with ONLY a JSON object — no markdown code fences, no commentary before or after it.\n"
        "The JSON object must follow this structure:\n"
        "{\n"
        '  "explanation": "Detailed explanation in Markdown format...",\n'
        '  "key_terms": [\n'
        '    {"term": "Term Name", "definition": "Clear concise definition"}\n'
        "  ],\n"
        '  "key_takeaways": [\n'
        '    "First key takeaway",\n'
        '    "Second key takeaway"\n'
        "  ]\n"
        "}\n\n"
        f"Source Excerpts:\n{excerpts_str}"
    )


async def generate_learn_topic(
    requested_document_ids: list[str],
    readable_documents: list[Document],
    topic_id: str,
    topic_title: str,
    db: Session,
    ai_provider: AIProvider,
    embedding_provider: EmbeddingProvider,
    action: Optional[str] = None,
    depth: str = "standard",
    parent_topic_title: Optional[str] = None,
    context: Optional[str] = None,
) -> LearnTopicResponse:
    """
    Generates a RAG-grounded topic explanation with citations, key terms, and key takeaways.
    """
    # 1. Ensure indexing for any readable document that has not yet been indexed.
    # If chunks already exist, retrieve directly without re-indexing.
    for doc in readable_documents:
        has_chunks = (
            db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).first()
            is not None
        )
        if not has_chunks:
            await index_document(doc, db, embedding_provider)

    # 2. Retrieve relevant chunks across readable documents
    search_query = f"{parent_topic_title}: {topic_title}" if parent_topic_title else topic_title
    retrieval_result = await retrieve_relevant_chunks(
        document_ids=[doc.id for doc in readable_documents],
        query=search_query,
        db=db,
        embedding_provider=embedding_provider,
    )

    documents_by_id = {doc.id: doc for doc in readable_documents}

    # 3. Construct prompt and generate
    prompt = build_topic_prompt(
        topic_title=topic_title,
        chunks=retrieval_result.chunks,
        documents_by_id=documents_by_id,
        action=action,
        depth=depth,
        parent_topic_title=parent_topic_title,
        context=context,
    )

    raw_text = await ai_provider.generate_text(prompt)

    try:
        data = extract_json(raw_text)
    except AIProviderError:
        raise
    except Exception as error:
        raise AIProviderError(f"Could not parse topic JSON: {error}") from error

    if isinstance(data, dict):
        explanation = str(data.get("explanation") or "").strip()
        raw_terms = data.get("key_terms")
        key_terms: list[LearnKeyTerm] = []
        if isinstance(raw_terms, list):
            for t in raw_terms:
                if isinstance(t, dict) and t.get("term"):
                    key_terms.append(
                        LearnKeyTerm(
                            term=str(t["term"]).strip(),
                            definition=str(t.get("definition") or "").strip(),
                        )
                    )
        raw_takeaways = data.get("key_takeaways")
        key_takeaways: list[str] = []
        if isinstance(raw_takeaways, list):
            key_takeaways = [str(k).strip() for k in raw_takeaways if str(k).strip()]
    elif isinstance(data, str):
        explanation = data.strip()
        key_terms = []
        key_takeaways = []
    else:
        raise AIProviderError("Expected a JSON object with 'explanation' for topic.")

    if not explanation:
        raise AIProviderError("AI did not produce an explanation for this topic.")

    # 4. Map sources from retrieved chunks
    sources: list[LearnSourceCitation] = []
    for scored in retrieval_result.chunks:
        doc = documents_by_id.get(scored.chunk.document_id)
        doc_name = doc.original_filename if doc else "Document"
        sources.append(
            LearnSourceCitation(
                document_id=scored.chunk.document_id,
                document_name=doc_name,
                chunk_id=scored.chunk.id,
                chunk_index=scored.chunk.chunk_index,
                content=scored.chunk.content,
                score=scored.score,
            )
        )

    grounding_metadata = LearnTopicGroundingMetadata(
        grounded=len(sources) > 0,
        retrieved_chunks_count=len(sources),
        document_ids=requested_document_ids,
        depth=depth,
        action=action,
    )

    return LearnTopicResponse(
        topic_id=topic_id,
        topic_title=topic_title,
        action=action,
        depth=depth,
        explanation=explanation,
        key_terms=key_terms,
        key_takeaways=key_takeaways,
        sources=sources,
        grounding_metadata=grounding_metadata,
    )
