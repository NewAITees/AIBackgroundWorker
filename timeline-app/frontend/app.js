import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { FBXLoader } from "three/addons/loaders/FBXLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import * as SkeletonUtils from "three/addons/utils/SkeletonUtils.js";
import { VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";

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
  detailAiPreviewContent: null,
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
    types: ["chat", "diary", "event", "todo", "news", "search", "memo", "system_log"],
    search: "",
    todoOnly: false,
    showAi: true,
  },
  lastUndoAction: null,
  weeklyReview: null,
};

const refs = {};
const vrmDebugConfig = {
  cameraTargetY: 0.72,
  cameraHeightFactor: 0.34,
  cameraWidthFactor: 0.44,
  cameraDepthFactor: 1.35,
  cameraYOffset: 0.015,
  leftShoulderZ: -0.015,
  rightShoulderZ: 0.015,
  leftUpperArmX: 0.03,
  rightUpperArmX: 0.03,
  leftUpperArmZ: -0.1,
  rightUpperArmZ: 0.1,
  leftLowerArmX: -0.08,
  rightLowerArmX: -0.08,
  leftLowerArmZ: -0.01,
  rightLowerArmZ: 0.01,
  leftHandZ: 0.003,
  rightHandZ: -0.003,
};
const vrmState = {
  renderer: null,
  scene: null,
  camera: null,
  controls: null,
  clock: null,
  currentVrm: null,
  baseSceneY: 0,
  idleRig: null,
  idleAnimation: null,
  animationFrameId: null,
  resizeObserver: null,
};
const VRM_IDLE_ANIMATION_FILE = "@KA_Idle01_breathing.FBX";
const VRM_ANIMATION_BONE_MAP = {
  hips: "Hips",
  spine: "Spine",
  chest: "Chest",
  upperChest: "Upper Chest",
  neck: "Neck",
  head: "Head",
  leftShoulder: "Shoulder_L",
  leftUpperArm: "Upper Arm_L",
  leftLowerArm: "Lower Arm_L",
  leftHand: "Hand_L",
  rightShoulder: "Shoulder_R",
  rightUpperArm: "Upper Arm_R",
  rightLowerArm: "Lower Arm_R",
  rightHand: "Hand_R",
  leftUpperLeg: "Upper Leg_L",
  leftLowerLeg: "Lower Leg_L",
  leftFoot: "Foot_L",
  rightUpperLeg: "Upper Leg_R",
  rightLowerLeg: "Lower Leg_R",
  rightFoot: "Foot_R",
};
const CHAT_DRAFT_KEY_PREFIX = "timeline-chat-draft:";
const INITIAL_TIMELINE_HOURS = 12;
const PAGING_TIMELINE_HOURS = 24;
const TIMELINE_FILTER_OPTIONS = ["chat", "diary", "event", "todo", "news", "search", "memo", "system_log"];
const DETAIL_TYPE_OPTIONS = [
  "chat_user",
  "chat_ai",
  "diary",
  "event",
  "todo",
  "todo_done",
  "memo",
  "news",
  "search",
  "system_log",
];

document.addEventListener("DOMContentLoaded", async () => {
  cacheRefs();
  bindEvents();
  initVrmDebugControls();
  await initVrmPane();
  await refreshWorkspace();
  await refreshAIStatus();
});

function cacheRefs() {
  refs.aiToggle = document.getElementById("ai-toggle");
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
  refs.vrmCanvas = document.getElementById("vrm-canvas");
  refs.vrmDebugPanel = document.getElementById("vrm-debug-panel");
  refs.vrmDebugControls = document.getElementById("vrm-debug-controls");
  refs.vrmDebugOutput = document.getElementById("vrm-debug-output");
  refs.vrmDebugCopy = document.getElementById("vrm-debug-copy");
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
  refs.detailRecurringPanel = document.getElementById("detail-recurring-panel");
  refs.detailRecurringEnabled = document.getElementById("detail-recurring-enabled");
  refs.detailRecurringFields = document.getElementById("detail-recurring-fields");
  refs.detailRecurringRule = document.getElementById("detail-recurring-rule");
  refs.detailRecurringInterval = document.getElementById("detail-recurring-interval");
  refs.detailRecurringCount = document.getElementById("detail-recurring-count");
  refs.detailRecurringWeekdays = document.getElementById("detail-recurring-weekdays");
  refs.detailStatusInput = document.getElementById("detail-status-input");
  refs.detailEditToggle = document.getElementById("detail-edit-toggle");
  refs.detailReadonly = document.getElementById("detail-readonly");
  refs.detailAiPanel = document.getElementById("detail-ai-panel");
  refs.detailAiInstruction = document.getElementById("detail-ai-instruction");
  refs.detailAiStatus = document.getElementById("detail-ai-status");
  refs.detailAiSubmit = document.getElementById("detail-ai-submit");
  refs.detailAiPreview = document.getElementById("detail-ai-preview");
  refs.detailAiPreviewContent = document.getElementById("detail-ai-preview-content");
  refs.detailAiSave = document.getElementById("detail-ai-save");
  refs.detailAiCancel = document.getElementById("detail-ai-cancel");
  refs.detailChatPanel = document.getElementById("detail-chat-panel");
  refs.detailChatForm = document.getElementById("detail-chat-form");
  refs.detailChatInput = document.getElementById("detail-chat-input");
  refs.detailChatStatus = document.getElementById("detail-chat-status");
  refs.detailChatSend = document.getElementById("detail-chat-send");
  refs.detailStatusMessage = document.getElementById("detail-status-message");
  refs.detailUndo = document.getElementById("detail-undo");
  refs.detailFormSubmit = document.getElementById("detail-form");
  refs.jumpNow = document.getElementById("jump-now");
  refs.nowAnchor = document.getElementById("now-anchor");
  // settings panel
  refs.navTimeline = document.getElementById("nav-timeline");
  refs.navReview = document.getElementById("nav-review");
  refs.navSettings = document.getElementById("nav-settings");
  refs.settingsPanel = document.getElementById("settings-panel");
  refs.settingsClose = document.getElementById("settings-close");
  refs.settingsTabButtons = Array.from(document.querySelectorAll("[data-settings-tab]"));
  refs.settingsTabPanels = Array.from(document.querySelectorAll("[data-settings-tab-panel]"));
  refs.reviewPanel = document.getElementById("review-panel");
  refs.reviewClose = document.getElementById("review-close");
  refs.reviewAnchorDate = document.getElementById("review-anchor-date");
  refs.reviewReload = document.getElementById("review-reload");
  refs.reviewStatus = document.getElementById("review-status");
  refs.reviewOverview = document.getElementById("review-overview");
  refs.reviewPerspectives = document.getElementById("review-perspectives");
  refs.reviewBigFive = document.getElementById("review-big-five");
  refs.reviewEntries = document.getElementById("review-entries");
  refs.sPersonality = document.getElementById("s-personality");
  refs.sPersonalityStatus = document.getElementById("s-personality-status");
  refs.sPersonalitySave = document.getElementById("s-personality-save");
  refs.sOllamaUrl = document.getElementById("s-ollama-url");
  refs.sOllamaModel = document.getElementById("s-ollama-model");
  refs.sOllamaTimeout = document.getElementById("s-ollama-timeout");
  refs.sAiStatus = document.getElementById("s-ai-status");
  refs.sAiSave = document.getElementById("s-ai-save");
  refs.sVrmModel = document.getElementById("s-vrm-model");
  refs.sVrmStatus = document.getElementById("s-vrm-status");
  refs.sVrmSave = document.getElementById("s-vrm-save");
  refs.sWorkers = document.getElementById("s-workers");
  refs.sReviewEnabled = document.getElementById("s-review-enabled");
  refs.sBigFiveEnabled = document.getElementById("s-big-five-enabled");
  refs.sDailyReviewTime = document.getElementById("s-daily-review-time");
  refs.sWeeklyReviewWeekday = document.getElementById("s-weekly-review-weekday");
  refs.sWeeklyReviewTime = document.getElementById("s-weekly-review-time");
  refs.sReviewPerspectives = document.getElementById("s-review-perspectives");
  refs.sBigFivePerspectives = document.getElementById("s-big-five-perspectives");
  refs.sBigFiveFocusTraits = document.getElementById("s-big-five-focus-traits");
  refs.sTraitTargetOpenness = document.getElementById("s-trait-target-openness");
  refs.sTraitTargetConscientiousness = document.getElementById("s-trait-target-conscientiousness");
  refs.sTraitTargetExtraversion = document.getElementById("s-trait-target-extraversion");
  refs.sTraitTargetAgreeableness = document.getElementById("s-trait-target-agreeableness");
  refs.sTraitTargetNeuroticism = document.getElementById("s-trait-target-neuroticism");
  refs.sBehaviorStatus = document.getElementById("s-behavior-status");
  refs.sBehaviorSave = document.getElementById("s-behavior-save");
  refs.sInfoLimit = document.getElementById("s-info-limit");
  refs.sInfoUseOllama = document.getElementById("s-info-use-ollama");
  refs.sAnalyzeBatch = document.getElementById("s-analyze-batch");
  refs.sDeepLimit = document.getElementById("s-deep-limit");
  refs.sFutureDailyDays = document.getElementById("s-future-daily-days");
  refs.sPipelineStatus = document.getElementById("s-pipeline-status");
  refs.sPipelineSave = document.getElementById("s-pipeline-save");
  refs.sFeeds = document.getElementById("s-feeds");
  refs.sFeedUrl = document.getElementById("s-feed-url");
  refs.sFeedAdd = document.getElementById("s-feed-add");
  refs.sFeedStatus = document.getElementById("s-feed-status");
  refs.sSearchQueries = document.getElementById("s-search-queries");
  refs.sSearchQuery = document.getElementById("s-search-query");
  refs.sSearchQueryAdd = document.getElementById("s-search-query-add");
  refs.sSearchQueryStatus = document.getElementById("s-search-query-status");
  refs.sNewsSourceStats = document.getElementById("s-news-source-stats");
  refs.sNewsCategoryStats = document.getElementById("s-news-category-stats");
  refs.sNewsStatsStatus = document.getElementById("s-news-stats-status");
}

