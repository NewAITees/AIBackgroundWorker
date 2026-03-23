const state = {
  workspace: null,
  entries: [],
  rawEntries: [],
  pastEntries: [],
  todoEntries: [],
  futureEntries: [],
  selectedEntryId: null,
  selectedEntry: null,
  chatThreadId: null,
  editMode: false,
  initialScrollDone: false,
  aroundTimestamp: null,
  oldestTimestamp: null,
  newestTimestamp: null,
  loadingMore: false,
  noMorePast: false,
  noMoreFuture: false,
  aiPaused: false,
  leftPaneOpen: true,
  detailPaneOpen: true,
  responsiveInitialized: false,
  filterMenuOpen: false,
  filters: {
    types: ["chat", "diary", "event", "todo", "news", "memo", "system_log"],
    search: "",
    todoOnly: false,
    showAi: true,
  },
  lastUndoAction: null,
};

const refs = {};
const CHAT_DRAFT_KEY_PREFIX = "timeline-chat-draft:";
const INITIAL_TIMELINE_HOURS = 12;
const PAGING_TIMELINE_HOURS = 24;
const TIMELINE_FILTER_OPTIONS = ["chat", "diary", "event", "todo", "news", "memo", "system_log"];
const DETAIL_TYPE_OPTIONS = [
  "chat_user",
  "chat_ai",
  "diary",
  "event",
  "todo",
  "todo_done",
  "memo",
  "news",
  "system_log",
];

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
  refs.closeVrmPane = document.getElementById("close-vrm-pane");
  refs.closeDetailPane = document.getElementById("close-detail-pane");
  refs.workspaceSummary = document.getElementById("workspace-summary");
  refs.timelineStatus = document.getElementById("timeline-status");
  refs.filterMenuButton = document.getElementById("filter-menu-button");
  refs.filterMenuPanel = document.getElementById("filter-menu-panel");
  refs.filterSummary = document.getElementById("filter-summary");
  refs.typeFilters = document.getElementById("type-filters");
  refs.timelineSearch = document.getElementById("timeline-search");
  refs.timelineDateJump = document.getElementById("timeline-date-jump");
  refs.timelineDateLoad = document.getElementById("timeline-date-load");
  refs.filterTodoOnly = document.getElementById("filter-todo-only");
  refs.filterShowAi = document.getElementById("filter-show-ai");
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
  refs.chatDraftClear = document.getElementById("chat-draft-clear");
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
  refs.detailQuickTypeSelect = document.getElementById("detail-quick-type-select");
  refs.detailContent = document.getElementById("detail-content");
  refs.detailForm = document.getElementById("detail-form");
  refs.detailTitleInput = document.getElementById("detail-title-input");
  refs.detailContentInput = document.getElementById("detail-content-input");
  refs.detailTypeInput = document.getElementById("detail-type-input");
  refs.detailTimestampInput = document.getElementById("detail-timestamp-input");
  refs.detailStatusInput = document.getElementById("detail-status-input");
  refs.detailEditToggle = document.getElementById("detail-edit-toggle");
  refs.detailReadonly = document.getElementById("detail-readonly");
  refs.detailStatusMessage = document.getElementById("detail-status-message");
  refs.detailUndo = document.getElementById("detail-undo");
  refs.detailFormSubmit = document.getElementById("detail-form");
  refs.jumpNow = document.getElementById("jump-now");
  refs.nowAnchor = document.getElementById("now-anchor");
  // settings panel
  refs.navTimeline = document.getElementById("nav-timeline");
  refs.navSettings = document.getElementById("nav-settings");
  refs.settingsPanel = document.getElementById("settings-panel");
  refs.settingsClose = document.getElementById("settings-close");
  refs.sPersonality = document.getElementById("s-personality");
  refs.sPersonalityStatus = document.getElementById("s-personality-status");
  refs.sPersonalitySave = document.getElementById("s-personality-save");
  refs.sOllamaUrl = document.getElementById("s-ollama-url");
  refs.sOllamaModel = document.getElementById("s-ollama-model");
  refs.sOllamaTimeout = document.getElementById("s-ollama-timeout");
  refs.sAiStatus = document.getElementById("s-ai-status");
  refs.sAiSave = document.getElementById("s-ai-save");
  refs.sWorkers = document.getElementById("s-workers");
  refs.sFeeds = document.getElementById("s-feeds");
  refs.sFeedUrl = document.getElementById("s-feed-url");
  refs.sFeedAdd = document.getElementById("s-feed-add");
  refs.sFeedStatus = document.getElementById("s-feed-status");
}

