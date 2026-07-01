from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from pgvector.psycopg import register_vector
from psycopg import ProgrammingError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.models import EvaluationCaseResult, EvaluationSummary, MetricSummary, RetrievedChunk


class Database:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.pool: ConnectionPool[Any] | None = None

    def open(self) -> None:
        if not self.database_url or self.pool:
            return
        self.pool = ConnectionPool(
            conninfo=self.database_url,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )
        with self.pool.connection() as connection:
            self._register_vector_if_available(connection)

    def close(self) -> None:
        if self.pool:
            self.pool.close()
            self.pool = None

    @contextmanager
    def connection(self):
        if not self.pool:
            raise RuntimeError("Database is not configured")
        with self.pool.connection() as connection:
            self._register_vector_if_available(connection)
            yield connection

    @staticmethod
    def _register_vector_if_available(connection) -> None:
        """Allow the initial migration to connect before pgvector exists."""
        try:
            register_vector(connection)
        except ProgrammingError as error:
            if "vector type not found" not in str(error):
                raise

    def ping(self) -> bool:
        try:
            with self.connection() as connection:
                return connection.execute("select 1").fetchone() is not None
        except Exception:
            return False

    def document_needs_update(
        self,
        *,
        source_path: str,
        checksum: str,
        replace: bool,
    ) -> bool:
        with self.connection() as connection:
            existing = connection.execute(
                "select checksum from documents where source_path = %s", (source_path,)
            ).fetchone()
            if existing and existing["checksum"] == checksum:
                return False
            if existing and not replace:
                return False
            return True

    def replace_document(
        self,
        *,
        title: str,
        source_path: str,
        checksum: str,
        branch_id: str | None,
        document_type: str,
        chunks: Sequence[dict[str, Any]],
    ) -> None:
        """Atomically replace a document only after all embeddings are available."""
        with self.connection() as connection:
            row = connection.execute(
                """
                insert into documents (title, source_path, checksum, branch_id, document_type)
                values (%s, %s, %s, %s, %s)
                on conflict (source_path) do update set
                  title = excluded.title,
                  checksum = excluded.checksum,
                  branch_id = excluded.branch_id,
                  document_type = excluded.document_type,
                  updated_at = now()
                returning id
                """,
                (title, source_path, checksum, branch_id, document_type),
            ).fetchone()
            document_id = row["id"]
            connection.execute("delete from chunks where document_id = %s", (document_id,))
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    insert into chunks
                      (document_id, section, page_number, chunk_index, content, embedding)
                    values
                      (%(document_id)s, %(section)s, %(page_number)s, %(chunk_index)s,
                       %(content)s, %(embedding)s)
                    """,
                    [{**chunk, "document_id": document_id} for chunk in chunks],
                )
            connection.commit()

    def search(
        self, question: str, query_embedding: list[float], branch_id: str, limit: int = 8
    ) -> list[RetrievedChunk]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                with scored as (
                  select
                    c.id, c.document_id, d.source_id, d.title as document_title, c.section,
                    c.page_number, d.branch_id, d.document_type, c.content,
                    greatest(0, 1 - (c.embedding <=> %s::vector)) as semantic_score,
                    greatest(
                      ts_rank_cd(c.search_vector, websearch_to_tsquery('simple', %s)),
                      similarity(c.content, %s)
                    ) as lexical_score
                  from chunks c
                  join documents d on d.id = c.document_id
                  where d.branch_id is null or d.branch_id = %s
                )
                select *,
                  (semantic_score * 0.72 + least(lexical_score, 1) * 0.28) as combined_score
                from scored
                order by combined_score desc, semantic_score desc
                limit %s
                """,
                (query_embedding, question, question, branch_id, limit),
            ).fetchall()
        return [RetrievedChunk.model_validate(row) for row in rows]

    def log_chat(self, values: dict[str, Any], citations: Sequence[dict[str, Any]]) -> UUID:
        with self.connection() as connection:
            try:
                row = connection.execute(
                    """
                    insert into chat_logs
                      (question, branch_id, answer, abstained, reason, citation_chunk_ids,
                       retrieved_chunk_ids, latency_ms, retrieval_ms, generation_ms,
                       input_tokens, output_tokens, model)
                    values
                      (%(question)s, %(branch_id)s, %(answer)s, %(abstained)s, %(reason)s,
                       %(citation_chunk_ids)s, %(retrieved_chunk_ids)s, %(latency_ms)s,
                       %(retrieval_ms)s, %(generation_ms)s, %(input_tokens)s,
                       %(output_tokens)s, %(model)s)
                    returning id
                    """,
                    values,
                ).fetchone()
                chat_log_id = row["id"]
                if citations:
                    with connection.cursor() as cursor:
                        cursor.executemany(
                            """
                            insert into chat_citations
                              (chat_log_id, citation_number, source_id, chunk_id, document_title,
                               section, page_number, branch_id, excerpt, statement)
                            values
                              (%(chat_log_id)s, %(citation_number)s, %(source_id)s, %(chunk_id)s,
                               %(document_title)s, %(section)s, %(page_number)s,
                               %(branch_id)s, %(excerpt)s, %(statement)s)
                            """,
                            [{**citation, "chat_log_id": chat_log_id} for citation in citations],
                        )
                connection.commit()
                return chat_log_id
            except Exception:
                connection.rollback()
                raise

    def metrics(self) -> MetricSummary:
        with self.connection() as connection:
            row = connection.execute(
                """
                select count(*) as total_requests,
                  coalesce(avg(case when abstained then 0 else 1 end), 0) as answer_rate,
                  coalesce(avg(latency_ms), 0) as average_latency_ms,
                  coalesce(avg(input_tokens), 0) as average_input_tokens,
                  coalesce(avg(output_tokens), 0) as average_output_tokens
                from chat_logs
                """
            ).fetchone()
        return MetricSummary.model_validate(row)

    def log_evaluation(
        self,
        values: dict[str, Any],
        results: Sequence[dict[str, Any]],
    ) -> UUID:
        with self.connection() as connection:
            try:
                row = connection.execute(
                    """
                    insert into evaluation_runs
                      (cases, recall_at_5, correct_abstention_rate,
                       citation_validity_rate, average_latency_ms, model)
                    values
                      (%(cases)s, %(recall_at_5)s, %(correct_abstention_rate)s,
                       %(citation_validity_rate)s, %(average_latency_ms)s, %(model)s)
                    returning id
                    """,
                    values,
                ).fetchone()
                run_id = row["id"]
                if results:
                    with connection.cursor() as cursor:
                        cursor.executemany(
                            """
                            insert into evaluation_case_results
                              (evaluation_run_id, case_id, question, branch_id,
                               expected_documents, retrieved_documents, retrieval_passed,
                               should_abstain, abstained, abstention_passed,
                               citation_validity_passed, cited_documents, answer, reason,
                               latency_ms, overall_passed)
                            values
                              (%(evaluation_run_id)s, %(case_id)s, %(question)s, %(branch_id)s,
                               %(expected_documents)s, %(retrieved_documents)s,
                               %(retrieval_passed)s, %(should_abstain)s, %(abstained)s,
                               %(abstention_passed)s, %(citation_validity_passed)s,
                               %(cited_documents)s, %(answer)s, %(reason)s, %(latency_ms)s,
                               %(overall_passed)s)
                            """,
                            [{**result, "evaluation_run_id": run_id} for result in results],
                        )
                connection.commit()
                return run_id
            except Exception:
                connection.rollback()
                raise

    def latest_evaluation(self) -> EvaluationSummary | None:
        with self.connection() as connection:
            run = connection.execute(
                """
                select id as run_id, created_at, cases, recall_at_5,
                  correct_abstention_rate, citation_validity_rate, average_latency_ms
                from evaluation_runs
                order by created_at desc
                limit 1
                """
            ).fetchone()
            if not run:
                return None
            rows = connection.execute(
                """
                select case_id as id, question, branch_id, expected_documents,
                  retrieved_documents, retrieval_passed, should_abstain, abstained,
                  abstention_passed, citation_validity_passed, cited_documents,
                  answer, reason, latency_ms, overall_passed
                from evaluation_case_results
                where evaluation_run_id = %s
                order by evaluation_case_results.id
                """,
                (run["run_id"],),
            ).fetchall()
        return EvaluationSummary(
            **run,
            results=[EvaluationCaseResult.model_validate(row) for row in rows],
        )
