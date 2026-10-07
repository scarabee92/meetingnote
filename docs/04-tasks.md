# 04. Tasks

MVP 를 3개 Phase 로 진행한다. Phase 이름과 개수는 고정이며 변경하지 않는다.

| Phase | 이름 | 단계 수 |
|---|---|---|
| 1 | 설계 | 10 |
| 2 | 백엔드 | 10 |
| 3 | 프론트 | 8 |

## 진행 규칙

- 순서대로만 진행한다. 병렬로 하지 않는다.
- 단계마다 검증을 거친다. 검증 없이 `[x]` 로 바꾸지 않는다.
- 완료 열은 `[ ]` 체크박스이고, 진행하면서 `[x]` 로 바꾼다.
- 'backend 진행해' = Phase 2 전체, 'frontend 진행해' = Phase 3 전체.
- 단계 수는 Phase 1 - 10단계 / Phase 2 - 10단계 / Phase 3 - 8단계로 고정한다.

## 고정 값

- 서버 포트: **8000**
- Phase 2 의존성은 아래 8개로 한정한다. 이 목록 밖은 추가하지 않는다.
  `fastapi`, `uvicorn`, `sqlalchemy`, `pytest`, `httpx`, `google-genai`, `python-multipart`, `python-dotenv`
- pytest 실행 시 httpx2 설치 권고가 떠도 무시한다.

## Phase 1 - 설계

CLAUDE.md + docs/ 6종 작성.

| 단계 | 검증 방법 | 완료 |
|---|---|---|
| 1.1 CLAUDE.md 4개 섹션 작성 (역할 / 기술 스택 / 시작 전 절차 / 절대규칙) | CLAUDE.md 에 4개 섹션이 모두 있음 | [x] |
| 1.2 `.env` 생성 (`GEMINI_API_KEY`, `GEMINI_MODEL`, 키 값은 비움) | `.env` 에 변수명 2개가 있고 키 값이 비어 있음 | [x] |
| 1.3 `.gitignore` 생성 | `.env` 가 무시 목록에 있음 | [x] |
| 1.4 `docs/` 에 6개 파일 생성 | 6개 이름이 CLAUDE.md 의 이름·순서와 같음 | [x] |
| 1.5 00-overview.md 작성 | 매핑표, 읽는 순서, 화면 4종, 분리 이유가 있음 | [x] |
| 1.6 01-product.md 작성 | 목표, 페르소나, MVP 범위, 범위 외, 성공 기준이 있음 | [x] |
| 1.7 02-specs.md 작성 | 모델 8필드, API 7개, 에러 코드가 있음 | [x] |
| 1.8 03-design.md 작성 | 8행 표, id 표, 의존성 정책이 있음 | [x] |
| 1.9 04-tasks.md 작성 | 3개 Phase 의 단계 수가 10 / 10 / 8 임 | [x] |
| 1.10 05-conventions.md 작성 + 첫 커밋 | 파일에 내용이 있고, `git log` 에 첫 커밋이 보이며 `.env` 가 커밋에 없음 | [x] |

## Phase 2 - 백엔드

`backend/` FastAPI > API 7개 + 받아쓰기 > Swagger 확인.

| 단계 | 검증 방법 | 완료 |
|---|---|---|
| 2.1 `backend/` 뼈대와 가상환경, 의존성 8개 설치 (`requirements.txt`) | `pip list` 에 8개만 추가되고 서버가 8000 포트에서 기동됨 | [x] |
| 2.2 `.env` 읽기 (`python-dotenv`) | pytest: 환경 변수에서 키와 모델명을 읽음. 코드에 키 문자열이 없음 | [x] |
| 2.3 Meeting 모델 8필드와 DB 세션 (SQLAlchemy, `sqlite_autoincrement`) | pytest: 행을 지우고 새로 넣어도 id 가 재사용되지 않음 | [x] |
| 2.4 요청 스키마(`extra="forbid"`)와 검증 예외 핸들러 | pytest: 필수 필드 누락은 400, 스펙 외 필드는 422 | [x] |
| 2.5 `POST /api/notes`, `GET /api/notes`, `GET /api/notes/{id}` | pytest: 201 / 200 / 404, 목록엔 body 가 없고 단건엔 있음 | [x] |
| 2.6 목록 검색 (`q`, `from`, `to`) | pytest: 제목·참석자 부분 일치, 본문은 검색 안 됨, `to` 는 그날 23:59:59 까지 | [x] |
| 2.7 `PUT /api/notes/{id}`, `DELETE /api/notes/{id}` | pytest: 수정 200, 삭제 204, 없는 id 는 404 | [x] |
| 2.8 `GET /api/todos` | pytest: what / who / when / note_id / note_title 필드, 회의 날짜 오래된 순 | [x] |
| 2.9 `POST /api/upload` (Gemini 받아쓰기) + 세 갈래 구분 연결 | pytest(실제 Gemini 호출, 05-conventions 따라 호출 사이 1초 간격): mp3·wav 외 415, 25MB 초과 413, 외부 실패 502, 구분 실패 시 201 + 빈 값 | [x] |
| 2.10 전체 테스트와 Swagger 확인 | `pytest` 전체 통과, `http://localhost:8000/docs` 에서 7개 경로가 보임 | [x] |

## Phase 3 - 프론트

`frontend/` HTML+JS+Tailwind > 화면 4종 > API 연결 > git push.

화면 4종은 02-specs 화면 명세와 03-design 표대로 만든다. 파일은 `index.html` 과 `app.js` 2개만 쓴다.

| 단계 | 검증 방법 | 완료 |
|---|---|---|
| 3.1 뼈대: `index.html` + `app.js`, 백엔드가 같은 오리진에서 제공, 공통 헤더·탭 3개·테마 토글 | `http://localhost:8000/` 에서 열림. 테마가 새로고침 후에도 유지되고 초기값은 시스템 설정 | [ ] |
| 3.2 목록 화면 | 카드 2열(360px 에서 1열), 검색 입력 3개가 보임 | [ ] |
| 3.3 넣기 화면 | 폼, 파일, 본문, 버튼 2개, 결과 세 칸이 03-design 배치대로 보임 | [ ] |
| 3.4 상세 화면 | 카드를 누르면 겹침 창이 뜨고, 바깥을 누르면 닫힘. 삭제는 한 번 더 눌러야 지워짐 | [ ] |
| 3.5 할 일 화면 | 담당자·기한·회의 열이 있는 표. 좁은 화면에서 표만 가로 스크롤되고 문서 전체는 안 됨 | [ ] |
| 3.6 요소 이름 확인 | 코드의 id 가 03-design 표의 id(`q` `from` `to` `cards` `title` `metAt` `attendees` `file` `body` `btnUp` `btnSave` `result` `modal` `mTitle` `todoBody`)와 모두 같음. 빠지거나 다른 이름이 없음 | [ ] |
| 3.7 API 연결 | 녹취 파일이 세 갈래로 저장되고 새로고침해도 유지됨. 검색으로 지난 회의를 찾음. 360px 에서 안 깨짐 (01-product 성공 기준 4개) | [ ] |
| 3.8 git push | 원격 저장소에 push 되고 `.env` 가 올라가지 않음 | [ ] |
