// Talentum — advisor/app.js
// Responsabilidade: Controla o estado do painel Advisor, chamadas à API, renderização e interações da tela.
// Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
// A origem vem da configuração publicada; parâmetros de URL não redirecionam tokens.
const API = (() => {
  const configured = document.querySelector('meta[name="talentum-api-url"]')?.content || "http://127.0.0.1:8001";
  const url = new URL(configured, window.location.origin);
  const isLocalHttp = url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if ((url.protocol !== "https:" && !isLocalHttp) || url.username || url.password || url.search || url.hash) {
    throw new Error("Configure a API Talentum com HTTPS antes de abrir o painel.");
  }
  return url.href.replace(/\/+$/, "");
})();
// Estado global da sessão e dos painéis; os dados são atualizados após cada operação.
const state = { token: sessionStorage.getItem("talentum_advisor_token"), refreshToken: sessionStorage.getItem("talentum_advisor_refresh_token"), clients: [], advisors: [], team: [], notifications: [], notificationPreferences: null, notificationTypeFilter: "all", notificationReadFilter: "all", userRole: null, selected: null, permissions: null, financialProfile: null, clientProfile: null, suitability: null, suitabilityProposalDraft: null, suitabilityProposalSearchResults: [], suitabilityProposalQuery: "", suitabilityProposalMarket: "all", editingReport: null, reports: [], documents: [], patrimony: [], goals: [], actionPlan: [], editingPatrimony: null, editingGoal: null, editingAction: null, investmentPortfolio: null, investmentTransactions: [], editingInvestmentPosition: null, investmentAnalytics: null, investmentSnapshots: [], investmentMonthlyPerformance: null, marketResults: [], marketTypeFilter: "all", marketSectorFilter: "all", marketSort: "relevance", marketCompareKeys: [], marketComparisonHistories: [], marketComparisonPeriod: "1y", marketAlerts: [], editingMarketAlert: null, marketWatchlist: [] };
// Busca um elemento da página pelo identificador HTML.
const $ = (id) => document.getElementById(id);
// Formata um valor no padrão monetário brasileiro.
const money = (value) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0));
// Escapa caracteres especiais antes de inserir texto não confiável no HTML.
const escapeHtml = (value) => String(value ?? "").replace(/[&<>\"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[character]));
// Extrai uma mensagem legível das respostas de erro da API.
const formatApiError = (data, status) => {
  const detail = data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") return item.msg || item.message || item.detail || JSON.stringify(item);
      return String(item);
    }).filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  if (detail && typeof detail === "object") return detail.message || detail.msg || JSON.stringify(detail);
  return status ? `A API retornou um erro (${status}).` : "Não foi possível concluir a operação.";
};
// Formata datas civis sem horário; timestamps ISO precisam de um formatador próprio (achado 47).
const formatDate = (value) => value ? new Intl.DateTimeFormat("pt-BR").format(new Date(`${value}T12:00:00`)) : "";
// Verifica se um item não concluído passou do prazo.
const isOverdue = (date, status) => Boolean(date && status !== "completed" && new Date(`${date}T23:59:59`) < new Date());
// Aplica às metas a mesma regra de vencimento usada nas ações.
const isGoalOverdue = (date, status) => isOverdue(date, status);
// Cliente HTTP: injeta o token, interpreta erros e renova a sessão quando necessário.
const api = async (path, options = {}, retryOnUnauthorized = true) => {
  let response;
  const { responseType, ...requestOptions } = options;
  const headers = { ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}), ...(requestOptions.headers || {}) };
  if (!(requestOptions.body instanceof FormData)) headers["Content-Type"] = "application/json";
  try {
    response = await fetch(`${API}${path}`, { ...requestOptions, headers });
  } catch (_) {
    const error = new Error("Não foi possível conectar à API. Inicie o backend na porta 8001 e tente novamente."); error.status = 0; throw error;
  }
  if (response.ok && responseType === "blob") return response.blob();
  const data = await response.json().catch(() => ({})); // Respostas vazias (204) viram objeto vazio; erros sem JSON usam a mensagem genérica por status.
  if (!response.ok) {
    if (response.status === 401 && retryOnUnauthorized && state.refreshToken && path !== "/auth/login" && path !== "/auth/refresh") {
      try {
        const tokens = await api("/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token: state.refreshToken }) }, false);
        state.token = tokens.access_token; state.refreshToken = tokens.refresh_token;
        sessionStorage.setItem("talentum_advisor_token", state.token); sessionStorage.setItem("talentum_advisor_refresh_token", state.refreshToken);
        return api(path, options, false);
      } catch (_) {
        // Como o servidor consome cada refresh uma vez, 401 paralelos podem competir e esta falha limpar tokens recém-renovados (achado 136).
        state.token = null; state.refreshToken = null; sessionStorage.removeItem("talentum_advisor_token"); sessionStorage.removeItem("talentum_advisor_refresh_token");
        show("login-view", true); show("app-view", false); $("login-error").textContent = "Sua sessão expirou. Entre novamente para continuar.";
      }
    }
    const error = new Error(formatApiError(data, response.status)); error.status = response.status; throw error;
  }
  return data;
};
// Alterna a visibilidade de um elemento da interface.
const show = (id, visible) => $(id).classList.toggle("hidden", !visible);
// Atualiza a mensagem e o estado visual de retorno de um formulário.
const setFeedback = (id, message, error = false) => { $(id).textContent = message; $(id).style.color = error ? "#b84a5c" : ""; };

// Mostra imediatamente ao usuário se a API configurada está pronta.
async function checkApiHealth() {
  const status = $("api-status");
  try {
    const response = await fetch(`${API}/health/ready`);
    if (!response.ok) throw new Error();
    status.textContent = "API conectada e pronta para uso.";
    status.className = "api-status online";
  } catch (_) {
    status.textContent = "API indisponível. Inicie o backend na porta 8001.";
    status.className = "api-status offline";
  }
}

// Autentica o Advisor/administrador e carrega o workspace após o login.
async function login(event) {
  event.preventDefault();
  $("login-error").textContent = "";
  try {
    const data = await api("/auth/login", { method: "POST", body: JSON.stringify({ email: $("email").value, password: $("password").value }) });
    state.token = data.access_token; state.refreshToken = data.refresh_token;
    sessionStorage.setItem("talentum_advisor_token", state.token); sessionStorage.setItem("talentum_advisor_refresh_token", state.refreshToken);
    await start();
  } catch (error) { $("login-error").textContent = error.message; }
}

// Monta o estado inicial de acordo com a role e habilita os módulos permitidos.
async function start() {
  try {
    const user = await api("/auth/me");
    if (!["admin", "advisor"].includes(user.role)) throw new Error("Este painel é exclusivo para administradores e consultores.");
    state.userRole = user.role;
    $("current-user").textContent = user.name;
    show("new-user", user.role === "admin");
    state.advisors = user.role === "admin" ? await api("/clients/advisors") : [];
    state.team = user.role === "admin" ? await api("/admin/users?role=advisor") : [];
    show("manage-team", user.role === "admin");
    show("assignment-panel", user.role === "admin");
    state.clients = await api("/clients");
    state.notifications = await api("/notifications");
    state.notificationPreferences = await api("/notifications/preferences"); // Endpoint auxiliar; a falha ainda cai no catch que apaga a sessão (achado 95).
    renderClients();
    renderOverview();
    renderNotifications();
    renderNotificationPreferences();
    show("login-view", false);
    show("app-view", true);
  } catch (error) {
    // Qualquer falha de inicialização apaga a sessão, inclusive erro transitório de rede (achado 95).
    sessionStorage.removeItem("talentum_advisor_token"); sessionStorage.removeItem("talentum_advisor_refresh_token"); state.token = null; state.refreshToken = null; show("login-view", true); show("app-view", false); $("login-error").textContent = error.message;
  }
}

// Renderiza a lista filtrável de clientes e destaca o cliente selecionado.
function renderClients() {
  $("client-list").innerHTML = "";
  const query = $("client-search").value.trim().toLowerCase();
  const statusFilter = $("client-status-filter").value;
  const clients = state.clients.filter((client) => {
    const matchesQuery = `${client.name} ${client.email}`.toLowerCase().includes(query);
    const matchesStatus = statusFilter === "all" || (statusFilter === "active" ? client.is_active : !client.is_active);
    return matchesQuery && matchesStatus;
  }).sort((left, right) => Number(right.is_active) - Number(left.is_active) || left.name.localeCompare(right.name, "pt-BR"));
  if (!clients.length) { $("client-list").innerHTML = `<p class="muted">${state.clients.length ? "Nenhum cliente encontrado." : "Nenhum cliente cadastrado."}</p>`; return; }
  clients.forEach((client) => { const button = document.createElement("button"); button.className = "client-button"; button.dataset.id = client.id; button.classList.toggle("active", state.selected?.id === client.id); button.classList.toggle("inactive", !client.is_active); button.innerHTML = `<strong></strong><span></span><em></em>`; button.querySelector("strong").textContent = client.name; button.querySelector("span").textContent = client.email; button.querySelector("em").textContent = client.is_active ? "Acesso ativo" : "Acesso inativo"; button.onclick = () => selectClient(client.id); $("client-list").append(button); });
}

// Atualiza os indicadores gerais do workspace Advisor.
function renderOverview() {
  $("overview-client-count").textContent = state.clients.length;
  $("overview-active-count").textContent = state.clients.filter((client) => client.is_active).length;
  $("overview-advisor-count").textContent = state.userRole === "admin" ? state.advisors.length : "—";
}

// Renderiza notificações aplicando filtros por tipo e status de leitura.
function renderNotifications() {
  // O indicador resume a lista padrão limitada a 50 itens, não o total do servidor.
  const unread = state.notifications.filter((notification) => !notification.read_at);
  const visible = state.notifications.filter((notification) => {
    const matchesType = state.notificationTypeFilter === "all" || notification.kind === state.notificationTypeFilter;
    const matchesRead = state.notificationReadFilter === "all" || (state.notificationReadFilter === "unread" ? !notification.read_at : Boolean(notification.read_at));
    return matchesType && matchesRead;
  });
  $("notification-count").textContent = unread.length;
  $("notifications-list").innerHTML = visible.length ? visible.map((notification) => `<article class="notification-row ${notification.read_at ? "" : "unread"}"><div><strong>${escapeHtml(notification.title)}</strong><p>${escapeHtml(notification.message)}</p><small class="muted">${formatDateTime(notification.created_at)}</small></div><div class="quick-record-actions">${notification.client_id ? `<button class="button ghost small" data-notification-open="${notification.id}">Abrir cliente</button>` : ""}${notification.read_at ? "" : `<button class="button ghost small" data-notification-read="${notification.id}">Marcar como lida</button>`}</div></article>`).join("") : '<p class="empty-line">Nenhum alerta neste filtro.</p>';
  document.querySelectorAll("[data-notification-read]").forEach((button) => { button.onclick = () => markNotificationRead(Number(button.dataset.notificationRead)); });
  document.querySelectorAll("[data-notification-open]").forEach((button) => { button.onclick = () => openNotification(Number(button.dataset.notificationOpen)); });
}

// Sincroniza os controles da interface com as preferências salvas.
function renderNotificationPreferences() {
  if (!state.notificationPreferences) return;
  document.querySelectorAll("[data-notification-preference]").forEach((input) => { input.checked = Boolean(state.notificationPreferences[input.dataset.notificationPreference]); });
}

// Persiste no backend as preferências que controlam os avisos do usuário.
async function saveNotificationPreferences() {
  const payload = Object.fromEntries([...document.querySelectorAll("[data-notification-preference]")].map((input) => [input.dataset.notificationPreference, input.checked]));
  // Gravações podem se sobrepor; cada PATCH leva uma fotografia completa dos seletores (achado 159).
  try {
    state.notificationPreferences = await api("/notifications/preferences", { method: "PATCH", body: JSON.stringify(payload) });
    renderNotificationPreferences();
    setFeedback("notification-preference-status", "Preferências salvas.");
  } catch (error) { setFeedback("notification-preference-status", error.message, true); }
}

// Formata data e horário para exibição no painel.
function formatDateTime(value) {
  return value ? new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : "";
}

// Atualiza notificações e a respectiva lista visual.
async function refreshNotifications() {
  state.notifications = await api("/notifications");
  renderNotifications();
}

// Atualiza notificações e abre a janela de consulta.
async function openNotificationsDialog() {
  try {
    await refreshNotifications();
    $("notifications-dialog").showModal();
  } catch (error) { window.alert(error.message); }
}

// Fecha a janela de notificações.
function closeNotificationsDialog() {
  $("notifications-dialog").close();
}

// Marca uma notificação individual sem recarregar o restante do workspace.
async function markNotificationRead(notificationId) {
  try {
    await api(`/notifications/${notificationId}/read`, { method: "PATCH" });
    await refreshNotifications();
  } catch (error) { window.alert(error.message); }
}

// Abre o cliente relacionado à notificação selecionada.
async function openNotification(notificationId) {
  const notification = state.notifications.find((item) => item.id === notificationId);
  if (!notification) return;
  try {
    if (!notification.read_at) await api(`/notifications/${notificationId}/read`, { method: "PATCH" });
    closeNotificationsDialog();
    if (notification.client_id && state.clients.some((client) => client.id === notification.client_id)) await selectClient(notification.client_id);
    await refreshNotifications();
  } catch (error) { window.alert(error.message); }
}

// Marca todas as notificações do usuário como lidas.
async function markAllNotificationsRead() {
  try {
    await api("/notifications/read-all", { method: "PATCH" });
    await refreshNotifications();
  } catch (error) { window.alert(error.message); }
}

// Formatadores de mercado evitam que valores nulos ou moedas inválidas quebrem a tela.
function marketNumber(value) {
  return value === null || value === undefined || Number.isNaN(Number(value)) ? "—" : new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(Number(value));
}

// Formata preço com o símbolo monetário apropriado.
function marketPrice(value, currency) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  try { return new Intl.NumberFormat("pt-BR", { style: "currency", currency: currency || "USD", maximumFractionDigits: 2 }).format(Number(value)); }
  // A moeda inválida volta sem escape; os chamadores que usam HTML precisam neutralizá-la.
  catch (_) { return `${marketNumber(value)} ${currency || ""}`.trim(); }
}

// Formata variações com sinal e sufixo configurado.
function marketChange(value, suffix = "%") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const number = Number(value);
  return `<span class="market-change ${number < 0 ? "negative" : "positive"}">${number > 0 ? "+" : ""}${marketNumber(number)}${suffix}</span>`;
}

// Formata uma taxa percentual para apresentação.
function marketPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `${marketNumber(Number(value) * 100)}%`;
}

// Aplica o formatador escolhido ou um marcador para dado ausente.
function marketDetailValue(value, formatter = marketNumber) {
  return value === null || value === undefined || value === "" ? "—" : formatter(value);
}

// Desenha o histórico em SVG, incluindo escala lateral, retorno e benchmark.
function renderMarketHistory(panel, data) {
  // Mantém na série somente pontos com retorno calculado.
  const points = (data.points || []).filter((point) => point.return_percent !== null && point.return_percent !== undefined);
  // Aplica o mesmo filtro à série de referência para o gráfico não receber valores ausentes.
  const benchmark = (data.benchmark_points || []).filter((point) => point.return_percent !== null && point.return_percent !== undefined);
  if (!points.length) { panel.innerHTML = '<p class="empty-line">Nenhum histórico disponível para este ativo.</p>'; return; }
  const width = 760; const height = 220; const padX = 58; const padY = 20;
  const values = [...points, ...benchmark].map((point) => Number(point.return_percent));
  let min = Math.min(...values); let max = Math.max(...values);
  if (min === max) { min -= 1; max += 1; }
  const range = max - min; min -= range * 0.08; max += range * 0.08;
  // Calcula a posição horizontal do ponto na linha do gráfico.
  const toX = (index, length) => padX + (index / Math.max(length - 1, 1)) * (width - padX * 2);
  // Converte o valor da série em uma coordenada vertical do gráfico.
  const toY = (value) => height - padY - ((value - min) / (max - min)) * (height - padY * 2);
  // Converte os pontos históricos em coordenadas SVG conectadas.
  const line = (series) => series.map((point, index) => `${toX(index, series.length).toFixed(1)},${toY(Number(point.return_percent)).toFixed(1)}`).join(" ");
  const ticks = Array.from({ length: 5 }, (_, index) => max - (index * (max - min)) / 4);
  const grid = ticks.map((tick) => `<line x1="${padX}" y1="${toY(tick)}" x2="${width - 12}" y2="${toY(tick)}" class="market-chart-grid"></line><text x="${padX - 8}" y="${toY(tick) + 4}" text-anchor="end" class="market-chart-axis-label">${marketNumber(tick)}%</text>`).join("");
  const last = points[points.length - 1];
  const benchmarkLast = benchmark[benchmark.length - 1];
  // Apresenta retorno com sinal e casas decimais da interface.
  const formatReturn = (value) => value === null || value === undefined ? "—" : `${Number(value) > 0 ? "+" : ""}${marketNumber(value)}%`;
  const volatilityLabels = { lower: "Menor", intermediate: "Intermediária", higher: "Maior" };
  const volatilityBand = volatilityLabels[data.volatility_band] || "—";
  panel.innerHTML = `<div class="market-history-metrics"><div><small class="muted">Volatilidade anualizada</small><strong>${marketDetailValue(data.annualized_volatility, (value) => `${marketNumber(value)}%`)}</strong><span>${volatilityBand}</span></div><div><small class="muted">Maior queda no período</small><strong>${marketDetailValue(data.max_drawdown, (value) => `${marketNumber(value)}%`)}</strong><span>do topo ao vale</span></div><div><small class="muted">Volume médio</small><strong>${marketNumber(data.average_volume)}</strong><span>${marketNumber(data.observation_count)} observações</span></div></div><div class="market-chart-summary"><span>Retorno de ${formatDateTime(points[0].date)} a ${formatDateTime(last.date)}: <strong>${formatReturn(last.return_percent)}</strong></span><span class="market-chart-legend"><i class="asset"></i>${escapeHtml(data.symbol)}${benchmarkLast ? `<i class="benchmark"></i>${escapeHtml(data.benchmark_symbol || "Referência")}` : ""}</span></div><div class="market-chart-wrap"><svg class="market-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Histórico de retorno percentual">${grid}<line x1="${padX}" y1="${toY(0)}" x2="${width - 12}" y2="${toY(0)}" class="market-chart-zero"></line><polyline points="${line(points)}" class="market-chart-line asset"></polyline>${benchmarkLast ? `<polyline points="${line(benchmark)}" class="market-chart-line benchmark"></polyline>` : ""}</svg></div><div class="market-chart-footer"><span>${escapeHtml(formatDateTime(points[0].date))}</span><span>Retorno acumulado (%)</span><span>${escapeHtml(formatDateTime(last.date))}</span></div>`;
}

// Aplica filtros e ordenação local sobre os resultados já recebidos da API.
function marketFilteredResults() {
  const filtered = state.marketResults.filter((item) => {
    const typeMatch = state.marketTypeFilter === "all" || String(item.asset_type || "").toLowerCase() === state.marketTypeFilter;
    const sectorMatch = state.marketSectorFilter === "all" || item.sector === state.marketSectorFilter || item.segment === state.marketSectorFilter;
    return typeMatch && sectorMatch;
  });
  // Converte um campo do ativo em número para ordenação.
  const value = (item, key) => Number(item[key] ?? Number.NEGATIVE_INFINITY);
  const sorters = {
    price_desc: (a, b) => value(b, "price") - value(a, "price"),
    change_desc: (a, b) => value(b, "change_percent") - value(a, "change_percent"),
    volume_desc: (a, b) => value(b, "volume") - value(a, "volume"),
    market_cap_desc: (a, b) => value(b, "market_cap") - value(a, "market_cap"),
    dividend_yield_desc: (a, b) => value(b, "dividend_yield") - value(a, "dividend_yield"),
  };
  return sorters[state.marketSort] ? filtered.sort(sorters[state.marketSort]) : filtered;
}

