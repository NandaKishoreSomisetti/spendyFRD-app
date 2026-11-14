/* spendyFRD frontend: talks to the Python API at /api. No framework, no build step. */
"use strict";

// Normally served by FastAPI (same origin). Via VS Code Live Server (:5500) → API on :8000.
const API = location.port === "5500" ? "http://localhost:8000/api" : "/api";
const UNDO_MS = 5000;

const $ = (sel) => document.querySelector(sel);
const state = {
  transactions: [],
  categories: [],
  type: "",          // "", "debit", "credit"
  category: null,    // category filter from the bars
  q: "",
  pendingDeletes: new Map(), // id -> timeout handle
};

// ---------------------------------------------------------------- helpers
const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const fmtMoney = (n) => money.format(n);
const localeFor = () => ({ en: "en-IN", te: "te-IN", hi: "hi-IN" }[currentLang] || "en-IN");
const fmtDate = (iso) => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(localeFor(), { day: "2-digit", month: "short", year: "numeric" });
};
const todayISO = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(API + path, options);
  } catch (_) {
    throw new Error(t("serverDown"));
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : t("invalidEntry");
    } catch (_) { /* not json */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

let toastTimer;
function toast(message, { error = false, actionLabel, onAction, duration = 3500 } = {}) {
  const el = $("#toast");
  const btn = $("#toastAction");
  $("#toastText").textContent = message;
  el.classList.toggle("err", error);
  btn.hidden = !actionLabel;
  btn.textContent = actionLabel || "";
  btn.onclick = () => { el.hidden = true; onAction?.(); };
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, duration);
}

// ---------------------------------------------------------------- data
async function loadAll() {
  try {
    state.transactions = await api("/transactions");
  } catch (err) {
    toast(err.message, { error: true, duration: 8000 });
    state.transactions = [];
  }
  render();
}

const visibleAll = () => state.transactions.filter((tx) => !state.pendingDeletes.has(tx.id));

function filtered() {
  const q = state.q.trim().toLowerCase();
  return visibleAll().filter((tx) =>
    (!state.type || tx.type === state.type) &&
    (!state.category || tx.category === state.category) &&
    (!q || tx.description.toLowerCase().includes(q) ||
      tx.category.toLowerCase().includes(q) || categoryLabel(tx.category).toLowerCase().includes(q) ||
      String(tx.amount).includes(q))
  );
}

// ---------------------------------------------------------------- render
function render() {
  renderSummary();
  renderBars();
  renderTable();
}

function renderSummary() {
  const txs = visibleAll();
  const income = txs.filter((x) => x.type === "credit").reduce((s, x) => s + x.amount, 0);
  const spent = txs.filter((x) => x.type === "debit").reduce((s, x) => s + x.amount, 0);
  const net = income - spent;
  $("#summarySection").hidden = txs.length === 0;
  $("#statIncome").textContent = fmtMoney(income);
  $("#statSpent").textContent = fmtMoney(spent);
  const bal = $("#statBalance");
  bal.textContent = fmtMoney(net);
  bal.className = `stat-value ${net >= 0 ? "pos" : "neg"}`;
  $("#statNote").textContent = !income ? "" :
    net >= 0 ? t("savedOf", { p: Math.round((net / income) * 100) }) : t("overBy", { a: fmtMoney(-net) });
}

function renderBars() {
  const totals = new Map();
  let spent = 0;
  for (const tx of visibleAll()) {
    if (tx.type !== "debit") continue;
    totals.set(tx.category, (totals.get(tx.category) || 0) + tx.amount);
    spent += tx.amount;
  }
  const rows = [...totals.entries()].sort((a, b) => b[1] - a[1]);
  $("#categorySection").hidden = rows.length === 0;
  const max = rows[0]?.[1] || 1;
  const list = $("#categoryBars");
  list.replaceChildren(...rows.map(([cat, total]) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `bar-btn${state.category === cat ? " active" : ""}`;
    btn.setAttribute("aria-pressed", String(state.category === cat));
    btn.innerHTML = `
      <span class="bar-name"></span>
      <span class="bar-amt"></span>
      <span class="bar-track"><span class="bar-fill"></span></span>`;
    btn.querySelector(".bar-name").textContent = categoryLabel(cat);
    btn.querySelector(".bar-amt").textContent = fmtMoney(total);
    const pct = document.createElement("small");
    pct.textContent = `${Math.round((total / spent) * 100)}%`;
    btn.querySelector(".bar-amt").append(pct);
    btn.querySelector(".bar-fill").style.width = `${(total / max) * 100}%`;
    btn.addEventListener("click", () => setCategoryFilter(state.category === cat ? null : cat));
    li.append(btn);
    return li;
  }));
}

