const state = {
  token: localStorage.getItem("sm_token") || "",
  user: null,
  categories: [],
  page: "home",
  homeView: "list",
  listTab: "today",
  editingCategoryId: null,
  filters: {
    keyword: "",
    category: "全部",
    status: "pending",
    sort: "created_desc",
  },
  calendar: {
    startDate: "",
    days: 35,
  },
  tasks: [],
  dashboard: null,
};

const recurrenceLabels = {
  none: "不重复",
  daily: "每天",
  weekly: "每周",
  monthly: "每月",
};

const quadrantLabels = {
  1: "Q1 重要且紧急",
  2: "Q2 重要不紧急",
  3: "Q3 紧急不重要",
  4: "Q4 不重要不紧急",
};

const el = {
  toast: document.getElementById("toast"),
  authView: document.getElementById("auth-view"),
  appView: document.getElementById("app-view"),
  userLabel: document.getElementById("user-label"),
  pageHome: document.getElementById("page-home"),
  pageCategories: document.getElementById("page-categories"),
  pageStats: document.getElementById("page-stats"),
  modalRoot: document.getElementById("modal-root"),
};

function showToast(msg) {
  el.toast.textContent = msg;
  el.toast.classList.add("show");
  setTimeout(() => el.toast.classList.remove("show"), 1800);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function recurrenceText(rule) {
  return recurrenceLabels[rule] || recurrenceLabels.none;
}

function quadrantText(quadrant) {
  return quadrantLabels[quadrant] || `Q${quadrant}`;
}

function formatDateTime(value) {
  if (!value) return "未设置截止时间";
  return String(value).slice(0, 16).replace("T", " ");
}

function formatDueForInput(value) {
  if (!value) return "";
  return String(value).slice(0, 16).replace(" ", "T");
}

function parseDateTime(value) {
  if (!value) return null;
  const date = new Date(String(value).replace(" ", "T"));
  return Number.isNaN(date.getTime()) ? null : date;
}

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function endOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
}

function addDays(date, days) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function addMonthsSafe(date, months) {
  const next = new Date(date);
  const totalMonth = next.getMonth() + months;
  const year = next.getFullYear() + Math.floor(totalMonth / 12);
  const month = ((totalMonth % 12) + 12) % 12;
  const day = Math.min(next.getDate(), 28);
  return new Date(year, month, day, next.getHours(), next.getMinutes(), next.getSeconds());
}

function computeNextOccurrence(task, rangeStart, rangeEnd) {
  const due = parseDateTime(task.due_at);
  if (!due) return null;
  const rule = task.recurrence_rule || "none";
  let current = new Date(due);
  let guard = 0;
  while (current < rangeStart && guard < 400) {
    if (rule === "daily") current = addDays(current, 1);
    else if (rule === "weekly") current = addDays(current, 7);
    else if (rule === "monthly") current = addMonthsSafe(current, 1);
    else break;
    guard += 1;
  }
  if (current >= rangeStart && current <= rangeEnd) return current;
  return null;
}

function expandOccurrences(task, rangeStart, rangeEnd, limit = 120) {
  const due = parseDateTime(task.due_at);
  if (!due) return [];
  const rule = task.recurrence_rule || "none";
  const items = [];
  let current = new Date(due);
  let guard = 0;
  while (current <= rangeEnd && guard < limit) {
    if (current >= rangeStart) {
      items.push({
        ...task,
        occurrence_at: current.toISOString().slice(0, 19).replace("T", " "),
        occurrence_date: current.toISOString().slice(0, 10),
      });
    }
    if (rule === "none") break;
    if (rule === "daily") current = addDays(current, 1);
    else if (rule === "weekly") current = addDays(current, 7);
    else current = addMonthsSafe(current, 1);
    guard += 1;
  }
  return items;
}

function jitter(seed, magnitude = 0.08) {
  let hash = 0;
  const src = String(seed);
  for (let i = 0; i < src.length; i += 1) {
    hash = (hash << 5) - hash + src.charCodeAt(i);
    hash |= 0;
  }
  return ((Math.abs(hash) % 100) / 100 - 0.5) * magnitude;
}

function quadrantToAxes(q) {
  const map = { 1: [0.8, 0.8], 2: [0.8, 0.3], 3: [0.3, 0.8], 4: [0.3, 0.3] };
  return map[q] || [0.5, 0.5];
}

