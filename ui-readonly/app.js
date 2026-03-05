const API_BASE = window.location.origin;
const state = {
  items: [],
  selectedId: null,
  mode: "latest", // latest | keyword | vector
  keyword: "",
  page: 1,
  pageSize: 10,
  total: 0,
  sortBy: "updated_at",
  sortDir: "desc",
  statusFilter: "1",
};

function el(id) {
  return document.getElementById(id);
}

function fmtTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function snippet(text, max = 50) {
  if (!text) return "-";
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function statusText(status) {
  const mapping = {
    0: "草稿",
    1: "已发布",
    2: "退役",
    3: "废弃",
    4: "其他",
  };
  return mapping[Number(status)] || `状态${status}`;
}

function buildStatusFilterPayload() {
  const selected = state.statusFilter;
  if (selected === "all") {
    return { status: null, is_latest: null };
  }
  const status = Number(selected);
  return {
    status,
    is_latest: status === 1 ? true : false,
  };
}

async function fetchJson(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`请求失败(${resp.status}) ${text}`);
  }
  return resp.json();
}

async function loadApiVersion() {
  try {
    const data = await fetchJson(`${API_BASE}/openapi.json`);
    el("apiVersion").textContent = `API 版本：${data?.info?.version || "unknown"}`;
  } catch (err) {
    el("apiVersion").textContent = `API 版本：读取失败（${err.message}）`;
  }
}

function setStatus(text) {
  el("statusBar").textContent = text;
}

function renderStatusStats(stats) {
  const node = el("statusStats");
  if (!stats) {
    node.innerHTML = "";
    return;
  }
  const counts = stats.counts || {};
  const items = [
    ["总量", stats.total ?? 0],
    ["已发布", counts.published ?? 0],
    ["草稿", counts.draft ?? 0],
    ["退役", counts.retired ?? 0],
    ["废弃", counts.deprecated ?? 0],
    ["其他", counts.other ?? 0],
  ];
  node.innerHTML = items
    .map(([label, value]) => `<div class="status-stat-item">${label}<strong>${value}</strong></div>`)
    .join("");
}

async function loadStatusStats() {
  const params = new URLSearchParams();
  if (state.keyword) {
    params.set("keyword", state.keyword);
  }
  const data = await fetchJson(`${API_BASE}/api/v1/standards/readonly/stats?${params.toString()}`);
  renderStatusStats(data);
}

function renderSortIndicators() {
  const sortButtons = document.querySelectorAll(".sort-btn");
  for (const btn of sortButtons) {
    const field = btn.dataset.field;
    const label = btn.dataset.label || btn.textContent.replace(/[↑↓]/g, "");
    btn.dataset.label = label;
    if (field === state.sortBy) {
      btn.classList.add("active");
      btn.textContent = `${label}${state.sortDir === "asc" ? " ↑" : " ↓"}`;
    } else {
      btn.classList.remove("active");
      btn.textContent = label;
    }
  }
}

function renderTable(items) {
  const tbody = el("standardTableBody");
  tbody.innerHTML = "";
  for (const item of items) {
    const tr = document.createElement("tr");
    if (item.id === state.selectedId) {
      tr.classList.add("active");
    }
    tr.innerHTML = `
      <td>${item.code}</td>
      <td>${item.name || "-"}</td>
      <td>${snippet(item.description)}</td>
      <td>${fmtTime(item.created_at)}</td>
      <td>${fmtTime(item.updated_at)}</td>
      <td>v${item.version}${item.is_latest ? " (latest)" : ""}</td>
      <td><span class="status-badge status-${item.status}">${statusText(item.status)}</span></td>
      <td>${item.has_code_list ? "是" : "否"}</td>
    `;
    tr.addEventListener("click", () => onRowClick(item.id));
    tbody.appendChild(tr);
  }
}

function renderPager() {
  const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
  el("pageInfo").textContent = `第 ${state.page} / ${totalPages} 页`;

  const prevBtn = el("prevPageBtn");
  const nextBtn = el("nextPageBtn");
  if (state.mode === "vector") {
    prevBtn.disabled = true;
    nextBtn.disabled = true;
    return;
  }
  prevBtn.disabled = state.page <= 1;
  nextBtn.disabled = state.page >= totalPages;
}