function bindEvents() {
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
  refs.detailAiSubmit.addEventListener("click", requestAiEditPreview);
  refs.detailAiSave.addEventListener("click", saveAiEditPreview);
  refs.detailAiCancel.addEventListener("click", cancelAiEditPreview);
  refs.detailChatForm.addEventListener("submit", submitDetailChat);
  refs.detailForm.addEventListener("submit", saveDetail);
  refs.detailTypeInput.addEventListener("change", renderRecurringFieldsState);
  refs.detailRecurringEnabled.addEventListener("change", renderRecurringFieldsState);
  refs.detailRecurringRule.addEventListener("change", renderRecurringFieldsState);
  refs.detailUndo.addEventListener("click", undoLastAction);
  refs.jumpNow.addEventListener("click", () => scrollToNow("smooth"));
  refs.navReview.addEventListener("click", openReviewPanel);
  refs.navSettings.addEventListener("click", openSettingsPanel);
  refs.navTimeline.addEventListener("click", closeOverlayPanels);
  refs.settingsClose.addEventListener("click", closeSettingsPanel);
  refs.reviewClose.addEventListener("click", closeReviewPanel);
  refs.reviewReload.addEventListener("click", loadWeeklyReview);
  refs.settingsTabButtons.forEach((button) => {
    button.addEventListener("click", () => setSettingsTab(button.dataset.settingsTab || "general"));
  });
  refs.vrmDebugCopy?.addEventListener("click", copyVrmDebugConfig);
  refs.sPersonalitySave.addEventListener("click", savePersonality);
  refs.sAiSave.addEventListener("click", saveAiSettings);
  refs.sVrmSave.addEventListener("click", saveVrmSettings);
  refs.sBehaviorSave.addEventListener("click", saveBehaviorSettings);
  refs.sPipelineSave.addEventListener("click", savePipelineSettings);
  refs.sFeedAdd.addEventListener("click", addFeed);
  refs.sSearchQueryAdd.addEventListener("click", addSearchQuery);
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

async function initVrmPane() {
  if (!refs.vrmCanvas) return;
  if (!vrmState.renderer) {
    setupVrmScene();
  }

  try {
    const vrm = await api("/api/vrm");
    await loadVrmModel(vrm.url);
  } catch (error) {
    console.error("VRM 読み込み失敗", error);
  }
}

function setupVrmScene() {
  const canvas = refs.vrmCanvas;
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  const controls = new OrbitControls(camera, canvas);
  const clock = new THREE.Clock();

  camera.position.set(0, 1.35, 2.1);
  controls.target.set(0, 1.15, 0);
  controls.enablePan = false;
  controls.enableZoom = false;
  controls.minPolarAngle = Math.PI / 2.4;
  controls.maxPolarAngle = Math.PI / 1.8;
  controls.update();

  scene.add(new THREE.AmbientLight(0xffffff, 1.2));
  const directionalLight = new THREE.DirectionalLight(0xfff4df, 1.8);
  directionalLight.position.set(1.8, 2.2, 2.6);
  scene.add(directionalLight);

  const rimLight = new THREE.DirectionalLight(0xf3b885, 0.8);
  rimLight.position.set(-1.2, 1.1, -1.8);
  scene.add(rimLight);

  vrmState.renderer = renderer;
  vrmState.scene = scene;
  vrmState.camera = camera;
  vrmState.controls = controls;
  vrmState.clock = clock;

  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  resizeVrmRenderer();
  if (!vrmState.resizeObserver) {
    vrmState.resizeObserver = new ResizeObserver(() => resizeVrmRenderer());
    vrmState.resizeObserver.observe(refs.vrmCanvas);
  }
  startVrmRenderLoop();
}

async function loadVrmModel(url) {
  const loader = new GLTFLoader();
  loader.crossOrigin = "anonymous";
  loader.register((parser) => new VRMLoaderPlugin(parser));

  const gltf = await loader.loadAsync(url);
  const vrm = gltf.userData.vrm;
  if (!vrm) {
    throw new Error("VRM として解釈できませんでした");
  }

  if (vrmState.currentVrm) {
    vrmState.scene.remove(vrmState.currentVrm.scene);
    VRMUtils.deepDispose(vrmState.currentVrm.scene);
  }
  vrmState.idleAnimation = null;

  VRMUtils.rotateVRM0(vrm);
  vrm.scene.rotation.y = 0;
  vrmState.scene.add(vrm.scene);
  vrmState.currentVrm = vrm;
  fitVrmInFrame(vrm);
  setupIdleRig(vrm);
  try {
    await loadIdleAnimation(vrm);
  } catch (error) {
    console.error("VRM idle animation 読み込み失敗", error);
  }
}

function fitVrmInFrame(vrm) {
  if (!vrmState.camera || !vrmState.controls) {
    throw new Error("VRM カメラが初期化されていません");
  }

  vrm.scene.updateMatrixWorld(true);
  let box = new THREE.Box3().setFromObject(vrm.scene);
  if (box.isEmpty()) {
    throw new Error("VRM のサイズを取得できませんでした");
  }

  const initialCenter = box.getCenter(new THREE.Vector3());
  vrm.scene.position.x -= initialCenter.x;
  vrm.scene.position.z -= initialCenter.z;
  vrm.scene.position.y -= box.min.y;
  vrm.scene.updateMatrixWorld(true);

  box = new THREE.Box3().setFromObject(vrm.scene);
  const size = box.getSize(new THREE.Vector3());
  const target = new THREE.Vector3(0, size.y * vrmDebugConfig.cameraTargetY, 0);
  const verticalFov = THREE.MathUtils.degToRad(vrmState.camera.fov);
  const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * vrmState.camera.aspect);
  const distanceForHeight = (size.y * vrmDebugConfig.cameraHeightFactor) / Math.tan(verticalFov / 2);
  const distanceForWidth = (size.x * vrmDebugConfig.cameraWidthFactor) / Math.tan(horizontalFov / 2);
  const distance = Math.max(distanceForHeight, distanceForWidth, size.z * vrmDebugConfig.cameraDepthFactor, 0.8);

  vrmState.camera.position.set(0, target.y + size.y * vrmDebugConfig.cameraYOffset, distance);
  vrmState.camera.near = Math.max(0.01, distance / 100);
  vrmState.camera.far = Math.max(20, distance * 20);
  vrmState.camera.updateProjectionMatrix();
  vrmState.controls.target.copy(target);
  vrmState.controls.update();
  vrmState.baseSceneY = vrm.scene.position.y;
  renderVrmDebugOutput();
}

