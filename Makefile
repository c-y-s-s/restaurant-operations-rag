.PHONY: backend-dev frontend-dev test ingest

backend-dev:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm run dev

test:
	cd backend && pytest
	cd frontend && npm run typecheck

ingest:
	cd backend && python -m app.cli ingest --path ../knowledge