function renderTable() {
  const all = visibleAll();
  const rows = filtered();
  $("#txCount").textContent = all.length ? `(${rows.length === all.length ? all.length : `${rows.length}/${all.length}`})` : "";
  ["#pdfBtn", "#csvBtn", "#clearBtn"].forEach((s) => { $(s).disabled = all.length === 0; });

  const chip = $("#categoryChip");
  chip.hidden = !state.category;
  chip.textContent = state.category ? categoryLabel(state.category) : "";

  const empty = $("#emptyState");
  empty.hidden = rows.length > 0;
  $("#emptyTitle").textContent = all.length ? t("noMatches") : t("emptyTitle");
  $("#emptyHint").textContent = all.length ? "" : t("emptyHint");
  document.querySelector(".table-wrap").hidden = rows.length === 0;

  $("#txBody").replaceChildren(...rows.map(rowFor));
}

function rowFor(tx) {
  const tr = document.createElement("tr");

  const date = document.createElement("td");
  date.className = "td-date";
  date.textContent = fmtDate(tx.date);

  const desc = document.createElement("td");
  desc.className = "td-desc";
  desc.textContent = tx.description;
  desc.title = tx.description;
  const descDate = document.createElement("small"); // shown under the description on phones
  descDate.textContent = fmtDate(tx.date);
  desc.append(descDate);

  const catTd = document.createElement("td");
  catTd.className = "td-cat";
  const select = document.createElement("select");
  select.className = "cat-select";
  select.setAttribute("aria-label", t("colCategory"));
  const options = tx.type === "credit" ? ["Income"] : state.categories.filter((c) => c !== "Income");
  for (const c of options) select.add(new Option(categoryLabel(c), c, false, c === tx.category));
  select.disabled = tx.type === "credit";
  select.addEventListener("change", () => changeCategory(tx, select.value));
  catTd.append(select);

  const amt = document.createElement("td");
  amt.className = `num ${tx.type === "credit" ? "pos" : ""}`;
  amt.textContent = `${tx.type === "credit" ? "+" : "−"}${fmtMoney(tx.amount)}`;

  const delTd = document.createElement("td");
  delTd.className = "td-del";
  const del = document.createElement("button");
  del.type = "button";
  del.className = "del-btn";
  del.setAttribute("aria-label", t("deleteRow"));
  del.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/></svg>';
  del.addEventListener("click", () => deleteWithUndo(tx.id));
  delTd.append(del);

  tr.append(date, desc, catTd, amt, delTd);
  return tr;
}

function setCategoryFilter(cat) {
  state.category = cat;
  render();
}

// ---------------------------------------------------------------- actions
async function uploadFiles(fileList) {
  const files = [...fileList];
  if (!files.length) return;
  const results = $("#uploadResults");
  const zone = $("#dropZone");
  results.replaceChildren(...files.map((f) => {
    const li = document.createElement("li");
    li.className = "info";
    li.textContent = t("reading", { name: f.name });
    return li;
  }));
  zone.classList.add("busy");

  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  try {
    const res = await api("/upload", { method: "POST", body: form });
    results.replaceChildren(...res.files.map((f) => {
      const li = document.createElement("li");
      if (f.error && !f.imported) {
        li.className = "err";
        li.textContent = `${f.filename}: ${f.error}`;
      } else {
        li.textContent = t("fileImported", { name: f.filename, n: f.imported }) +
          (f.duplicates ? ` · ${t("fileDupes", { n: f.duplicates })}` : "");
      }
      return li;
    }));
    await loadAll();
  } catch (err) {
    const li = document.createElement("li");
    li.className = "err";
    li.textContent = err.message || t("uploadFailed");
    results.replaceChildren(li);
  } finally {
    zone.classList.remove("busy");
    $("#fileInput").value = "";
  }
}

