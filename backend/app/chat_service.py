import asyncio
from time import perf_counter
from uuid import UUID

from app.config import Settings
from app.database import Database
from app.models import ChatResponse, Citation, ExecutionInfo
from app.openai_service import OpenAIService


class ChatService:
    def __init__(
        self, database: Database, openai_service: OpenAIService, settings: Settings
    ) -> None:
        self.database = database
        self.openai = openai_service
        self.settings = settings

    async def ask(self, question: str, branch_id: str, *, log: bool = True) -> ChatResponse:
        started = perf_counter()
        query_embedding = (await self.openai.embed([question]))[0]
        retrieved = await asyncio.to_thread(
            self.database.search,
            question,
            query_embedding,
            branch_id,
            self.settings.retrieval_candidates,
        )

        retrieval_done = perf_counter()

        if (
            not retrieved
            or retrieved[0].semantic_score < self.settings.retrieval_min_semantic_score
        ):
            draft_answer = "目前的營運文件不足以回答這個問題。"
            response = ChatResponse(
                answer=draft_answer,
                abstained=True,
                reason="沒有找到相關度足夠的內部文件。",
                citations=[],
                execution=ExecutionInfo(
                    latency_ms=round((perf_counter() - started) * 1000),
                    retrieval_ms=round((retrieval_done - started) * 1000),
                    generation_ms=0,
                    input_tokens=0,
                    output_tokens=0,
                    retrieved_chunks=len(retrieved),
                ),
            )
            if log:
                response.trace_id = await self._log(question, branch_id, response, retrieved)
            return response

        context_chunks = retrieved[: self.settings.generation_context_chunks]
        draft, input_tokens, output_tokens = await self.openai.answer(
            question, branch_id, context_chunks
        )
        generation_done = perf_counter()
        chunks_by_id = {chunk.id: chunk for chunk in context_chunks}
        citations: list[Citation] = []
        seen: set[UUID] = set()
        for model_citation in draft.citations:
            chunk = chunks_by_id.get(model_citation.chunk_id)
            if not chunk or chunk.id in seen:
                continue
            seen.add(chunk.id)
            citations.append(
                Citation(
                    citation_number=len(citations) + 1,
                    source_id=chunk.source_id,
                    chunk_id=chunk.id,
                    statement=model_citation.statement,
                    document_title=chunk.document_title,
                    section=chunk.section,
                    page_number=chunk.page_number,
                    branch_id=chunk.branch_id,
                    excerpt=chunk.content[:500],
                )
            )

        abstained = draft.abstained or not citations
        answer = (
            draft.answer
            if not (not draft.abstained and not citations)
            else "目前無法以可靠來源支持回答。"
        )
        reason = draft.reason
        if not draft.abstained and not citations:
            reason = "模型沒有提供可驗證的引用。"

        response = ChatResponse(
            answer=answer,
            abstained=abstained,
            reason=reason,
            citations=citations if not abstained else [],
            execution=ExecutionInfo(
                latency_ms=round((generation_done - started) * 1000),
                retrieval_ms=round((retrieval_done - started) * 1000),
                generation_ms=round((generation_done - retrieval_done) * 1000),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                retrieved_chunks=len(retrieved),
            ),
        )
        if log:
            response.trace_id = await self._log(question, branch_id, response, retrieved)
        return response

    async def _log(self, question: str, branch_id: str, response: ChatResponse, retrieved) -> UUID:
        return await asyncio.to_thread(
            self.database.log_chat,
            {
                "question": question,
                "branch_id": branch_id,
                "answer": response.answer,
                "abstained": response.abstained,
                "reason": response.reason,
                "citation_chunk_ids": [item.chunk_id for item in response.citations],
                "retrieved_chunk_ids": [item.id for item in retrieved],
                "latency_ms": response.execution.latency_ms,
                "retrieval_ms": response.execution.retrieval_ms,
                "generation_ms": response.execution.generation_ms,
                "input_tokens": response.execution.input_tokens,
                "output_tokens": response.execution.output_tokens,
                "model": self.settings.openai_chat_model,
            },
            [
                {
                    "citation_number": item.citation_number,
                    "source_id": item.source_id,
                    "chunk_id": item.chunk_id,
                    "document_title": item.document_title,
                    "section": item.section,
                    "page_number": item.page_number,
                    "branch_id": item.branch_id,
                    "excerpt": item.excerpt,
                    "statement": item.statement,
                }
                for item in response.citations
            ],
        )
