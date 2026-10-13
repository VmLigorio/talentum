// Talentum — mobile-react-native-prototype/src/api.ts
// Responsabilidade: centraliza comunicação HTTP, autenticação e sessão segura do protótipo.

import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';
import * as FileSystem from 'expo-file-system';

// O endereço pode ser trocado sem alterar o código usando EXPO_PUBLIC_API_URL.
export const API_URL =
  process.env.EXPO_PUBLIC_API_URL?.replace(/\/+$/, '') ||
  'http://192.168.1.2:8001';

// Usa chaves distintas para manter access token e refresh token no armazenamento seguro.
const ACCESS_TOKEN_KEY = 'talentum_prototype_access_token';
const REFRESH_TOKEN_KEY = 'talentum_prototype_refresh_token';

// Forma mínima da conta autenticada devolvida pelo backend.
export type User = {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
};

// Indicadores agregados usados na tela inicial do cliente.
export type Dashboard = {
  patrimony_total?: number | null;
  monthly_income?: number | null;
  monthly_expenses?: number | null;
  goals?: Array<{ title: string; percentage: number }>;
};

// Subconjunto dos campos de posição consumidos pelas telas do protótipo.
export type InvestmentPosition = {
  id: number;
  symbol: string;
  name?: string | null;
  market: 'br' | 'global';
  quantity: number;
  average_price: number;
  currency?: string | null;
  current_value?: number | null;
  pnl?: number | null;
  pnl_percent?: number | null;
  allocation_percent?: number | null;
};

// Subconjunto da resposta consolidada usado pelo protótipo; a API também envia outros contadores e valores derivados.
export type Portfolio = {
  invested_total?: number | null;
  current_total?: number | null;
  pnl_total?: number | null;
  position_count: number;
  total_currency?: string | null;
  mixed_currency?: boolean;
  currency_totals?: Array<{ currency: string; invested_total: number; current_total: number; pnl_total: number; pnl_percent?: number | null; position_count: number }>;
  allocations?: Array<{ market: 'br' | 'global'; label: string; currency: string; value: number; percentage: number }>;
  positions: InvestmentPosition[];
};

// Metadados de arquivo usados nas listas e no visualizador de documentos.
export type DocumentItem = {
  id: number;
  original_name: string;
  kind: string;
  content_type?: string;
  size_bytes: number;
  description?: string | null;
  created_at: string;
};

// Estrutura flexível para respostas que ainda não têm contrato tipado específico.
export type JsonMap = Record<string, any>;

// Notificação persistida e seu estado de leitura.
export type NotificationItem = {
  id: number;
  user_id: number;
  client_id: number;
  kind: string;
  title: string;
  message: string;
  read_at?: string | null;
  created_at: string;
};

// Condição de preço monitorada e seu estado no backend.
export type MarketAlert = {
  id: number;
  client_id: number;
  client_name: string;
  created_by_user_id: number;
  symbol: string;
  market: 'br' | 'global';
  target_price: number;
  condition: 'at_or_below' | 'at_or_above';
  status: 'active' | 'paused' | 'triggered' | 'cancelled';
  last_price?: number | null;
  triggered_at?: string | null;
  created_at: string;
  updated_at: string;
};

// Áreas do cliente que podem ser editadas conforme as permissões concedidas.
export type ClientPermissions = {
  can_edit_profile?: boolean;
  can_edit_financial_profile?: boolean;
  can_edit_patrimony?: boolean;
  can_edit_goals?: boolean;
  can_upload_documents?: boolean;
};

// Guarda a preferência de login biométrico separada das credenciais da sessão.
const BIOMETRIC_ENABLED_KEY = 'talentum_prototype_biometric_enabled';

// Erro de comunicação com a API acompanhado do status HTTP quando disponível.
export class ApiError extends Error {
  // Preserva o status HTTP junto à mensagem para decisões de fluxo no cliente.
  constructor(
    message: string,
    public readonly status = 0,
  ) {
    super(message);
  }
}

// Mantém os tokens fora do AsyncStorage comum, usando o armazenamento seguro da plataforma.
async function saveTokens(accessToken: string, refreshToken: string) {
  // A gravação em sequência pode deixar o token de acesso salvo se a segunda etapa falhar.
  await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, accessToken);
  await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refreshToken);
}

// Remove os tokens armazenados com segurança.
async function clearTokens() {
  // As exclusões são sequenciais; erro na primeira pode deixar a segunda chave no SecureStore (achado 116).
  await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
  await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
}

