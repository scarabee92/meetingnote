// MeetingNote 프론트: 모듈 변수 + DOM 직접 갱신 (03-design 6번)
// 요소 id 는 03-design 의 id 표를 그대로 쓴다. 그 밖의 요소는 data-* 로 찾는다.
'use strict';

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const SEARCH_DELAY_MS = 250;
const DELETE_CONFIRM_MS = 3000;
const TOAST_MS = 2600;

// ---------- 상태 ----------
let currentTab = 'list';
let searchTimer = null;
let listRequestSeq = 0;
let openedNote = null;
let deleteArmedTimer = null;
let toastTimer = null;

// ---------- 요소 ----------
const byId = (id) => document.getElementById(id);
const pick = (selector, root = document) => root.querySelector(selector);

const ui = {
  q: byId('q'),
  from: byId('from'),
  to: byId('to'),
  cards: byId('cards'),
  title: byId('title'),
  metAt: byId('metAt'),
  attendees: byId('attendees'),
  file: byId('file'),
  body: byId('body'),
  btnUp: byId('btnUp'),
  btnSave: byId('btnSave'),
  result: byId('result'),
  modal: byId('modal'),
  mTitle: byId('mTitle'),
  todoBody: byId('todoBody'),
  listEmpty: pick('[data-role="list-empty"]'),
  upStatus: pick('[data-role="up-status"]'),
  saveStatus: pick('[data-role="save-status"]'),
  theme: pick('[data-role="theme"]'),
  toast: pick('[data-role="toast"]'),
  mHeading: pick('[data-role="m-heading"]'),
  mMeta: pick('[data-role="m-meta"]'),
  mSummary: pick('[data-role="m-summary"]'),
  mDecisions: pick('[data-role="m-decisions"]'),
  mTodos: pick('[data-role="m-todos"]'),
  mBody: pick('[data-role="m-body"]'),
  mHint: pick('[data-role="m-hint"]'),
  mClose: pick('[data-role="m-close"]'),
  mRename: pick('[data-role="m-rename"]'),
  mDelete: pick('[data-role="m-delete"]'),
};

