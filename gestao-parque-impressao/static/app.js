const statusOptions = ["Aberta", "Em atendimento", "Aguardando peça", "Concluída", "Cancelada"];
const priorityOptions = ["Baixa", "Normal", "Alta", "Urgente"];
const viewTitles = {
  dashboard: ["PAINEL DE CONTROLE", "Visão geral"],
  orders: ["ATENDIMENTO", "Ordens de serviço"],
  stock: ["MATERIAIS", "Estoque"],
  assistant: ["APOIO À OPERAÇÃO", "Assistente"],
  data: ["DADOS", "Importar / exportar"],
};
let toastTimer;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) },
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) throw new Error(body.error || "Não foi possível concluir a solicitação.");
  return body;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function showToast(message, isError = false) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3200);
}

function setFeedback(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function money(value) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value || 0);
}

function dateLabel(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("pt-BR");
}

function statusClass(status) {
  if (status === "Aberta") return "open";
  if (status === "Em atendimento") return "progress";
  if (status === "Aguardando peça") return "waiting";
  if (status === "Concluída") return "done";
  return "danger";
}

function options(items, selected, placeholder = "") {
  const first = placeholder ? `<option value="">${escapeHtml(placeholder)}</option>` : "";
  return first + items.map((item) => {
    const value = typeof item === "object" ? item.id : item;
    const label = typeof item === "object" ? item.name : item;
    return `<option value="${escapeHtml(value)}" ${String(value) === String(selected) ? "selected" : ""}>${escapeHtml(label)}</option>`;
  }).join("");
}

function renderDashboard(dashboard) {
  document.querySelector("#metric-orders").textContent = dashboard.open_work_orders;
  document.querySelector("#metric-stock").textContent = dashboard.stock_units;
  document.querySelector("#metric-usage").textContent = dashboard.monthly_consumption;
  document.querySelector("#metric-value").textContent = money(dashboard.inventory_value);
  const lowStock = document.querySelector("#dashboard-low-stock");
  lowStock.innerHTML = dashboard.low_stock.length ? `
    <table><thead><tr><th>Toner</th><th>Saldo</th><th>Mínimo</th></tr></thead><tbody>
      ${dashboard.low_stock.map((item) => `<tr><td><strong>${escapeHtml(item.name)}</strong><br><small>${escapeHtml(item.sku)}</small></td><td class="${item.quantity === 0 ? "low" : ""}">${item.quantity}</td><td>${item.min_stock}</td></tr>`).join("")}
    </tbody></table>` : '<div class="empty-row">Nenhum toner no nível mínimo.</div>';
  const recent = document.querySelector("#dashboard-orders");
  recent.innerHTML = dashboard.recent_work_orders.length ? dashboard.recent_work_orders.map((order) => `
    <div class="recent-item"><span class="recent-initial">${escapeHtml((order.client_name || "?").slice(0, 1).toUpperCase())}</span>
    <div class="recent-info"><strong>OS #${order.id} · ${escapeHtml(order.client_name)}</strong><small>${escapeHtml(order.equipment)} · ${dateLabel(order.opened_at)}</small></div>
    <span class="pill ${statusClass(order.status)}">${escapeHtml(order.status)}</span></div>`).join("") : '<div class="empty-row">Nenhuma OS cadastrada ainda.</div>';
}

function renderClients(clients) {
  const select = document.querySelector("#order-client");
  const selected = select.value;
  select.innerHTML = options(clients.map((client) => ({ id: client.id, name: client.name })), selected, "Selecione um cliente");
}

