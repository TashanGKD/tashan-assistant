import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_nine_lessons_are_present():
    lessons = json.loads((ROOT / "knowledge" / "lessons.json").read_text(encoding="utf-8"))
    assert [x["id"] for x in lessons] == list(range(1, 10))
    for lesson in lessons:
        assert (ROOT / "knowledge" / "lessons" / f"{lesson['id']:02d}.md").exists()