function setupIdleRig(vrm) {
  const humanoid = vrm.humanoid;
  if (!humanoid) {
    vrmState.idleRig = null;
    return;
  }

  const definitions = [
    { name: "hips", base: [0.0, 0.02, 0.0], breath: [0.01, 0.0, 0.0], sway: [0.0, 0.015, 0.0] },
    { name: "spine", base: [0.05, 0.0, 0.0], breath: [0.01, 0.0, 0.0], sway: [0.0, 0.01, 0.01] },
    { name: "chest", base: [0.09, 0.0, 0.0], breath: [0.025, 0.0, 0.0], sway: [0.0, 0.012, 0.012] },
    { name: "upperChest", base: [0.07, 0.0, 0.0], breath: [0.03, 0.0, 0.0], sway: [0.0, 0.015, 0.015] },
    { name: "neck", base: [-0.02, 0.0, 0.0], breath: [0.008, 0.0, 0.0], sway: [0.0, 0.012, 0.0] },
    { name: "head", base: [-0.03, 0.0, 0.0], breath: [0.01, 0.0, 0.0], sway: [0.0, 0.018, 0.0] },
    { name: "leftShoulder", base: [0.0, 0.0, vrmDebugConfig.leftShoulderZ], breath: [0.004, 0.0, -0.002], sway: [0.0, 0.0, -0.003] },
    { name: "rightShoulder", base: [0.0, 0.0, vrmDebugConfig.rightShoulderZ], breath: [0.004, 0.0, 0.002], sway: [0.0, 0.0, 0.003] },
    { name: "leftUpperArm", base: [vrmDebugConfig.leftUpperArmX, 0.0, vrmDebugConfig.leftUpperArmZ], breath: [0.005, 0.0, -0.003], sway: [0.0, 0.004, -0.004] },
    { name: "rightUpperArm", base: [vrmDebugConfig.rightUpperArmX, 0.0, vrmDebugConfig.rightUpperArmZ], breath: [0.005, 0.0, 0.003], sway: [0.0, -0.004, 0.004] },
    { name: "leftLowerArm", base: [vrmDebugConfig.leftLowerArmX, 0.0, vrmDebugConfig.leftLowerArmZ], breath: [0.004, 0.0, 0.0], sway: [0.0, 0.0, -0.003] },
    { name: "rightLowerArm", base: [vrmDebugConfig.rightLowerArmX, 0.0, vrmDebugConfig.rightLowerArmZ], breath: [0.004, 0.0, 0.0], sway: [0.0, 0.0, 0.003] },
    { name: "leftHand", base: [0.0, 0.0, vrmDebugConfig.leftHandZ], breath: [0.0, 0.0, 0.001], sway: [0.0, 0.0, 0.001] },
    { name: "rightHand", base: [0.0, 0.0, vrmDebugConfig.rightHandZ], breath: [0.0, 0.0, -0.001], sway: [0.0, 0.0, -0.001] },
    { name: "leftUpperLeg", base: [0.03, 0.0, 0.02], breath: [0.0, 0.0, 0.0], sway: [0.0, 0.006, 0.0] },
    { name: "rightUpperLeg", base: [0.03, 0.0, -0.02], breath: [0.0, 0.0, 0.0], sway: [0.0, -0.006, 0.0] },
  ];

  vrmState.idleRig = definitions
    .map((definition) => {
      const node =
        humanoid.getNormalizedBoneNode?.(definition.name) ||
        humanoid.getRawBoneNode?.(definition.name) ||
        null;
      if (!node) return null;
      return {
        ...definition,
        node,
        baseQuaternion: node.quaternion.clone(),
      };
    })
    .filter(Boolean);

  applyIdlePose(0);
  renderVrmDebugOutput();
}

async function loadIdleAnimation(vrm) {
  const humanoid = vrm.humanoid;
  if (!humanoid) return;

  const loader = new FBXLoader();
  const sourceRoot = await loader.loadAsync(`/api/vrm/animation/${encodeURIComponent(VRM_IDLE_ANIMATION_FILE)}`);
  const clip = sourceRoot.animations?.[0];
  if (!clip) return;

  const normalizedRoot = humanoid.normalizedHumanBonesRoot;
  if (!normalizedRoot) return;

  Object.entries(VRM_ANIMATION_BONE_MAP).forEach(([humanoidName]) => {
    const node = humanoid.getNormalizedBoneNode?.(humanoidName);
    if (node) {
      node.userData.humanoidBoneName = humanoidName;
    }
  });

  sourceRoot.visible = false;
  sourceRoot.updateMatrixWorld(true);
  const sourceMixer = new THREE.AnimationMixer(sourceRoot);
  const action = sourceMixer.clipAction(clip);
  action.setLoop(THREE.LoopRepeat, Infinity);
  action.clampWhenFinished = false;
  action.play();

  vrmState.idleAnimation = {
    sourceRoot,
    sourceMixer,
    sourceHelper: new THREE.SkeletonHelper(sourceRoot),
    targetHelper: new THREE.SkeletonHelper(normalizedRoot),
  };
}