// Aplica os filtros atuais e atualiza os resultados de mercado.
function refreshMarketFilters() {
  if (!state.marketResults.length) { show("market-filter-controls", false); return; }
  show("market-filter-controls", true);
  const types = [...new Set(state.marketResults.map((item) => String(item.asset_type || "").toLowerCase()).filter(Boolean))].sort();
  const sectors = [...new Set(state.marketResults.map((item) => item.sector || item.segment).filter(Boolean))].sort();
  $("market-type-filter").innerHTML = '<option value="all">Todos</option>' + types.map((type) => `<option value="${escapeHtml(type)}">${escapeHtml(type)}</option>`).join("");
  $("market-sector-filter").innerHTML = '<option value="all">Todos</option>' + sectors.map((sector) => `<option value="${escapeHtml(sector)}">${escapeHtml(sector)}</option>`).join("");
  $("market-type-filter").value = state.marketTypeFilter;
  $("market-sector-filter").value = state.marketSectorFilter;
  $("market-sort").value = state.marketSort;
}

// Gera uma chave estável que combina mercado e símbolo do ativo.
function marketKey(item) { return `${item.market}:${item.symbol}`; }

// Traduz o estado do alerta para o rótulo da interface.
function marketAlertStatusLabel(status) {
  return { active: "Ativo", paused: "Pausado", triggered: "Disparado", cancelled: "Cancelado" }[status] || status;
}

// Traduz a condição do alerta para texto amigável.
function marketAlertConditionLabel(condition) {
  return condition === "at_or_above" ? "atingir ou superar" : "atingir ou ficar abaixo";
}

// Escolhe a ação disponível conforme o estado atual do alerta.
function marketAlertStatusAction(status) {
  return status === "active" ? ["Pausar", "paused"] : ["Reativar", "active"];
}

// Prepara o formulário para editar o alerta selecionado.
function startEditMarketAlert(alertId) {
  const alert = state.marketAlerts.find((item) => item.id === alertId);
  if (!alert) return;
  state.editingMarketAlert = alert;
  $("market-alert-client").value = String(alert.client_id);
  $("market-alert-symbol").value = alert.symbol;
  $("market-alert-market").value = alert.market;
  $("market-alert-target").value = alert.target_price;
  $("market-alert-condition").value = alert.condition;
  $("market-alert-submit").textContent = "Salvar alterações";
  show("market-alert-cancel-edit", true);
  $("market-alert-form").scrollIntoView({ behavior: "smooth", block: "center" });
}

// Cancela a edição e limpa o estado temporário do alerta.
function cancelMarketAlertEdit() {
  state.editingMarketAlert = null;
  $("market-alert-form").reset();
  refreshMarketAlertClients();
  $("market-alert-submit").textContent = "Criar alerta";
  show("market-alert-cancel-edit", false);
}

// Altera o estado de um alerta e atualiza o painel; cliques simultâneos duplicam o evento de auditoria (achado 191).
async function updateMarketAlertStatus(alertId, status) {
  try {
    await api(`/market/alerts/${alertId}`, { method: "PATCH", body: JSON.stringify({ status }) });
    await loadMarketAlerts();
    setFeedback("market-alert-status", status === "paused" ? "Alerta pausado." : "Alerta reativado.");
  } catch (error) { setFeedback("market-alert-status", error.message, true); }
}

// Atualiza a seleção de clientes disponível para os alertas.
function refreshMarketAlertClients() {
  const select = $("market-alert-client");
  if (!select) return;
  // Ao reconstruir as opções, o cliente aberto no painel prevalece sobre a escolha manual.
  const selectedId = state.selected?.id || Number(select.value) || state.clients[0]?.id;
  select.innerHTML = state.clients.length ? state.clients.map((client) => `<option value="${client.id}">${escapeHtml(client.name)} · ${escapeHtml(client.email)}</option>`).join("") : '<option value="">Nenhum cliente disponível</option>';
  select.disabled = !state.clients.length;
  if (selectedId && state.clients.some((client) => client.id === selectedId)) select.value = String(selectedId);
}

// Atualiza a seleção de clientes para a lista acompanhada.
function refreshMarketWatchlistClients() {
  const select = $("market-watchlist-client");
  if (!select) return;
  // Ao reconstruir as opções, o cliente aberto no painel prevalece sobre a escolha manual.
  const selectedId = state.selected?.id || Number(select.value) || state.clients[0]?.id;
  select.innerHTML = state.clients.length ? state.clients.map((client) => `<option value="${client.id}">${escapeHtml(client.name)} · ${escapeHtml(client.email)}</option>`).join("") : '<option value="">Nenhum cliente disponível</option>';
  select.disabled = !state.clients.length;
  if (selectedId && state.clients.some((client) => client.id === selectedId)) select.value = String(selectedId);
}

// Desenha alertas de mercado com estado e ações disponíveis.
function renderMarketAlerts() {
  const list = $("market-alert-list");
  if (!state.marketAlerts.length) { list.innerHTML = '<p class="empty-line">Nenhum alerta cadastrado para este cliente.</p>'; return; }
  list.innerHTML = state.marketAlerts.map((alert) => {
    const [statusLabel, nextStatus] = marketAlertStatusAction(alert.status);
    // A resposta só informa o mercado; o painel assume USD para qualquer ativo global.
    return `<article class="market-alert-row"><div><div class="market-alert-heading"><strong>${escapeHtml(alert.symbol)}</strong><span class="market-badge ${alert.market === "br" ? "br" : "global"}">${alert.market === "br" ? "B3" : "Exterior"}</span><span class="market-alert-status ${escapeHtml(alert.status)}">${marketAlertStatusLabel(alert.status)}</span></div><small class="muted">Alerta para ${escapeHtml(alert.client_name)} · ${marketAlertConditionLabel(alert.condition)} ${marketPrice(alert.target_price, alert.market === "br" ? "BRL" : "USD")}</small><small class="muted">${alert.last_price == null ? "Cotação ainda não consultada" : "Última cotação: " + marketPrice(alert.last_price, alert.market === "br" ? "BRL" : "USD")}</small></div><div class="quick-record-actions"><button class="button ghost small" type="button" data-market-alert-edit="${alert.id}">Editar</button><button class="button ghost small" type="button" data-market-alert-status="${alert.id}" data-market-alert-next-status="${nextStatus}">${statusLabel}</button></div></article>`;
  }).join("");
}

// Busca alertas de mercado do cliente selecionado.
async function loadMarketAlerts() {
  refreshMarketAlertClients();
  const clientId = Number($("market-alert-client")?.value);
  if (!clientId) { state.marketAlerts = []; renderMarketAlerts(); return; }
  try {
    state.marketAlerts = await api(`/market/alerts?client_id=${clientId}`);
    renderMarketAlerts();
  } catch (error) {
    // A falha fica na própria lista e não é propagada a quem aguarda esta atualização.
    state.marketAlerts = []; $("market-alert-list").innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  }
}

// Desenha ativos acompanhados e seus dados disponíveis.
function renderMarketWatchlist() {
  const list = $("market-watchlist-list");
  if (!state.marketWatchlist.length) { list.innerHTML = '<p class="empty-line">Nenhum ativo cadastrado para este cliente.</p>'; return; }
  list.innerHTML = state.marketWatchlist.map((item) => {
    const price = item.current_price == null ? "Cotação indisponível" : marketPrice(item.current_price, item.currency || (item.market === "br" ? "BRL" : "USD"));
    return `<article class="market-watchlist-row"><div><div class="market-watchlist-heading"><strong>${escapeHtml(item.symbol)}</strong><span class="market-badge ${item.market === "br" ? "br" : "global"}">${item.market === "br" ? "B3" : "Exterior"}</span></div><small class="muted">${escapeHtml(item.name || "Ativo acompanhado")} · ${escapeHtml(price)}</small><small class="muted">Fonte: ${escapeHtml(item.source || "não informada")}</small></div><div class="quick-record-actions"><button class="button ghost small" type="button" data-market-watchlist-open="${escapeHtml(item.symbol)}" data-market-watchlist-open-market="${escapeHtml(item.market)}">Abrir ativo</button><button class="button ghost small" type="button" data-market-watchlist-remove="${item.id}">Remover</button></div></article>`;
  }).join("");
}

// Busca a lista de ativos acompanhados do cliente.
async function loadMarketWatchlist() {
  refreshMarketWatchlistClients();
  const clientId = Number($("market-watchlist-client")?.value);
  if (!clientId) { state.marketWatchlist = []; renderMarketWatchlist(); return; }
  try {
    state.marketWatchlist = await api(`/market/watchlist?client_id=${clientId}`);
    renderMarketWatchlist();
  } catch (error) {
    // A falha fica na própria lista e não é propagada a quem aguarda esta atualização.
    state.marketWatchlist = []; $("market-watchlist-list").innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  }
}

// Inclui um ativo na lista de acompanhamento do cliente escolhido.
async function createMarketWatchlistItem(event) {
  event.preventDefault();
  const clientId = Number($("market-watchlist-client").value);
  const symbol = $("market-watchlist-symbol").value.trim();
  if (!clientId || !symbol) { setFeedback("market-watchlist-status", "Informe um cliente e um ticker válido.", true); return; }
  const button = $("market-watchlist-submit");
  if (button) { button.disabled = true; button.textContent = "Salvando…"; }
  try {
    await api("/market/watchlist", { method: "POST", body: JSON.stringify({ client_id: clientId, symbol, market: $("market-watchlist-market").value }) });
    $("market-watchlist-symbol").value = "";
    await loadMarketWatchlist();
    setFeedback("market-watchlist-status", "Ativo adicionado à lista de acompanhamento.");
  } catch (error) { setFeedback("market-watchlist-status", error.message, true); }
  finally { if (button) { button.disabled = false; button.textContent = "Adicionar ativo"; } }
}

// Remove o ativo selecionado; uma chamada repetida após o commit pode receber 404.
async function removeMarketWatchlistItem(itemId) {
  if (!window.confirm("Remover este ativo da lista de acompanhamento?")) return;
  try {
    await api(`/market/watchlist/${itemId}`, { method: "DELETE" });
    await loadMarketWatchlist();
    setFeedback("market-watchlist-status", "Ativo removido da lista.");
  } catch (error) { setFeedback("market-watchlist-status", error.message, true); }
}

// Preenche o formulário a partir do ativo escolhido na lista.
function prefillMarketWatchlist(button) {
  $("market-watchlist-symbol").value = button.dataset.marketWatchlistSymbol || "";
  $("market-watchlist-market").value = button.dataset.marketWatchlistMarket || "br";
  $("market-watchlist-symbol").focus();
  $("market-watchlist-form").scrollIntoView({ behavior: "smooth", block: "center" });
}