function dueTone(task) {
  if (task.due_state === "overdue") return "danger";
  if (task.due_state === "upcoming") return "warn";
  return "muted";
}

function taskSummary(task, occurrenceAt = "") {
  const parts = [
    quadrantText(task.quadrant),
    `分类: ${task.category}`,
    `截止: ${task.due_at ? formatDateTime(task.due_at) : "未设置"}`,
    `重复: ${recurrenceText(task.recurrence_rule)}`,
  ];
  if (occurrenceAt) parts.push(`本次安排: ${occurrenceAt.slice(0, 16)}`);
  return parts.join(" | ");
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const resp = await fetch(path, { ...options, headers });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || "请求失败");
  return data;
}

async function downloadFile(path, filenameHint) {
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const resp = await fetch(path, { headers });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || "下载失败");
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filenameHint;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function loadCategories() {
  const result = await api("/api/categories");
  state.categories = result.items;
}

function getCategoryNames() {
  return state.categories.map((item) => item.name);
}

function getCategoryByName(name) {
  return state.categories.find((item) => item.name === name) || null;
}

function sortTasks(tasks) {
  const mapping = {
    created_desc: ["created_at", true],
    created_asc: ["created_at", false],
    updated_desc: ["updated_at", true],
    updated_asc: ["updated_at", false],
  };
  const [field, desc] = mapping[state.filters.sort] || mapping.created_desc;
  return [...tasks].sort((a, b) => {
    const aa = a[field] || "";
    const bb = b[field] || "";
    if (aa === bb) return desc ? b.id - a.id : a.id - b.id;
    return desc ? bb.localeCompare(aa) : aa.localeCompare(bb);
  });
}

function getFilteredTasks() {
  let items = [...state.tasks];
  if (state.filters.keyword.trim()) {
    const keyword = state.filters.keyword.trim().toLowerCase();
    items = items.filter((task) => `${task.title} ${task.description || ""}`.toLowerCase().includes(keyword));
  }
  if (state.filters.category !== "全部") {
    items = items.filter((task) => task.category === state.filters.category);
  }
  return sortTasks(items);
}

async function loadWorkspaceData() {
  const [tasksResp, dashboardResp] = await Promise.all([
    api(`/api/tasks?status=${encodeURIComponent(state.filters.status)}&sort=${encodeURIComponent(state.filters.sort)}`),
    api("/api/stats/dashboard"),
  ]);
  state.tasks = tasksResp.items;
  state.dashboard = dashboardResp;
}

function closeModal() {
  el.modalRoot.innerHTML = "";
  el.modalRoot.classList.add("hidden");
}

