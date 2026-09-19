import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk
from app.schemas.learn import LearnContributingDocument, LearnExcludedDocument
from app.schemas.visualize import (
    MAX_EDGES_PER_DEPTH,
    MAX_NODES_PER_DEPTH,
    VisualizeConceptEdge,
    VisualizeConceptNode,
    VisualizeDepth,
    VisualizeGraphResponse,
    VisualizeProvenance,
    VisualizeSourceCitation,
)
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.structured_output import extract_json
from app.services.rag.embedding_service import index_document
from app.services.rag.retrieval_service import retrieve_relevant_chunks

logger = logging.getLogger(__name__)

MAX_VISUALIZE_TOTAL_CHARS = 16000


def build_visualize_prompt(
    contributing_documents: list[Document],
    depth: VisualizeDepth = "standard",
) -> tuple[str, str]:
    """
    Constructs bounded system and user prompts to generate a structured concept graph.
    Caps total document excerpt length across 1 to 10 documents.
    """
    max_nodes = MAX_NODES_PER_DEPTH.get(depth, 16)
    max_edges = MAX_EDGES_PER_DEPTH.get(depth, 26)

    num_docs = max(1, len(contributing_documents))
    chars_per_doc = max(1000, MAX_VISUALIZE_TOTAL_CHARS // num_docs)

    doc_excerpts = []
    for doc in contributing_documents:
        text = (doc.extracted_text or "").strip()
        truncated_text = text[:chars_per_doc]
        doc_excerpts.append(
            f"=== DOCUMENT ID: {doc.id} | TITLE: {doc.original_filename} ===\n{truncated_text}\n"
        )

    context_block = "\n".join(doc_excerpts)

    system_prompt = (
        "You are an expert educational knowledge graph and concept visualizer. "
        "Your task is to analyze the provided study documents and construct a clear, coherent concept network graph. "
        "Strict Requirements:\n"
        f"1. Generate between 6 and {max_nodes} distinct concept nodes.\n"
        f"2. Generate between 5 and {max_edges} directed relationship edges connecting those nodes.\n"
        "3. Every edge must connect a valid source node id to a valid target node id.\n"
        "4. Assign each concept a clear category (e.g. 'Core Theory', 'Algorithm', 'Architecture', 'Component', 'Methodology').\n"
        "5. Categorize each concept's importance on a scale from 1.0 to 3.0 (higher = more central).\n"
        "6. List the contributing document ID(s) where each concept appears.\n"
        "7. Give each edge an informative semantic relationship label (e.g. 'relies on', 'implements', 'part of', 'contrasts with', 'coordinates').\n"
        "8. Return strictly valid JSON adhering to the specified schema with no surrounding commentary.\n"
    )

    user_prompt = (
        f"Generate a concept network graph for the following material at '{depth}' depth.\n\n"
        f"Documents:\n{context_block}\n\n"
        "Produce a JSON object with this exact schema:\n"
        "{\n"
        '  "title": "Comprehensive Title for the Concept Graph",\n'
        '  "summary": "Brief 1-2 sentence overview of the conceptual domain covered.",\n'
        '  "nodes": [\n'
        "    {\n"
        '      "id": "concept_1",\n'
        '      "label": "Concept Name",\n'
        '      "summary": "Concise 1-2 sentence definition/explanation of this concept grounded in the text.",\n'
        '      "category": "Category Name",\n'
        '      "document_ids": ["matching-doc-id"],\n'
        '      "importance": 1.5\n'
        "    }\n"
        "  ],\n"
        '  "edges": [\n'
        "    {\n"
        '      "id": "edge_1",\n'
        '      "source": "concept_1",\n'
        '      "target": "concept_2",\n'
        '      "label": "relationship predicate"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )

    return system_prompt, user_prompt


async def generate_visualize_graph(
    requested_document_ids: list[str],
    contributing_documents: list[Document],
    excluded_documents: list[tuple[Document, str]],
    db: Session,
    ai_provider: AIProvider,
    embedding_provider: EmbeddingProvider,
    depth: VisualizeDepth = "standard",
) -> VisualizeGraphResponse:
    """
    Generates a validated concept graph across 1 to 10 documents with bounded node/edge counts
    and grounded source citations from document chunks.
    """
    system_prompt, user_prompt = build_visualize_prompt(contributing_documents, depth)

    try:
        raw_response = await ai_provider.generate_content(
            system_prompt=system_prompt,
            prompt=user_prompt,
        )
    except Exception as exc:
        logger.error(f"Visualize graph generation failed at provider: {exc}")
        raise AIProviderError(f"Concept graph generation failed: {exc}") from exc

    try:
        data = extract_json(raw_response)
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object from provider.")
    except Exception as exc:
        logger.error(f"Failed to parse concept graph JSON: {exc}. Raw response: {raw_response[:500]}")
        raise AIProviderError(f"Malformed concept graph output from AI provider: {exc}") from exc

    # Enforce graph size bounds per depth
    max_nodes = MAX_NODES_PER_DEPTH.get(depth, 16)
    max_edges = MAX_EDGES_PER_DEPTH.get(depth, 26)

    raw_nodes = data.get("nodes") or []
    raw_edges = data.get("edges") or []

    if not isinstance(raw_nodes, list) or len(raw_nodes) == 0:
        raise AIProviderError("AI provider generated an empty set of concept nodes.")

    # Validate and bound nodes
    bounded_nodes: list[VisualizeConceptNode] = []
    seen_node_ids: set[str] = set()

    for idx, raw_node in enumerate(raw_nodes[:max_nodes]):
        if not isinstance(raw_node, dict):
            continue
        node_id = str(raw_node.get("id") or f"node_{idx+1}").strip()
        label = str(raw_node.get("label") or f"Concept {idx+1}").strip()
        summary = str(raw_node.get("summary") or "").strip()
        category = str(raw_node.get("category") or "General").strip()

        doc_ids = raw_node.get("document_ids") or []
        if not isinstance(doc_ids, list):
            doc_ids = [str(doc_ids)]
        # Filter doc_ids to requested documents
        valid_doc_ids = [d for d in doc_ids if d in requested_document_ids]
        if not valid_doc_ids and contributing_documents:
            valid_doc_ids = [contributing_documents[0].id]

        try:
            importance = float(raw_node.get("importance", 1.0))
            importance = max(0.5, min(3.0, importance))
        except (ValueError, TypeError):
            importance = 1.0

        if node_id not in seen_node_ids:
            seen_node_ids.add(node_id)
            bounded_nodes.append(
                VisualizeConceptNode(
                    id=node_id,
                    label=label,
                    summary=summary or label,
                    category=category,
                    document_ids=valid_doc_ids,
                    importance=importance,
                )
            )

    if not bounded_nodes:
        raise AIProviderError("Could not extract valid concept nodes from provider response.")

    # Validate and bound edges
    bounded_edges: list[VisualizeConceptEdge] = []
    seen_edge_ids: set[str] = set()

    for idx, raw_edge in enumerate(raw_edges):
        if len(bounded_edges) >= max_edges:
            break
        if not isinstance(raw_edge, dict):
            continue
        edge_id = str(raw_edge.get("id") or f"edge_{idx+1}").strip()
        source = str(raw_edge.get("source") or "").strip()
        target = str(raw_edge.get("target") or "").strip()
        label = str(raw_edge.get("label") or "relates to").strip()

        # Both source and target must exist in bounded_nodes
        if source in seen_node_ids and target in seen_node_ids and source != target:
            if edge_id not in seen_edge_ids:
                seen_edge_ids.add(edge_id)
                bounded_edges.append(
                    VisualizeConceptEdge(
                        id=edge_id,
                        source=source,
                        target=target,
                        label=label,
                    )
                )

    # Ensure documents have chunks for citations
    doc_ids_to_search = [doc.id for doc in contributing_documents]
    for doc in contributing_documents:
        has_chunks = (
            db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).first() is not None
        )
        if not has_chunks:
            try:
                await index_document(doc, db, embedding_provider)
            except Exception as idx_err:
                logger.warning(f"Indexing document {doc.id} for citations failed: {idx_err}")

    # Generate source citations for top concept nodes
    citations: list[VisualizeSourceCitation] = []
    doc_lookup = {doc.id: doc.original_filename for doc in contributing_documents}

    # Retrieve citations for top concepts (up to 4 key nodes)
    top_nodes = sorted(bounded_nodes, key=lambda n: n.importance, reverse=True)[:4]
    for node in top_nodes:
        try:
            retrieval_result = await retrieve_relevant_chunks(
                document_ids=doc_ids_to_search,
                query=f"{node.label}: {node.summary}",
                db=db,
                embedding_provider=embedding_provider,
                top_k=2,
            )
            for scored in retrieval_result.chunks:
                citations.append(
                    VisualizeSourceCitation(
                        node_id=node.id,
                        document_id=scored.chunk.document_id,
                        document_name=doc_lookup.get(scored.chunk.document_id, "Document"),
                        chunk_id=scored.chunk.id,
                        chunk_index=scored.chunk.chunk_index,
                        content=scored.chunk.content[:400],
                        score=round(scored.score, 3),
                    )
                )
        except Exception as rag_err:
            logger.warning(f"RAG retrieval for node {node.id} citation failed: {rag_err}")

    # Build provenance
    contributing_provenance = [
        LearnContributingDocument(
            id=doc.id,
            original_filename=doc.original_filename,
            character_count=len(doc.extracted_text or ""),
        )
        for doc in contributing_documents
    ]
    excluded_provenance = [
        LearnExcludedDocument(
            id=doc.id,
            original_filename=doc.original_filename,
            reason=reason,
        )
        for doc, reason in excluded_documents
    ]

    provenance = VisualizeProvenance(
        document_ids=requested_document_ids,
        contributing_documents=contributing_provenance,
        excluded_documents=excluded_provenance,
        total_nodes=len(bounded_nodes),
        total_edges=len(bounded_edges),
        depth=depth,
    )

    return VisualizeGraphResponse(
        document_ids=requested_document_ids,
        title=str(data.get("title") or "Concept Network Graph").strip(),
        summary=str(data.get("summary") or "").strip(),
        nodes=bounded_nodes,
        edges=bounded_edges,
        citations=citations,
        grounding_metadata=provenance,
    )