function bindEvents() {
  refs.workspaceOpen.addEventListener("click", openWorkspace);
  refs.filterMenuButton.addEventListener("click", toggleFilterMenu);
  refs.typeFilters.addEventListener("change", handleTypeFilterChange);
  refs.timelineSearch.addEventListener("input", handleTimelineSearch);
  refs.timelineDateLoad.addEventListener("click", jumpToDate);
  refs.timelineDateJump.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      jumpToDate();
    }
  });
  refs.filterTodoOnly.addEventListener("change", handleTodoOnlyToggle);
  refs.filterShowAi.addEventListener("change", handleShowAiToggle);
  refs.detailQuickTypeSelect.addEventListener("change", handleQuickTypeSelect);
  refs.showVrmPane.addEventListener("click", () => setLeftPaneOpen(true));
  refs.showDetailPane.addEventListener("click", () => setDetailPaneOpen(true));
  refs.showTimelinePane.addEventListener("click", () => {
    setLeftPaneOpen(false);
    setDetailPaneOpen(false);
  });
  refs.closeVrmPane.addEventListener("click", () => setLeftPaneOpen(false));
  refs.closeDetailPane.addEventListener("click", () => setDetailPaneOpen(false));
  refs.aiToggle.addEventListener("click", toggleAI);
  refs.chatForm.addEventListener("submit", submitChat);
  refs.chatInput.addEventListener("input", persistChatDraft);
  refs.chatDraftClear.addEventListener("click", clearChatDraft);
  refs.detailEditToggle.addEventListener("click", toggleDetailEdit);
  refs.detailForm.addEventListener("submit", saveDetail);
  refs.detailUndo.addEventListener("click", undoLastAction);
  refs.jumpNow.addEventListener("click", () => scrollToNow("smooth"));
  refs.navSettings.addEventListener("click", openSettingsPanel);
  refs.navTimeline.addEventListener("click", closeSettingsPanel);
  refs.settingsClose.addEventListener("click", closeSettingsPanel);
  refs.sPersonalitySave.addEventListener("click", savePersonality);
  refs.sAiSave.addEventListener("click", saveAiSettings);
  refs.sFeedAdd.addEventListener("click", addFeed);
  document.addEventListener("keydown", handleGlobalKeydown);
  document.addEventListener("click", handleDocumentClick);
  window.addEventListener("resize", syncResponsivePaneState);
  syncResponsivePaneState();
  setupInfiniteScroll();
}

function isMobileLayout() {
  return window.matchMedia("(max-width: 900px)").matches;
}

function setLeftPaneOpen(open) {
  state.leftPaneOpen = open;
  syncResponsivePaneState();
}

function setDetailPaneOpen(open) {
  state.detailPaneOpen = open;
  syncResponsivePaneState();
}

