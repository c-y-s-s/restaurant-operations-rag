import json
from pathlib import Path

from app.chunking import discover_documents, load_document
from app.evaluation import EvaluationCase

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "knowledge"
EVALUATIONS = ROOT / "backend" / "evals" / "cases.json"


def test_knowledge_source_paths_and_titles_are_unique() -> None:
    documents = [load_document(path) for path in discover_documents(KNOWLEDGE)]

    assert len({document.source_path.name for document in documents}) == len(documents)
    assert len({document.title for document in documents}) == len(documents)


def test_branch_specific_menu_summary_is_not_global() -> None:
    documents = [load_document(path) for path in discover_documents(KNOWLEDGE)]
    taipei_summary = next(document for document in documents if document.title == "台北店菜單總覽")

    assert taipei_summary.branch_id == "taipei"
    assert all(
        "台北店目前共有" not in section.content
        for document in documents
        if document.branch_id is None
        for section in document.sections
    )


def test_evaluation_expected_documents_exist() -> None:
    titles = {load_document(path).title for path in discover_documents(KNOWLEDGE)}
    cases = [
        EvaluationCase.model_validate(item)
        for item in json.loads(EVALUATIONS.read_text(encoding="utf-8"))
    ]

    missing = {
        source
        for case in cases
        for source in case.expected_sources
        if source not in titles
    }
    assert missing == set()


def test_compound_case_requires_both_sources() -> None:
    cases = [
        EvaluationCase.model_validate(item)
        for item in json.loads(EVALUATIONS.read_text(encoding="utf-8"))
    ]
    compound = next(case for case in cases if case.id == "compound-01")

    assert compound.expected_sources == {
        "台北店打烊補充 SOP",
        "全店菜單與過敏原指南",
    }


def test_answered_evaluation_cases_have_expected_keywords() -> None:
    cases = [
        EvaluationCase.model_validate(item)
        for item in json.loads(EVALUATIONS.read_text(encoding="utf-8"))
    ]

    missing = {
        case.id
        for case in cases
        if not case.should_abstain and not case.expected_keywords
    }
    assert missing == set()


def test_evaluation_set_has_expected_case_count_and_unique_ids() -> None:
    cases = json.loads(EVALUATIONS.read_text(encoding="utf-8"))
    ids = [case["id"] for case in cases]

    assert len(cases) == 25
    assert len(set(ids)) == len(ids)