async function loadReadonlyList() {
  const params = new URLSearchParams({
    page: String(state.page),
    page_size: String(state.pageSize),
    order_by: state.sortBy,
    order_dir: state.sortDir,
  });
  if (state.statusFilter !== "all") {
    params.set("status", state.statusFilter);
    // 发布状态默认只看最新；其他状态默认看非最新历史，便于过滤展示
    params.set("is_latest", state.statusFilter === "1" ? "true" : "false");
  }
  if (state.mode === "keyword" && state.keyword) {
    params.set("keyword", state.keyword);
  }
  const data = await fetchJson(`${API_BASE}/api/v1/standards/readonly/list?${params.toString()}`);
  state.items = data.items || [];
  state.total = data.total || 0;
  state.selectedId = null;
  renderSortIndicators();
  renderTable(state.items);
  renderPager();
  if (state.mode === "latest") {
    setStatus(`默认最新记录：共 ${state.total} 条，当前展示 ${state.items.length} 条`);
  } else {
    setStatus(
      `关键词搜索：${state.keyword}，状态=${el("statusFilter").selectedOptions[0]?.text || "全部"}，命中 ${state.total} 条，当前展示 ${state.items.length} 条`
    );
  }
  await loadStatusStats();
  renderEmptyDetail();
}

function sortVectorItemsInPlace() {
  const factor = state.sortDir === "asc" ? 1 : -1;
  const getter = (item) => {
    if (state.sortBy === "created_at" || state.sortBy === "updated_at") {
      return item[state.sortBy] ? new Date(item[state.sortBy]).getTime() : 0;
    }
    if (state.sortBy === "version") {
      return Number(item.version || 0);
    }
    return String(item[state.sortBy] || "").toLowerCase();
  };
  state.items.sort((a, b) => {
    const av = getter(a);
    const bv = getter(b);
    if (av < bv) return -1 * factor;
    if (av > bv) return 1 * factor;
    return 0;
  });
}

async function loadLatest() {
  state.mode = "latest";
  state.keyword = "";
  state.statusFilter = "1";
  state.page = 1;
  el("statusFilter").value = "1";
  await loadReadonlyList();
}

async function keywordSearch() {
  const query = el("searchInput").value.trim();
  if (!query) {
    await loadLatest();
    return;
  }
  state.mode = "keyword";
  state.keyword = query;
  state.statusFilter = el("statusFilter").value;
  state.page = 1;
  await loadReadonlyList();
}