// ---------- 공통 도구 ----------
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(path, options);
  } catch (err) {
    throw new ApiError(0, '서버에 연결하지 못했습니다.');
  }
  if (!res.ok) {
    throw new ApiError(res.status, `요청에 실패했습니다 (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

function showToast(message) {
  const text = pick('p', ui.toast);
  text.textContent = message;
  ui.toast.classList.remove('opacity-0');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ui.toast.classList.add('opacity-0'), TOAST_MS);
}

function pad(n) {
  return String(n).padStart(2, '0');
}

// 서버는 UTC(Z)로 주므로 화면에는 로컬 시각으로 보여 준다
function formatLocal(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// datetime-local 값(로컬 시각)을 UTC ISO 로 바꿔 보낸다
function localInputToUtcIso(value) {
  return new Date(value).toISOString();
}

function nowAsLocalInput() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function splitLines(text) {
  return (text || '').split('\n').map((line) => line.trim()).filter(Boolean);
}

// todos 한 줄: 내용 | 담당자 | 기한  (내용에 | 가 있어도 뒤에서부터 나눈다)
function parseTodoLine(line) {
  const parts = line.split('|').map((p) => p.trim());
  while (parts.length < 3) parts.push('');
  const when = parts.pop();
  const who = parts.pop();
  return { what: parts.join(' | '), who, when };
}

function fillList(container, lines, emptyText) {
  container.replaceChildren();
  if (lines.length === 0) {
    container.append(el('p', 'text-slate-400', emptyText));
    return;
  }
  const ul = el('ul', 'list-disc space-y-1 pl-5');
  lines.forEach((line) => ul.append(el('li', '', line)));
  container.append(ul);
}

function todoLinesForView(text) {
  return splitLines(text).map((line) => {
    const { what, who, when } = parseTodoLine(line);
    return `${what} · ${who || '미정'}${when ? ` · ${when}` : ''}`;
  });
}

// ---------- 테마 ----------
function applyTheme(theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark');
}

function toggleTheme() {
  const next = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
  applyTheme(next);
  try {
    localStorage.setItem('theme', next);
  } catch (err) {
    // 저장이 막힌 환경에서는 이번 화면에서만 바뀐다
  }
}

// ---------- 탭 ----------
const TAB_ON = ['bg-slate-900', 'text-white', 'dark:bg-white', 'dark:text-slate-900'];
const TAB_OFF = ['text-slate-600', 'hover:bg-black/5', 'dark:text-slate-300', 'dark:hover:bg-white/10'];

function showTab(name) {
  currentTab = name;
  document.querySelectorAll('[data-screen]').forEach((section) => {
    section.classList.toggle('hidden', section.dataset.screen !== name);
  });
  document.querySelectorAll('[data-tab]').forEach((button) => {
    const on = button.dataset.tab === name;
    button.classList.remove(...TAB_ON, ...TAB_OFF);
    button.classList.add(...(on ? TAB_ON : TAB_OFF));
    button.setAttribute('aria-current', on ? 'page' : 'false');
  });
  if (name === 'list') loadNotes();
  if (name === 'todo') loadTodos();
}

// ---------- 화면 1: 목록 ----------
function buildQuery() {
  const params = new URLSearchParams();
  if (ui.q.value.trim()) params.set('q', ui.q.value.trim());
  if (ui.from.value) params.set('from', ui.from.value);
  if (ui.to.value) params.set('to', ui.to.value);
  const text = params.toString();
  return text ? `?${text}` : '';
}

async function loadNotes() {
  const seq = ++listRequestSeq;
  let notes;
  try {
    notes = await api(`/api/notes${buildQuery()}`);
  } catch (err) {
    if (seq === listRequestSeq) showToast(err.message);
    return;
  }
  if (seq !== listRequestSeq) return; // 더 최근 검색이 있으면 이 결과는 버린다
  renderCards(notes);
}

function renderCards(notes) {
  ui.cards.replaceChildren();
  const searching = ui.q.value.trim() || ui.from.value || ui.to.value;
  ui.listEmpty.classList.toggle('hidden', notes.length > 0);
  ui.listEmpty.textContent = searching
    ? '조건에 맞는 회의록이 없습니다.'
    : '아직 회의록이 없습니다. 넣기 탭에서 첫 회의록을 만들어 보세요.';
  notes.forEach((note) => ui.cards.append(buildCard(note)));
}

function buildCard(note) {
  const card = el(
    'button',
    'block w-full rounded-2xl border border-black/5 bg-white/70 p-5 text-left shadow-lg shadow-slate-900/5 backdrop-blur-xl transition hover:-translate-y-0.5 hover:shadow-xl dark:border-white/10 dark:bg-slate-800/50',
  );
  card.type = 'button';
  const meta = [formatLocal(note.met_at), note.attendees].filter(Boolean).join(' · ');
  const firstLine = splitLines(note.summary)[0];
  card.append(
    el('h3', 'break-words text-base font-semibold', note.title),
    el('p', 'mt-1 text-xs text-slate-500 dark:text-slate-400', meta),
    el(
      'p',
      firstLine ? 'mt-3 line-clamp-2 text-sm text-slate-700 dark:text-slate-200' : 'mt-3 text-sm text-slate-400',
      firstLine || '요약 없음',
    ),
  );
  card.addEventListener('click', () => openModal(note.id));
  return card;
}

function scheduleSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadNotes, SEARCH_DELAY_MS);
}

// ---------- 화면 2: 넣기 ----------
function setStatus(node, message, isError = false) {
  node.textContent = message;
  node.classList.toggle('text-red-500', isError);
  node.classList.toggle('text-slate-500', !isError);
  node.classList.toggle('dark:text-slate-400', !isError);
}

function uploadErrorMessage(err) {
  if (err.status === 415) return 'mp3, wav 파일만 올릴 수 있습니다.';
  if (err.status === 413) return '25MB 이하 파일만 올릴 수 있습니다.';
  if (err.status === 502) return '받아쓰기에 실패했습니다. 잠시 뒤 다시 시도해 주세요.';
  return err.message;
}

async function transcribe() {
  const file = ui.file.files[0];
  if (!file) {
    setStatus(ui.upStatus, '녹취 파일을 먼저 선택해 주세요.', true);
    return;
  }
  if (!/\.(mp3|wav)$/i.test(file.name)) {
    setStatus(ui.upStatus, 'mp3, wav 파일만 올릴 수 있습니다.', true);
    return;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    setStatus(ui.upStatus, '25MB 이하 파일만 올릴 수 있습니다.', true);
    return;
  }
  const form = new FormData();
  form.append('file', file);
  ui.btnUp.disabled = true;
  setStatus(ui.upStatus, '받아쓰는 중입니다. 파일이 길면 시간이 걸립니다...');
  try {
    const data = await api('/api/upload', { method: 'POST', body: form });
    ui.body.value = data.text;
    setStatus(ui.upStatus, data.text ? '받아쓰기가 끝났습니다. 본문을 확인해 주세요.' : '들린 내용이 없습니다.');
  } catch (err) {
    setStatus(ui.upStatus, uploadErrorMessage(err), true);
  } finally {
    ui.btnUp.disabled = false;
  }
}

function resultPart(name) {
  const part = pick(`[data-part="${name}"]`, ui.result);
  return { body: pick('[data-role="part-body"]', part), hint: pick('[data-role="part-hint"]', part) };
}

function renderResult(note) {
  const failed = !note.summary && !note.decisions && !note.todos;
  const summary = resultPart('summary');
  const decisions = resultPart('decisions');
  const todos = resultPart('todos');
  [summary, decisions, todos].forEach((part) => {
    part.hint.classList.add('hidden');
    part.body.replaceChildren();
  });
  if (failed) {
    // 구분에 실패해도 회의록은 저장돼 있다 (02-specs 7장)
    summary.body.append(el('p', 'font-medium text-red-500', '구분 실패'));
    summary.body.append(el('p', 'mt-1 text-slate-500', '본문은 저장됐습니다. 구분만 하지 못했습니다.'));
    return;
  }
  summary.body.textContent = note.summary;
  fillList(decisions.body, splitLines(note.decisions), '합의가 끝난 결정사항이 없습니다.');
  fillList(todos.body, todoLinesForView(note.todos), '담당자와 기한이 드러난 할 일이 없습니다.');
}

function resetResult() {
  ['summary', 'decisions', 'todos'].forEach((name) => {
    const part = resultPart(name);
    part.body.replaceChildren();
    part.hint.classList.remove('hidden');
  });
}

async function saveNote() {
  const title = ui.title.value.trim();
  const body = ui.body.value.trim();
  if (!title) return setStatus(ui.saveStatus, '제목을 입력해 주세요.', true);
  if (!ui.metAt.value) return setStatus(ui.saveStatus, '일시를 입력해 주세요.', true);
  if (!body) return setStatus(ui.saveStatus, '본문을 입력하거나 받아쓰기를 먼저 해 주세요.', true);

  ui.btnSave.disabled = true;
  resetResult();
  setStatus(ui.saveStatus, '정리하는 중입니다...');
  try {
    const note = await api('/api/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        met_at: localInputToUtcIso(ui.metAt.value),
        attendees: ui.attendees.value.trim() || null,
        body,
      }),
    });
    renderResult(note);
    setStatus(ui.saveStatus, '저장했습니다.');
    clearForm();
  } catch (err) {
    setStatus(ui.saveStatus, err.status === 400 ? '입력값을 확인해 주세요.' : err.message, true);
  } finally {
    ui.btnSave.disabled = false;
  }
}

// 같은 내용이 중복 저장되지 않도록 저장 뒤에는 입력칸을 비운다
function clearForm() {
  ui.title.value = '';
  ui.attendees.value = '';
  ui.body.value = '';
  ui.file.value = '';
  ui.metAt.value = nowAsLocalInput();
  setStatus(ui.upStatus, '');
}

// ---------- 화면 3: 상세 ----------
function setModalHint(message, isError = false) {
  ui.mHint.textContent = message;
  ui.mHint.classList.toggle('text-red-500', isError);
  ui.mHint.classList.toggle('text-slate-500', !isError);
}

function disarmDelete() {
  clearTimeout(deleteArmedTimer);
  ui.mDelete.textContent = '삭제';
  delete ui.mDelete.dataset.armed;
}

async function openModal(id) {
  let note;
  try {
    note = await api(`/api/notes/${id}`);
  } catch (err) {
    showToast(err.message);
    return;
  }
  openedNote = note;
  ui.mHeading.textContent = note.title;
  ui.mMeta.textContent = [formatLocal(note.met_at), note.attendees].filter(Boolean).join(' · ');
  ui.mSummary.textContent = note.summary || '요약 없음';
  fillList(ui.mDecisions, splitLines(note.decisions), '없음');
  fillList(ui.mTodos, todoLinesForView(note.todos), '없음');
  ui.mBody.textContent = note.body;
  pick('details', ui.modal).open = false;
  ui.mTitle.value = note.title;
  setModalHint('삭제는 한 번 더 눌러야 지워집니다.');
  disarmDelete();
  ui.modal.classList.remove('hidden');
  ui.modal.classList.add('flex');
}

function closeModal() {
  ui.modal.classList.add('hidden');
  ui.modal.classList.remove('flex');
  disarmDelete();
  openedNote = null;
}

async function renameNote() {
  if (!openedNote) return;
  const title = ui.mTitle.value.trim();
  if (!title) return setModalHint('제목을 입력해 주세요.', true);
  ui.mRename.disabled = true;
  try {
    // 필수 필드만 보내면 서버가 나머지 필드를 그대로 둔다
    const note = await api(`/api/notes/${openedNote.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, met_at: openedNote.met_at, body: openedNote.body }),
    });
    openedNote = note;
    ui.mHeading.textContent = note.title;
    setModalHint('제목을 고쳤습니다.');
    loadNotes();
  } catch (err) {
    setModalHint(err.status === 400 ? '제목은 200자 이하로 입력해 주세요.' : err.message, true);
  } finally {
    ui.mRename.disabled = false;
  }
}

