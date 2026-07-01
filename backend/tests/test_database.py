from contextlib import contextmanager
from uuid import uuid4

import pytest
from psycopg import ProgrammingError

from app.database import Database


class FakeResult:
    def __init__(self, row) -> None:
        self.row = row

    def fetchone(self):
        return self.row


class FakeCursor:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def executemany(self, _query, rows) -> None:
        if self.fail:
            raise RuntimeError("citation insert failed")
        self.rows = rows


class FakeConnection:
    def __init__(self, *, fail_citations: bool = False) -> None:
        self.log_id = uuid4()
        self.fake_cursor = FakeCursor(fail=fail_citations)
        self.committed = False
        self.rolled_back = False

    def execute(self, _query, _values=None):
        return FakeResult({"id": self.log_id})

    def cursor(self):
        return self.fake_cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def test_initial_connection_allows_missing_vector_extension(monkeypatch) -> None:
    def missing_vector(_connection) -> None:
        raise ProgrammingError("vector type not found in the database")

    monkeypatch.setattr("app.database.register_vector", missing_vector)

    Database._register_vector_if_available(object())


def test_unrelated_registration_error_is_not_hidden(monkeypatch) -> None:
    def unrelated_error(_connection) -> None:
        raise ProgrammingError("permission denied")

    monkeypatch.setattr("app.database.register_vector", unrelated_error)

    with pytest.raises(ProgrammingError, match="permission denied"):
        Database._register_vector_if_available(object())


def test_log_chat_writes_snapshot_in_same_transaction(monkeypatch) -> None:
    database = Database("")
    connection = FakeConnection()

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(database, "connection", fake_connection)
    citation = {"citation_number": 1, "chunk_id": uuid4()}

    trace_id = database.log_chat({}, [citation])

    assert trace_id == connection.log_id
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.fake_cursor.rows == [{**citation, "chat_log_id": connection.log_id}]


def test_log_chat_rolls_back_when_snapshot_insert_fails(monkeypatch) -> None:
    database = Database("")
    connection = FakeConnection(fail_citations=True)

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(database, "connection", fake_connection)

    with pytest.raises(RuntimeError, match="citation insert failed"):
        database.log_chat({}, [{"citation_number": 1}])

    assert connection.committed is False
    assert connection.rolled_back is True


def test_log_evaluation_writes_cases_in_same_transaction(monkeypatch) -> None:
    database = Database("")
    connection = FakeConnection()

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(database, "connection", fake_connection)
    result = {"case_id": "case-01", "overall_passed": True}

    run_id = database.log_evaluation({}, [result])

    assert run_id == connection.log_id
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.fake_cursor.rows == [
        {**result, "evaluation_run_id": connection.log_id}
    ]


def test_log_evaluation_rolls_back_when_case_insert_fails(monkeypatch) -> None:
    database = Database("")
    connection = FakeConnection(fail_citations=True)

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(database, "connection", fake_connection)

    with pytest.raises(RuntimeError):
        database.log_evaluation({}, [{"case_id": "case-01"}])

    assert connection.committed is False
    assert connection.rolled_back is True
