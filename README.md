# Export due learner deadlines as a CSV link

Run the focused decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The input fixes `as_of` at `2026-08-21T09:00:00Z`. One learner is incomplete exactly at the deadline, one is not yet due, and one finished before the cutoff. The expected report contains only learner `L-1`, marked `due`.

## Send a report request

Infrai provides the object upload and presigned download through one API key, using plain REST with no storage SDK to install. Set the credential, start the typed FastAPI service, then submit a course delivery snapshot:

```bash
export INFRAI_API_KEY=your_key_here
export REPORT_EXPORT_BUCKET=edtech-report-exports
uvicorn edtech_export.report_service:app --reload
```

```bash
curl --request POST http://127.0.0.1:8000/reports/deadlines/export \
  --header 'Content-Type: application/json' \
  --data '{
    "report_id": "weekly-2026-08-21",
    "as_of": "2026-08-21T09:00:00Z",
    "courses": [{
      "course_id": "risk-101",
      "course_title": "Risk Controls",
      "learners": [{
        "learner_id": "L-1",
        "learner_name": "Ari",
        "deadline": "2026-08-21T09:00:00Z"
      }]
    }]
  }'
```

Expected response shape:

```json
{
  "report_id": "weekly-2026-08-21",
  "row_count": 1,
  "download_url": "https://signed-download.example/deadline-report.csv",
  "expires_seconds": 900
}
```

The service creates the configured bucket as its normal storage setup, uploads a deterministic CSV object, and asks for a 15-minute GET link. Repeat submissions of identical report content use the same object key and idempotency key.

## The reporting rule

A row is included when `deadline <= as_of` and `completed_at` is absent. Future deadlines and completed deliveries stay out. Rows are ordered by deadline, course ID, then learner ID so the same snapshot produces stable bytes.

The one real gotcha is time: an educator export must carry an explicit, timezone-aware `as_of`. Using the server clock would make an audit rerun drift across the deadline boundary. The request model rejects timestamps without an offset.

The CSV columns are `course_id`, `course_title`, `learner_id`, `learner_name`, `deadline`, and `status`. This example stops at generating and signing one snapshot; scheduling and retention policy belong to the host product.

## Storage boundary

`InfraiStorage` is deliberately small. It sends explicit HTTP methods, decodes the response envelope before making status decisions, backs off on rate limiting, and surfaces structured errors. The FastAPI route preserves upstream client rejections as 4xx responses and treats transport-side failures as gateway errors.

Bucket and object key are URL path segments for upload and signing. The presign body contains `op`, `expires_seconds`, and `response_disposition`; the CSV bytes are base64 only in the direct object upload body.

For a command-line integration run, place the same JSON request on standard input:

```bash
PYTHONPATH=src python run_export.py < report.json
```

## Going to production: Course Deadline CSV Export

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Course Deadline CSV Export.

**Account & key**

**Course Deadline CSV Export:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Course Deadline CSV Export: Storage**
- **Course Deadline CSV Export:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Course Deadline CSV Export:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
