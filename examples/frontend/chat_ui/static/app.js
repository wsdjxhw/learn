const state = {
  sessions: [],
  activeSessionId: null,
  pollingTimer: null,
};

const sessionList = document.getElementById("session-list");
const messageList = document.getElementById("message-list");
const sessionTitleInput = document.getElementById("session-title");
const saveTitleButton = document.getElementById("save-title-button");
const newSessionButton = document.getElementById("new-session-button");
const composer = document.getElementById("composer");
const messageInput = document.getElementById("message-input");
const taskStatus = document.getElementById("task-status");
const sourceList = document.getElementById("source-list");

async function api(path, options = {}) {
  // 统一封装 fetch：
  // 页面其它地方只关心“调用哪个 API”，不用每次重复写错误处理。
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const message = payload.detail || payload.message || `HTTP ${response.status}`;
    throw new Error(message);
  }

  return response.json();
}

function setTaskStatus(text, status = "") {
  // 任务状态会显示在右侧面板。
  // status 同时作为 class，用于区分 running / failed 等视觉状态。
  taskStatus.className = `task-status ${status}`.trim();
  taskStatus.textContent = text;
}

function renderSources(sources) {
  // sources 是 RAG 或检索结果的来源列表。
  // 这里展示 title、snippet、score，让用户能看到回答参考了什么。
  sourceList.innerHTML = "";

  if (!sources || sources.length === 0) {
    sourceList.innerHTML = '<p class="empty-note">暂无 sources</p>';
    return;
  }

  for (const source of sources) {
    const item = document.createElement("article");
    item.className = "source-item";
    item.innerHTML = `
      <div class="source-title">
        <span>${escapeHtml(source.title)}</span>
        <span class="source-score">${Number(source.score).toFixed(1)}</span>
      </div>
      <p class="source-snippet">${escapeHtml(source.snippet)}</p>
    `;
    sourceList.appendChild(item);
  }
}

function renderSessions() {
  // 根据后端返回的 sessions 渲染左侧会话列表。
  // 当前选中的会话会加 active class。
  sessionList.innerHTML = "";

  for (const session of state.sessions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `session-item ${session.id === state.activeSessionId ? "active" : ""}`;
    button.innerHTML = `
      <span class="session-title">${escapeHtml(session.title)}</span>
      <span class="session-meta">${session.message_count} 条消息</span>
    `;
    button.addEventListener("click", () => selectSession(session.id));
    sessionList.appendChild(button);
  }
}

function renderMessages(messages) {
  // 消息列表按 role 分成 user 和 assistant 两种样式。
  // 数据来自 GET /api/sessions/{session_id}/messages。
  messageList.innerHTML = "";

  if (messages.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-note";
    empty.textContent = "暂无消息";
    messageList.appendChild(empty);
    return;
  }

  for (const message of messages) {
    const item = document.createElement("article");
    item.className = `message ${message.role}`;
    item.innerHTML = `
      <div class="message-role">${message.role}</div>
      <div>${escapeHtml(message.content)}</div>
    `;
    messageList.appendChild(item);
  }

  messageList.scrollTop = messageList.scrollHeight;
}

async function loadSessions() {
  // 页面启动和消息变化后都会重新加载会话列表。
  // 这样 message_count 和排序能及时更新。
  const payload = await api("/api/sessions");
  state.sessions = payload.items;

  if (!state.activeSessionId && state.sessions.length > 0) {
    state.activeSessionId = state.sessions[0].id;
  }

  renderSessions();
  syncTitleInput();
}

async function selectSession(sessionId) {
  // 切换会话时，需要同时刷新标题、消息列表和右侧 sources。
  state.activeSessionId = sessionId;
  renderSessions();
  syncTitleInput();
  renderSources([]);
  setTaskStatus("暂无任务");
  const payload = await api(`/api/sessions/${sessionId}/messages`);
  renderMessages(payload.items);
}

function syncTitleInput() {
  const session = state.sessions.find((item) => item.id === state.activeSessionId);
  sessionTitleInput.value = session ? session.title : "";
}

async function createSession() {
  // 新建会话后立刻切换到新会话。
  const session = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ title: "新会话" }),
  });
  state.activeSessionId = session.id;
  await loadSessions();
  await selectSession(session.id);
}

async function saveTitle() {
  // 保存标题使用 PATCH，表达“局部更新会话”。
  if (!state.activeSessionId) return;
  await api(`/api/sessions/${state.activeSessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title: sessionTitleInput.value }),
  });
  await loadSessions();
}

async function sendMessage(event) {
  // 发送消息后，后端不会直接返回 assistant 回复。
  // 它会返回 task_id，前端再轮询任务状态。
  event.preventDefault();
  if (!state.activeSessionId) return;

  const message = messageInput.value.trim();
  if (!message) return;

  messageInput.value = "";
  setTaskStatus("pending", "running");
  renderSources([]);

  const payload = await api(`/api/sessions/${state.activeSessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });

  await refreshMessages();
  pollTask(payload.task.id);
}

async function refreshMessages() {
  // assistant 消息由后台任务写入数据库。
  // 所以任务完成后要重新拉取消息列表。
  if (!state.activeSessionId) return;
  const payload = await api(`/api/sessions/${state.activeSessionId}/messages`);
  renderMessages(payload.items);
  await loadSessions();
}

function pollTask(taskId) {
  // 轮询是前端处理后台任务的常见方式：
  // 每隔一段时间查询任务，直到 succeeded 或 failed。
  if (state.pollingTimer) {
    clearInterval(state.pollingTimer);
  }

  state.pollingTimer = setInterval(async () => {
    const task = await api(`/api/tasks/${taskId}`);
    setTaskStatus(task.status, task.status);

    if (task.status === "succeeded") {
      clearInterval(state.pollingTimer);
      state.pollingTimer = null;
      renderSources(task.sources);
      await refreshMessages();
    }

    if (task.status === "failed") {
      clearInterval(state.pollingTimer);
      state.pollingTimer = null;
      setTaskStatus(task.error_message || "任务失败", "failed");
    }
  }, 600);
}

function escapeHtml(value) {
  // 用户输入不能直接拼进 innerHTML。
  // 这里做最小 HTML 转义，避免把 <script> 当成页面代码执行。
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

newSessionButton.addEventListener("click", createSession);
saveTitleButton.addEventListener("click", saveTitle);
composer.addEventListener("submit", sendMessage);

loadSessions().then(() => {
  if (state.activeSessionId) {
    selectSession(state.activeSessionId);
  }
});
