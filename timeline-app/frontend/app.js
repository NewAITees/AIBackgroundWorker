const state = {
  workspace: null,
  entries: [],
  pastEntries: [],
  todoEntries: [],
  futureEntries: [],
  selectedEntryId: null,
  selectedEntry: null,
  chatThreadId: null,
  editMode: false,
  initialScrollDone: false,
  oldestTimestamp: null,
  newestTimestamp: null,
  loadingMore: false,
  noMorePast: false,
  noMoreFuture: false,
  aiPaused: false,
  mobileActivePane: "timeline",
};

const refs = {};

document.addEventListener("DOMContentLoaded", async () => {
  cacheRefs();
  bindEvents();
  await refreshWorkspace();
  await refreshAIStatus();
});

function cacheRefs() {
  refs.workspacePath = document.getElementById("workspace-path");
  refs.aiToggle = document.getElementById("ai-toggle");
  refs.workspaceOpen = document.getElementById("workspace-open");
  refs.showVrmPane = document.getElementById("show-vrm-pane");
  refs.showDetailPane = document.getElementById("show-detail-pane");
  refs.showTimelinePane = document.getElementById("show-timeline-pane");
  refs.workspaceSummary = document.getElementById("workspace-summary");
  refs.timelineStatus = document.getElementById("timeline-status");
  refs.workspaceEmpty = document.getElementById("workspace-empty");
  refs.layout = document.querySelector(".layout");
  refs.vrmPane = document.querySelector(".vrm-pane");
  refs.timelineRoot = document.getElementById("timeline-root");
  refs.timelinePane = document.querySelector(".timeline-pane");
  refs.pastList = document.getElementById("past-list");
  refs.todoList = document.getElementById("todo-list");
  refs.futureList = document.getElementById("future-list");
  refs.chatForm = document.getElementById("chat-form");
  refs.chatInput = document.getElementById("chat-input");
  refs.chatStatus = document.getElementById("chat-status");
  refs.chatResponse = document.getElementById("chat-response");
  refs.chatReplyText = document.getElementById("chat-reply-text");
  refs.candidateList = document.getElementById("candidate-list");
  refs.detailEmpty = document.getElementById("detail-empty");
  refs.detailView = document.getElementById("detail-view");
  refs.detailType = document.getElementById("detail-type");
  refs.detailPane = document.querySelector(".detail-pane");
  refs.detailTitle = document.getElementById("detail-title");
  refs.detailMeta = document.getElementById("detail-meta");
  refs.detailContent = document.getElementById("detail-content");
  refs.detailForm = document.getElementById("detail-form");
  refs.detailTitleInput = document.getElementById("detail-title-input");
  refs.detailContentInput = document.getElementById("detail-content-input");
  refs.detailTimestampInput = document.getElementById("detail-timestamp-input");
  refs.detailStatusInput = document.getElementById("detail-status-input");
  refs.detailEditToggle = document.getElementById("detail-edit-toggle");
  refs.detailReadonly = document.getElementById("detail-readonly");
  refs.detailStatusMessage = document.getElementById("detail-status-message");
  refs.detailFormSubmit = document.getElementById("detail-form");
  refs.jumpNow = document.getElementById("jump-now");
  refs.nowAnchor = document.getElementById("now-anchor");
}

function bindEvents() {
  refs.workspaceOpen.addEventListener("click", openWorkspace);
  refs.showVrmPane.addEventListener("click", () => setActivePane("vrm"));
  refs.showDetailPane.addEventListener("click", () => setActivePane("detail"));
  refs.showTimelinePane.addEventListener("click", () => setActivePane("timeline"));
  refs.aiToggle.addEventListener("click", toggleAI);
  refs.chatForm.addEventListener("submit", submitChat);
  refs.detailEditToggle.addEventListener("click", toggleDetailEdit);
  refs.detailForm.addEventListener("submit", saveDetail);
  refs.jumpNow.addEventListener("click", () => scrollToNow("smooth"));
  document.addEventListener("keydown", handleGlobalKeydown);
  window.addEventListener("resize", syncResponsivePaneState);
  bindSwipeNavigation();
  syncResponsivePaneState();
  setupInfiniteScroll();
}

function isMobileLayout() {
  return window.matchMedia("(max-width: 900px)").matches;
}

function setActivePane(pane) {
  state.mobileActivePane = pane;
  syncResponsivePaneState();
}