// Abre os detalhes de mercado do ativo acompanhado.
function openMarketWatchlistItem(button) {
  $("market-query").value = button.dataset.marketWatchlistOpen || "";
  $("market-region").value = button.dataset.marketWatchlistOpenMarket || "br";
  $("market-search-form").requestSubmit();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// Cria ou atualiza um alerta de preço conforme o formulário selecionado.
async function createMarketAlert(event) {
  event.preventDefault();
  const clientId = Number($("market-alert-client").value);
  const targetPrice = Number($("market-alert-target").value);
  if (!clientId || !Number.isFinite(targetPrice) || targetPrice <= 0) { setFeedback("market-alert-status", "Informe um cliente e um preço-alvo válido.", true); return; }
  const editing = state.editingMarketAlert;
  const button = $("market-alert-submit");
  if (button) { button.disabled = true; button.textContent = "Salvando…"; }
  try {
    // No PATCH, o schema só aceita preço/condição/status; símbolo e mercado do formulário não mudam (achado 130).
    const body = { symbol: $("market-alert-symbol").value.trim(), market: $("market-alert-market").value, target_price: targetPrice, condition: $("market-alert-condition").value };
    if (!editing) body.client_id = clientId;
    await api(editing ? `/market/alerts/${editing.id}` : "/market/alerts", { method: editing ? "PATCH" : "POST", body: JSON.stringify(body) });
    cancelMarketAlertEdit();
    await loadMarketAlerts();
    setFeedback("market-alert-status", editing ? "Alerta atualizado." : "Alerta criado. A cotação será verificada ao atualizar as notificações.");
  } catch (error) { setFeedback("market-alert-status", error.message, true); }
  finally { if (button) { button.disabled = false; button.textContent = state.editingMarketAlert ? "Salvar alterações" : "Criar alerta"; } }
}

// Cancela um alerta e recarrega seu estado no painel.
async function cancelMarketAlert(alertId) {
  if (!window.confirm("Desativar este alerta de preço?")) return;
  try { await api(`/market/alerts/${alertId}`, { method: "DELETE" }); await loadMarketAlerts(); setFeedback("market-alert-status", "Alerta desativado."); }
  catch (error) { setFeedback("market-alert-status", error.message, true); }
}

// Preenche os campos do alerta com dados de um ativo escolhido.
function prefillMarketAlert(button) {
  $("market-alert-symbol").value = button.dataset.marketAlertSymbol || "";
  $("market-alert-market").value = button.dataset.marketAlertMarket || "br";
  $("market-alert-target").focus();
  $("market-alert-form").scrollIntoView({ behavior: "smooth", block: "center" });
}

// Atualiza indicadores e ações da barra de comparação.
function refreshMarketCompareToolbar() {
  const available = state.marketResults.length > 0;
  show("market-compare-toolbar", available);
  const count = state.marketCompareKeys.length;
  $("market-compare-count").textContent = count ? `${count} ativo(s) selecionado(s) — máximo de 3.` : "Selecione até 3 ativos para comparar.";
  $("market-compare-button").disabled = count < 2;
}

// Limpa ativos e séries selecionados para comparação.
function resetMarketComparison() {
  state.marketCompareKeys = [];
  state.marketComparisonHistories = [];
  state.marketComparisonPeriod = "1y";
  $("market-compare-period").value = "1y";
  $("market-compare-chart").innerHTML = "";
  $("market-compare-status").textContent = "";
  show("market-compare-panel", false);
}

// Desenha séries de retorno comparáveis no gráfico SVG.
function renderMarketComparison(panel, histories) {
  const series = histories.map((history) => ({ symbol: history.symbol, points: (history.points || []).filter((point) => point.return_percent !== null && point.return_percent !== undefined) })).filter((item) => item.points.length);
  if (!series.length) { panel.innerHTML = '<p class="empty-line">Nenhum histórico disponível para a comparação.</p>'; return; }
  const width = 760; const height = 240; const padX = 58; const padY = 20;
  const values = series.flatMap((item) => item.points.map((point) => Number(point.return_percent)));
  let min = Math.min(...values); let max = Math.max(...values); if (min === max) { min -= 1; max += 1; }
  const range = max - min; min -= range * 0.08; max += range * 0.08;
  // Calcula a posição horizontal do ponto na linha do gráfico.
  const toX = (index, length) => padX + (index / Math.max(length - 1, 1)) * (width - padX - 12);
  // Converte o valor da série em uma coordenada vertical do gráfico.
  const toY = (value) => height - padY - ((value - min) / (max - min)) * (height - padY * 2);
  const ticks = Array.from({ length: 5 }, (_, index) => max - (index * (max - min)) / 4);
  const grid = ticks.map((tick) => `<line x1="${padX}" y1="${toY(tick)}" x2="${width - 12}" y2="${toY(tick)}" class="market-chart-grid"></line><text x="${padX - 8}" y="${toY(tick) + 4}" text-anchor="end" class="market-chart-axis-label">${marketNumber(tick)}%</text>`).join("");
  const colors = ["#17324D", "#167C76", "#d18a34"];
  const lines = series.map((item, index) => `<polyline points="${item.points.map((point, pointIndex) => `${toX(pointIndex, item.points.length).toFixed(1)},${toY(Number(point.return_percent)).toFixed(1)}`).join(" ")}" class="market-chart-line" style="stroke:${colors[index % colors.length]}"></polyline>`).join("");
  const legend = series.map((item, index) => `<span class="market-chart-legend"><i style="background:${colors[index % colors.length]}"></i>${escapeHtml(item.symbol)}</span>`).join("");
  const ranking = [...series].sort((a, b) => Number(b.points.at(-1).return_percent) - Number(a.points.at(-1).return_percent)).map((item, index) => `<div class="market-comparison-row"><strong>${index + 1}. ${escapeHtml(item.symbol)}</strong><span>${Number(item.points.at(-1).return_percent) > 0 ? "+" : ""}${marketNumber(item.points.at(-1).return_percent)}%</span></div>`).join("");
  panel.innerHTML = `<div class="market-chart-summary"><span>Retorno acumulado normalizado</span><span class="market-chart-legend-list">${legend}</span></div><div class="market-chart-wrap"><svg class="market-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Comparação histórica de ativos">${grid}<line x1="${padX}" y1="${toY(0)}" x2="${width - 12}" y2="${toY(0)}" class="market-chart-zero"></line>${lines}</svg></div><div class="market-comparison-ranking"><p class="eyebrow">resultado no período</p>${ranking}</div>`;
}

// Busca históricos de até três ativos e prepara a comparação visual.
async function compareSelectedMarketAssets() {
  const selected = state.marketResults.filter((item) => state.marketCompareKeys.includes(marketKey(item))).slice(0, 3);
  if (selected.length < 2) return;
  const panel = $("market-compare-chart"); const button = $("market-compare-button");
  button.disabled = true; setFeedback("market-compare-status", "Carregando comparação…"); show("market-compare-panel", true);
  try {
    const period = $("market-compare-period").value;
    const responses = await Promise.allSettled(selected.map((item) => {
      const params = new URLSearchParams({ symbol: item.symbol, market: item.market, period });
      return api(`/market/history?${params.toString()}`);
    }));
    const histories = responses.filter((response) => response.status === "fulfilled").map((response) => response.value);
    const failures = responses.filter((response) => response.status === "rejected");
    if (histories.length < 2) throw new Error("Não foi possível carregar o histórico de pelo menos dois ativos selecionados.");
    // Os ativos podem mudar durante os awaits; a resposta ainda usa a seleção capturada no início (achado 131).
    state.marketComparisonHistories = histories; state.marketComparisonPeriod = period;
    renderMarketComparison(panel, histories);
    const status = failures.length ? `Comparação parcial: ${histories.length} ativo(s) carregado(s); ${failures.length} não respondeu.` : "Comparação carregada.";
    setFeedback("market-compare-status", status, failures.length > 0);
  } catch (error) { setFeedback("market-compare-status", error.message, true); }
  finally { button.disabled = state.marketCompareKeys.length < 2; }
}

// Gera arquivo exportável com os dados da análise de mercado.
function exportMarketAnalysis() {
  if (!state.marketComparisonHistories.length) { setFeedback("market-compare-status", "Carregue uma comparação antes de exportar.", true); return; }
  const selected = state.marketResults.filter((item) => state.marketCompareKeys.includes(marketKey(item))).slice(0, 3);
  const chart = $("market-compare-chart").querySelector("svg")?.outerHTML || "";
  const rows = selected.map((item) => {
    const history = state.marketComparisonHistories.find((entry) => entry.symbol === item.symbol);
    const last = history?.points?.at(-1);
    return `<tr><td>${escapeHtml(item.symbol)}</td><td>${escapeHtml(item.name)}</td><td>${marketPrice(item.price, item.currency)}</td><td>${marketChange(item.change_percent)}</td><td>${marketNumber(item.volume)}</td><td>${last ? `${marketNumber(last.return_percent)}%` : "—"}</td><td>${history?.annualized_volatility == null ? "—" : `${marketNumber(history.annualized_volatility)}%`}</td><td>${history?.max_drawdown == null ? "—" : `${marketNumber(history.max_drawdown)}%`}</td></tr>`;
  }).join("");
  const reportWindow = window.open("", "_blank", "width=1100,height=800");
  if (!reportWindow) { setFeedback("market-compare-status", "Permita pop-ups para gerar o relatório.", true); return; }
  reportWindow.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Talentum — Análise de investimentos</title><style>body{font:14px/1.5 Arial,sans-serif;color:#1F2B35;padding:34px}h1{margin:0 0 5px}h2{margin-top:28px}small,.muted{color:#63717D}.header{display:flex;justify-content:space-between;gap:20px;border-bottom:2px solid #17324D;padding-bottom:16px}.chart{margin-top:18px;border:1px solid #DCE4E8;border-radius:10px;padding:12px}.chart svg{width:100%;height:auto}.market-chart-line{fill:none;stroke-width:3}.market-chart-line.benchmark{stroke-dasharray:6 5;stroke-width:2}.market-chart-grid{stroke:#E8EFF2;stroke-width:1}.market-chart-zero{stroke:#B8C3CA;stroke-width:1.3;stroke-dasharray:3 4}.market-chart-axis-label{fill:#63717D;font-size:11px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;padding:9px;border-bottom:1px solid #DCE4E8}th{background:#F7F9FA}.disclaimer{margin-top:28px;color:#63717D;font-size:11px}@media print{body{padding:0}.no-print{display:none}}</style></head><body><div class="header"><div><h1>Talentum — Análise de investimentos</h1><small>Período: ${escapeHtml(state.marketComparisonPeriod)} · Gerado em ${escapeHtml(formatDateTime(new Date().toISOString()))}</small></div><div class="no-print">Use “Salvar como PDF” na janela de impressão.</div></div><h2>Comparação de desempenho</h2><div class="chart">${chart}</div><h2>Resumo dos ativos</h2><table><thead><tr><th>Ativo</th><th>Nome</th><th>Preço</th><th>Variação</th><th>Volume</th><th>Retorno</th><th>Volatilidade</th><th>Maior queda</th></tr></thead><tbody>${rows}</tbody></table><p class="disclaimer">Dados informativos, sujeitos a atraso e à disponibilidade dos provedores. Este material não constitui recomendação de investimento.</p></body></html>`);
  reportWindow.document.close(); reportWindow.focus(); setTimeout(() => reportWindow.print(), 350);
}

// Busca o histórico do ativo para o período solicitado.
async function loadMarketHistory(event) {
  const button = event.target.closest("[data-market-history-button]");
  if (!button) return false;
  const article = button.closest(".market-result");
  const panel = article?.querySelector("[data-market-history-panel]");
  const period = article?.querySelector("[data-market-history-period]")?.value || "1y";
  if (!article || !panel) return true;
  button.disabled = true; button.textContent = "Carregando…";
  panel.innerHTML = '<p class="muted">Consultando histórico…</p>';
  try {
    const params = new URLSearchParams({ symbol: article.dataset.marketSymbol, market: article.dataset.market, period });
    const data = await api(`/market/history?${params.toString()}`);
    renderMarketHistory(panel, data);
  } catch (error) {
    panel.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  } finally {
    button.disabled = false; button.textContent = "Atualizar histórico";
  }
  return true;
}

// Monta painel com informações e indicadores do instrumento.
function renderMarketDetails(panel, item) {
  const details = [
    ["Volume negociado", marketDetailValue(item.volume)],
    ["Volume médio", marketDetailValue(item.average_volume)],
    ["Fechamento anterior", marketDetailValue(item.previous_close, (value) => marketPrice(value, item.currency))],
    ["Mínima 52 semanas", marketDetailValue(item.fifty_two_week_low, (value) => marketPrice(value, item.currency))],
    ["Máxima 52 semanas", marketDetailValue(item.fifty_two_week_high, (value) => marketPrice(value, item.currency))],
    ["Valor de mercado", marketDetailValue(item.market_cap, (value) => marketPrice(value, item.currency))],
    ["Cotas/ações emitidas", marketDetailValue(item.shares_outstanding)],
    ["Cotistas", marketDetailValue(item.total_investors)],
    ["Dividend yield 12 meses", marketDetailValue(item.dividend_yield, marketPercent)],
    ["Dividend yield mensal", marketDetailValue(item.dividend_yield_1m, marketPercent)],
    ["P/L", marketDetailValue(item.price_earnings)],
    ["P/VP", marketDetailValue(item.price_to_book)],
    ["ROE", marketDetailValue(item.return_on_equity, marketPercent)],
    ["Valor patrimonial por cota", marketDetailValue(item.nav_per_share, (value) => marketPrice(value, item.currency))],
    ["Patrimônio líquido", marketDetailValue(item.equity, (value) => marketPrice(value, item.currency))],
    ["Ativo total", marketDetailValue(item.total_assets, (value) => marketPrice(value, item.currency))],
    ["Setor", marketDetailValue(item.sector)],
    ["Subsetor", marketDetailValue(item.subsector)],
    ["Indústria", marketDetailValue(item.industry)],
    ["Segmento", marketDetailValue(item.segment)],
    ["Gestão", marketDetailValue(item.management_type)],
    ["Data de referência", item.as_of_date ? formatDateTime(item.as_of_date) : "—"],
  ];
  const report = item.fii_report;
  const reportMetrics = report ? [
    ["Data do informe CVM", report.reference_date ? formatDateTime(report.reference_date) : "—"],
    ["Retorno mensal", marketDetailValue(report.monthly_return, marketPercent)],
    ["Retorno patrimonial", marketDetailValue(report.monthly_patrimonial_return, marketPercent)],
    ["DY mensal no informe", marketDetailValue(report.monthly_dividend_yield, marketPercent)],
    ["Taxa de administração", marketDetailValue(report.admin_fee_rate, marketPercent)],
    ["Caixa", marketDetailValue(report.cash, (value) => marketPrice(value, item.currency))],
    ["CRI", marketDetailValue(report.cri, (value) => marketPrice(value, item.currency))],
    ["LCI", marketDetailValue(report.lci, (value) => marketPrice(value, item.currency))],
    ["Imóveis", marketDetailValue(report.real_estate_assets, (value) => marketPrice(value, item.currency))],
    ["Cotas de outros FIIs", marketDetailValue(report.fii_holdings, (value) => marketPrice(value, item.currency))],
    ["Recebíveis", marketDetailValue(report.receivables, (value) => marketPrice(value, item.currency))],
    ["Passivos totais", marketDetailValue(report.total_liabilities, (value) => marketPrice(value, item.currency))],
  ] : [];
  const reportHtml = report ? `<section class="market-report"><div class="market-report-heading"><div><p class="eyebrow">referência regulatória</p><h3>Informe mensal baseado na CVM</h3></div><span class="market-badge br">CVM</span></div><div class="market-details-grid">${reportMetrics.map(([label, value]) => `<div class="market-detail-item"><small class="muted">${escapeHtml(label)}</small><strong>${escapeHtml(String(value))}</strong></div>`).join("")}</div><p class="market-details-note">O informe é periódico e pode ter defasagem em relação à cotação do dia.</p></section>` : "";
  const referencesHtml = item.references?.length ? `<section class="market-references"><p class="eyebrow">fontes</p><div class="market-reference-list">${item.references.map((reference) => `<a class="market-reference" href="${escapeHtml(reference.url)}" target="_blank" rel="noopener noreferrer"><span>${escapeHtml(reference.label)}</span><small>${escapeHtml(reference.source)} ↗</small></a>`).join("")}</div></section>` : "";
  const historyHtml = `<section class="market-history"><div class="market-report-heading"><div><p class="eyebrow">análise histórica</p><h3>Desempenho e referência</h3></div><div class="market-history-controls"><select data-market-history-period aria-label="Período do histórico"><option value="1mo">1 mês</option><option value="3mo">3 meses</option><option value="6mo">6 meses</option><option value="1y" selected>1 ano</option><option value="5y">5 anos</option></select><button class="button ghost small" type="button" data-market-history-button>Carregar histórico</button></div></div><div data-market-history-panel><p class="muted">Escolha um período para carregar o histórico.</p></div></section>`;
  // O bypass atual aceita qualquer valor com a substring <span como HTML confiável.
  panel.innerHTML = `<div class="market-details-grid">${details.map(([label, value]) => `<div class="market-detail-item"><small class="muted">${escapeHtml(label)}</small><strong>${typeof value === "string" && value.includes("<span") ? value : escapeHtml(String(value))}</strong></div>`).join("")}</div>${historyHtml}${reportHtml}${referencesHtml}<p class="market-details-note">Indicadores dependem da cobertura da fonte e podem ter atraso. Volume representa negócios/cotas negociados no período informado pela fonte.</p>`;
}

// Abre ou fecha os detalhes do ativo solicitado.
async function toggleMarketDetails(event) {
  const watchlistOpenButton = event.target.closest("[data-market-watchlist-open]");
  if (watchlistOpenButton) { openMarketWatchlistItem(watchlistOpenButton); return; }
  const watchlistButton = event.target.closest("[data-market-watchlist-symbol]");
  if (watchlistButton) { prefillMarketWatchlist(watchlistButton); return; }
  const alertButton = event.target.closest("[data-market-alert-symbol]");
  if (alertButton) { prefillMarketAlert(alertButton); return; }
  if (await loadMarketHistory(event)) return;
  const button = event.target.closest("[data-market-toggle]");
  if (!button) return;
  const article = button.closest(".market-result");
  const panel = article?.querySelector("[data-market-details-panel]");
  if (!article || !panel) return;
  const isOpen = !panel.classList.contains("hidden");
  panel.classList.toggle("hidden", isOpen);
  button.textContent = isOpen ? "Mais informações" : "Ocultar informações";
  if (isOpen || panel.dataset.loaded === "true") return;
  panel.innerHTML = '<p class="muted">Carregando indicadores…</p>';
  try {
    const params = new URLSearchParams({ symbol: button.dataset.marketToggle, market: article.dataset.market });
    const details = await api(`/market/details?${params.toString()}`);
    renderMarketDetails(panel, details);
    panel.dataset.loaded = "true";
  } catch (error) {
    const summary = state.marketResults.find((item) => item.symbol === button.dataset.marketToggle);
    if (summary) {
      renderMarketDetails(panel, summary);
      panel.insertAdjacentHTML("beforeend", '<p class="market-details-note">Os indicadores adicionais não responderam; exibindo os dados básicos disponíveis.</p>');
      panel.dataset.loaded = "true";
    } else {
      panel.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
    }
  }
}

// Desenha os resultados filtrados da pesquisa de ativos.
function renderMarketResults() {
  const results = marketFilteredResults();
  // Preço pode conter a moeda bruta do provedor no fallback do formatador (achado 40).
  $("market-results").innerHTML = results.length ? results.map((item) => `<article class="market-result" data-market-symbol="${escapeHtml(item.symbol)}" data-market="${escapeHtml(item.market)}"><div class="market-result-main"><div class="market-symbol-row"><strong>${escapeHtml(item.symbol)}</strong><span class="market-badge ${item.market === "br" ? "br" : "global"}">${item.market === "br" ? "B3" : "Exterior"}</span><span class="muted">${escapeHtml(item.exchange || "")}</span></div><h3>${escapeHtml(item.name)}</h3><small class="muted">${escapeHtml(item.asset_type || "Ativo")} · ${escapeHtml(item.currency || "Moeda não informada")} · fonte: ${escapeHtml(item.source)}</small></div><div class="market-result-metrics"><div><small class="muted">Preço</small><strong>${marketPrice(item.price, item.currency)}</strong></div><div><small class="muted">Variação</small><strong>${marketChange(item.change_percent)}</strong></div><div><small class="muted">Volume</small><strong>${marketNumber(item.volume)}</strong></div></div><div class="market-result-actions"><label class="market-compare-check"><input type="checkbox" data-market-compare="${escapeHtml(marketKey(item))}" ${state.marketCompareKeys.includes(marketKey(item)) ? "checked" : ""}> Comparar</label><button class="button ghost small" type="button" data-market-watchlist-symbol="${escapeHtml(item.symbol)}" data-market-watchlist-market="${escapeHtml(item.market)}">Acompanhar</button><button class="button ghost small" type="button" data-market-alert-symbol="${escapeHtml(item.symbol)}" data-market-alert-market="${escapeHtml(item.market)}">Criar alerta</button><button class="button ghost small" type="button" data-market-toggle="${escapeHtml(item.symbol)}">Mais informações</button></div><div class="market-result-details hidden" data-market-details-panel><p class="muted">Clique para carregar os indicadores.</p></div></article>`).join("") : '<p class="empty-line">Nenhum ativo encontrado para esta pesquisa.</p>';
  refreshMarketCompareToolbar();
}

// Abre a área de pesquisa e análise de mercado.
function openMarketResearch() {
  state.selected = null;
  document.querySelectorAll(".client-button").forEach((button) => button.classList.remove("active"));
  show("empty-state", false);
  show("client-view", false);
  show("market-view", true);
  refreshMarketAlertClients();
  refreshMarketWatchlistClients();
  loadMarketAlerts();
  loadMarketWatchlist();
  $("market-query").focus();
}

// Pesquisa ativos no Brasil ou no exterior e atualiza filtros/resultados.
async function searchMarket(event) {
  event.preventDefault();
  const query = $("market-query").value.trim();
  if (!query) { setFeedback("market-status", "Informe um ticker ou nome para pesquisar.", true); return; }
  resetMarketComparison();
  const button = $("market-search-button");
  button.disabled = true;
  button.textContent = "Pesquisando…";
  setFeedback("market-status", "Consultando dados de mercado…");
  $("market-warnings").innerHTML = "";
  try {
    const params = new URLSearchParams({ q: query, market: $("market-region").value });
    const data = await api(`/market/search?${params.toString()}`);
    state.marketResults = data.results || [];
    state.marketCompareKeys = [];
    state.marketTypeFilter = "all"; state.marketSectorFilter = "all"; state.marketSort = "relevance";
    refreshMarketFilters();
    renderMarketResults();
    $("market-updated").textContent = data.fetched_at ? `Atualizado ${formatDateTime(data.fetched_at)}` : "";
    if (data.warnings?.length) $("market-warnings").innerHTML = data.warnings.map((warning) => `<p class="market-warning">${escapeHtml(warning)}</p>`).join("");
    setFeedback("market-status", `${state.marketResults.length} ativo(s) encontrado(s).`);
  } catch (error) {
    state.marketResults = [];
    $("market-updated").textContent = "";
    $("market-warnings").innerHTML = "";
    renderMarketResults();
    setFeedback("market-status", error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Pesquisar";
  }
}

// Recarrega os dados principais sem perder a tela atualmente selecionada.
async function refreshWorkspace() {
  const button = $("refresh-workspace");
  const selectedId = state.selected?.id; // Se a seleção mudar durante os awaits, este valor antigo pode ser reaplicado (achado 12).
  button.disabled = true;
  button.textContent = "Atualizando…";
  try {
    state.clients = await api("/clients");
    if (state.userRole === "admin") {
      state.advisors = await api("/clients/advisors");
      state.team = await api("/admin/users?role=advisor");
      renderTeam();
    }
    renderClients();
    renderOverview();
    if (selectedId && state.clients.some((client) => client.id === selectedId)) {
      await selectClient(selectedId);
    } else if (selectedId) {
      state.selected = null;
      show("empty-state", true);
      show("client-view", false);
    }
    setFeedback("workspace-status", "Lista atualizada.");
  } catch (error) {
    setFeedback("workspace-status", error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Atualizar lista";
  }
}

// Atualiza a lista de assessores e seus estados de acesso.
function renderTeam() {
  $("team-list").innerHTML = state.team.length ? state.team.map((advisor) => `<article class="team-row"><div><strong>${escapeHtml(advisor.name)}</strong><small>${escapeHtml(advisor.email)}</small></div><div class="quick-record-actions"><span class="team-status ${advisor.is_active ? "active" : "inactive"}">${advisor.is_active ? "Ativo" : "Inativo"}</span><button class="button ghost small" data-team-status="${advisor.id}">${advisor.is_active ? "Desativar" : "Reativar"}</button><button class="button ghost small" data-team-reset="${advisor.id}">Redefinir senha</button></div></article>`).join("") : '<p class="empty-line">Nenhum Advisor cadastrado.</p>';
  document.querySelectorAll("[data-team-status]").forEach((button) => { button.onclick = () => toggleAdvisor(Number(button.dataset.teamStatus)); });
  document.querySelectorAll("[data-team-reset]").forEach((button) => { button.onclick = () => resetUserPassword(Number(button.dataset.teamReset), "Advisor"); });
}

// Abre o formulário de gerenciamento de equipe.
function openTeamDialog() {
  renderTeam();
  $("team-dialog").showModal();
}

// Fecha o formulário de gerenciamento de equipe.
function closeTeamDialog() {
  $("team-dialog").close();
}

// Ativa ou desativa a conta do assessor selecionado.
async function toggleAdvisor(advisorId) {
  const advisor = state.team.find((item) => item.id === advisorId);
  if (!advisor) return;
  try {
    await api(`/admin/users/${advisorId}/status`, { method: "PATCH", body: JSON.stringify({ is_active: !advisor.is_active }) });
    // O PATCH já foi confirmado; falhas nas recargas seguintes não desfazem a alteração (achado 28).
    state.team = await api("/admin/users?role=advisor");
    state.advisors = await api("/clients/advisors");
    renderOverview();
    renderTeam();
    if (state.selected && state.clientProfile) renderClientProfile(state.clientProfile);
  } catch (error) { window.alert(error.message); }
}

// Redefine a senha de uma conta pelo fluxo administrativo.
async function resetUserPassword(userId, label) {
  // O prompt nativo exibe a senha digitada sem máscara; usar diálogo com campo type=password (achado 192).
  const newPassword = window.prompt(`Digite a nova senha temporária do ${label} (mínimo de 8 caracteres):`);
  if (newPassword === null) return;
  const confirmation = window.prompt("Confirme a nova senha temporária:");
  if (newPassword !== confirmation) { window.alert("As senhas não conferem."); return; }
  // O handler valida o mínimo, mas deixa o máximo de 128 caracteres para o schema (achado 67).
  if (newPassword.length < 8) { window.alert("A senha precisa ter pelo menos 8 caracteres."); return; }
  try {
    await api(`/admin/users/${userId}/reset-password`, { method: "POST", body: JSON.stringify({ new_password: newPassword }) });
    window.alert("Senha redefinida. As sessões anteriores foram encerradas.");
  } catch (error) { window.alert(error.message); }
}

// Inicia a redefinição de senha do cliente atualmente selecionado.
function resetSelectedClientPassword() {
  if (state.selected) resetUserPassword(state.selected.id, "cliente");
}

// Carrega todos os módulos do cliente para o painel de acompanhamento. Chamadas após mutações devem preservar o ID original: reler state.selected.id depois de um await pode selecionar outro cliente (achado 12).
async function selectClient(id) {
  show("market-view", false);
  show("empty-state", false);
  show("client-view", true);
  if (state.editingReport) cancelReportEdit();
  if (state.editingPatrimony) cancelPatrimonyEdit();
  if (state.editingGoal) cancelGoalEdit();
  if (state.editingAction) cancelActionEdit();
  if (state.editingInvestmentPosition) cancelInvestmentPositionEdit();
  state.selected = state.clients.find((client) => client.id === id); // Até recarga concluída, os dados antigos ficam visíveis; falha mantém o estado anterior (achado 12).
  state.investmentAnalytics = null;
  state.investmentSnapshots = [];
  state.investmentMonthlyPerformance = null;
  renderInvestmentAnalytics(null);
  renderInvestmentSnapshots([]);
  renderInvestmentMonthlyPerformance(null);
  setFeedback("investment-monthly-status", "Carregando rendimento e comparação com o CDI...");
  document.querySelectorAll(".client-button").forEach((button) => button.classList.toggle("active", Number(button.dataset.id) === id));
  show("empty-state", false); show("client-view", true); $("client-name").textContent = state.selected.name; $("client-email").textContent = state.selected.email; $("client-status").textContent = state.selected.is_active ? "Ativo" : "Inativo";
  try {
    // A consulta de operações usa o limite padrão da API e não pagina o histórico.
    // Busca os módulos em paralelo; a seleção não é revalidada após o await (resposta cruzada: achado 12).
    const [dashboard, permissions, reports, documents, financialProfile, clientProfile, audit, patrimony, goals, actionPlan, investmentPortfolio, investmentTransactions, suitability] = await Promise.all([api(`/clients/${id}/dashboard`), api(`/clients/${id}/permissions`), api(`/clients/${id}/reports`), api(`/clients/${id}/documents`), api(`/clients/${id}/financial-profile`).catch((error) => { if (error.status === 404) return null; throw error; }), api(`/clients/${id}/profile`), api(`/clients/${id}/audit-log`), api(`/clients/${id}/patrimony`), api(`/clients/${id}/goals`), api(`/clients/${id}/action-plan`), api(`/clients/${id}/investment-portfolio`), api(`/clients/${id}/investment-transactions`), api(`/clients/${id}/suitability`).catch((error) => { if (error.status === 404) return null; throw error; })]);
    state.permissions = permissions; state.financialProfile = financialProfile; state.clientProfile = clientProfile; state.suitability = suitability; state.reports = reports; state.documents = documents; state.patrimony = patrimony; state.goals = goals; state.actionPlan = actionPlan; state.investmentPortfolio = investmentPortfolio; state.investmentTransactions = investmentTransactions; state.investmentMonthlyPerformance = null; renderDashboard(dashboard, reports); renderInvestmentPortfolio(investmentPortfolio); renderInvestmentTransactions(investmentTransactions); renderInvestmentHistoryCurrencies(investmentPortfolio); renderPermissions(permissions); renderFinancialProfile(financialProfile); renderSuitability(suitability); renderReports(reports); renderDocuments(documents); renderClientProfile(clientProfile); renderAudit(audit); renderQuickRecords(); renderActionPlan(); loadInvestmentMonthlyPerformance(id).catch(() => {}); // O erro desta atualização automática mantém o contador anterior até uma nova consulta (achado 146).
    refreshNotifications().catch(() => {}); // A falha conserva a lista e o contador conhecidos (achado 146).
  } catch (error) { setFeedback("permission-status", error.message, true); }
}

// Atualiza indicadores e blocos financeiros do cliente.
function renderDashboard(dashboard, reports) {
  // A resposta usa null para perfil ausente; este fallback atual mostra zero no resumo (achado 142).
  const monthlyIncome = Number(dashboard.monthly_income || 0); const monthlyExpenses = Number(dashboard.monthly_expenses || 0); const balance = monthlyIncome - monthlyExpenses;
  $("patrimony-total").textContent = money(dashboard.patrimony_total); $("monthly-income-total").textContent = money(monthlyIncome); $("monthly-expenses-total").textContent = money(monthlyExpenses); $("monthly-balance-total").textContent = money(balance); $("monthly-balance-total").classList.toggle("negative", balance < 0); $("goals-count").textContent = dashboard.goals.filter((goal) => goal.status === "active").length; $("reports-count").textContent = reports.filter((report) => report.status === "published").length; $("actions-pending-count").textContent = dashboard.action_pending ?? 0; $("actions-overdue-count").textContent = dashboard.action_overdue ?? 0;
  $("categories").innerHTML = dashboard.patrimony_by_category.length ? dashboard.patrimony_by_category.map((item) => `<div class="category-row"><div class="row-top"><span>${escapeHtml(item.category)}</span><strong>${money(item.total)}</strong></div><div class="bar"><i style="width:${item.percentage}%"></i></div></div>`).join("") : '<p class="empty-line">Nenhum patrimônio cadastrado.</p>';
  $("goals").innerHTML = dashboard.goals.length ? dashboard.goals.map((goal) => `<div class="goal-row"><div class="row-top"><span>${escapeHtml(goal.title)}</span><strong>${goal.percentage}%</strong></div><div class="bar"><i style="width:${goal.percentage}%"></i></div><small class="muted">${money(goal.current_value)} de ${money(goal.target_value)}${goal.target_date ? ` · até ${formatDate(goal.target_date)}` : ""}${isGoalOverdue(goal.target_date, goal.status) ? ' · <span class="overdue-label">Prazo vencido</span>' : ""}</small></div>`).join("") : '<p class="empty-line">Nenhuma meta cadastrada.</p>';
}

// Formata um valor da carteira conforme a moeda informada.
function portfolioMoney(value, currency) {
  const safeCurrency = currency === "USD" || currency === "US$" ? "USD" : "BRL";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: safeCurrency }).format(Number(value || 0));
}

// Obtém o valor de mercado da posição com fallback definido.
function portfolioValue(position) {
  return position.current_value == null ? "Cotação indisponível" : portfolioMoney(position.current_value, position.currency);
}

// Calcula ou apresenta o resultado financeiro da posição.
function portfolioPnl(position) {
  if (position.pnl == null) return "Resultado indisponível";
  const value = portfolioMoney(position.pnl, position.currency);
  return (Number(position.pnl) >= 0 ? "+" : "") + value + " (" + Number(position.pnl_percent || 0).toFixed(2).replace(".", ",") + "%)";
}

// Exibe posições, valores, variação e distribuição da carteira do cliente.
function renderInvestmentPortfolio(portfolio) {
  state.investmentPortfolio = portfolio;
  const mixedCurrency = portfolio.mixed_currency === true;
  $("investment-invested-total").textContent = mixedCurrency ? "Ver por moeda" : money(portfolio.invested_total);
  $("investment-current-total").textContent = mixedCurrency ? "Ver por moeda" : money(portfolio.current_total);
  $("investment-pnl-total").textContent = mixedCurrency ? "Ver por moeda" : (Number(portfolio.pnl_total) >= 0 ? "+" : "") + money(portfolio.pnl_total) + (portfolio.pnl_percent == null ? "" : " (" + Number(portfolio.pnl_percent).toFixed(2).replace(".", ",") + "%)");
  $("investment-pnl-total").classList.toggle("negative", !mixedCurrency && Number(portfolio.pnl_total) < 0);
  $("investment-position-count").textContent = String(portfolio.position_count) + (portfolio.unpriced_position_count ? " · " + portfolio.unpriced_position_count + " sem cotação" : "");
  $("investment-currency-totals").innerHTML = (portfolio.currency_totals || []).map((item) => "<div class=\"investment-currency-total\"><strong>" + escapeHtml(item.currency) + "</strong><span>Investido: " + portfolioMoney(item.invested_total, item.currency) + " · Atualizado: " + portfolioMoney(item.current_total, item.currency) + " · Resultado: " + (Number(item.pnl_total) >= 0 ? "+" : "") + portfolioMoney(item.pnl_total, item.currency) + "</span></div>").join("");
  $("investment-allocations").innerHTML = portfolio.allocations?.length ? portfolio.allocations.map((item) => "<div class=\"investment-allocation\"><div class=\"row-top\"><span>" + escapeHtml(item.label) + "</span><strong>" + Number(item.percentage).toFixed(2).replace(".", ",") + "%</strong></div><div class=\"bar\"><i style=\"width:" + Math.min(100, Number(item.percentage)) + "%\"></i></div><small class=\"muted\">" + money(item.value) + "</small></div>").join("") : "";
  const positions = portfolio.positions || [];
  renderInvestmentAllocationChart(positions);
  // Monta um cartão por posição e identifica se seu saldo já é controlado pelo histórico de operações.
  $("investment-position-list").innerHTML = positions.length ? positions.map((item) => {
    // A busca usa somente as operações carregadas; registros antigos podem ficar fora dos 100 iniciais.
    const hasOperations = (state.investmentTransactions || []).some((transaction) => transaction.position_id === item.id);
    return "<article class=\"investment-position-row\"><div><div class=\"investment-position-heading\"><strong>" + escapeHtml(item.symbol) + "</strong><span class=\"market-badge " + (item.market === "br" ? "br" : "global") + "\">" + (item.market === "br" ? "B3" : "Exterior") + "</span></div><small class=\"muted\">" + escapeHtml(item.name || "Ativo") + " · " + Number(item.quantity).toLocaleString("pt-BR", { maximumFractionDigits: 8 }) + " cotas · médio " + portfolioMoney(item.average_price, item.currency) + "</small><small class=\"muted\">" + (item.institution ? escapeHtml(item.institution) + " · " : "") + "Atual: " + portfolioValue(item) + " · " + portfolioPnl(item) + "</small>" + (item.notes ? "<small class=\"muted\">" + escapeHtml(item.notes) + "</small>" : "") + (hasOperations ? "<small class=\"muted\">Saldo controlado pelo histórico de operações.</small>" : "") + "</div>" + (hasOperations ? "" : "<div class=\"quick-record-actions\"><button class=\"button ghost small\" type=\"button\" data-investment-edit=\"" + item.id + "\">Editar</button><button class=\"button ghost small\" type=\"button\" data-investment-delete=\"" + item.id + "\">Remover</button></div>") + "</article>";
  }).join("") : "<p class=\"empty-line\">Nenhuma posição de investimento cadastrada.</p>";
  document.querySelectorAll("[data-investment-edit]").forEach((button) => { button.onclick = () => startInvestmentPositionEdit(positions.find((item) => item.id === Number(button.dataset.investmentEdit))); });
  document.querySelectorAll("[data-investment-delete]").forEach((button) => { button.onclick = () => deleteInvestmentPosition(Number(button.dataset.investmentDelete)); });
}

// Mostra a composição por ativo, mantendo cada moeda em seu próprio gráfico.
function renderInvestmentAllocationChart(positions) {
  const container = $("investment-allocation-chart");
  const palette = ["#17324D", "#167C76", "#D18A34", "#C95F6D", "#4A82B8", "#728FA4", "#55A66E", "#D07842", "#4C9EAA", "#967D55"];
  const currencies = new Map();
  (positions || []).forEach((position) => {
    const value = Number(position.current_value);
    if (!Number.isFinite(value) || value <= 0) return;
    const currency = position.currency || (position.market === "br" ? "BRL" : "USD");
    if (!currencies.has(currency)) currencies.set(currency, []);
    currencies.get(currency).push({ ...position, chartValue: value });
  });
  if (!currencies.size) {
    container.innerHTML = '<p class="empty-line">Nenhuma posição com cotação disponível para o gráfico.</p>';
    return;
  }
  container.innerHTML = Array.from(currencies.entries()).map(([currency, items]) => {
    const total = items.reduce((sum, item) => sum + item.chartValue, 0);
    let angle = 0;
    const slices = items.map((item, index) => {
      const start = angle;
      angle += item.chartValue / total * 100;
      return { item, index, start, end: angle, percent: item.chartValue / total * 100 };
    });
    const gradient = slices.map((slice) => `${palette[slice.index % palette.length]} ${slice.start.toFixed(3)}% ${slice.end.toFixed(3)}%`).join(", ");
    const legend = slices.map(({ item, index }) => `<div class="investment-donut-entry"><button class="investment-donut-legend-row" type="button" aria-expanded="false"><i style="--legend-color:${palette[index % palette.length]}"></i><span><strong>${escapeHtml(item.symbol)}</strong></span><b>${portfolioMoney(item.chartValue, currency)}</b></button><small class="investment-donut-full-name hidden">${escapeHtml(item.name || "Nome do ativo não informado")}</small></div>`).join("");
    return `<article class="investment-donut-group"><div class="investment-donut" style="--donut:conic-gradient(${gradient})" role="img" aria-label="Composição da carteira em ${escapeHtml(currency)}"><span><small>${escapeHtml(currency)}</small><strong>${portfolioMoney(total, currency)}</strong></span></div><div class="investment-donut-legend">${legend}</div></article>`;
  }).join("");
  // Ao expandir uma legenda, mantém aria-expanded sincronizado com a exibição do nome completo.
  container.querySelectorAll(".investment-donut-legend-row").forEach((button) => {
    button.addEventListener("click", () => {
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!expanded));
      button.nextElementSibling.classList.toggle("hidden", expanded);
    });
  });
}

