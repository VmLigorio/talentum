// Talentum — mobile-react-native-prototype/src/api.ts
// Responsabilidade: centraliza comunicação HTTP, autenticação e sessão segura do protótipo.

import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';
import * as FileSystem from 'expo-file-system';

// O endereço pode ser trocado sem alterar o código usando EXPO_PUBLIC_API_URL.
export const API_URL =
  process.env.EXPO_PUBLIC_API_URL?.replace(/\/+$/, '') ||
  'http://192.168.1.2:8001';

const ACCESS_TOKEN_KEY = 'talentum_prototype_access_token';
const REFRESH_TOKEN_KEY = 'talentum_prototype_refresh_token';

export type User = {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
};

export type Dashboard = {
  patrimony_total?: number | null;
  monthly_income?: number | null;
  monthly_expenses?: number | null;
  goals?: Array<{ title: string; percentage: number }>;
};

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

export type DocumentItem = {
  id: number;
  original_name: string;
  kind: string;
  content_type?: string;
  size_bytes: number;
  description?: string | null;
  created_at: string;
};

export type JsonMap = Record<string, any>;

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

export type ClientPermissions = {
  can_edit_profile?: boolean;
  can_edit_financial_profile?: boolean;
  can_edit_patrimony?: boolean;
  can_edit_goals?: boolean;
  can_upload_documents?: boolean;
};

const BIOMETRIC_ENABLED_KEY = 'talentum_prototype_biometric_enabled';

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status = 0,
  ) {
    super(message);
  }
}

// Mantém os tokens fora do AsyncStorage comum, usando o armazenamento seguro da plataforma.
async function saveTokens(accessToken: string, refreshToken: string) {
  await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, accessToken);
  await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refreshToken);
}

async function clearTokens() {
  await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
  await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
}

// Cliente mínimo com tratamento de erro compreensível para o protótipo.
export class TalentumApi {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private refreshPromise: Promise<void> | null = null;
  private sessionVersion = 0;
  private storageQueue: Promise<void> = Promise.resolve();
  private expirationListeners = new Set<() => void>();

  onSessionExpired(listener: () => void) {
    this.expirationListeners.add(listener);
    return () => { this.expirationListeners.delete(listener); };
  }

  private writeStorage(operation: () => Promise<void>) {
    const pending = this.storageQueue.then(operation);
    this.storageQueue = pending.catch(() => {});
    return pending;
  }

  private checkSession(version: number) {
    if (version !== this.sessionVersion) {
      throw new ApiError('A sessão foi alterada. Tente novamente.', 401);
    }
  }

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

  async logout() {
    this.sessionVersion += 1;
    this.accessToken = null;
    this.refreshToken = null;
    this.refreshPromise = null;
    await this.writeStorage(clearTokens);
  }

  private async expireSession() {
    const clearing = this.logout();
    this.expirationListeners.forEach((listener) => listener());
    await clearing;
  }

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

  async me() {
    return this.request<User>('/auth/me');
  }

  async dashboard(clientId: number) {
    return this.request<Dashboard>('/clients/' + clientId + '/dashboard');
  }

  async portfolio(clientId: number) {
    return this.request<Portfolio>('/clients/' + clientId + '/investment-portfolio');
  }

  async investmentMonthlyPerformance(clientId: number) {
    return this.request<JsonMap>('/clients/' + clientId + '/investment-monthly-performance');
  }

  async investmentTransactions(clientId: number) {
    return this.request<JsonMap[]>('/clients/' + clientId + '/investment-transactions?limit=100');
  }

  async documents(clientId: number) {
    return this.request<DocumentItem[]>('/clients/' + clientId + '/documents');
  }

  async downloadDocument(clientId: number, documentId: number, originalName: string) {
    const filename = originalName.replace(/[^a-zA-Z0-9._-]/g, '_') || `documento-${documentId}`;
    const destination = (FileSystem.cacheDirectory || FileSystem.documentDirectory || '') + filename;
    if (!destination) throw new ApiError('O armazenamento temporário não está disponível.');
    return this.downloadFileAttempt(`/clients/${clientId}/documents/${documentId}/download`, destination, true);
  }

