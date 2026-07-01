from uuid import uuid4

import pytest

from app.chat_service import ChatService
from app.config import Settings
from app.models import AnswerDraft, ModelCitation, RetrievedChunk


def make_chunk(score: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(
        id=uuid4(),
        document_id=uuid4(),
        source_id=3,
        document_title="食品安全與溫度管理",
        section="冷藏與冷凍",
        page_number=None,
        branch_id=None,
        document_type="safety",
        content="冷藏設備應維持 0°C 至 7°C。",
        semantic_score=score,
        lexical_score=0.4,
        combined_score=0.76,
    )


class FakeDatabase:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks
        self.logs: list[dict] = []
        self.citation_snapshots: list[list[dict]] = []
        self.trace_id = uuid4()

    def search(self, *_args):
        return self.chunks

    def log_chat(self, values, citations):
        self.logs.append(values)
        self.citation_snapshots.append(citations)
        return self.trace_id


class FakeOpenAI:
    def __init__(self, answer: AnswerDraft) -> None:
        self.draft = answer

    async def embed(self, _texts):
        return [[0.0] * 1536]

    async def answer(self, *_args):
        return self.draft, 100, 20


@pytest.mark.asyncio
async def test_valid_citation_is_hydrated() -> None:
    chunk = make_chunk()
    model_answer = AnswerDraft(
        answer="冷藏設備應維持 0°C 至 7°C。",
        abstained=False,
        reason=None,
        citations=[ModelCitation(chunk_id=chunk.id, statement="支持冷藏溫度範圍")],
    )
    database = FakeDatabase([chunk])
    service = ChatService(database, FakeOpenAI(model_answer), Settings())  # type: ignore[arg-type]

    response = await service.ask("冷藏溫度？", "taipei")

    assert response.abstained is False
    assert response.trace_id == database.trace_id
    assert response.citations[0].citation_number == 1
    assert response.citations[0].source_id == 3
    assert response.citations[0].document_title == "食品安全與溫度管理"
    assert database.logs[0]["citation_chunk_ids"] == [chunk.id]
    assert database.citation_snapshots[0][0] == {
        "citation_number": 1,
        "source_id": 3,
        "chunk_id": chunk.id,
        "document_title": "食品安全與溫度管理",
        "section": "冷藏與冷凍",
        "page_number": None,
        "branch_id": None,
        "excerpt": "冷藏設備應維持 0°C 至 7°C。",
        "statement": "支持冷藏溫度範圍",
    }


@pytest.mark.asyncio
async def test_hallucinated_citation_forces_abstention() -> None:
    chunk = make_chunk()
    model_answer = AnswerDraft(
        answer="不可靠回答",
        abstained=False,
        reason=None,
        citations=[ModelCitation(chunk_id=uuid4(), statement="不存在的來源")],
    )
    database = FakeDatabase([chunk])
    service = ChatService(
        database,
        FakeOpenAI(model_answer),
        Settings(),  # type: ignore[arg-type]
    )

    response = await service.ask("冷藏溫度？", "taipei")

    assert response.abstained is True
    assert response.citations == []
    assert response.reason == "模型沒有提供可驗證的引用。"
    assert database.citation_snapshots == [[]]


@pytest.mark.asyncio
async def test_low_relevance_abstains_without_generation() -> None:
    chunk = make_chunk(score=0.1)
    model_answer = AnswerDraft(answer="不應使用", abstained=False, reason=None, citations=[])
    service = ChatService(
        FakeDatabase([chunk]),
        FakeOpenAI(model_answer),
        Settings(),  # type: ignore[arg-type]
    )

    response = await service.ask("年終獎金？", "taipei")

    assert response.abstained is True
    assert response.execution.generation_ms == 0


@pytest.mark.asyncio
async def test_conflicting_context_preserves_model_abstention() -> None:
    first = make_chunk()
    second = make_chunk()
    first = first.model_copy(
        update={
            "id": uuid4(),
            "document_title": "台北店打烊補充 SOP",
            "content": "台北店週六最後點餐時間為 21:30。",
        }
    )
    second = second.model_copy(
        update={
            "id": uuid4(),
            "document_title": "臨時營運公告",
            "content": "台北店週六最後點餐時間為 21:00。",
        }
    )
    model_answer = AnswerDraft(
        answer="目前資料互相衝突，無法確認最後點餐時間。",
        abstained=True,
        reason="兩份文件分別記載 21:30 與 21:00。",
        citations=[],
    )
    database = FakeDatabase([first, second])
    service = ChatService(database, FakeOpenAI(model_answer), Settings())  # type: ignore[arg-type]

    response = await service.ask("台北店週六最後點餐時間？", "taipei")

    assert response.abstained is True
    assert response.citations == []
    assert "21:30" in (response.reason or "")
    assert "21:00" in (response.reason or "")
    assert database.logs[0]["abstained"] is True