const VRM_DEBUG_CONTROLS = [
  { key: "cameraTargetY", label: "targetY", min: 0.4, max: 0.9, step: 0.01 },
  { key: "cameraHeightFactor", label: "heightFit", min: 0.2, max: 0.8, step: 0.01 },
  { key: "cameraWidthFactor", label: "widthFit", min: 0.2, max: 0.8, step: 0.01 },
  { key: "cameraDepthFactor", label: "depthFit", min: 0.6, max: 2.0, step: 0.01 },
  { key: "cameraYOffset", label: "cameraYOffset", min: -0.1, max: 0.2, step: 0.005 },
  { key: "leftShoulderZ", label: "leftShoulderZ", min: -0.5, max: 0.2, step: 0.005 },
  { key: "rightShoulderZ", label: "rightShoulderZ", min: -0.2, max: 0.5, step: 0.005 },
  { key: "leftUpperArmX", label: "leftUpperArmX", min: -0.3, max: 0.4, step: 0.005 },
  { key: "rightUpperArmX", label: "rightUpperArmX", min: -0.3, max: 0.4, step: 0.005 },
  { key: "leftUpperArmZ", label: "leftUpperArmZ", min: -0.8, max: 0.2, step: 0.005 },
  { key: "rightUpperArmZ", label: "rightUpperArmZ", min: -0.2, max: 0.8, step: 0.005 },
  { key: "leftLowerArmX", label: "leftLowerArmX", min: -0.5, max: 0.2, step: 0.005 },
  { key: "rightLowerArmX", label: "rightLowerArmX", min: -0.5, max: 0.2, step: 0.005 },
  { key: "leftLowerArmZ", label: "leftLowerArmZ", min: -0.3, max: 0.2, step: 0.005 },
  { key: "rightLowerArmZ", label: "rightLowerArmZ", min: -0.2, max: 0.3, step: 0.005 },
  { key: "leftHandZ", label: "leftHandZ", min: -0.1, max: 0.1, step: 0.001 },
  { key: "rightHandZ", label: "rightHandZ", min: -0.1, max: 0.1, step: 0.001 },
];

function initVrmDebugControls() {
  if (!refs.vrmDebugControls) return;
  refs.vrmDebugControls.innerHTML = "";
  VRM_DEBUG_CONTROLS.forEach((control) => {
    const row = document.createElement("label");
    row.className = "vrm-debug-row";
    row.innerHTML = `
      <span>${control.label}</span>
      <input type="range" min="${control.min}" max="${control.max}" step="${control.step}" value="${vrmDebugConfig[control.key]}">
      <span class="vrm-debug-value">${Number(vrmDebugConfig[control.key]).toFixed(3)}</span>
    `;
    const input = row.querySelector("input");
    const value = row.querySelector(".vrm-debug-value");
    input.addEventListener("input", () => {
      vrmDebugConfig[control.key] = Number(input.value);
      value.textContent = vrmDebugConfig[control.key].toFixed(3);
      applyVrmDebugConfig();
    });
    refs.vrmDebugControls.appendChild(row);
  });
  renderVrmDebugOutput();
}

function applyVrmDebugConfig() {
  if (!vrmState.currentVrm) {
    renderVrmDebugOutput();
    return;
  }
  fitVrmInFrame(vrmState.currentVrm);
  setupIdleRig(vrmState.currentVrm);
}

function renderVrmDebugOutput() {
  if (!refs.vrmDebugOutput) return;
  refs.vrmDebugOutput.textContent = JSON.stringify(vrmDebugConfig, null, 2);
}

async function copyVrmDebugConfig() {
  const payload = JSON.stringify(vrmDebugConfig, null, 2);
  try {
    await navigator.clipboard.writeText(payload);
  } catch (error) {
    console.error("VRM debug 値のコピーに失敗しました", error);
  }
}

function applyIdlePose(elapsed) {
  if (!vrmState.currentVrm || !vrmState.idleRig) return;

  const breath = Math.sin(elapsed * 1.35);
  const sway = Math.sin(elapsed * 0.55);
  const secondary = Math.sin(elapsed * 0.82 + 1.3);

  vrmState.idleRig.forEach((bone) => {
    const euler = new THREE.Euler(
      bone.base[0] + bone.breath[0] * breath + bone.sway[0] * sway,
      bone.base[1] + bone.breath[1] * breath + bone.sway[1] * secondary,
      bone.base[2] + bone.breath[2] * breath + bone.sway[2] * sway,
      "XYZ",
    );
    const offset = new THREE.Quaternion().setFromEuler(euler);
    bone.node.quaternion.copy(bone.baseQuaternion).multiply(offset);
  });
}

function resizeVrmRenderer() {
  if (!vrmState.renderer || !vrmState.camera || !refs.vrmCanvas) return;
  const width = refs.vrmCanvas.clientWidth || refs.vrmCanvas.parentElement?.clientWidth || 1;
  const height = refs.vrmCanvas.clientHeight || refs.vrmCanvas.parentElement?.clientHeight || 1;
  vrmState.renderer.setSize(width, height, false);
  vrmState.camera.aspect = width / height;
  vrmState.camera.updateProjectionMatrix();
}

