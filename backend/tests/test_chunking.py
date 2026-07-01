from pathlib import Path

from app.chunking import chunk_document, load_document


def test_markdown_frontmatter_and_sections(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text(
        "---\ntitle: 測試文件\nbranch: taipei\ndocument_type: sop\n---\n"
        "# 開店\n第一段內容。\n\n第二段內容。\n# 打烊\n最後內容。",
        encoding="utf-8",
    )

    document = load_document(path)

    assert document.title == "測試文件"
    assert document.branch_id == "taipei"
    assert [section.section for section in document.sections] == ["開店", "打烊"]
    assert len(chunk_document(document)) == 2


def test_global_branch_becomes_none(tmp_path: Path) -> None:
    path = tmp_path / "global.md"
    path.write_text("---\nbranch: global\n---\n# 共通\n內容", encoding="utf-8")
    assert load_document(path).branch_id is None
