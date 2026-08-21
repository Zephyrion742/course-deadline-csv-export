import json
import sys

from edtech_export.deadline_report import ExportRequest, export_deadline_report
from edtech_export.infrai_storage import InfraiStorage


def main() -> None:
    request = ExportRequest.model_validate(json.load(sys.stdin))
    result = export_deadline_report(request, InfraiStorage.from_environment(), "edtech-report-exports")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
