from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException

from .deadline_report import ExportRequest, ExportResult, export_deadline_report
from .infrai_storage import InfraiError, InfraiStorage

app = FastAPI(title="Course deadline export")


@app.post("/reports/deadlines/export", response_model=ExportResult)
def create_deadline_export(request: ExportRequest) -> ExportResult:
    try:
        storage = InfraiStorage.from_environment()
        bucket = os.environ.get("REPORT_EXPORT_BUCKET", "edtech-report-exports")
        return export_deadline_report(request, storage, bucket)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