function taskFormMarkup(editing, defaults = {}) {
  const categoryNames = getCategoryNames();
  const seed = editing ? { ...editing } : { quadrant: 1, recurrence_rule: "none", ...defaults };
  if (!categoryNames.length) {
    return `
      <div class="modal-card">
        <div class="modal-head">
          <h3>无法添加任务</h3>
          <button class="modal-close" data-close-modal>×</button>
        </div>
        <p>请先创建至少一个分类，再回来添加任务。</p>
        <div class="modal-actions">
          <button class="btn primary" data-go-categories>前往分类管理</button>
        </div>
      </div>
    `;
  }
  return `
    <div class="modal-card modal-wide">
      <div class="modal-head">
        <h3>${editing ? "编辑任务" : "新增任务"}</h3>
        <button class="modal-close" data-close-modal>×</button>
      </div>
      <form id="task-modal-form" class="form">
        <label>任务标题
          <input id="task-title" required value="${escapeHtml(seed.title || "")}" />
        </label>
        <label>任务描述
          <textarea id="task-desc">${escapeHtml(seed.description || "")}</textarea>
        </label>
        <div class="editor-grid">
          <label>分类
            <select id="task-category">
              ${categoryNames.map((name, index) => `<option ${(seed.category ? seed.category === name : index === 0) ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}
            </select>
          </label>
          <label>优先级象限
            <select id="task-quadrant">
              ${[1, 2, 3, 4].map((q) => `<option value="${q}" ${Number(seed.quadrant || 1) === q ? "selected" : ""}>${quadrantText(q)}</option>`).join("")}
            </select>
          </label>
        </div>
        <div class="editor-grid">
          <label>截止日期时间
            <input id="task-due-at" type="datetime-local" value="${escapeHtml(formatDueForInput(seed.due_at || ""))}" />
          </label>
          <label>重复日程
            <select id="task-recurrence">
              ${Object.entries(recurrenceLabels).map(([key, label]) => `<option value="${key}" ${(seed.recurrence_rule || "none") === key ? "selected" : ""}>${escapeHtml(label)}</option>`).join("")}
            </select>
          </label>
        </div>
        <div class="modal-actions">
          <button class="btn primary" type="submit">${editing ? "保存修改" : "创建任务"}</button>
          <button class="btn ghost" type="button" data-close-modal>取消</button>
        </div>
      </form>
    </div>
  `;
}

function openTaskModal(task = null, defaults = {}) {
  el.modalRoot.innerHTML = `<div class="modal-backdrop">${taskFormMarkup(task, defaults)}</div>`;
  el.modalRoot.classList.remove("hidden");
  el.modalRoot.querySelectorAll("[data-close-modal]").forEach((node) => node.addEventListener("click", closeModal));
  const jump = el.modalRoot.querySelector("[data-go-categories]");
  if (jump) {
    jump.addEventListener("click", () => {
      closeModal();
      showPage("categories");
    });
  }
  const form = document.getElementById("task-modal-form");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      title: document.getElementById("task-title").value,
      description: document.getElementById("task-desc").value,
      category: document.getElementById("task-category").value,
      quadrant: Number(document.getElementById("task-quadrant").value),
      due_at: document.getElementById("task-due-at").value,
      recurrence_rule: document.getElementById("task-recurrence").value,
    };
    if (task) {
      await api(`/api/tasks/${task.id}`, { method: "PUT", body: JSON.stringify(payload) });
      showToast("任务已更新");
    } else {
      await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
      showToast("任务已创建");
    }
    closeModal();
    await rerenderCurrentPage();
  });
}

async function confirmDeleteTask(task) {
  const ok = window.confirm(`确认删除任务？\n\n${task.title}\n${taskSummary(task)}`);
  if (!ok) return;
  await api(`/api/tasks/${task.id}`, { method: "DELETE" });
  showToast("任务已删除");
  await rerenderCurrentPage();
}

function renderTaskActions(taskId, compact = false) {
  return `
    <div class="task-actions ${compact ? "compact" : ""}">
      <button class="btn ghost" data-action="edit-task" data-id="${taskId}">编辑</button>
      <button class="btn danger" data-action="delete-task" data-id="${taskId}">删除</button>
    </div>
  `;
}

function renderTaskCard(task, options = {}) {
  const categoryInfo = getCategoryByName(task.category);
  const categoryColor = categoryInfo?.color || task.category_color || "#94A3B8";
  return `
    <article class="task-card ${task.completed ? "is-completed" : ""}" id="task-${task.id}">
      <div class="task-body">
        <div class="task-head">
          <label class="task-check">
            <input type="checkbox" data-action="toggle-task" data-id="${task.id}" ${task.completed ? "checked" : ""} />
            <span class="task-title">${escapeHtml(task.title)}</span>
          </label>
          <span class="category-badge" style="--badge:${escapeHtml(categoryColor)}">${escapeHtml(task.category)}</span>
        </div>
        <div class="task-tags">
          <span class="quad-badge q${task.quadrant}">${quadrantText(task.quadrant)}</span>
          <span class="due-badge ${dueTone(task)}">${escapeHtml(task.due_text || "未设置截止时间")}</span>
          <span class="plain-badge">${escapeHtml(recurrenceText(task.recurrence_rule))}</span>
        </div>
        <div class="task-meta">${escapeHtml(taskSummary(task, options.occurrenceAt || ""))}</div>
        ${task.description ? `<p>${escapeHtml(task.description)}</p>` : ""}
      </div>
      ${renderTaskActions(task.id)}
    </article>
  `;
}

async function bindTaskActions(root) {
  root.querySelectorAll("[data-action='edit-task']").forEach((node) => {
    node.addEventListener("click", () => {
      const task = state.tasks.find((item) => item.id === Number(node.dataset.id));
      if (task) openTaskModal(task);
    });
  });
  root.querySelectorAll("[data-action='delete-task']").forEach((node) => {
    node.addEventListener("click", async () => {
      const task = state.tasks.find((item) => item.id === Number(node.dataset.id));
      if (task) await confirmDeleteTask(task);
    });
  });
  root.querySelectorAll("[data-action='toggle-task']").forEach((node) => {
    node.addEventListener("change", async () => {
      await api(`/api/tasks/${node.dataset.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ completed: node.checked }),
      });
      showToast(node.checked ? "任务已标记为完成" : "任务已恢复为未完成");
      await rerenderCurrentPage();
    });
  });
}