function syncResponsivePaneState() {
  const mobile = isMobileLayout();
  document.body.dataset.mobileLayout = mobile ? "true" : "false";
  const paneMap = {
    vrm: refs.vrmPane,
    detail: refs.detailPane,
    timeline: refs.timelinePane,
  };
  for (const [pane, node] of Object.entries(paneMap)) {
    if (!node) continue;
    node.dataset.active = mobile ? String(state.mobileActivePane === pane) : "true";
  }
  refs.showVrmPane.dataset.active = String(state.mobileActivePane === "vrm");
  refs.showDetailPane.dataset.active = String(state.mobileActivePane === "detail");
  refs.showTimelinePane.dataset.active = String(state.mobileActivePane === "timeline");
}

function bindSwipeNavigation() {
  let touchStartX = null;
  let touchStartY = null;
  refs.layout.addEventListener("touchstart", (event) => {
    const touch = event.touches[0];
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
  }, { passive: true });

  refs.layout.addEventListener("touchend", (event) => {
    if (!isMobileLayout() || touchStartX == null || touchStartY == null) return;
    const touch = event.changedTouches[0];
    const deltaX = touch.clientX - touchStartX;
    const deltaY = touch.clientY - touchStartY;
    touchStartX = null;
    touchStartY = null;
    if (Math.abs(deltaX) < 50 || Math.abs(deltaX) <= Math.abs(deltaY)) return;
    const order = ["vrm", "detail", "timeline"];
    const currentIndex = order.indexOf(state.mobileActivePane);
    if (deltaX < 0 && currentIndex < order.length - 1) {
      setActivePane(order[currentIndex + 1]);
    } else if (deltaX > 0 && currentIndex > 0) {
      setActivePane(order[currentIndex - 1]);
    }
  }, { passive: true });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const message = typeof body === "object" && body?.detail ? body.detail : response.statusText;
    throw new Error(message);
  }
  return body;
}

async function refreshWorkspace() {
  try {
    const workspace = await api("/api/workspace");
    state.workspace = workspace;
    renderWorkspace();
    if (workspace.opened) {
      refs.workspacePath.value = workspace.path;
      await loadTimeline();
    }
  } catch (error) {
    refs.workspaceSummary.textContent = error.message;
  }
}

async function refreshAIStatus() {
  try {
    const status = await api("/api/ai/status");
    state.aiPaused = !!status.paused;
    renderAIStatus();
  } catch (error) {
    refs.aiToggle.textContent = "AI: 状態不明";
  }
}

function renderAIStatus() {
  refs.aiToggle.dataset.paused = String(state.aiPaused);
  refs.aiToggle.textContent = state.aiPaused ? "AI: 停止中" : "AI: 稼働中";
}

async function toggleAI() {
  refs.aiToggle.disabled = true;
  try {
    const path = state.aiPaused ? "/api/ai/resume" : "/api/ai/pause";
    const status = await api(path, { method: "POST" });
    state.aiPaused = !!status.paused;
    renderAIStatus();
  } catch (error) {
    refs.chatStatus.textContent = error.message;
  } finally {
    refs.aiToggle.disabled = false;
  }
}

function renderWorkspace() {
  if (!state.workspace?.opened) {
    refs.workspaceSummary.textContent = "未設定";
    refs.workspaceEmpty.classList.remove("hidden");
    refs.timelineRoot.classList.add("hidden");
    return;
  }

  refs.workspaceEmpty.classList.add("hidden");
  refs.timelineRoot.classList.remove("hidden");
  refs.workspaceSummary.textContent = `${state.workspace.mode}\n${state.workspace.path}`;
}