async function changeCategory(tx, category) {
  try {
    await api(`/transactions/${tx.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category }),
    });
    toast(t("categoryChanged"));
    await loadAll(); // other rows from the same merchant may have changed too
  } catch (err) {
    toast(err.message, { error: true });
    render();
  }
}

function deleteWithUndo(id) {
  const commit = () => {
    state.pendingDeletes.delete(id);
    api(`/transactions/${id}`, { method: "DELETE" })
      .then(() => { state.transactions = state.transactions.filter((x) => x.id !== id); })
      .catch((err) => { toast(err.message, { error: true }); render(); });
  };
  state.pendingDeletes.set(id, setTimeout(commit, UNDO_MS));
  render();
  toast(t("deleted"), {
    actionLabel: t("undo"),
    duration: UNDO_MS,
    onAction: () => {
      clearTimeout(state.pendingDeletes.get(id));
      state.pendingDeletes.delete(id);
      render();
    },
  });
}

// Don't lose pending deletes if the tab closes during the undo window.
window.addEventListener("pagehide", () => {
  for (const [id, handle] of state.pendingDeletes) {
    clearTimeout(handle);
    fetch(`${API}/transactions/${id}`, { method: "DELETE", keepalive: true });
  }
  state.pendingDeletes.clear();
});

async function submitEntry(e) {
  e.preventDefault();
  const form = e.target;
  const data = new FormData(form);
  const description = String(data.get("description") || "").trim();
  const amount = parseFloat(data.get("amount"));
  if (!description || !(amount > 0)) {
    toast(t("invalidEntry"), { error: true });
    return;
  }
  const body = {
    description,
    amount,
    type: data.get("type"),
    date: data.get("date") || null,
  };
  if (body.type === "debit" && data.get("category")) body.category = data.get("category");
  try {
    const tx = await api("/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    toast(t("added", { d: tx.description, c: categoryLabel(tx.category) }));
    form.reset();
    form.date.value = todayISO();
    syncEntryCategory();
    form.description.focus();
    await loadAll();
  } catch (err) {
    toast(err.message, { error: true });
  }
}

function download(path) {
  if (!visibleAll().length) { toast(t("noDataReport")); return; }
  const a = document.createElement("a");
  a.href = API + path;
  a.download = "";
  document.body.append(a);
  a.click();
  a.remove();
}

async function clearAll() {
  if (!confirm(t("confirmClear"))) return;
  try {
    await api("/transactions", { method: "DELETE" });
    state.category = null;
    $("#uploadResults").replaceChildren();
    await loadAll();
  } catch (err) {
    toast(err.message, { error: true });
  }
}

// ---------------------------------------------------------------- entry form
function fillEntryCategories() {
  const sel = $("#entryCategory");
  const current = sel.value;
  sel.replaceChildren(new Option(t("autoCategory"), ""));
  state.categories.filter((c) => c !== "Income").forEach((c) => sel.add(new Option(categoryLabel(c), c)));
  sel.value = current;
}

function syncEntryCategory() {
  const isCredit = $("#entryForm").type.value === "credit";
  const sel = $("#entryCategory");
  sel.disabled = isCredit;
  if (isCredit) sel.value = "";
}

function toggleEntryForm(open) {
  const form = $("#entryForm");
  const btn = $("#addEntryBtn");
  form.hidden = !open;
  btn.setAttribute("aria-expanded", String(open));
  if (open) {
    if (!form.date.value) form.date.value = todayISO();
    form.description.focus();
  }
}

// ---------------------------------------------------------------- theme & language
function toggleTheme() {
  const root = document.documentElement;
  const isDark = root.dataset.theme
    ? root.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = isDark ? "light" : "dark";
  try { localStorage.setItem("spendyfrd_theme", root.dataset.theme); } catch (_) { /* ignore */ }
}

// ---------------------------------------------------------------- wire up
async function init() {
  await initI18n();
  applyTranslations();
  $("#langSelect").value = currentLang;
  $("#langSelect").addEventListener("change", async (e) => {
    await setLanguage(e.target.value);
    fillEntryCategories();
    render();
  });
  $("#themeBtn").addEventListener("click", toggleTheme);

  // file input & drag-drop
  const zone = $("#dropZone");
  $("#fileInput").addEventListener("change", (e) => uploadFiles(e.target.files));
  ["dragenter", "dragover"].forEach((ev) => zone.addEventListener(ev, (e) => {
    e.preventDefault();
    zone.classList.add("over");
  }));
  ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, (e) => {
    e.preventDefault();
    zone.classList.remove("over");
  }));
  zone.addEventListener("drop", (e) => uploadFiles(e.dataTransfer.files));
  // dropping a file anywhere else shouldn't navigate away
  ["dragover", "drop"].forEach((ev) => window.addEventListener(ev, (e) => e.preventDefault()));

  // entry form
  $("#addEntryBtn").addEventListener("click", () => toggleEntryForm($("#entryForm").hidden));
  $("#cancelEntryBtn").addEventListener("click", () => toggleEntryForm(false));
  $("#entryForm").addEventListener("submit", submitEntry);
  $("#entryForm").addEventListener("change", (e) => { if (e.target.name === "type") syncEntryCategory(); });

  // filters
  let searchTimer;
  $("#searchInput").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.q = e.target.value; renderTable(); }, 120);
  });
  $("#typeFilter").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-type]");
    if (!btn) return;
    state.type = btn.dataset.type;
    $("#typeFilter").querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
    renderTable();
  });
  $("#categoryChip").addEventListener("click", () => setCategoryFilter(null));

  // exports
  $("#pdfBtn").addEventListener("click", () => download(`/report.pdf?lang=${currentLang}`));
  $("#csvBtn").addEventListener("click", () => download("/export.csv"));
  $("#clearBtn").addEventListener("click", clearAll);

  api("/categories")
    .then((cats) => { state.categories = cats; fillEntryCategories(); })
    .catch(() => {})
    .finally(loadAll);
}

init();
