import asyncio
import json
from pathlib import Path
from time import perf_counter

from psycopg import OperationalError
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
    expected_keywords: list[str] = Field(default_factory=list)
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
        correctness_hits = 0
        correctness_cases = 0
        total_input_tokens = 0
        total_output_tokens = 0
        results: list[EvaluationCaseResult] = []

        for case in cases:
            question = case.question
            branch_id = case.branch_id
            embedding = (await self.openai.embed([question]))[0]
            chunks = await self._to_thread_with_db_retry(
                self.database.search, question, embedding, branch_id, 5
            )
            retrieved_documents = list(dict.fromkeys(item.document_title for item in chunks))
            retrieval_passed: bool | None = None
            if case.expected_sources:
                retrieval_cases += 1
                retrieval_passed = case.expected_sources <= set(retrieved_documents)
                if retrieval_passed:
                    retrieval_hits += 1

            started = perf_counter()
            response = await self._with_db_retry(
                lambda question=question, branch_id=branch_id: self.chat_service.ask(
                    question, branch_id, log=False
                )
            )
            latency_ms = round((perf_counter() - started) * 1000)
            latencies.append(latency_ms)
            total_input_tokens += response.execution.input_tokens
            total_output_tokens += response.execution.output_tokens
            abstention_passed = response.abstained == case.should_abstain
            if abstention_passed:
                abstention_hits += 1
            matched_keywords: list[str] = []
            missing_keywords: list[str] = []
            answer_correctness_passed: bool | None = None
            if not case.should_abstain:
                correctness_cases += 1
                matched_keywords = [
                    keyword for keyword in case.expected_keywords if keyword in response.answer
                ]
                missing_keywords = [
                    keyword for keyword in case.expected_keywords if keyword not in response.answer
                ]
                answer_correctness_passed = bool(case.expected_keywords) and not missing_keywords
                if answer_correctness_passed:
                    correctness_hits += 1
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
                    answer_correctness_passed=answer_correctness_passed,
                    matched_keywords=matched_keywords,
                    missing_keywords=missing_keywords,
                    cited_documents=list(
                        dict.fromkeys(citation.document_title for citation in response.citations)
                    ),
                    answer=response.answer,
                    reason=response.reason,
                    latency_ms=latency_ms,
                    overall_passed=(
                        (retrieval_passed is not False)
                        and abstention_passed
                        and citation_validity_passed
                        and (answer_correctness_passed is not False)
                    ),
                )
            )

        count = len(cases)
        estimated_cost = self._estimated_cost_usd(total_input_tokens, total_output_tokens)
        summary = EvaluationSummary(
            cases=count,
            recall_at_5=retrieval_hits / retrieval_cases if retrieval_cases else 1.0,
            correct_abstention_rate=abstention_hits / count if count else 0,
            citation_validity_rate=valid_citations / citation_total if citation_total else 1.0,
            answer_correctness_rate=(
                correctness_hits / correctness_cases if correctness_cases else 1.0
            ),
            average_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            p50_latency_ms=self._percentile(latencies, 0.50),
            p95_latency_ms=self._percentile(latencies, 0.95),
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            estimated_cost_usd=estimated_cost,
            results=results,
        )
        summary.run_id = await self._to_thread_with_db_retry(
            self.database.log_evaluation,
            {
                "cases": summary.cases,
                "recall_at_5": summary.recall_at_5,
                "correct_abstention_rate": summary.correct_abstention_rate,
                "citation_validity_rate": summary.citation_validity_rate,
                "answer_correctness_rate": summary.answer_correctness_rate,
                "average_latency_ms": summary.average_latency_ms,
                "p50_latency_ms": summary.p50_latency_ms,
                "p95_latency_ms": summary.p95_latency_ms,
                "total_input_tokens": summary.total_input_tokens,
                "total_output_tokens": summary.total_output_tokens,
                "estimated_cost_usd": summary.estimated_cost_usd,
                "model": self.chat_service.settings.openai_chat_model,
            },
            [
                {**result.model_dump(), "case_id": result.id}
                for result in summary.results
            ],
        )
        return summary

    async def _to_thread_with_db_retry(self, func, *args):
        last_error: OperationalError | None = None
        for attempt in range(2):
            try:
                return await asyncio.to_thread(func, *args)
            except OperationalError as error:
                last_error = error
                if attempt == 0:
                    await asyncio.sleep(1)
        raise last_error

    async def _with_db_retry(self, factory):
        last_error: OperationalError | None = None
        for attempt in range(2):
            try:
                return await factory()
            except OperationalError as error:
                last_error = error
                if attempt == 0:
                    await asyncio.sleep(1)
        raise last_error

    @staticmethod
    def _percentile(values: list[int], percentile: float) -> float:
        if not values:
            return 0
        ordered = sorted(values)
        index = round((len(ordered) - 1) * percentile)
        return ordered[index]

    def _estimated_cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        settings = self.chat_service.settings
        input_cost = input_tokens / 1_000_000 * settings.openai_chat_input_cost_per_1m_tokens
        output_cost = output_tokens / 1_000_000 * settings.openai_chat_output_cost_per_1m_tokens
        return round(input_cost + output_cost, 6)