async function openWorkspace() {
  const path = refs.workspacePath.value.trim();
  if (!path) {
    refs.workspaceSummary.textContent = "パスを入力してください";
    return;
  }

  refs.workspaceSummary.textContent = "ワークスペースを開いています...";
  try {
    state.workspace = await api("/api/workspace/open", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
    renderWorkspace();
    await loadTimeline();
  } catch (error) {
    refs.workspaceSummary.textContent = error.message;
  }
}

async function loadTimeline() {
  refs.timelineStatus.textContent = "タイムライン読込中...";
  state.noMorePast = false;
  state.noMoreFuture = false;
  try {
    const response = await api("/api/timeline");
    setTimelineState(response);
    renderTimeline();
    refs.timelineStatus.textContent = `${state.entries.length} 件を表示`;
    if (!state.initialScrollDone) {
      state.initialScrollDone = true;
      scrollToNow("instant");
    }
  } catch (error) {
    setTimelineState({});
    renderTimeline();
    refs.timelineStatus.textContent = error.message;
  }
}

function scrollToNow(behavior = "smooth") {
  refs.nowAnchor.scrollIntoView({ behavior, block: "center" });
}

function scrollToTimelineEdge(edge, behavior = "smooth") {
  const target =
    edge === "future"
      ? refs.futureList.firstElementChild || refs.timelineRoot
      : refs.pastList.lastElementChild || refs.timelineRoot;
  if (!target) return;
  target.scrollIntoView({
    behavior,
    block: edge === "future" ? "start" : "end",
  });
}

function handleGlobalKeydown(event) {
  if (shouldIgnoreGlobalKeydown(event)) return;

  if (event.key === "Home") {
    event.preventDefault();
    scrollToTimelineEdge("future");
    return;
  }
  if (event.key === "End") {
    event.preventDefault();
    scrollToTimelineEdge("past");
    return;
  }
  if (event.key === "n" || event.key === "N") {
    event.preventDefault();
    scrollToNow();
  }
}

function shouldIgnoreGlobalKeydown(event) {
  if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return true;
  const target = event.target;
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || tag === "BUTTON";
}

function renderTimeline() {
  // sentinel を退避（innerHTML クリアで消えるのを防ぐ）
  const topSentinel = document.getElementById("sentinel-top");
  const bottomSentinel = document.getElementById("sentinel-bottom");

  refs.futureList.innerHTML = "";
  refs.todoList.innerHTML = "";
  refs.pastList.innerHTML = "";

  for (const entry of state.futureEntries.sort(sortByTimeDesc)) {
    refs.futureList.appendChild(buildEntryCard(entry));
  }
  for (const entry of state.todoEntries.sort(sortByTimeDesc)) {
    refs.todoList.appendChild(buildEntryCard(entry));
  }
  for (const entry of state.pastEntries.sort(sortByTimeDesc)) {
    refs.pastList.appendChild(buildEntryCard(entry));
  }

  // sentinel を再挿入（observer は同じ要素を observe し続けるので再登録不要）
  if (topSentinel) refs.futureList.prepend(topSentinel);
  if (bottomSentinel) refs.pastList.append(bottomSentinel);
  updateTimelineBounds();
}

function buildEntryCard(entry) {
  const template = document.getElementById("entry-card-template");
  const node = template.content.firstElementChild.cloneNode(true);
  const button = node.querySelector(".entry-card-button");
  const typeEl = node.querySelector(".entry-type");
  const timeEl = node.querySelector(".entry-time");
  const actionsEl = node.querySelector(".entry-card-actions");
  const titleEl = node.querySelector(".entry-title");
  const contentEl = node.querySelector(".entry-content");

  node.dataset.type = entry.type;
  typeEl.textContent = entry.type;
  typeEl.dataset.type = entry.type;
  timeEl.textContent = formatDateTime(entry.timestamp);
  titleEl.textContent = entry.title || fallbackTitle(entry);
  contentEl.textContent = entry.summary || entry.content;

  button.addEventListener("click", () => selectEntry(entry.id));

  if (entry.type === "todo" || entry.type === "todo_done") {
    const checkbox = document.createElement("button");
    checkbox.className = "todo-checkbox";
    checkbox.type = "button";
    checkbox.setAttribute("aria-label", entry.type === "todo_done" ? "完了済み" : "完了にする");
    checkbox.disabled = entry.type === "todo_done";
    checkbox.addEventListener("click", (e) => {
      e.stopPropagation();
      if (entry.type === "todo") completeTodo(entry.id);
    });
    actionsEl.appendChild(checkbox);
  }

  return node;
}

async function completeTodo(entryId) {
  try {
    const now = new Date().toISOString();
    await api(`/api/entries/${encodeURIComponent(entryId)}`, {
      method: "PATCH",
      body: JSON.stringify({
        type: "todo_done",
        status: "done",
        meta: { completed_at: now },
      }),
    });
    await loadTimeline();
  } catch (err) {
    console.warn("completeTodo failed:", err);
  }
}

function fallbackTitle(entry) {
  if (entry.type === "chat_ai") return "AI reply";
  if (entry.type === "chat_user") return "User note";
  return "Untitled";
}

async function selectEntry(entryId) {
  state.selectedEntryId = entryId;
  refs.detailStatusMessage.textContent = "";
  try {
    state.selectedEntry = await api(`/api/entries/${encodeURIComponent(entryId)}`);
    state.editMode = false;
    renderDetail();
    if (isMobileLayout()) setActivePane("detail");
  } catch (error) {
    refs.detailEmpty.classList.remove("hidden");
    refs.detailView.classList.add("hidden");
    refs.detailEmpty.querySelector("p").textContent = error.message;
  }
}

function renderDetail() {
  if (!state.selectedEntry) {
    refs.detailEmpty.classList.remove("hidden");
    refs.detailView.classList.add("hidden");
    return;
  }

  refs.detailEmpty.classList.add("hidden");
  refs.detailView.classList.remove("hidden");
  refs.detailType.textContent = state.selectedEntry.type;
  refs.detailTitle.textContent = state.selectedEntry.title || fallbackTitle(state.selectedEntry);
  refs.detailMeta.textContent = `${formatDateTime(state.selectedEntry.timestamp)} | ${state.selectedEntry.status}`;
  refs.detailContent.innerHTML = DOMPurify.sanitize(marked.parse(state.selectedEntry.content || ""));
  refs.detailTitleInput.value = state.selectedEntry.title || "";
  refs.detailContentInput.value = state.selectedEntry.content;
  refs.detailTimestampInput.value = toDatetimeLocal(state.selectedEntry.timestamp);
  refs.detailStatusInput.value = state.selectedEntry.status;
  applyDetailMode();
}

function toggleDetailEdit() {
  if (!state.selectedEntry) return;
  state.editMode = !state.editMode;
  applyDetailMode();
}

function applyDetailMode() {
  refs.detailReadonly.classList.toggle("hidden", state.editMode);
  refs.detailForm.classList.toggle("hidden", !state.editMode);
  refs.detailEditToggle.textContent = state.editMode ? "閲覧" : "編集";
}

async function saveDetail(event) {
  event.preventDefault();
  if (!state.selectedEntryId) return;

  refs.detailStatusMessage.textContent = "保存中...";
  try {
    state.selectedEntry = await api(`/api/entries/${encodeURIComponent(state.selectedEntryId)}`, {
      method: "PATCH",
      body: JSON.stringify({
        title: refs.detailTitleInput.value.trim() || null,
        content: refs.detailContentInput.value,
        timestamp: refs.detailTimestampInput.value
          ? new Date(refs.detailTimestampInput.value).toISOString()
          : undefined,
        status: refs.detailStatusInput.value,
      }),
    });
    state.editMode = false;
    refs.detailStatusMessage.textContent = "保存しました";
    renderDetail();
    await loadTimeline();
  } catch (error) {
    refs.detailStatusMessage.textContent = error.message;
  }
}

async function submitChat(event) {
  event.preventDefault();
  if (state.aiPaused) {
    refs.chatStatus.textContent = "AI処理は一時停止中です";
    return;
  }
  const content = refs.chatInput.value.trim();
  if (!content) return;

  refs.chatStatus.textContent = "AIに送信中...";
  try {
    const response = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        content,
        thread_id: state.chatThreadId,
      }),
    });
    state.chatThreadId = response.thread_id;
    refs.chatInput.value = "";
    refs.chatReplyText.innerHTML = DOMPurify.sanitize(marked.parse(response.reply || ""));
    renderCandidates(response.entry_candidates || []);
    refs.chatResponse.classList.remove("hidden");
    refs.chatStatus.textContent = "応答を保存しました";
    if (isMobileLayout()) setActivePane("timeline");
    await loadTimeline();
  } catch (error) {
    refs.chatStatus.textContent = error.message;
  }
}

