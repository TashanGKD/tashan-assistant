import json
import uuid
from pathlib import Path

from .config import settings

class LocalStore:
    """开发兜底。正式课堂应配置飞书。"""

    def __init__(self):
        self.path = Path(settings.local_store_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def _write(self, rows: list[dict]) -> None:
        self.path.write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )

    def create_case(self, fields: dict) -> str:
        record_id = "local_" + uuid.uuid4().hex[:12]
        rows = self._read()
        rows.append({"record_id": record_id, **fields})
        self._write(rows)
        return record_id

    def update_case(self, record_id: str, fields: dict) -> None:
        rows = self._read()
        for row in rows:
            if row.get("record_id") == record_id:
                row.update(fields)
                break
        self._write(rows)

    def list_cases(self, lesson_id: int | None = None) -> list[dict]:
        rows = self._read()
        if lesson_id is not None:
            rows = [x for x in rows if str(x.get("课次")) == str(lesson_id)]
        return rows

    def save_report(self, fields: dict) -> str:
        report_path = self.path.with_name("reports.jsonl")
        rows = []
        if report_path.exists():
            for line in report_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        record_id = "report_" + uuid.uuid4().hex[:12]
        rows.append({"record_id": record_id, **fields})
        report_path.write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n",
            encoding="utf-8",
        )
        return record_id