function getListGroups(tasks) {
  const now = new Date();
  const todayStart = startOfDay(now);
  const todayEnd = endOfDay(now);
  const weekEnd = endOfDay(addDays(todayStart, 6));
  const today = tasks
    .map((task) => ({ task, occurrence: computeNextOccurrence(task, todayStart, todayEnd) }))
    .filter((item) => item.occurrence)
    .sort((a, b) => a.occurrence - b.occurrence);
  const week = tasks
    .map((task) => ({ task, occurrence: computeNextOccurrence(task, todayStart, weekEnd) }))
    .filter((item) => item.occurrence)
    .sort((a, b) => a.occurrence - b.occurrence);
  return { today, week, all: tasks };
}

function renderListView(tasks) {
  const groups = getListGroups(tasks);
  const tabs = [
    { key: "today", label: `今日任务 (${groups.today.length})` },
    { key: "week", label: `本周任务 (${groups.week.length})` },
    { key: "all", label: `全部任务 (${groups.all.length})` },
  ];
  let content = "";
  if (state.listTab === "today") {
    content = groups.today.length
      ? groups.today.map(({ task, occurrence }) => renderTaskCard(task, { occurrenceAt: occurrence.toISOString().slice(0, 19).replace("T", " ") })).join("")
      : '<div class="empty-state">今天没有符合筛选条件的任务。</div>';
  } else if (state.listTab === "week") {
    content = groups.week.length
      ? groups.week.map(({ task, occurrence }) => renderTaskCard(task, { occurrenceAt: occurrence.toISOString().slice(0, 19).replace("T", " ") })).join("")
      : '<div class="empty-state">本周没有符合筛选条件的任务。</div>';
  } else {
    content = groups.all.length
      ? groups.all.map((task) => renderTaskCard(task)).join("")
      : '<div class="empty-state">当前没有符合筛选条件的任务。</div>';
  }
  return `
    <div class="subtabs">
      ${tabs.map((tab) => `<button class="subtab ${state.listTab === tab.key ? "active" : ""}" data-list-tab="${tab.key}">${tab.label}</button>`).join("")}
    </div>
    <div class="task-list">${content}</div>
  `;
}

function renderQuadrantView(tasks) {
  return `
    <div class="quad-board">
      <span class="quad-label top-left">Q1 重要且紧急</span>
      <span class="quad-label top-right">Q3 紧急不重要</span>
      <span class="quad-label bottom-left">Q2 重要不紧急</span>
      <span class="quad-label bottom-right">Q4 不重要不紧急</span>
      ${tasks.map((task) => {
        const [x, y] = quadrantToAxes(task.quadrant);
        return `<button class="task-dot q${task.quadrant} ${task.completed ? "is-completed" : ""}" style="left:${(x + jitter(task.id + "x")) * 100}%;bottom:${(y + jitter(task.id + "y")) * 100}%;" title="${escapeHtml(`${task.title} | ${quadrantText(task.quadrant)} | ${task.due_text}`)}" data-scroll-id="${task.id}"></button>`;
      }).join("")}
    </div>
    <div class="task-list">${tasks.length ? tasks.map((task) => renderTaskCard(task)).join("") : '<div class="empty-state">当前没有符合筛选条件的任务。</div>'}</div>
  `;
}