function syncResponsivePaneState() {
  const mobile = isMobileLayout();
  if (!state.responsiveInitialized) {
    if (mobile) {
      state.leftPaneOpen = false;
      state.detailPaneOpen = false;
    }
    state.responsiveInitialized = true;
  }
  document.body.dataset.mobileLayout = mobile ? "true" : "false";
  refs.layout.dataset.leftOpen = String(state.leftPaneOpen);
  refs.layout.dataset.detailOpen = String(state.detailPaneOpen);
  refs.vrmPane.dataset.active = mobile ? String(state.leftPaneOpen) : "true";
  refs.detailPane.dataset.active = mobile ? String(state.detailPaneOpen) : "true";
  refs.timelinePane.dataset.active = "true";
  refs.showVrmPane.dataset.active = String(state.leftPaneOpen);
  refs.showDetailPane.dataset.active = String(state.detailPaneOpen);
  refs.showTimelinePane.dataset.active = String(!state.leftPaneOpen && !state.detailPaneOpen);
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
  restoreChatDraft();
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
    const response = await api(
      `/api/timeline?before=${INITIAL_TIMELINE_HOURS}&after=${INITIAL_TIMELINE_HOURS}`
    );
    setTimelineState(response);
    renderTimeline();
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
    return;
  }
  if (event.key === "Escape" && state.filterMenuOpen) {
    closeFilterMenu();
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

  const visibleFutureEntries = getVisibleEntries(state.futureEntries).sort(sortByTimeDesc);
  const visibleTodoEntries = getVisibleEntries(state.todoEntries).sort(sortByTimeDesc);
  const visiblePastEntries = getVisibleEntries(state.pastEntries).sort(sortByTimeDesc);

  for (const entry of visibleFutureEntries) {
    refs.futureList.appendChild(buildEntryCard(entry));
  }
  for (const entry of visibleTodoEntries) {
    refs.todoList.appendChild(buildEntryCard(entry));
  }
  for (const entry of visiblePastEntries) {
    refs.pastList.appendChild(buildEntryCard(entry));
  }

  // sentinel を再挿入（observer は同じ要素を observe し続けるので再登録不要）
  if (topSentinel) refs.futureList.prepend(topSentinel);
  if (bottomSentinel) refs.pastList.append(bottomSentinel);
  updateTimelineBounds();
  renderTimelineStatus();
  renderFilterState();
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

  if (entry.type === "news" && entry.related_ids && entry.related_ids.length > 0) {
    const articleIds = entry.related_ids.filter((id) => id.startsWith("collected-info-"));
    if (articleIds.length > 0) {
      const panel = document.createElement("div");
      panel.className = "news-articles-panel hidden";

      const expandBtn = document.createElement("button");
      expandBtn.className = "news-expand-btn";
      expandBtn.type = "button";
      expandBtn.textContent = `記事を見る (${articleIds.length})`;
      expandBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = !panel.classList.contains("hidden");
        if (isOpen) {
          panel.classList.add("hidden");
          expandBtn.textContent = `記事を見る (${articleIds.length})`;
        } else {
          panel.classList.remove("hidden");
          expandBtn.textContent = "閉じる";
          if (!panel.dataset.loaded) {
            loadNewsArticles(articleIds, panel);
          }
        }
      });

      node.appendChild(expandBtn);
      node.appendChild(panel);
    }
  }

  return node;
}

async function loadNewsArticles(articleIds, panel) {
  panel.dataset.loaded = "1";
  panel.innerHTML = '<p class="news-articles-loading">読み込み中…</p>';

  try {
    const idsParam = encodeURIComponent(articleIds.join(","));
    const articles = await api(`/api/news/articles?ids=${idsParam}`);
    panel.innerHTML = "";

    if (!articles || articles.length === 0) {
      panel.innerHTML = '<p class="news-articles-empty">記事が見つかりませんでした</p>';
      return;
    }

    for (const article of articles) {
      panel.appendChild(buildArticleRow(article));
    }
  } catch (err) {
    panel.innerHTML = `<p class="news-articles-error">読み込み失敗: ${err.message}</p>`;
  }
}

