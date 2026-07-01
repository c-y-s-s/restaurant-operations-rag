import asyncio
import json
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, Field

from app.chat_service import ChatService
from app.database import Database
from app.models import EvaluationCaseResult, EvaluationSummary
from app.openai_service import OpenAIService


class EvaluationCase(BaseModel):
    id: str
    question: str
    branch_id: str
    expected_document: str | None = None
    expected_documents: list[str] = Field(default_factory=list)
    should_abstain: bool = False

    @property
    def expected_sources(self) -> set[str]:
        sources = set(self.expected_documents)
        if self.expected_document:
            sources.add(self.expected_document)
        return sources


class EvaluationRunner:
    def __init__(
        self, database: Database, openai_service: OpenAIService, chat_service: ChatService
    ) -> None:
        self.database = database
        self.openai = openai_service
        self.chat_service = chat_service

    async def run(self, path: Path, limit: int | None = None) -> EvaluationSummary:
        raw = json.loads(path.read_text(encoding="utf-8"))
        cases = [EvaluationCase.model_validate(item) for item in raw]
        if limit:
            cases = cases[:limit]

        retrieval_hits = 0
        retrieval_cases = 0
        abstention_hits = 0
        valid_citations = 0
        citation_total = 0
        latencies: list[int] = []
        results: list[EvaluationCaseResult] = []

        for case in cases:
            embedding = (await self.openai.embed([case.question]))[0]
            chunks = await asyncio.to_thread(
                self.database.search, case.question, embedding, case.branch_id, 5
            )
            retrieved_documents = list(dict.fromkeys(item.document_title for item in chunks))
            retrieval_passed: bool | None = None
            if case.expected_sources:
                retrieval_cases += 1
                retrieval_passed = case.expected_sources <= set(retrieved_documents)
                if retrieval_passed:
                    retrieval_hits += 1

            started = perf_counter()
            response = await self.chat_service.ask(case.question, case.branch_id, log=False)
            latency_ms = round((perf_counter() - started) * 1000)
            latencies.append(latency_ms)
            abstention_passed = response.abstained == case.should_abstain
            if abstention_passed:
                abstention_hits += 1
            retrieved_ids = {item.id for item in chunks}
            citation_total += len(response.citations)
            case_valid_citations = sum(
                1 for citation in response.citations if citation.chunk_id in retrieved_ids
            )
            valid_citations += case_valid_citations
            citation_validity_passed = case_valid_citations == len(response.citations)
            results.append(
                EvaluationCaseResult(
                    id=case.id,
                    question=case.question,
                    branch_id=case.branch_id,
                    expected_documents=sorted(case.expected_sources),
                    retrieved_documents=retrieved_documents,
                    retrieval_passed=retrieval_passed,
                    should_abstain=case.should_abstain,
                    abstained=response.abstained,
                    abstention_passed=abstention_passed,
                    citation_validity_passed=citation_validity_passed,
                    cited_documents=list(
                        dict.fromkeys(citation.document_title for citation in response.citations)
                    ),
                    answer=response.answer,
                    reason=response.reason,
                    latency_ms=latency_ms,
                    overall_passed=(retrieval_passed is not False)
                    and abstention_passed
                    and citation_validity_passed,
                )
            )

        count = len(cases)
        summary = EvaluationSummary(
            cases=count,
            recall_at_5=retrieval_hits / retrieval_cases if retrieval_cases else 1.0,
            correct_abstention_rate=abstention_hits / count if count else 0,
            citation_validity_rate=valid_citations / citation_total if citation_total else 1.0,
            average_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            results=results,
        )
        summary.run_id = await asyncio.to_thread(
            self.database.log_evaluation,
            {
                "cases": summary.cases,
                "recall_at_5": summary.recall_at_5,
                "correct_abstention_rate": summary.correct_abstention_rate,
                "citation_validity_rate": summary.citation_validity_rate,
                "average_latency_ms": summary.average_latency_ms,
                "model": self.chat_service.settings.openai_chat_model,
            },
            [
                {**result.model_dump(), "case_id": result.id}
                for result in summary.results
            ],
        )
        return summary