// Cliente HTTP do protótipo; mantém autenticação e chamadas a recursos do backend.
export class TalentumApi {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private refreshPromise: Promise<void> | null = null;
  private sessionVersion = 0;
  private storageQueue: Promise<void> = Promise.resolve();
  private expirationListeners = new Set<() => void>();

  // Registra uma função chamada quando a sessão deixa de ser válida.
  onSessionExpired(listener: () => void) {
    this.expirationListeners.add(listener);
    return () => { this.expirationListeners.delete(listener); };
  }

  // Enfileira gravações no armazenamento para preservar a ordem dos tokens.
  private writeStorage(operation: () => Promise<void>) {
    const pending = this.storageQueue.then(operation);
    this.storageQueue = pending.catch(() => {});
    return pending;
  }

  // Impede que uma resposta atrasada altere uma sessão mais recente.
  private checkSession(version: number) {
    if (version !== this.sessionVersion) {
      throw new ApiError('A sessão foi alterada. Tente novamente.', 401);
    }
  }

  // Restaura credenciais seguras e verifica se ainda pertencem à sessão atual.
  async restoreSession() {
    const version = this.sessionVersion;
    await this.storageQueue;
    const accessToken = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
    const refreshToken = await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
    this.checkSession(version);
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    return Boolean(this.accessToken && this.refreshToken);
  }