function buildArticleRow(article) {
  const row = document.createElement("div");
  row.className = "news-article-row";
  row.dataset.articleId = article.id;

  const source = article.source_name ? `<span class="article-source">${article.source_name}</span>` : "";
  const link = document.createElement("a");
  link.href = article.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.className = "article-title-link";
  link.textContent = article.title || article.url;

  const meta = document.createElement("div");
  meta.className = "article-meta";
  meta.innerHTML = source;

  const actions = document.createElement("div");
  actions.className = "article-actions";

  const reportBtn = document.createElement("button");
  reportBtn.type = "button";
  reportBtn.className = "article-btn report-btn";
  reportBtn.textContent = "レポート生成";
  reportBtn.addEventListener("click", () => handleGenerateReport(article.id, reportBtn, row));

  const likeBtn = document.createElement("button");
  likeBtn.type = "button";
  likeBtn.className = "article-btn like-btn" + (article.feedback === "positive" ? " active" : "");
  likeBtn.textContent = "👍";
  likeBtn.addEventListener("click", () => handleFeedback(article.id, "positive", likeBtn, dislikeBtn));

  const dislikeBtn = document.createElement("button");
  dislikeBtn.type = "button";
  dislikeBtn.className = "article-btn dislike-btn" + (article.feedback === "negative" ? " active" : "");
  dislikeBtn.textContent = "👎";
  dislikeBtn.addEventListener("click", () => handleFeedback(article.id, "negative", dislikeBtn, likeBtn));

  if (article.feedback === "report_requested") {
    reportBtn.textContent = "生成済み";
    reportBtn.disabled = true;
  }

  actions.appendChild(reportBtn);
  actions.appendChild(likeBtn);
  actions.appendChild(dislikeBtn);

  row.appendChild(link);
  row.appendChild(meta);
  row.appendChild(actions);
  return row;
}

