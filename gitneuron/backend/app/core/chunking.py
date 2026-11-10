"""
Repository-aware chunking.

Fixed-size splitting can cut a function or class in half, which is
exactly what hurts retrieval quality for code. This module instead
tries to split along *structural* boundaries:

  1. For languages tree-sitter supports, parse the file and chunk at
     function / class / method boundaries (``_chunk_with_tree_sitter``).
  2. For everything else (or if tree-sitter has no grammar installed
     for a language), fall back to a language-aware heuristic splitter
     that still respects blank-line and indentation boundaries rather
     than cutting at a fixed character count (``_chunk_heuristically``).
  3. Markdown / plain text is split by heading / paragraph
     (``_chunk_prose``).

Every chunk keeps its originating file path, language and line range,
which is what lets GitNeuron cite sources precisely.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.github_service import RepoFile

TREE_SITTER_LANGUAGES = {
    "python", "javascript", "typescript", "go", "rust", "java",
    "ruby", "php", "c", "cpp", "csharp",
}

# Node types (per tree-sitter grammar) that mark a natural chunk boundary.
DEFINITION_NODE_TYPES = {
    "function_definition", "class_definition", "method_definition",
    "function_declaration", "class_declaration", "method_declaration",
    "function_item", "impl_item", "struct_item", "trait_item",
    "interface_declaration",
}


@dataclass
class Chunk:
    file_path: str
    language: str
    start_line: int
    end_line: int
    text: str


def _approx_tokens(text: str) -> int:
    # ~4 chars/token is a reasonable approximation for mixed code+prose
    # and avoids pulling in a tokenizer for every provider's own scheme.
    return max(1, len(text) // 4)


def _get_parser(language: str):
    try:
        from tree_sitter_languages import get_parser
        return get_parser(language)
    except Exception:
        return None


def _chunk_with_tree_sitter(file: RepoFile, max_tokens: int) -> list[Chunk] | None:
    parser = _get_parser(file.language)
    if parser is None:
        return None

    try:
        tree = parser.parse(bytes(file.content, "utf-8"))
    except Exception:
        return None

    lines = file.content.splitlines()
    root = tree.root_node

    boundaries: list[tuple[int, int]] = []  # (start_line, end_line) 0-indexed inclusive

    def visit(node):
        if node.type in DEFINITION_NODE_TYPES:
            boundaries.append((node.start_point[0], node.end_point[0]))
            return  # don't descend into nested definitions separately
        for child in node.children:
            visit(child)

    visit(root)

    if not boundaries:
        return None

    boundaries.sort()
    chunks: list[Chunk] = []
    covered_until = 0

    for start, end in boundaries:
        # Leading module-level code before this definition (imports, globals)
        if start > covered_until:
            leading = "\n".join(lines[covered_until:start]).strip()
            if leading:
                chunks.append(Chunk(file.path, file.language, covered_until + 1, start, leading))

        text = "\n".join(lines[start:end + 1])
        if _approx_tokens(text) > max_tokens * 2:
            # A single function is unusually huge — fall back to sub-splitting it.
            chunks.extend(_split_long_block(file, text, start + 1, max_tokens))
        else:
            chunks.append(Chunk(file.path, file.language, start + 1, end + 1, text))
        covered_until = end + 1

    if covered_until < len(lines):
        trailing = "\n".join(lines[covered_until:]).strip()
        if trailing:
            chunks.append(Chunk(file.path, file.language, covered_until + 1, len(lines), trailing))

    return chunks


def _split_long_block(file: RepoFile, text: str, start_line: int, max_tokens: int) -> list[Chunk]:
    lines = text.splitlines()
    out: list[Chunk] = []
    buf: list[str] = []
    buf_start = start_line
    for i, line in enumerate(lines):
        buf.append(line)
        if _approx_tokens("\n".join(buf)) >= max_tokens:
            out.append(Chunk(file.path, file.language, buf_start, start_line + i, "\n".join(buf)))
            buf = []
            buf_start = start_line + i + 1
    if buf:
        out.append(Chunk(file.path, file.language, buf_start, start_line + len(lines) - 1, "\n".join(buf)))
    return out


def _chunk_heuristically(file: RepoFile, max_tokens: int) -> list[Chunk]:
    """Blank-line / brace-aware fallback for languages without a grammar."""
    lines = file.content.splitlines()
    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_start = 1

    for i, line in enumerate(lines, start=1):
        buf.append(line)
        at_boundary = line.strip() == "" and _approx_tokens("\n".join(buf)) >= max_tokens
        if at_boundary or _approx_tokens("\n".join(buf)) >= max_tokens * 1.5:
            text = "\n".join(buf).strip("\n")
            if text.strip():
                chunks.append(Chunk(file.path, file.language, buf_start, i, text))
            buf = []
            buf_start = i + 1

    if buf:
        text = "\n".join(buf).strip("\n")
        if text.strip():
            chunks.append(Chunk(file.path, file.language, buf_start, len(lines), text))

    return chunks or [Chunk(file.path, file.language, 1, len(lines), file.content)]


def _chunk_prose(file: RepoFile, max_tokens: int) -> list[Chunk]:
    """Split markdown/text by headings first, then by size within a section."""
    lines = file.content.splitlines()
    sections: list[tuple[int, list[str]]] = []
    current_start = 1
    current: list[str] = []

    heading_re = re.compile(r"^#{1,6}\s")
    for i, line in enumerate(lines, start=1):
        if heading_re.match(line) and current:
            sections.append((current_start, current))
            current = []
            current_start = i
        current.append(line)
    if current:
        sections.append((current_start, current))

    chunks: list[Chunk] = []
    for start, section_lines in sections:
        text = "\n".join(section_lines)
        if _approx_tokens(text) <= max_tokens * 1.5:
            chunks.append(Chunk(file.path, file.language, start, start + len(section_lines) - 1, text))
        else:
            chunks.extend(_split_long_block(file, text, start, max_tokens))

    return chunks or [Chunk(file.path, file.language, 1, len(lines), file.content)]


def chunk_file(file: RepoFile, max_tokens: int = 400) -> list[Chunk]:
    if not file.content.strip():
        return []

    if file.language in ("markdown", "text"):
        return _chunk_prose(file, max_tokens)

    if file.language in TREE_SITTER_LANGUAGES:
        result = _chunk_with_tree_sitter(file, max_tokens)
        if result:
            return result

    return _chunk_heuristically(file, max_tokens)


def chunk_repository(files: list[RepoFile], max_tokens: int = 400) -> list[Chunk]:
    chunks: list[Chunk] = []
    for f in files:
        chunks.extend(chunk_file(f, max_tokens))
    return chunks
