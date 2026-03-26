const state = {
  token: localStorage.getItem("sm_token") || "",
  user: null,
  categories: [],
  page: "dashboard",
  editId: null,
  editingCategoryId: null,
  taskFilters: {
    keyword: "",
    category: "全部",
    quadrant: "全部",
    sort: "created_desc",
    status: "pending",
  },
};

const el = {
  toast: document.getElementById("toast"),
  authView: document.getElementById("auth-view"),
  appView: document.getElementById("app-view"),
  userLabel: document.getElementById("user-label"),
  pageDashboard: document.getElementById("page-dashboard"),
  pageQuadrant: document.getElementById("page-quadrant"),
  pageEditor: document.getElementById("page-editor"),
  pageCategories: document.getElementById("page-categories"),
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

function getCategoryNames() {
  return state.categories.map((item) => item.name);
}

function getCategoryByName(name) {
  return state.categories.find((item) => item.name === name) || null;
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

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;

  const resp = await fetch(path, { ...options, headers });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || "请求失败");
  return data;
}

async function loadCategories() {
  const result = await api("/api/categories");
  state.categories = result.items;
}

function showPage(page) {
  state.page = page;
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.page === page);
  });

  el.pageDashboard.classList.toggle("hidden", page !== "dashboard");
  el.pageQuadrant.classList.toggle("hidden", page !== "quadrant");
  el.pageEditor.classList.toggle("hidden", page !== "editor");
  el.pageCategories.classList.toggle("hidden", page !== "categories");

  if (page === "dashboard") renderDashboard();
  if (page === "quadrant") renderQuadrant();
  if (page === "editor") renderEditor();
  if (page === "categories") renderCategories();
}