// Desenha rendimento mensal e comparação com referência de mercado.
function renderInvestmentMonthlyPerformance(performance) {
  state.investmentMonthlyPerformance = performance;
  const chart = $("investment-monthly-chart");
  if (!performance?.currencies?.length) {
    chart.innerHTML = '<p class="empty-line">Ainda não há dados de rendimento para este mês.</p>';
    return;
  }
  const groups = performance.currencies.map((item) => {
    if (!item.data_available || !item.points?.length) {
      return `<article class="investment-monthly-currency"><h4>${escapeHtml(item.currency)}</h4><p class="muted">Dados insuficientes para calcular o rendimento. ${item.source_status === "partial" ? "Há posições sem cotação ou snapshots incompletos." : "Registre snapshots em dias diferentes para formar o histórico."}</p></article>`;
    }
    const points = item.points;
    // Traça valores absolutos da série, que o backend já mantém separados por moeda.
    const values = points.map((point) => Number(point.profit_value));
    const min = Math.min(0, ...values);
    const max = Math.max(0, ...values);
    const spread = max - min || 1;
    // Calcula a coordenada horizontal de um mês no gráfico.
    const x = (index) => 28 + (points.length === 1 ? 0 : index * 584 / (points.length - 1));
    // Mapeia um rendimento mensal para a coordenada vertical do gráfico.
    const y = (value) => 166 - ((value - min) / spread) * 128;
    const line = points.map((point, index) => `${x(index).toFixed(1)},${y(Number(point.profit_value)).toFixed(1)}`).join(" ");
    const zeroY = y(0).toFixed(1);
    const chartSvg = `<svg class="investment-monthly-svg" viewBox="0 0 640 210" role="img" aria-label="Evolução do rendimento em ${escapeHtml(item.currency)} no mês"><line x1="28" y1="38" x2="612" y2="38" class="investment-monthly-grid"/><line x1="28" y1="102" x2="612" y2="102" class="investment-monthly-grid"/><line x1="28" y1="166" x2="612" y2="166" class="investment-monthly-grid"/><line x1="28" y1="${zeroY}" x2="612" y2="${zeroY}" class="investment-monthly-zero"/><polyline points="${line}" class="investment-monthly-line"/>${points.map((point, index) => `<circle cx="${x(index).toFixed(1)}" cy="${y(Number(point.profit_value)).toFixed(1)}" r="3.5" class="investment-monthly-point"><title>${formatDate(point.date)} · ${portfolioMoney(point.profit_value, item.currency)}</title></circle>`).join("")}<text x="28" y="194" class="investment-monthly-axis">${formatDate(points[0].date)}</text><text x="612" y="194" text-anchor="end" class="investment-monthly-axis">${formatDate(points[points.length - 1].date)}</text></svg>`;
    // Mostra a diferença em pontos percentuais; o percentual do retorno sobre o CDI ainda não é exibido (achado 177).
    const excess = item.excess_percentage_points == null ? "—" : `${Number(item.excess_percentage_points) >= 0 ? "+" : ""}${Number(item.excess_percentage_points).toFixed(2).replace(".", ",")} p.p.`;
    const cdi = item.cdi_percent == null ? "Indisponível" : `${Number(item.cdi_percent).toFixed(2).replace(".", ",")}%`;
    const coverage = item.full_month_to_date ? "mês completo até hoje" : `desde ${formatDate(item.coverage_start)}`;
    return `<article class="investment-monthly-currency"><div class="investment-monthly-heading"><h4>${escapeHtml(item.currency)} · ${escapeHtml(coverage)}</h4><span>${item.source_status === "complete" ? "dados completos" : "dados parciais"}</span></div><div class="investment-monthly-stats"><div><small>Rendimento no mês</small><strong>${portfolioMoney(item.profit_value, item.currency)}</strong></div><div><small>Retorno</small><strong>${Number(item.return_percent).toFixed(2).replace(".", ",")}%</strong></div><div><small>CDI no período</small><strong>${cdi}</strong></div><div><small>Acima do CDI</small><strong>${excess}</strong></div></div>${chartSvg}</article>`;
  }).join("");
  chart.innerHTML = groups;
}

// Carrega a série mensal de desempenho para o cliente selecionado.
async function loadInvestmentMonthlyPerformance(clientId = state.selected?.id) {
  if (!clientId) return;
  const button = $("investment-monthly-load");
  if (button) { button.disabled = true; button.textContent = "Atualizando…"; }
  setFeedback("investment-monthly-status", "Atualizando snapshots e consultando o CDI...");
  try {
    const performance = await api(`/clients/${clientId}/investment-monthly-performance`);
    if (state.selected?.id !== clientId) return;
    renderInvestmentMonthlyPerformance(performance);
    const cdiDate = performance.cdi_as_of ? ` CDI atualizado até ${formatDate(performance.cdi_as_of)}.` : " CDI indisponível no momento.";
    const status = performance.cdi_status === "cached" ? "Dados recentes do CDI em cache." : performance.cdi_status === "unavailable" ? "A fonte do CDI está indisponível." : "Dados do CDI atualizados.";
    setFeedback("investment-monthly-status", `${performance.month} · ${status}${cdiDate}`);
  } catch (error) {
    if (state.selected?.id === clientId) setFeedback("investment-monthly-status", error.message, true);
  } finally {
    if (button) { button.disabled = false; button.textContent = "Atualizar"; }
  }
}