  async downloadInvestmentReport(clientId: number) {
    const destination = (FileSystem.cacheDirectory || FileSystem.documentDirectory || '') + `relatorio-carteira-talentum-${clientId}.pdf`;
    if (!destination) throw new ApiError('O armazenamento temporário não está disponível.');
    return this.downloadFileAttempt(`/clients/${clientId}/investment-report.pdf`, destination, true);
  }

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
    } finally { clearTimeout(timeout); }
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
    const bytes = new Uint8Array(await response.arrayBuffer());
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    let encoded = '';
    for (let i = 0; i < bytes.length; i += 3) {
      const a = bytes[i]; const b = bytes[i + 1]; const c = bytes[i + 2];
      encoded += alphabet[a >> 2] + alphabet[((a & 3) << 4) | ((b ?? 0) >> 4)];
      encoded += b === undefined ? '=' : alphabet[((b & 15) << 2) | ((c ?? 0) >> 6)];
      encoded += c === undefined ? '=' : alphabet[c & 63];
    }
    await FileSystem.writeAsStringAsync(destination, encoded, { encoding: FileSystem.EncodingType.Base64 });
    this.checkSession(version);
    return destination;
  }

  async patrimony(clientId: number) {
    return this.request<JsonMap[]>('/clients/' + clientId + '/patrimony');
  }

  async goals(clientId: number) {
    return this.request<JsonMap[]>('/clients/' + clientId + '/goals');
  }

  async actionPlan(clientId: number) {
    return this.request<JsonMap[]>('/clients/' + clientId + '/action-plan');
  }

  async reports(clientId: number) {
    return this.request<JsonMap[]>('/clients/' + clientId + '/reports');
  }

  async profile(clientId: number) {
    return this.request<JsonMap>('/clients/' + clientId + '/profile');
  }

  async financialProfile(clientId: number) {
    try {
      return await this.request<JsonMap>('/clients/' + clientId + '/financial-profile');
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) return null;
      throw cause;
    }
  }

  async permissions(clientId: number) {
    return this.request<ClientPermissions>('/clients/' + clientId + '/permissions');
  }

  async notifications(unreadOnly = false) {
    return this.request<NotificationItem[]>(
      '/notifications?unread_only=' + String(unreadOnly),
    );
  }

  async notificationPreferences() {
    return this.request<JsonMap>('/notifications/preferences');
  }

  async updateNotificationPreferences(body: JsonMap) {
    return this.request<JsonMap>('/notifications/preferences', {
      method: 'PATCH',
      body: JSON.stringify(body),
    });
  }

  async markNotificationRead(id: number) {
    return this.request<NotificationItem>('/notifications/' + id + '/read', {
      method: 'PATCH',
    });
  }

  async markAllNotificationsRead() {
    await this.request<null>('/notifications/read-all', { method: 'PATCH' });
  }

  async marketAlerts() {
    return this.request<MarketAlert[]>('/market/alerts');
  }

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

  async cancelMarketAlert(id: number) {
    return this.request<MarketAlert>('/market/alerts/' + id, {
      method: 'DELETE',
    });
  }

  async suitabilityQuestionnaire() {
    return this.request<JsonMap>('/clients/me/suitability/questionnaire');
  }

  async suitability() {
    try {
      return await this.request<JsonMap | null>('/clients/me/suitability');
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) return null;
      throw cause;
    }
  }

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

  async respondToSuitability(assessmentId: number, response: string, note?: string) {
    return this.request<JsonMap>(`/clients/me/suitability/${assessmentId}/response`, {
      method: 'POST',
      body: JSON.stringify({ response, note }),
    });
  }

  async createPatrimony(clientId: number, body: JsonMap) {
    return this.request<JsonMap>(`/clients/${clientId}/patrimony`, { method: 'POST', body: JSON.stringify(body) });
  }

  async updatePatrimony(clientId: number, itemId: number, body: JsonMap) {
    return this.request<JsonMap>(`/clients/${clientId}/patrimony/${itemId}`, { method: 'PATCH', body: JSON.stringify(body) });
  }

  async deletePatrimony(clientId: number, itemId: number) {
    return this.request<null>(`/clients/${clientId}/patrimony/${itemId}`, { method: 'DELETE' });
  }

  async createGoal(clientId: number, body: JsonMap) {
    return this.request<JsonMap>(`/clients/${clientId}/goals`, { method: 'POST', body: JSON.stringify(body) });
  }

  async updateGoal(clientId: number, goalId: number, body: JsonMap) {
    return this.request<JsonMap>(`/clients/${clientId}/goals/${goalId}`, { method: 'PATCH', body: JSON.stringify(body) });
  }

  async deleteGoal(clientId: number, goalId: number) {
    return this.request<null>(`/clients/${clientId}/goals/${goalId}`, { method: 'DELETE' });
  }

  async updateProfile(clientId: number, body: JsonMap) {
    return this.request<null>(`/clients/${clientId}/profile`, { method: 'PUT', body: JSON.stringify(body) });
  }

  async updateFinancialProfile(clientId: number, body: JsonMap) {
    return this.request<null>(`/clients/${clientId}/financial-profile`, { method: 'PUT', body: JSON.stringify(body) });
  }

  async changePassword(currentPassword: string, newPassword: string) {
    return this.request<null>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
  }

  async biometricAvailable() {
    const hardware = await LocalAuthentication.hasHardwareAsync();
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    return hardware && enrolled;
  }

  async biometricEnabled() {
    return (await SecureStore.getItemAsync(BIOMETRIC_ENABLED_KEY)) === 'true';
  }

  async setBiometricEnabled(enabled: boolean) {
    if (enabled) {
      await SecureStore.setItemAsync(BIOMETRIC_ENABLED_KEY, 'true');
    } else {
      await SecureStore.deleteItemAsync(BIOMETRIC_ENABLED_KEY);
    }
  }

  async authenticateBiometric() {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: 'Confirme sua identidade para acessar o Talentum',
      cancelLabel: 'Cancelar',
      disableDeviceFallback: false,
    });
    return result.success;
  }

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

  private refresh(): Promise<void> {
    if (this.refreshPromise) return this.refreshPromise;
    const pending = this.performRefresh().finally(() => {
      if (this.refreshPromise === pending) this.refreshPromise = null;
    });
    this.refreshPromise = pending;
    return pending;
  }

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