function renderToners(toners) {
  document.querySelectorAll(".toner-select").forEach((select) => {
    const selected = select.value;
    select.innerHTML = options(toners.map((toner) => ({ id: toner.id, name: `${toner.sku} — ${toner.name}` })), selected, "Selecione um toner");
  });
  const table = document.querySelector("#stock-table");
  table.innerHTML = toners.length ? toners.map((toner) => {
    const state = toner.quantity === 0 ? ["Sem estoque", "empty"] : toner.quantity <= toner.min_stock ? ["Repor", "warning"] : ["Normal", "ok"];
    return `<tr><td><strong>${escapeHtml(toner.sku)}</strong></td><td>${escapeHtml(toner.name)}</td><td class="${state[1] === "empty" ? "low" : ""}">${toner.quantity}</td><td>${toner.min_stock}</td><td>${money(toner.inventory_value)}</td><td><span class="stock-state ${state[1]}">${state[0]}</span></td></tr>`;
  }).join("") : '<tr><td class="empty-row" colspan="6">Cadastre o primeiro toner para começar.</td></tr>';
}

function renderOrders(orders) {
  const table = document.querySelector("#orders-table");
  table.innerHTML = orders.length ? orders.map((order) => `
    <tr data-order-row="${order.id}">
      <td><span class="order-primary">#${order.id} · ${escapeHtml(order.client_name)}</span><span class="order-secondary">${dateLabel(order.opened_at)}</span></td>
      <td><span class="order-primary">${escapeHtml(order.equipment)}</span><span class="order-secondary" title="${escapeHtml(order.issue)}">${escapeHtml(order.issue)}</span></td>
      <td><select data-field="priority" aria-label="Prioridade da OS ${order.id}">${options(priorityOptions, order.priority)}</select></td>
      <td><select data-field="status" aria-label="Status da OS ${order.id}">${options(statusOptions, order.status)}</select><span class="order-secondary"><span class="pill ${statusClass(order.status)}">${escapeHtml(order.status)}</span></span></td>
      <td><textarea data-field="resolution" aria-label="Solução da OS ${order.id}" placeholder="Registrar solução">${escapeHtml(order.resolution)}</textarea></td>
      <td><button class="button secondary" data-save-order="${order.id}" type="button">Salvar</button></td>
    </tr>`).join("") : '<tr><td class="empty-row" colspan="6">Nenhuma ordem registrada. Abra a primeira acima.</td></tr>';
}

function renderWorkOrderSelect(orders) {
  const active = orders.filter((order) => order.status !== "Concluída" && order.status !== "Cancelada");
  const select = document.querySelector("#consume-order");
  const selected = select.value;
  select.innerHTML = options(active.map((order) => ({ id: order.id, name: `OS #${order.id} — ${order.client_name}` })), selected, "Sem OS vinculada");
}

async function refresh() {
  try {
    const [dashboard, clients, toners, orders] = await Promise.all([
      api("/api/dashboard"), api("/api/clients"), api("/api/toners"), api("/api/work-orders"),
    ]);
    renderDashboard(dashboard);
    renderClients(clients);
    renderToners(toners);
    renderOrders(orders);
    renderWorkOrderSelect(orders);
  } catch (error) {
    showToast(error.message, true);
  }
}

async function postForm(form, path, feedback, transform = (data) => data, successMessage = "Salvo com sucesso.") {
  const button = form.querySelector("button[type='submit']");
  const oldText = button.textContent;
  button.disabled = true;
  setFeedback(feedback, "");
  try {
    const values = Object.fromEntries(new FormData(form));
    await api(path, { method: "POST", body: JSON.stringify(transform(values)) });
    form.reset();
    setFeedback(feedback, successMessage);
    showToast(successMessage);
    await refresh();
  } catch (error) {
    setFeedback(feedback, error.message, true);
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    if (button.textContent !== oldText) button.textContent = oldText;
  }
}

