// Talentum — mobile-react-native-prototype/src/api.ts
// Responsabilidade: centraliza comunicação HTTP, autenticação e sessão segura do protótipo.

import * as SecureStore from 'expo-secure-store';

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
};

export type Portfolio = {
  invested_total?: number | null;
  current_total?: number | null;
  pnl_total?: number | null;
  position_count: number;
  positions: InvestmentPosition[];
};

export type DocumentItem = {
  id: number;
  original_name: string;
  kind: string;
  size_bytes: number;
  description?: string | null;
  created_at: string;
};

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

  async restoreSession() {
    this.accessToken = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
    this.refreshToken = await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
    return Boolean(this.accessToken && this.refreshToken);
  }

  async logout() {
    this.accessToken = null;
    this.refreshToken = null;
    await clearTokens();
  }

  async login(email: string, password: string) {
    const data = await this.request<{ access_token: string; refresh_token: string }>(
      '/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      },
      false,
    );
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    await saveTokens(data.access_token, data.refresh_token);
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

  async documents(clientId: number) {
    return this.request<DocumentItem[]>('/clients/' + clientId + '/documents');
  }

  private async refresh() {
    if (!this.refreshToken) throw new ApiError('Sessão expirada.', 401);
    const data = await this.request<{ access_token: string; refresh_token: string }>(
      '/auth/refresh',
      {
        method: 'POST',
        body: JSON.stringify({ refresh_token: this.refreshToken }),
      },
      false,
    );
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    await saveTokens(data.access_token, data.refresh_token);
  }

  private async request<T>(
    path: string,
    init: RequestInit = {},
    retryOnUnauthorized = true,
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetch(API_URL + path, {
        ...init,
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          ...(this.accessToken
            ? { Authorization: 'Bearer ' + this.accessToken }
            : {}),
          ...(init.headers || {}),
        },
      });
    } catch {
      throw new ApiError(
        'Não foi possível conectar à API em ' +
          API_URL +
          '. Verifique a rede e a porta 8001.',
      );
    }

    const data = await response.json().catch(() => null);
    if (response.status === 401 && retryOnUnauthorized && this.refreshToken) {
      try {
        await this.refresh();
        return this.request<T>(path, init, false);
      } catch {
        await this.logout();
      }
    }
    if (!response.ok) {
      const message =
        data && typeof data.detail === 'string'
          ? data.detail
          : 'Não foi possível concluir a operação.';
      throw new ApiError(message, response.status);
    }
    return data as T;
  }
}
