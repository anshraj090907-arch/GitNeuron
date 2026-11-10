"""
One-click export: push an answer to a GitHub Gist, render it (with
citations) as a PDF, or package referenced files into a CodeSandbox
"define API" payload the frontend can POST straight to CodeSandbox.
"""
from __future__ import annotations

import io

import httpx

from app.config import get_settings
from app.models import ExportPdfRequest


def export_to_gist(title: str, content: str) -> dict:
    settings = get_settings()
    token = settings.github_gist_token or settings.github_token
    if not token:
        raise RuntimeError("No GitHub token configured for Gist export "
                            "(set GITHUB_GIST_TOKEN or GITHUB_TOKEN).")

    resp = httpx.post(
        "https://api.github.com/gists",
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        json={
            "description": title,
            "public": False,
            "files": {f"{title.replace(' ', '_')[:40]}.md": {"content": content}},
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"url": data["html_url"]}


def export_to_pdf(req: ExportPdfRequest) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, req.title)
    pdf.ln(2)

    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, req.content.encode("latin-1", "replace").decode("latin-1"))

    if req.sources:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        pdf.multi_cell(0, 8, "Sources")
        pdf.set_font("Courier", size=9)
        for s in req.sources:
            line = f"{s.file_path}  (lines {s.start_line}-{s.end_line})"
            pdf.multi_cell(0, 5, line.encode("latin-1", "replace").decode("latin-1"))

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def build_sandbox_payload(title: str, files: dict[str, str]) -> dict:
    """CodeSandbox's `define` API expects {file: {content: str}} entries."""
    return {
        "files": {path: {"content": content} for path, content in files.items()},
        "template": "node",
        "title": title,
    }