function startVrmRenderLoop() {
  if (vrmState.animationFrameId) {
    cancelAnimationFrame(vrmState.animationFrameId);
  }

  const tick = () => {
    vrmState.animationFrameId = requestAnimationFrame(tick);
    if (!vrmState.renderer || !vrmState.scene || !vrmState.camera || !vrmState.clock) return;

    const delta = vrmState.clock.getDelta();
    const elapsed = vrmState.clock.elapsedTime;
    if (vrmState.currentVrm) {
      if (vrmState.idleAnimation) {
        vrmState.idleAnimation.sourceMixer.update(delta);
        vrmState.idleAnimation.sourceRoot.updateMatrixWorld(true);
        SkeletonUtils.retarget(vrmState.idleAnimation.targetHelper, vrmState.idleAnimation.sourceHelper, {
          preserveBoneMatrix: true,
          preserveBonePositions: true,
          useTargetMatrix: true,
          hip: "Hips",
          getBoneName: (bone) => VRM_ANIMATION_BONE_MAP[bone.userData?.humanoidBoneName] ?? null,
        });
      } else {
        applyIdlePose(elapsed);
      }
      vrmState.currentVrm.update(delta);
      vrmState.currentVrm.scene.rotation.y = Math.sin(elapsed * 0.45) * 0.03;
      vrmState.currentVrm.scene.position.y = vrmState.baseSceneY + Math.sin(elapsed * 1.35) * 0.012;
    }
    vrmState.controls?.update();
    vrmState.renderer.render(vrmState.scene, vrmState.camera);
  };

  tick();
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

  if (isCollectedInfoEntry(entry) && entry.related_ids && entry.related_ids.length > 0) {
    const articleIds = entry.related_ids.filter((id) => id.startsWith("collected-info-"));
    if (articleIds.length > 0) {
      const panel = document.createElement("div");
      panel.className = "news-articles-panel hidden";

      const expandBtn = document.createElement("button");
      expandBtn.className = "news-expand-btn";
      expandBtn.type = "button";
      expandBtn.textContent = `${entry.type === "search" ? "検索結果" : "記事"}を見る (${articleIds.length})`;
      expandBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = !panel.classList.contains("hidden");
        if (isOpen) {
          panel.classList.add("hidden");
          expandBtn.textContent = `${entry.type === "search" ? "検索結果" : "記事"}を見る (${articleIds.length})`;
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

function isCollectedInfoEntry(entry) {
  return (entry.type === "news" || entry.type === "search") && Array.isArray(entry.related_ids);
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
  row.dataset.sentiment = article.feedback?.sentiment || "";
  row.dataset.reportStatus = article.feedback?.report_status || "none";
  row.dataset.reportEntryId = article.feedback?.report_entry_id || "";

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
  reportBtn.addEventListener("click", () => handleGenerateReport(article.id, reportBtn, row));

  const likeBtn = document.createElement("button");
  likeBtn.type = "button";
  likeBtn.className = "article-btn like-btn";
  likeBtn.textContent = "👍";
  likeBtn.addEventListener("click", () => handleFeedback(article.id, "positive", likeBtn, dislikeBtn));

  const dislikeBtn = document.createElement("button");
  dislikeBtn.type = "button";
  dislikeBtn.className = "article-btn dislike-btn";
  dislikeBtn.textContent = "👎";
  dislikeBtn.addEventListener("click", () => handleFeedback(article.id, "negative", dislikeBtn, likeBtn));

  actions.appendChild(reportBtn);
  actions.appendChild(likeBtn);
  actions.appendChild(dislikeBtn);

  row.appendChild(link);
  row.appendChild(meta);
  row.appendChild(actions);
  syncArticleButtons(row, article.feedback || {});
  return row;
}

function syncArticleButtons(row, feedback) {
  const sentiment = feedback?.sentiment || "";
  const reportStatus = feedback?.report_status || "none";
  const reportEntryId = feedback?.report_entry_id || "";
  row.dataset.sentiment = sentiment;
  row.dataset.reportStatus = reportStatus;
  row.dataset.reportEntryId = reportEntryId;

  const likeBtn = row.querySelector(".like-btn");
  const dislikeBtn = row.querySelector(".dislike-btn");
  const reportBtn = row.querySelector(".report-btn");

  likeBtn?.classList.toggle("active", sentiment === "positive");
  dislikeBtn?.classList.toggle("active", sentiment === "negative");

  if (!reportBtn) return;

  reportBtn.disabled = false;
  reportBtn.classList.toggle("is-done", reportStatus === "done");
  reportBtn.classList.toggle("is-busy", reportStatus === "requested" || reportStatus === "running");

  if (reportStatus === "done") {
    reportBtn.textContent = "生成済み";
    reportBtn.disabled = true;
  } else if (reportStatus === "requested") {
    reportBtn.textContent = "生成待ち…";
    reportBtn.disabled = true;
  } else if (reportStatus === "running") {
    reportBtn.textContent = "生成中…";
    reportBtn.disabled = true;
  } else if (reportStatus === "failed") {
    reportBtn.textContent = "再生成";
  } else {
    reportBtn.textContent = "レポート生成";
  }
}

async function handleFeedback(articleId, type, activeBtn, oppositeBtn) {
  try {
    const response = await api(`/api/news/articles/${articleId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ type }),
    });
    syncArticleButtons(activeBtn.closest(".news-article-row"), response.feedback);
  } catch (err) {
    console.warn("feedback failed:", err);
  }
}

async function handleGenerateReport(articleId, btn, row) {
  syncArticleButtons(row, {
    sentiment: row.dataset.sentiment || null,
    report_status: "requested",
    report_entry_id: row.dataset.reportEntryId || null,
  });
  try {
    const response = await api(`/api/news/articles/${articleId}/generate_report`, { method: "POST" });
    syncArticleButtons(row, response.feedback);
  } catch (err) {
    syncArticleButtons(row, {
      sentiment: row.dataset.sentiment || null,
      report_status: "failed",
      report_entry_id: row.dataset.reportEntryId || null,
    });
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
  state.detailAiPreviewContent = null;
  refs.detailAiInstruction.value = "";
  refs.detailAiStatus.textContent = "";
  refs.detailChatInput.value = "";
  refs.detailChatStatus.textContent = "";
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
  refs.detailMeta.textContent = buildDetailMeta(state.selectedEntry);
  refs.detailContent.innerHTML = renderEntryMarkdown(state.selectedEntry);
  refs.detailTitleInput.value = state.selectedEntry.title || "";
  refs.detailContentInput.value = state.selectedEntry.content;
  refs.detailTypeInput.value = state.selectedEntry.type;
  refs.detailTimestampInput.value = toDatetimeLocal(state.selectedEntry.timestamp);
  populateRecurringForm(state.selectedEntry);
  refs.detailStatusInput.value = state.selectedEntry.status;
  renderDetailAiState();
  renderDetailChatState();
  renderQuickTypeOptions();
  renderUndoState();
  applyDetailMode();
}

function buildDetailMeta(entry) {
  const parts = [`${formatDateTime(entry.timestamp)}`, entry.status];
  const traits = entry.meta?.traits || {};
  const traitParts = Object.entries(traits)
    .filter(([, value]) => Number(value) > 0)
    .map(([trait, value]) => `${trait}:${Number(value).toFixed(2)}`);
  if (traitParts.length) {
    parts.push(`Big Five ${traitParts.join(", ")}`);
  }
  return parts.join(" | ");
}

function toggleDetailEdit() {
  if (!state.selectedEntry) return;
  state.editMode = !state.editMode;
  applyDetailMode();
}

function applyDetailMode() {
  const aiEditable = isAiEditableEntry(state.selectedEntry);
  refs.detailReadonly.classList.toggle("hidden", state.editMode);
  refs.detailForm.classList.toggle("hidden", !state.editMode);
  refs.detailAiPanel.classList.toggle("hidden", state.editMode || !aiEditable);
  refs.detailChatPanel.classList.toggle("hidden", state.editMode || !isChatEntry(state.selectedEntry));
  refs.detailRecurringPanel.classList.toggle("hidden", !state.editMode || !isTodoType(refs.detailTypeInput.value));
  refs.detailEditToggle.textContent = state.editMode ? "閲覧" : "編集";
  renderRecurringFieldsState();
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
        meta: buildRecurringMetaPayload(),
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

function isTodoType(type) {
  return type === "todo" || type === "todo_done";
}

function populateRecurringForm(entry) {
  const meta = entry?.meta || {};
  refs.detailRecurringEnabled.checked = !!meta.recurring_enabled;
  refs.detailRecurringRule.value = meta.recurring_rule || "daily";
  refs.detailRecurringInterval.value = meta.recurring_interval || 1;
  refs.detailRecurringCount.value = meta.recurring_count || "";
  for (const input of refs.detailRecurringWeekdays.querySelectorAll('input[type="checkbox"]')) {
    input.checked = Array.isArray(meta.recurring_weekdays)
      ? meta.recurring_weekdays.includes(Number(input.value))
      : false;
  }
  renderRecurringFieldsState();
}

function renderRecurringFieldsState() {
  const todoVisible = state.editMode && isTodoType(refs.detailTypeInput.value);
  refs.detailRecurringPanel.classList.toggle("hidden", !todoVisible);
  const enabled = todoVisible && refs.detailRecurringEnabled.checked;
  refs.detailRecurringFields.classList.toggle("hidden", !enabled);
  const customWeekdays = enabled && refs.detailRecurringRule.value === "custom_weekdays";
  refs.detailRecurringWeekdays.classList.toggle("hidden", !customWeekdays);
}

function buildRecurringMetaPayload() {
  const currentMeta = state.selectedEntry?.meta || {};
  if (!isTodoType(refs.detailTypeInput.value)) {
    return currentMeta;
  }
  if (!refs.detailRecurringEnabled.checked) {
    return {
      ...currentMeta,
      recurring_enabled: false,
      recurring_rule: null,
      recurring_interval: null,
      recurring_count: null,
      recurring_weekdays: [],
      recurring_series_id: null,
      recurring_sequence: null,
      recurring_scheduled_for: null,
    };
  }
  return {
    ...currentMeta,
    recurring_enabled: true,
    recurring_rule: refs.detailRecurringRule.value,
    recurring_interval: Math.max(parseInt(refs.detailRecurringInterval.value || "1", 10), 1),
    recurring_count: refs.detailRecurringCount.value
      ? Math.max(parseInt(refs.detailRecurringCount.value, 10), 1)
      : null,
    recurring_weekdays:
      refs.detailRecurringRule.value === "custom_weekdays"
        ? Array.from(refs.detailRecurringWeekdays.querySelectorAll('input[type="checkbox"]:checked')).map(
            (input) => Number(input.value),
          )
        : [],
  };
}

function renderDetailAiState() {
  const visible = isAiEditableEntry(state.selectedEntry);
  const hasPreview = !!state.detailAiPreviewContent;
  refs.detailAiPanel.classList.toggle("hidden", !visible || state.editMode);
  refs.detailAiPreview.classList.toggle("hidden", !hasPreview);
  refs.detailAiPreviewContent.innerHTML = hasPreview
    ? DOMPurify.sanitize(marked.parse(state.detailAiPreviewContent || ""))
    : "";
  if (!visible) {
    refs.detailAiStatus.textContent = "";
    refs.detailAiInstruction.value = "";
  }
}

async function requestAiEditPreview() {
  if (!state.selectedEntryId) return;
  const instruction = refs.detailAiInstruction.value.trim();
  if (!instruction) {
    refs.detailAiStatus.textContent = "指示を入力してください";
    return;
  }

  refs.detailAiStatus.textContent = "AI が編集中...";
  refs.detailAiSubmit.disabled = true;
  try {
    const response = await api(`/api/entries/${encodeURIComponent(state.selectedEntryId)}/ai_edit`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    });
    state.detailAiPreviewContent = response.edited_content || "";
    refs.detailAiStatus.textContent = "プレビューを生成しました";
    renderDetailAiState();
  } catch (error) {
    refs.detailAiStatus.textContent = error.message;
  } finally {
    refs.detailAiSubmit.disabled = false;
  }
}

async function saveAiEditPreview() {
  if (!state.selectedEntryId || !state.detailAiPreviewContent) return;

  refs.detailAiStatus.textContent = "保存中...";
  refs.detailAiSave.disabled = true;
  try {
    const previous = snapshotEntry(state.selectedEntry);
    state.selectedEntry = await api(`/api/entries/${encodeURIComponent(state.selectedEntryId)}`, {
      method: "PATCH",
      body: JSON.stringify({ content: state.detailAiPreviewContent }),
    });
    setUndoAction({
      entryId: state.selectedEntryId,
      label: "AI編集前に戻す",
      payload: previous,
    });
    state.detailAiPreviewContent = null;
    refs.detailAiInstruction.value = "";
    refs.detailAiStatus.textContent = "AI 編集を保存しました";
    renderDetail();
    await loadTimeline();
  } catch (error) {
    refs.detailAiStatus.textContent = error.message;
  } finally {
    refs.detailAiSave.disabled = false;
  }
}

async function cancelAiEditPreview() {
  if (!state.selectedEntryId) return;

  refs.detailAiCancel.disabled = true;
  try {
    await api(`/api/entries/${encodeURIComponent(state.selectedEntryId)}/ai_edit_backup`, {
      method: "DELETE",
    });
    state.detailAiPreviewContent = null;
    refs.detailAiInstruction.value = "";
    refs.detailAiStatus.textContent = "AI 編集を破棄しました";
    renderDetailAiState();
    applyDetailMode();
  } catch (error) {
    refs.detailAiStatus.textContent = error.message;
  } finally {
    refs.detailAiCancel.disabled = false;
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

function renderDetailChatState() {
  const visible = isChatEntry(state.selectedEntry);
  refs.detailChatPanel.classList.toggle("hidden", !visible || state.editMode);
  if (!visible) {
    refs.detailChatStatus.textContent = "";
  }
}

async function submitDetailChat(event) {
  event.preventDefault();
  if (!state.selectedEntryId || !isChatEntry(state.selectedEntry)) return;
  if (state.aiPaused) {
    refs.detailChatStatus.textContent = "AI処理は一時停止中です";
    return;
  }

  const content = refs.detailChatInput.value.trim();
  if (!content) return;

  refs.detailChatStatus.textContent = "AIに送信中...";
  refs.detailChatSend.disabled = true;
  try {
    const threadId = state.selectedEntry.meta?.thread_id || null;
    const response = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        content,
        thread_id: threadId,
        save_entry: false,
      }),
    });
    if (response.thread_id && response.thread_id !== threadId) {
      state.selectedEntry = await api(`/api/entries/${encodeURIComponent(state.selectedEntryId)}`, {
        method: "PATCH",
        body: JSON.stringify({ meta: { thread_id: response.thread_id } }),
      });
    }
    state.selectedEntry = await api(`/api/entries/${encodeURIComponent(state.selectedEntryId)}/append_message`, {
      method: "POST",
      body: JSON.stringify({ role: "user", content }),
    });
    state.selectedEntry = await api(`/api/entries/${encodeURIComponent(state.selectedEntryId)}/append_message`, {
      method: "POST",
      body: JSON.stringify({ role: "assistant", content: response.reply || "" }),
    });
    refs.detailChatInput.value = "";
    refs.detailChatStatus.textContent = "会話を追記しました";
    renderDetail();
    await loadTimeline();
  } catch (error) {
    refs.detailChatStatus.textContent = error.message;
  } finally {
    refs.detailChatSend.disabled = false;
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

function isChatEntry(entry) {
  return !!entry && (entry.type === "chat" || entry.type === "chat_user" || entry.type === "chat_ai");
}

function isAiEditableEntry(entry) {
  return !!entry && !isChatEntry(entry);
}

function renderEntryMarkdown(entry) {
  const markdown = isChatEntry(entry) ? buildChatHistoryMarkdown(entry) : entry.content || "";
  return DOMPurify.sanitize(marked.parse(markdown));
}

function buildChatHistoryMarkdown(entry) {
  const messages = parseChatTranscript(entry.content || "");
  if (!messages.length) {
    const heading = entry.type === "chat_ai" ? "### Assistant" : "### User";
    return `${heading}\n\n${entry.content || ""}`;
  }
  return messages
    .map((message) => `### ${message.role === "assistant" ? "Assistant" : "User"}\n\n${message.content}`)
    .join("\n\n");
}

function parseChatTranscript(content) {
  const pattern = /<!--\s*chat-message:(user|assistant)\s*-->\s*\n([\s\S]*?)(?=(?:\n<!--\s*chat-message:)|$)/g;
  const messages = [];
  for (const match of content.matchAll(pattern)) {
    const role = match[1];
    const body = match[2].replace(/^###\s+(?:User|Assistant)\s*\n+/u, "").trim();
    if (!body) continue;
    messages.push({ role, content: body });
  }
  return messages;
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
  closeReviewPanel({ preserveNav: true });
  refs.settingsPanel.classList.remove("hidden");
  refs.navSettings.classList.add("active");
  refs.navTimeline.classList.remove("active");
  refs.navReview.classList.remove("active");
  setSettingsTab("general");
  await loadSettings();
}

function closeSettingsPanel() {
  refs.settingsPanel.classList.add("hidden");
  refs.navSettings.classList.remove("active");
  if (refs.reviewPanel.classList.contains("hidden")) {
    refs.navTimeline.classList.add("active");
  }
}

async function openReviewPanel() {
  closeSettingsPanel();
  refs.reviewPanel.classList.remove("hidden");
  refs.navReview.classList.add("active");
  refs.navTimeline.classList.remove("active");
  refs.navSettings.classList.remove("active");
  if (!refs.reviewAnchorDate.value) {
    refs.reviewAnchorDate.value = new Date().toISOString().slice(0, 10);
  }
  await loadWeeklyReview();
}

function closeReviewPanel(options = {}) {
  refs.reviewPanel.classList.add("hidden");
  refs.navReview.classList.remove("active");
  if (!options.preserveNav && refs.settingsPanel.classList.contains("hidden")) {
    refs.navTimeline.classList.add("active");
  }
}

function closeOverlayPanels() {
  closeSettingsPanel();
  closeReviewPanel();
}

async function loadSettings() {
  try {
    const [s, newsStats] = await Promise.all([
      api("/api/settings"),
      api("/api/news/feedback/stats").catch((error) => ({ __error: error.message })),
    ]);
    refs.sPersonality.value = s.ai.personality ?? "";
    refs.sOllamaUrl.value = s.ai.ollama_base_url;
    refs.sOllamaModel.value = s.ai.ollama_model;
    refs.sOllamaTimeout.value = s.ai.timeout_seconds;
    renderVrmOptions(s.vrm?.available_models ?? [], s.vrm?.model_filename ?? "");
    refs.sReviewEnabled.checked = !!s.behavior?.review_enabled;
    refs.sBigFiveEnabled.checked = !!s.behavior?.big_five_enabled;
    refs.sDailyReviewTime.value = buildTimeValue(s.behavior?.daily_review_hour ?? 0, s.behavior?.daily_review_minute ?? 0);
    refs.sWeeklyReviewWeekday.value = String(s.behavior?.weekly_review_weekday ?? 6);
    refs.sWeeklyReviewTime.value = buildTimeValue(s.behavior?.weekly_review_hour ?? 9, s.behavior?.weekly_review_minute ?? 0);
    refs.sReviewPerspectives.value = (s.behavior?.review_perspectives ?? []).join("\n");
    refs.sBigFivePerspectives.value = (s.behavior?.big_five_perspectives ?? []).join("\n");
    refs.sBigFiveFocusTraits.value = (s.behavior?.big_five_focus_traits ?? []).join("\n");
    applyTraitTargetSettings(s.behavior?.big_five_trait_targets ?? {});
    refs.sInfoLimit.value = s.pipeline.info_limit;
    refs.sInfoUseOllama.checked = !!s.pipeline.info_use_ollama;
    refs.sAnalyzeBatch.value = s.pipeline.analyze_batch_size;
    refs.sDeepLimit.value = s.pipeline.deep_limit;
    refs.sFutureDailyDays.value = s.pipeline.future_daily_days_ahead ?? 0;
    renderWorkers(s.workers);
    renderFeeds(s.feeds);
    renderSearchQueries(s.search_queries ?? []);
    if (newsStats && !newsStats.__error) {
      renderNewsStats(newsStats);
      refs.sNewsStatsStatus.textContent = "";
    } else {
      renderNewsStats(null);
      refs.sNewsStatsStatus.textContent = newsStats?.__error || "学習状態を取得できませんでした";
    }
  } catch (e) {
    refs.sAiStatus.textContent = e.message;
  }
}

function setSettingsTab(tabName) {
  refs.settingsTabButtons.forEach((button) => {
    const active = (button.dataset.settingsTab || "general") === tabName;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });
  refs.settingsTabPanels.forEach((panel) => {
    panel.classList.toggle("hidden", (panel.dataset.settingsTabPanel || "general") !== tabName);
  });
}

function renderVrmOptions(models, selected) {
  refs.sVrmModel.innerHTML = "";
  const autoOption = document.createElement("option");
  autoOption.value = "";
  autoOption.textContent = models.length ? "自動選択（先頭のモデル）" : "モデルなし";
  refs.sVrmModel.appendChild(autoOption);
  for (const model of models) {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    refs.sVrmModel.appendChild(option);
  }
  refs.sVrmModel.value = selected || "";
}

function renderWorkers(workers) {
  const labels = {
    activity: "活動ログ収集",
    browser: "ブラウザ履歴",
    info: "RSS / ニュース / 検索収集",
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

function renderSearchQueries(queries) {
  refs.sSearchQueries.innerHTML = "";
  if (!queries.length) {
    refs.sSearchQueries.textContent = "登録済み検索クエリなし";
    return;
  }
  for (const query of queries) {
    const row = document.createElement("div");
    row.className = "settings-feed-row";
    const label = document.createElement("span");
    label.textContent = query;
    label.title = query;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ghost-button";
    btn.textContent = "削除";
    btn.addEventListener("click", () => deleteSearchQuery(query));
    row.appendChild(label);
    row.appendChild(btn);
    refs.sSearchQueries.appendChild(row);
  }
}

function renderNewsStats(stats) {
  renderStatsGroup(refs.sNewsSourceStats, stats?.source ?? [], "source の学習データはまだありません");
  renderStatsGroup(refs.sNewsCategoryStats, stats?.category ?? [], "category の学習データはまだありません");
}

function renderStatsGroup(container, items, emptyText) {
  if (!container) return;
  container.innerHTML = "";
  if (!items.length) {
    container.textContent = emptyText;
    return;
  }
  items.slice(0, 8).forEach((item) => {
    const row = document.createElement("div");
    row.className = "settings-stat-row";
    row.innerHTML = `
      <strong>${escapeHtml(item.name || "不明")}</strong>
      <div class="settings-stat-meta">
        <span>score ${formatStatNumber(item.score, 3)}</span>
        <span>bonus ${formatSignedNumber(item.bonus, 3)}</span>
        <span>samples ${formatStatNumber(item.samples, 1)}</span>
        <span>+ ${formatStatNumber(item.positive, 1)}</span>
        <span>- ${formatStatNumber(item.negative, 1)}</span>
        <span>report ${formatStatNumber(item.report_requested, 1)}</span>
      </div>
    `;
    container.appendChild(row);
  });
}

function formatStatNumber(value, digits = 1) {
  const num = Number(value ?? 0);
  return Number.isFinite(num) ? num.toFixed(digits) : "0.0";
}

function formatSignedNumber(value, digits = 1) {
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return "0.0";
  return `${num >= 0 ? "+" : ""}${num.toFixed(digits)}`;
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

async function saveVrmSettings() {
  refs.sVrmStatus.textContent = "保存中...";
  try {
    const response = await api("/api/settings/vrm", {
      method: "PATCH",
      body: JSON.stringify({
        model_filename: refs.sVrmModel.value || "",
      }),
    });
    renderVrmOptions(response.available_models || [], response.model_filename || "");
    refs.sVrmStatus.textContent = "保存しました";
    await initVrmPane();
  } catch (e) {
    refs.sVrmStatus.textContent = e.message;
  }
}

async function saveBehaviorSettings() {
  refs.sBehaviorStatus.textContent = "保存中...";
  try {
    const dailyTime = parseTimeValue(refs.sDailyReviewTime.value || "00:20");
    const weeklyTime = parseTimeValue(refs.sWeeklyReviewTime.value || "09:00");
    await api("/api/settings/behavior", {
      method: "PATCH",
      body: JSON.stringify({
        review_enabled: !!refs.sReviewEnabled.checked,
        big_five_enabled: !!refs.sBigFiveEnabled.checked,
        daily_review_hour: dailyTime.hour,
        daily_review_minute: dailyTime.minute,
        weekly_review_weekday: parseInt(refs.sWeeklyReviewWeekday.value, 10),
        weekly_review_hour: weeklyTime.hour,
        weekly_review_minute: weeklyTime.minute,
        review_perspectives: textareaLines(refs.sReviewPerspectives.value),
        big_five_perspectives: textareaLines(refs.sBigFivePerspectives.value),
        big_five_focus_traits: textareaLines(refs.sBigFiveFocusTraits.value),
        big_five_trait_targets: collectTraitTargetSettings(),
      }),
    });
    refs.sBehaviorStatus.textContent = "保存しました";
  } catch (e) {
    refs.sBehaviorStatus.textContent = e.message;
  }
}

async function savePipelineSettings() {
  refs.sPipelineStatus.textContent = "保存中...";
  try {
    await api("/api/settings/pipeline", {
      method: "PATCH",
      body: JSON.stringify({
        info_limit: parseInt(refs.sInfoLimit.value, 10),
        info_use_ollama: !!refs.sInfoUseOllama.checked,
        analyze_batch_size: parseInt(refs.sAnalyzeBatch.value, 10),
        deep_limit: parseInt(refs.sDeepLimit.value, 10),
        future_daily_days_ahead: parseInt(refs.sFutureDailyDays.value, 10),
      }),
    });
    refs.sPipelineStatus.textContent = "保存しました";
  } catch (e) {
    refs.sPipelineStatus.textContent = e.message;
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

async function addSearchQuery() {
  const query = refs.sSearchQuery.value.trim();
  if (!query) return;
  refs.sSearchQueryStatus.textContent = "追加中...";
  try {
    const res = await api("/api/settings/search-queries", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
    refs.sSearchQuery.value = "";
    refs.sSearchQueryStatus.textContent = "追加しました";
    renderSearchQueries(res.search_queries);
  } catch (e) {
    refs.sSearchQueryStatus.textContent = e.message;
  }
}

async function deleteSearchQuery(query) {
  refs.sSearchQueryStatus.textContent = "削除中...";
  try {
    const res = await api("/api/settings/search-queries", {
      method: "DELETE",
      body: JSON.stringify({ query }),
    });
    refs.sSearchQueryStatus.textContent = "削除しました";
    renderSearchQueries(res.search_queries);
  } catch (e) {
    refs.sSearchQueryStatus.textContent = e.message;
  }
}

async function loadWeeklyReview() {
  refs.reviewStatus.textContent = "読込中...";
  refs.reviewOverview.textContent = "";
  refs.reviewPerspectives.innerHTML = "";
  refs.reviewBigFive.innerHTML = "";
  refs.reviewEntries.innerHTML = "";
  try {
    const anchorDate = refs.reviewAnchorDate.value || new Date().toISOString().slice(0, 10);
    const res = await api(`/api/reviews/weekly?anchor_date=${encodeURIComponent(anchorDate)}`);
    state.weeklyReview = res;
    renderWeeklyReview();
    refs.reviewStatus.textContent = `${res.week_start} - ${res.week_end}`;
  } catch (e) {
    refs.reviewStatus.textContent = e.message;
  }
}

function renderWeeklyReview() {
  const review = state.weeklyReview;
  if (!review) return;
  refs.reviewOverview.textContent = review.overview || "";

  refs.reviewPerspectives.innerHTML = "";
  for (const item of review.perspective_notes || []) {
    refs.reviewPerspectives.appendChild(buildReviewCard(item.title, item.body));
  }

  refs.reviewBigFive.innerHTML = "";
  if (!review.big_five_enabled) {
    refs.reviewBigFive.appendChild(
      buildReviewCard("Big Five はオフです", "興味があるときだけ設定で有効にし、通常レビューとは分けて確認できます。"),
    );
  } else {
    for (const item of review.big_five?.trait_notes || []) {
      const focus = (review.big_five?.focus_traits || []).includes(item.trait) ? "重点" : "参考";
      const directionLabel = traitDirectionLabel(item.target_direction);
      refs.reviewBigFive.appendChild(
        buildReviewCard(`${item.label} (${focus})`, `${item.body}\n\n改善行動: ${item.improvement_hint}`),
      );
      refs.reviewBigFive.lastElementChild.querySelector("h4").textContent = `${item.label} (${focus} / ${directionLabel})`;
    }
  }

  refs.reviewEntries.innerHTML = "";
  for (const entry of review.entries || []) {
    refs.reviewEntries.appendChild(
      buildReviewCard(
        `${formatDateTime(entry.timestamp)} | ${entry.type}`,
        `${entry.title}\n${entry.summary || ""}`,
      ),
    );
  }
}

function buildReviewCard(title, body) {
  const card = document.createElement("article");
  card.className = "review-card";
  const heading = document.createElement("h4");
  heading.textContent = title;
  const copy = document.createElement("p");
  copy.textContent = body;
  card.appendChild(heading);
  card.appendChild(copy);
  return card;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function textareaLines(value) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function buildTimeValue(hour, minute) {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function parseTimeValue(value) {
  const [hour, minute] = (value || "00:00").split(":").map((part) => parseInt(part, 10) || 0);
  return { hour, minute };
}

function applyTraitTargetSettings(targets) {
  refs.sTraitTargetOpenness.value = targets.openness || "up";
  refs.sTraitTargetConscientiousness.value = targets.conscientiousness || "up";
  refs.sTraitTargetExtraversion.value = targets.extraversion || "up";
  refs.sTraitTargetAgreeableness.value = targets.agreeableness || "up";
  refs.sTraitTargetNeuroticism.value = targets.neuroticism || "down";
}

function collectTraitTargetSettings() {
  return {
    openness: refs.sTraitTargetOpenness.value,
    conscientiousness: refs.sTraitTargetConscientiousness.value,
    extraversion: refs.sTraitTargetExtraversion.value,
    agreeableness: refs.sTraitTargetAgreeableness.value,
    neuroticism: refs.sTraitTargetNeuroticism.value,
  };
}

function traitDirectionLabel(direction) {
  if (direction === "up") return "上げたい";
  if (direction === "down") return "下げたい";
  return "維持したい";
}

function toDatetimeLocal(isoString) {
  const d = new Date(isoString);
  const pad = (n) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}
