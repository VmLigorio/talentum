import { ApiError, ClientPermissions, Dashboard, DocumentItem, JsonMap, MarketAlert, NotificationItem, Portfolio, TalentumApi } from './api';

export type Workspace = {
  dashboard: Dashboard | null;
  portfolio: Portfolio | null;
  investmentTransactions: JsonMap[];
  monthlyPerformance: JsonMap | null;
  patrimony: JsonMap[];
  goals: JsonMap[];
  actionPlan: JsonMap[];
  documents: DocumentItem[];
  reports: JsonMap[];
  profile: JsonMap | null;
  financialProfile: JsonMap | null;
  notifications: NotificationItem[];
  notificationPreferences: JsonMap;
  suitability: JsonMap | null;
  marketAlerts: MarketAlert[];
  permissions: ClientPermissions | null;
};

export const emptyWorkspace: Workspace = {
  dashboard: null, portfolio: null, investmentTransactions: [], monthlyPerformance: null, patrimony: [], goals: [], actionPlan: [],
  documents: [], reports: [], profile: null, financialProfile: null,
  notifications: [], notificationPreferences: {}, suitability: null, marketAlerts: [], permissions: null,
};

export type WorkspaceErrors = Partial<Record<keyof Workspace, string>>;
export type WorkspaceFallbacks = Partial<Record<keyof Workspace, boolean>>;

// Cada módulo pode falhar isoladamente; uma sessão inválida interrompe o acesso inteiro.
export async function fetchWorkspace(api: TalentumApi, clientId: number) {
  const data: Workspace = { ...emptyWorkspace };
  const errors: WorkspaceErrors = {};
  const fallbackEligible: WorkspaceFallbacks = {};
  async function load<K extends keyof Workspace>(key: K, request: () => Promise<Workspace[K]>) {
    try {
      data[key] = await request();
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) throw cause;
      fallbackEligible[key] = cause instanceof ApiError && (cause.status === 0 || cause.status >= 500);
      errors[key] = cause instanceof ApiError && cause.status === 403
        ? 'Seu acesso a esta seção não está autorizado.'
        : 'Não foi possível carregar esta seção. Toque em Atualizar dados para tentar novamente.';
    }
  }
  await Promise.all([
    load('dashboard', () => api.dashboard(clientId)),
    load('portfolio', () => api.portfolio(clientId)),
    load('investmentTransactions', () => api.investmentTransactions(clientId)),
    load('monthlyPerformance', () => api.investmentMonthlyPerformance(clientId)),
    load('patrimony', () => api.patrimony(clientId)),
    load('goals', () => api.goals(clientId)),
    load('actionPlan', () => api.actionPlan(clientId)),
    load('documents', () => api.documents(clientId)),
    load('reports', () => api.reports(clientId)),
    load('profile', () => api.profile(clientId)),
    load('financialProfile', () => api.financialProfile(clientId)),
    load('notifications', () => api.notifications()),
    load('notificationPreferences', () => api.notificationPreferences()),
    load('suitability', () => api.suitability()),
    load('marketAlerts', () => api.marketAlerts()),
    load('permissions', () => api.permissions(clientId)),
  ]);
  return { data, errors, fallbackEligible };
}