function showView(name) {
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${name}`));
  document.querySelectorAll(".nav-link").forEach((link) => link.classList.toggle("active", link.dataset.view === name));
  const [eyebrow, title] = viewTitles[name] || viewTitles.dashboard;
  document.querySelector("#page-eyebrow").textContent = eyebrow;
  document.querySelector("#page-title").textContent = title;
  if (name === "dashboard" || name === "stock" || name === "orders") refresh();
}

document.querySelectorAll(".nav-link").forEach((button) => button.addEventListener("click", () => showView(button.dataset.view)));
document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.go)));

document.querySelector("#client-form").addEventListener("submit", (event) => {
  event.preventDefault();
  postForm(event.currentTarget, "/api/clients", document.querySelector("#order-feedback"), (data) => data, "Cliente cadastrado.");
});

document.querySelector("#order-form").addEventListener("submit", (event) => {
  event.preventDefault();
  postForm(event.currentTarget, "/api/work-orders", document.querySelector("#order-feedback"), (data) => ({ ...data, client_id: Number(data.client_id) }), "Ordem de serviço criada.");
});

document.querySelector("#toner-form").addEventListener("submit", (event) => {
  event.preventDefault();
  postForm(event.currentTarget, "/api/toners", document.querySelector("#toner-feedback"), (data) => ({ ...data, min_stock: Number(data.min_stock) }), "Toner cadastrado.");
});

document.querySelector("#receipt-form").addEventListener("submit", (event) => {
  event.preventDefault();
  postForm(event.currentTarget, "/api/stock/receipts", document.querySelector("#receipt-feedback"), (data) => ({
    ...data, toner_id: Number(data.toner_id), quantity: Number(data.quantity), cost_per_unit: Number(data.cost_per_unit),
  }), "Entrada de estoque registrada.");
});

document.querySelector("#consume-form").addEventListener("submit", (event) => {
  event.preventDefault();
  postForm(event.currentTarget, "/api/stock/consume", document.querySelector("#consume-feedback"), (data) => ({
    ...data, toner_id: Number(data.toner_id), quantity: Number(data.quantity), work_order_id: data.work_order_id ? Number(data.work_order_id) : null,
  }), "Baixa FIFO registrada.");
});

document.querySelector("#orders-table").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-save-order]");
  if (!button) return;
  const row = button.closest("[data-order-row]");
  button.disabled = true;
  try {
    await api(`/api/work-orders/${button.dataset.saveOrder}`, {
      method: "PATCH",
      body: JSON.stringify({
        status: row.querySelector('[data-field="status"]').value,
        priority: row.querySelector('[data-field="priority"]').value,
        resolution: row.querySelector('[data-field="resolution"]').value,
      }),
    });
    showToast("Ordem atualizada.");
    await refresh();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#assistant-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = document.querySelector("#assistant-question").value;
  const button = event.currentTarget.querySelector("button[type='submit']");
  button.disabled = true;
  try {
    const result = await api("/api/assistant", { method: "POST", body: JSON.stringify({ question }) });
    document.querySelector("#assistant-answer").textContent = result.answer;
    document.querySelector("#assistant-answer-panel").hidden = false;
    document.querySelector("#assistant-details").textContent = "";
    document.querySelector("#assistant-answer-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
  }
});

document.querySelectorAll("[data-question]").forEach((button) => button.addEventListener("click", () => {
  document.querySelector("#assistant-question").value = button.dataset.question;
  document.querySelector("#assistant-question").focus();
}));

document.querySelector("#import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const feedback = document.querySelector("#import-feedback");
  const button = form.querySelector("button[type='submit']");
  const file = form.elements.file.files[0];
  if (!file) return;
  button.disabled = true;
  setFeedback(feedback, "Validando arquivo…");
  try {
    const resource = form.elements.resource.value;
    const result = await api(`/api/import/${resource}`, { method: "POST", body: JSON.stringify({ csv: await file.text() }) });
    form.reset();
    setFeedback(feedback, `${result.imported} registro(s) importado(s).`);
    showToast("Importação concluída.");
    await refresh();
  } catch (error) {
    setFeedback(feedback, error.message, true);
    showToast(error.message, true);
  } finally {
    button.disabled = false;
  }
});

refresh();