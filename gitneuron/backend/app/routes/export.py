from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.core import export as export_core
from app.models import ExportGistRequest, ExportPdfRequest, ExportSandboxRequest

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/gist")
def export_gist(req: ExportGistRequest) -> dict:
    try:
        return export_core.export_to_gist(req.title, req.content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/pdf")
def export_pdf(req: ExportPdfRequest) -> Response:
    pdf_bytes = export_core.export_to_pdf(req)
    filename = f"{req.title.replace(' ', '_')[:40] or 'gitneuron-export'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/sandbox")
def export_sandbox(req: ExportSandboxRequest) -> dict:
    return export_core.build_sandbox_payload(req.title, req.files)