// Atualiza a lista do histórico de operações de investimento.
function renderInvestmentTransactions(transactions) {
  const rows = transactions || [];
  $("investment-transaction-list").innerHTML = rows.length ? rows.map((item) => {
    const label = item.operation_type === "buy" ? "Compra" : "Venda";
    const operationValue = portfolioMoney(item.net_value, item.currency);
    const realized = item.realized_pnl == null || item.voided_at ? "" : " · resultado realizado " + (Number(item.realized_pnl) >= 0 ? "+" : "") + portfolioMoney(item.realized_pnl, item.currency);
    const voided = item.voided_at ? "<small class=\"muted\">Operação anulada · " + escapeHtml(item.void_reason || "") + "</small>" : "<button class=\"button ghost small\" type=\"button\" data-investment-transaction-void=\"" + item.id + "\">Anular</button>";
    return "<article class=\"investment-transaction-row\"><div><strong>" + label + " · " + escapeHtml(item.symbol) + "</strong><small class=\"muted\">" + formatDate(item.operation_date) + " · " + escapeHtml(item.market === "br" ? "B3" : "Exterior") + "</small></div><div><small>" + Number(item.quantity).toLocaleString("pt-BR", { maximumFractionDigits: 8 }) + " cotas × " + portfolioMoney(item.unit_price, item.currency) + "</small><small class=\"muted\">Bruto " + portfolioMoney(item.gross_value, item.currency) + " · taxas " + portfolioMoney(item.fees, item.currency) + realized + "</small></div><div class=\"investment-transaction-value\"><strong>" + operationValue + "</strong><small class=\"muted\">" + (item.operation_type === "buy" ? "total da compra" : "valor líquido da venda") + "</small>" + voided + "</div></article>";
  }).join("") : '<p class="empty-line">Nenhuma operação registrada. Saldos cadastrados manualmente não têm histórico anterior.</p>';
  document.querySelectorAll("[data-investment-transaction-void]").forEach((button) => { button.onclick = () => voidInvestmentTransaction(Number(button.dataset.investmentTransactionVoid)); });
}

// Formata um indicador numérico como percentual.
function analyticsPercent(value) {
  if (value == null) return "—";
  return (Number(value) >= 0 ? "+" : "") + Number(value).toFixed(2).replace(".", ",") + "%";
}

// Apresenta indicadores consolidados da carteira do cliente.
function renderInvestmentAnalytics(analytics) {
  state.investmentAnalytics = analytics;
  const summary = $("investment-analytics-summary");
  const flags = $("investment-analytics-flags");
  const list = $("investment-analytics-list");
  const exportButton = $("investment-analytics-export");
  if (!analytics) {
    summary.innerHTML = "";
    flags.innerHTML = "";
    list.innerHTML = "";
    if (exportButton) exportButton.disabled = true;
    return;
  }
  summary.innerHTML = (analytics.currency_summaries || []).map((item) => "<article><small class=\"muted\">" + escapeHtml(item.currency) + " · retorno ponderado</small><strong>" + analyticsPercent(item.portfolio_return_percent) + "</strong><span>Concentração máxima: " + Number(item.top_concentration_percent).toFixed(2).replace(".", ",") + "%</span></article>").join("") + (analytics.benchmarks || []).map((item) => "<article><small class=\"muted\">" + escapeHtml(item.label) + " · referência</small><strong>" + (item.data_available ? analyticsPercent(item.return_percent) : "Sem dados") + "</strong><span>Período: " + escapeHtml(analytics.period) + "</span></article>").join("");
  flags.innerHTML = (analytics.risk_flags || []).map((flag) => "<p class=\"investment-analytics-flag\">" + escapeHtml(flag) + "</p>").join("");
  list.innerHTML = analytics.positions?.length ? analytics.positions.map((item) => "<article class=\"investment-analytics-row\"><div><div class=\"investment-position-heading\"><strong>" + escapeHtml(item.symbol) + "</strong><span class=\"market-badge " + (item.market === "br" ? "br" : "global") + "\">" + (item.market === "br" ? "B3" : "Exterior") + "</span></div><small class=\"muted\">" + escapeHtml(item.currency) + " · alocação " + Number(item.allocation_percent).toFixed(2).replace(".", ",") + "%</small></div><div class=\"investment-analytics-metrics\"><span>Retorno: <strong>" + analyticsPercent(item.period_return_percent) + "</strong></span><span>Contribuição: <strong>" + analyticsPercent(item.contribution_percent) + "</strong></span></div></article>").join("") : "<p class=\"empty-line\">Nenhuma posição disponível para análise.</p>";
  if (exportButton) exportButton.disabled = false;
}

// Formata a data de captura do histórico da carteira.
function formatSnapshotDate(value) {
  return value ? new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : "—";
}

// Organiza histórico e valores da carteira por moeda.
function renderInvestmentHistoryCurrencies(portfolio) {
  const select = $("investment-history-currency");
  if (!select) return;
  // Extrai as moedas disponíveis para alimentar o filtro do histórico.
  const currencies = (portfolio?.currency_totals || []).map((item) => item.currency);
  // Cria uma opção para cada moeda disponível na composição da carteira.
  select.innerHTML = '<option value="">Todas as moedas</option>' + currencies.map((currency) => '<option value="' + escapeHtml(currency) + '">' + escapeHtml(currency) + '</option>').join("");
}

// Desenha a evolução histórica registrada da carteira.
function renderInvestmentSnapshots(snapshots) {
  state.investmentSnapshots = snapshots || [];
  const summary = $("investment-history-summary");
  const list = $("investment-history-list");
  if (!summary || !list) return;
  if (!state.investmentSnapshots.length) {
    summary.innerHTML = "";
    list.innerHTML = '<p class="empty-line">Nenhum snapshot encontrado para este filtro.</p>';
    return;
  }
  const latestByCurrency = new Map();
  state.investmentSnapshots.forEach((item) => latestByCurrency.set(item.currency, item));
  summary.innerHTML = Array.from(latestByCurrency.values()).map((item) => '<article><small class="muted">' + escapeHtml(item.currency) + ' · último registro</small><strong>' + portfolioMoney(item.current_total, item.currency) + '</strong><span>' + formatSnapshotDate(item.captured_at) + ' · ' + (item.source_status === "complete" ? "dados completos" : "dados parciais") + '</span></article>').join("");
  list.innerHTML = state.investmentSnapshots.slice().reverse().map((item) => '<article class="investment-history-row"><div><strong>' + escapeHtml(item.currency) + '</strong><small class="muted">' + formatSnapshotDate(item.captured_at) + ' · ' + item.priced_position_count + '/' + item.position_count + ' posições cotadas</small></div><div class="investment-analytics-metrics"><span>Atualizado: <strong>' + portfolioMoney(item.current_total, item.currency) + '</strong></span><span>Resultado: <strong class="' + (Number(item.pnl_total) < 0 ? "negative" : "") + '">' + (Number(item.pnl_total) >= 0 ? "+" : "") + portfolioMoney(item.pnl_total, item.currency) + '</strong></span></div></article>').join("");
}

// Busca fotografias históricas da carteira no backend.
async function loadInvestmentSnapshots() {
  if (!state.selected) return;
  const button = $("investment-history-load");
  if (button) { button.disabled = true; button.textContent = "Atualizando…"; }
  setFeedback("investment-history-status", "Consultando o histórico salvo da carteira...");
  try {
    const currency = $("investment-history-currency").value;
    const suffix = currency ? "&currency=" + encodeURIComponent(currency) : "";
    const snapshots = await api("/clients/" + state.selected.id + "/investment-snapshots?limit=90" + suffix);
    renderInvestmentSnapshots(snapshots);
    setFeedback("investment-history-status", snapshots.length ? "Histórico atualizado." : "Ainda não há registros para este filtro.");
  } catch (error) { setFeedback("investment-history-status", error.message, true); }
  finally { if (button) { button.disabled = false; button.textContent = "Atualizar histórico"; } }
}

// Salva uma fotografia temporal da carteira para formar o histórico de evolução.
async function captureInvestmentSnapshot() {
  if (!state.selected) return;
  const button = $("investment-history-capture");
  if (button) { button.disabled = true; button.textContent = "Capturando…"; }
  setFeedback("investment-history-status", "Atualizando cotações e registrando a carteira...");
  try {
    const snapshots = await api("/clients/" + state.selected.id + "/investment-snapshots/capture", { method: "POST" });
    // O carregador trata falhas do GET internamente; a confirmação abaixo pode substituir esse aviso.
    await loadInvestmentSnapshots();
    setFeedback("investment-history-status", snapshots.length ? "Snapshot registrado com sucesso." : "A carteira já possui um registro recente ou não tem posições.");
  } catch (error) { setFeedback("investment-history-status", error.message, true); }
  finally { if (button) { button.disabled = false; button.textContent = "Capturar agora"; } }
}

// Consulta históricos e benchmarks para gerar a análise comparativa da carteira.
async function loadInvestmentAnalytics() {
  if (!state.selected) return;
  const period = $("investment-analytics-period").value;
  const button = $("investment-analytics-load");
  if (button) { button.disabled = true; button.textContent = "Calculando…"; }
  setFeedback("investment-analytics-status", "Consultando históricos dos ativos e benchmarks...");
  try {
    const analytics = await api("/clients/" + state.selected.id + "/investment-analytics?period=" + encodeURIComponent(period));
    renderInvestmentAnalytics(analytics);
    setFeedback("investment-analytics-status", "Análise calculada com dados disponíveis para o período.");
  } catch (error) { setFeedback("investment-analytics-status", error.message, true); }
  finally { if (button) { button.disabled = false; button.textContent = "Calcular análise"; } }
}

// Exporta indicadores calculados para análise posterior.
function exportInvestmentAnalytics() {
  const analytics = state.investmentAnalytics;
  if (!analytics || !state.selected) return;
  const reportWindow = window.open("", "_blank");
  if (!reportWindow) { setFeedback("investment-analytics-status", "Permita pop-ups para exportar a análise.", true); return; }
  // Converte cada posição do resultado em uma linha da tabela de impressão.
  const rows = (analytics.positions || []).map((item) => "<tr><td>" + escapeHtml(item.symbol) + "</td><td>" + escapeHtml(item.currency) + "</td><td>" + analyticsPercent(item.allocation_percent) + "</td><td>" + analyticsPercent(item.period_return_percent) + "</td><td>" + analyticsPercent(item.contribution_percent) + "</td></tr>").join("");
  // Transforma alertas de risco em itens da lista do relatório.
  const flags = (analytics.risk_flags || []).map((flag) => "<li>" + escapeHtml(flag) + "</li>").join("");
  reportWindow.document.write("<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><title>Talentum — Análise da carteira</title><style>body{font:14px/1.5 Arial,sans-serif;color:#1F2B35;padding:34px}h1{margin:0 0 5px}h2{margin-top:28px}small{color:#63717D}.header{border-bottom:2px solid #17324D;padding-bottom:16px}table{width:100%;border-collapse:collapse;font-size:12px;margin-top:12px}th,td{text-align:left;padding:9px;border-bottom:1px solid #DCE4E8}th{background:#F7F9FA}.disclaimer{margin-top:28px;color:#63717D;font-size:11px}@media print{body{padding:0}}</style></head><body><div class=\"header\"><h1>Talentum — Análise da carteira</h1><small>Cliente: " + escapeHtml(state.selected.name) + " · Período: " + escapeHtml(analytics.period) + " · Gerado em: " + escapeHtml(new Date(analytics.generated_at).toLocaleString("pt-BR")) + "</small></div><h2>Posições</h2><table><thead><tr><th>Ativo</th><th>Moeda</th><th>Alocação</th><th>Retorno</th><th>Contribuição</th></tr></thead><tbody>" + rows + "</tbody></table><h2>Alertas de leitura</h2><ul>" + (flags || "<li>Nenhum alerta de concentração ou disponibilidade.</li>") + "</ul><p class=\"disclaimer\">Dados informativos, sujeitos a atraso e à disponibilidade dos provedores. Este material não constitui recomendação de investimento.</p></body></html>");
  reportWindow.document.close(); reportWindow.focus(); reportWindow.print();
}

// Valida e cadastra uma posição de investimento.
async function addInvestmentPosition(event) {
  event.preventDefault();
  if (!state.selected) return;
  const quantity = Number($("investment-quantity").value);
  const averagePrice = Number($("investment-average-price").value);
  if (!$("investment-symbol").value.trim() || !Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(averagePrice) || averagePrice <= 0) {
    setFeedback("investment-position-status", "Informe ticker, quantidade e preço médio válidos.", true);
    return;
  }
  try {
    const payload = { symbol: $("investment-symbol").value.trim(), name: $("investment-name").value.trim() || null, market: $("investment-market").value, quantity, average_price: averagePrice, institution: $("investment-institution").value.trim() || null, notes: $("investment-notes").value.trim() || null };
    const editing = Boolean(state.editingInvestmentPosition);
    await api(editing ? "/clients/" + state.selected.id + "/investment-positions/" + state.editingInvestmentPosition.id : "/clients/" + state.selected.id + "/investment-positions", { method: editing ? "PATCH" : "POST", body: JSON.stringify(editing ? { symbol: payload.symbol, name: payload.name, market: payload.market, quantity, average_price: averagePrice, institution: payload.institution, notes: payload.notes } : payload) });
    cancelInvestmentPositionEdit(false);
    setFeedback("investment-position-status", editing ? "Posição atualizada." : "Posição adicionada.");
    await selectClient(state.selected.id); // A mutação da posição já foi concluída; falha nesta recarga pode mostrar erro depois da gravação (achado 28).
  } catch (error) { setFeedback("investment-position-status", error.message, true); }
}

// Registra uma operação e atualiza a posição correspondente.
async function addInvestmentTransaction(event) {
  event.preventDefault();
  if (!state.selected) return;
  const submitButton = $("investment-transaction-form").querySelector("button[type='submit']");
  if (submitButton.disabled) return;
  const quantity = Number($("investment-transaction-quantity").value);
  const unitPrice = Number($("investment-transaction-price").value);
  const fees = Number($("investment-transaction-fees").value || 0);
  const operationDate = $("investment-transaction-date").value;
  if (!$("investment-transaction-symbol").value.trim() || !operationDate || !Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(unitPrice) || unitPrice <= 0 || !Number.isFinite(fees) || fees < 0) {
    setFeedback("investment-transaction-status", "Informe ativo, data, quantidade, preço e taxas válidos.", true);
    return;
  }
  submitButton.disabled = true;
  try {
    const payload = {
      operation_type: $("investment-transaction-type").value,
      symbol: $("investment-transaction-symbol").value.trim(),
      name: $("investment-transaction-name").value.trim() || null,
      market: $("investment-transaction-market").value,
      operation_date: operationDate,
      quantity,
      unit_price: unitPrice,
      fees,
      institution: $("investment-transaction-institution").value.trim() || null,
      notes: $("investment-transaction-notes").value.trim() || null,
    };
    const transaction = await api("/clients/" + state.selected.id + "/investment-transactions", { method: "POST", body: JSON.stringify(payload) });
    $("investment-transaction-form").reset();
    $("investment-transaction-date").value = localDateInputValue();
    $("investment-transaction-market").value = "br";
    $("investment-transaction-fees").value = "0";
    const feedback = transaction.realized_pnl == null ? "" : " Resultado realizado: " + portfolioMoney(transaction.realized_pnl, transaction.currency) + ".";
    setFeedback("investment-transaction-status", "Operação registrada." + feedback);
    await selectClient(state.selected.id);
  } catch (error) { setFeedback("investment-transaction-status", error.message, true); }
  finally { submitButton.disabled = false; }
}

// Cancela logicamente uma operação do histórico.
async function voidInvestmentTransaction(transactionId) {
  if (!state.selected || !window.confirm("Anular esta operação e recalcular o saldo e o custo médio?")) return;
  const reason = window.prompt("Informe o motivo da anulação (mínimo de 10 caracteres):")?.trim();
  if (!reason || reason.length < 10) {
    setFeedback("investment-transaction-status", "Informe um motivo com pelo menos 10 caracteres.", true);
    return;
  }
  // O botão da linha segue ativo durante o POST; cliques repetidos podem receber 409 após a primeira anulação (achado 196).
  try {
    await api("/clients/" + state.selected.id + "/investment-transactions/" + transactionId + "/void", { method: "POST", body: JSON.stringify({ reason }) });
    setFeedback("investment-transaction-status", "Operação anulada e saldo recalculado.");
    await selectClient(state.selected.id);
  } catch (error) { setFeedback("investment-transaction-status", error.message, true); }
}

// Gera a data local no formato aceito por um campo date.
function localDateInputValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

// Carrega os dados da posição no formulário de edição.
function startInvestmentPositionEdit(item) {
  if (!item) return;
  state.editingInvestmentPosition = item;
  $("investment-symbol").value = item.symbol;
  $("investment-name").value = item.name || "";
  $("investment-market").value = item.market;
  $("investment-quantity").value = item.quantity;
  $("investment-average-price").value = item.average_price;
  $("investment-institution").value = item.institution || "";
  $("investment-notes").value = item.notes || "";
  $("investment-position-submit").textContent = "Salvar alterações";
  show("investment-position-cancel", true);
  $("investment-position-form").scrollIntoView({ behavior: "smooth", block: "center" });
}

// Cancela a edição da posição e limpa mensagens se solicitado.
function cancelInvestmentPositionEdit(clearStatus = true) {
  state.editingInvestmentPosition = null;
  $("investment-position-form").reset();
  $("investment-market").value = "br";
  $("investment-position-submit").textContent = "Adicionar posição";
  show("investment-position-cancel", false);
  if (clearStatus) $("investment-position-status").textContent = "";
}

// Remove a posição após confirmar a operação.
async function deleteInvestmentPosition(positionId) {
  if (!state.selected || !window.confirm("Remover esta posição da carteira?")) return;
  // O botão permanece ativo durante a chamada; uma segunda exclusão após o commit pode receber 404.
  try {
    await api("/clients/" + state.selected.id + "/investment-positions/" + positionId, { method: "DELETE" });
    setFeedback("investment-position-status", "Posição removida.");
    await selectClient(state.selected.id);
  } catch (error) { setFeedback("investment-position-status", error.message, true); }
}

// Desenha relatórios disponíveis e seus estados de publicação.
function renderReports(reports) {
  const filter = $("report-filter").value;
  const visibleReports = filter === "all" ? reports : reports.filter((report) => report.status === filter);
  $("reports-list").innerHTML = visibleReports.length ? visibleReports.map((report) => `<article class="report-row"><div class="report-row-heading"><strong>${escapeHtml(report.title)}</strong><span class="report-status ${report.status}">${report.status === "published" ? "Publicado" : "Rascunho"}</span></div><div class="muted">${formatDate(report.period_start)} a ${formatDate(report.period_end)}</div><p>${escapeHtml(report.summary)}</p><div class="quick-record-actions"><button class="button ghost small report-edit-button" data-report-edit="${report.id}">Editar</button>${report.status === "draft" ? `<button class="button ghost small" data-report-delete="${report.id}">Remover</button>` : ""}</div></article>`).join("") : '<p class="empty-line">Nenhum relatório neste filtro.</p>';
  document.querySelectorAll("[data-report-edit]").forEach((button) => { button.onclick = () => editReport(reports.find((report) => report.id === Number(button.dataset.reportEdit))); });
  document.querySelectorAll("[data-report-delete]").forEach((button) => { button.onclick = () => deleteReport(Number(button.dataset.reportDelete)); });
}

// Formata tamanho de arquivo para leitura humana.
function formatBytes(value) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Atualiza o texto do seletor para confirmar visualmente o arquivo escolhido.
function updateDocumentFileName() {
  const file = $("document-file").files[0];
  $("document-file-name").textContent = file ? file.name : "Nenhum arquivo selecionado";
}

