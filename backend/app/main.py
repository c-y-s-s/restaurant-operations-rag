import asyncio
import hmac
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import APIConnectionError, APIStatusError, RateLimitError

from app.chat_service import ChatService
from app.config import get_settings
from app.database import Database
from app.evaluation import EvaluationRunner
from app.ingestion import IngestionService
from app.models import (
    ChatRequest,
    ChatResponse,
    EvaluationRequest,
    EvaluationSummary,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    MetricSummary,
)
from app.openai_service import OpenAIService
from app.rate_limit import DailyRateLimiter

settings = get_settings()
database = Database(settings.database_url)
openai_service = OpenAIService(
    settings.openai_api_key or "missing-key",
    settings.openai_chat_model,
    settings.openai_embedding_model,
)
chat_service = ChatService(database, openai_service, settings)
ingestion_service = IngestionService(database, openai_service)
evaluation_runner = EvaluationRunner(database, openai_service, chat_service)
rate_limiter = DailyRateLimiter(settings.max_daily_requests_per_ip)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.is_configured:
        await asyncio.to_thread(database.open)
    yield
    await asyncio.to_thread(database.close)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Citation-first RAG API for fictional restaurant operations.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Secret"],
)


def require_configured() -> None:
    if not settings.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Set a real OPENAI_API_KEY and Supabase DATABASE_URL in the project .env",
        )


def require_admin(x_admin_secret: str = Header(default="")) -> None:
    if settings.admin_secret == "change-me":
        raise HTTPException(status_code=503, detail="ADMIN_SECRET must be configured")
    if not hmac.compare_digest(x_admin_secret, settings.admin_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin secret")


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


@app.exception_handler(RateLimitError)
async def openai_rate_limit_handler(_: Request, __: RateLimitError) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Model service is busy; retry shortly"})


@app.exception_handler(APIConnectionError)
async def openai_connection_handler(_: Request, __: APIConnectionError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Unable to reach model service"})


@app.exception_handler(APIStatusError)
async def openai_status_handler(_: Request, error: APIStatusError) -> JSONResponse:
    return JSONResponse(
        status_code=502, content={"detail": f"Model service returned {error.status_code}"}
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    database_ok = await asyncio.to_thread(database.ping) if settings.is_configured else False
    return HealthResponse(
        status="ok" if database_ok and bool(settings.openai_api_key) else "degraded",
        database=database_ok,
        openai_configured=bool(settings.openai_api_key),
        timestamp=datetime.now(UTC),
    )


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_configured)])
async def chat(payload: ChatRequest, request: Request, response: Response) -> ChatResponse:
    allowed, remaining = rate_limiter.check(client_key(request))
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    if not allowed:
        raise HTTPException(status_code=429, detail="Daily demo request limit reached")
    return await chat_service.ask(payload.question.strip(), payload.branch_id)


@app.post(
    "/admin/ingest",
    response_model=IngestResponse,
    dependencies=[Depends(require_configured), Depends(require_admin)],
)
async def ingest(payload: IngestRequest) -> IngestResponse:
    default_root = Path(__file__).resolve().parents[2] / "knowledge"
    root = Path(payload.path).expanduser().resolve() if payload.path else default_root
    if not root.is_dir():
        raise HTTPException(status_code=400, detail="Knowledge path does not exist")
    return await ingestion_service.ingest(root, replace=payload.replace)


@app.post(
    "/evaluations/run",
    response_model=EvaluationSummary,
    dependencies=[Depends(require_configured), Depends(require_admin)],
)
async def run_evaluation(payload: EvaluationRequest) -> EvaluationSummary:
    path = Path(__file__).resolve().parents[1] / "evals" / "cases.json"
    return await evaluation_runner.run(path, payload.limit)


@app.get(
    "/evaluations/latest",
    response_model=EvaluationSummary,
    dependencies=[Depends(require_configured), Depends(require_admin)],
)
async def latest_evaluation() -> EvaluationSummary:
    result = await asyncio.to_thread(database.latest_evaluation)
    if result is None:
        raise HTTPException(status_code=404, detail="No evaluation run found")
    return result


@app.get(
    "/metrics/summary",
    response_model=MetricSummary,
    dependencies=[Depends(require_configured), Depends(require_admin)],
)
async def metrics() -> MetricSummary:
    return await asyncio.to_thread(database.metrics)
