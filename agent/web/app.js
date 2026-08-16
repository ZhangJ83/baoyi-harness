// Xiaopu Modern Web UI Application Logic with Hierarchical Tree Management
(() => {
  // DOM Elements
  const chatArea = document.getElementById("chat-area");
  const promptInput = document.getElementById("prompt-input");
  const btnSend = document.getElementById("btn-send");
  const btnStop = document.getElementById("btn-stop");
  const modelSelect = document.getElementById("model-select");
  const permSelect = document.getElementById("perm-select");
  const currentTitle = document.getElementById("current-title");
  const themeToggleBtn = document.getElementById("theme-toggle-btn");

  // Tree Elements
  const projectsTreeList = document.getElementById("projects-tree-list");
  const conversationsTreeList = document.getElementById("conversations-tree-list");
  const addProjectBtn = document.getElementById("add-project-btn");
  const sortProjectsBtn = document.getElementById("sort-projects-btn");
  const newConversationBtn = document.getElementById("new-conversation-btn");

  // Activity Drawer Elements
  const activityDrawer = document.getElementById("activity-drawer");
  const btnToggleActivity = document.getElementById("btn-toggle-activity");
  const drawerCloseBtn = document.getElementById("drawer-close-btn");
  const liveAction = document.getElementById("live-action");
  const livePhase = document.getElementById("live-phase");
  const liveElapsed = document.getElementById("live-elapsed");
  const liveCounts = document.getElementById("live-counts");
  const timelineLog = document.getElementById("timeline-log");
  const cotLog = document.getElementById("cot-log");
  const tabTimelineBtn = document.getElementById("tab-timeline-btn");
  const tabCotBtn = document.getElementById("tab-cot-btn");
  const tabTimelinePanel = document.getElementById("tab-timeline-panel");
  const tabCotPanel = document.getElementById("tab-cot-panel");
  const copyTimelineBtn = document.getElementById("copy-timeline-btn");
  const copyCotBtn = document.getElementById("copy-cot-btn");

  // Action Buttons
  const btnVerify = document.getElementById("btn-verify");
  const btnSavePpt = document.getElementById("btn-save-ppt");
  const btnUndo = document.getElementById("btn-undo");
  const btnExport = document.getElementById("btn-export");
  const btnGoalDialog = document.getElementById("btn-goal-dialog");

  // App State
  let activeSessionId = null;
  let activeWorkspacePath = null;
  let isRunning = false;
  let abortController = null;
  let timerInterval = null;
  let startTime = null;
  let toolStarted = 0, toolCompleted = 0, toolFailed = 0;
  let rawReasoning = "";
  let sortReverse = false;

  // ------------------------------------------------------------------ Theme
  const savedTheme = localStorage.getItem("xiaopu-theme") || "light";
  document.documentElement.setAttribute("data-theme", savedTheme);

  themeToggleBtn.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("xiaopu-theme", next);
  });

  // ------------------------------------------------------------------ Drawer Tabs
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

  btnToggleActivity.addEventListener("click", () => {
    activityDrawer.classList.toggle("closed");
  });

  drawerCloseBtn.addEventListener("click", () => {
    activityDrawer.classList.add("closed");
  });

  copyTimelineBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(timelineLog.innerText);
    showToast("已复制时间线");
  });

  copyCotBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(rawReasoning || cotLog.innerText);
    showToast("已复制原始思维链");
  });

  // ------------------------------------------------------------------ Toast
  function showToast(msg) {
    const toast = document.createElement("div");
    toast.className = "message-card system";
    toast.style.position = "fixed";
    toast.style.bottom = "80px";
    toast.style.left = "50%";
    toast.style.transform = "translateX(-50%)";
    toast.style.zIndex = "9999";
    toast.innerText = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
  }

  // ------------------------------------------------------------------ Init Data
  async function init() {
    try {
      // 1. Load config & models
      const cfgRes = await fetch("/api/config");
      const cfg = await cfgRes.json();
      
      modelSelect.innerHTML = cfg.known_models.map(m => 
        `<option value="${m}" ${m === cfg.current_model ? "selected" : ""}>${m}</option>`
      ).join("");

      permSelect.value = cfg.command_policy || "ask";

      // 2. Load tree hierarchy (Projects & Conversations)
      await refreshTree();
    } catch (e) {
      console.error("Init failed:", e);
    }
  }

  // ------------------------------------------------------------------ Tree Hierarchy Rendering
  async function refreshTree() {
    try {
      const res = await fetch("/api/tree");
      const data = await res.json();
      activeWorkspacePath = data.current_workspace;

      const projects = data.projects || [];
      const conversations = data.conversations || [];

      if (sortReverse) {
        projects.reverse();
      }

      // 1. Render Projects
      if (projects.length === 0) {
        projectsTreeList.innerHTML = `<div class="empty-tree-placeholder">暂无项目</div>`;
      } else {
        projectsTreeList.innerHTML = projects.map(p => {
          const sessionsHtml = (p.sessions && p.sessions.length > 0)
            ? p.sessions.map(s => renderSessionRow(s)).join("")
            : `<div class="empty-tree-placeholder" style="padding: 4px 10px;">(暂无会话)</div>`;

          return `
            <div class="project-node" data-path="${escapeAttr(p.path)}">
              <div class="project-folder-header">
                <div class="project-folder-info" title="${escapeAttr(p.path)}">
                  <span class="project-folder-icon">📁</span>
                  <span class="project-folder-name">${escapeHtml(p.name)}</span>
                </div>
                <button class="project-add-chat-btn" data-path="${escapeAttr(p.path)}" title="在此项目下新建对话">＋</button>
              </div>
              <div class="project-sessions-list">
                ${sessionsHtml}
              </div>
            </div>
          `;
        }).join("");
      }

      // 2. Render Conversations (Standalone/Unassigned)
      if (conversations.length === 0) {
        conversationsTreeList.innerHTML = `<div class="empty-tree-placeholder" style="padding: 4px 10px;">暂无独立对话</div>`;
      } else {
        conversationsTreeList.innerHTML = conversations.map(s => renderSessionRow(s)).join("");
      }

      // 3. Bind Tree Click & Delete Handlers
      bindTreeEvents();
    } catch (e) {
      console.error("Refresh tree failed:", e);
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
          <button class="tree-session-del-btn" data-id="${s.id}" title="删除会话">✕</button>
        </div>
      </div>
    `;
  }

  function bindTreeEvents() {
    // Click on session row -> load session
    document.querySelectorAll(".tree-session-item").forEach(el => {
      el.addEventListener("click", (e) => {
        if (e.target.classList.contains("tree-session-del-btn")) return;
        const id = el.getAttribute("data-id");
        const ws = el.getAttribute("data-ws");
        loadSession(id, ws);
      });
    });

    // Delete button
    document.querySelectorAll(".tree-session-del-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = btn.getAttribute("data-id");
        if (confirm("确认删除该会话记录？")) {
          await fetch(`/api/session/${id}`, { method: "DELETE" });
          if (activeSessionId === id) {
            newSessionInProject(activeWorkspacePath);
          } else {
            refreshTree();
          }
        }
      });
    });

    // Click on "+" in project header -> new chat in that project
    document.querySelectorAll(".project-add-chat-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const ws = btn.getAttribute("data-path");
        await switchWorkspace(ws);
        newSessionInProject(ws);
      });
    });

    // Click on folder header -> switch active workspace
    document.querySelectorAll(".project-folder-header").forEach(hdr => {
      hdr.addEventListener("click", async (e) => {
        if (e.target.classList.contains("project-add-chat-btn")) return;
        const projectNode = hdr.closest(".project-node");
        if (projectNode) {
          const ws = projectNode.getAttribute("data-path");
          if (ws && ws !== activeWorkspacePath) {
            await switchWorkspace(ws);
            showToast(`已切换工作区到：${ws}`);
            refreshTree();
          }
        }
      });
    });
  }

  // ------------------------------------------------------------------ Tree Action Buttons
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
      showToast("无法打开系统选择器");
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

  async function switchWorkspace(workspacePath) {
    if (!workspacePath) return;
    activeWorkspacePath = workspacePath;
    await fetch("/api/workspace", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workspace: workspacePath })
    });
  }

  function newSessionInProject(workspacePath) {
    if (isRunning) return;
    activeSessionId = null;
    currentTitle.innerText = "新对话";
    chatArea.innerHTML = `
      <div class="chat-row system">
        <div class="message-card system">已开启全新对话。输入任务描述开始执行。</div>
      </div>
    `;
    timelineLog.innerText = "";
    cotLog.innerText = "模型实际返回的 reasoning_content 会实时显示在这里。";
    rawReasoning = "";
    refreshCounts(0, 0, 0);
    refreshTree();
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
      showToast("会话已加载，可接着继续对话");
    } catch (e) {
      console.error("Load session failed:", e);
    }
  }

  function renderHistory(payload) {
    chatArea.innerHTML = "";
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
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  // ------------------------------------------------------------------ Message Rendering
  function appendUserMessage(text) {
    const row = document.createElement("div");
    row.className = "chat-row user";
    row.innerHTML = `
      <div class="message-card user">
        <div class="msg-header">
          <span class="msg-role">你</span>
          <button class="msg-copy-btn">复制</button>
        </div>
        <div class="msg-body">${escapeHtml(text)}</div>
      </div>
    `;
    row.querySelector(".msg-copy-btn").addEventListener("click", () => {
      navigator.clipboard.writeText(text);
      showToast("已复制");
    });
    chatArea.appendChild(row);
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  function appendThoughtCard(reasoningText) {
    const card = document.createElement("div");
    card.className = "thought-card";
    card.innerHTML = `
      <div class="thought-header">
        <div class="thought-title">
          <span>⏱</span> Thought process (思考过程)
          <span class="thought-done-badge">✓ Done</span>
        </div>
        <button class="msg-copy-btn" style="font-size: 9px;">折叠/展开</button>
      </div>
      <div class="thought-body">${escapeHtml(reasoningText.trim())}</div>
    `;
    const body = card.querySelector(".thought-body");
    card.querySelector(".thought-header").addEventListener("click", () => {
      body.classList.toggle("collapsed");
    });
    chatArea.appendChild(card);
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  function appendAssistantMessage(text) {
    const row = document.createElement("div");
    row.className = "chat-row assistant";
    row.innerHTML = `
      <div class="message-card assistant">
        <div class="msg-header">
          <span class="msg-role">
            <span style="display:inline-block;width:16px;height:16px;background:var(--accent-blue);color:#fff;border-radius:4px;text-align:center;line-height:16px;font-size:9px;">朴</span>
            小朴
          </span>
          <button class="msg-copy-btn">复制</button>
        </div>
        <div class="msg-body">${formatMarkdown(text)}</div>
      </div>
    `;
    row.querySelector(".msg-copy-btn").addEventListener("click", () => {
      navigator.clipboard.writeText(text);
      showToast("已复制");
    });
    chatArea.appendChild(row);
    chatArea.scrollTop = chatArea.scrollHeight;
    return row.querySelector(".msg-body");
  }

  function appendSystemMessage(text) {
    const row = document.createElement("div");
    row.className = "chat-row system";
    row.innerHTML = `<div class="message-card system">${escapeHtml(text)}</div>`;
    chatArea.appendChild(row);
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  // ------------------------------------------------------------------ Chat Dispatch & Streaming
  async function sendMessage() {
    if (isRunning) return;
    const task = promptInput.value.trim();
    if (!task) return;

    promptInput.value = "";
    appendUserMessage(task);

    if (currentTitle.innerText === "新对话") {
      currentTitle.innerText = task.slice(0, 18) + (task.length > 18 ? "…" : "");
    }

    setRunning(true);
    let streamBodyEl = null;
    let streamBuffer = "";
    let reasoningBuffer = "";

    try {
      abortController = new AbortController();
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task: task,
          session_id: activeSessionId,
          model: modelSelect.value,
          permission: permSelect.value,
        }),
        signal: abortController.signal,
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep last incomplete line

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr || jsonStr === "[DONE]") continue;

          try {
            const event = JSON.parse(jsonStr);
            handleStreamEvent(event, (token) => {
              streamBuffer += token;
              if (!streamBodyEl) {
                if (reasoningBuffer.trim()) {
                  appendThoughtCard(reasoningBuffer);
                }
                streamBodyEl = appendAssistantMessage(streamBuffer);
              } else {
                streamBodyEl.innerHTML = formatMarkdown(streamBuffer);
              }
              chatArea.scrollTop = chatArea.scrollHeight;
            }, (reasoningToken) => {
              reasoningBuffer += reasoningToken;
              rawReasoning += reasoningToken;
              cotLog.innerText = rawReasoning;
            });
          } catch (e) {
            console.error("Parse event error:", e);
          }
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") {
        appendSystemMessage(`执行出错: ${e.message}`);
      }
    } finally {
      setRunning(false);
      refreshTree();
    }
  }

  function handleStreamEvent(event, onToken, onReasoning) {
    const type = event.type;
    const payload = event.payload || {};

    if (type === "token") {
      onToken(event.content);
    } else if (type === "reasoning") {
      onReasoning(event.content);
    } else if (type === "tool_started") {
      toolStarted++;
      refreshCounts(toolStarted, toolCompleted, toolFailed);
      liveAction.innerText = `⚡ 调用 ${payload.tool}…`;
      const logLine = `▸ ${payload.tool} ${payload.arguments || ""}\n`;
      timelineLog.innerText += logLine;
    } else if (type === "tool_completed") {
      toolCompleted++;
      refreshCounts(toolStarted, toolCompleted, toolFailed);
      liveAction.innerText = `✓ ${payload.tool} 完成`;
      const logLine = `✓ ${payload.tool} 结果: ${(payload.output || "").slice(0, 300)}\n`;
      timelineLog.innerText += logLine;
    } else if (type === "tool_failed") {
      toolFailed++;
      refreshCounts(toolStarted, toolCompleted, toolFailed);
      liveAction.innerText = `✕ ${payload.tool} 失败`;
      const logLine = `✕ ${payload.tool}: ${(payload.error || "").slice(0, 200)}\n`;
      timelineLog.innerText += logLine;
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

  // Keyboard shortcut Ctrl+Enter to send
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

  // ------------------------------------------------------------------ Action Tools
  btnVerify.addEventListener("click", async () => {
    showToast("正在执行 PPT 结构校验…");
    const res = await fetch("/api/ppt/verify", { method: "POST" });
    const data = await res.json();
    appendAssistantMessage(`【PPT 校验结果】\n${data.result}`);
  });

  btnSavePpt.addEventListener("click", async () => {
    let savePath = "";
    try {
      showToast("正在打开系统文件保存窗口…");
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
      savePath = prompt("请输入另存为的 PPT 文件名或路径：", "presentation.pptx");
    }
    if (!savePath) return;

    const res = await fetch("/api/ppt/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: savePath })
    });
    const data = await res.json();
    appendAssistantMessage(`【保存 PPT】\n${data.result}`);
  });

  btnUndo.addEventListener("click", async () => {
    const res = await fetch("/api/ppt/undo", { method: "POST" });
    const data = await res.json();
    appendAssistantMessage(`【撤销】\n${data.result}`);
  });

  btnExport.addEventListener("click", async () => {
    const res = await fetch("/api/session/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: activeSessionId })
    });
    const data = await res.json();
    showToast(`会话已导出: ${data.path}`);
  });

  btnGoalDialog.addEventListener("click", async () => {
    const res = await fetch("/api/goal");
    const data = await res.json();
    const action = prompt(`🎯 长期目标状态：\n${data.summary}\n\n输入新目标描述并确定即可启动新目标（直接取消则仅查看）：`);
    if (action && action.trim()) {
      const startRes = await fetch("/api/goal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ objective: action.trim() })
      });
      const startData = await startRes.json();
      appendSystemMessage(`【长期目标】${startData.result}`);
    }
  });

  // ------------------------------------------------------------------ Helpers
  function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.innerText = str;
    return div.innerHTML;
  }

  function escapeAttr(str) {
    if (!str) return "";
    return String(str).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function formatMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);
    // Code blocks
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    // Bullet points
    html = html.replace(/^[*-]\s+(.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/g, '<ul>$1</ul>');
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    return html;
  }

  // Initialize on load
  init();
})();