// Atualiza a lista de documentos do cliente.
function renderDocuments(documents) {
  const kindLabels = { identification: "Identificação", income_proof: "Comprovante de renda", address_proof: "Comprovante de endereço", other: "Outro documento" };
  $("documents-list").innerHTML = documents.length ? documents.map((item) => `<article class="quick-record document-record"><div><strong>${escapeHtml(item.original_name)}</strong><small class="muted">${escapeHtml(kindLabels[item.kind] || kindLabels.other)} · ${formatBytes(item.size_bytes)} · ${formatDate(item.created_at)}${item.description ? ` · ${escapeHtml(item.description)}` : ""}</small></div><div class="quick-record-actions"><button class="button ghost small" data-document-download="${item.id}" data-document-name="${escapeHtml(item.original_name)}">Baixar</button><button class="button ghost small" data-document-delete="${item.id}">Remover</button></div></article>`).join("") : '<p class="empty-line">Nenhum documento enviado.</p>';
  document.querySelectorAll("[data-document-download]").forEach((button) => { button.onclick = () => downloadDocument(Number(button.dataset.documentDownload), button.dataset.documentName); });
  document.querySelectorAll("[data-document-delete]").forEach((button) => { button.onclick = () => deleteDocument(Number(button.dataset.documentDelete)); });
}

// Envia documentos com multipart e atualiza a lista após a validação do backend.
async function uploadDocument(event) {
  event.preventDefault();
  if (!state.selected) return;
  const file = $("document-file").files[0];
  if (!file) { setFeedback("document-status", "Selecione um arquivo.", true); return; }
  // Repete o limite da API para dar retorno imediato; o backend também conta o stream recebido.
  if (file.size > 10 * 1024 * 1024) { setFeedback("document-status", "O arquivo excede o limite de 10 MB.", true); return; }
  const formData = new FormData();
  formData.append("file", file);
  formData.append("kind", $("document-kind").value);
  formData.append("description", $("document-description").value.trim());
  try {
    await api(`/clients/${state.selected.id}/documents`, { method: "POST", body: formData });
    $("document-form").reset();
    updateDocumentFileName();
    setFeedback("document-status", "Documento enviado com sucesso.");
    await selectClient(state.selected.id); // O upload já foi confirmado; falha nesta recarga pode mostrar erro após o documento ter sido gravado (achado 28).
  } catch (error) { setFeedback("document-status", error.message, true); }
}

