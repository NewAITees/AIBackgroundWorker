const state = {
  workspace: null,
  entries: [],
  selectedEntryId: null,
  selectedEntry: null,
  chatThreadId: null,
  editMode: false,
  initialScrollDone: false,
  oldestTimestamp: null,
  newestTimestamp: null,
  loadingMore: false,
};

const refs = {};

document.addEventListener("DOMContentLoaded", async () => {
  cacheRefs();
  bindEvents();
  await refreshWorkspace();
});

function cacheRefs() {
  refs.workspacePath = document.getElementById("workspace-path");
  refs.workspaceOpen = document.getElementById("workspace-open");
  refs.workspaceSummary = document.getElementById("workspace-summary");
  refs.timelineStatus = document.getElementById("timeline-status");
  refs.workspaceEmpty = document.getElementById("workspace-empty");
  refs.timelineRoot = document.getElementById("timeline-root");
  refs.pastList = document.getElementById("past-list");
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
  refs.detailTitle = document.getElementById("detail-title");
  refs.detailMeta = document.getElementById("detail-meta");
  refs.detailContent = document.getElementById("detail-content");
  refs.detailForm = document.getElementById("detail-form");
  refs.detailTitleInput = document.getElementById("detail-title-input");
  refs.detailContentInput = document.getElementById("detail-content-input");
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
  refs.chatForm.addEventListener("submit", submitChat);
  refs.detailEditToggle.addEventListener("click", toggleDetailEdit);
  refs.detailForm.addEventListener("submit", saveDetail);
  refs.jumpNow.addEventListener("click", () => {
    refs.nowAnchor.scrollIntoView({ behavior: "smooth", block: "center" });
  });
  setupInfiniteScroll();
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

function renderWorkspace() {
  if (!state.workspace?.opened) {
    refs.workspaceSummary.textContent = "ワークスペース未設定";
    refs.workspaceEmpty.classList.remove("hidden");
    refs.timelineRoot.classList.add("hidden");
    return;
  }

  refs.workspaceEmpty.classList.add("hidden");
  refs.timelineRoot.classList.remove("hidden");
  refs.workspaceSummary.textContent = `${state.workspace.mode} | ${state.workspace.path}`;
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
  try {
    const response = await api("/api/timeline");
    state.entries = response.entries || [];
    renderTimeline();
    refs.timelineStatus.textContent = `${state.entries.length} 件を表示`;
    if (!state.initialScrollDone) {
      state.initialScrollDone = true;
      refs.nowAnchor.scrollIntoView({ behavior: "instant", block: "center" });
    }
  } catch (error) {
    state.entries = [];
    renderTimeline();
    refs.timelineStatus.textContent = error.message;
  }
}

function renderTimeline() {
  refs.pastList.innerHTML = "";
  refs.futureList.innerHTML = "";

  const now = new Date();
  const past = state.entries.filter((entry) => new Date(entry.timestamp) <= now);
  const future = state.entries.filter((entry) => new Date(entry.timestamp) > now);

  for (const entry of past.sort(sortByTimeAsc)) {
    refs.pastList.appendChild(buildEntryCard(entry));
  }
  for (const entry of future.sort(sortByTimeAsc)) {
    refs.futureList.appendChild(buildEntryCard(entry));
  }

  if (state.entries.length > 0) {
    const sorted = [...state.entries].sort(sortByTimeAsc);
    state.oldestTimestamp = sorted[0].timestamp;
    state.newestTimestamp = sorted[sorted.length - 1].timestamp;
  }
}

function buildEntryCard(entry) {
  const template = document.getElementById("entry-card-template");
  const node = template.content.firstElementChild.cloneNode(true);
  const button = node.querySelector(".entry-card-button");
  const typeEl = node.querySelector(".entry-type");
  const timeEl = node.querySelector(".entry-time");
  const titleEl = node.querySelector(".entry-title");
  const contentEl = node.querySelector(".entry-content");

  node.dataset.type = entry.type;
  typeEl.textContent = entry.type;
  typeEl.dataset.type = entry.type;
  timeEl.textContent = formatDateTime(entry.timestamp);
  titleEl.textContent = entry.title || fallbackTitle(entry);
  contentEl.textContent = entry.summary || entry.content;

  button.addEventListener("click", () => selectEntry(entry.id));
  return node;
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
  refs.detailContent.textContent = state.selectedEntry.content;
  refs.detailTitleInput.value = state.selectedEntry.title || "";
  refs.detailContentInput.value = state.selectedEntry.content;
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
    refs.chatReplyText.textContent = response.reply;
    renderCandidates(response.entry_candidates || []);
    refs.chatResponse.classList.remove("hidden");
    refs.chatStatus.textContent = "応答を保存しました";
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
    await loadTimeline();
  } catch (error) {
    refs.chatStatus.textContent = error.message;
  }
}

function setupInfiniteScroll() {
  // past-list の先頭に sentinel を置いて「過去をもっと読む」
  const topSentinel = document.createElement("div");
  topSentinel.id = "sentinel-top";
  refs.pastList.prepend(topSentinel);

  // future-list の末尾に sentinel を置いて「未来をもっと読む」
  const bottomSentinel = document.createElement("div");
  bottomSentinel.id = "sentinel-bottom";
  refs.futureList.append(bottomSentinel);

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting || state.loadingMore) continue;
        if (entry.target.id === "sentinel-top") loadMorePast();
        if (entry.target.id === "sentinel-bottom") loadMoreFuture();
      }
    },
    { rootMargin: "200px" }
  );

  observer.observe(topSentinel);
  observer.observe(bottomSentinel);
}

async function loadMorePast() {
  if (!state.oldestTimestamp || !state.workspace?.opened) return;
  state.loadingMore = true;
  try {
    const around = new Date(state.oldestTimestamp).toISOString();
    const res = await api(`/api/timeline?around=${encodeURIComponent(around)}&before=24&after=0`);
    const incoming = (res.entries || []).filter(
      (e) => !state.entries.some((ex) => ex.id === e.id)
    );
    if (incoming.length > 0) {
      state.entries = [...incoming, ...state.entries];
      renderTimeline();
    }
  } catch (_) {
    // サイレント失敗
  } finally {
    state.loadingMore = false;
  }
}

async function loadMoreFuture() {
  if (!state.newestTimestamp || !state.workspace?.opened) return;
  state.loadingMore = true;
  try {
    const around = new Date(state.newestTimestamp).toISOString();
    const res = await api(`/api/timeline?around=${encodeURIComponent(around)}&before=0&after=24`);
    const incoming = (res.entries || []).filter(
      (e) => !state.entries.some((ex) => ex.id === e.id)
    );
    if (incoming.length > 0) {
      state.entries = [...state.entries, ...incoming];
      renderTimeline();
    }
  } catch (_) {
    // サイレント失敗
  } finally {
    state.loadingMore = false;
  }
}

function sortByTimeAsc(a, b) {
  return new Date(a.timestamp) - new Date(b.timestamp);
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
