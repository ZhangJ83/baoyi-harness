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
  const permSelect = document.getElementById("perm-select");
  const currentTitle = document.getElementById("current-title");

  // Sidebar Tree
  const projectsTreeList = document.getElementById("projects-tree-list");
  const conversationsTreeList = document.getElementById("conversations-tree-list");
  const addProjectBtn = document.getElementById("add-project-btn");
  const sortProjectsBtn = document.getElementById("sort-projects-btn");
  const newConversationBtn = document.getElementById("new-conversation-btn");
  const themeToggleBtn = document.getElementById("theme-toggle-btn");

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

  // Goal Modal
  const btnGoalDialog = document.getElementById("btn-goal-dialog");
  const goalModal = document.getElementById("goal-modal");
  const goalModalClose = document.getElementById("goal-modal-close");
  const goalInput = document.getElementById("goal-input");
  const goalCancelBtn = document.getElementById("goal-cancel-btn");
  const goalSaveBtn = document.getElementById("goal-save-btn");

  const toast = document.getElementById("toast");

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

      if (data.command_policy) {
        permSelect.value = data.command_policy;
      }
    } catch (e) {
      console.error("Failed to load config:", e);
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
    // Reveal file
    document.querySelectorAll(".art-reveal-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const p = btn.getAttribute("data-path");
        if (p) await revealFile(p);
      });
    });

    // Copy path
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

    // Save PPT
    document.querySelectorAll(".art-save-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        await handleSavePpt();
      });
    });

    // Verify PPT
    document.querySelectorAll(".art-verify-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        await handleVerifyPpt();
      });
    });

    // Undo PPT
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
      const res = await fetch("/api/tree");
      const data = await res.json();
      if (!data) return;

      activeWorkspacePath = data.current_workspace;
      const projects = data.projects || [];
      const conversations = data.conversations || [];

      if (sortReverse) {
        projects.reverse();
      }

      // 1. Render Projects
      if (projects.length === 0) {
        projectsTreeList.innerHTML = `<div class="empty-tree-placeholder">暂无工作区项目</div>`;
      } else {
        projectsTreeList.innerHTML = projects.map(p => {
          const isCollapsed = collapsedFolders.has(p.path);
          const isCurrentWs = (p.is_current || (activeWorkspacePath && p.path && p.path.toLowerCase() === activeWorkspacePath.toLowerCase()));
          const count = (p.sessions && p.sessions.length) || 0;
          const sessionsHtml = count > 0
            ? p.sessions.map(s => renderSessionRow(s)).join("")
            : `<div class="empty-tree-placeholder">(暂无会话)</div>`;

          return `
            <div class="project-node ${isCollapsed ? "collapsed" : ""} ${isCurrentWs ? "active-ws" : ""}" data-path="${escapeAttr(p.path)}">
              <div class="project-folder-header">
                <div class="project-folder-info" title="${escapeAttr(p.path)}">
                  <span class="icon project-chevron-icon">${ICONS.chevron}</span>
                  <span class="icon project-folder-icon">${ICONS.folder}</span>
                  <span class="project-folder-name">${escapeHtml(p.name)}</span>
                </div>
                <div class="project-header-actions">
                  <span class="project-count-badge">${count}</span>
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
        conversationsTreeList.innerHTML = conversations.map(s => renderSessionRow(s)).join("");
      }

      // 3. Bind Dynamic Tree Events
      bindTreeEvents();
    } catch (e) {
      console.error("Refresh tree error:", e);
    }
  }

  function renderSessionRow(s) {
    const isActive = (s.id === activeSessionId);
    const timeDisplay = isActive ? "now" : (s.time_ago || "now");
    const showDot = !isActive;

    return `
      <div class="tree-session-item ${isActive ? "active" : ""}" data-id="${s.id}" data-ws="${escapeAttr(s.workspace || "")}">
        <span class="tree-session-title" title="${escapeAttr(s.title || "未命名对话")}">${escapeHtml(s.title || "未命名对话")}</span>
        <div class="tree-session-meta">
          <span class="meta-time-text">${escapeHtml(timeDisplay)}</span>
          ${showDot ? `<span class="meta-status-dot"></span>` : ""}
          <button class="tree-session-del-btn" data-id="${s.id}" title="删除会话">
            <span class="icon">${ICONS.close}</span>
          </button>
        </div>
      </div>
    `;
  }

  function bindTreeEvents() {
    // Toggle folder collapse or switch workspace
    document.querySelectorAll(".project-folder-header").forEach(hdr => {
      hdr.addEventListener("click", async (e) => {
        if (e.target.closest(".project-add-chat-btn")) return;
        const projectNode = hdr.closest(".project-node");
        if (!projectNode) return;
        const ws = projectNode.getAttribute("data-path");

        if (e.target.closest(".project-chevron-icon")) {
          // Toggle collapse
          if (collapsedFolders.has(ws)) {
            collapsedFolders.delete(ws);
            projectNode.classList.remove("collapsed");
          } else {
            collapsedFolders.add(ws);
            projectNode.classList.add("collapsed");
          }
          return;
        }

        // Switch workspace
        if (ws && ws !== activeWorkspacePath) {
          await switchWorkspace(ws);
          showToast(`已切换工作区：${ws}`);
          refreshTree();
          fetchArtifacts();
        }
      });
    });

    // Session click -> load session
    document.querySelectorAll(".tree-session-item").forEach(el => {
      el.addEventListener("click", (e) => {
        if (e.target.closest(".tree-session-del-btn")) return;
        const id = el.getAttribute("data-id");
        const ws = el.getAttribute("data-ws");
        loadSession(id, ws);
      });
    });

    // Session delete
    document.querySelectorAll(".tree-session-del-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = btn.getAttribute("data-id");
        if (confirm("确认删除该历史会话？")) {
          await fetch(`/api/session/${id}`, { method: "DELETE" });
          if (activeSessionId === id) {
            newSessionInProject(activeWorkspacePath);
          } else {
            refreshTree();
          }
        }
      });
    });

    // Project "+" button -> new session in that project
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
    currentTitle.innerText = "新对话";
    
    // Clear chat container and show welcome hero
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

  function appendChatArtifactCard(art) {
    removeWelcomeHero();
    const card = document.createElement("div");
    card.className = "chat-artifact-card";
    const icon = art.is_pptx ? ICONS.ppt : ICONS.file;
    const tagText = art.is_pptx ? `PPT 演示文稿${art.slides_count ? ` · ${art.slides_count}页` : ""}` : `${art.type.toUpperCase()} 文件`;

    card.innerHTML = `
      <div class="chat-artifact-header">
        <div class="chat-artifact-title">
          <span class="icon" style="color: var(--accent);">${icon}</span>
          <span>${escapeHtml(art.name)}</span>
        </div>
        <span class="artifact-tag">${escapeHtml(tagText)}</span>
      </div>
      <div class="chat-artifact-desc">文件已成功在工作区生成并就绪（大小: ${escapeHtml(art.size_human)}）</div>
      <div class="chat-artifact-actions">
        ${art.is_pptx ? `
          <button class="pill-btn art-save-btn" data-path="${escapeAttr(art.path)}"><span class="icon">${ICONS.save}</span><span>另存为</span></button>
          <button class="pill-btn art-verify-btn" data-path="${escapeAttr(art.path)}"><span class="icon">${ICONS.verify}</span><span>结构校验</span></button>
          <button class="pill-btn art-reveal-btn" data-path="${escapeAttr(art.path)}"><span class="icon">${ICONS.reveal}</span><span>打开文件夹</span></button>
        ` : `
          <button class="pill-btn art-copy-path-btn" data-path="${escapeAttr(art.path)}"><span class="icon">${ICONS.copy}</span><span>复制路径</span></button>
          <button class="pill-btn art-reveal-btn" data-path="${escapeAttr(art.path)}"><span class="icon">${ICONS.reveal}</span><span>打开文件夹</span></button>
        `}
      </div>
    `;

    chatContainer.appendChild(card);
    scrollToBottom();
    bindArtifactActions();
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
          command_policy: permSelect.value
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

    if (type === "token") {
      onToken(payload.text || "");
    } else if (type === "thought") {
      const thoughtText = payload.text || "";
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
    themeToggleBtn.addEventListener("click", toggleTheme);

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