function renderTrendSVG(points) {
  const width = 860;
  const height = 220;
  const maxY = Math.max(1, ...points.map((p) => p.count));
  const step = points.length > 1 ? width / (points.length - 1) : width;

  const d = points
    .map((p, i) => {
      const x = i * step;
      const y = height - (p.count / maxY) * (height - 20) - 10;
      return `${i === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");

  return `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%">
      <path d="${d}" fill="none" stroke="#0f766e" stroke-width="3" />
      ${points
        .map((p, i) => {
          const x = i * step;
          const y = height - (p.count / maxY) * (height - 20) - 10;
          return `<circle cx="${x}" cy="${y}" r="4" fill="#0f766e"><title>${p.date}: ${p.count}</title></circle>`;
        })
        .join("")}
    </svg>
  `;
}

async function renderDashboard() {
  const data = await api("/api/stats/dashboard");
  const stats = data.stats;
  const byCategory = Object.entries(stats.by_category);
  const byQuadrant = Object.entries(stats.by_quadrant);
  const total = Math.max(1, stats.total);

  const categoryBars = byCategory
    .map(
      ([name, count]) => `
      <button class="bar-item clickable" data-filter-type="category" data-filter-value="${escapeHtml(name)}">
        <div class="meta"><span>${escapeHtml(name)}</span><span>${count}</span></div>
        <div class="bar-track"><div class="bar-fill" style="width:${(count / total) * 100}%"></div></div>
      </button>
    `
    )
    .join("");

  const quadrantBars = byQuadrant
    .map(
      ([q, count]) => `
      <button class="bar-item clickable" data-filter-type="quadrant" data-filter-value="${q}">
        <div class="meta"><span>Q${q}</span><span>${count}</span></div>
        <div class="bar-track"><div class="bar-fill" style="width:${(count / total) * 100}%"></div></div>
      </button>
    `
    )
    .join("");

  const recent = data.trend.reduce((sum, x) => sum + x.count, 0);

  el.pageDashboard.innerHTML = `
    <h1>任务统计首页</h1>
    <div class="metrics">
      <div class="metric"><div class="label">总任务</div><div class="value">${stats.total}</div></div>
      <div class="metric"><div class="label">未完成</div><div class="value">${stats.pending}</div></div>
      <div class="metric"><div class="label">已完成</div><div class="value">${stats.completed}</div></div>
      <div class="metric"><div class="label">近14天新增</div><div class="value">${recent}</div></div>
    </div>

    <div class="grid-2">
      <div class="panel"><h3>分类分布（点击可查看任务）</h3>${categoryBars}</div>
      <div class="panel"><h3>四象限分布（点击可查看任务）</h3>${quadrantBars}</div>
    </div>

    <div class="panel" style="margin-top:16px;">
      <h3>近14天新增趋势</h3>
      <div class="trend-chart">${renderTrendSVG(data.trend)}</div>
    </div>
  `;

  el.pageDashboard.querySelectorAll(".bar-item.clickable").forEach((node) => {
    node.addEventListener("click", () => {
      const type = node.dataset.filterType;
      const value = node.dataset.filterValue || "全部";

      state.taskFilters.keyword = "";
      state.taskFilters.sort = "created_desc";
      state.taskFilters.status = "pending";

      if (type === "category") {
        state.taskFilters.category = value;
        state.taskFilters.quadrant = "全部";
        showToast(`已筛选分类：${value}`);
      } else {
        state.taskFilters.category = "全部";
        state.taskFilters.quadrant = value;
        showToast(`已筛选象限：Q${value}`);
      }

      showPage("quadrant");
    });
  });
}

async function renderQuadrant() {
  const page = el.pageQuadrant;
  const categoryNames = getCategoryNames();
  const selectedCategory = categoryNames.includes(state.taskFilters.category) ? state.taskFilters.category : "全部";
  const selectedQuadrant = ["全部", "1", "2", "3", "4"].includes(state.taskFilters.quadrant)
    ? state.taskFilters.quadrant
    : "全部";
  const selectedSort = ["created_desc", "created_asc", "updated_desc", "updated_asc"].includes(state.taskFilters.sort)
    ? state.taskFilters.sort
    : "created_desc";
  const selectedStatus = ["all", "pending", "completed"].includes(state.taskFilters.status)
    ? state.taskFilters.status
    : "pending";

  page.innerHTML = `
    <h1>四象限任务</h1>
    <div class="filters">
      <input id="flt-keyword" placeholder="搜索标题或描述" value="${escapeHtml(state.taskFilters.keyword)}" />
      <select id="flt-category"><option ${selectedCategory === "全部" ? "selected" : ""}>全部</option>${categoryNames
        .map((c) => `<option ${selectedCategory === c ? "selected" : ""}>${escapeHtml(c)}</option>`)
        .join("")}</select>
      <select id="flt-quadrant"><option ${selectedQuadrant === "全部" ? "selected" : ""}>全部</option><option ${selectedQuadrant === "1" ? "selected" : ""}>1</option><option ${selectedQuadrant === "2" ? "selected" : ""}>2</option><option ${selectedQuadrant === "3" ? "selected" : ""}>3</option><option ${selectedQuadrant === "4" ? "selected" : ""}>4</option></select>
      <select id="flt-status">
        <option value="pending" ${selectedStatus === "pending" ? "selected" : ""}>未完成</option>
        <option value="all" ${selectedStatus === "all" ? "selected" : ""}>全部</option>
        <option value="completed" ${selectedStatus === "completed" ? "selected" : ""}>已完成</option>
      </select>
      <select id="flt-sort">
        <option value="created_desc" ${selectedSort === "created_desc" ? "selected" : ""}>最新创建</option>
        <option value="created_asc" ${selectedSort === "created_asc" ? "selected" : ""}>最早创建</option>
        <option value="updated_desc" ${selectedSort === "updated_desc" ? "selected" : ""}>最新更新</option>
        <option value="updated_asc" ${selectedSort === "updated_asc" ? "selected" : ""}>最早更新</option>
      </select>
    </div>
    <div id="quad-board" class="quad-board">
      <span class="quad-label top-left">Q1 重要且紧急</span>
      <span class="quad-label top-right">Q3 紧急不重要</span>
      <span class="quad-label bottom-left">Q2 重要不紧急</span>
      <span class="quad-label bottom-right">Q4 不重要不紧急</span>
    </div>
    <div id="task-list" class="task-list"></div>
  `;

  async function refresh() {
    const keyword = document.getElementById("flt-keyword").value;
    const category = document.getElementById("flt-category").value;
    const quadrant = document.getElementById("flt-quadrant").value;
    const status = document.getElementById("flt-status").value;
    const sort = document.getElementById("flt-sort").value;
    state.taskFilters = { keyword, category, quadrant, status, sort };
    const q = new URLSearchParams({ keyword, category, quadrant, status, sort });
    const data = await api(`/api/tasks?${q.toString()}`);

    const board = document.getElementById("quad-board");
    const list = document.getElementById("task-list");

    board.querySelectorAll(".task-dot").forEach((node) => node.remove());

    data.items.forEach((task) => {
      const [x, y] = quadrantToAxes(task.quadrant);
      const dot = document.createElement("button");
      dot.className = `task-dot q${task.quadrant} ${task.completed ? "is-completed" : ""}`;
      dot.style.left = `${(x + jitter(task.id + "x")) * 100}%`;
      dot.style.bottom = `${(y + jitter(task.id + "y")) * 100}%`;
      dot.title = `${task.title} (${task.category})`;
      dot.addEventListener("click", () => {
        const row = document.getElementById(`task-${task.id}`);
        if (row) row.scrollIntoView({ behavior: "smooth", block: "center" });
      });
      board.appendChild(dot);
    });

    list.innerHTML = data.items.length
      ? data.items
          .map((task) => {
            const categoryInfo = getCategoryByName(task.category);
            const categoryColor = categoryInfo?.color || task.category_color || "#94A3B8";
            return `
            <article class="task-card ${task.completed ? "is-completed" : ""}" id="task-${task.id}">
              <div>
                <div class="task-head">
                  <label class="task-check">
                    <input type="checkbox" data-action="toggle" data-id="${task.id}" ${task.completed ? "checked" : ""} />
                    <span class="task-title">${escapeHtml(task.title)}</span>
                  </label>
                  <span class="category-badge" style="--badge:${escapeHtml(categoryColor)}">${escapeHtml(task.category)}</span>
                </div>
                <div class="task-meta">Q${task.quadrant} | 创建: ${task.created_at} | 更新: ${task.updated_at}</div>
                <p>${escapeHtml(task.description || "")}</p>
              </div>
              <div class="task-actions">
                <button class="btn ghost" data-action="edit" data-id="${task.id}">编辑</button>
                <button class="btn danger" data-action="delete" data-id="${task.id}">删除</button>
              </div>
            </article>
          `;
          })
          .join("")
      : '<div class="empty-state">当前筛选条件下暂无任务。</div>';

    list.querySelectorAll("button[data-action='edit']").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.editId = Number(btn.dataset.id);
        showPage("editor");
      });
    });

    list.querySelectorAll("button[data-action='delete']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const ok = window.confirm("确认删除这个任务吗？");
        if (!ok) return;
        await api(`/api/tasks/${btn.dataset.id}`, { method: "DELETE" });
        showToast("任务已删除");
        refresh();
      });
    });

    list.querySelectorAll("input[data-action='toggle']").forEach((input) => {
      input.addEventListener("change", async () => {
        const taskId = Number(input.dataset.id);
        const checked = input.checked;
        await api(`/api/tasks/${taskId}/status`, {
          method: "PATCH",
          body: JSON.stringify({ completed: checked }),
        });
        showToast(checked ? "任务已标记为完成" : "任务已恢复为未完成");
        refresh();
      });
    });
  }

  ["flt-keyword", "flt-category", "flt-quadrant", "flt-status", "flt-sort"].forEach((id) => {
    document.getElementById(id).addEventListener("input", refresh);
    document.getElementById(id).addEventListener("change", refresh);
  });

  refresh();
}

async function renderEditor() {
  const page = el.pageEditor;
  const categoryNames = getCategoryNames();
  let editing = null;

  if (state.editId) {
    const data = await api("/api/tasks?sort=created_desc&status=all");
    editing = data.items.find((x) => x.id === state.editId) || null;
  }

  if (!categoryNames.length) {
    page.innerHTML = `
      <h1>${editing ? "编辑任务" : "添加任务"}</h1>
      <div class="editor-card">
        <p>请先创建至少一个分类，再添加任务。</p>
        <button class="btn primary" id="go-category-page">前往分类管理</button>
      </div>
    `;
    document.getElementById("go-category-page").addEventListener("click", () => showPage("categories"));
    return;
  }

  page.innerHTML = `
    <h1>${editing ? "编辑任务" : "添加任务"}</h1>
    <div class="editor-card">
      <form id="editor-form" class="form">
        <label>任务标题 <input id="ed-title" required value="${escapeHtml(editing ? editing.title : "")}" /></label>
        <label>任务描述 <textarea id="ed-desc">${escapeHtml(editing ? editing.description : "")}</textarea></label>
        <div class="editor-grid">
          <label>分类
            <select id="ed-category">${categoryNames
              .map((c) => `<option ${editing && editing.category === c ? "selected" : ""}>${escapeHtml(c)}</option>`)
              .join("")}</select>
          </label>
          <label>象限
            <select id="ed-quadrant">
              ${[1, 2, 3, 4]
                .map((q) => `<option value="${q}" ${editing && editing.quadrant === q ? "selected" : ""}>Q${q}</option>`)
                .join("")}
            </select>
          </label>
        </div>
        <div class="task-actions">
          <button class="btn primary" type="submit">保存任务</button>
          <button class="btn ghost" id="cancel-btn" type="button">取消</button>
        </div>
      </form>
    </div>
  `;

  document.getElementById("cancel-btn").addEventListener("click", () => {
    state.editId = null;
    showPage("quadrant");
  });

  document.getElementById("editor-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      title: document.getElementById("ed-title").value,
      description: document.getElementById("ed-desc").value,
      category: document.getElementById("ed-category").value,
      quadrant: Number(document.getElementById("ed-quadrant").value),
    };

    if (state.editId) {
      await api(`/api/tasks/${state.editId}`, { method: "PUT", body: JSON.stringify(payload) });
      showToast("任务已更新");
    } else {
      await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
      showToast("任务已创建");
    }

    state.editId = null;
    showPage("quadrant");
  });
}

async function renderCategories() {
  await loadCategories();
  const page = el.pageCategories;
  const editingCategory = state.categories.find((item) => item.id === state.editingCategoryId) || null;

  page.innerHTML = `
    <h1>分类管理</h1>
    <div class="grid-2 categories-layout">
      <section class="panel">
        <h3>${editingCategory ? "编辑分类" : "新建分类"}</h3>
        <form id="category-form" class="form">
          <label>分类名称 <input id="cat-name" maxlength="20" required value="${escapeHtml(editingCategory?.name || "")}" /></label>
          <label>分类颜色 <input id="cat-color" type="color" value="${escapeHtml(editingCategory?.color || "#006D77")}" /></label>
          <div class="task-actions">
            <button class="btn primary" type="submit">${editingCategory ? "保存分类" : "创建分类"}</button>
            <button class="btn ghost" id="cat-cancel" type="button">取消</button>
          </div>
        </form>
      </section>
      <section class="panel">
        <h3>现有分类</h3>
        <div class="category-list">
          ${state.categories
            .map(
              (item) => `
              <article class="category-row">
                <div class="category-row-main">
                  <span class="category-dot" style="background:${escapeHtml(item.color)}"></span>
                  <div>
                    <strong>${escapeHtml(item.name)}</strong>
                    <div class="task-meta">${escapeHtml(item.color)}</div>
                  </div>
                </div>
                <div class="task-actions">
                  <button class="btn ghost" data-action="edit-category" data-id="${item.id}">编辑</button>
                  <button class="btn danger" data-action="delete-category" data-id="${item.id}">删除</button>
                </div>
              </article>
            `
            )
            .join("")}
        </div>
      </section>
    </div>
  `;

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
      await api(`/api/categories/${state.editingCategoryId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      showToast("分类已更新");
    } else {
      await api("/api/categories", { method: "POST", body: JSON.stringify(payload) });
      showToast("分类已创建");
    }

    state.editingCategoryId = null;
    await loadCategories();
    renderCategories();
  });

  page.querySelectorAll("button[data-action='edit-category']").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.editingCategoryId = Number(btn.dataset.id);
      renderCategories();
    });
  });

  page.querySelectorAll("button[data-action='delete-category']").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ok = window.confirm("确认删除这个分类吗？");
      if (!ok) return;
      await api(`/api/categories/${btn.dataset.id}`, { method: "DELETE" });
      showToast("分类已删除");
      if (state.editingCategoryId === Number(btn.dataset.id)) state.editingCategoryId = null;
      await loadCategories();
      renderCategories();
    });
  });
}

async function bootstrapApp() {
  const me = await api("/api/auth/me");
  state.user = me.user;
  await loadCategories();

  el.userLabel.textContent = `当前用户: ${state.user.username}`;
  el.authView.classList.add("hidden");
  el.appView.classList.remove("hidden");
  showPage(state.page);
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
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => showPage(btn.dataset.page));
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try {
      if (state.token) await api("/api/auth/logout", { method: "POST" });
    } catch (_) {
      // ignore
    }

    state.token = "";
    state.user = null;
    state.editId = null;
    state.editingCategoryId = null;
    localStorage.removeItem("sm_token");
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
