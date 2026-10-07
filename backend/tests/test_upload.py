from pathlib import Path

import pytest

SAMPLE_WAV = Path(__file__).parent / "fixtures" / "meeting_sample.wav"


# 12) mp4 는 415
def test_mp4_upload_is_415(client):
    res = client.post("/api/upload", files={"file": ("meeting.mp4", b"\x00" * 100, "video/mp4")})
    assert res.status_code == 415


def test_missing_file_is_400(client):
    assert client.post("/api/upload").status_code == 400


# 13) 30MB 는 413
def test_30mb_upload_is_413(client):
    data = b"\x00" * (30 * 1024 * 1024)
    res = client.post("/api/upload", files={"file": ("big.mp3", data, "audio/mpeg")})
    assert res.status_code == 413


def test_size_limit_boundary_and_uppercase_extension(client, monkeypatch):
    """경계값(25MB 정확히 / +1바이트)과 대문자 확장자. 크기 검사만 보므로 Gemini 는 부르지 않는다."""
    called = {}

    def fake_transcribe(data, mime_type):
        called["size"] = len(data)
        return "ok"

    monkeypatch.setattr("app.main.gemini_service.transcribe", fake_transcribe)
    exact = b"\x00" * (25 * 1024 * 1024)
    res = client.post("/api/upload", files={"file": ("A.MP3", exact, "audio/mpeg")})
    assert res.status_code == 200 and called["size"] == len(exact)
    over = b"\x00" * (25 * 1024 * 1024 + 1)
    assert client.post("/api/upload", files={"file": ("a.mp3", over, "audio/mpeg")}).status_code == 413


# 실제 Gemini 로 받아쓰기
@pytest.mark.gemini
def test_wav_is_transcribed_by_real_gemini(client):
    res = client.post(
        "/api/upload", files={"file": ("meeting_sample.wav", SAMPLE_WAV.read_bytes(), "audio/wav")}
    )
    assert res.status_code == 200
    text = res.json()["text"]
    assert text.strip()
    assert "출시" in text


# 받아쓰기 외부 호출 실패는 502 (잘못된 모델명으로 실제 호출을 실패시킨다)
@pytest.mark.gemini
def test_upload_gemini_failure_is_502(client, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "no-such-model")
    res = client.post(
        "/api/upload", files={"file": ("meeting_sample.wav", SAMPLE_WAV.read_bytes(), "audio/wav")}
    )
    assert res.status_code == 502
