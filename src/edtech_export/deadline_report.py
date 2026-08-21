from __future__ import annotations

import base64
import csv
import hashlib
import io
from datetime import datetime, timezone
from typing import Protocol

from pydantic import BaseModel, Field


class LearnerDelivery(BaseModel):
    learner_id: str = Field(min_length=1)
    learner_name: str = Field(min_length=1)
    deadline: datetime
    completed_at: datetime | None = None


class CourseDelivery(BaseModel):
    course_id: str = Field(min_length=1)
    course_title: str = Field(min_length=1)
    learners: list[LearnerDelivery] = Field(min_length=1)


class ExportRequest(BaseModel):
    report_id: str = Field(min_length=1)
    as_of: datetime
    courses: list[CourseDelivery] = Field(min_length=1)


class ExportResult(BaseModel):
    report_id: str
    row_count: int
    download_url: str
    expires_seconds: int = 900


class ReportStorage(Protocol):
    def create_bucket(self, name: str) -> None:
        pass

    def put_csv(self, bucket: str, key: str, data_base64: str, idempotency_key: str) -> None:
        pass

    def presign_download(self, bucket: str, key: str) -> str:
        pass


def due_rows(request: ExportRequest) -> list[dict[str, str]]:
    as_of = _utc(request.as_of)
    rows: list[dict[str, str]] = []
    for course in request.courses:
        for learner in course.learners:
            deadline = _utc(learner.deadline)
            if deadline <= as_of and learner.completed_at is None:
                rows.append(
                    {
                        "course_id": course.course_id,
                        "course_title": course.course_title,
                        "learner_id": learner.learner_id,
                        "learner_name": learner.learner_name,
                        "deadline": deadline.isoformat(),
                        "status": "due",
                    }
                )
    return sorted(rows, key=lambda row: (row["deadline"], row["course_id"], row["learner_id"]))


def render_csv(rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO(newline="")
    fields = ["course_id", "course_title", "learner_id", "learner_name", "deadline", "status"]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def export_deadline_report(request: ExportRequest, storage: ReportStorage, bucket: str) -> ExportResult:
    rows = due_rows(request)
    csv_bytes = render_csv(rows)
    digest = hashlib.sha256(csv_bytes).hexdigest()[:16]
    key = f"deadline-reports/{request.report_id}-{digest}.csv"
    storage.create_bucket(bucket)
    storage.put_csv(
        bucket,
        key,
        base64.b64encode(csv_bytes).decode("ascii"),
        idempotency_key=f"deadline-report:{request.report_id}:{digest}",
    )
    return ExportResult(
        report_id=request.report_id,
        row_count=len(rows),
        download_url=storage.presign_download(bucket, key),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(timezone.utc)
