// Xiaopu Agent Modern Desktop Web GUI Client
(function () {
  "use strict";

  // ------------------------------------------------------------------ DOM Elements
  const chatArea = document.getElementById("chat-area");
  const chatContainer = document.getElementById("chat-container");
  const welcomeHero = document.getElementById("welcome-hero");
  const promptInput = document.getElementById("prompt-input");
  const btnSend = document.getElementById("btn-send");
  const btnStop = document.getElementById("btn-stop");
  const modelSelect = document.getElementById("model-select");
  const reasoningEffortSelect = document.getElementById("reasoning-effort-select");
  const permSelect = document.getElementById("perm-select");
  const currentTitle = document.getElementById("current-title");

  // Sidebar Tree
  const projectsTreeList = document.getElementById("projects-tree-list");
  const conversationsTreeList = document.getElementById("conversations-tree-list");
  const addProjectBtn = document.getElementById("add-project-btn");
  const sortProjectsBtn = document.getElementById("sort-projects-btn");
  const newConversationBtn = document.getElementById("new-conversation-btn");
  const themeToggleBtn = document.getElementById("theme-toggle-btn");
  const btnOpenSettings = document.getElementById("btn-open-settings");

  // Activity Drawer & Tabs
  const activityDrawer = document.getElementById("activity-drawer");
  const btnToggleActivity = document.getElementById("btn-toggle-activity");
  const drawerCloseBtn = document.getElementById("drawer-close-btn");
  const tabPptBtn = document.getElementById("tab-ppt-btn");
  const tabTimelineBtn = document.getElementById("tab-timeline-btn");
  const tabCotBtn = document.getElementById("tab-cot-btn");
  const tabPptPanel = document.getElementById("tab-ppt-panel");
  const tabTimelinePanel = document.getElementById("tab-timeline-panel");
  const tabCotPanel = document.getElementById("tab-cot-panel");
  const timelineLog = document.getElementById("timeline-log");
  const cotLog = document.getElementById("cot-log");
  const copyTimelineBtn = document.getElementById("copy-timeline-btn");
  const copyCotBtn = document.getElementById("copy-cot-btn");
  const liveAction = document.getElementById("live-action");
  const livePhase = document.getElementById("live-phase");
  const liveElapsed = document.getElementById("live-elapsed");
  const liveCounts = document.getElementById("live-counts");

  // PPT Preview & TXT Editor Elements
  const pptDeckName = document.getElementById("ppt-deck-name");
  const pptSlideCounter = document.getElementById("ppt-slide-counter");
  const btnRefreshPpt = document.getElementById("btn-refresh-ppt");
  const btnSaveasPpt = document.getElementById("btn-saveas-ppt");
  const pptSlideNavBar = document.getElementById("ppt-slide-nav-bar");
  const pptPreviewImg = document.getElementById("ppt-preview-img");
  const pptPreviewPlaceholder = document.getElementById("ppt-preview-placeholder");
  const btnCopyPptText = document.getElementById("btn-copy-ppt-text");
  const pptContentTxt = document.getElementById("ppt-content-txt");
  const btnApplyPptText = document.getElementById("btn-apply-ppt-text");

  let currentPptData = null;
  let currentDeckPath = "";
  let currentSlideIndex = 1;

  // Topbar Actions
  const btnArtifactsHub = document.getElementById("btn-artifacts-hub");
  const artifactsCountBadge = document.getElementById("artifacts-count-badge");
  const btnExport = document.getElementById("btn-export");

  // Artifacts Modal
  const artifactsModal = document.getElementById("artifacts-modal");
  const artifactsModalClose = document.getElementById("artifacts-modal-close");
  const artifactsModalDone = document.getElementById("artifacts-modal-done");
  const btnRefreshArtifacts = document.getElementById("btn-refresh-artifacts");
  const artifactsWsInfo = document.getElementById("artifacts-ws-info");
  const artifactsListContainer = document.getElementById("artifacts-list-container");

  // Settings Modal
  const settingsModal = document.getElementById("settings-modal");
  const settingsModalClose = document.getElementById("settings-modal-close");
  const settingsCancelBtn = document.getElementById("settings-cancel-btn");
  const settingsSaveBtn = document.getElementById("settings-save-btn");
  const setProvider = document.getElementById("set-provider");
  const setApiBase = document.getElementById("set-api-base");
  const setApiKey = document.getElementById("set-api-key");
  const setModel = document.getElementById("set-model");
  const setModelsCsv = document.getElementById("set-models-csv");
  const setReasoningEffort = document.getElementById("set-reasoning-effort");
  const setCommandPolicy = document.getElementById("set-command-policy");
  const setTogglePwdBtn = document.getElementById("set-toggle-pwd-btn");

  // Goal Modal
  const btnGoalDialog = document.getElementById("btn-goal-dialog");
  const goalModal = document.getElementById("goal-modal");
  const goalModalClose = document.getElementById("goal-modal-close");
  const goalInput = document.getElementById("goal-input");
  const goalCancelBtn = document.getElementById("goal-cancel-btn");
  const goalSaveBtn = document.getElementById("goal-save-btn");

  const toast = document.getElementById("toast");

  // Sidebar Management v2
  const sidebarSearch = document.getElementById("sidebar-search");
  const sidebarViewTabs = document.querySelectorAll(".sidebar-view-tab[data-view]");
  const btnManageWorkspaces = document.getElementById("btn-manage-workspaces");
  const sidebarBatchBar = document.getElementById("sidebar-batch-bar");
  const batchCount = document.getElementById("batch-count");
  const btnBatchArchive = document.getElementById("btn-batch-archive");
  const btnBatchTrash = document.getElementById("btn-batch-trash");
  const btnBatchRestore = document.getElementById("btn-batch-restore");
  const btnBatchPurge = document.getElementById("btn-batch-purge");
  const btnBatchCancel = document.getElementById("btn-batch-cancel");
  const contextMenu = document.getElementById("context-menu");
  const workspacesModal = document.getElementById("workspaces-modal");
  const workspacesModalClose = document.getElementById("workspaces-modal-close");
  const workspacesModalDone = document.getElementById("workspaces-modal-done");
  const workspacesManageBody = document.getElementById("workspaces-manage-body");
  const confirmModal = document.getElementById("confirm-modal");
  const confirmModalClose = document.getElementById("confirm-modal-close");
  const confirmTitle = document.getElementById("confirm-title");
  const confirmText = document.getElementById("confirm-text");
  const confirmInput = document.getElementById("confirm-input");
  const confirmOkBtn = document.getElementById("confirm-ok-btn");
  const confirmCancelBtn = document.getElementById("confirm-cancel-btn");
  const composerWorkspaceSelect = document.getElementById("composer-workspace-select");
  const composerWorkspacePath = document.getElementById("composer-workspace-path");

  // ------------------------------------------------------------------ Application State
  let activeSessionId = null;
  let activeWorkspacePath = null;
  let isRunning = false;
  let abortController = null;
  let startTime = null;
  let timerInterval = null;
  let toolStarted = 0;
  let toolCompleted = 0;
  let toolFailed = 0;
  let rawReasoning = "";
  let currentThoughtCard = null;
  let currentAssistantCard = null;
  let sortReverse = false;
  const collapsedFolders = new Set();
  let cachedArtifacts = [];
  let sidebarView = "active";
  let sidebarQuery = "";
  const selectedSessionIds = new Set();
  let confirmCallback = null;

  // ------------------------------------------------------------------ Icons SVG constants
  const ICONS = {
    chevron: `<svg viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>`,
    folder: `<svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`,
    plus: `<svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
    close: `<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
    sparkle: `<svg viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
    tool: `<svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
    copy: `<svg viewBox="0 0 24 24"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`,
    check: `<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>`,
    file: `<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`,
    ppt: `<svg viewBox="0 0 24 24"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 15h4M7 9h6a2 2 0 0 1 0 4H7z"/></svg>`,
    save: `<svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>`,
    verify: `<svg viewBox="0 0 24 24"><path d="m9 11 3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`,
    undo: `<svg viewBox="0 0 24 24"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>`,
    reveal: `<svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><circle cx="12" cy="14" r="2"/></svg>`,
    more: `<svg viewBox="0 0 24 24"><circle cx="12" cy="5" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="12" cy="19" r="1.6"/></svg>`,
  };

  // ------------------------------------------------------------------ Init & Config
  async function init() {
    initTheme();
    bindEvents();
    autoResizeTextarea();
    await loadConfig();
    await refreshTree();
    await fetchArtifacts();
  }

  function initTheme() {
    const savedTheme = localStorage.getItem("xiaopu_theme") || "light";
    document.documentElement.setAttribute("data-theme", savedTheme);
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = (current === "dark") ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("xiaopu_theme", next);
    showToast(next === "dark" ? "已切换至黑曜石深色主题" : "已切换至温暖纸质浅色主题");
  }

  async function loadConfig() {
    try {
      const res = await fetch("/api/config");
      const data = await res.json();
      if (!data) return;

      // Populate models
      modelSelect.innerHTML = "";
      (data.known_models || []).forEach(m => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.innerText = m;
        if (m === data.current_model) opt.selected = true;
        modelSelect.appendChild(opt);
      });

      if (data.command_policy && permSelect) {
        permSelect.value = data.command_policy;
      }

      if (data.reasoning_effort && reasoningEffortSelect) {
        reasoningEffortSelect.value = data.reasoning_effort;
      }
    } catch (e) {
      console.error("Failed to load config:", e);
    }
  }

  // ------------------------------------------------------------------ Settings Management
  async function loadSettingsForm() {
    try {
      const res = await fetch("/api/settings");
      const data = await res.json();
      if (!data) return;

      if (setProvider) setProvider.value = data.provider || "openai";
      if (setApiBase) setApiBase.value = data.api_base || "";
      if (setApiKey) setApiKey.value = data.api_key || "";
      if (setModel) setModel.value = data.model || "";
      if (setModelsCsv) setModelsCsv.value = data.models_csv || "";
      if (setReasoningEffort) setReasoningEffort.value = data.reasoning_effort || "high";
      if (setCommandPolicy) setCommandPolicy.value = data.command_policy || "ask";
    } catch (e) {
      console.error("Failed to load settings:", e);
    }
  }

  async function saveSettingsForm() {
    try {
      const payload = {
        provider: setProvider.value,
        api_base: setApiBase.value.trim(),
        api_key: setApiKey.value.trim(),
        model: setModel.value.trim(),
        models_csv: setModelsCsv.value.trim(),
        reasoning_effort: setReasoningEffort.value,
        command_policy: setCommandPolicy.value,
      };

      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === "ok") {
        if (settingsModal) settingsModal.style.display = "none";
        await loadConfig();
        showToast("模型与 API 设置已保存并即时生效！");
      }
    } catch (e) {
      console.error("Failed to save settings:", e);
      showToast("保存设置失败，请检查网络或参数");
    }
  }

  // ------------------------------------------------------------------ Artifacts Hub Management
  async function fetchArtifacts() {
    try {
      const res = await fetch("/api/artifacts");
      const data = await res.json();
      if (!data) return;

      cachedArtifacts = data.artifacts || [];
      const count = cachedArtifacts.length;
      if (artifactsCountBadge) {
        artifactsCountBadge.innerText = String(count);
      }
      if (artifactsWsInfo) {
        artifactsWsInfo.innerText = `当前工作区：${data.workspace || activeWorkspacePath || "-"}`;
      }
      renderArtifactsList(cachedArtifacts);
      loadPptPreview(currentSlideIndex, false, null, activeSessionId);
    } catch (e) {
      console.error("Fetch artifacts error:", e);
    }
  }

  function renderArtifactsList(artifacts) {
    if (!artifactsListContainer) return;
    if (artifacts.length === 0) {
      artifactsListContainer.innerHTML = `
        <div class="empty-tree-placeholder" style="padding: 24px; text-align: center;">
          当前工作区暂无生成的产物文件（.pptx / .py / .md 等）
        </div>
      `;
      return;
    }

    artifactsListContainer.innerHTML = artifacts.map(art => {
      const icon = art.is_pptx ? ICONS.ppt : ICONS.file;
      const tagText = art.is_pptx ? `PPT 演示文稿${art.slides_count ? ` · ${art.slides_count}页` : ""}` : `${art.type.toUpperCase()} 文件`;
      
      let actionsHtml = "";
      if (art.is_pptx) {
        actionsHtml = `
          <button class="pill-btn art-save-btn" data-path="${escapeAttr(art.path)}">
            <span class="icon">${ICONS.save}</span><span>另存为</span>
          </button>
          <button class="pill-btn art-verify-btn" data-path="${escapeAttr(art.path)}">
            <span class="icon">${ICONS.verify}</span><span>校验结构</span>
          </button>
          <button class="pill-btn art-undo-btn">
            <span class="icon">${ICONS.undo}</span><span>撤销</span>
          </button>
          <button class="pill-btn art-reveal-btn" data-path="${escapeAttr(art.path)}">
            <span class="icon">${ICONS.reveal}</span><span>定位文件</span>
          </button>
        `;
      } else {
        actionsHtml = `
          <button class="pill-btn art-copy-path-btn" data-path="${escapeAttr(art.path)}">
            <span class="icon">${ICONS.copy}</span><span>复制路径</span>
          </button>
          <button class="pill-btn art-reveal-btn" data-path="${escapeAttr(art.path)}">
            <span class="icon">${ICONS.reveal}</span><span>定位文件</span>
          </button>
        `;
      }

      return `
        <div class="artifact-item-card" data-path="${escapeAttr(art.path)}">
          <div class="artifact-item-header">
            <div class="artifact-file-info">
              <span class="artifact-icon">${icon}</span>
              <span class="artifact-name" title="${escapeAttr(art.path)}">${escapeHtml(art.name)}</span>
              <span class="artifact-tag">${escapeHtml(tagText)}</span>
            </div>
            <span class="meta-time-text">${escapeHtml(art.time_ago || "now")}</span>
          </div>
          <div class="artifact-meta-line">
            <span>大小: ${escapeHtml(art.size_human)}</span>
            <span>路径: ${escapeHtml(art.path)}</span>
          </div>
          <div class="artifact-actions-bar">
            ${actionsHtml}
          </div>
        </div>
      `;
    }).join("");

    bindArtifactActions();
  }

  function bindArtifactActions() {
    document.querySelectorAll(".art-reveal-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const p = btn.getAttribute("data-path");
        if (p) await revealFile(p);
      });
    });

    document.querySelectorAll(".art-copy-path-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const p = btn.getAttribute("data-path");
        if (p) {
          navigator.clipboard.writeText(p);
          showToast("文件绝对路径已复制");
        }
      });
    });

    document.querySelectorAll(".art-save-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        await handleSavePpt();
      });
    });

    document.querySelectorAll(".art-verify-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        await handleVerifyPpt();
      });
    });

    document.querySelectorAll(".art-undo-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        await handleUndoPpt();
      });
    });

    document.querySelectorAll(".artifact-item-card").forEach(card => {
      card.addEventListener("click", async () => {
        const p = card.getAttribute("data-path");
        if (p && (p.toLowerCase().endsWith(".pptx") || p.toLowerCase().endsWith(".ppt"))) {
          if (tabPptBtn) tabPptBtn.click();
          if (artifactsModal) artifactsModal.style.display = "none";
          await loadPptPreview(1, true, p);
          showToast(`已切换 PPT 预览：${p.split(/[\\/]/).pop()}`);
        }
      });
    });
  }

  async function revealFile(filePath) {
    try {
      const res = await fetch("/api/reveal_file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: filePath })
      });
      const data = await res.json();
      if (data.status === "ok") {
        showToast("已在 Windows 资源管理器中打开并选中该文件");
      }
    } catch (e) {
      console.error("Reveal file failed:", e);
    }
  }

  async function handleVerifyPpt() {
    showToast("正在执行 PPT 结构与排版校验…");
    const res = await fetch("/api/ppt/verify", { method: "POST" });
    const data = await res.json();
    appendAssistantContainer().innerHTML = formatMarkdown(`### 🔍 PPT 校验结果\n\n${data.result}`);
    if (artifactsModal) artifactsModal.style.display = "none";
  }

  async function handleSavePpt() {
    let savePath = "";
    try {
      showToast("正在打开系统另存为窗口…");
      const dlgRes = await fetch("/api/choose_save_ppt", { method: "POST" });
      const dlgData = await dlgRes.json();
      if (dlgData.status === "ok" && dlgData.path) {
        savePath = dlgData.path;
      } else if (dlgData.status === "cancelled") {
        return;
      }
    } catch (e) {
      console.error("Choose save dialog error:", e);
    }

    if (!savePath) {
      savePath = "presentation.pptx";
    }

    const res = await fetch("/api/ppt/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: savePath })
    });
    const data = await res.json();
    appendAssistantContainer().innerHTML = formatMarkdown(`### 💾 保存 PPT\n\n${data.result}`);
    await fetchArtifacts();
    if (artifactsModal) artifactsModal.style.display = "none";
  }

  async function handleUndoPpt() {
    const res = await fetch("/api/ppt/undo", { method: "POST" });
    const data = await res.json();
    appendAssistantContainer().innerHTML = formatMarkdown(`### ↩ 撤销结果\n\n${data.result}`);
    await fetchArtifacts();
    if (artifactsModal) artifactsModal.style.display = "none";
    await loadPptPreview(currentSlideIndex, true);
  }

  // ------------------------------------------------------------------ PPT Preview & Content Sync
  async function loadPptPreview(slideNum = 1, forceTextUpdate = false, specificFile = null, sessionId = null) {
    try {
      const targetSessionId = sessionId !== null && sessionId !== undefined ? sessionId : activeSessionId;
      const params = new URLSearchParams();
      if (activeWorkspacePath) params.set("workspace", activeWorkspacePath);
      if (targetSessionId) params.set("session_id", targetSessionId);
      if (specificFile) params.set("file", specificFile);
      const queryString = params.toString() ? `?${params.toString()}` : "";

      const res = await fetch(`/api/ppt/content${queryString}`);
      if (!res.ok) return;
      const data = await res.json();
      currentPptData = data;

      if (!data.success || data.total_slides <= 0) {
        if (pptDeckName) pptDeckName.textContent = "未检测到 PPT";
        if (pptSlideCounter) pptSlideCounter.textContent = "-";
        if (pptSlideNavBar) pptSlideNavBar.innerHTML = "";
        if (pptPreviewImg) pptPreviewImg.style.display = "none";
        if (pptPreviewPlaceholder) pptPreviewPlaceholder.style.display = "flex";
        if (forceTextUpdate && pptContentTxt) pptContentTxt.value = "";
        currentDeckPath = "";
        return;
      }

      const total = data.total_slides;
      currentSlideIndex = Math.max(1, Math.min(slideNum, total));

      if (pptDeckName) pptDeckName.textContent = data.deck_name || "deck.pptx";
      if (pptSlideCounter) pptSlideCounter.textContent = `${total} 页`;

      // Render Page Buttons
      if (pptSlideNavBar) {
        pptSlideNavBar.innerHTML = Array.from({ length: total }, (_, i) => i + 1)
          .map(p => `<button class="ppt-page-pill ${p === currentSlideIndex ? 'active' : ''}" data-page="${p}">第 ${p} 页</button>`)
          .join("");

        pptSlideNavBar.querySelectorAll(".ppt-page-pill").forEach(btn => {
          btn.addEventListener("click", () => {
            const page = parseInt(btn.getAttribute("data-page"), 10);
            if (page) switchPptSlide(page);
          });
        });
      }

      // Render Visual Preview Image
      if (pptPreviewImg) {
        const previewParams = new URLSearchParams();
        previewParams.set("slide", currentSlideIndex);
        if (activeWorkspacePath) previewParams.set("workspace", activeWorkspacePath);
        if (targetSessionId) previewParams.set("session_id", targetSessionId);
        if (specificFile) previewParams.set("file", specificFile);
        else if (data.deck_path) previewParams.set("file", data.deck_path);
        previewParams.set("t", Date.now());
        pptPreviewImg.src = `/api/ppt/preview?${previewParams.toString()}`;
        pptPreviewImg.style.display = "block";
        if (pptPreviewPlaceholder) pptPreviewPlaceholder.style.display = "none";
      }

      // Populate TXT Content
      if (pptContentTxt) {
        if (forceTextUpdate || !pptContentTxt.value.trim() || currentDeckPath !== (data.deck_path || "")) {
          pptContentTxt.value = data.text_content || "";
          currentDeckPath = data.deck_path || "";
        }
      }
    } catch (e) {
      console.warn("Failed to load PPT preview:", e);
    }
  }

  function switchPptSlide(slideNum) {
    if (!currentPptData || currentPptData.total_slides <= 0) return;
    currentSlideIndex = Math.max(1, Math.min(slideNum, currentPptData.total_slides));
    if (pptSlideNavBar) {
      pptSlideNavBar.querySelectorAll(".ppt-page-pill").forEach(btn => {
        const p = parseInt(btn.getAttribute("data-page"), 10);
        btn.classList.toggle("active", p === currentSlideIndex);
      });
    }
    if (pptPreviewImg) {
      const previewParams = new URLSearchParams();
      previewParams.set("slide", currentSlideIndex);
      if (activeWorkspacePath) previewParams.set("workspace", activeWorkspacePath);
      if (activeSessionId) previewParams.set("session_id", activeSessionId);
      if (currentPptData && currentPptData.deck_path) previewParams.set("file", currentPptData.deck_path);
      previewParams.set("t", Date.now());
      pptPreviewImg.src = `/api/ppt/preview?${previewParams.toString()}`;
      pptPreviewImg.style.display = "block";
      if (pptPreviewPlaceholder) pptPreviewPlaceholder.style.display = "none";
    }
  }

  async function applyPptContent() {
    const text = pptContentTxt ? pptContentTxt.value.trim() : "";
    if (!text) {
      showToast("文本内容为空，请先编写或修改幻灯片要点");
      return;
    }
    const instruction = "请保持当前演示文稿的精美排版、布局结构与视觉设计风格，按照以下修改后的文本内容更新 PPT 对应的页面标题、卡片内容与要点细节，更新后自动保存并校验：\n\n" + text;
    if (promptInput) {
      promptInput.value = instruction;
      promptInput.style.height = "auto";
      promptInput.style.height = Math.min(promptInput.scrollHeight, 180) + "px";
    }
    showToast("已组装修改指令，正在让报一更新 PPT...");
    await sendMessage();
  }

  // ------------------------------------------------------------------ Tree Management
  async function refreshWorkspaceSelector(currentPath) {
    if (!composerWorkspaceSelect || !composerWorkspacePath) return;
    let records = [];
    try {
      const res = await fetch("/api/workspaces?view=active");
      const data = await res.json();
      records = data.records || [];
    } catch (e) {
      records = [];
    }
    const current = currentPath || activeWorkspacePath || "";
    if (current && !records.some(r => r.path === current)) {
      records.unshift({ path: current, display_name: current.split(/[\\/]/).pop() || current });
    }
    composerWorkspaceSelect.innerHTML = records.map(r =>
      `<option value="${escapeAttr(r.path)}">${escapeHtml(r.display_name || r.name || r.path)}</option>`
    ).join("");
    if (current) composerWorkspaceSelect.value = current;
    composerWorkspacePath.textContent = current || "-";
    composerWorkspacePath.title = current || "";
  }

  async function refreshTree() {
    try {
      const params = new URLSearchParams({ view: sidebarView, q: sidebarQuery });
      const res = await fetch(`/api/tree?${params.toString()}`);
      const data = await res.json();
      if (!data) return;

      activeWorkspacePath = data.current_workspace;
      refreshWorkspaceSelector(activeWorkspacePath);
      const projects = data.projects || [];
      const conversations = data.conversations || [];

      if (sortReverse) projects.reverse();

      // 1. Render Projects (workspace folders with nested sessions)
      if (projects.length === 0) {
        projectsTreeList.innerHTML = `<div class="empty-tree-placeholder">暂无工作区项目</div>`;
      } else {
        projectsTreeList.innerHTML = projects.map(p => {
          const isCollapsed = collapsedFolders.has(p.path);
          const isCurrentWs = (p.is_current || (activeWorkspacePath && p.path && p.path.toLowerCase() === activeWorkspacePath.toLowerCase()));
          const count = (p.sessions && p.sessions.length) || 0;
          const sessionsHtml = count > 0
            ? renderGroupedSessions(p.sessions)
            : `<div class="empty-tree-placeholder">(暂无会话)</div>`;
          const pinnedIcon = p.pinned ? `<span class="tree-pin-icon">📌</span>` : "";

          return `
            <div class="project-node ${isCollapsed ? "collapsed" : ""} ${isCurrentWs ? "active-ws" : ""}" data-path="${escapeAttr(p.path)}">
              <div class="project-folder-header">
                <div class="project-folder-info" title="${escapeAttr(p.path)}">
                  <span class="icon project-chevron-icon">${ICONS.chevron}</span>
                  <span class="icon project-folder-icon">${ICONS.folder}</span>
                  <span class="project-folder-name">${escapeHtml(p.name)}${pinnedIcon}</span>
                </div>
                <div class="project-header-actions">
                  <span class="project-count-badge">${count}</span>
                  <button class="project-menu-btn" data-path="${escapeAttr(p.path)}" title="工作区管理">
                    <span class="icon">${ICONS.more}</span>
                  </button>
                  <button class="project-add-chat-btn" data-path="${escapeAttr(p.path)}" title="在此项目下新建对话">
                    <span class="icon">${ICONS.plus}</span>
                  </button>
                </div>
              </div>
              <div class="project-sessions-list">
                ${sessionsHtml}
              </div>
            </div>
          `;
        }).join("");
      }

      // 2. Render Independent Conversations
      if (conversations.length === 0) {
        conversationsTreeList.innerHTML = `<div class="empty-tree-placeholder">暂无独立对话</div>`;
      } else {
        conversationsTreeList.innerHTML = renderGroupedSessions(conversations);
      }

      updateBatchBar();
      bindTreeEvents();
    } catch (e) {
      console.error("Refresh tree error:", e);
    }
  }

  function groupKeyFor(updatedAt) {
    if (!updatedAt) return "更早";
    const dt = new Date(updatedAt);
    if (Number.isNaN(dt.getTime())) return "更早";
    const now = new Date();
    const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const startYesterday = startToday - 86400000;
    const startWeek = startToday - 6 * 86400000;
    if (dt.getTime() >= startToday) return "今天";
    if (dt.getTime() >= startYesterday) return "昨天";
    if (dt.getTime() >= startWeek) return "近 7 天";
    return "更早";
  }

  function renderGroupedSessions(sessions) {
    const pinned = sessions.filter(s => s.pinned);
    const rest = sessions.filter(s => !s.pinned);
    const groups = [];
    if (pinned.length) groups.push(["📌 置顶", pinned]);
    const order = sidebarView === "active" ? ["今天", "昨天", "近 7 天", "更早"] : ["会话"];
    if (sidebarView === "active") {
      for (const key of order) {
        const items = rest.filter(s => groupKeyFor(s.updated_at) === key);
        if (items.length) groups.push([key, items]);
      }
    } else if (rest.length) {
      groups.push([sidebarView === "archive" ? "已归档" : "回收站", rest]);
    }
    return groups.map(([label, items]) => {
      const rows = items.map(renderSessionRow).join("");
      return `<div class="tree-group-header">${escapeHtml(label)}</div>${rows}`;
    }).join("");
  }

  function renderSessionRow(s) {
    const isActive = (s.id === activeSessionId);
    const selected = selectedSessionIds.has(s.id);
    const timeDisplay = isActive ? "now" : (s.time_ago || "now");
    const pinnedIcon = s.pinned ? `<span class="tree-pin-icon">📌</span>` : "";
    const statusBadge = s.status && s.status !== "active"
      ? `<span class="meta-status-badge">${escapeHtml(s.status === "archive" ? "归档" : "回收站")}</span>` : "";

    return `
      <div class="tree-session-item ${isActive ? "active" : ""} ${s.pinned ? "pinned" : ""} ${selected ? "selected" : ""}" data-id="${escapeAttr(s.id)}" data-ws="${escapeAttr(s.workspace || "")}" data-title="${escapeAttr(s.title || "")}" data-status="${escapeAttr(s.status || "active")}">
        <input type="checkbox" class="tree-session-check" data-id="${escapeAttr(s.id)}" title="批量选择" ${selected ? "checked" : ""}>
        <span class="tree-session-title" title="${escapeAttr(s.title || "未命名对话")}">${escapeHtml(s.title || "未命名对话")}${pinnedIcon}</span>
        <div class="tree-session-meta">
          ${statusBadge}
          <span class="meta-time-text">${escapeHtml(timeDisplay)}</span>
          <button class="session-menu-btn" data-id="${escapeAttr(s.id)}" title="会话管理">
            <span class="icon">${ICONS.more}</span>
          </button>
        </div>
      </div>
    `;
  }

  function bindTreeEvents() {
    document.querySelectorAll(".project-folder-header").forEach(hdr => {
      hdr.addEventListener("click", async (e) => {
        if (e.target.closest(".project-add-chat-btn") || e.target.closest(".project-menu-btn")) return;
        const projectNode = hdr.closest(".project-node");
        if (!projectNode) return;
        const ws = projectNode.getAttribute("data-path");

        if (e.target.closest(".project-chevron-icon")) {
          if (collapsedFolders.has(ws)) {
            collapsedFolders.delete(ws);
            projectNode.classList.remove("collapsed");
          } else {
            collapsedFolders.add(ws);
            projectNode.classList.add("collapsed");
          }
          return;
        }

        if (ws && ws !== activeWorkspacePath) {
          await switchWorkspace(ws);
          showToast(`已切换工作区：${ws}`);
          refreshTree();
          fetchArtifacts();
        }
      });
    });

    document.querySelectorAll(".tree-session-item").forEach(el => {
      el.addEventListener("click", (e) => {
        if (e.target.closest(".tree-session-check") || e.target.closest(".session-menu-btn")) return;
        const id = el.getAttribute("data-id");
        const ws = el.getAttribute("data-ws");
        loadSession(id, ws);
      });
    });

    document.querySelectorAll(".tree-session-check").forEach(box => {
      box.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = box.getAttribute("data-id");
        if (box.checked) selectedSessionIds.add(id);
        else selectedSessionIds.delete(id);
        const row = box.closest(".tree-session-item");
        if (row) row.classList.toggle("selected", box.checked);
        updateBatchBar();
      });
    });

    document.querySelectorAll(".session-menu-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        openSessionMenu(btn.getAttribute("data-id"), e.clientX, e.clientY);
      });
    });

    document.querySelectorAll(".project-menu-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        openWorkspaceMenu(btn.getAttribute("data-path"), e.clientX, e.clientY);
      });
    });

    document.querySelectorAll(".project-add-chat-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const ws = btn.getAttribute("data-path");
        await switchWorkspace(ws);
        newSessionInProject(ws);
        fetchArtifacts();
      });
    });
  }

  // ------------------------------------------------------------------ Sidebar Management v2
  function closeContextMenu() {
    if (contextMenu) contextMenu.style.display = "none";
  }

  function openContextMenu(x, y, items) {
    closeContextMenu();
    contextMenu.innerHTML = items.map((item, index) => {
      if (item.separator) return `<div class="context-menu-separator"></div>`;
      return `<button class="context-menu-item ${item.danger ? "danger" : ""}" data-cm-index="${index}">${escapeHtml(item.label)}</button>`;
    }).join("");
    contextMenu.style.display = "block";
    const rect = contextMenu.getBoundingClientRect();
    contextMenu.style.left = `${Math.min(x, window.innerWidth - rect.width - 12)}px`;
    contextMenu.style.top = `${Math.min(y, window.innerHeight - rect.height - 12)}px`;
    contextMenu.querySelectorAll(".context-menu-item").forEach(btn => {
      btn.addEventListener("click", () => {
        closeContextMenu();
        const item = items[Number(btn.getAttribute("data-cm-index"))];
        if (item && item.action) item.action();
      });
    });
  }

  function openSessionMenu(id, x, y) {
    const row = document.querySelector(`.tree-session-item[data-id="${CSS.escape(id)}"]`);
    const status = row ? row.getAttribute("data-status") : "active";
    const title = row ? row.getAttribute("data-title") : "";
    const items = [];
    if (status === "active" || status === "archive") {
      items.push({ label: "✏ 重命名", action: () => startInlineRename(row) });
    }
    items.push({
      label: status === "active" ? "📌 置顶" : "📌 取消置顶",
      action: async () => {
        const current = row && row.classList.contains("pinned");
        await sessionAction(id, "pin", { pinned: !current });
      }
    });
    if (status === "active") {
      items.push({ label: "🗂 归档", action: () => confirmThenSession(id, "archive") });
    }
    if (status !== "active") {
      items.push({ label: "↩ 恢复到全部", action: () => sessionAction(id, "restore") });
    }
    items.push({ label: "⬇ 导出 MD", action: () => sessionAction(id, "export") });
    if (status === "active" || status === "archive") {
      items.push({ separator: true });
      items.push({ label: "🗑 移入回收站", danger: true, action: () => confirmThenSession(id, "trash") });
    }
    if (status === "trash") {
      items.push({ separator: true });
      items.push({ label: "⛔ 彻底删除", danger: true, action: () => confirmThenSession(id, "purge") });
    }
    openContextMenu(x, y, items);
  }

  function openWorkspaceMenu(path, x, y) {
    const row = [...document.querySelectorAll(".project-node")].find(n => n.getAttribute("data-path") === path);
    const isCurrent = row && row.classList.contains("active-ws");
    const items = [];
    if (!isCurrent) {
      items.push({ label: "◎ 设为当前工作区", action: async () => { await switchWorkspace(path); refreshTree(); } });
    }
    items.push({ label: "✏ 重命名显示名", action: () => startWorkspaceRename(path, row) });
    items.push({ label: row && row.classList.contains("pinned") ? "📌 取消置顶" : "📌 置顶", action: async () => {
      const current = row && row.classList.contains("pinned");
      await workspaceAction(path, "pin", { pinned: !current });
    }});
    items.push({ label: "🗂 归档工作区", action: () => confirmThenWorkspace(path, "archive") });
    items.push({ label: "🚫 从侧栏移除", danger: true, action: () => confirmThenWorkspace(path, "remove") });
    items.push({ separator: true });
    items.push({ label: "＋ 新建对话", action: async () => { await switchWorkspace(path); newSessionInProject(path); } });
    openContextMenu(x, y, items);
  }

  function startInlineRename(row) {
    if (!row) return;
    const titleEl = row.querySelector(".tree-session-title");
    const id = row.getAttribute("data-id");
    if (!titleEl || !id) return;
    const input = document.createElement("input");
    input.type = "text";
    input.className = "inline-rename-input";
    input.value = titleEl.getAttribute("title") || titleEl.innerText.replace("📌", "").trim();
    titleEl.innerHTML = "";
    titleEl.appendChild(input);
    input.focus();
    input.select();
    let done = false;
    const finish = async (save) => {
      if (done) return;
      done = true;
      if (save && input.value.trim()) {
        await sessionAction(id, "rename", { title: input.value.trim() });
      } else {
        refreshTree();
      }
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); finish(true); }
      else if (e.key === "Escape") { e.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", () => finish(true));
  }

  function startWorkspaceRename(path, row) {
    const nameEl = row ? row.querySelector(".project-folder-name") : null;
    if (!nameEl || !path) return;
    const input = document.createElement("input");
    input.type = "text";
    input.className = "inline-rename-input";
    input.value = nameEl.innerText.replace("📌", "").trim();
    nameEl.innerHTML = "";
    nameEl.appendChild(input);
    input.focus();
    input.select();
    let done = false;
    const finish = async (save) => {
      if (done) return;
      done = true;
      if (save && input.value.trim()) {
        await workspaceAction(path, "rename", { display_name: input.value.trim() });
      } else {
        refreshTree();
      }
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); finish(true); }
      else if (e.key === "Escape") { e.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", () => finish(true));
  }

  async function sessionAction(id, action, extra = {}) {
    try {
      const res = await fetch("/api/session/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, action, ...extra })
      });
      const data = await res.json();
      if (data.status === "ok") {
        if (action === "export") {
          showToast(`已导出：${data.path || "OK"}`);
        } else {
          showToast(actionLabel(action, "session", true));
        }
        if (activeSessionId === id && (action === "trash" || action === "archive" || action === "purge")) {
          activeSessionId = null;
          newSessionInProject(activeWorkspacePath);
        }
        selectedSessionIds.delete(id);
        await refreshTree();
      } else {
        showToast(actionLabel(action, "session", false));
      }
    } catch (e) {
      showToast(`操作失败: ${e.message}`);
    }
  }

  async function workspaceAction(path, action, extra = {}) {
    try {
      const res = await fetch("/api/workspace/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, action, ...extra })
      });
      const data = await res.json();
      if (data.status === "ok") {
        showToast(actionLabel(action, "workspace", true));
        let currentWasHidden = false;
        if ((action === "archive" || action === "remove" || action === "purge")
            && activeWorkspacePath && path.toLowerCase() === activeWorkspacePath.toLowerCase()) {
          activeWorkspacePath = null;
          currentWasHidden = true;
        }
        await refreshTree();
        if (currentWasHidden) {
          // Move the UI onto another visible workspace instead of leaving it
          // silently bound to a hidden one.
          const first = document.querySelector(".project-node[data-path]");
          if (first) await switchWorkspace(first.getAttribute("data-path"));
        }
        if (workspacesModal && workspacesModal.style.display === "flex") {
          await openWorkspaceManager(true);
        }
      } else {
        showToast("工作区操作失败（未找到或已变更）");
      }
    } catch (e) {
      showToast(`工作区操作失败: ${e.message}`);
    }
  }

  function actionLabel(action, kind, ok) {
    const labels = {
      rename: ok ? "已重命名" : "重命名失败",
      pin: ok ? "已更新置顶状态" : "置顶更新失败",
      archive: ok ? (kind === "workspace" ? "工作区已归档" : "已归档") : "归档失败",
      restore: ok ? "已恢复" : "恢复失败",
      trash: ok ? "已移入回收站（30 天内可恢复）" : "移入回收站失败",
      purge: ok ? "已彻底删除" : "删除失败",
      remove: ok ? "已从侧栏移除（磁盘目录未动）" : "移除失败",
      export: ok ? "已导出" : "导出失败",
    };
    return labels[action] || (ok ? "操作成功" : "操作失败");
  }

  function confirmThenSession(id, action) {
    const texts = {
      archive: "归档后会话将从“全部”列表隐藏，可随时恢复。",
      trash: "移入回收站后保留 30 天，期间可以恢复。",
      purge: "彻底删除后无法恢复，是否继续？",
    };
    showConfirm({
      title: action === "purge" ? "彻底删除会话" : (action === "trash" ? "移入回收站" : "归档会话"),
      text: texts[action],
      danger: true,
      requireText: action === "purge" ? "DELETE" : null,
      onConfirm: () => sessionAction(id, action),
    });
  }

  function confirmThenWorkspace(path, action) {
    const texts = {
      archive: "归档后该工作区默认不再显示在侧栏，目录和产物不会受影响，可恢复。",
      remove: "仅从侧栏移除注册，磁盘目录、任务与产物完全保留。",
    };
    showConfirm({
      title: action === "archive" ? "归档工作区" : "从侧栏移除工作区",
      text: texts[action],
      danger: action === "remove",
      onConfirm: () => workspaceAction(path, action),
    });
  }

  function updateBatchBar() {
    const ids = [...selectedSessionIds];
    sidebarBatchBar.style.display = ids.length ? "flex" : "none";
    batchCount.innerText = `已选 ${ids.length} 项`;
    btnBatchRestore.style.display = (sidebarView !== "active") ? "inline-block" : "none";
    btnBatchArchive.style.display = sidebarView === "active" ? "inline-block" : "none";
    btnBatchTrash.style.display = sidebarView !== "trash" ? "inline-block" : "none";
    btnBatchPurge.style.display = sidebarView === "trash" ? "inline-block" : "none";
  }

  async function batchApply(action) {
    const ids = [...selectedSessionIds];
    if (!ids.length) return;
    const labels = {
      archive: ["批量归档", "归档后可在“归档”视图恢复。"],
      trash: ["批量移入回收站", `将 ${ids.length} 个会话移入回收站，30 天内可恢复。`],
      restore: ["批量恢复", "恢复后会话将回到“全部”视图。"],
      purge: ["批量彻底删除", `将永久删除 ${ids.length} 个会话，无法恢复。`],
    };
    showConfirm({
      title: labels[action][0],
      text: labels[action][1],
      danger: action === "trash" || action === "purge",
      requireText: (action === "purge" && ids.length >= 10) ? "DELETE" : null,
      onConfirm: async () => {
        const res = await fetch("/api/sessions/batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids, action })
        });
        const data = await res.json();
        selectedSessionIds.clear();
        if (action === "archive" || action === "trash" || action === "restore") {
          for (const id of data.ok || []) selectedSessionIds.delete(id);
        }
        showToast(`批量${labels[action][0]}：成功 ${(data.ok || []).length}，失败 ${(data.missing || []).length}`);
        await refreshTree();
      }
    });
  }

  function showConfirm({ title, text, danger = false, requireText = null, onConfirm }) {
    confirmTitle.innerText = title;
    confirmText.innerText = text;
    confirmInput.style.display = requireText ? "block" : "none";
    confirmInput.value = "";
    confirmOkBtn.classList.toggle("danger", danger);
    confirmCallback = onConfirm;
    confirmModal.style.display = "flex";
    if (requireText) confirmInput.focus();
  }

  function hideConfirm() {
    confirmModal.style.display = "none";
    confirmCallback = null;
  }

  async function openWorkspaceManager(silent = false) {
    try {
      const res = await fetch("/api/workspaces/manage");
      const data = await res.json();
      renderWorkspaceManager(data);
      workspacesModal.style.display = "flex";
    } catch (e) {
      if (!silent) showToast(`工作区管理加载失败: ${e.message}`);
    }
  }

  function renderWorkspaceManager(data) {
    const groups = [
      ["active", "当前工作区", data.active || []],
      ["archived", "已归档", data.archived || []],
      ["removed", "已从侧栏移除", data.removed || []],
    ];
    workspacesManageBody.innerHTML = groups.map(([key, label, rows]) => {
      if (!rows.length) return "";
      const rowsHtml = rows.map(w => {
        const isCurrent = data.current && w.path.toLowerCase() === data.current.toLowerCase();
        return `
          <div class="ws-row" data-path="${escapeAttr(w.path)}">
            <div class="ws-row-info">
              <div class="ws-row-title">${escapeHtml(w.display_name || w.name)}${w.pinned ? " 📌" : ""}${isCurrent ? " · 当前" : ""}</div>
              <div class="ws-row-path" title="${escapeAttr(w.path)}">${escapeHtml(w.path)}</div>
            </div>
            <div class="ws-row-actions">
              ${key === "active" ? `
                <button class="ws-action-btn" data-ws-action="rename">重命名</button>
                <button class="ws-action-btn" data-ws-action="pin">${w.pinned ? "取消置顶" : "置顶"}</button>
                <button class="ws-action-btn" data-ws-action="archive">归档</button>
                <button class="ws-action-btn danger" data-ws-action="remove">移出侧栏</button>
              ` : `
                <button class="ws-action-btn" data-ws-action="restore">恢复</button>
                <button class="ws-action-btn danger" data-ws-action="purge">删除注册</button>
              `}
            </div>
          </div>
        `;
      }).join("");
      return `<div><div class="ws-group-title">${escapeHtml(label)}</div>${rowsHtml}</div>`;
    }).join("") || `<div class="empty-tree-placeholder">没有已注册的工作区</div>`;

    workspacesManageBody.querySelectorAll("[data-ws-action]").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const row = btn.closest(".ws-row");
        const path = row.getAttribute("data-path");
        const action = btn.getAttribute("data-ws-action");
        if (action === "rename") {
          const titleEl = row.querySelector(".ws-row-title");
          const input = document.createElement("input");
          input.type = "text";
          input.className = "inline-rename-input";
          input.value = titleEl.innerText.replace("📌", "").replace(" · 当前", "").trim();
          titleEl.innerHTML = "";
          titleEl.appendChild(input);
          input.focus();
          input.select();
          let done = false;
          const finish = async (save) => {
            if (done) return;
            done = true;
            if (save && input.value.trim()) await workspaceAction(path, "rename", { display_name: input.value.trim() });
            else await openWorkspaceManager(true);
          };
          input.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter") { ev.preventDefault(); finish(true); }
            else if (ev.key === "Escape") { ev.preventDefault(); finish(false); }
          });
          input.addEventListener("blur", () => finish(true));
          return;
        }
        if (action === "pin") {
          const pinned = btn.innerText.includes("取消");
          await workspaceAction(path, "pin", { pinned: !pinned });
          return;
        }
        if (action === "archive" || action === "remove") {
          confirmThenWorkspace(path, action);
          return;
        }
        if (action === "restore") {
          await workspaceAction(path, "restore");
          return;
        }
        if (action === "purge") {
          showConfirm({
            title: "删除工作区注册",
            text: "只会删除注册记录，不会触碰磁盘目录。确定？",
            danger: true,
            onConfirm: async () => {
              await workspaceAction(path, "purge");
              openWorkspaceManager(true);
            }
          });
        }
      });
    });
  }

  // ------------------------------------------------------------------ Workspace & Session Actions
  async function switchWorkspace(workspacePath) {
    if (!workspacePath) return;
    activeWorkspacePath = workspacePath;
    await fetch("/api/workspace", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workspace: workspacePath })
    });
    fetchArtifacts();
    loadPptPreview(1, true);
  }

  function newSessionInProject(workspacePath) {
    if (isRunning) return;
    activeSessionId = null;
    currentPptData = null;
    currentDeckPath = "";
    if (sidebarView !== "active") {
      sidebarView = "active";
      sidebarViewTabs.forEach(t => t.classList.toggle("active", (t.getAttribute("data-view") || "active") === "active"));
    }
    currentTitle.innerText = "新对话";
    
    chatContainer.innerHTML = "";
    if (welcomeHero) {
      chatContainer.appendChild(welcomeHero.cloneNode(true));
      bindWelcomeCards();
    }
    
    timelineLog.innerText = "";
    cotLog.innerText = "模型实际返回的 reasoning_content 会实时显示在这里。";
    rawReasoning = "";
    refreshCounts(0, 0, 0);
    refreshTree();
    fetchArtifacts();
    if (pptDeckName) pptDeckName.textContent = "未检测到 PPT";
    if (pptSlideCounter) pptSlideCounter.textContent = "-";
    if (pptSlideNavBar) pptSlideNavBar.innerHTML = "";
    if (pptPreviewImg) pptPreviewImg.style.display = "none";
    if (pptPreviewPlaceholder) pptPreviewPlaceholder.style.display = "flex";
    if (pptContentTxt) pptContentTxt.value = "";
    promptInput.focus();
  }

  async function loadSession(sessionId, workspacePath) {
    if (isRunning) return;
    try {
      if (workspacePath && workspacePath !== activeWorkspacePath) {
        await switchWorkspace(workspacePath);
      }
      const res = await fetch(`/api/session/${sessionId}`);
      const data = await res.json();
      if (!data || !data.messages) return;

      activeSessionId = sessionId;
      currentTitle.innerText = data.title || "对话";
      renderHistory(data);
      refreshTree();
      fetchArtifacts();
      await loadPptPreview(1, true, null, sessionId);
      showToast("历史会话已加载，可接着继续对话");
    } catch (e) {
      console.error("Load session failed:", e);
    }
  }

  function renderSessionActivity(payload) {
    const messages = payload.messages || [];
    const toolOutputs = {};
    for (const msg of messages) {
      if (msg.role === "tool" && msg.tool_call_id) {
        toolOutputs[msg.tool_call_id] = msg.content || "";
      }
    }

    const timeline = [];
    const reasoningParts = [];
    let started = 0;
    let completed = 0;
    let failed = 0;

    for (const msg of messages) {
      if (msg.role === "assistant") {
        const reasoning = msg.reasoning_content;
        if (reasoning && reasoning.trim()) {
          reasoningParts.push(reasoning.trim());
        }
        for (const tc of msg.tool_calls || []) {
          const fn = tc.function || {};
          const name = fn.name || "tool";
          let args = "";
          try {
            args = JSON.stringify(JSON.parse(fn.arguments || "{}"));
          } catch (e) {
            args = fn.arguments || "";
          }
          const output = toolOutputs[tc.id] || "";
          const isError = /TOOL ERROR|RuntimeError|ValueError|TypeError/.test(output);
          started += 1;
          if (isError) {
            failed += 1;
            timeline.push(`✕ ${name} ${args}`);
          } else {
            completed += 1;
            timeline.push(`✓ ${name} ${args}`);
          }
          const tail = output.slice(0, 500).replace(/\n+/g, " ");
          if (tail) timeline.push(`  → ${tail}`);
        }
      }
    }

    timelineLog.innerText = timeline.join("\n") || "该会话没有工具调用。";
    cotLog.innerText = reasoningParts.join("\n\n") || "模型未返回 reasoning_content；真实思维链为空，不伪造。";
    liveCounts.innerText = `工具 ${started} · 完成 ${completed} · 失败 ${failed}`;
    livePhase.innerText = `Phase: ${payload.phase || "unknown"}`;
    liveElapsed.innerText = "历史会话";
    liveAction.innerHTML = `<span class="icon" style="color: var(--accent);">${ICONS.file}</span><span>${payload.final_summary ? "历史会话已完成" : "历史会话已加载"}</span>`;
  }

  function historyOriginalPrompt(payload) {
    const messages = payload.messages || [];
    const hasRealUser = messages.some(m =>
      m.role === "user"
      && (m.content || "").trim()
      && !looksLikeHarnessInjected(m.content)
      && !(m.content || "").trim().toLowerCase().startsWith("continue the active task")
    );
    if (hasRealUser) return "";
    for (const msg of messages) {
      if (msg.role !== "system") continue;
      const match = /Goal:\s*([^\n]+)/.exec(msg.content || "");
      if (match && match[1].trim()) {
        return match[1].trim();
      }
    }
    const facts = payload.facts || {};
    return (facts.manifest_batch_goal || "").trim();
  }

  function renderHistory(payload) {
    removeWorkingStatus();
    chatContainer.innerHTML = "";
    timelineLog.innerText = "";
    cotLog.innerText = "";
    rawReasoning = "";
    renderSessionActivity(payload);

    const originalPrompt = historyOriginalPrompt(payload);
    if (originalPrompt) {
      appendUserMessage(originalPrompt);
    }

    const messages = payload.messages || [];
    const toolOutputs = {};
    for (const msg of messages) {
      if (msg.role === "tool" && msg.tool_call_id) {
        toolOutputs[msg.tool_call_id] = msg.content || "";
      }
    }

    for (const msg of messages) {
      const role = msg.role;
      const content = msg.content || "";
      const reasoning = msg.reasoning_content;

      if (role === "user") {
        if (content && !looksLikeHarnessInjected(content)) {
          appendUserMessage(content);
        }
      } else if (role === "assistant") {
        if (reasoning && reasoning.trim()) {
          appendThoughtCard(reasoning);
        }
        if (msg.tool_calls && msg.tool_calls.length) {
          for (const tc of msg.tool_calls) {
            const fn = tc.function || {};
            const output = toolOutputs[tc.id] || "";
            const failed = /TOOL ERROR|RuntimeError|ValueError|TypeError/.test(output);
            appendHistoryToolCard(fn.name || "tool", fn.arguments || "", output, failed);
          }
        }
        if (content && !content.trim()) {
          // empty assistant content is normal for a pure tool-call turn
        } else if (content) {
          appendAssistantMessage(content);
        }
      } else if (role === "tool") {
        // already rendered next to its assistant tool_calls
      } else if (role === "system") {
        if (content.startsWith("Identity (non-negotiable):") || looksLikeRuntimeState(content)) {
          continue;
        }
        appendSystemMessage(content);
      }
    }

    // The model's own final summary is authoritative; never synthesize a
    // harness verdict for it.
    const finalSummary = (payload.final_summary || "").trim();
    if (finalSummary) {
      const last = messages[messages.length - 1];
      const alreadyShown = last && last.role === "assistant" && (last.content || "") === finalSummary;
      if (!alreadyShown) {
        appendAssistantMessage(finalSummary);
      }
    }

    scrollToBottom();
  }

  function looksLikeHarnessInjected(text) {
    const t = text.trim().toLowerCase();
    return (
      t.startsWith("continue the active task")
      || t.startsWith("cegar-h detected")
      || t.startsWith("observation stays closed")
      || t.startsWith("ppt observation is closed")
      || t.startsWith("this action task is not complete")
    );
  }

  function looksLikeRuntimeState(text) {
    const t = text.trim().toLowerCase();
    return (
      t.startsWith("long history compacted")
      || t.startsWith("cegar-h runtime decision")
      || t.startsWith("bound source paths:")
    );
  }

  function appendHistoryToolCard(toolName, args, output, failed) {
    removeWelcomeHero();
    const card = document.createElement("div");
    card.className = "tool-step-card history";
    let argsHtml = "";
    if (args) {
      try {
        const parsed = JSON.parse(args);
        argsHtml = `<div class="tool-step-args">${escapeHtml(JSON.stringify(parsed, null, 1))}</div>`;
      } catch (e) {
        argsHtml = `<div class="tool-step-args">${escapeHtml(args)}</div>`;
      }
    }
    const outputHtml = output ? `<div class="tool-step-output">${escapeHtml(output.slice(0, 2000))}</div>` : "";
    const status = failed ? `<span class="tool-status-pill failed">失败</span>` : `<span class="tool-status-pill done">完成</span>`;
    card.innerHTML = `
      <div class="tool-step-header">
        <div class="tool-badge">
          <span class="icon" style="color: var(--accent);">${ICONS.tool}</span>
          <span>${escapeHtml(toolName)}</span>
        </div>
        ${status}
      </div>
      ${argsHtml}
      ${outputHtml}
    `;
    chatContainer.appendChild(card);
    scrollToBottom();
    return card;
  }

  // ------------------------------------------------------------------ Message & Stream Rendering
  function appendUserMessage(text) {
    removeWelcomeHero();
    const row = document.createElement("div");
    row.className = "chat-row user";
    row.innerHTML = `<div class="message-card user">${escapeHtml(text)}</div>`;
    chatContainer.appendChild(row);
    scrollToBottom();
  }

  function appendSystemMessage(text) {
    removeWelcomeHero();
    const row = document.createElement("div");
    row.className = "chat-row system";
    row.innerHTML = `<div class="message-card system">${escapeHtml(text)}</div>`;
    chatContainer.appendChild(row);
    scrollToBottom();
  }

  function appendAssistantMessage(text) {
    const card = appendAssistantContainer();
    card.innerHTML = formatMarkdown(text);
    return card;
  }

  function appendThoughtCard(initialContent = "") {
    removeWelcomeHero();
    const card = document.createElement("div");
    card.className = "thought-card";
    card.innerHTML = `
      <div class="thought-header">
        <div class="thought-title-group">
          <span class="icon thought-sparkle">${ICONS.sparkle}</span>
          <span>Thought process (思考过程)</span>
          <span class="thought-timer-badge">实时</span>
        </div>
        <span class="icon project-chevron-icon">${ICONS.chevron}</span>
      </div>
      <div class="thought-content">${escapeHtml(initialContent)}</div>
    `;

    card.querySelector(".thought-header").addEventListener("click", () => {
      card.classList.toggle("collapsed");
    });

    if (activeWorkingIndicator && activeWorkingIndicator.parentNode === chatContainer) {
      chatContainer.insertBefore(card, activeWorkingIndicator);
    } else {
      chatContainer.appendChild(card);
    }
    scrollToBottom();
    return card;
  }

  let activeWorkingIndicator = null;

  function showWorkingIndicator(title = "✨ 报一正在思考与执行中…", detail = "正在分析任务意图与编排工具…") {
    removeWorkingStatus();
    removeWelcomeHero();
    const indicator = document.createElement("div");
    indicator.className = "working-indicator-card";
    indicator.innerHTML = `
      <div class="working-spinner">
        <div class="spinner-dot"></div>
        <div class="spinner-dot"></div>
        <div class="spinner-dot"></div>
      </div>
      <div class="working-status-info">
        <div class="working-title">
          <span>${escapeHtml(title)}</span>
        </div>
        <div class="working-detail">${escapeHtml(detail)}</div>
      </div>
      <div class="working-live-badge">工作中</div>
    `;
    chatContainer.appendChild(indicator);
    activeWorkingIndicator = indicator;
    scrollToBottom();
    return indicator;
  }

  function updateWorkingStatus(title, detail) {
    if (!activeWorkingIndicator || !activeWorkingIndicator.isConnected) {
      showWorkingIndicator(title || "✨ 报一正在思考与执行中…", detail || "正在执行…");
      return;
    }
    if (title) {
      const titleEl = activeWorkingIndicator.querySelector(".working-title span");
      if (titleEl) titleEl.innerText = title;
    }
    if (detail) {
      const detailEl = activeWorkingIndicator.querySelector(".working-detail");
      if (detailEl) detailEl.innerText = detail;
    }
    if (chatContainer.lastElementChild !== activeWorkingIndicator) {
      chatContainer.appendChild(activeWorkingIndicator);
    }
    scrollToBottom();
  }

  function removeWorkingStatus() {
    document.querySelectorAll(".working-indicator-card").forEach(el => el.remove());
    activeWorkingIndicator = null;
  }

  function appendAssistantContainer() {
    removeWelcomeHero();
    const row = document.createElement("div");
    row.className = "chat-row assistant";
    const box = document.createElement("div");
    box.className = "assistant-message-box";
    const msgCard = document.createElement("div");
    msgCard.className = "message-card assistant";
    box.appendChild(msgCard);
    row.appendChild(box);

    if (activeWorkingIndicator && activeWorkingIndicator.parentNode === chatContainer) {
      chatContainer.insertBefore(row, activeWorkingIndicator);
    } else {
      chatContainer.appendChild(row);
    }
    scrollToBottom();
    return msgCard;
  }

  function appendToolCard(toolName, args) {
    removeWelcomeHero();
    const card = document.createElement("div");
    card.className = "tool-step-card";
    card.innerHTML = `
      <div class="tool-step-header">
        <div class="tool-badge">
          <span class="icon" style="color: var(--accent);">${ICONS.tool}</span>
          <span>${escapeHtml(toolName)}</span>
        </div>
        <span class="tool-status-pill running">执行中…</span>
      </div>
      ${args ? `<div class="tool-step-output">${escapeHtml(args)}</div>` : ""}
    `;
    if (activeWorkingIndicator && activeWorkingIndicator.parentNode === chatContainer) {
      chatContainer.insertBefore(card, activeWorkingIndicator);
    } else {
      chatContainer.appendChild(card);
    }
    scrollToBottom();
    return card;
  }

  function formatMarkdown(text) {
    if (!text) return "";
    
    // Code blocks with language header & copy button
    let formatted = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const language = lang.trim() || "CODE";
      return `
        <div class="code-block-wrapper">
          <div class="code-block-header">
            <span>${escapeHtml(language)}</span>
            <button class="copy-code-btn" onclick="navigator.clipboard.writeText(this.closest('.code-block-wrapper').querySelector('pre').innerText); this.innerText='已复制✓'; setTimeout(()=>this.innerText='复制', 2000);">
              <span class="icon" style="width: 12px; height: 12px;">${ICONS.copy}</span>
              <span>复制</span>
            </button>
          </div>
          <pre><code>${escapeHtml(code.trim())}</code></pre>
        </div>
      `;
    });

    // Inline code
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Headers
    formatted = formatted.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    formatted = formatted.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    formatted = formatted.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Bold & Italics
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Unordered lists
    formatted = formatted.replace(/^\s*[-*]\s+(.*$)/gim, '<li>$1</li>');
    formatted = formatted.replace(/(<li>.*<\/li>)/sim, '<ul>$1</ul>');

    // Paragraphs
    formatted = formatted.replace(/\n\n+/g, '</p><p>');
    if (!formatted.startsWith("<")) {
      formatted = `<p>${formatted}</p>`;
    }

    return formatted;
  }

  function removeWelcomeHero() {
    const hero = document.getElementById("welcome-hero");
    if (hero) hero.remove();
  }

  function scrollToBottom() {
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  // ------------------------------------------------------------------ Send & Stream Logic
  async function sendMessage() {
    const prompt = promptInput.value.trim();
    if (!prompt || isRunning) return;

    appendUserMessage(prompt);
    promptInput.value = "";
    promptInput.style.height = "28px";

    setRunning(true);
    abortController = new AbortController();
    rawReasoning = "";
    currentThoughtCard = null;
    showWorkingIndicator("✨ 报一正在思考与执行中…", "正在分析任务意图与编排工具…");
    currentAssistantCard = appendAssistantContainer();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt,
          session_id: activeSessionId,
          model: modelSelect.value,
          reasoning_effort: reasoningEffortSelect ? reasoningEffortSelect.value : "high",
          command_policy: permSelect ? permSelect.value : "ask"
        }),
        signal: abortController.signal
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let fullAssistantText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep remainder

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;
          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr || jsonStr === "[DONE]") continue;

          try {
            const event = JSON.parse(jsonStr);
            handleStreamEvent(event, (token) => {
              fullAssistantText += token;
              if (currentAssistantCard) {
                currentAssistantCard.innerHTML = formatMarkdown(fullAssistantText);
                scrollToBottom();
              }
            });
          } catch (pe) {
            console.error("SSE parse error:", pe);
          }
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") {
        console.error("Chat error:", e);
        appendSystemMessage(`请求异常: ${e.message}`);
      }
    } finally {
      setRunning(false);
      refreshTree();
      await fetchArtifacts();
    }
  }

  function handleStreamEvent(event, onToken) {
    const type = event.type;
    const payload = event.payload || {};
    const directText = event.content || "";

    if (type === "token") {
      // Server streams {"type":"token","content":...}; tolerate payload.text too.
      removeWorkingStatus();
      onToken(payload.text || directText || "");
    } else if (type === "thought" || type === "reasoning") {
      const thoughtText = payload.text || directText || "";
      rawReasoning += thoughtText;
      cotLog.innerText = rawReasoning;
      updateWorkingStatus("🧠 报一正在深度思考…", "正在推理设计方案与结构…");

      if (!currentThoughtCard) {
        currentThoughtCard = appendThoughtCard(rawReasoning);
      } else {
        const contentEl = currentThoughtCard.querySelector(".thought-content");
        if (contentEl) {
          contentEl.innerText = rawReasoning;
        }
      }
      scrollToBottom();
    } else if (type === "model_response") {
      const reasoning = payload.reasoning_content || "";
      const content = payload.content || "";
      if (reasoning.trim()) {
        rawReasoning += reasoning;
        cotLog.innerText = rawReasoning;
        if (!currentThoughtCard) {
          currentThoughtCard = appendThoughtCard(rawReasoning);
        } else {
          const contentEl = currentThoughtCard.querySelector(".thought-content");
          if (contentEl) contentEl.innerText = rawReasoning;
        }
        scrollToBottom();
      }
      if (content.trim()) {
        removeWorkingStatus();
        appendAssistantMessage(content);
      }
    } else if (type === "result") {
      removeWorkingStatus();
      const finalText = (directText || payload.content || "").trim();
      if (finalText) {
        if (!currentAssistantCard) {
          appendAssistantMessage(finalText);
        } else if (!currentAssistantCard.innerText.trim()) {
          currentAssistantCard.innerHTML = formatMarkdown(finalText);
        } else if (!currentAssistantCard.innerText.includes(finalText.slice(0, 40))) {
          const summaryDiv = document.createElement("div");
          summaryDiv.className = "final-summary-card";
          summaryDiv.style.marginTop = "12px";
          summaryDiv.style.paddingTop = "12px";
          summaryDiv.style.borderTop = "1px solid var(--border-color, #e2e8f0)";
          summaryDiv.innerHTML = formatMarkdown(finalText);
          currentAssistantCard.appendChild(summaryDiv);
        }
        scrollToBottom();
      }
      const paused = /已安全暂停|STUCK|额度已用完/.test(finalText);
      livePhase.innerText = "Phase: done";
      liveAction.innerHTML = paused
        ? `<span class="icon" style="color: var(--danger);">${ICONS.close}</span><span>运行安全暂停</span>`
        : `<span class="icon" style="color: var(--accent-emerald);">${ICONS.check}</span><span>任务已完成并验证</span>`;
    } else if (type === "error") {
      removeWorkingStatus();
      appendSystemMessage(`请求异常: ${directText || payload.content || "未知错误"}`);
      livePhase.innerText = "Phase: error";
      liveAction.innerHTML = `<span class="icon" style="color: var(--danger);">${ICONS.close}</span><span>运行异常</span>`;
    } else if (type === "tool_started") {
      toolStarted++;
      refreshCounts(toolStarted, toolCompleted, toolFailed);
      liveAction.innerHTML = `<span class="icon" style="color: var(--accent);">${ICONS.tool}</span><span>调用 ${escapeHtml(payload.tool)}…</span>`;
      timelineLog.innerText += `▸ ${payload.tool} ${payload.arguments || ""}\n`;
      updateWorkingStatus("🛠 正在调用工具", `正在执行 ${escapeHtml(payload.tool)}…`);
      appendToolCard(payload.tool, payload.arguments || "");
    } else if (type === "tool_completed") {
      toolCompleted++;
      refreshCounts(toolStarted, toolCompleted, toolFailed);
      liveAction.innerHTML = `<span class="icon" style="color: var(--accent-emerald);">${ICONS.check}</span><span>${escapeHtml(payload.tool)} 完成</span>`;
      timelineLog.innerText += `✓ ${payload.tool} 结果: ${(payload.output || "").slice(0, 300)}\n`;
      updateWorkingStatus("✓ 工具调用完成", `${escapeHtml(payload.tool)} 执行成功，继续下一步…`);
      const runningCards = [...document.querySelectorAll(".tool-step-card")].reverse();
      const card = runningCards.find(c => c.querySelector(".tool-status-pill.running"));
      if (card) {
        const pill = card.querySelector(".tool-status-pill.running");
        pill.className = "tool-status-pill done";
        pill.innerText = "完成";
        const out = document.createElement("div");
        out.className = "tool-step-output";
        out.innerText = (payload.output || "").slice(0, 2000);
        card.appendChild(out);
      }
    } else if (type === "tool_failed") {
      toolFailed++;
      refreshCounts(toolStarted, toolCompleted, toolFailed);
      liveAction.innerHTML = `<span class="icon" style="color: var(--danger);">${ICONS.close}</span><span>${escapeHtml(payload.tool)} 失败</span>`;
      timelineLog.innerText += `✕ ${payload.tool}: ${(payload.error || "").slice(0, 200)}\n`;
      updateWorkingStatus("✕ 工具执行异常", `${escapeHtml(payload.tool)} 执行失败，正在自动修复…`);
      const runningCards = [...document.querySelectorAll(".tool-step-card")].reverse();
      const card = runningCards.find(c => c.querySelector(".tool-status-pill.running"));
      if (card) {
        const pill = card.querySelector(".tool-status-pill.running");
        pill.className = "tool-status-pill failed";
        pill.innerText = "失败";
        const out = document.createElement("div");
        out.className = "tool-step-output";
        out.innerText = (payload.error || "").slice(0, 2000);
        card.appendChild(out);
      }
    } else if (type === "phase_changed") {
      livePhase.innerText = `Phase: ${payload.to_phase}`;
      timelineLog.innerText += `阶段流转 · ${payload.from_phase} → ${payload.to_phase}\n`;
      updateWorkingStatus("⚡ 阶段流转", `当前阶段：${payload.to_phase}…`);
    } else if (type === "session_saved") {
      activeSessionId = event.session_id;
    }
  }

  function setRunning(running) {
    isRunning = running;
    btnSend.disabled = running;
    btnStop.classList.toggle("active", running);

    if (running) {
      startTime = Date.now();
      toolStarted = toolCompleted = toolFailed = 0;
      refreshCounts(0, 0, 0);
      liveAction.innerText = "已提交任务给模型…";
      livePhase.innerText = "Phase: intake";
      timerInterval = setInterval(() => {
        const sec = Math.floor((Date.now() - startTime) / 1000);
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        liveElapsed.innerText = m ? `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${sec} 秒`;
      }, 1000);
    } else {
      clearInterval(timerInterval);
      removeWorkingStatus();
      liveAction.innerText = "就绪 · 等待指令";
    }
  }

  function refreshCounts(s, c, f) {
    liveCounts.innerText = `工具 ${s} · 完成 ${c} · 失败 ${f}`;
  }

  function autoResizeTextarea() {
    promptInput.addEventListener("input", () => {
      promptInput.style.height = "auto";
      promptInput.style.height = Math.min(promptInput.scrollHeight, 180) + "px";
    });
  }

  function bindWelcomeCards() {
    document.querySelectorAll(".quick-start-card").forEach(card => {
      card.addEventListener("click", () => {
        const prompt = card.getAttribute("data-prompt");
        if (prompt) {
          promptInput.value = prompt;
          promptInput.focus();
          promptInput.style.height = "auto";
          promptInput.style.height = Math.min(promptInput.scrollHeight, 180) + "px";
        }
      });
    });
  }

  // ------------------------------------------------------------------ Event Listeners
  function bindEvents() {
    bindWelcomeCards();

    // Theme Toggle
    if (themeToggleBtn) themeToggleBtn.addEventListener("click", toggleTheme);

    // Settings Modal
    if (btnOpenSettings) {
      btnOpenSettings.addEventListener("click", async () => {
        await loadSettingsForm();
        if (settingsModal) settingsModal.style.display = "flex";
      });
    }
    if (settingsModalClose) {
      settingsModalClose.addEventListener("click", () => {
        if (settingsModal) settingsModal.style.display = "none";
      });
    }
    if (settingsCancelBtn) {
      settingsCancelBtn.addEventListener("click", () => {
        if (settingsModal) settingsModal.style.display = "none";
      });
    }
    if (settingsSaveBtn) {
      settingsSaveBtn.addEventListener("click", async () => {
        await saveSettingsForm();
      });
    }
    if (setTogglePwdBtn && setApiKey) {
      setTogglePwdBtn.addEventListener("click", () => {
        const isPwd = (setApiKey.type === "password");
        setApiKey.type = isPwd ? "text" : "password";
      });
    }

    // Native Directory Picker
    addProjectBtn.addEventListener("click", async () => {
      try {
        showToast("正在打开系统文件夹选择窗口…");
        const res = await fetch("/api/choose_directory", { method: "POST" });
        const data = await res.json();
        if (data.status === "ok" && data.path) {
          await switchWorkspace(data.path);
          newSessionInProject(data.path);
          showToast(`已添加并切换至项目：${data.path}`);
        }
      } catch (e) {
        console.error("Choose directory error:", e);
      }
    });

    sortProjectsBtn.addEventListener("click", () => {
      sortReverse = !sortReverse;
      refreshTree();
      showToast(sortReverse ? "已切换为倒序排列" : "已切换为顺序排列");
    });

    newConversationBtn.addEventListener("click", () => {
      newSessionInProject(activeWorkspacePath);
    });

    if (composerWorkspaceSelect) {
      composerWorkspaceSelect.addEventListener("change", async () => {
        const ws = composerWorkspaceSelect.value;
        if (!ws || ws === activeWorkspacePath) return;
        await switchWorkspace(ws);
        activeWorkspacePath = ws;
        refreshWorkspaceSelector(ws);
        refreshTree();
        fetchArtifacts();
        showToast(`工作区已切换：${ws}`);
      });
    }

    // Sidebar management: search, lifecycle views, batch operations
    let searchTimer = null;
    if (sidebarSearch) {
      sidebarSearch.addEventListener("input", () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
          sidebarQuery = sidebarSearch.value.trim();
          selectedSessionIds.clear();
          refreshTree();
        }, 180);
      });
    }
    sidebarViewTabs.forEach(tab => {
      tab.addEventListener("click", () => {
        sidebarView = tab.getAttribute("data-view") || "active";
        sidebarViewTabs.forEach(t => t.classList.toggle("active", t === tab));
        selectedSessionIds.clear();
        refreshTree();
      });
    });
    if (btnManageWorkspaces) {
      btnManageWorkspaces.addEventListener("click", () => openWorkspaceManager());
    }
    if (btnBatchArchive) btnBatchArchive.addEventListener("click", () => batchApply("archive"));
    if (btnBatchTrash) btnBatchTrash.addEventListener("click", () => batchApply("trash"));
    if (btnBatchRestore) btnBatchRestore.addEventListener("click", () => batchApply("restore"));
    if (btnBatchPurge) btnBatchPurge.addEventListener("click", () => batchApply("purge"));
    if (btnBatchCancel) {
      btnBatchCancel.addEventListener("click", () => {
        selectedSessionIds.clear();
        refreshTree();
      });
    }
    if (workspacesModalClose) workspacesModalClose.addEventListener("click", () => { workspacesModal.style.display = "none"; });
    if (workspacesModalDone) workspacesModalDone.addEventListener("click", () => { workspacesModal.style.display = "none"; refreshTree(); });
    if (confirmModalClose) confirmModalClose.addEventListener("click", hideConfirm);
    if (confirmCancelBtn) confirmCancelBtn.addEventListener("click", hideConfirm);
    if (confirmOkBtn) {
      confirmOkBtn.addEventListener("click", () => {
        if (confirmInput.style.display !== "none" && confirmInput.value.trim() !== "DELETE") {
          showToast("请输入 DELETE 确认彻底删除");
          confirmInput.focus();
          return;
        }
        const cb = confirmCallback;
        hideConfirm();
        if (cb) cb();
      });
    }
    document.addEventListener("click", (e) => {
      if (!e.target.closest("#context-menu")) closeContextMenu();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeContextMenu();
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
        if (sidebarSearch) { e.preventDefault(); sidebarSearch.focus(); }
      }
      if (e.key === "F2") {
        const active = document.querySelector(".tree-session-item.active");
        if (active) { e.preventDefault(); startInlineRename(active); }
      }
    });

    // Composer Input
    promptInput.addEventListener("keydown", (e) => {
      if (e.ctrlKey && e.key === "Enter") {
        e.preventDefault();
        sendMessage();
      }
    });
    btnSend.addEventListener("click", sendMessage);

    btnStop.addEventListener("click", () => {
      if (abortController) {
        abortController.abort();
        fetch("/api/cancel", { method: "POST" });
        appendSystemMessage("已发送中断请求。");
      }
    });

    // Drawer Tabs & Toggle
    btnToggleActivity.addEventListener("click", () => {
      activityDrawer.classList.toggle("closed");
    });
    drawerCloseBtn.addEventListener("click", () => {
      activityDrawer.classList.add("closed");
    });

    if (tabPptBtn) {
      tabPptBtn.addEventListener("click", () => {
        tabPptBtn.classList.add("active");
        tabTimelineBtn.classList.remove("active");
        tabCotBtn.classList.remove("active");
        if (tabPptPanel) tabPptPanel.style.display = "flex";
        tabTimelinePanel.style.display = "none";
        tabCotPanel.style.display = "none";
        loadPptPreview(currentSlideIndex, false, null, activeSessionId);
      });
    }

    tabTimelineBtn.addEventListener("click", () => {
      tabTimelineBtn.classList.add("active");
      if (tabPptBtn) tabPptBtn.classList.remove("active");
      tabCotBtn.classList.remove("active");
      if (tabPptPanel) tabPptPanel.style.display = "none";
      tabTimelinePanel.style.display = "flex";
      tabCotPanel.style.display = "none";
    });

    tabCotBtn.addEventListener("click", () => {
      tabCotBtn.classList.add("active");
      if (tabPptBtn) tabPptBtn.classList.remove("active");
      tabTimelineBtn.classList.remove("active");
      if (tabPptPanel) tabPptPanel.style.display = "none";
      tabCotPanel.style.display = "flex";
      tabTimelinePanel.style.display = "none";
    });

    if (btnRefreshPpt) {
      btnRefreshPpt.addEventListener("click", async () => {
        await loadPptPreview(currentSlideIndex, true, null, activeSessionId);
        showToast("PPT 预览与文本已刷新");
      });
    }

    if (btnSaveasPpt) {
      btnSaveasPpt.addEventListener("click", async () => {
        await handleSavePpt();
      });
    }

    if (btnCopyPptText) {
      btnCopyPptText.addEventListener("click", async () => {
        const text = pptContentTxt ? pptContentTxt.value : "";
        const ok = await copyText(text);
        showToast(ok ? "幻灯片 TXT 文本已复制" : "复制失败");
      });
    }

    if (btnApplyPptText) {
      btnApplyPptText.addEventListener("click", async () => {
        await applyPptContent();
      });
    }

    copyTimelineBtn.addEventListener("click", async () => {
      const ok = await copyText(timelineLog.innerText || "");
      showToast(ok ? "时间线记录已复制" : "复制失败，请手动选择复制");
    });

    copyCotBtn.addEventListener("click", async () => {
      const ok = await copyText(rawReasoning || cotLog.innerText || "");
      showToast(ok ? "原始思维链已复制" : "复制失败，请手动选择复制");
    });

    // Artifacts Hub Modal Trigger
    if (btnArtifactsHub) {
      btnArtifactsHub.addEventListener("click", async () => {
        await fetchArtifacts();
        if (artifactsModal) {
          artifactsModal.style.display = "flex";
        }
      });
    }
    if (artifactsModalClose) {
      artifactsModalClose.addEventListener("click", () => {
        if (artifactsModal) artifactsModal.style.display = "none";
      });
    }
    if (artifactsModalDone) {
      artifactsModalDone.addEventListener("click", () => {
        if (artifactsModal) artifactsModal.style.display = "none";
      });
    }
    if (btnRefreshArtifacts) {
      btnRefreshArtifacts.addEventListener("click", async () => {
        await fetchArtifacts();
        showToast("产物列表已刷新");
      });
    }

    // Export Session
    if (btnExport) {
      btnExport.addEventListener("click", async () => {
        const res = await fetch("/api/session/export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: activeSessionId })
        });
        const data = await res.json();
        if (data.status === "ok") {
          showToast(`已导出至：${data.path}`);
        } else {
          showToast(data.message || "导出失败");
        }
      });
    }

    // Goal Modal
    btnGoalDialog.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/goal");
        const data = await res.json();
        goalInput.value = data.summary || "";
      } catch (e) {
        goalInput.value = "";
      }
      goalModal.style.display = "flex";
    });

    goalModalClose.addEventListener("click", () => {
      goalModal.style.display = "none";
    });
    goalCancelBtn.addEventListener("click", () => {
      goalModal.style.display = "none";
    });

    goalSaveBtn.addEventListener("click", async () => {
      const goalText = goalInput.value.trim();
      await fetch("/api/goal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: goalText })
      });
      goalModal.style.display = "none";
      showToast("长期目标已保存");
    });
  }

  // ------------------------------------------------------------------ Toast & Helpers
  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      try {
        const area = document.createElement("textarea");
        area.value = text;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
        return true;
      } catch (e2) {
        return false;
      }
    }
  }

  function showToast(msg) {
    if (!toast) return;
    toast.innerText = msg;
    toast.classList.add("show");
    setTimeout(() => {
      toast.classList.remove("show");
    }, 2800);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function escapeAttr(str) {
    if (!str) return "";
    return String(str)
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Launch on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
