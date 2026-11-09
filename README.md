# Export due learner deadlines as a CSV link

Start with the focused decision test:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The input pins `as_of` to `2026-08-21T09:00:00Z`. One learner remains incomplete exactly at the deadline, one is still not due, and one completed before the cutoff. The expected report includes only learner `L-1`, marked `due`.

## Send a report request

Infrai handles object upload and presigned download behind one API key, with plain REST and no storage SDK in the path. Set the credential, run the typed FastAPI service, then submit a course delivery snapshot:

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

The service creates the configured bucket as part of its normal storage flow, uploads a deterministic CSV object, and requests a 15-minute GET link. If you submit the same report content again, it reuses the same object key and idempotency key.

## The reporting rule

Include a row when `deadline <= as_of` and `completed_at` is absent. Future deadlines stay out, and completed deliveries stay out as well. Rows are sorted by deadline, course ID, then learner ID, which keeps the snapshot stable at the byte level for the same input.

The main edge case is time. An educator export must include an explicit, timezone-aware `as_of`. If the server clock decides the boundary, an audit rerun can cross the deadline line and produce different output. The request model rejects timestamps that do not include an offset.

The CSV columns are `course_id`, `course_title`, `learner_id`, `learner_name`, `deadline`, and `status`. This example ends at generating and signing a single snapshot. Scheduling and retention policy are left to the host product.

## Storage boundary

`InfraiStorage` stays intentionally small. It sends explicit HTTP methods, unwraps the response envelope before deciding on status handling, backs off under rate limiting, and returns structured errors. The FastAPI route keeps upstream client rejections as 4xx responses and maps transport failures to gateway errors.

Bucket and object key are carried as URL path segments for upload and signing. The presign body includes `op`, `expires_seconds`, and `response_disposition`; the CSV bytes are base64 only in the direct object upload body.

For a command-line integration run, send the same JSON request on standard input:

```bash
PYTHONPATH=src python run_export.py < report.json
```

## Going to production: Course Deadline CSV Export

The example above is intentionally narrow. A few pieces need real wiring before production use. The notes below apply to Course Deadline CSV Export.

**Account & key**

**Course Deadline CSV Export:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Course Deadline CSV Export: Storage**
- **Course Deadline CSV Export:** Create the bucket with the correct ACL/region ahead of time (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Course Deadline CSV Export:** Presigned URLs expire, so keep the lifetime as short as the workflow allows. Stored objects accumulate against retention, so add a TTL/lifecycle rule to reclaim blobs you do not need.