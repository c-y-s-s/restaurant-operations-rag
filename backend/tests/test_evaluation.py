import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.evaluation import EvaluationRunner
from app.models import ChatResponse, Citation, ExecutionInfo, RetrievedChunk


def make_chunk(title: str) -> RetrievedChunk:
    return RetrievedChunk(
        id=uuid4(),
        document_id=uuid4(),
        source_id=1,
        document_title=title,
        section="測試章節",
        page_number=None,
        branch_id=None,
        document_type="sop",
        content="測試內容",
        semantic_score=0.9,
        lexical_score=0.5,
        combined_score=0.8,
    )


class FakeDatabase:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks
        self.run_id = uuid4()
        self.evaluation_values = None
        self.evaluation_results = None

    def search(self, *_args):
        return self.chunks

    def log_evaluation(self, values, results):
        self.evaluation_values = values
        self.evaluation_results = results
        return self.run_id


class FakeOpenAI:
    async def embed(self, _texts):
        return [[0.0] * 1536]


class FakeChatService:
    def __init__(self, responses: list[ChatResponse]) -> None:
        self.responses = responses
        self.settings = SimpleNamespace(openai_chat_model="test-model")

    async def ask(self, *_args, **_kwargs):
        return self.responses.pop(0)


def make_response(chunk: RetrievedChunk | None, *, abstained: bool) -> ChatResponse:
    citations = []
    if chunk:
        citations.append(
            Citation(
                citation_number=1,
                source_id=chunk.source_id,
                chunk_id=chunk.id,
                statement="支持答案",
                document_title=chunk.document_title,
                section=chunk.section,
                page_number=None,
                branch_id=None,
                excerpt=chunk.content,
            )
        )
    return ChatResponse(
        answer="資料不足" if abstained else "測試答案",
        abstained=abstained,
        reason="沒有資料" if abstained else None,
        citations=citations,
        execution=ExecutionInfo(
            latency_ms=10,
            retrieval_ms=3,
            generation_ms=7,
            input_tokens=10,
            output_tokens=5,
            retrieved_chunks=1,
        ),
    )


@pytest.mark.asyncio
async def test_evaluation_returns_per_case_details(tmp_path) -> None:
    chunk = make_chunk("預期文件")
    cases = [
        {
            "id": "answer-01",
            "question": "有答案嗎？",
            "branch_id": "taipei",
            "expected_document": "預期文件",
            "should_abstain": False,
        },
        {
            "id": "unknown-01",
            "question": "沒有答案嗎？",
            "branch_id": "taipei",
            "should_abstain": True,
        },
    ]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    database = FakeDatabase([chunk])
    runner = EvaluationRunner(
        database,  # type: ignore[arg-type]
        FakeOpenAI(),  # type: ignore[arg-type]
        FakeChatService(
            [make_response(chunk, abstained=False), make_response(None, abstained=True)]
        ),  # type: ignore[arg-type]
    )

    summary = await runner.run(path)

    assert summary.cases == 2
    assert summary.run_id == database.run_id
    assert summary.recall_at_5 == 1
    assert summary.correct_abstention_rate == 1
    assert summary.citation_validity_rate == 1
    assert summary.results[0].retrieval_passed is True
    assert summary.results[0].retrieved_documents == ["預期文件"]
    assert summary.results[0].cited_documents == ["預期文件"]
    assert summary.results[0].overall_passed is True
    assert summary.results[1].retrieval_passed is None
    assert summary.results[1].abstention_passed is True
    assert database.evaluation_values["model"] == "test-model"
    assert len(database.evaluation_results) == 2