// Baixa um documento autorizado para consulta local.
async function downloadDocument(documentId, originalName) {
  if (!state.selected) return;
  try {
    const blob = await api(`/clients/${state.selected.id}/documents/${documentId}/download`, { responseType: "blob" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = originalName || "documento"; link.click();
    // A revogação imediata pode ocorrer antes de o navegador iniciar o download assíncrono (achado 198).
    URL.revokeObjectURL(url);
  } catch (error) { setFeedback("document-status", error.message, true); }
}

// Remove o documento selecionado e atualiza a lista.
async function deleteDocument(documentId) {
  if (!state.selected || !window.confirm("Remover este documento?")) return;
  // O botão permanece ativo durante o DELETE; uma repetição posterior ao commit pode receber 404.
  try {
    await api(`/clients/${state.selected.id}/documents/${documentId}`, { method: "DELETE" });
    setFeedback("document-status", "Documento removido.");
    await selectClient(state.selected.id); // A exclusão já foi confirmada; falha nesta recarga pode mostrar erro após a remoção (achado 28).
  } catch (error) { setFeedback("document-status", error.message, true); }
}

// Carrega um relatório existente no formulário de edição.
function editReport(report) {
  if (!report) return;
  state.editingReport = report;
  $("report-form-title").textContent = "Editar relatório";
  $("report-title").value = report.title;
  $("period-start").value = report.period_start;
  $("period-end").value = report.period_end;
  $("report-summary").value = report.summary;
  $("report-status-select").value = report.status;
  $("report-submit-button").textContent = "Salvar alterações";
  show("cancel-report-edit", true);
  $("report-status").textContent = "Editando relatório selecionado.";
}

// Cancela a edição de relatório e redefine o formulário.
function cancelReportEdit(clearStatus = true) {
  state.editingReport = null;
  $("report-form").reset();
  $("report-form-title").textContent = "Publicar relatório";
  $("report-submit-button").textContent = "Publicar relatório";
  show("cancel-report-edit", false);
  if (clearStatus) $("report-status").textContent = "";
}

// Exibe eventos recentes de auditoria do cliente.
function renderAudit(entries) {
  const labels = { create: "Criou", update: "Atualizou", delete: "Removeu", assign: "Vinculou", change_password: "Alterou a senha" };
  const resources = { client_profile: "dados cadastrais", client_permissions: "permissões", financial_profile: "perfil financeiro", patrimony_item: "patrimônio", goal: "meta", action_item: "ação", client_advisor: "vínculo do Advisor", user: "conta" };
  const formatter = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });
  $("audit-list").innerHTML = entries.length ? entries.map((entry) => `<article class="audit-row"><div class="report-row-heading"><strong>${escapeHtml(labels[entry.action] || entry.action)} ${escapeHtml(resources[entry.resource] || entry.resource)}</strong><span>${escapeHtml(formatter.format(new Date(entry.created_at)))}</span></div><div class="muted">Por ${escapeHtml(entry.actor_name || `usuário #${entry.actor_user_id ?? "removido"}`)}</div></article>`).join("") : '<p class="empty-line">Nenhuma alteração registrada.</p>';
}

// Atualiza atalhos para os registros principais do cliente.
function renderQuickRecords() {
  $("advisor-patrimony-list").innerHTML = state.patrimony.length ? state.patrimony.map((item) => `<article class="quick-record"><div><strong>${escapeHtml(item.description)}</strong><small class="muted">${escapeHtml(item.category)} · ${money(item.value)}${item.institution ? ` · ${escapeHtml(item.institution)}` : ""}${item.notes ? ` · ${escapeHtml(item.notes)}` : ""}</small></div><div class="quick-record-actions"><button class="button ghost small" data-patrimony-edit="${item.id}">Editar</button><button class="button ghost small" data-patrimony-delete="${item.id}">Remover</button></div></article>`).join("") : '<p class="empty-line">Nenhum item cadastrado.</p>';
  const goalStatuses = { active: "Ativa", paused: "Pausada", completed: "Concluída" };
  const goalFilter = $("goal-filter").value;
  const visibleGoals = goalFilter === "all" ? state.goals : state.goals.filter((goal) => goalFilter === "overdue" ? isGoalOverdue(goal.target_date, goal.status) : goal.status === goalFilter);
  $("advisor-goal-list").innerHTML = visibleGoals.length ? visibleGoals.map((goal) => `<article class="quick-record"><div><strong>${escapeHtml(goal.title)}</strong><small class="muted">${money(goal.current_value)} de ${money(goal.target_value)} · ${escapeHtml(goalStatuses[goal.status] || goal.status)}${goal.target_date ? ` · até ${formatDate(goal.target_date)}` : ""}${isGoalOverdue(goal.target_date, goal.status) ? ' · <span class="overdue-label">Prazo vencido</span>' : ""}</small></div><div class="quick-record-actions"><button class="button ghost small" data-goal-edit="${goal.id}">Editar</button><button class="button ghost small" data-goal-delete="${goal.id}">Remover</button></div></article>`).join("") : '<p class="empty-line">Nenhuma meta neste filtro.</p>';
  document.querySelectorAll("[data-patrimony-edit]").forEach((button) => { button.onclick = () => startPatrimonyEdit(state.patrimony.find((item) => item.id === Number(button.dataset.patrimonyEdit))); });
  document.querySelectorAll("[data-patrimony-delete]").forEach((button) => { button.onclick = () => deleteAdvisorPatrimony(Number(button.dataset.patrimonyDelete)); });
  document.querySelectorAll("[data-goal-edit]").forEach((button) => { button.onclick = () => startGoalEdit(state.goals.find((goal) => goal.id === Number(button.dataset.goalEdit))); });
  document.querySelectorAll("[data-goal-delete]").forEach((button) => { button.onclick = () => deleteAdvisorGoal(Number(button.dataset.goalDelete)); });
}

// Desenha ações do cliente aplicando o filtro atual.
function renderActionPlan() {
  const statuses = { planned: "Planejada", in_progress: "Em andamento", completed: "Concluída" };
  const priorities = { low: "baixa", medium: "média", high: "alta" };
  const filter = $("action-filter").value;
  const priorityOrder = { high: 0, medium: 1, low: 2 }; // Desempata ações após atraso e estado; prazo e título vêm depois.
  // Seleciona ações visíveis conforme o filtro da interface.
  const visibleActions = (filter === "all" ? [...state.actionPlan] : state.actionPlan.filter((action) => filter === "completed" ? action.status === "completed" : filter === "overdue" ? isOverdue(action.due_date, action.status) : action.status !== "completed"))
    .sort((left, right) => {
      const overdueDifference = Number(isOverdue(right.due_date, right.status)) - Number(isOverdue(left.due_date, left.status));
      if (overdueDifference) return overdueDifference;
      const completedDifference = Number(left.status === "completed") - Number(right.status === "completed");
      if (completedDifference) return completedDifference;
      const priorityDifference = (priorityOrder[left.priority] ?? 3) - (priorityOrder[right.priority] ?? 3);
      if (priorityDifference) return priorityDifference;
      if (left.due_date && right.due_date && left.due_date !== right.due_date) return left.due_date.localeCompare(right.due_date);
      if (left.due_date && !right.due_date) return -1;
      if (!left.due_date && right.due_date) return 1;
      return left.title.localeCompare(right.title, "pt-BR");
    });
  $("action-goal").innerHTML = '<option value="">Sem meta vinculada</option>' + state.goals.map((goal) => `<option value="${goal.id}">${escapeHtml(goal.title)}</option>`).join(""); // Ao renderizar durante a edição, a seleção atual não é restaurada (achado 172).
  $("action-list").innerHTML = visibleActions.length ? visibleActions.map((action) => { const linkedGoal = state.goals.find((goal) => goal.id === action.goal_id); const quickStatusButton = action.status === "planned" ? `<button class="button secondary small" data-action-start="${action.id}">Iniciar</button>` : action.status !== "completed" ? `<button class="button secondary small" data-action-complete="${action.id}">Concluir</button>` : ""; return `<article class="quick-record action-record"><div><strong>${escapeHtml(action.title)}</strong><small class="muted">${escapeHtml(statuses[action.status] || action.status)} · <span class="priority-badge ${escapeHtml(action.priority)}">${escapeHtml(priorities[action.priority] || action.priority)}</span>${action.due_date ? ` · até ${formatDate(action.due_date)}` : ""}${linkedGoal ? ` · meta: ${escapeHtml(linkedGoal.title)}` : ""}${isOverdue(action.due_date, action.status) ? ' · <span class="overdue-label">Atrasada</span>' : ""}</small>${action.description ? `<p class="muted">${escapeHtml(action.description)}</p>` : ""}</div><div class="quick-record-actions">${quickStatusButton}<button class="button ghost small" data-action-edit="${action.id}">Editar</button><button class="button ghost small" data-action-delete="${action.id}">Remover</button></div></article>`; }).join("") : '<p class="empty-line">Nenhuma ação neste filtro.</p>';
  document.querySelectorAll("[data-action-edit]").forEach((button) => { button.onclick = () => startActionEdit(state.actionPlan.find((action) => action.id === Number(button.dataset.actionEdit))); });
  document.querySelectorAll("[data-action-delete]").forEach((button) => { button.onclick = () => deleteAction(Number(button.dataset.actionDelete)); });
  document.querySelectorAll("[data-action-complete]").forEach((button) => { button.onclick = () => completeAction(Number(button.dataset.actionComplete)); });
  document.querySelectorAll("[data-action-start]").forEach((button) => { button.onclick = () => startAction(Number(button.dataset.actionStart)); });
}

// Atualiza controles de permissão de edição do cliente.
function renderPermissions(permissions) {
  const labels = { can_edit_financial_profile: "Editar perfil financeiro", can_edit_patrimony: "Editar patrimônio", can_edit_goals: "Editar metas" };
  $("permissions").innerHTML = `<p class="muted">Dados cadastrais e documentos são sempre gerenciados pelo Advisor ou administrador.</p>${Object.entries(labels).map(([field, label]) => `<label class="permission"><input type="checkbox" data-permission="${field}" ${permissions[field] ? "checked" : ""}><span>${label}</span></label>`).join("")}`;
}

// Exibe renda, despesas e perfil de risco registrados.
function renderFinancialProfile(profile) {
  $("monthly-income").value = profile?.monthly_income ?? 0;
  $("monthly-expenses").value = profile?.monthly_expenses ?? 0;
  // A tradução é apresentada e depois enviada como texto sem conversão de volta (achado 139).
  const riskLabels = { conservative: "Conservador", moderate: "Moderado", aggressive: "Agressivo" };
  $("risk-profile").value = riskLabels[profile?.risk_profile] || profile?.risk_profile || "";
  setFeedback("financial-status", profile ? "Dados carregados." : "Ainda não cadastrado. Preencha os dados para criar o perfil.");
}

// Mostra ao Advisor o resultado versionado do questionário do cliente.
function renderSuitability(assessment) {
  show("suitability-empty", !assessment);
  show("suitability-content", Boolean(assessment));
  if (!assessment) return;
  const statusLabels = { pending_review: "Aguardando validação", approved: "Aprovada", rejected: "Nova avaliação solicitada", superseded: "Substituída" };
  const clientResponseLabels = { pending: "Aguardando resposta do cliente", accepted: "Aceita pelo cliente", declined: "Recusada pelo cliente", adjustment_requested: "Ajustes solicitados pelo cliente" };
  const recommendation = assessment.recommendation || {};
  const financial = assessment.financial_situation || {};
  $("suitability-summary").innerHTML = `<div><small>Objetivo</small><strong>${escapeHtml(assessment.objective_label)}</strong></div><div><small>Perfil indicado pelas respostas</small><strong>${escapeHtml(assessment.risk_profile_label)}</strong></div><div><small>Pontuação</small><strong>${escapeHtml(assessment.score)}</strong></div><div><small>Status</small><strong>${escapeHtml(statusLabels[assessment.status] || assessment.status)}</strong></div>`;
  $("suitability-recommendation").textContent = `${recommendation.title || "Carteira sugerida"}. ${recommendation.summary || ""}`;
  const recommendedActions = recommendation.recommended_actions || [];
  $("suitability-recommended-actions").innerHTML = recommendedActions.length
    ? `<h3>Próximas ações para validar a carteira</h3><ul>${recommendedActions.map((action) => `<li><strong>${escapeHtml(action.title)}</strong><br><span class="muted">${escapeHtml(action.detail)}</span></li>`).join("")}</ul>`
    : "";
  $("suitability-recommended-actions").classList.toggle("hidden", !recommendedActions.length);
  const financialFlags = {
    monthly_surplus_not_positive: "Saldo mensal cadastrado não é positivo.",
    active_goal_within_2_years: "Há meta ativa com prazo nos próximos dois anos.",
    no_patrimony_items_recorded: "Nenhum item de patrimônio foi cadastrado.",
    liabilities_not_recorded: "O Talentum não registra dívidas ou outros passivos.",
  };
  // Resume patrimônio e metas em linhas legíveis para o contexto da avaliação.
  const categoryRows = (financial.patrimony_by_category || []).map((item) => `<li>${escapeHtml(item.category)}: ${money(item.value)}</li>`).join("");
  // Resume cada meta ativa com progresso e prazo para contextualizar a recomendação.
  const goalRows = (financial.active_goals || []).map((goal) => `<li>${escapeHtml(goal.title)}: ${money(goal.current_value)} de ${money(goal.target_value)}${goal.target_date ? ` · prazo ${formatDate(goal.target_date)}` : ""}</li>`).join("");
  const flags = [...new Set([...(financial.capacity_flags || []), ...(recommendation.financial_review_flags || [])])];
  const flagList = flags.length ? `<ul>${flags.map((flag) => `<li>${escapeHtml(financialFlags[flag] || flag)}</li>`).join("")}</ul>` : "";
  $("suitability-financial-context").innerHTML = financial.data_version
    ? `<h3>Situação financeira confirmada pelo cliente</h3><div class="suitability-financial-grid"><span>Renda mensal<strong>${money(financial.monthly_income)}</strong></span><span>Despesas mensais<strong>${money(financial.monthly_expenses)}</strong></span><span>Saldo mensal<strong>${money(financial.monthly_surplus)}</strong></span><span>Patrimônio cadastrado, sem passivos<strong>${money(financial.patrimony_total)}</strong></span></div><p><strong>Patrimônio por categoria</strong></p>${categoryRows ? `<ul>${categoryRows}</ul>` : '<p class="muted">Nenhum item cadastrado.</p>'}<p><strong>Metas ativas</strong></p>${goalRows ? `<ul>${goalRows}</ul>` : '<p class="muted">Nenhuma meta ativa cadastrada.</p>'}${flagList ? `<div class="suitability-financial-flags"><strong>Pontos para revisar</strong>${flagList}</div>` : ""}<small class="muted">Dados confirmados em ${financial.client_confirmed_at ? formatDate(financial.client_confirmed_at) : "data não informada"}.</small>`
    : '<p class="muted">Esta avaliação anterior não contém um registro financeiro confirmado.</p>';
  const answerLabels = {
    product_familiarity: "Familiaridade com produtos",
    operation_products: "Produtos já utilizados",
    operation_period: "Tempo de experiência",
    operation_frequency: "Frequência das operações",
    monthly_operation_volume: "Volume mensal aproximado",
    financial_education: "Formação ou experiência profissional",
  };
  const optionLabels = {
    none: "Nenhum / não realizou operações",
    fixed_income: "Renda fixa",
    funds: "Fundos de investimento",
    stocks_etfs: "Ações e ETFs",
    fiis: "Fundos imobiliários (FIIs)",
    derivatives_structured: "Derivativos e produtos estruturados",
    under_1_year: "Menos de 1 ano",
    "1_to_3_years": "De 1 a 3 anos",
    over_3_years: "Mais de 3 anos",
    few_per_year: "Algumas vezes por ano",
    monthly: "Mensalmente",
    weekly_or_more: "Semanalmente ou mais",
    under_1000: "Até R$ 1.000",
    "1000_to_10000": "De R$ 1.000 a R$ 10.000",
    over_10000: "Acima de R$ 10.000",
    prefer_not_to_say: "Prefere não informar",
    education: "Curso ou formação relacionada",
    professional: "Experiência profissional na área",
    both: "Formação e experiência profissional",
  };
  // Converte cada resposta de experiência em um item rotulado para revisão do Advisor.
  const experienceRows = Object.entries(answerLabels).map(([key, label]) => {
    const raw = assessment.answers?.[key];
    const values = String(raw || "").split(",").filter(Boolean);
    const display = values.map((value) => optionLabels[value] || value).join(", ") || "Não informado";
    return `<li><strong>${escapeHtml(label)}:</strong> ${escapeHtml(display)}</li>`;
  }).join("");
  // Traduz alertas de conhecimento em mensagens que orientam a revisão humana.
  const experienceFlags = (recommendation.knowledge_review_flags || []).map((flag) => {
    const messages = {
      no_prior_market_operations_reported: "O cliente declarou não ter realizado operações anteriormente.",
      review_familiarity_with_recommended_products: "Confira a familiaridade do cliente com as classes sugeridas.",
      no_financial_education_or_professional_experience_reported: "O cliente não relatou formação ou experiência profissional financeira.",
    };
    return `<li>${escapeHtml(messages[flag] || flag)}</li>`;
  }).join("");
  $("suitability-knowledge-context").innerHTML = `<h3>Conhecimento e histórico relatados</h3><ul>${experienceRows}</ul>${experienceFlags ? `<div class="suitability-financial-flags"><strong>Pontos para revisar</strong><ul>${experienceFlags}</ul></div>` : ""}<small class="muted">Essas respostas são apresentadas para análise do Advisor; não aumentam automaticamente o perfil de risco.</small>`;
  // Renderiza cada categoria com os exemplos e ativos específicos escolhidos pelo Advisor.
  $("suitability-allocations").innerHTML = (recommendation.allocations || []).map((allocation) => {
    // Formata as subclasses e os exemplos associados à categoria da carteira.
    const segments = (allocation.suballocations || []).map((segment) => `<div class="suitability-segment"><div class="row-top"><span>${escapeHtml(segment.label)}</span><strong>${escapeHtml(segment.percentage)}%</strong></div><small class="muted">Exemplos para análise: ${escapeHtml((segment.examples || []).join(", "))}. ${escapeHtml(segment.rationale)}</small></div>`).join("");
    // Lista os ativos concretos incluídos pelo Advisor nessa categoria.
    const advisorAssets = (allocation.advisor_assets || []).map((asset) => `${asset.symbol} — ${asset.name}`).join(", ");
    return `<div class="suitability-allocation"><div class="row-top"><strong>${escapeHtml(allocation.label)}</strong><span>${escapeHtml(allocation.percentage)}%</span></div><div class="bar"><i style="width:${Math.max(0, Math.min(100, Number(allocation.percentage || 0)))}%"></i></div><small class="muted">${escapeHtml(allocation.rationale)}</small>${advisorAssets ? `<div class="suitability-segment"><strong>Ativos selecionados pelo Advisor</strong><small class="muted">${escapeHtml(advisorAssets)}</small></div>` : ""}${segments}</div>`;
  }).join("");
  renderSuitabilityProposalEditor(assessment);
  const expiryLabel = assessment.expires_at ? new Intl.DateTimeFormat("pt-BR").format(new Date(assessment.expires_at)) : "não informada";
  const clientResponse = clientResponseLabels[assessment.client_response] || clientResponseLabels.pending;
  const responseNote = assessment.client_response_note ? ` · Observação: ${assessment.client_response_note}` : "";
  setFeedback("suitability-status", `${statusLabels[assessment.status] || assessment.status}. ${clientResponse}${responseNote}. Validade: ${expiryLabel}`);
  $("suitability-approve").disabled = assessment.status === "approved";
  $("suitability-reject").disabled = assessment.status === "rejected";
}

// Monta o editor de ativos da recomendação do assessor.
function renderSuitabilityProposalEditor(assessment) {
  const recommendation = assessment.recommendation || {};
  const allocations = recommendation.allocations || [];
  const published = Boolean(recommendation.advisor_proposal_published_at);
  const locked = assessment.client_response === "accepted" || assessment.status === "rejected" || assessment.status === "superseded";
  if (!state.suitabilityProposalDraft || state.suitabilityProposalDraft.assessmentId !== assessment.id) {
    state.suitabilityProposalDraft = {
      assessmentId: assessment.id,
      selectedClass: allocations[0]?.asset_class || "",
      assetsByClass: Object.fromEntries(allocations.map((allocation) => [allocation.asset_class, (allocation.advisor_assets || []).map((asset) => ({ ...asset }))])),
    };
    state.suitabilityProposalSearchResults = [];
  }
  const draft = state.suitabilityProposalDraft;
  if (!allocations.some((allocation) => allocation.asset_class === draft.selectedClass)) draft.selectedClass = allocations[0]?.asset_class || "";
  const selectedAssets = allocations.map((allocation, allocationIndex) => {
    const assets = draft.assetsByClass[allocation.asset_class] || [];
    return assets.length ? `<div class="suitability-proposal-category"><strong>${escapeHtml(allocation.label)} (${escapeHtml(allocation.percentage)}%)</strong>${assets.map((asset, assetIndex) => `<div class="suitability-proposal-asset"><span><strong>${escapeHtml(asset.symbol)}</strong> · ${escapeHtml(asset.name)} <small class="muted">${asset.market === "br" ? "B3" : "Exterior"}</small></span>${locked ? "" : `<button class="button ghost small" type="button" data-suitability-remove="${allocationIndex}:${assetIndex}">Remover</button>`}</div>`).join("")}</div>` : "";
  }).join("");
  const results = state.suitabilityProposalSearchResults.map((asset, index) => `<article class="suitability-proposal-result"><span><strong>${escapeHtml(asset.symbol)}</strong> · ${escapeHtml(asset.name)}<small class="muted">${escapeHtml(asset.market === "br" ? "B3" : "Exterior")} · ${escapeHtml(asset.asset_type || "Ativo")} · ${escapeHtml(asset.currency || "")}</small></span><button class="button ghost small" type="button" data-suitability-add="${index}" ${locked ? "disabled" : ""}>Adicionar</button></article>`).join("");
  const emptySearchMessage = state.suitabilityProposalQuery && !state.suitabilityProposalSearchResults.length
    ? "Nenhum ativo encontrado para esta pesquisa."
    : "Pesquise um ativo para adicionar à categoria selecionada.";
  $("suitability-proposal-editor").innerHTML = `<div class="suitability-proposal-heading"><h3>Montar sugestão para o cliente</h3><span class="muted">Use as respostas e o perfil acima para selecionar ativos por categoria.</span></div>${published ? `<p class="feedback">Publicada em ${formatDate(recommendation.advisor_proposal_published_at)}${recommendation.advisor_proposal_by ? ` por ${escapeHtml(recommendation.advisor_proposal_by)}` : ""}.</p>` : ""}<label>Categoria da carteira<select id="suitability-proposal-category" ${locked ? "disabled" : ""}>${allocations.map((allocation) => `<option value="${escapeHtml(allocation.asset_class)}" ${draft.selectedClass === allocation.asset_class ? "selected" : ""}>${escapeHtml(allocation.label)} — ${escapeHtml(allocation.percentage)}%</option>`).join("")}</select></label><form id="suitability-proposal-search" class="suitability-proposal-search"><label>Pesquisar ativo<input id="suitability-proposal-query" type="search" maxlength="120" placeholder="Ticker ou nome" value="${escapeHtml(state.suitabilityProposalQuery)}" required ${locked ? "disabled" : ""}></label><label>Mercado<select id="suitability-proposal-market" ${locked ? "disabled" : ""}><option value="all" ${state.suitabilityProposalMarket === "all" ? "selected" : ""}>Todos</option><option value="br" ${state.suitabilityProposalMarket === "br" ? "selected" : ""}>Brasil (B3)</option><option value="global" ${state.suitabilityProposalMarket === "global" ? "selected" : ""}>Exterior</option></select></label><button class="button secondary small" type="submit" ${locked ? "disabled" : ""}>Pesquisar</button></form><div class="suitability-proposal-results">${results || `<p class="muted">${emptySearchMessage}</p>`}</div><h4>Ativos na sugestão</h4>${selectedAssets || '<p class="muted">Nenhum ativo adicionado.</p>'}<button id="suitability-proposal-publish" class="button primary small" type="button" ${locked ? "disabled" : ""}>${published ? "Atualizar e publicar sugestão" : "Publicar sugestão para o cliente"}</button>`;
}

// Pesquisa ativos para incluir na proposta de carteira.
async function searchSuitabilityProposal(event) {
  event.preventDefault();
  const query = $("suitability-proposal-query").value.trim();
  if (!query) return;
  state.suitabilityProposalQuery = query;
  state.suitabilityProposalMarket = $("suitability-proposal-market").value;
  try {
    const params = new URLSearchParams({ q: query, market: state.suitabilityProposalMarket });
    const data = await api(`/market/search?${params.toString()}`);
    state.suitabilityProposalSearchResults = data.results || [];
    renderSuitabilityProposalEditor(state.suitability);
    setFeedback("suitability-status", `${state.suitabilityProposalSearchResults.length} ativo(s) encontrado(s).`);
  } catch (error) { setFeedback("suitability-status", error.message, true); }
}

// Publica os ativos escolhidos dentro da recomendação de suitability.
async function publishSuitabilityProposal() {
  if (!state.selected || !state.suitability || !state.suitabilityProposalDraft) return;
  const allocations = state.suitability.recommendation?.allocations || [];
  const payload = { allocations: allocations.map((allocation) => ({ asset_class: allocation.asset_class, assets: state.suitabilityProposalDraft.assetsByClass[allocation.asset_class] || [] })) };
  try {
    // O botão permanece disponível enquanto a API processa; cliques repetidos podem gerar auditorias duplicadas (achado 27).
    state.suitability = await api(`/clients/${state.selected.id}/suitability/${state.suitability.id}/proposal`, { method: "PUT", body: JSON.stringify(payload) });
    state.suitabilityProposalDraft = null;
    state.suitabilityProposalSearchResults = [];
    renderSuitability(state.suitability);
    setFeedback("suitability-status", "Sugestão publicada. O cliente poderá aceitá-la na Carteira sugerida do aplicativo.");
  } catch (error) { setFeedback("suitability-status", error.message, true); }
}

// Registra a decisão do Advisor e mantém o histórico de auditoria no backend.
async function reviewSuitability(approved) {
  if (!state.selected || !state.suitability) return;
  try {
    // A decisão só desabilita o botão após a resposta; pedidos concorrentes podem registrar resultados diferentes (achado 27).
    state.suitability = await api(`/clients/${state.selected.id}/suitability/${state.suitability.id}/review`, { method: "POST", body: JSON.stringify({ approved }) });
    renderSuitability(state.suitability);
    setFeedback("suitability-status", approved ? "Carteira aprovada e registrada." : "Nova avaliação solicitada ao cliente.");
    await selectClient(state.selected.id);
  } catch (error) { setFeedback("suitability-status", error.message, true); }
}

// Preenche o formulário cadastral com os dados visíveis e editáveis pelo Advisor.
function renderClientProfile(profile) {
  $("client-profile-name").value = profile?.name ?? "";
  $("client-profile-phone").value = profile?.phone ?? "";
  $("client-profile-father").value = profile?.father_name ?? "";
  $("client-profile-mother").value = profile?.mother_name ?? "";
  $("client-profile-street").value = profile?.address_street ?? "";
  $("client-profile-number").value = profile?.address_number ?? "";
  $("client-profile-city").value = profile?.address_city ?? "";
  $("client-profile-zip").value = profile?.address_zip_code ?? "";
  $("client-profile-state").value = profile?.address_state ?? "";
  // Este status vem do cadastro complementar; o controle de acesso usa state.selected.is_active.
  $("client-profile-status").value = profile?.status ?? "active";
  $("toggle-client-access").textContent = state.selected?.is_active ? "Desativar acesso" : "Reativar acesso";
  // Preserva no seletor um vínculo existente mesmo quando o Advisor deixou de estar ativo.
  const assignedId = profile?.advisor_id?.toString() ?? "";
  const assignedAdvisor = profile?.advisor_id && !state.advisors.some((advisor) => advisor.id === profile.advisor_id)
    ? `<option value="${profile.advisor_id}">${escapeHtml(profile.advisor_name || "Advisor inativo")} — inativo</option>`
    : "";
  $("advisor-assignment").innerHTML = '<option value="">Sem Advisor vinculado</option>' + assignedAdvisor + state.advisors.map((advisor) => `<option value="${advisor.id}">${escapeHtml(advisor.name)} — ${escapeHtml(advisor.email)}</option>`).join("");
  $("advisor-assignment").value = assignedId;
  setFeedback("client-profile-status-message", "Dados carregados.");
}

// Valida e salva os dados cadastrais do cliente.
async function saveClientProfile(event) {
  event.preventDefault(); if (!state.selected) return;
  const name = $("client-profile-name").value.trim();
  if (name.length < 2) { setFeedback("client-profile-status-message", "Informe um nome válido.", true); return; }
  try {
    // Campos opcionais vazios são enviados como null para limpar seus valores já salvos.
    state.clientProfile = await api(`/clients/${state.selected.id}/profile`, { method: "PUT", body: JSON.stringify({ name, phone: $("client-profile-phone").value.trim() || null, father_name: $("client-profile-father").value.trim() || null, mother_name: $("client-profile-mother").value.trim() || null, address_street: $("client-profile-street").value.trim() || null, address_number: $("client-profile-number").value.trim() || null, address_city: $("client-profile-city").value.trim() || null, address_zip_code: $("client-profile-zip").value.trim() || null, address_state: $("client-profile-state").value.trim() || null }) }); // O PUT leva o formulário completo; gravações concorrentes podem terminar fora de ordem (160), e uma troca de cliente durante a espera pode exibir esta resposta no cliente errado (12).
    state.selected.name = state.clientProfile.name; renderClientProfile(state.clientProfile); renderClients(); setFeedback("client-profile-status-message", "Dados do cliente salvos.");
  } catch (error) { setFeedback("client-profile-status-message", error.message, true); }
}

// Atualiza o assessor responsável pelo cliente selecionado.
async function saveAssignment(event) {
  event.preventDefault(); if (!state.selected) return;
  const value = $("advisor-assignment").value;
  try {
    // Campo vazio representa explicitamente a remoção do vínculo com um Advisor.
    const assignment = await api(`/clients/${state.selected.id}/assignment`, { method: "PUT", body: JSON.stringify({ advisor_id: value ? Number(value) : null }) }); // Escolhas podem terminar fora de ordem (160), e a resposta não confere se o cliente selecionado ainda é o mesmo (12).
    state.clientProfile.advisor_id = assignment.advisor_id; state.clientProfile.advisor_name = assignment.advisor_name;
    setFeedback("assignment-status", assignment.advisor_name ? `Cliente vinculado a ${assignment.advisor_name}.` : "Cliente desvinculado.");
  } catch (error) { setFeedback("assignment-status", error.message, true); }
}

// Ativa ou bloqueia o acesso da conta do cliente.
async function toggleClientAccess() {
  if (!state.selected) return;
  const isActive = !state.selected.is_active;
  try {
    const user = await api(`/admin/users/${state.selected.id}/status`, { method: "PATCH", body: JSON.stringify({ is_active: isActive }) }); // A seleção pode mudar durante a espera; o retorno ainda é aplicado ao estado global atual (achado 12).
    state.selected.is_active = user.is_active; $("client-status").textContent = user.is_active ? "Ativo" : "Inativo"; renderClients(); renderOverview(); renderClientProfile(state.clientProfile); setFeedback("assignment-status", user.is_active ? "Acesso reativado." : "Acesso desativado.");
  } catch (error) { setFeedback("assignment-status", error.message, true); }
}

// Persiste renda, despesas e perfil de risco do cliente selecionado.
async function saveFinancialProfile(event) {
  event.preventDefault(); if (!state.selected) return;
  // O botão externo ao formulário chama este handler diretamente; campos vazios viram zero sem validar required.
  const payload = { monthly_income: Number($("monthly-income").value), monthly_expenses: Number($("monthly-expenses").value), risk_profile: $("risk-profile").value.trim() || null }; // O PUT substitui o conjunto de valores e não há bloqueio durante o envio (achado 160).
  if (!Number.isFinite(payload.monthly_income) || payload.monthly_income < 0 || !Number.isFinite(payload.monthly_expenses) || payload.monthly_expenses < 0) { setFeedback("financial-status", "Informe valores válidos para renda e despesas.", true); return; }
  try {
    state.financialProfile = await api(`/clients/${state.selected.id}/financial-profile`, { method: "PUT", body: JSON.stringify(payload) }); // A resposta é aplicada sem confirmar que o cliente selecionado continua sendo o mesmo (achado 12).
    renderFinancialProfile(state.financialProfile); setFeedback("financial-status", "Perfil financeiro salvo.");
  } catch (error) { setFeedback("financial-status", error.message, true); }
}

// Persiste permissões de edição configuradas no painel.
async function savePermissions() {
  if (!state.selected) return;
  const payload = Object.fromEntries([...document.querySelectorAll("[data-permission]")].map((input) => [input.dataset.permission, input.checked])); // PUTs concorrentes podem persistir conjuntos em ordem diferente (160); o retorno também não revalida o cliente selecionado (12).
  try { state.permissions = await api(`/clients/${state.selected.id}/permissions`, { method: "PUT", body: JSON.stringify(payload) }); setFeedback("permission-status", "Permissões salvas."); }
  catch (error) { setFeedback("permission-status", error.message, true); }
}

// Cria ou atualiza um relatório que será disponibilizado ao cliente.
async function publishReport(event) {
  event.preventDefault(); if (!state.selected) return;
  const payload = { title: $("report-title").value.trim(), period_start: $("period-start").value, period_end: $("period-end").value, summary: $("report-summary").value.trim(), status: $("report-status-select").value };
  if (payload.title.length < 2) { setFeedback("report-status", "Informe um título válido.", true); return; }
  if (payload.summary.length < 2) { setFeedback("report-status", "Informe um resumo para o relatório.", true); return; }
  if (!payload.period_start || !payload.period_end || payload.period_end < payload.period_start) { setFeedback("report-status", "O fim do período precisa ser igual ou posterior ao início.", true); return; }
  // A mutação e a recarga usam o mesmo try; se a recarga falhar após o commit, a UI pode reportar erro (achado 28).
  try { const wasEditing = Boolean(state.editingReport); await api(wasEditing ? `/clients/${state.selected.id}/reports/${state.editingReport.id}` : `/clients/${state.selected.id}/reports`, { method: wasEditing ? "PATCH" : "POST", body: JSON.stringify(payload) }); cancelReportEdit(false); setFeedback("report-status", wasEditing ? "Relatório atualizado." : "Relatório criado."); await selectClient(state.selected.id); }
  catch (error) { setFeedback("report-status", error.message, true); }
}

// Remove um relatório que ainda pode ser excluído.
async function deleteReport(reportId) {
  if (!state.selected || !window.confirm("Remover este rascunho?")) return;
  // O DELETE pode ser repetido antes da recarga; após o primeiro commit, outra chamada pode receber 404.
  // A falha na recarga seguinte também pode substituir o feedback de sucesso (achado 28).
  try {
    await api(`/clients/${state.selected.id}/reports/${reportId}`, { method: "DELETE" });
    setFeedback("report-status", "Rascunho removido.");
    await selectClient(state.selected.id);
  } catch (error) { setFeedback("report-status", error.message, true); }
}

// Cadastra um item patrimonial para o cliente selecionado.
async function addAdvisorPatrimony(event) {
  event.preventDefault(); if (!state.selected) return;
  const value = Number($("advisor-patrimony-value").value);
  if ($("advisor-patrimony-category").value.trim().length < 2 || $("advisor-patrimony-description").value.trim().length < 2) { setFeedback("advisor-patrimony-status", "Informe categoria e descrição válidas.", true); return; }
  if (!Number.isFinite(value) || value < 0) { setFeedback("advisor-patrimony-status", "Informe um valor válido.", true); return; }
  try {
    const payload = { category: $("advisor-patrimony-category").value.trim(), description: $("advisor-patrimony-description").value.trim(), institution: $("advisor-patrimony-institution").value.trim() || null, value, notes: $("advisor-patrimony-notes").value.trim() || null };
    const wasEditing = Boolean(state.editingPatrimony); await api(wasEditing ? `/clients/${state.selected.id}/patrimony/${state.editingPatrimony.id}` : `/clients/${state.selected.id}/patrimony`, { method: wasEditing ? "PATCH" : "POST", body: JSON.stringify(payload) });
    cancelPatrimonyEdit(false); setFeedback("advisor-patrimony-status", wasEditing ? "Patrimônio atualizado." : "Patrimônio adicionado."); await selectClient(state.selected.id);
  } catch (error) { setFeedback("advisor-patrimony-status", error.message, true); }
}

// Preenche o formulário com o item patrimonial escolhido.
function startPatrimonyEdit(item) {
  if (!item) return; state.editingPatrimony = item; $("advisor-patrimony-form-title").textContent = "Editar patrimônio"; $("advisor-patrimony-category").value = item.category; $("advisor-patrimony-description").value = item.description; $("advisor-patrimony-institution").value = item.institution ?? ""; $("advisor-patrimony-value").value = item.value; $("advisor-patrimony-notes").value = item.notes ?? ""; $("advisor-patrimony-submit").textContent = "Salvar alterações"; show("advisor-patrimony-cancel", true);
}

// Descarta a edição patrimonial em andamento.
function cancelPatrimonyEdit(clearStatus = true) {
  state.editingPatrimony = null; $("advisor-patrimony-form").reset(); $("advisor-patrimony-form-title").textContent = "Adicionar patrimônio"; $("advisor-patrimony-submit").textContent = "Adicionar patrimônio"; show("advisor-patrimony-cancel", false); if (clearStatus) $("advisor-patrimony-status").textContent = "";
}

// Remove um item do patrimônio após a ação solicitada.
async function deleteAdvisorPatrimony(itemId) {
  if (!state.selected || !window.confirm("Remover este item patrimonial?")) return;
  // O botão segue ativo durante o DELETE; uma repetição após o commit pode encontrar item inexistente.
  try { await api(`/clients/${state.selected.id}/patrimony/${itemId}`, { method: "DELETE" }); setFeedback("advisor-patrimony-status", "Patrimônio removido."); await selectClient(state.selected.id); }
  catch (error) { setFeedback("advisor-patrimony-status", error.message, true); }
}

// Cadastra uma meta financeira para o cliente.
async function addAdvisorGoal(event) {
  event.preventDefault(); if (!state.selected) return;
  const target = Number($("advisor-goal-target").value); const current = Number($("advisor-goal-current").value || 0);
  if ($("advisor-goal-title").value.trim().length < 2) { setFeedback("advisor-goal-status", "Informe um título válido para a meta.", true); return; }
  if (!Number.isFinite(target) || target <= 0 || !Number.isFinite(current) || current < 0) { setFeedback("advisor-goal-status", "Informe valores válidos.", true); return; }
  try {
    const payload = { title: $("advisor-goal-title").value.trim(), target_value: target, current_value: current, target_date: $("advisor-goal-date").value || null, status: $("advisor-goal-status-select").value };
    const wasEditing = Boolean(state.editingGoal); await api(wasEditing ? `/clients/${state.selected.id}/goals/${state.editingGoal.id}` : `/clients/${state.selected.id}/goals`, { method: wasEditing ? "PATCH" : "POST", body: JSON.stringify(payload) });
    cancelGoalEdit(false); setFeedback("advisor-goal-status", wasEditing ? "Meta atualizada." : "Meta adicionada."); await selectClient(state.selected.id);
  } catch (error) { setFeedback("advisor-goal-status", error.message, true); }
}

// Preenche o formulário com os dados da meta escolhida.
function startGoalEdit(goal) {
  if (!goal) return; state.editingGoal = goal; $("advisor-goal-form-title").textContent = "Editar meta"; $("advisor-goal-title").value = goal.title; $("advisor-goal-target").value = goal.target_value; $("advisor-goal-current").value = goal.current_value; $("advisor-goal-date").value = goal.target_date ?? ""; $("advisor-goal-status-select").value = goal.status; $("advisor-goal-submit").textContent = "Salvar alterações"; show("advisor-goal-cancel", true);
}

// Descarta a edição de meta em andamento.
function cancelGoalEdit(clearStatus = true) {
  state.editingGoal = null; $("advisor-goal-form").reset(); $("advisor-goal-current").value = "0"; $("advisor-goal-status-select").value = "active"; $("advisor-goal-form-title").textContent = "Adicionar meta"; $("advisor-goal-submit").textContent = "Adicionar meta"; show("advisor-goal-cancel", false); if (clearStatus) $("advisor-goal-status").textContent = "";
}

// Remove a meta financeira selecionada.
async function deleteAdvisorGoal(goalId) {
  if (!state.selected || !window.confirm("Remover esta meta?")) return;
  // O botão segue ativo durante o DELETE; uma repetição após o commit pode encontrar meta inexistente.
  try { await api(`/clients/${state.selected.id}/goals/${goalId}`, { method: "DELETE" }); setFeedback("advisor-goal-status", "Meta removida."); await selectClient(state.selected.id); }
  catch (error) { setFeedback("advisor-goal-status", error.message, true); }
}

// Cria ou atualiza uma ação do plano de acompanhamento do cliente.
async function saveAction(event) {
  event.preventDefault(); if (!state.selected) return;
  const title = $("action-title").value.trim();
  if (title.length < 2) { setFeedback("action-feedback", "Informe um título válido.", true); return; } // O cliente verifica o mínimo; os limites máximos ficam no schema da API (achado 67).
  try {
    // Se o seletor perder a meta durante uma troca de filtro, o valor vazio vira null e remove o vínculo (achado 172).
    const payload = { title, description: $("action-description").value.trim() || null, due_date: $("action-due-date").value || null, goal_id: $("action-goal").value ? Number($("action-goal").value) : null, priority: $("action-priority").value, status: $("action-status").value };
    const wasEditing = Boolean(state.editingAction);
    await api(wasEditing ? `/clients/${state.selected.id}/action-plan/${state.editingAction.id}` : `/clients/${state.selected.id}/action-plan`, { method: wasEditing ? "PATCH" : "POST", body: JSON.stringify(payload) });
    cancelActionEdit(false); setFeedback("action-feedback", wasEditing ? "Ação atualizada." : "Ação adicionada."); await selectClient(state.selected.id);
  } catch (error) { setFeedback("action-feedback", error.message, true); }
}

// Carrega a ação escolhida no formulário de edição.
function startActionEdit(action) {
  if (!action) return;
  state.editingAction = action;
  $("action-form-title").textContent = "Editar ação";
  $("action-title").value = action.title;
  $("action-description").value = action.description ?? "";
  $("action-due-date").value = action.due_date ?? "";
  $("action-goal").value = action.goal_id?.toString() ?? "";
  $("action-priority").value = action.priority;
  $("action-status").value = action.status;
  $("action-submit").textContent = "Salvar alterações";
  show("action-cancel", true);
  setFeedback("action-feedback", "Editando ação selecionada.");
}

// Descarta a edição da ação e limpa seu estado temporário.
function cancelActionEdit(clearStatus = true) {
  state.editingAction = null;
  $("action-form").reset();
  $("action-form-title").textContent = "Plano de ação";
  $("action-submit").textContent = "Adicionar ação";
  show("action-cancel", false);
  if (clearStatus) $("action-feedback").textContent = "";
}

// Remove uma ação do plano do cliente.
async function deleteAction(actionId) {
  if (!state.selected || !window.confirm("Remover esta ação?")) return;
  // O botão segue ativo durante o DELETE; uma repetição após o commit pode encontrar ação inexistente.
  try { await api(`/clients/${state.selected.id}/action-plan/${actionId}`, { method: "DELETE" }); setFeedback("action-feedback", "Ação removida."); await selectClient(state.selected.id); }
  catch (error) { setFeedback("action-feedback", error.message, true); }
}

// Marca a ação selecionada como concluída.
async function completeAction(actionId) {
  await updateActionStatus(actionId, "completed", "Ação concluída.");
}

// Move a ação selecionada para o estado em andamento.
async function startAction(actionId) {
  await updateActionStatus(actionId, "in_progress", "Ação marcada como em andamento.");
}

// Persiste o novo estado da ação e apresenta o resultado.
async function updateActionStatus(actionId, status, message) {
  if (!state.selected) return;
  try {
    await api(`/clients/${state.selected.id}/action-plan/${actionId}`, { method: "PATCH", body: JSON.stringify({ status }) });
    setFeedback("action-feedback", message);
    await selectClient(state.selected.id);
  } catch (error) { setFeedback("action-feedback", error.message, true); }
}

// Abre a janela de alteração da senha do usuário atual.
function openPasswordDialog() {
  $("password-status").textContent = "";
  $("password-dialog").showModal();
}

// Fecha e limpa a janela de alteração de senha.
function closePasswordDialog() {
  $("password-dialog").close();
  $("password-form").reset();
}

// Troca a senha do usuário atual e encerra a sessão para exigir novo login.
async function changePassword(event) {
  event.preventDefault();
  if ($("new-password").value !== $("confirm-password").value) { setFeedback("password-status", "As novas senhas não conferem.", true); return; }
  try {
    await api("/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: $("current-password").value, new_password: $("new-password").value }) });
    // Só após confirmação da API apaga a sessão local e exige novo login com a senha alterada.
    closePasswordDialog(); sessionStorage.clear(); state.token = null; state.refreshToken = null; show("login-view", true); show("app-view", false); $("login-error").textContent = "Senha alterada. Entre novamente com a nova senha.";
  } catch (error) { setFeedback("password-status", error.message, true); }
}

// Abre o formulário administrativo de criação de usuário.
function openUserDialog() {
  $("user-status").textContent = "";
  $("user-dialog").showModal();
}

// Fecha o formulário administrativo de usuário.
function closeUserDialog() {
  $("user-dialog").close();
  $("user-form").reset();
}

// Permite ao administrador criar usuários e atualizar as listas do workspace.
async function createUser(event) {
  event.preventDefault();
  if ($("new-user-password").value !== $("new-user-confirm").value) { setFeedback("user-status", "As senhas não conferem.", true); return; }
  try {
    // O campo exige preenchimento, mas não espelha o mínimo de dois caracteres do schema (achado 67).
    await api("/admin/users", { method: "POST", body: JSON.stringify({ name: $("new-user-name").value.trim(), email: $("new-user-email").value.trim(), role: $("new-user-role").value, password: $("new-user-password").value }) });
    // A conta já foi confirmada; um erro nas consultas de atualização não reverte a criação (achado 28).
    state.clients = await api("/clients"); state.advisors = await api("/clients/advisors"); state.team = await api("/admin/users?role=advisor"); renderClients(); renderOverview(); renderTeam(); if (state.clientProfile) renderClientProfile(state.clientProfile); $("user-form").reset(); setFeedback("user-status", "Usuário criado com sucesso.");
  } catch (error) { setFeedback("user-status", error.message, true); }
}

// Tenta revogar a sessão no servidor e sempre remove as credenciais deste painel.
async function logoutAdvisor() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);
  try {
    if (state.token) await api("/auth/logout", { method: "POST", signal: controller.signal });
  } catch (_) {
    // A sessão local ainda deve ser removida quando o servidor estiver indisponível.
  } finally {
    clearTimeout(timeout);
    state.token = null;
    state.refreshToken = null;
    sessionStorage.removeItem("talentum_advisor_token");
    sessionStorage.removeItem("talentum_advisor_refresh_token");
    location.reload();
  }
}