function renderCandidates(candidates) {
  refs.candidateList.innerHTML = "";
  if (!candidates.length) {
    const note = document.createElement("p");
    note.textContent = "今回は候補なし";
    refs.candidateList.appendChild(note);
    return;
  }

  for (const candidate of candidates) {
    const template = document.getElementById("candidate-template");
    const button = template.content.firstElementChild.cloneNode(true);
    button.textContent = `${candidate.type} にする`;
    button.addEventListener("click", async () => {
      await createCandidateEntry(candidate);
    });
    refs.candidateList.appendChild(button);
  }
}

async function createCandidateEntry(candidate) {
  refs.chatStatus.textContent = `${candidate.type} を保存中...`;
  try {
    const body = {
      type: candidate.type,
      title: candidate.title,
      content: candidate.content,
      source: "ai",
      meta: { thread_id: state.chatThreadId },
    };
    if (candidate.timestamp) {
      body.timestamp = candidate.timestamp;
    }
    await api("/api/entries", { method: "POST", body: JSON.stringify(body) });
    refs.chatStatus.textContent = `${candidate.type} を保存しました`;
    if (isMobileLayout()) setActivePane("timeline");
    await loadTimeline();
  } catch (error) {
    refs.chatStatus.textContent = error.message;
  }
}

function setupInfiniteScroll() {
  // future-list の先頭に sentinel を置いて「未来をもっと読む」
  const topSentinel = document.createElement("div");
  topSentinel.id = "sentinel-top";
  refs.futureList.prepend(topSentinel);

  // past-list の末尾に sentinel を置いて「過去をもっと読む」
  const bottomSentinel = document.createElement("div");
  bottomSentinel.id = "sentinel-bottom";
  refs.pastList.append(bottomSentinel);

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting || state.loadingMore) continue;
        if (entry.target.id === "sentinel-top") loadMoreFuture();
        if (entry.target.id === "sentinel-bottom") loadMorePast();
      }
    },
    { rootMargin: "200px" }
  );

  observer.observe(topSentinel);
  observer.observe(bottomSentinel);
}