async function deleteNote() {
  if (!openedNote) return;
  if (!ui.mDelete.dataset.armed) {
    // 첫 번째 누름: 확인 상태로 바꾼다
    ui.mDelete.dataset.armed = '1';
    ui.mDelete.textContent = '정말 삭제';
    setModalHint('한 번 더 누르면 지워지고 되돌릴 수 없습니다.', true);
    deleteArmedTimer = setTimeout(() => {
      disarmDelete();
      setModalHint('삭제는 한 번 더 눌러야 지워집니다.');
    }, DELETE_CONFIRM_MS);
    return;
  }
  const id = openedNote.id;
  ui.mDelete.disabled = true;
  try {
    await api(`/api/notes/${id}`, { method: 'DELETE' });
    closeModal();
    showToast('삭제했습니다.');
    loadNotes();
  } catch (err) {
    setModalHint(err.message, true);
  } finally {
    ui.mDelete.disabled = false;
  }
}

// ---------- 화면 4: 할일 ----------
async function loadTodos() {
  let todos;
  try {
    todos = await api('/api/todos');
  } catch (err) {
    showToast(err.message);
    return;
  }
  ui.todoBody.replaceChildren();
  if (todos.length === 0) {
    const row = el('tr');
    const cell = el('td', 'px-4 py-10 text-center text-slate-400', '아직 모아 볼 할 일이 없습니다.');
    cell.colSpan = 4;
    row.append(cell);
    ui.todoBody.append(row);
    return;
  }
  todos.forEach((todo) => {
    const row = el('tr');
    row.append(
      el('td', 'px-4 py-3', todo.what),
      el('td', 'whitespace-nowrap px-4 py-3', todo.who || '미정'),
      el('td', 'whitespace-nowrap px-4 py-3', todo.when || '-'),
      el('td', 'px-4 py-3 text-slate-500 dark:text-slate-400', todo.note_title),
    );
    ui.todoBody.append(row);
  });
}

// ---------- 연결 ----------
document.querySelectorAll('[data-tab]').forEach((button) => {
  button.addEventListener('click', () => showTab(button.dataset.tab));
});
ui.theme.addEventListener('click', toggleTheme);
[ui.q, ui.from, ui.to].forEach((input) => input.addEventListener('input', scheduleSearch));
ui.btnUp.addEventListener('click', transcribe);
ui.btnSave.addEventListener('click', saveNote);
ui.mRename.addEventListener('click', renameNote);
ui.mDelete.addEventListener('click', deleteNote);
ui.mClose.addEventListener('click', closeModal);
ui.modal.addEventListener('click', (event) => {
  if (event.target === ui.modal) closeModal(); // 바깥 어두운 영역
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && openedNote) closeModal();
});

ui.metAt.value = nowAsLocalInput();
showTab('list');
