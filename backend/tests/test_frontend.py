"""프론트 점검: 파일 구성, 같은 오리진 제공, 03-design id 표와의 일치 (04-tasks 3.6)."""
import re

from app.config import FRONTEND_DIR

# 03-design.md 의 id 표 (순서 그대로)
DESIGN_IDS = [
    "q", "from", "to", "cards", "title", "metAt", "attendees", "file", "body",
    "btnUp", "btnSave", "result", "modal", "mTitle", "todoBody",
]


def test_frontend_has_only_two_files():
    assert sorted(p.name for p in FRONTEND_DIR.iterdir()) == ["app.js", "index.html"]


def test_html_ids_match_design_table_exactly():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert sorted(ids) == sorted(DESIGN_IDS)


def test_js_looks_up_only_design_ids():
    js = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
    used = set(re.findall(r"byId\('([^']+)'\)", js))
    assert used == set(DESIGN_IDS)


def test_no_inline_styles_or_important():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    assert "<style" not in html
    assert "!important" not in html


def test_frontend_is_served_from_same_origin(client):
    index = client.get("/")
    assert index.status_code == 200
    assert "MeetingNote" in index.text
    assert client.get("/app.js").status_code == 200
    # 프론트 마운트가 API 와 Swagger 를 가리지 않는다
    assert client.get("/api/notes").status_code == 200
    assert client.get("/docs").status_code == 200