async function loadMorePast() {
  if (!state.oldestTimestamp || !state.workspace?.opened || state.loadingMore || state.noMorePast) return;
  state.loadingMore = true;
  try {
    const around = new Date(state.oldestTimestamp).toISOString();
    const res = await api(`/api/timeline?around=${encodeURIComponent(around)}&before=24&after=0`);
    const incoming = (res.past_entries || []).filter(
      (e) => !state.pastEntries.some((ex) => ex.id === e.id)
    );
    if (incoming.length > 0) {
      state.pastEntries = [...state.pastEntries, ...incoming];
      state.entries = [...state.pastEntries, ...state.todoEntries, ...state.futureEntries];
      updateTimelineBounds();
      renderTimeline();
    } else {
      state.noMorePast = true;
    }
  } catch (err) {
    console.warn("loadMorePast failed:", err);
  } finally {
    state.loadingMore = false;
  }
}

async function loadMoreFuture() {
  if (!state.newestTimestamp || !state.workspace?.opened || state.loadingMore || state.noMoreFuture) return;
  state.loadingMore = true;
  try {
    const around = new Date(state.newestTimestamp).toISOString();
    const res = await api(`/api/timeline?around=${encodeURIComponent(around)}&before=0&after=24`);
    const incoming = (res.future_entries || []).filter(
      (e) => !state.futureEntries.some((ex) => ex.id === e.id)
    );
    if (incoming.length > 0) {
      state.futureEntries = [...incoming, ...state.futureEntries];
      state.entries = [...state.pastEntries, ...state.todoEntries, ...state.futureEntries];
      updateTimelineBounds();
      renderTimeline();
    } else {
      state.noMoreFuture = true;
    }
  } catch (err) {
    console.warn("loadMoreFuture failed:", err);
  } finally {
    state.loadingMore = false;
  }
}

function sortByTimeAsc(a, b) {
  return new Date(a.timestamp) - new Date(b.timestamp);
}

function sortByTimeDesc(a, b) {
  return new Date(b.timestamp) - new Date(a.timestamp);
}

function setTimelineState(response) {
  state.pastEntries = response.past_entries || [];
  state.todoEntries = response.todo_entries || [];
  state.futureEntries = response.future_entries || [];
  state.entries = response.entries || [
    ...state.pastEntries,
    ...state.todoEntries,
    ...state.futureEntries,
  ];
  updateTimelineBounds();
}

function updateTimelineBounds() {
  const timelineEntries = [...state.pastEntries, ...state.futureEntries].sort(sortByTimeAsc);
  if (timelineEntries.length > 0) {
    state.oldestTimestamp = timelineEntries[0].timestamp;
    state.newestTimestamp = timelineEntries[timelineEntries.length - 1].timestamp;
    return;
  }
  state.oldestTimestamp = null;
  state.newestTimestamp = null;
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function toDatetimeLocal(isoString) {
  const d = new Date(isoString);
  const pad = (n) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}
