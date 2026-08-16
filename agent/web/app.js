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

  // Activity Drawer
  const activityDrawer = document.getElementById("activity-drawer");
  const btnToggleActivity = document.getElementById("btn-toggle-activity");
  const drawerCloseBtn = document.getElementById("drawer-close-btn");
  const tabTimelineBtn = document.getElementById("tab-timeline-btn");
  const tabCotBtn = document.getElementById("tab-cot-btn");
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
  }

  // ------------------------------------------------------------------ Tree Management
  async function refreshTree() {
    try {
      const params = new URLSearchParams({ view: sidebarView, q: sidebarQuery });
      const res = await fetch(`/api/tree?${params.toString()}`);
      const data = await res.json();
      if (!data) return;

      activeWorkspacePath = data.current_workspace;
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
  }

  function newSessionInProject(workspacePath) {
    if (isRunning) return;
    activeSessionId = null;
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
      showToast("历史会话已加载，可接着继续对话");
    } catch (e) {
      console.error("Load session failed:", e);
    }
  }

  function renderHistory(payload) {
    chatContainer.innerHTML = "";
    timelineLog.innerText = "";
    cotLog.innerText = "";
    rawReasoning = "";

    const messages = payload.messages || [];
    for (const msg of messages) {
      const role = msg.role;
      const content = msg.content || "";
      const reasoning = msg.reasoning_content;

      if (role === "user" && content) {
        appendUserMessage(content);
      } else if (role === "assistant") {
        if (reasoning && reasoning.trim()) {
          appendThoughtCard(reasoning);
        }
        if (content) {
          appendAssistantMessage(content);
        } else if (msg.tool_calls && msg.tool_calls.length) {
          const toolNames = msg.tool_calls.map(tc => tc.function?.name || "tool").join(", ");
          appendAssistantMessage(`✓ 调用了工具: ${toolNames}`);
        }
      } else if (role === "system" && content && !content.startsWith("Identity (non-negotiable):")) {
        appendSystemMessage(content);
      }
    }
    scrollToBottom();
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

    chatContainer.appendChild(card);
    scrollToBottom();
    return card;
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
    chatContainer.appendChild(row);
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
    chatContainer.appendChild(card);
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
      onToken(payload.text || directText || "");
    } else if (type === "thought" || type === "reasoning") {
      const thoughtText = payload.text || directText || "";
      rawReasoning += thoughtText;
      cotLog.innerText = rawReasoning;

      if (!currentThoughtCard) {
        currentThoughtCard = appendThoughtCard(rawReasoning);
      } else {
        const contentEl = currentThoughtCard.querySelector(".thought-content");
        if (contentEl) {
          contentEl.innerText = rawReasoning;
        }
      }
      scrollToBottom();
    } else if (type === "result") {
      // Providers occasionally return no token deltas; render the final text
      // so a completed turn is never invisible in the bubble.
      const finalText = directText || "";
      if (finalText && currentAssistantCard && !currentAssistantCard.innerText.trim()) {
        currentAssistantCard.innerHTML = formatMarkdown(finalText);
        scrollToBottom();
      }
    } else if (type === "error") {
      appendSystemMessage(`请求异常: ${directText || payload.content || "未知错误"}`);
    } else if (type === "tool_started") {
      toolStarted++;
      refreshCounts(toolStarted, toolCompleted, toolFailed);
      liveAction.innerHTML = `<span class="icon" style="color: var(--accent);">${ICONS.tool}</span><span>调用 ${escapeHtml(payload.tool)}…</span>`;
      timelineLog.innerText += `▸ ${payload.tool} ${payload.arguments || ""}\n`;
      appendToolCard(payload.tool, payload.arguments || "");
    } else if (type === "tool_completed") {
      toolCompleted++;
      refreshCounts(toolStarted, toolCompleted, toolFailed);
      liveAction.innerHTML = `<span class="icon" style="color: var(--accent-emerald);">${ICONS.check}</span><span>${escapeHtml(payload.tool)} 完成</span>`;
      timelineLog.innerText += `✓ ${payload.tool} 结果: ${(payload.output || "").slice(0, 300)}\n`;
    } else if (type === "tool_failed") {
      toolFailed++;
      refreshCounts(toolStarted, toolCompleted, toolFailed);
      liveAction.innerHTML = `<span class="icon" style="color: var(--danger);">${ICONS.close}</span><span>${escapeHtml(payload.tool)} 失败</span>`;
      timelineLog.innerText += `✕ ${payload.tool}: ${(payload.error || "").slice(0, 200)}\n`;
    } else if (type === "phase_changed") {
      livePhase.innerText = `Phase: ${payload.to_phase}`;
      timelineLog.innerText += `阶段流转 · ${payload.from_phase} → ${payload.to_phase}\n`;
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

    tabTimelineBtn.addEventListener("click", () => {
      tabTimelineBtn.classList.add("active");
      tabCotBtn.classList.remove("active");
      tabTimelinePanel.style.display = "flex";
      tabCotPanel.style.display = "none";
    });

    tabCotBtn.addEventListener("click", () => {
      tabCotBtn.classList.add("active");
      tabTimelineBtn.classList.remove("active");
      tabCotPanel.style.display = "flex";
      tabTimelinePanel.style.display = "none";
    });

    copyTimelineBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(timelineLog.innerText);
      showToast("时间线记录已复制");
    });

    copyCotBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(rawReasoning || cotLog.innerText);
      showToast("原始思维链已复制");
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
