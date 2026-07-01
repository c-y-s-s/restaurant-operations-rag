from contextlib import contextmanager

from app.cli import migrate


class MigrationResult:
    def __init__(self, rows=None) -> None:
        self.rows = rows or []

    def fetchall(self):
        return self.rows


class MigrationConnection:
    def __init__(self) -> None:
        self.versions: set[str] = set()
        self.commits = 0
        self.rollbacks = 0

    def execute(self, query, params=None):
        normalized = " ".join(query.split()).lower()
        if normalized.startswith("select version from schema_migrations"):
            return MigrationResult([{"version": version} for version in self.versions])
        if normalized.startswith("insert into schema_migrations"):
            self.versions.add(params[0])
        return MigrationResult()

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class MigrationDatabase:
    def __init__(self) -> None:
        self.fake_connection = MigrationConnection()

    @contextmanager
    def connection(self):
        yield self.fake_connection


def test_migration_runner_is_idempotent() -> None:
    database = MigrationDatabase()

    first = migrate(database)  # type: ignore[arg-type]
    second = migrate(database)  # type: ignore[arg-type]

    assert first == [
        "001_initial",
        "002_citation_snapshots",
        "003_document_source_id",
        "004_evaluation_runs",
    ]
    assert second == []
    assert database.fake_connection.rollbacks == 0