async function handleFeedback(articleId, type, activeBtn, oppositeBtn) {
  try {
    await api(`/api/news/articles/${articleId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ type }),
    });
    activeBtn.classList.add("active");
    oppositeBtn.classList.remove("active");
  } catch (err) {
    console.warn("feedback failed:", err);
  }
}

async function handleGenerateReport(articleId, btn, row) {
  btn.disabled = true;
  btn.textContent = "生成中…";
  try {
    await api(`/api/news/articles/${articleId}/generate_report`, { method: "POST" });
    btn.textContent = "生成済み";
    row.querySelector(".like-btn")?.classList.add("active");
  } catch (err) {
    btn.disabled = false;
    btn.textContent = "レポート生成";
    console.warn("generate_report failed:", err);
  }
}

async function completeTodo(entryId) {
  try {
    const current = findEntryById(entryId);
    const now = new Date().toISOString();
    await api(`/api/entries/${encodeURIComponent(entryId)}`, {
      method: "PATCH",
      body: JSON.stringify({
        type: "todo_done",
        status: "done",
        meta: { completed_at: now },
      }),
    });
    if (current) {
      setUndoAction({
        entryId,
        label: "TODO完了を戻す",
        payload: {
          type: current.type,
          status: current.status,
          timestamp: current.timestamp,
        },
      });
    }
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
    setDetailPaneOpen(true);
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
    renderQuickTypeOptions();
    renderUndoState();
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
  refs.detailTypeInput.value = state.selectedEntry.type;
  refs.detailTimestampInput.value = toDatetimeLocal(state.selectedEntry.timestamp);
  refs.detailStatusInput.value = state.selectedEntry.status;
  renderQuickTypeOptions();
  renderUndoState();
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
    const previous = snapshotEntry(state.selectedEntry);
    state.selectedEntry = await api(`/api/entries/${encodeURIComponent(state.selectedEntryId)}`, {
      method: "PATCH",
      body: JSON.stringify({
        title: refs.detailTitleInput.value.trim() || null,
        content: refs.detailContentInput.value,
        type: refs.detailTypeInput.value,
        timestamp: refs.detailTimestampInput.value
          ? new Date(refs.detailTimestampInput.value).toISOString()
          : undefined,
        status: refs.detailStatusInput.value,
      }),
    });
    setUndoAction({
      entryId: state.selectedEntryId,
      label: "保存前に戻す",
      payload: previous,
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
    if (isMobileLayout()) {
      setLeftPaneOpen(false);
      setDetailPaneOpen(false);
    }
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
    clearChatDraft({ preserveStatus: true });
    if (isMobileLayout()) {
      setLeftPaneOpen(false);
      setDetailPaneOpen(false);
    }
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
    const res = await api(
      `/api/timeline?around=${encodeURIComponent(around)}&before=${PAGING_TIMELINE_HOURS}&after=0`
    );
    if (mergeTimelineEntries(res.entries || []) > 0) {
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
    const res = await api(
      `/api/timeline?around=${encodeURIComponent(around)}&before=0&after=${PAGING_TIMELINE_HOURS}`
    );
    if (mergeTimelineEntries(res.entries || []) > 0) {
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
  state.aroundTimestamp = response.around || state.aroundTimestamp || new Date().toISOString();
  state.rawEntries = response.entries || [
    ...(response.past_entries || []),
    ...(response.todo_entries || []),
    ...(response.future_entries || []),
  ];
  normalizeTimelineBuckets();
  updateTimelineBounds();
  renderFilterState();
  renderTimelineStatus();
}

function mergeTimelineEntries(incomingEntries) {
  const byId = new Map(state.rawEntries.map((entry) => [entry.id, entry]));
  let mergedCount = 0;
  for (const entry of incomingEntries) {
    if (!byId.has(entry.id)) {
      mergedCount += 1;
    }
    byId.set(entry.id, entry);
  }
  state.rawEntries = Array.from(byId.values());
  normalizeTimelineBuckets();
  updateTimelineBounds();
  return mergedCount;
}

function normalizeTimelineBuckets() {
  const byId = new Map(state.rawEntries.map((entry) => [entry.id, entry]));
  state.rawEntries = Array.from(byId.values());

  const aroundMs = new Date(state.aroundTimestamp || new Date().toISOString()).getTime();
  const pastEntries = [];
  const todoEntries = [];
  const futureEntries = [];

  for (const entry of state.rawEntries) {
    if (entry.type === "todo" && entry.status === "active") {
      todoEntries.push(entry);
      continue;
    }
    if (new Date(entry.timestamp).getTime() <= aroundMs) {
      pastEntries.push(entry);
    } else {
      futureEntries.push(entry);
    }
  }

  state.pastEntries = pastEntries;
  state.todoEntries = todoEntries;
  state.futureEntries = futureEntries;
  state.entries = [...state.rawEntries];
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

function renderTimelineStatus() {
  const visibleCount =
    getVisibleEntries(state.pastEntries).length +
    getVisibleEntries(state.todoEntries).length +
    getVisibleEntries(state.futureEntries).length;
  refs.timelineStatus.textContent = `${visibleCount} / ${state.entries.length} 件を表示`;
}

function renderFilterState() {
  refs.filterMenuButton.setAttribute("aria-expanded", String(state.filterMenuOpen));
  refs.filterMenuPanel.classList.toggle("hidden", !state.filterMenuOpen);
  refs.filterTodoOnly.checked = state.filters.todoOnly;
  refs.filterShowAi.checked = state.filters.showAi;
  for (const input of refs.typeFilters.querySelectorAll("[data-filter-type]")) {
    input.checked = state.filters.types.includes(input.dataset.filterType);
  }
  refs.filterSummary.textContent = buildFilterSummary();
}

function buildFilterSummary() {
  const typeCount = state.filters.types.length;
  const typeLabel =
    typeCount === TIMELINE_FILTER_OPTIONS.length
      ? "すべて表示"
      : `${typeCount}種別を表示`;
  const chips = [];
  if (state.filters.todoOnly) chips.push("未完了TODO");
  if (!state.filters.showAi) chips.push("AI非表示");
  return chips.length ? `${typeLabel} / ${chips.join(" / ")}` : typeLabel;
}

function toggleFilterMenu() {
  state.filterMenuOpen = !state.filterMenuOpen;
  renderFilterState();
}

function closeFilterMenu() {
  if (!state.filterMenuOpen) return;
  state.filterMenuOpen = false;
  renderFilterState();
}

function handleDocumentClick(event) {
  const target = event.target;
  if (!(target instanceof Node)) return;
  if (
    state.filterMenuOpen &&
    !refs.filterMenuPanel.contains(target) &&
    !refs.filterMenuButton.contains(target)
  ) {
    closeFilterMenu();
  }
}

function handleTypeFilterChange(event) {
  const input = event.target.closest("[data-filter-type]");
  if (!(input instanceof HTMLInputElement)) return;
  const type = input.dataset.filterType;
  if (!type) return;
  if (input.checked) {
    if (!state.filters.types.includes(type)) {
      state.filters.types = [...state.filters.types, type];
    }
  } else {
    if (state.filters.types.length === 1) {
      input.checked = true;
      return;
    }
    state.filters.types = state.filters.types.filter((value) => value !== type);
  }
  renderTimeline();
}

function handleTimelineSearch(event) {
  state.filters.search = event.target.value.trim().toLowerCase();
  renderTimeline();
}

function handleTodoOnlyToggle(event) {
  state.filters.todoOnly = !!event.target.checked;
  renderTimeline();
}

function handleShowAiToggle(event) {
  state.filters.showAi = !!event.target.checked;
  renderTimeline();
}

async function jumpToDate() {
  const value = refs.timelineDateJump.value;
  if (!value) return;
  refs.timelineStatus.textContent = "指定日を読込中...";
  try {
    const around = new Date(`${value}T12:00:00`).toISOString();
    const response = await api(
      `/api/timeline?around=${encodeURIComponent(around)}&before=${INITIAL_TIMELINE_HOURS}&after=${INITIAL_TIMELINE_HOURS}`
    );
    state.initialScrollDone = true;
    state.noMorePast = false;
    state.noMoreFuture = false;
    setTimelineState(response);
    renderTimeline();
    scrollToNow("instant");
  } catch (error) {
    refs.timelineStatus.textContent = error.message;
  }
}

function getVisibleEntries(entries) {
  return entries.filter(matchesEntryFilter);
}

function matchesEntryFilter(entry) {
  if (state.filters.todoOnly && !(entry.type === "todo" && entry.status === "active")) {
    return false;
  }
  if (!state.filters.showAi && entry.source === "ai") {
    return false;
  }
  if (!matchesTypeFilter(entry)) {
    return false;
  }
  if (!matchesSearchFilter(entry)) {
    return false;
  }
  return true;
}

function matchesTypeFilter(entry) {
  return state.filters.types.some((type) => matchesEntryTypeGroup(entry, type));
}

function matchesEntryTypeGroup(entry, type) {
  if (type === "chat") {
    return entry.type === "chat_ai" || entry.type === "chat_user";
  }
  if (type === "todo") {
    return entry.type === "todo" || entry.type === "todo_done";
  }
  return entry.type === type;
}

function matchesSearchFilter(entry) {
  if (!state.filters.search) return true;
  const haystack = [entry.type, entry.title, entry.summary, entry.content]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(state.filters.search);
}

function renderQuickTypeOptions() {
  refs.detailQuickTypeSelect.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "変更先を選択";
  refs.detailQuickTypeSelect.appendChild(placeholder);
  if (!state.selectedEntry) return;
  for (const type of DETAIL_TYPE_OPTIONS) {
    if (type === state.selectedEntry.type) continue;
    const option = document.createElement("option");
    option.value = type;
    option.textContent = type;
    refs.detailQuickTypeSelect.appendChild(option);
  }
  refs.detailQuickTypeSelect.value = "";
}

async function handleQuickTypeSelect(event) {
  const { value } = event.target;
  if (!value) return;
  await quickChangeEntryType(value);
  refs.detailQuickTypeSelect.value = "";
}

async function quickChangeEntryType(type) {
  if (!state.selectedEntryId || !state.selectedEntry) return;
  refs.detailStatusMessage.textContent = `${type} に変更中...`;
  try {
    const previous = snapshotEntry(state.selectedEntry);
    const body = { type };
    if (type === "todo") body.status = "active";
    if (type === "todo_done") body.status = "done";
    state.selectedEntry = await api(`/api/entries/${encodeURIComponent(state.selectedEntryId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    setUndoAction({
      entryId: state.selectedEntryId,
      label: "種別変更を戻す",
      payload: previous,
    });
    refs.detailStatusMessage.textContent = `${type} に変更しました`;
    renderDetail();
    await loadTimeline();
  } catch (error) {
    refs.detailStatusMessage.textContent = error.message;
  }
}

function snapshotEntry(entry) {
  return {
    type: entry.type,
    title: entry.title,
    content: entry.content,
    timestamp: entry.timestamp,
    status: entry.status,
  };
}

function setUndoAction(action) {
  state.lastUndoAction = action;
  renderUndoState();
}

function renderUndoState() {
  if (!state.lastUndoAction) {
    refs.detailUndo.classList.add("hidden");
    return;
  }
  refs.detailUndo.classList.remove("hidden");
  refs.detailUndo.textContent = state.lastUndoAction.label || "直前を戻す";
}

async function undoLastAction() {
  if (!state.lastUndoAction) return;
  const action = state.lastUndoAction;
  refs.detailStatusMessage.textContent = "巻き戻し中...";
  try {
    await api(`/api/entries/${encodeURIComponent(action.entryId)}`, {
      method: "PATCH",
      body: JSON.stringify(action.payload),
    });
    state.lastUndoAction = null;
    refs.detailStatusMessage.textContent = "元に戻しました";
    if (state.selectedEntryId === action.entryId) {
      await selectEntry(state.selectedEntryId);
    }
    await loadTimeline();
    renderUndoState();
  } catch (error) {
    refs.detailStatusMessage.textContent = error.message;
  }
}

function findEntryById(entryId) {
  return state.entries.find((entry) => entry.id === entryId) || null;
}

function chatDraftKey() {
  return `${CHAT_DRAFT_KEY_PREFIX}${state.workspace?.path || "default"}`;
}

function persistChatDraft() {
  try {
    localStorage.setItem(chatDraftKey(), refs.chatInput.value);
    if (refs.chatInput.value.trim()) {
      refs.chatStatus.textContent = "下書きを保存中";
    }
  } catch (error) {
    console.warn("persistChatDraft failed:", error);
  }
}

function restoreChatDraft() {
  try {
    const draft = localStorage.getItem(chatDraftKey()) || "";
    if (draft && !refs.chatInput.value) {
      refs.chatInput.value = draft;
      refs.chatStatus.textContent = "下書きを復元しました";
    }
  } catch (error) {
    console.warn("restoreChatDraft failed:", error);
  }
}

function clearChatDraft(options = {}) {
  refs.chatInput.value = "";
  try {
    localStorage.removeItem(chatDraftKey());
    if (!options.preserveStatus) {
      refs.chatStatus.textContent = "下書きを破棄しました";
    }
  } catch (error) {
    console.warn("clearChatDraft failed:", error);
  }
}

// ---------------------------------------------------------------------------
// 設定パネル
// ---------------------------------------------------------------------------

async function openSettingsPanel() {
  refs.settingsPanel.classList.remove("hidden");
  refs.navSettings.classList.add("active");
  refs.navTimeline.classList.remove("active");
  await loadSettings();
}

function closeSettingsPanel() {
  refs.settingsPanel.classList.add("hidden");
  refs.navSettings.classList.remove("active");
  refs.navTimeline.classList.add("active");
}

async function loadSettings() {
  try {
    const s = await api("/api/settings");
    refs.sPersonality.value = s.ai.personality ?? "";
    refs.sOllamaUrl.value = s.ai.ollama_base_url;
    refs.sOllamaModel.value = s.ai.ollama_model;
    refs.sOllamaTimeout.value = s.ai.timeout_seconds;
    renderWorkers(s.workers);
    renderFeeds(s.feeds);
  } catch (e) {
    refs.sAiStatus.textContent = e.message;
  }
}

function renderWorkers(workers) {
  const labels = {
    activity: "活動ログ収集",
    browser: "ブラウザ履歴",
    info: "RSS / ニュース収集",
    analysis: "RSS 分析パイプライン",
    hourly_summary: "1時間まとめ生成",
    daily_digest: "日次振り返り",
    windows: "Windows フォアグラウンド",
  };
  refs.sWorkers.innerHTML = "";
  for (const [id, enabled] of Object.entries(workers)) {
    const row = document.createElement("label");
    row.className = "settings-toggle-row";
    row.innerHTML = `
      <span>${labels[id] ?? id}</span>
      <input type="checkbox" data-worker="${id}" ${enabled ? "checked" : ""} />
    `;
    row.querySelector("input").addEventListener("change", (e) => {
      updateWorker(id, e.target.checked);
    });
    refs.sWorkers.appendChild(row);
  }
}

async function updateWorker(workerId, enabled) {
  try {
    await api("/api/settings/workers", {
      method: "PATCH",
      body: JSON.stringify({ workers: { [workerId]: enabled } }),
    });
  } catch (e) {
    console.warn("worker update failed:", e);
  }
}

function renderFeeds(feeds) {
  refs.sFeeds.innerHTML = "";
  if (!feeds.length) {
    refs.sFeeds.textContent = "登録済みフィードなし";
    return;
  }
  for (const url of feeds) {
    const row = document.createElement("div");
    row.className = "settings-feed-row";
    const label = document.createElement("span");
    label.textContent = url;
    label.title = url;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ghost-button";
    btn.textContent = "削除";
    btn.addEventListener("click", () => deleteFeed(url));
    row.appendChild(label);
    row.appendChild(btn);
    refs.sFeeds.appendChild(row);
  }
}

async function savePersonality() {
  refs.sPersonalityStatus.textContent = "保存中...";
  try {
    await api("/api/settings/ai", {
      method: "PATCH",
      body: JSON.stringify({ personality: refs.sPersonality.value }),
    });
    refs.sPersonalityStatus.textContent = "保存しました";
  } catch (e) {
    refs.sPersonalityStatus.textContent = e.message;
  }
}

async function saveAiSettings() {
  refs.sAiStatus.textContent = "保存中...";
  try {
    await api("/api/settings/ai", {
      method: "PATCH",
      body: JSON.stringify({
        ollama_base_url: refs.sOllamaUrl.value.trim(),
        ollama_model: refs.sOllamaModel.value.trim(),
        timeout_seconds: parseInt(refs.sOllamaTimeout.value, 10),
      }),
    });
    refs.sAiStatus.textContent = "保存しました";
  } catch (e) {
    refs.sAiStatus.textContent = e.message;
  }
}

async function addFeed() {
  const url = refs.sFeedUrl.value.trim();
  if (!url) return;
  refs.sFeedStatus.textContent = "追加中...";
  try {
    const res = await api("/api/settings/feeds", {
      method: "POST",
      body: JSON.stringify({ url }),
    });
    refs.sFeedUrl.value = "";
    refs.sFeedStatus.textContent = "追加しました";
    renderFeeds(res.feeds);
  } catch (e) {
    refs.sFeedStatus.textContent = e.message;
  }
}

async function deleteFeed(url) {
  refs.sFeedStatus.textContent = "削除中...";
  try {
    const res = await api("/api/settings/feeds", {
      method: "DELETE",
      body: JSON.stringify({ url }),
    });
    refs.sFeedStatus.textContent = "削除しました";
    renderFeeds(res.feeds);
  } catch (e) {
    refs.sFeedStatus.textContent = e.message;
  }
}

function toDatetimeLocal(isoString) {
  const d = new Date(isoString);
  const pad = (n) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}
