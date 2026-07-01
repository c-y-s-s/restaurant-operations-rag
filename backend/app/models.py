from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Branch = Literal["taipei", "taichung"]


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    branch_id: Branch


class ModelCitation(BaseModel):
    chunk_id: UUID
    statement: str = Field(min_length=1, max_length=300)


class AnswerDraft(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)
    abstained: bool
    reason: str | None
    citations: list[ModelCitation] = Field(max_length=5)


class Citation(BaseModel):
    citation_number: int = Field(ge=1)
    source_id: int = Field(ge=1)
    chunk_id: UUID
    statement: str
    document_title: str
    section: str
    page_number: int | None
    branch_id: str | None
    excerpt: str


class ExecutionInfo(BaseModel):
    latency_ms: int
    retrieval_ms: int
    generation_ms: int
    input_tokens: int
    output_tokens: int
    retrieved_chunks: int


class ChatResponse(BaseModel):
    trace_id: UUID | None = None
    answer: str
    abstained: bool
    reason: str | None
    citations: list[Citation]
    execution: ExecutionInfo


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    source_id: int
    document_title: str
    section: str
    page_number: int | None
    branch_id: str | None
    document_type: str
    content: str
    semantic_score: float
    lexical_score: float
    combined_score: float


class IngestRequest(BaseModel):
    path: str | None = None
    replace: bool = True


class IngestResponse(BaseModel):
    documents: int
    chunks: int
    skipped: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    openai_configured: bool
    timestamp: datetime


class MetricSummary(BaseModel):
    total_requests: int
    answer_rate: float
    average_latency_ms: float
    average_input_tokens: float
    average_output_tokens: float


class EvaluationSummary(BaseModel):
    run_id: UUID | None = None
    created_at: datetime | None = None
    cases: int
    recall_at_5: float
    correct_abstention_rate: float
    citation_validity_rate: float
    average_latency_ms: float
    results: list["EvaluationCaseResult"] = Field(default_factory=list)


class EvaluationCaseResult(BaseModel):
    id: str
    question: str
    branch_id: str
    expected_documents: list[str]
    retrieved_documents: list[str]
    retrieval_passed: bool | None
    should_abstain: bool
    abstained: bool
    abstention_passed: bool
    citation_validity_passed: bool
    cited_documents: list[str]
    answer: str
    reason: str | None
    latency_ms: int
    overall_passed: bool


class EvaluationRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=100)