function renderCalendarView(tasks) {
  const startDate = state.calendar.startDate || new Date().toISOString().slice(0, 10);
  const start = new Date(`${startDate}T00:00:00`);
  const end = endOfDay(addDays(start, state.calendar.days - 1));
  const grouped = {};
  tasks.forEach((task) => {
    expandOccurrences(task, start, end).forEach((item) => {
      grouped[item.occurrence_date] ||= [];
      grouped[item.occurrence_date].push(item);
    });
  });
  Object.keys(grouped).forEach((key) => grouped[key].sort((a, b) => a.occurrence_at.localeCompare(b.occurrence_at)));
  const cells = [];
  for (let i = 0; i < state.calendar.days; i += 1) {
    const date = addDays(start, i);
    const iso = date.toISOString().slice(0, 10);
    const items = grouped[iso] || [];
    cells.push(`
      <article class="calendar-cell">
        <div class="calendar-cell-head">
          <button class="calendar-date-btn" data-add-date="${iso}" title="为 ${iso} 添加任务">${iso}</button>
          <button class="icon-btn" data-add-date="${iso}">新增</button>
        </div>
        <div class="calendar-items">
          ${
            items.length
              ? items.map((item) => `
                <div class="calendar-entry ${item.due_state}">
                  <div class="calendar-entry-main">
                    <span class="calendar-time">${escapeHtml(item.occurrence_at.slice(11, 16))}</span>
                    <strong>${escapeHtml(item.title)}</strong>
                    <span class="mini-quad q${item.quadrant}">${quadrantText(item.quadrant)}</span>
                  </div>
                  <div class="calendar-entry-actions">
                    <button class="icon-btn" data-action="edit-task" data-id="${item.id}">编辑</button>
                    <button class="icon-btn danger" data-action="delete-task" data-id="${item.id}">删除</button>
                  </div>
                </div>`).join("")
              : '<div class="calendar-empty">暂无安排</div>'
          }
        </div>
      </article>`);
  }
  return `
    <div class="calendar-toolbar">
      <label>起始日期 <input id="calendar-start-date" type="date" value="${escapeHtml(startDate)}" /></label>
      <label>显示范围
        <select id="calendar-days">
          ${[7, 14, 35].map((days) => `<option value="${days}" ${state.calendar.days === days ? "selected" : ""}>${days}天</option>`).join("")}
        </select>
      </label>
      <button class="btn ghost" id="calendar-apply">更新视图</button>
    </div>
    <div class="calendar-grid">${cells.join("")}</div>
  `;
}

