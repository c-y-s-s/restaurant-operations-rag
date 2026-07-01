FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .
COPY backend/migrations ./migrations
COPY backend/evals ./evals
COPY knowledge ./knowledge
EXPOSE 8000
CMD ["sh", "-c", "python -m app.cli migrate && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
