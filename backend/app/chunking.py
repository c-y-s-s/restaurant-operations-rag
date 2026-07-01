import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class SourceSection:
    section: str
    content: str
    page_number: int | None = None


@dataclass(frozen=True)
class SourceDocument:
    source_path: Path
    title: str
    branch_id: str | None
    document_type: str
    sections: list[SourceSection]


@dataclass(frozen=True)
class TextChunk:
    section: str
    content: str
    page_number: int | None
    chunk_index: int


FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.MULTILINE)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip("\"'")
    return metadata, text[match.end() :]


def load_document(path: Path) -> SourceDocument:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(path)
        sections = [
            SourceSection(
                section=f"第 {index} 頁", content=page.extract_text() or "", page_number=index
            )
            for index, page in enumerate(reader.pages, start=1)
            if (page.extract_text() or "").strip()
        ]
        return SourceDocument(path, path.stem, None, "manual", sections)

    raw = path.read_text(encoding="utf-8")
    metadata, body = _parse_frontmatter(raw)
    matches = list(HEADING_RE.finditer(body))
    sections: list[SourceSection] = []
    if not matches:
        sections.append(SourceSection("本文", body.strip()))
    else:
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            content = body[match.end() : end].strip()
            if content:
                sections.append(SourceSection(match.group(1), content))
    branch = metadata.get("branch")
    if branch in {"global", "all", "none", ""}:
        branch = None
    return SourceDocument(
        source_path=path,
        title=metadata.get("title", path.stem.replace("-", " ")),
        branch_id=branch,
        document_type=metadata.get("document_type", "sop"),
        sections=sections,
    )


def chunk_document(
    document: SourceDocument, max_chars: int = 900, overlap: int = 120
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    chunk_index = 0
    for section in document.sections:
        paragraphs = [
            item.strip() for item in re.split(r"\n\s*\n", section.content) if item.strip()
        ]
        buffer = ""
        for paragraph in paragraphs:
            candidate = f"{buffer}\n\n{paragraph}".strip()
            if buffer and len(candidate) > max_chars:
                chunks.append(TextChunk(section.section, buffer, section.page_number, chunk_index))
                chunk_index += 1
                tail = buffer[-overlap:] if overlap else ""
                buffer = f"{tail}\n\n{paragraph}".strip()
            else:
                buffer = candidate
        if buffer:
            chunks.append(TextChunk(section.section, buffer, section.page_number, chunk_index))
            chunk_index += 1
    return chunks


def discover_documents(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.suffix.lower() in {".md", ".pdf"})
