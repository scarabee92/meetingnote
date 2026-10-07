"""02-specs 와 05-conventions 의 테스트 매트릭스 (13케이스) + 보강."""
from datetime import datetime

import pytest

from app import gemini_service
from app.models import Meeting

VALID = {"title": "기획 회의", "met_at": "2026-10-07T01:00:00Z", "body": "원문"}

SAMPLE_BODY = (
    "오늘 회의에서는 다음 주 출시 일정을 논의했습니다. "
    "출시일은 다음 주 금요일로 확정했습니다. "
    "김대리가 이번 주 안에 테스트 보고서를 작성하기로 했습니다. "
    "점심은 뭘 먹을지는 정하지 못했습니다."
)


# 1) 정상 생성 - 실제 Gemini 로 세 갈래까지 구분
@pytest.mark.gemini
def test_create_note_classifies_into_three_parts(client):
    res = client.post(
        "/api/notes", json={**VALID, "attendees": "김대리, 이주임", "body": SAMPLE_BODY}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"] >= 1
    assert data["body"] == SAMPLE_BODY
    assert data["summary"].strip()
    assert data["decisions"].strip()
    todo_lines = data["todos"].splitlines()
    assert todo_lines and all(line.count(" | ") == 2 for line in todo_lines)
    assert any("김대리" in line for line in todo_lines)
    # 저장 확인: 다시 읽어도 같다
    assert client.get(f"/api/notes/{data['id']}").json() == data


# 2) 목록 - body 없음
def test_list_notes_excludes_body(client, make_note):
    make_note()
    res = client.get("/api/notes")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert "body" not in items[0]
    assert items[0]["summary"] == "요약"


# 3) 단건 - body 있음
def test_get_note_includes_body(client, make_note):
    note_id = make_note()
    res = client.get(f"/api/notes/{note_id}")
    assert res.status_code == 200
    assert res.json()["body"] == "원문"


# 4) 수정 - 전 필드
def test_update_all_fields(client, make_note):
    note_id = make_note()
    payload = {
        "title": "수정된 제목",
        "met_at": "2026-11-01T09:30:00Z",
        "attendees": "박과장",
        "body": "수정 원문",
        "summary": "수정 요약",
        "decisions": "수정 결정",
        "todos": "할 일 | 박과장 | 내일",
    }
    res = client.put(f"/api/notes/{note_id}", json=payload)
    assert res.status_code == 200
    data = res.json()
    for key, value in payload.items():
        assert data[key] == value
    assert client.get(f"/api/notes/{note_id}").json()["title"] == "수정된 제목"


def test_update_required_only_keeps_optional_fields(client, make_note):
    note_id = make_note()
    res = client.put(
        f"/api/notes/{note_id}",
        json={"title": "새 제목", "met_at": "2026-10-07T01:00:00Z", "body": "원문"},
    )
    assert res.status_code == 200
    assert res.json()["summary"] == "요약"
    assert res.json()["attendees"] == "김대리, 이주임"


# 5) 삭제
def test_delete_note(client, make_note):
    note_id = make_note()
    res = client.delete(f"/api/notes/{note_id}")
    assert res.status_code == 204
    assert res.content == b""
    assert client.get(f"/api/notes/{note_id}").status_code == 404


# 6) 검색 - 제목·참석자 일치만, 본문은 제외
def test_search_matches_title_and_attendees_only(client, make_note):
    by_title = make_note(title="신제품 기획 회의", attendees="김대리", body="x")
    by_attendee = make_note(title="주간 회의", attendees="기획팀 박과장", body="x")
    make_note(title="주간 회의", attendees="이주임", body="이 본문에는 기획이 들어 있다")
    res = client.get("/api/notes", params={"q": "기획"})
    assert res.status_code == 200
    assert {item["id"] for item in res.json()} == {by_title, by_attendee}


def test_search_treats_percent_literally(client, make_note):
    make_note(title="일반 회의")
    make_note(title="100% 달성 회의")
    res = client.get("/api/notes", params={"q": "%"})
    assert [item["title"] for item in res.json()] == ["100% 달성 회의"]


def test_date_range_is_inclusive_through_end_of_day(client, make_note):
    before = make_note(title="전날", met_at=datetime(2026, 10, 6, 23, 59, 59))
    first = make_note(title="시작일", met_at=datetime(2026, 10, 7, 0, 0, 0))
    last = make_note(title="종료일", met_at=datetime(2026, 10, 8, 23, 59, 59))
    after = make_note(title="다음날", met_at=datetime(2026, 10, 9, 0, 0, 0))
    res = client.get("/api/notes", params={"from": "2026-10-07", "to": "2026-10-08"})
    ids = {item["id"] for item in res.json()}
    assert ids == {first, last}
    assert before not in ids and after not in ids


def test_invalid_date_filter_is_400(client):
    assert client.get("/api/notes", params={"from": "10/07/2026"}).status_code == 400


# 7) 할 일
def test_todos_sorted_by_meeting_date_ascending(client, make_note):
    new_id = make_note(
        title="나중 회의", met_at=datetime(2026, 10, 9), todos="C 작업 | 이주임 | 다음 달 10일"
    )
    old_id = make_note(
        title="먼저 회의",
        met_at=datetime(2026, 10, 1),
        todos="A 작업 | 김대리 | 다음 주 금요일\nB 작업 | 미정 | 이번 주 안",
    )
    make_note(title="할 일 없음", todos="")
    res = client.get("/api/todos")
    assert res.status_code == 200
    assert res.json() == [
        {"what": "A 작업", "who": "김대리", "when": "다음 주 금요일", "note_id": old_id, "note_title": "먼저 회의"},
        {"what": "B 작업", "who": "미정", "when": "이번 주 안", "note_id": old_id, "note_title": "먼저 회의"},
        {"what": "C 작업", "who": "이주임", "when": "다음 달 10일", "note_id": new_id, "note_title": "나중 회의"},
    ]


# 8) title 누락 (+ met_at, body 누락, 빈 값)
@pytest.mark.parametrize("missing", ["title", "met_at", "body"])
def test_missing_required_field_is_400(client, missing):
    payload = {k: v for k, v in VALID.items() if k != missing}
    assert client.post("/api/notes", json=payload).status_code == 400


def test_blank_title_is_400(client):
    assert client.post("/api/notes", json={**VALID, "title": "   "}).status_code == 400


def test_title_over_200_chars_is_400(client):
    assert client.post("/api/notes", json={**VALID, "title": "가" * 201}).status_code == 400


def test_update_missing_required_field_is_400(client, make_note):
    note_id = make_note()
    res = client.put(f"/api/notes/{note_id}", json={"met_at": "2026-10-07T01:00:00Z", "body": "x"})
    assert res.status_code == 400


# 9) met_at 형식 오류
def test_invalid_met_at_is_400(client):
    assert client.post("/api/notes", json={**VALID, "met_at": "어제 오후"}).status_code == 400


# 10) 없는 id
def test_unknown_id_is_404(client):
    assert client.get("/api/notes/9999").status_code == 404
    assert client.delete("/api/notes/9999").status_code == 404
    assert client.put("/api/notes/9999", json=VALID).status_code == 404


# 11) 스펙 외 필드
def test_unknown_field_is_422(client):
    res = client.post("/api/notes", json={**VALID, "unknown": "x"})
    assert res.status_code == 422


def test_client_cannot_send_id_or_three_parts_on_create(client):
    assert client.post("/api/notes", json={**VALID, "id": 5}).status_code == 422
    assert client.post("/api/notes", json={**VALID, "summary": "x"}).status_code == 422


# 보강: UTC 저장·표시
def test_met_at_with_offset_is_stored_as_utc(client, session_factory):
    res = client.post("/api/notes", json={**VALID, "met_at": "2026-10-07T09:30:00+09:00"})
    assert res.status_code == 201
    assert res.json()["met_at"] == "2026-10-07T00:30:00Z"
    with session_factory() as db:
        assert db.get(Meeting, res.json()["id"]).met_at == datetime(2026, 10, 7, 0, 30, 0)


# 보강: 구분 실패해도 201, 세 갈래는 빈 값 (잘못된 모델명으로 실제 호출을 실패시킨다)
@pytest.mark.gemini
def test_classify_failure_still_saves_with_empty_parts(client, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "no-such-model")
    res = client.post("/api/notes", json={**VALID, "body": SAMPLE_BODY})
    assert res.status_code == 201
    data = res.json()
    assert (data["summary"], data["decisions"], data["todos"]) == ("", "", "")
    assert client.get(f"/api/notes/{data['id']}").json()["body"] == SAMPLE_BODY


def test_gemini_client_is_reused():
    assert gemini_service.get_client() is gemini_service.get_client()