async function vectorSearch() {
  const query = el("searchInput").value.trim();
  if (!query) {
    setStatus("请先输入向量搜索关键词");
    return;
  }
  const statusFilter = buildStatusFilterPayload();
  const payload = {
    query,
    lang: "zh",
    use_vector: true,
    top_k: 10,
    status: statusFilter.status,
    is_latest: statusFilter.is_latest,
  };
  const data = await fetchJson(`${API_BASE}/api/v1/standards/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.mode = "vector";
  state.keyword = query;
  state.page = 1;
  state.total = (data.items || []).length;
  state.selectedId = null;
  state.items = data.items || [];
  const localStats = { draft: 0, published: 0, retired: 0, deprecated: 0, other: 0 };
  for (const item of state.items) {
    if (item.status === 0) localStats.draft += 1;
    else if (item.status === 1) localStats.published += 1;
    else if (item.status === 2) localStats.retired += 1;
    else if (item.status === 3) localStats.deprecated += 1;
    else localStats.other += 1;
  }
  sortVectorItemsInPlace();
  renderSortIndicators();
  renderTable(state.items);
  renderPager();
  setStatus(`向量搜索：${query}，返回 ${state.items.length} 条`);
  renderStatusStats({ total: state.items.length, counts: localStats });
  renderEmptyDetail();
}

function renderEmptyDetail() {
  el("detailEmpty").classList.remove("hidden");
  el("detailContent").classList.add("hidden");
  el("detailContent").innerHTML = "";
}

function renderDetail(detail, codeListDetail) {
  const detailNode = el("detailContent");
  const codeListHtml = codeListDetail
    ? `
      <div class="code-list-card">
        <h3 class="code-list-title">关联标准代码：${codeListDetail.list_code} - ${codeListDetail.name}</h3>
        <div class="detail-grid">
          <div><div class="label">用途</div><div class="value">${codeListDetail.purpose || "-"}</div></div>
          <div><div class="label">版本</div><div class="value">v${codeListDetail.version}</div></div>
          <div><div class="label">状态</div><div class="value">${codeListDetail.status}</div></div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>标准代码</th>
                <th>标准代码名称</th>
                <th>代码含义</th>
                <th>排序</th>
              </tr>
            </thead>
            <tbody>
              ${(codeListDetail.items || [])
                .map(
                  (it) => `
                <tr>
                  <td>${it.item_code}</td>
                  <td>${it.item_name}</td>
                  <td>${it.meaning || "-"}</td>
                  <td>${it.sort_order}</td>
                </tr>
              `
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `
    : `<div class="code-list-card"><div class="empty">该数据标准未绑定标准代码</div></div>`;

  detailNode.innerHTML = `
    <div class="detail-grid">
      <div><div class="label">标准编码</div><div class="value">${detail.code}</div></div>
      <div><div class="label">名称</div><div class="value">${detail.name}</div></div>
      <div><div class="label">状态</div><div class="value">${detail.status}</div></div>
      <div><div class="label">版本</div><div class="value">v${detail.version}${detail.is_latest ? " (latest)" : ""}</div></div>
      <div><div class="label">创建时间</div><div class="value">${fmtTime(detail.created_at)}</div></div>
      <div><div class="label">最近修改</div><div class="value">${fmtTime(detail.updated_at)}</div></div>
      <div style="grid-column: 1/-1;">
        <div class="label">描述</div>
        <div class="value">${detail.description || "-"}</div>
      </div>
    </div>
    ${codeListHtml}
  `;
  el("detailEmpty").classList.add("hidden");
  detailNode.classList.remove("hidden");
}

async function onRowClick(standardId) {
  try {
    state.selectedId = standardId;
    renderTable(state.items);
    const detail = await fetchJson(`${API_BASE}/api/v1/standards/${standardId}?lang=zh`);
    let codeListDetail = null;
    if (detail.code_list && detail.code_list.id) {
      codeListDetail = await fetchJson(`${API_BASE}/api/v1/code-lists/${detail.code_list.id}?include_items=true`);
    }
    renderDetail(detail, codeListDetail);
  } catch (err) {
    setStatus(`加载详情失败：${err.message}`);
  }
}

function bindEvents() {
  el("keywordBtn").addEventListener("click", async () => {
    try {
      await keywordSearch();
    } catch (err) {
      setStatus(`关键词搜索失败：${err.message}`);
    }
  });
  el("vectorBtn").addEventListener("click", async () => {
    try {
      await vectorSearch();
    } catch (err) {
      setStatus(`向量搜索失败：${err.message}`);
    }
  });
  el("resetBtn").addEventListener("click", async () => {
    el("searchInput").value = "";
    try {
      await loadLatest();
    } catch (err) {
      setStatus(`重置失败：${err.message}`);
    }
  });
  el("prevPageBtn").addEventListener("click", async () => {
    if (state.page <= 1 || state.mode === "vector") return;
    state.page -= 1;
    try {
      await loadReadonlyList();
    } catch (err) {
      setStatus(`翻页失败：${err.message}`);
    }
  });
  el("nextPageBtn").addEventListener("click", async () => {
    if (state.mode === "vector") return;
    const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
    if (state.page >= totalPages) return;
    state.page += 1;
    try {
      await loadReadonlyList();
    } catch (err) {
      setStatus(`翻页失败：${err.message}`);
    }
  });
  document.querySelectorAll(".sort-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const field = btn.dataset.field;
      if (!field) return;
      if (state.sortBy === field) {
        state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
      } else {
        state.sortBy = field;
        state.sortDir = field === "code" || field === "name" ? "asc" : "desc";
      }
      state.page = 1;
      try {
        if (state.mode === "vector") {
          sortVectorItemsInPlace();
          renderSortIndicators();
          renderTable(state.items);
          renderPager();
        } else {
          await loadReadonlyList();
        }
      } catch (err) {
        setStatus(`排序失败：${err.message}`);
      }
    });
  });
  el("statusFilter").addEventListener("change", async () => {
    state.statusFilter = el("statusFilter").value;
    state.page = 1;
    try {
      if (state.mode === "vector" && state.keyword) {
        await vectorSearch();
      } else if (state.mode === "keyword") {
        await keywordSearch();
      } else {
        await loadReadonlyList();
      }
    } catch (err) {
      setStatus(`状态过滤失败：${err.message}`);
    }
  });
}

async function init() {
  bindEvents();
  await loadApiVersion();
  try {
    await loadLatest();
  } catch (err) {
    setStatus(`初始化失败：${err.message}`);
  }
}

init();