// Liga os formulários e controles da página aos handlers de negócio.
$("login-form").addEventListener("submit", login); $("client-search").addEventListener("input", renderClients); $("client-status-filter").addEventListener("change", renderClients); $("manage-team").addEventListener("click", openTeamDialog); $("close-team").addEventListener("click", closeTeamDialog); $("new-user").addEventListener("click", openUserDialog); $("close-user").addEventListener("click", closeUserDialog); $("user-form").addEventListener("submit", createUser); $("change-password").addEventListener("click", openPasswordDialog); $("close-password").addEventListener("click", closePasswordDialog); $("password-form").addEventListener("submit", changePassword); $("save-permissions").addEventListener("click", savePermissions); $("save-financial-profile").addEventListener("click", saveFinancialProfile); $("financial-form").addEventListener("submit", saveFinancialProfile); $("save-client-profile").addEventListener("click", saveClientProfile); $("client-profile-form").addEventListener("submit", saveClientProfile); $("save-assignment").addEventListener("click", saveAssignment); $("assignment-form").addEventListener("submit", saveAssignment); $("toggle-client-access").addEventListener("click", toggleClientAccess); $("reset-client-password").addEventListener("click", resetSelectedClientPassword); $("advisor-patrimony-form").addEventListener("submit", addAdvisorPatrimony); $("advisor-patrimony-cancel").addEventListener("click", cancelPatrimonyEdit); $("advisor-goal-form").addEventListener("submit", addAdvisorGoal); $("advisor-goal-cancel").addEventListener("click", cancelGoalEdit); $("goal-filter").addEventListener("change", renderQuickRecords); $("action-form").addEventListener("submit", saveAction); $("action-filter").addEventListener("change", renderActionPlan); $("action-cancel").addEventListener("click", cancelActionEdit); $("report-form").addEventListener("submit", publishReport); $("report-filter").addEventListener("change", () => renderReports(state.reports)); $("cancel-report-edit").addEventListener("click", cancelReportEdit); $("logout").addEventListener("click", () => { void logoutAdvisor(); });
$("document-form").addEventListener("submit", uploadDocument);
$("document-file").addEventListener("change", updateDocumentFileName);
$("investment-position-form").addEventListener("submit", addInvestmentPosition);
$("investment-transaction-form").addEventListener("submit", addInvestmentTransaction);
$("investment-transaction-date").value = localDateInputValue();
$("investment-position-cancel").addEventListener("click", cancelInvestmentPositionEdit);
$("investment-analytics-load").addEventListener("click", loadInvestmentAnalytics);
$("investment-analytics-export").addEventListener("click", exportInvestmentAnalytics);
$("investment-history-load").addEventListener("click", loadInvestmentSnapshots);
$("investment-history-capture").addEventListener("click", captureInvestmentSnapshot);
$("investment-monthly-load").addEventListener("click", () => loadInvestmentMonthlyPerformance());
$("notifications").addEventListener("click", openNotificationsDialog);
$("close-notifications").addEventListener("click", closeNotificationsDialog);
$("mark-all-notifications").addEventListener("click", markAllNotificationsRead);
$("save-notification-preferences").addEventListener("click", saveNotificationPreferences);
// Os filtros atualizam a seleção local e redesenham notificações já carregadas.
$("notification-type-filter").addEventListener("change", (event) => { state.notificationTypeFilter = event.target.value; renderNotifications(); });
$("notification-read-filter").addEventListener("change", (event) => { state.notificationReadFilter = event.target.value; renderNotifications(); });
$("refresh-workspace").addEventListener("click", refreshWorkspace);
$("open-market-research").addEventListener("click", openMarketResearch);
$("market-search-form").addEventListener("submit", searchMarket);
$("market-alert-form").addEventListener("submit", createMarketAlert);
$("market-alert-client").addEventListener("change", loadMarketAlerts);
// Delega edição e mudança de status dos alertas criados dinamicamente.
$("market-alert-list").addEventListener("click", (event) => { const editButton = event.target.closest("[data-market-alert-edit]"); if (editButton) { startEditMarketAlert(Number(editButton.dataset.marketAlertEdit)); return; } const statusButton = event.target.closest("[data-market-alert-status]"); if (statusButton) { updateMarketAlertStatus(Number(statusButton.dataset.marketAlertStatus), statusButton.dataset.marketAlertNextStatus); } });
$("market-alert-cancel-edit").addEventListener("click", cancelMarketAlertEdit);
$("market-watchlist-form").addEventListener("submit", createMarketWatchlistItem);
$("market-watchlist-client").addEventListener("change", loadMarketWatchlist);
// Delega a remoção e a abertura de ativos inseridos dinamicamente na lista acompanhada.
$("market-watchlist-list").addEventListener("click", (event) => { const removeButton = event.target.closest("[data-market-watchlist-remove]"); if (removeButton) { removeMarketWatchlistItem(Number(removeButton.dataset.marketWatchlistRemove)); return; } const openButton = event.target.closest("[data-market-watchlist-open]"); if (openButton) openMarketWatchlistItem(openButton); });
$("market-results").addEventListener("click", toggleMarketDetails);
// Mantém no máximo três ativos selecionados e atualiza a barra de comparação.
$("market-results").addEventListener("change", (event) => { const checkbox = event.target.closest("[data-market-compare]"); if (!checkbox) return; const key = checkbox.dataset.marketCompare; if (checkbox.checked && !state.marketCompareKeys.includes(key)) { if (state.marketCompareKeys.length >= 3) { checkbox.checked = false; return; } state.marketCompareKeys.push(key); } else { state.marketCompareKeys = state.marketCompareKeys.filter((item) => item !== key); } refreshMarketCompareToolbar(); });
// Tipo, setor e ordenação reaproveitam os resultados atuais sem repetir a busca na API.
$("market-type-filter").addEventListener("change", (event) => { state.marketTypeFilter = event.target.value; renderMarketResults(); });
$("market-sector-filter").addEventListener("change", (event) => { state.marketSectorFilter = event.target.value; renderMarketResults(); });
$("market-sort").addEventListener("change", (event) => { state.marketSort = event.target.value; renderMarketResults(); });
$("market-compare-button").addEventListener("click", compareSelectedMarketAssets);
$("market-export-button").addEventListener("click", exportMarketAnalysis);
$("market-compare-close").addEventListener("click", () => show("market-compare-panel", false));
$("suitability-approve").addEventListener("click", () => reviewSuitability(true));
$("suitability-reject").addEventListener("click", () => reviewSuitability(false));
// Encaminha busca, mudança de categoria, inclusão/remoção e publicação da proposta pelo editor dinâmico.
$("suitability-proposal-editor").addEventListener("submit", (event) => { if (event.target.id === "suitability-proposal-search") void searchSuitabilityProposal(event); });
$("suitability-proposal-editor").addEventListener("change", (event) => { if (event.target.id !== "suitability-proposal-category" || !state.suitabilityProposalDraft) return; state.suitabilityProposalDraft.selectedClass = event.target.value; renderSuitabilityProposalEditor(state.suitability); });
$("suitability-proposal-editor").addEventListener("click", (event) => {
  const add = event.target.closest("[data-suitability-add]");
  const remove = event.target.closest("[data-suitability-remove]");
  if (add && state.suitabilityProposalDraft && state.suitability) {
    const asset = state.suitabilityProposalSearchResults[Number(add.dataset.suitabilityAdd)];
    const assetClass = state.suitabilityProposalDraft.selectedClass;
    if (!asset || !assetClass) return;
    const current = state.suitabilityProposalDraft.assetsByClass[assetClass] || [];
    if (current.length >= 20) { setFeedback("suitability-status", "O limite é de 20 ativos por categoria.", true); return; }
    // Evita repetição na categoria selecionada; cada categoria mantém sua lista independente.
    if (!current.some((item) => item.symbol.toLowerCase() === asset.symbol.toLowerCase() && item.market === asset.market)) {
      state.suitabilityProposalDraft.assetsByClass[assetClass] = [...current, { symbol: asset.symbol, name: asset.name, market: asset.market, asset_type: asset.asset_type || null, currency: asset.currency || null }];
      renderSuitabilityProposalEditor(state.suitability);
    }
    return;
  }
  if (remove && state.suitabilityProposalDraft && state.suitability) {
    const [allocationIndex, assetIndex] = remove.dataset.suitabilityRemove.split(":").map(Number);
    const assetClass = state.suitability.recommendation.allocations[allocationIndex]?.asset_class;
    if (!assetClass) return;
    state.suitabilityProposalDraft.assetsByClass[assetClass].splice(assetIndex, 1);
    renderSuitabilityProposalEditor(state.suitability);
    return;
  }
  if (event.target.closest("#suitability-proposal-publish")) void publishSuitabilityProposal();
});
if (state.token) start();
checkApiHealth();