function renderFilters() {
  const categoryNames = getCategoryNames();
  return `
    <div class="workspace-topbar">
      <div class="view-tabs">
        <button class="view-tab ${state.homeView === "list" ? "active" : ""}" data-view="list">列表视图</button>
        <button class="view-tab ${state.homeView === "quadrant" ? "active" : ""}" data-view="quadrant">四象限视图</button>
        <button class="view-tab ${state.homeView === "calendar" ? "active" : ""}" data-view="calendar">日历视图</button>
      </div>
      <div class="status-switch">
        ${[["pending", "未完成"], ["all", "全部"], ["completed", "已完成"]].map(([value, label]) => `<button class="status-pill ${state.filters.status === value ? "active" : ""}" data-status="${value}">${label}</button>`).join("")}
      </div>
      <div class="toolbar-actions">
        <button class="btn ghost" id="export-tasks-btn">导出CSV</button>
        <button class="btn ghost" id="import-tasks-btn">导入CSV</button>
        <input id="import-tasks-file" type="file" accept=".csv,text/csv" class="hidden" />
        <button class="btn primary" id="add-task-btn">新增任务</button>
      </div>
    </div>
    <div class="filters-grid">
      <input id="flt-keyword" placeholder="搜索标题或描述" value="${escapeHtml(state.filters.keyword)}" />
      <select id="flt-category">
        <option ${state.filters.category === "全部" ? "selected" : ""}>全部</option>
        ${categoryNames.map((name) => `<option ${state.filters.category === name ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}
      </select>
      <select id="flt-sort">
        <option value="created_desc" ${state.filters.sort === "created_desc" ? "selected" : ""}>最新创建</option>
        <option value="created_asc" ${state.filters.sort === "created_asc" ? "selected" : ""}>最早创建</option>
        <option value="updated_desc" ${state.filters.sort === "updated_desc" ? "selected" : ""}>最新更新</option>
        <option value="updated_asc" ${state.filters.sort === "updated_asc" ? "selected" : ""}>最早更新</option>
      </select>
    </div>
  `;
}

async function renderHome() {
  await loadWorkspaceData();
  const tasks = getFilteredTasks();
  let viewContent = "";
  if (state.homeView === "list") viewContent = renderListView(tasks);
  else if (state.homeView === "quadrant") viewContent = renderQuadrantView(tasks);
  else viewContent = renderCalendarView(tasks);

  el.pageHome.innerHTML = `
    <section class="hero-card">
      <div>
        <p class="eyebrow">首页</p>
        <h1>任务工作台</h1>
        <p class="hero-copy">在一个页面里完成查看、筛选、增删改和多视图切换，减少来回跳转。</p>
      </div>
      <div class="hero-metrics">
        <div><span>当前结果</span><strong>${tasks.length}</strong></div>
        <div><span>当前状态</span><strong>${state.filters.status === "pending" ? "未完成" : state.filters.status === "completed" ? "已完成" : "全部"}</strong></div>
      </div>
    </section>
    <section class="panel workspace-panel">
      ${renderFilters()}
      <div class="workspace-content">${viewContent}</div>
    </section>
  `;

  document.getElementById("add-task-btn").addEventListener("click", () => openTaskModal());
  document.getElementById("export-tasks-btn").addEventListener("click", async () => {
    try {
      await downloadFile("/api/tasks/export", "self-manager-tasks.csv");
      showToast("任务CSV已导出");
    } catch (error) {
      showToast(error.message);
    }
  });
  document.getElementById("import-tasks-btn").addEventListener("click", () => {
    document.getElementById("import-tasks-file").click();
  });
  document.getElementById("import-tasks-file").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const result = await api("/api/tasks/import", {
        method: "POST",
        body: JSON.stringify({ csv_text: text }),
      });
      showToast(`导入完成：${result.imported} 条`);
      await renderHome();
    } catch (error) {
      showToast(error.message);
    } finally {
      event.target.value = "";
    }
  });
  document.querySelectorAll("[data-view]").forEach((node) => node.addEventListener("click", async () => {
    state.homeView = node.dataset.view;
    await renderHome();
  }));
  document.querySelectorAll("[data-status]").forEach((node) => node.addEventListener("click", async () => {
    state.filters.status = node.dataset.status;
    await renderHome();
  }));
  document.getElementById("flt-keyword").addEventListener("input", async (event) => {
    state.filters.keyword = event.target.value;
    await renderHome();
  });
  document.getElementById("flt-category").addEventListener("change", async (event) => {
    state.filters.category = event.target.value;
    await renderHome();
  });
  document.getElementById("flt-sort").addEventListener("change", async (event) => {
    state.filters.sort = event.target.value;
    await renderHome();
  });
  el.pageHome.querySelectorAll("[data-list-tab]").forEach((node) => node.addEventListener("click", async () => {
    state.listTab = node.dataset.listTab;
    await renderHome();
  }));
  el.pageHome.querySelectorAll("[data-scroll-id]").forEach((node) => node.addEventListener("click", () => {
    const row = document.getElementById(`task-${node.dataset.scrollId}`);
    if (row) row.scrollIntoView({ behavior: "smooth", block: "center" });
  }));
  const applyCalendar = document.getElementById("calendar-apply");
  if (applyCalendar) {
    applyCalendar.addEventListener("click", async () => {
      state.calendar.startDate = document.getElementById("calendar-start-date").value;
      state.calendar.days = Number(document.getElementById("calendar-days").value);
      await renderHome();
    });
  }
  el.pageHome.querySelectorAll("[data-add-date]").forEach((node) => {
    node.addEventListener("click", () => {
      const date = node.dataset.addDate;
      openTaskModal(null, { due_at: `${date}T09:00` });
    });
  });
  await bindTaskActions(el.pageHome);
}

function renderTrendSVG(points) {
  const width = 860;
  const height = 220;
  const maxY = Math.max(1, ...points.map((p) => p.count));
  const step = points.length > 1 ? width / (points.length - 1) : width;
  const d = points.map((p, i) => {
    const x = i * step;
    const y = height - (p.count / maxY) * (height - 20) - 10;
    return `${i === 0 ? "M" : "L"}${x},${y}`;
  }).join(" ");
  return `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%">
      <path d="${d}" fill="none" stroke="#0f766e" stroke-width="3" />
      ${points.map((p, i) => {
        const x = i * step;
        const y = height - (p.count / maxY) * (height - 20) - 10;
        return `<circle cx="${x}" cy="${y}" r="4" fill="#0f766e"><title>${p.date}: ${p.count}</title></circle>`;
      }).join("")}
    </svg>`;
}

async function renderStats() {
  const dashboard = state.dashboard || (await api("/api/stats/dashboard"));
  const stats = dashboard.stats;
  const total = Math.max(1, stats.total);
  el.pageStats.innerHTML = `
    <h1>任务统计</h1>
    <div class="stats-toolbar">
      <button class="btn ghost" id="stats-export-tasks-btn">导出CSV备份</button>
    </div>
    <div class="metrics">
      <div class="metric"><div class="label">总任务</div><div class="value">${stats.total}</div></div>
      <div class="metric"><div class="label">未完成</div><div class="value">${stats.pending}</div></div>
      <div class="metric"><div class="label">已完成</div><div class="value">${stats.completed}</div></div>
      <div class="metric"><div class="label">近14天新增</div><div class="value">${dashboard.trend.reduce((sum, item) => sum + item.count, 0)}</div></div>
    </div>
    <div class="grid-2">
      <div class="panel"><h3>分类分布</h3>${Object.entries(stats.by_category).map(([name, count]) => `<div class="bar-item"><div class="meta"><span>${escapeHtml(name)}</span><span>${count}</span></div><div class="bar-track"><div class="bar-fill" style="width:${(count / total) * 100}%"></div></div></div>`).join("")}</div>
      <div class="panel"><h3>优先级分布</h3>${Object.entries(stats.by_quadrant).map(([q, count]) => `<div class="bar-item"><div class="meta"><span>${quadrantText(Number(q))}</span><span>${count}</span></div><div class="bar-track"><div class="bar-fill" style="width:${(count / total) * 100}%"></div></div></div>`).join("")}</div>
    </div>
    <div class="panel" style="margin-top:16px;">
      <h3>近14天新增趋势</h3>
      <div class="trend-chart">${renderTrendSVG(dashboard.trend)}</div>
    </div>`;
  document.getElementById("stats-export-tasks-btn").addEventListener("click", async () => {
    try {
      await downloadFile("/api/tasks/export", "self-manager-tasks.csv");
      showToast("任务CSV已导出");
    } catch (error) {
      showToast(error.message);
    }
  });
}

async function renderCategories() {
  await loadCategories();
  const editingCategory = state.categories.find((item) => item.id === state.editingCategoryId) || null;
  el.pageCategories.innerHTML = `
    <h1>分类管理</h1>
    <div class="grid-2 categories-layout">
      <section class="panel">
        <h3>${editingCategory ? "编辑分类" : "新建分类"}</h3>
        <form id="category-form" class="form">
          <label>分类名称 <input id="cat-name" maxlength="20" required value="${escapeHtml(editingCategory?.name || "")}" /></label>
          <label>分类颜色 <input id="cat-color" type="color" value="${escapeHtml(editingCategory?.color || "#006D77")}" /></label>
          <div class="modal-actions">
            <button class="btn primary" type="submit">${editingCategory ? "保存分类" : "创建分类"}</button>
            <button class="btn ghost" id="cat-cancel" type="button">取消</button>
          </div>
        </form>
      </section>
      <section class="panel">
        <h3>现有分类</h3>
        <div class="category-list">
          ${state.categories.map((item) => `
            <article class="category-row">
              <div class="category-row-main">
                <span class="category-dot" style="background:${escapeHtml(item.color)}"></span>
                <div>
                  <strong>${escapeHtml(item.name)}</strong>
                  <div class="task-meta">${escapeHtml(item.color)}</div>
                </div>
              </div>
              <div class="task-actions compact">
                <button class="btn ghost" data-edit-category="${item.id}">编辑</button>
                <button class="btn danger" data-delete-category="${item.id}">删除</button>
              </div>
            </article>`).join("")}
        </div>
      </section>
    </div>`;

  document.getElementById("cat-cancel").addEventListener("click", () => {
    state.editingCategoryId = null;
    renderCategories();
  });
  document.getElementById("category-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      name: document.getElementById("cat-name").value,
      color: document.getElementById("cat-color").value,
    };
    if (state.editingCategoryId) {
      await api(`/api/categories/${state.editingCategoryId}`, { method: "PUT", body: JSON.stringify(payload) });
      showToast("分类已更新");
    } else {
      await api("/api/categories", { method: "POST", body: JSON.stringify(payload) });
      showToast("分类已创建");
    }
    state.editingCategoryId = null;
    await renderCategories();
  });
  el.pageCategories.querySelectorAll("[data-edit-category]").forEach((node) => node.addEventListener("click", () => {
    state.editingCategoryId = Number(node.dataset.editCategory);
    renderCategories();
  }));
  el.pageCategories.querySelectorAll("[data-delete-category]").forEach((node) => node.addEventListener("click", async () => {
    const category = state.categories.find((item) => item.id === Number(node.dataset.deleteCategory));
    const ok = window.confirm(`确认删除分类？\n\n${category?.name || ""}`);
    if (!ok) return;
    await api(`/api/categories/${node.dataset.deleteCategory}`, { method: "DELETE" });
    showToast("分类已删除");
    await renderCategories();
  }));
}

async function rerenderCurrentPage() {
  if (state.page === "home") await renderHome();
  else if (state.page === "categories") await renderCategories();
  else await renderStats();
}

async function showPage(page) {
  state.page = page;
  document.querySelectorAll(".nav-btn").forEach((btn) => btn.classList.toggle("active", btn.dataset.page === page));
  el.pageHome.classList.toggle("hidden", page !== "home");
  el.pageCategories.classList.toggle("hidden", page !== "categories");
  el.pageStats.classList.toggle("hidden", page !== "stats");
  if (page === "home") await renderHome();
  else if (page === "categories") await renderCategories();
  else await renderStats();
}

async function bootstrapApp() {
  const me = await api("/api/auth/me");
  state.user = me.user;
  await loadCategories();
  el.userLabel.textContent = `当前用户: ${state.user.username}`;
  el.authView.classList.add("hidden");
  el.appView.classList.remove("hidden");
  await showPage(state.page);
}

function wireAuthForms() {
  const tabLogin = document.getElementById("tab-login");
  const tabRegister = document.getElementById("tab-register");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  tabLogin.addEventListener("click", () => {
    tabLogin.classList.add("active");
    tabRegister.classList.remove("active");
    loginForm.classList.remove("hidden");
    registerForm.classList.add("hidden");
  });
  tabRegister.addEventListener("click", () => {
    tabRegister.classList.add("active");
    tabLogin.classList.remove("active");
    registerForm.classList.remove("hidden");
    loginForm.classList.add("hidden");
  });
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: document.getElementById("login-username").value,
          password: document.getElementById("login-password").value,
          remember_me: document.getElementById("login-remember-me").checked,
        }),
      });
      state.token = result.token;
      localStorage.setItem("sm_token", state.token);
      showToast("登录成功");
      await bootstrapApp();
    } catch (error) {
      showToast(error.message);
    }
  });
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = document.getElementById("reg-password").value;
    const confirm = document.getElementById("reg-confirm").value;
    if (password !== confirm) {
      showToast("两次密码不一致");
      return;
    }
    try {
      await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          username: document.getElementById("reg-username").value,
          password,
        }),
      });
      showToast("注册成功，请登录");
      tabLogin.click();
    } catch (error) {
      showToast(error.message);
    }
  });
}

function wireAppShell() {
  document.querySelectorAll(".nav-btn").forEach((btn) => btn.addEventListener("click", () => showPage(btn.dataset.page)));
  document.getElementById("logout-btn").addEventListener("click", async () => {
    try {
      if (state.token) await api("/api/auth/logout", { method: "POST" });
    } catch (_) {
      // ignore
    }
    state.token = "";
    state.user = null;
    localStorage.removeItem("sm_token");
    closeModal();
    el.appView.classList.add("hidden");
    el.authView.classList.remove("hidden");
    showToast("已退出登录");
  });
}

(async function init() {
  wireAuthForms();
  wireAppShell();
  if (!state.token) return;
  try {
    await bootstrapApp();
  } catch (_) {
    state.token = "";
    localStorage.removeItem("sm_token");
  }
})();
