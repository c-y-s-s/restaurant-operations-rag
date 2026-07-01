import asyncio
import hashlib
from pathlib import Path

from app.chunking import chunk_document, discover_documents, load_document
from app.database import Database
from app.models import IngestResponse
from app.openai_service import OpenAIService


class IngestionService:
    def __init__(self, database: Database, openai_service: OpenAIService) -> None:
        self.database = database
        self.openai = openai_service

    async def ingest(self, root: Path, replace: bool = True) -> IngestResponse:
        paths = discover_documents(root)
        document_count = 0
        chunk_count = 0
        skipped = 0
        for path in paths:
            raw = path.read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            document = load_document(path)
            changed = await asyncio.to_thread(
                self.database.document_needs_update,
                source_path=str(path.relative_to(root)),
                checksum=checksum,
                replace=replace,
            )
            if not changed:
                skipped += 1
                continue
            chunks = chunk_document(document)
            embeddings: list[list[float]] = []
            for start in range(0, len(chunks), 64):
                embeddings.extend(
                    await self.openai.embed([c.content for c in chunks[start : start + 64]])
                )
            rows = [
                {
                    "section": chunk.section,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "embedding": embedding,
                }
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ]
            await asyncio.to_thread(
                self.database.replace_document,
                title=document.title,
                source_path=str(path.relative_to(root)),
                checksum=checksum,
                branch_id=document.branch_id,
                document_type=document.document_type,
                chunks=rows,
            )
            document_count += 1
            chunk_count += len(rows)
        return IngestResponse(documents=document_count, chunks=chunk_count, skipped=skipped)