  // Revoga a sessão no servidor quando possível e sempre apaga os tokens locais.
  async logout(revokeRemote = true) {
    const accessToken = this.accessToken;
    this.sessionVersion += 1;
    this.accessToken = null;
    this.refreshToken = null;
    this.refreshPromise = null;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    try {
      if (revokeRemote && accessToken) {
        await fetch(`${API_URL}/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${accessToken}` },
          signal: controller.signal,
        });
      }
    } catch {
      // A indisponibilidade da rede não impede o encerramento local da sessão.
    } finally {
      clearTimeout(timeout);
      await this.writeStorage(clearTokens);
    }
  }

  // Limpa credenciais expiradas e comunica que é necessário autenticar novamente.
  private async expireSession() {
    const clearing = this.logout(false);
    this.expirationListeners.forEach((listener) => listener());
    await clearing;
  }

  // Autentica o usuário e salva os tokens emitidos pelo backend.
  async login(email: string, password: string) {
    await this.logout();
    const version = this.sessionVersion;
    const data = await this.request<{ access_token: string; refresh_token: string }>(
      '/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      },
      false,
    );
    await this.acceptTokens(data, version);
  }

  // Consulta a identidade da conta autenticada.
  async me() {
    return this.request<User>('/auth/me');
  }

  // Busca o resumo financeiro do cliente.
  async dashboard(clientId: number) {
    return this.request<Dashboard>('/clients/' + clientId + '/dashboard');
  }

  // Consulta posições e valores da carteira do cliente.
  async portfolio(clientId: number) {
    return this.request<Portfolio>('/clients/' + clientId + '/investment-portfolio');
  }

  // Carrega o desempenho mensal e a comparação disponível com o CDI.
  async investmentMonthlyPerformance(clientId: number) {
    return this.request<JsonMap>('/clients/' + clientId + '/investment-monthly-performance');
  }

  // Busca a primeira página de até 100 operações, sem filtros neste protótipo.
  async investmentTransactions(clientId: number) {
    return this.request<JsonMap[]>('/clients/' + clientId + '/investment-transactions?limit=100');
  }

  // Lista documentos cadastrados para o cliente.
  async documents(clientId: number) {
    return this.request<DocumentItem[]>('/clients/' + clientId + '/documents');
  }

  // Baixa o arquivo de documento e o salva no local temporário.
  async downloadDocument(clientId: number, documentId: number, originalName: string) {
    const filename = originalName.replace(/[^a-zA-Z0-9._-]/g, '_') || `documento-${documentId}`;
    // Prefere o cache para arquivos temporários e usa o diretório persistente como fallback.
    const destination = (FileSystem.cacheDirectory || FileSystem.documentDirectory || '') + filename;
    if (!destination) throw new ApiError('O armazenamento temporário não está disponível.');
    return this.downloadFileAttempt(`/clients/${clientId}/documents/${documentId}/download`, destination, true);
  }

  // Solicita o PDF detalhado e o salva no local temporário.
  async downloadInvestmentReport(clientId: number) {
    // Mantém a mesma prioridade de armazenamento usada no download de documentos.
    const destination = (FileSystem.cacheDirectory || FileSystem.documentDirectory || '') + `relatorio-carteira-talentum-${clientId}.pdf`;
    if (!destination) throw new ApiError('O armazenamento temporário não está disponível.');
    return this.downloadFileAttempt(`/clients/${clientId}/investment-report.pdf`, destination, true);
  }

  // Baixa um arquivo com autenticação, renovação de sessão e validação de resposta.
  private async downloadFileAttempt(path: string, destination: string, retryOnUnauthorized: boolean): Promise<string> {
    const version = this.sessionVersion;
    const sentAccessToken = this.accessToken;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30_000);
    let response: Response;
    try {
      response = await fetch(`${API_URL}${path}`, {
        signal: controller.signal,
        headers: { Authorization: `Bearer ${sentAccessToken || ''}` },
      });
    } catch {
      throw new ApiError(controller.signal.aborted ? 'O download demorou demais. Tente novamente.' : 'Não foi possível conectar à API.');
    } finally {
      // fetch resolve nos cabeçalhos; o timeout atual não cobre a leitura do corpo abaixo.
      clearTimeout(timeout);
    }
    this.checkSession(version);
    if (response.status === 401) {
      if (retryOnUnauthorized && this.refreshToken) {
        if (sentAccessToken === this.accessToken) await this.refresh();
        this.checkSession(version);
        return this.downloadFileAttempt(path, destination, false);
      }
      await this.expireSession();
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ApiError(typeof body?.detail === 'string' ? body.detail : 'Não foi possível baixar o documento.', response.status);
    }
    // A conversão do corpo em bytes pode continuar sem limite depois de fetch retornar.
    const bytes = new Uint8Array(await response.arrayBuffer());
    // O Expo recebe o conteúdo Base64 ao gravar texto com a opção de codificação Base64.
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    let encoded = '';
    for (let i = 0; i < bytes.length; i += 3) {
      const a = bytes[i]; const b = bytes[i + 1]; const c = bytes[i + 2];
      encoded += alphabet[a >> 2] + alphabet[((a & 3) << 4) | ((b ?? 0) >> 4)];
      encoded += b === undefined ? '=' : alphabet[((b & 15) << 2) | ((c ?? 0) >> 6)];
      encoded += c === undefined ? '=' : alphabet[c & 63];
    }
    await FileSystem.writeAsStringAsync(destination, encoded, { encoding: FileSystem.EncodingType.Base64 });
    // A sessão é revalidada após gravar; uma troca durante o download pode deixar o arquivo local.
    this.checkSession(version);
    return destination;
  }

  // Lista os itens patrimoniais do cliente.
  async patrimony(clientId: number) {
    return this.request<JsonMap[]>('/clients/' + clientId + '/patrimony');
  }

  // Lista metas financeiras do cliente.
  async goals(clientId: number) {
    return this.request<JsonMap[]>('/clients/' + clientId + '/goals');
  }

  // Consulta tarefas do plano de acompanhamento.
  async actionPlan(clientId: number) {
    return this.request<JsonMap[]>('/clients/' + clientId + '/action-plan');
  }

  // Lista relatórios disponíveis para o cliente.
  async reports(clientId: number) {
    return this.request<JsonMap[]>('/clients/' + clientId + '/reports');
  }

  // Consulta o perfil cadastral do cliente.
  async profile(clientId: number) {
    return this.request<JsonMap>('/clients/' + clientId + '/profile');
  }

  // Consulta dados do perfil financeiro, tratando ausência como resultado vazio.
  async financialProfile(clientId: number) {
    try {
      return await this.request<JsonMap>('/clients/' + clientId + '/financial-profile');
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) return null;
      throw cause;
    }
  }

  // Carrega permissões de edição do cliente.
  async permissions(clientId: number) {
    return this.request<ClientPermissions>('/clients/' + clientId + '/permissions');
  }

  // Lista até 50 notificações por padrão; a contagem total tem endpoint próprio.
  async notifications(unreadOnly = false) {
    return this.request<NotificationItem[]>(
      '/notifications?unread_only=' + String(unreadOnly),
    );
  }

  // Consulta preferências de recebimento de notificações.
  async notificationPreferences() {
    return this.request<JsonMap>('/notifications/preferences');
  }

  // Atualiza as preferências de notificações do usuário.
  async updateNotificationPreferences(body: JsonMap) {
    return this.request<JsonMap>('/notifications/preferences', {
      method: 'PATCH',
      body: JSON.stringify(body),
    });
  }

  // Marca uma notificação específica como lida.
  async markNotificationRead(id: number) {
    return this.request<NotificationItem>('/notifications/' + id + '/read', {
      method: 'PATCH',
    });
  }

  // Marca todas as notificações do usuário como lidas.
  async markAllNotificationsRead() {
    await this.request<null>('/notifications/read-all', { method: 'PATCH' });
  }

  // Lista alertas de preço do usuário autenticado.
  async marketAlerts() {
    return this.request<MarketAlert[]>('/market/alerts');
  }

  // Cria um alerta de mercado com os parâmetros informados.
  async createMarketAlert(payload: {
    symbol: string;
    market: 'br' | 'global';
    target_price: number;
    condition: 'at_or_below' | 'at_or_above';
  }) {
    return this.request<MarketAlert>('/market/alerts', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // Atualiza parâmetros de um alerta existente.
  async updateMarketAlert(
    id: number,
    payload: {
      target_price?: number;
      condition?: 'at_or_below' | 'at_or_above';
      status?: 'active' | 'paused' | 'triggered' | 'cancelled';
    },
  ) {
    return this.request<MarketAlert>('/market/alerts/' + id, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  // Cancela o alerta de preço identificado.
  async cancelMarketAlert(id: number) {
    return this.request<MarketAlert>('/market/alerts/' + id, {
      method: 'DELETE',
    });
  }

  // Carrega o questionário e o retrato financeiro para a avaliação.
  async suitabilityQuestionnaire() {
    return this.request<JsonMap>('/clients/me/suitability/questionnaire');
  }

  // Consulta a avaliação de suitability mais recente.
  async suitability() {
    try {
      return await this.request<JsonMap | null>('/clients/me/suitability');
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) return null;
      throw cause;
    }
  }

  // Envia respostas e confirmação do contexto financeiro.
  async submitSuitability(
    objective: string,
    answers: JsonMap,
    financialDataVersion: string,
    confirmFinancialSituation: boolean,
  ) {
    return this.request<JsonMap>('/clients/me/suitability', {
      method: 'POST',
      body: JSON.stringify({
        objective,
        answers,
        financial_data_version: financialDataVersion,
        confirm_financial_situation: confirmFinancialSituation,
      }),
    });
  }

  // Registra a resposta do cliente à carteira recomendada.
  async respondToSuitability(assessmentId: number, response: string, note?: string) {
    return this.request<JsonMap>(`/clients/me/suitability/${assessmentId}/response`, {
      method: 'POST',
      body: JSON.stringify({ response, note }),
    });
  }

  // Adiciona um item patrimonial ao cliente.
  async createPatrimony(clientId: number, body: JsonMap) {
    return this.request<JsonMap>(`/clients/${clientId}/patrimony`, { method: 'POST', body: JSON.stringify(body) });
  }

  // Atualiza um item patrimonial existente.
  async updatePatrimony(clientId: number, itemId: number, body: JsonMap) {
    return this.request<JsonMap>(`/clients/${clientId}/patrimony/${itemId}`, { method: 'PATCH', body: JSON.stringify(body) });
  }

  // Remove um item patrimonial do cliente.
  async deletePatrimony(clientId: number, itemId: number) {
    return this.request<null>(`/clients/${clientId}/patrimony/${itemId}`, { method: 'DELETE' });
  }

  // Cria uma meta financeira.
  async createGoal(clientId: number, body: JsonMap) {
    return this.request<JsonMap>(`/clients/${clientId}/goals`, { method: 'POST', body: JSON.stringify(body) });
  }

  // Atualiza uma meta financeira existente.
  async updateGoal(clientId: number, goalId: number, body: JsonMap) {
    return this.request<JsonMap>(`/clients/${clientId}/goals/${goalId}`, { method: 'PATCH', body: JSON.stringify(body) });
  }

  // Remove uma meta financeira.
  async deleteGoal(clientId: number, goalId: number) {
    return this.request<null>(`/clients/${clientId}/goals/${goalId}`, { method: 'DELETE' });
  }

  // Atualiza os dados cadastrais do cliente.
  async updateProfile(clientId: number, body: JsonMap) {
    return this.request<null>(`/clients/${clientId}/profile`, { method: 'PUT', body: JSON.stringify(body) });
  }

  // Salva renda, despesas e perfil de risco do cliente.
  async updateFinancialProfile(clientId: number, body: JsonMap) {
    // A API devolve o perfil persistido, mesmo que a tela atual recarregue o workspace.
    return this.request<JsonMap>(`/clients/${clientId}/financial-profile`, { method: 'PUT', body: JSON.stringify(body) });
  }

  // Envia a alteração de senha para a conta autenticada.
  async changePassword(currentPassword: string, newPassword: string) {
    return this.request<null>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
  }

  // Verifica se o aparelho aceita autenticação biométrica.
  async biometricAvailable() {
    const hardware = await LocalAuthentication.hasHardwareAsync();
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    return hardware && enrolled;
  }

  // Consulta a preferência local de autenticação biométrica.
  async biometricEnabled() {
    return (await SecureStore.getItemAsync(BIOMETRIC_ENABLED_KEY)) === 'true';
  }

  // Salva ou remove a preferência local de biometria.
  async setBiometricEnabled(enabled: boolean) {
    if (enabled) {
      await SecureStore.setItemAsync(BIOMETRIC_ENABLED_KEY, 'true');
    } else {
      await SecureStore.deleteItemAsync(BIOMETRIC_ENABLED_KEY);
    }
  }

  // Solicita ao sistema operacional uma autenticação biométrica.
  async authenticateBiometric() {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: 'Confirme sua identidade para acessar o Talentum',
      cancelLabel: 'Cancelar',
      disableDeviceFallback: false,
    });
    return result.success;
  }

  // Armazena tokens somente se a versão da sessão ainda for válida.
  private async acceptTokens(data: { access_token: string; refresh_token: string }, version: number) {
    this.checkSession(version);
    await this.writeStorage(async () => {
      this.checkSession(version);
      await saveTokens(data.access_token, data.refresh_token);
    });
    this.checkSession(version);
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
  }

  // Compartilha uma renovação em andamento para evitar trocas concorrentes.
  private refresh(): Promise<void> {
    if (this.refreshPromise) return this.refreshPromise;
    const pending = this.performRefresh().finally(() => {
      if (this.refreshPromise === pending) this.refreshPromise = null;
    });
    this.refreshPromise = pending;
    return pending;
  }

  // Troca o token atual e invalida a sessão apenas quando o servidor rejeita a renovação (401).
  private async performRefresh() {
    if (!this.refreshToken) throw new ApiError('Sessão expirada.', 401);
    const version = this.sessionVersion;
    try {
      const data = await this.request<{ access_token: string; refresh_token: string }>(
        '/auth/refresh',
        {
          method: 'POST',
          body: JSON.stringify({ refresh_token: this.refreshToken }),
        },
        false,
      );
      await this.acceptTokens(data, version);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401 && version === this.sessionVersion) {
        await this.expireSession();
      }
      throw cause;
    }
  }

  // Envia requisições JSON, valida a sessão e tenta renovar credenciais após 401.
  private async request<T>(
    path: string,
    init: RequestInit = {},
    retryOnUnauthorized = true,
  ): Promise<T> {
    const version = this.sessionVersion;
    const sentAccessToken = this.accessToken;
    const authenticated = path !== '/auth/login' && path !== '/auth/refresh';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30_000);
    let response: Response;
    let data: any;
    let invalidJson = false;
    try {
      response = await fetch(API_URL + path, {
        ...init,
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          ...(sentAccessToken
            ? { Authorization: 'Bearer ' + sentAccessToken }
            : {}),
          ...(init.headers || {}),
        },
      });
      data = await response.json().catch(() => { invalidJson = true; return null; });
    } catch {
      throw new ApiError(
        controller.signal.aborted ? 'A conexão demorou demais. Tente novamente.' :
          'Não foi possível conectar à API em ' +
          API_URL +
          '. Verifique a rede e a porta 8001.',
      );
    } finally {
      clearTimeout(timeout);
    }
    if (controller.signal.aborted) throw new ApiError('A conexão demorou demais. Tente novamente.');
    this.checkSession(version);
    if (response.status === 401 && authenticated) {
      if (retryOnUnauthorized && this.refreshToken) {
        // Uma resposta atrasada pode usar o token anterior à renovação já concluída.
        if (sentAccessToken === this.accessToken) await this.refresh();
        this.checkSession(version);
        return this.request<T>(path, init, false);
      }
      await this.expireSession();
    }
    if (!response.ok) {
      const message =
        data && typeof data.detail === 'string'
          ? data.detail
          : 'Não foi possível concluir a operação.';
      throw new ApiError(message, response.status);
    }
    if (invalidJson && response.status !== 204) {
      throw new ApiError('A API retornou uma resposta inválida.', 502);
    }
    return data as T;
  }
}
