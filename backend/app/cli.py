import argparse
import asyncio
from pathlib import Path

from app.config import get_settings
from app.database import Database
from app.ingestion import IngestionService
from app.openai_service import OpenAIService


def migrate(database: Database) -> list[str]:
    migration_dir = Path(__file__).resolve().parents[1] / "migrations"
    applied_now: list[str] = []
    with database.connection() as connection:
        try:
            connection.execute(
                """
                create table if not exists schema_migrations (
                  version text primary key,
                  applied_at timestamptz not null default now()
                )
                """
            )
            applied = {
                row["version"]
                for row in connection.execute("select version from schema_migrations").fetchall()
            }
            for migration_path in sorted(migration_dir.glob("*.sql")):
                version = migration_path.stem
                if version in applied:
                    continue
                connection.execute(migration_path.read_text(encoding="utf-8"))
                connection.execute(
                    "insert into schema_migrations (version) values (%s)", (version,)
                )
                applied_now.append(version)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return applied_now


async def ingest(database: Database, path: Path, replace: bool) -> None:
    settings = get_settings()
    service = IngestionService(
        database,
        OpenAIService(
            settings.openai_api_key,
            settings.openai_chat_model,
            settings.openai_embedding_model,
        ),
    )
    result = await service.ingest(path.resolve(), replace=replace)
    print(result.model_dump_json(indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaurant RAG administration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("migrate", help="Apply the database schema")
    ingest_parser = subparsers.add_parser("ingest", help="Index a knowledge directory")
    ingest_parser.add_argument("--path", type=Path, default=Path("../knowledge"))
    ingest_parser.add_argument("--no-replace", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.database_url or "example.supabase.co" in settings.database_url:
        parser.error("Set DATABASE_URL to the real Supabase connection string in ../.env")
    database = Database(settings.database_url)
    database.open()
    try:
        if args.command == "migrate":
            applied = migrate(database)
            if applied:
                print(f"Database migration completed: {', '.join(applied)}")
            else:
                print("Database schema is already up to date")
        else:
            if not settings.openai_api_key:
                parser.error("Set OPENAI_API_KEY in ../.env before ingestion")
            asyncio.run(ingest(database, args.path, not args.no_replace))
    finally:
        database.close()


if __name__ == "__main__":
    main()
