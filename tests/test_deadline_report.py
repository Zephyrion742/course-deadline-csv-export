from datetime import datetime, timezone

from edtech_export.deadline_report import ExportRequest, due_rows, export_deadline_report


def request_at_cutoff() -> ExportRequest:
    return ExportRequest.model_validate(
        {
            "report_id": "weekly-2026-08-21",
            "as_of": "2026-08-21T09:00:00+00:00",
            "courses": [
                {
                    "course_id": "risk-101",
                    "course_title": "Risk Controls",
                    "learners": [
                        {"learner_id": "L-2", "learner_name": "Lin", "deadline": "2026-08-22T09:00:00+00:00"},
                        {"learner_id": "L-1", "learner_name": "Ari", "deadline": "2026-08-21T09:00:00+00:00"},
                        {
                            "learner_id": "L-3",
                            "learner_name": "Sam",
                            "deadline": "2026-08-20T09:00:00+00:00",
                            "completed_at": "2026-08-20T08:00:00+00:00",
                        },
                    ],
                }
            ],
        }
    )


def test_only_incomplete_learners_due_at_cutoff_are_reported() -> None:
    rows = due_rows(request_at_cutoff())
    assert [(row["learner_id"], row["status"]) for row in rows] == [("L-1", "due")]


class RecordingStorage:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.upload: tuple[str, str, str, str] | None = None

    def create_bucket(self, name: str) -> None:
        self.created.append(name)

    def put_csv(self, bucket: str, key: str, data_base64: str, idempotency_key: str) -> None:
        self.upload = (bucket, key, data_base64, idempotency_key)

    def presign_download(self, bucket: str, key: str) -> str:
        return f"https://downloads.example/{bucket}/{key}"


def test_export_creates_storage_before_upload_and_returns_link() -> None:
    storage = RecordingStorage()
    result = export_deadline_report(request_at_cutoff(), storage, "audit-exports")
    assert storage.created == ["audit-exports"]
    assert storage.upload is not None
    assert storage.upload[0] == "audit-exports"
    assert storage.upload[3].startswith("deadline-report:weekly-2026-08-21:")
    assert result.row_count == 1
    assert result.download_url.startswith("https://downloads.example/audit-exports/deadline-reports/")
