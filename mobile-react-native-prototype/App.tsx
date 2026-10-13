// Talentum — mobile-react-native-prototype/App.tsx
// Responsabilidade: reproduz a experiência principal do cliente que já existe no Flutter.
// O arquivo é um protótipo de comparação e mantém o cliente sem permissões de edição.

import React, { useEffect, useRef, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import * as Sharing from 'expo-sharing';
import Svg, { Circle, Line, Polyline } from 'react-native-svg';
import {
  ActivityIndicator,
  Alert,
  Image,
  Modal,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';

import {
  API_URL,
  ApiError,
  Dashboard,
  DocumentItem,
  JsonMap,
  MarketAlert,
  NotificationItem,
  Portfolio,
  TalentumApi,
  User,
} from './src/api';
import { emptyWorkspace, fetchWorkspace, Workspace, WorkspaceErrors } from './src/workspace';
import { formatInvestmentQuantity, formatMoneyInput, moneyCaretOffset, parseMoneyInput } from './src/money';

// Compartilha o cliente HTTP e a sessão entre telas e ações do aplicativo.
const api = new TalentumApi();
// Guarda o identificador do último cliente para tentar restaurar o cache offline.
const lastCachedClientIdKey = 'talentum_prototype_cached_client_id';
// Gera a chave local usada para separar o cache por cliente.
const workspaceCacheKey = (clientId: number) => `talentum_prototype_workspace_${clientId}`;
// Mantém as cores compartilhadas pelos componentes do protótipo.
const colors = {
  primary: '#17324D',
  accent: '#167C76',
  silver: '#B8C3CA',
  ink: '#1F2B35',
  muted: '#63717D',
  line: '#DCE4E8',
  background: '#F7F9FA',
  mist: '#E8EFF2',
  placeholder: '#8997A1',
  error: '#B84A5C',
};

// Identifica as áreas navegáveis exibidas ao cliente.
type Tab =
  | 'summary'
  | 'portfolio'
  | 'patrimony'
  | 'goals'
  | 'documents'
  | 'reports'
  | 'notifications'
  | 'profile';

// Formata valores financeiros para a moeda escolhida.
const money = (value?: number | string | null, currency = 'BRL') =>
  value == null || value === ''
    ? '—'
    : new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency,
      }).format(Number(value));

// Converte conteúdo opcional em texto e aplica um rótulo alternativo.
const textValue = (value: unknown, fallback = '—') =>
  value == null || value === '' ? fallback : String(value);

// Valida e formata uma data para apresentação ao usuário.
const dateValue = (value: unknown) => {
  if (value == null || value === '') return '—';
  // Datas ISO sem horário viram meia-noite UTC; use dateOnlyValue para datas civis.
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString('pt-BR');
};

// Formata datas sem horário sem deslocar o dia por fuso horário.
const dateOnlyValue = (value: unknown) => {
  const raw = String(value ?? '');
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw.split('-').reverse().join('/') : dateValue(value);
};

// Calcula o progresso em porcentagem e limita o resultado ao intervalo de 0 a 100.
const percentage = (current: unknown, target: unknown) => {
  const currentNumber = Number(current || 0);
  const targetNumber = Number(target || 0);
  if (!targetNumber) return 0;
  return Math.max(0, Math.min(100, (currentNumber / targetNumber) * 100));
};

// Apresenta um campo monetário com máscara e controle da posição do cursor.
function MoneyInput({
  value,
  onChangeText,
  placeholder,
}: {
  value: string;
  onChangeText: (value: string) => void;
  placeholder: string;
}) {
  const [selection, setSelection] = useState({ start: value.length, end: value.length });
  const selectionRef = useRef(selection);
  const renderedValueRef = useRef(value);
  // Reposiciona o cursor no fim quando o valor muda por atualização externa do formulário.
  useEffect(() => {
    if (renderedValueRef.current === value) return;
    renderedValueRef.current = value;
    const end = value.length;
    setSelection({ start: end, end });
    selectionRef.current = { start: end, end };
  }, [value]);
  // Formata o texto digitado e atualiza o campo preservando o cursor.
  function change(text: string) {
    const caret = selectionRef.current.start;
    // Conta os dígitos à esquerda do cursor antes de inserir separadores de milhar.
    const digitsBeforeCaret = (text.slice(0, caret).match(/\d/g) || []).length;
    const separatorIndex = text.includes(',') ? text.indexOf(',') : text.lastIndexOf('.');
    const pastDecimal = separatorIndex >= 0 && caret > separatorIndex;
    const formatted = formatMoneyInput(text);
    const offset = moneyCaretOffset(formatted, digitsBeforeCaret, pastDecimal);
    const nextSelection = { start: offset, end: offset };
    selectionRef.current = nextSelection;
    renderedValueRef.current = formatted;
    setSelection(nextSelection);
    onChangeText(formatted);
  }
  return (
    <View style={styles.moneyInputContainer}>
      <Text style={styles.moneyInputPrefix}>R$</Text>
      {/* Acompanha e restaura a seleção para que a máscara preserve a posição do cursor. */}
      <TextInput
        style={styles.moneyInput}
        keyboardType="decimal-pad"
        value={value}
        onChangeText={change}
        onSelectionChange={(event) => {
          const next = event.nativeEvent.selection;
          selectionRef.current = next;
          setSelection(next);
        }}
        selection={selection}
        placeholder={placeholder}
      />
    </View>
  );
}

// Traduz o tipo de documento para o rótulo da interface.
const documentKind = (kind: string) =>
  ({
    identification: 'Identificação',
    income_proof: 'Comprovante de renda',
    address_proof: 'Comprovante de endereço',
    other: 'Outro documento',
  })[kind] || 'Outro documento';

// Traduz o mercado do ativo para um nome legível.
const marketLabel = (market: string) =>
  market === 'br' ? 'Brasil — B3' : 'Exterior';

// Traduz a condição de preço usada pelo alerta.
const alertConditionLabel = (condition: string) =>
  condition === 'at_or_above' ? 'Atingir ou superar' : 'Atingir ou ficar abaixo';

// Traduz o estado atual do alerta para a interface.
const alertStatusLabel = (status: string) =>
  ({
    active: 'Ativo',
    paused: 'Pausado',
    triggered: 'Disparado',
    cancelled: 'Desativado',
  })[status] || 'Desconhecido';

// Relaciona cada chave de preferência da API ao rótulo exibido na tela de perfil.
const preferenceLabels: Array<{ key: string; label: string }> = [
  { key: 'action_overdue', label: 'Ações vencidas' },
  { key: 'action_due_soon', label: 'Ações próximas do vencimento' },
  { key: 'goal_overdue', label: 'Metas vencidas' },
  { key: 'goal_due_soon', label: 'Metas próximas do vencimento' },
  { key: 'document_uploaded', label: 'Novos documentos' },
  { key: 'document_review_due', label: 'Revisão de documentos' },
  { key: 'market_price_alert', label: 'Alertas de preço' },
];

// Coordena a sessão, os módulos carregados e a navegação principal do cliente.
export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [workspace, setWorkspace] = useState<Workspace>(emptyWorkspace);
  const [workspaceErrors, setWorkspaceErrors] = useState<WorkspaceErrors>({});
  const loadVersion = useRef(0);
  const cacheOwnerId = useRef<number | null>(null);
  const [canRetrySession, setCanRetrySession] = useState(false);
  const [tab, setTab] = useState<Tab>('summary');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [biometricOn, setBiometricOn] = useState(false);
  const [biometricLoginAvailable, setBiometricLoginAvailable] = useState(false);
  const [questionnaire, setQuestionnaire] = useState<JsonMap | null>(null);
  const [questionnaireVisible, setQuestionnaireVisible] = useState(false);
  const [alertsVisible, setAlertsVisible] = useState(false);
  const [editingAlert, setEditingAlert] = useState<MarketAlert | null>(null);
  const [recordEditor, setRecordEditor] = useState<{ kind: 'patrimony' | 'goal'; item: JsonMap | null } | null>(null);
  const [hideValues, setHideValues] = useState(false);
  const [offlineCacheUsed, setOfflineCacheUsed] = useState(false);

  // Registra a reação à expiração, inicia a restauração da sessão e invalida cargas ao desmontar.
  useEffect(() => {
    const unsubscribe = api.onSessionExpired(() => {
      void clearWorkspace();
      setError('Sua sessão expirou. Entre novamente para continuar.');
    });
    void bootstrap();
    return () => { unsubscribe(); loadVersion.current += 1; };
  }, []);

  // Atualiza rendimento e CDI a cada hora sem recarregar as demais seções do workspace.
  useEffect(() => {
    if (!user) return;
    const timer = setInterval(() => {
      void api.investmentMonthlyPerformance(user.id).then((data) => {
        setWorkspace((current) => ({ ...current, monthlyPerformance: data }));
        setWorkspaceErrors((current) => ({ ...current, monthlyPerformance: undefined }));
      }).catch((cause) => {
        setWorkspaceErrors((current) => ({ ...current, monthlyPerformance: cause instanceof Error ? cause.message : 'Não foi possível atualizar o CDI.' }));
      });
    }, 60 * 60 * 1000);
    return () => clearInterval(timer);
  }, [user?.id]);

  // Apaga dados locais da sessão e invalida a tentativa de carregamento atual.
  async function clearWorkspace() {
    const cachedClientId = cacheOwnerId.current;
    cacheOwnerId.current = null;
    let cacheCleanup: Promise<void>;
    if (cachedClientId != null) {
      cacheCleanup = Promise.all([
        SecureStore.deleteItemAsync(workspaceCacheKey(cachedClientId)),
        SecureStore.deleteItemAsync(lastCachedClientIdKey),
      ]).then(() => {});
    } else {
      cacheCleanup = SecureStore.getItemAsync(lastCachedClientIdKey).then(async (value) => {
        const previousId = Number(value);
        if (Number.isInteger(previousId) && previousId > 0) await SecureStore.deleteItemAsync(workspaceCacheKey(previousId));
        await SecureStore.deleteItemAsync(lastCachedClientIdKey);
      });
    }
    loadVersion.current += 1;
    setUser(null);
    setWorkspace(emptyWorkspace);
    setWorkspaceErrors({});
    setTab('summary');
    setBiometricLoginAvailable(false);
    setCanRetrySession(false);
    setQuestionnaireVisible(false);
    setQuestionnaire(null);
    setAlertsVisible(false);
    setEditingAlert(null);
    setRecordEditor(null);
    setOfflineCacheUsed(false);
    // A falha de limpeza não bloqueia outro login; a restauração offline ainda usa o último ID salvo.
    await cacheCleanup.catch(() => {});
  }

  // Restaura a sessão e determina se deve abrir login ou carregar o workspace.
  async function bootstrap() {
    setLoading(true);
    try {
      const hasSession = await api.restoreSession();
      setCanRetrySession(hasSession);
      const enabled = await api.biometricEnabled();
      const available = enabled && (await api.biometricAvailable());
      setBiometricLoginAvailable(Boolean(hasSession && available));
      setBiometricOn(enabled);
      if (!hasSession) return;
      if (available && !(await api.authenticateBiometric())) {
        setError('Confirme sua identidade com a biometria para continuar.');
        return;
      }
      try {
        const currentUser = await api.me();
        await loadWorkspace(currentUser);
      } catch (cause) {
        if (cause instanceof ApiError && (cause.status === 0 || cause.status >= 500) && await restoreOfflineWorkspace()) {
          setError('Sem conexão com a API. Exibindo os últimos dados salvos neste aparelho.');
          return;
        }
        throw cause;
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível restaurar a sessão.');
    } finally {
      setLoading(false);
    }
  }

  // Carrega dados do cliente e atualiza cache e erros por seção.
  async function loadWorkspace(currentUser: User) {
    if (currentUser.role !== 'client') {
      await api.logout();
      await clearWorkspace();
      throw new ApiError(
        currentUser.role === 'admin'
          ? 'Esta conta é de administrador. Entre com uma conta de cliente no aplicativo mobile.'
          : 'Esta conta é de advisor. Use o painel Advisor para essa conta.',
        403,
      );
    }
    const version = ++loadVersion.current;
    const result = await fetchWorkspace(api, currentUser.id);
    if (version !== loadVersion.current) return;
    let nextData = result.data;
    const nextErrors = { ...result.errors };
    let usedCache = false;
    let previousWorkspace: Workspace | null = null;
    try {
      const stored = await SecureStore.getItemAsync(workspaceCacheKey(currentUser.id));
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed?.workspace && parsed?.user?.id === currentUser.id) previousWorkspace = { ...emptyWorkspace, ...parsed.workspace } as Workspace;
      }
    } catch { /* Cache inválido ou indisponível não impede o acesso online. */ }
    if (previousWorkspace) { // Só substitui seções vazias por falha transitória; respostas válidas da API prevalecem.
      for (const key of Object.keys(result.fallbackEligible) as Array<keyof Workspace>) {
        const failedWithoutData = result.data[key] == null || (Array.isArray(result.data[key]) && (result.data[key] as unknown[]).length === 0);
        if (result.fallbackEligible[key] && failedWithoutData) {
          const previousValue = previousWorkspace[key];
          if (previousValue != null && (!Array.isArray(previousValue) || previousValue.length > 0)) {
            nextData = { ...nextData, [key]: previousValue };
            delete nextErrors[key];
            usedCache = true;
          }
        }
      }
    }
    if (version !== loadVersion.current) return;
    if (!Object.keys(nextErrors).length) {
      // A geração não é revalidada depois destas gravações assíncronas no SecureStore.
      try {
        await SecureStore.setItemAsync(workspaceCacheKey(currentUser.id), JSON.stringify({ user: currentUser, workspace: nextData }));
        await SecureStore.setItemAsync(lastCachedClientIdKey, String(currentUser.id));
        cacheOwnerId.current = currentUser.id;
      } catch { /* Cache completo pode ser rejeitado por tamanho; o app segue online, mas a cópia offline pode ficar antiga (achado 134). */ }
    }
    setUser(currentUser);
    const hidden = await SecureStore.getItemAsync(`talentum_hide_values_${currentUser.id}`);
    if (version !== loadVersion.current) return;
    setHideValues(hidden === 'true');
    setWorkspace(nextData);
    setWorkspaceErrors(nextErrors);
    setOfflineCacheUsed(usedCache);
    setCanRetrySession(false);
    setError('');
  }

  // Restaura uma cópia local quando a API está indisponível.
  async function restoreOfflineWorkspace() {
    try {
      // Sem resposta de /me, o ID local não é comparado à identidade dos tokens armazenados.
      const clientId = Number(await SecureStore.getItemAsync(lastCachedClientIdKey));
      if (!Number.isInteger(clientId) || clientId <= 0) return false;
      const stored = await SecureStore.getItemAsync(workspaceCacheKey(clientId));
      if (!stored) return false;
      const parsed = JSON.parse(stored);
      if (parsed?.user?.id !== clientId || parsed?.user?.role !== 'client' || !parsed?.workspace) return false;
      setUser(parsed.user as User);
      setWorkspace({ ...emptyWorkspace, ...parsed.workspace } as Workspace);
      setWorkspaceErrors({});
      setHideValues((await SecureStore.getItemAsync(`talentum_hide_values_${clientId}`)) === 'true');
      setOfflineCacheUsed(true);
      cacheOwnerId.current = clientId;
      return true;
    } catch { return false; } // Cache ausente, inválido ou inacessível desativa o fallback para manter o erro original da API.
  }

  // Autentica o usuário e carrega o espaço de trabalho.
  async function handleLogin(email: string, password: string) {
    await clearWorkspace();
    setBusy(true);
    setError('');
    try {
      await api.login(email, password);
      const currentUser = await api.me();
      await loadWorkspace(currentUser);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível entrar.');
    } finally {
      setBusy(false);
    }
  }

  // Usa autenticação biométrica para reabrir uma sessão salva.
  async function handleBiometricLogin() {
    setBusy(true);
    setError('');
    try {
      if (!(await api.authenticateBiometric())) {
        setError('A autenticação biométrica foi cancelada.');
        return;
      }
      const currentUser = await api.me();
      await loadWorkspace(currentUser);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível entrar com biometria.');
    } finally {
      setBusy(false);
    }
  }

  // Encerra a sessão local, limpa o workspace e retorna o aplicativo para o login.
  async function handleLogout() {
    try {
      await api.logout(); // Revoga a sessão remotamente quando possível e limpa as credenciais locais.
    } finally {
      await clearWorkspace();
    }
  }

  // Atualiza os dados remotos da tela do cliente.
  async function handleRefresh() {
    if (!user) return;
    setBusy(true);
    try {
      await loadWorkspace(user);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível atualizar.');
    } finally {
      setBusy(false);
    }
  }

  // Baixa e abre o documento selecionado no visualizador.
  async function openDocument(document: DocumentItem) {
    if (!user) return;
    setBusy(true);
    try {
      const localUri = await api.downloadDocument(user.id, document.id, document.original_name);
      if (!(await Sharing.isAvailableAsync())) {
        Alert.alert('Documento baixado', 'O arquivo foi armazenado temporariamente, mas não há um aplicativo disponível para abri-lo.');
        return;
      }
      await Sharing.shareAsync(localUri, { mimeType: document.content_type || 'application/octet-stream', dialogTitle: document.original_name, UTI: 'public.data' });
    } catch (cause) {
      Alert.alert('Não foi possível abrir o documento', cause instanceof Error ? cause.message : 'Tente novamente.');
    } finally { setBusy(false); }
  }

  // Solicita à API e abre o relatório detalhado de investimentos.
  async function emitInvestmentReport() {
    if (!user) return;
    setBusy(true);
    try {
      const localUri = await api.downloadInvestmentReport(user.id);
      if (!(await Sharing.isAvailableAsync())) {
        Alert.alert('Relatório emitido', 'O PDF foi salvo temporariamente, mas não há um aplicativo disponível para compartilhá-lo.');
        return;
      }
      await Sharing.shareAsync(localUri, { mimeType: 'application/pdf', dialogTitle: 'Relatório detalhado da carteira', UTI: 'com.adobe.pdf' });
    } catch (cause) {
      Alert.alert('Não foi possível emitir o relatório', cause instanceof Error ? cause.message : 'Tente novamente.');
    } finally { setBusy(false); }
  }

  // Salva a preferência de ocultar valores financeiros na interface.
  async function toggleHideValues(hidden: boolean) {
    setHideValues(hidden);
    if (user) await SecureStore.setItemAsync(`talentum_hide_values_${user.id}`, String(hidden));
  }

  // Busca o questionário e abre o fluxo de avaliação de suitability.
  async function openQuestionnaire() {
    setBusy(true);
    setError('');
    try {
      const definition = await api.suitabilityQuestionnaire();
      setQuestionnaire(definition);
      setQuestionnaireVisible(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível abrir o questionário.');
    } finally {
      setBusy(false);
    }
  }

  // Registra o aceite do cliente para a carteira sugerida.
  async function acceptSuitability(assessment: JsonMap) {
    try {
      const updated = await api.respondToSuitability(Number(assessment.id), 'accepted');
      setWorkspace((current) => ({ ...current, suitability: updated }));
      // Invalida o cache após o aceite; uma falha ainda cai no alerta de erro (achado 119).
      if (user) await SecureStore.deleteItemAsync(workspaceCacheKey(user.id));
      Alert.alert('Sugestão aceita', 'A sugestão foi registrada na Carteira sugerida.');
    } catch (cause) {
      Alert.alert('Não foi possível aceitar', cause instanceof Error ? cause.message : 'Tente novamente.');
    }
  }

  // Atualiza a lista de alertas e fecha o editor após a gravação.
  async function saveAlert() {
    try {
      const alerts = await api.marketAlerts();
      setWorkspace((current) => ({ ...current, marketAlerts: alerts })); // Atualiza só o estado em memória; o cache offline permanece antigo (achado 204).
      setAlertsVisible(false);
      setEditingAlert(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível atualizar os alertas.');
    }
  }

  // Cria ou altera um item patrimonial ou uma meta.
  async function saveRecord(kind: 'patrimony' | 'goal', item: JsonMap | null, values: JsonMap) {
    if (!user) return;
    try {
      if (kind === 'patrimony') {
        if (item?.id) await api.updatePatrimony(user.id, Number(item.id), values);
        else await api.createPatrimony(user.id, values);
      } else if (item?.id) await api.updateGoal(user.id, Number(item.id), values);
      else await api.createGoal(user.id, values);
      setRecordEditor(null);
      await loadWorkspace(user);
    } catch (cause) { Alert.alert('Não foi possível salvar', cause instanceof Error ? cause.message : 'Tente novamente.'); }
  }

  // Remove o item patrimonial ou a meta após confirmação.
  async function deleteRecord(kind: 'patrimony' | 'goal', item: JsonMap) {
    if (!user || !item.id) return;
    try {
      if (kind === 'patrimony') await api.deletePatrimony(user.id, Number(item.id));
      else await api.deleteGoal(user.id, Number(item.id));
      setRecordEditor(null);
      await loadWorkspace(user);
    } catch (cause) { Alert.alert('Não foi possível excluir', cause instanceof Error ? cause.message : 'Tente novamente.'); }
  }

  // Marca a notificação selecionada como lida.
  async function markNotificationRead(notification: NotificationItem) {
    try {
      const updated = await api.markNotificationRead(notification.id);
      setWorkspace((current) => ({
        ...current,
        notifications: current.notifications.map((item) =>
          item.id === updated.id ? updated : item,
        ),
      })); // A leitura atualizada não é persistida no cache offline (achado 204).
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível marcar a notificação.');
    }
  }

  // Marca como lidas as notificações apresentadas ao usuário.
  async function markAllNotificationsRead() {
    try {
      await api.markAllNotificationsRead();
      setWorkspace((current) => ({
        ...current,
        notifications: current.notifications.map((item) => ({
          ...item,
          read_at: item.read_at || new Date().toISOString(),
        })),
      })); // A leitura atualizada não é persistida no cache offline (achado 204).
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível marcar as notificações.');
    }
  }

  // Salva a preferência de notificação que foi alterada.
  async function updatePreference(key: string, value: boolean) {
    try {
      // Switches continuam ativos durante a requisição; respostas atrasadas podem sobrescrever o estado mais recente (achado 159).
      const updated = await api.updateNotificationPreferences({ [key]: value });
      setWorkspace((current) => ({
        ...current,
        notificationPreferences: { ...current.notificationPreferences, ...updated },
      })); // As preferências atualizadas não são persistidas no cache offline (achado 204).
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível atualizar as preferências.');
    }
  }

  // Ativa ou desativa o login biométrico e salva a preferência.
  async function toggleBiometric(enabled: boolean) {
    try {
      if (enabled) {
        if (!(await api.biometricAvailable())) {
          setError('Este aparelho não possui uma biometria configurada.');
          return;
        }
        if (!(await api.authenticateBiometric())) return;
      }
      await api.setBiometricEnabled(enabled);
      setBiometricOn(enabled);
      setBiometricLoginAvailable(enabled);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível configurar a biometria.');
    }
  }

  if (loading) {
    return (
      <Centered>
        <ActivityIndicator color={colors.primary} size="large" />
      </Centered>
    );
  }

  if (!user) {
    return (
      <LoginScreen
        busy={busy}
        error={error}
        biometricAvailable={biometricLoginAvailable}
        onBiometricLogin={handleBiometricLogin}
        onLogin={handleLogin}
        onRetrySession={canRetrySession ? bootstrap : undefined}
      />
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.brandLockup} accessibilityRole="image" accessibilityLabel="Talentum">
          <Image source={require('./assets/talentum-moeda-prata.png')} style={styles.brandMark} resizeMode="contain" />
          <Text style={styles.brandName}>talentum</Text>
        </View>
        <Text style={styles.eyebrow}>PROTÓTIPO RN</Text>
        <View style={styles.header}>
          <View style={styles.headerCopy}>
            <Text style={styles.title}>Olá, {user.name.split(' ')[0]}</Text>
            <Text style={styles.muted}>Experiência React Native em comparação com o Flutter</Text>
          </View>
          <Pressable onPress={() => void handleLogout()} style={styles.outlineButton}>
            <Text style={styles.outlineButtonText}>Sair</Text>
          </Pressable>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}
        {offlineCacheUsed ? <Text style={styles.muted}>Alguns dados podem estar desatualizados. Reconecte-se e toque em Atualizar dados.</Text> : null}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.tabBar}>
          <TabButton label="Resumo" active={tab === 'summary'} onPress={() => setTab('summary')} />
          <TabButton label="Carteira" active={tab === 'portfolio'} onPress={() => setTab('portfolio')} />
          <TabButton label="Patrimônio" active={tab === 'patrimony'} onPress={() => setTab('patrimony')} />
          <TabButton label="Metas" active={tab === 'goals'} onPress={() => setTab('goals')} />
          <TabButton label="Documentos" active={tab === 'documents'} onPress={() => setTab('documents')} />
          <TabButton label="Relatórios" active={tab === 'reports'} onPress={() => setTab('reports')} />
          <TabButton label="Avisos" active={tab === 'notifications'} onPress={() => setTab('notifications')} />
          <TabButton label="Perfil" active={tab === 'profile'} onPress={() => setTab('profile')} />
        </ScrollView>

        {/* Os callbacks limpam a edição anterior ao criar e guardam o alerta escolhido ao editar. */}
        {tab === 'summary' ? (
          <SummaryView
            errors={workspaceErrors}
            dashboard={workspace.dashboard}
            portfolio={workspace.portfolio}
            notifications={workspace.notifications}
            suitability={workspace.suitability}
            goals={workspace.goals}
            marketAlerts={workspace.marketAlerts}
            hideValues={hideValues}
            onToggleHideValues={(value) => void toggleHideValues(value)}
            onQuestionnaire={() => void openQuestionnaire()}
            onAcceptSuitability={(assessment) => void acceptSuitability(assessment)}
            onMarkRead={(item) => void markNotificationRead(item)}
            onMarkAllRead={() => void markAllNotificationsRead()}
            onOpenNotifications={() => setTab('notifications')}
            onOpenTab={setTab}
            onNewAlert={() => {
              setEditingAlert(null);
              setAlertsVisible(true);
            }}
            onEditAlert={(item) => {
              setEditingAlert(item);
              setAlertsVisible(true);
            }}
          />
        ) : null}
        {tab === 'portfolio' ? <ModuleState error={workspaceErrors.portfolio}><PortfolioView portfolio={workspace.portfolio} transactions={workspace.investmentTransactions} monthlyPerformance={workspace.monthlyPerformance} monthlyPerformanceError={workspaceErrors.monthlyPerformance} hideValues={hideValues} onEmitReport={() => void emitInvestmentReport()} /></ModuleState> : null}
        {tab === 'patrimony' ? <ModuleState error={workspaceErrors.patrimony}><PatrimonyView items={workspace.patrimony} hideValues={hideValues} canEdit={Boolean(workspace.permissions?.can_edit_patrimony)} onEdit={(item) => setRecordEditor({ kind: 'patrimony', item })} onCreate={() => setRecordEditor({ kind: 'patrimony', item: null })} /></ModuleState> : null}
        {tab === 'goals' ? <GoalsView goals={workspace.goals} actionPlan={workspace.actionPlan} errors={workspaceErrors} hideValues={hideValues} canEdit={Boolean(workspace.permissions?.can_edit_goals)} onEdit={(item) => setRecordEditor({ kind: 'goal', item })} onCreate={() => setRecordEditor({ kind: 'goal', item: null })} /> : null}
        {tab === 'documents' ? <ModuleState error={workspaceErrors.documents}><DocumentsView documents={workspace.documents} onOpen={(document) => void openDocument(document)} /></ModuleState> : null}
        {tab === 'reports' ? <ModuleState error={workspaceErrors.reports}><ReportsView reports={workspace.reports} /></ModuleState> : null}
        {tab === 'notifications' ? <NotificationsView notifications={workspace.notifications} onMarkRead={(item) => void markNotificationRead(item)} onMarkAllRead={() => void markAllNotificationsRead()} /> : null}
        {tab === 'profile' ? (
          <ProfileView
            errors={workspaceErrors}
            profile={workspace.profile}
            financialProfile={workspace.financialProfile}
            hideValues={hideValues}
            canEditFinancial={Boolean(workspace.permissions?.can_edit_financial_profile)}
            clientId={user.id}
            onSaved={() => { void loadWorkspace(user); /* Rejeições da recarga não são observadas por este callback (achado 42). */ }}
            biometricOn={biometricOn}
            preferences={workspace.notificationPreferences}
            onToggleBiometric={(value) => void toggleBiometric(value)}
            onTogglePreference={(key, value) => void updatePreference(key, value)}
          />
        ) : null}

        <Pressable onPress={() => void handleRefresh()} style={styles.secondaryButton} disabled={busy}>
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.secondaryButtonText}>Atualizar dados</Text>}
        </Pressable>
        <Text style={styles.apiLabel}>API: {API_URL}</Text>
      </ScrollView>

      <SuitabilityModal
        visible={questionnaireVisible}
        questionnaire={questionnaire}
        current={workspace.suitability}
        onClose={() => setQuestionnaireVisible(false)}
        onSaved={(assessment) => {
          // Atualiza a avaliação só em memória; esta submissão não sincroniza o cache offline (achado 204).
          setWorkspace((current) => ({ ...current, suitability: assessment }));
          setQuestionnaireVisible(false);
        }}
      />
      <RecordEditorModal
        visible={Boolean(recordEditor)}
        kind={recordEditor?.kind || 'goal'}
        item={recordEditor?.item || null}
        onClose={() => setRecordEditor(null)}
        onSave={(values) => recordEditor && void saveRecord(recordEditor.kind, recordEditor.item, values)}
        onDelete={() => recordEditor?.item && void deleteRecord(recordEditor.kind, recordEditor.item)}
      />
      {/* Ao fechar, o modal também limpa o alerta selecionado para edição. */}
      <AlertEditorModal
        visible={alertsVisible}
        initial={editingAlert}
        onClose={() => {
          setAlertsVisible(false);
          setEditingAlert(null);
        }}
        onSaved={() => void saveAlert()}
      />
    </SafeAreaView>
  );
}

// Apresenta o formulário de entrada e opções de autenticação.
function LoginScreen({
  busy,
  error,
  biometricAvailable,
  onBiometricLogin,
  onLogin,
  onRetrySession,
}: {
  busy: boolean;
  error: string;
  biometricAvailable: boolean;
  onBiometricLogin: () => Promise<void>;
  onLogin: (email: string, password: string) => Promise<void>;
  onRetrySession?: () => Promise<void>;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // O formulário não rola nem ajusta o layout ao teclado; telas baixas podem ocultar ações.
  return (
    <Centered>
      <View style={styles.loginCard}>
        {onRetrySession ? (
          <Pressable onPress={() => void onRetrySession()} disabled={busy} style={styles.outlineButton}>
            <Text style={styles.outlineButtonText}>Tentar restaurar sessão novamente</Text>
          </Pressable>
        ) : null}
        <View style={styles.brandLockup} accessibilityRole="image" accessibilityLabel="Talentum">
          <Image source={require('./assets/talentum-moeda-prata.png')} style={styles.brandMark} resizeMode="contain" />
          <Text style={styles.brandName}>talentum</Text>
        </View>
        <Text style={styles.eyebrow}>PROTÓTIPO RN</Text>
        <Text style={styles.title}>Acesso do cliente</Text>
        <Text style={[styles.muted, styles.loginDescription]}>
          Sessão segura, carteira, documentos, metas, suitability e alertas em React Native.
        </Text>
        <TextInput
          autoCapitalize="none"
          keyboardType="email-address"
          placeholder="E-mail"
          placeholderTextColor={colors.placeholder}
          style={styles.input}
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          placeholder="Senha"
          placeholderTextColor={colors.placeholder}
          secureTextEntry
          style={styles.input}
          value={password}
          onChangeText={setPassword}
        />
        {/* A mensagem é visual, mas ainda não tem papel de alerta para leitores de tela. */}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Pressable
          disabled={busy}
          onPress={() => void onLogin(email, password)}
          style={styles.primaryButton}
        >
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>Entrar</Text>}
        </Pressable>
        {biometricAvailable ? (
          <Pressable disabled={busy} onPress={() => void onBiometricLogin()} style={styles.outlineWideButton}>
            <Text style={styles.outlineButtonText}>Entrar com biometria</Text>
          </Pressable>
        ) : null}
        <Text style={styles.apiLabel}>API: {API_URL}</Text>
      </View>
    </Centered>
  );
}

// Representa estados carregando, erro ou conteúdo das seções do app.
function ModuleState({ error, children }: { error?: string; children: React.ReactNode }) {
  return error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : <>{children}</>;
}

// Mostra os principais indicadores financeiros do cliente.
function SummaryView({
  errors,
  dashboard,
  portfolio,
  notifications,
  suitability,
  goals,
  marketAlerts,
  hideValues,
  onToggleHideValues,
  onQuestionnaire,
  onAcceptSuitability,
  onMarkRead,
  onMarkAllRead,
  onOpenNotifications,
  onOpenTab,
  onNewAlert,
  onEditAlert,
}: {
  errors: WorkspaceErrors;
  dashboard: Dashboard | null;
  portfolio: Portfolio | null;
  notifications: NotificationItem[];
  suitability: JsonMap | null;
  goals: JsonMap[];
  marketAlerts: MarketAlert[];
  hideValues: boolean;
  onToggleHideValues: (hidden: boolean) => void;
  onQuestionnaire: () => void;
  onAcceptSuitability: (assessment: JsonMap) => void;
  onMarkRead: (item: NotificationItem) => void;
  onMarkAllRead: () => void;
  onOpenNotifications: () => void;
  onOpenTab: (tab: Tab) => void;
  onNewAlert: () => void;
  onEditAlert: (item: MarketAlert) => void;
}) {
  // O resumo conta os avisos recebidos pela lista padrão da API (até 50).
  const unread = notifications.filter((item) => !item.read_at);
  return (
    <View style={styles.section}>
      <View style={styles.rowBetween}><Text style={styles.sectionTitle}>Visão geral</Text><Pressable onPress={() => onToggleHideValues(!hideValues)}><Text style={styles.link}>{hideValues ? 'Mostrar valores' : 'Ocultar valores'}</Text></Pressable></View>
      <View style={styles.cardGrid}>
        <ModuleState error={errors.dashboard && 'Resumo financeiro: ' + errors.dashboard}>
          <Metric label="Patrimônio" value={hideValues ? '••••••' : money(dashboard?.patrimony_total)} />
          <Metric label="Renda mensal" value={hideValues ? '••••••' : money(dashboard?.monthly_income)} />
          <Metric label="Despesas" value={hideValues ? '••••••' : money(dashboard?.monthly_expenses)} />
        </ModuleState>
        <ModuleState error={errors.portfolio && 'Carteira: ' + errors.portfolio}>
          <Metric label="Posições" value={String(portfolio?.position_count ?? 0)} />
        </ModuleState>
      </View>
      <ModuleState error={errors.goals && 'Metas: ' + errors.goals}>
        <View style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.cardTitle}>Metas financeiras</Text>
            <Pressable onPress={() => onOpenTab('goals')}><Text style={styles.link}>Ver todas</Text></Pressable>
          </View>
          {goals.slice(0, 3).map((goal) => (
            <View key={String(goal.id)} style={styles.listRow}>
              <View style={styles.flexOne}>
                <Text style={styles.bodyText}>{textValue(goal.title)}</Text>
                <Text style={styles.muted}>{hideValues ? '•••••• de ••••••' : `${money(goal.current_value)} de ${money(goal.target_value)}`}</Text>
              </View>
              {/* O progresso percentual também deriva de valores ocultados e continua visível. */}
              <Text style={styles.badge}>{Math.round(percentage(goal.current_value, goal.target_value))}%</Text>
            </View>
          ))}
          {!goals.length ? <Text style={styles.muted}>Nenhuma meta cadastrada.</Text> : null}
        </View>
      </ModuleState>
      <ModuleState error={errors.notifications && 'Notificações: ' + errors.notifications}>
        <NotificationCard
          notifications={notifications}
          unread={unread}
          onMarkRead={onMarkRead}
          onMarkAllRead={onMarkAllRead}
          onOpenAll={onOpenNotifications}
        />
      </ModuleState>
      <ModuleState error={errors.suitability && 'Suitability: ' + errors.suitability}>
        <SuitabilityCard assessment={suitability} onQuestionnaire={onQuestionnaire} onAccept={onAcceptSuitability} />
      </ModuleState>
      <ModuleState error={errors.marketAlerts && 'Alertas de preço: ' + errors.marketAlerts}>
        {/* AlertCard não recebe hideValues e mantém os preços-alvo visíveis. */}
        <AlertCard alerts={marketAlerts} onNew={onNewAlert} onEdit={onEditAlert} />
      </ModuleState>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Acesso somente leitura</Text>
        <Text style={styles.muted}>
          Seus dados cadastrais e documentos são atualizados pelo Advisor. O aplicativo exibe a informação aprovada para você.
        </Text>
      </View>
      <Pressable onPress={() => onOpenTab('portfolio')} style={styles.secondaryButton}>
        <Text style={styles.secondaryButtonText}>Abrir carteira completa</Text>
      </Pressable>
    </View>
  );
}

// A paleta contém oito cores e o índice cíclico abaixo as reutiliza em carteiras maiores.
const portfolioColors = [colors.primary, colors.accent, '#D18A34', '#C95F6D', '#4A82B8', '#728FA4', '#55A66E', '#D07842'];

// Desenha a composição das posições em um gráfico de rosca.
function PortfolioDonut({ positions, currency }: { positions: Portfolio['positions']; currency: string }) { // Mostra somente posições positivas da moeda recebida.
  const items = positions.filter((position) => (position.currency || 'BRL') === currency && Number(position.allocation_percent || 0) > 0);
  if (!items.length) return null;
  const radius = 39;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return <View style={styles.donutWrap}>
    <View style={styles.donutGraphic}>
      <Svg width={132} height={132} viewBox="0 0 104 104">
        <Circle cx="52" cy="52" r={radius} fill="none" stroke="#E8EFF2" strokeWidth="18" />
        {items.map((item, index) => {
          const ratio = Math.max(0, Math.min(100, Number(item.allocation_percent || 0))) / 100;
          const segment = circumference * ratio;
          const element = <Circle key={item.id} cx="52" cy="52" r={radius} fill="none" stroke={portfolioColors[index % portfolioColors.length]} strokeWidth="18" strokeDasharray={`${segment} ${circumference - segment}`} strokeDashoffset={-offset} transform="rotate(-90 52 52)" />;
          offset += segment;
          return element;
        })}
      </Svg>
      <View pointerEvents="none" style={styles.donutCenter}><Text style={styles.donutCenterLabel}>{currency}</Text><Text style={styles.donutCenterValue}>{items.length} ativos</Text></View>
    </View>
    <View style={styles.donutLegend}>{items.map((item, index) => <View key={item.id} style={styles.donutLegendRow}><View style={[styles.donutDot, { backgroundColor: portfolioColors[index % portfolioColors.length] }]} /><Text numberOfLines={1} style={styles.donutLegendName}>{item.symbol}</Text><Text style={styles.donutLegendPct}>{Number(item.allocation_percent || 0).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%</Text></View>)}</View>
  </View>;
}

// Desenha a evolução mensal da carteira e a série CDI quando disponível.
function MonthlyReturnGraph({ points, cdiAvailable }: { points: JsonMap[]; cdiAvailable: boolean }) {
  const width = 320; const height = 156; const pad = 12;
  if (!points.length) return <Text style={styles.muted}>O histórico mensal ainda está sendo formado.</Text>;
  const values = points.flatMap((point) => [Number(point.return_percent || 0), ...(cdiAvailable && point.cdi_return_percent != null ? [Number(point.cdi_return_percent)] : [])]);
  let min = Math.min(0, ...values); let max = Math.max(0, ...values);
  if (max - min < 0.15) { max += 0.1; min -= 0.1; }
  // Converte o índice mensal na coordenada horizontal do gráfico.
  const x = (index: number) => pad + (points.length <= 1 ? 0 : index * (width - pad * 2) / (points.length - 1));
  // Converte o rendimento em uma coordenada vertical do gráfico.
  const y = (value: number) => pad + (max - value) * (height - pad * 2) / (max - min);
  const portfolioLine = points.map((point, index) => `${x(index)},${y(Number(point.return_percent || 0))}`).join(' ');
  const cdiPoints = points.map((point, index) => point.cdi_return_percent == null ? null : `${x(index)},${y(Number(point.cdi_return_percent))}`).filter(Boolean).join(' ');
  // O traçado mostra a série, mas os valores mensais intermediários não têm alternativa textual (achado 201).
  return <View style={styles.monthlyGraph}>
    <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
      <Line x1={pad} y1={y(0)} x2={width - pad} y2={y(0)} stroke={colors.silver} strokeDasharray="4 4" />
      {points.length > 1 ? <Polyline points={portfolioLine} fill="none" stroke={colors.primary} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" /> : null}
      {cdiAvailable && points.filter((point) => point.cdi_return_percent != null).length > 1 ? <Polyline points={cdiPoints} fill="none" stroke={colors.accent} strokeWidth="2.5" strokeDasharray="5 4" strokeLinejoin="round" strokeLinecap="round" /> : null}
    </Svg>
    <View style={styles.monthlyGraphAxis}><Text style={styles.muted}>{String(points[0].date).slice(5)}</Text><Text style={styles.muted}>{String(points[points.length - 1].date).slice(5)}</Text></View>
    <View style={styles.graphLegend}><View style={styles.graphLegendItem}><View style={[styles.graphLineSample, { backgroundColor: colors.primary }]} /><Text style={styles.muted}>Carteira</Text></View>{cdiAvailable ? <View style={styles.graphLegendItem}><View style={[styles.graphLineSample, { backgroundColor: colors.accent }]} /><Text style={styles.muted}>CDI</Text></View> : null}</View>
  </View>;
}

// Exibe indicadores e evolução mensal da carteira por moeda.
function MonthlyPerformance({ data, error, hideValues }: { data: JsonMap | null; error?: string; hideValues: boolean }) { // Separa métricas por moeda e apresenta a série mensal disponível.
  const currencies = Array.isArray(data?.currencies) ? data.currencies as JsonMap[] : [];
  const month = String(data?.month || '').split('-').reverse().join('/');
  return <View style={styles.card}>
    <Text style={styles.cardTitle}>Rendimento no mês</Text>
    {error ? <Text style={styles.muted}>{error}</Text> : null}
    {!error && !currencies.length ? <Text style={styles.muted}>O histórico do mês será exibido após as primeiras atualizações da carteira.</Text> : null}
    {currencies.map((item) => {
      const currency = String(item.currency || 'BRL');
      const points = Array.isArray(item.points) ? item.points as JsonMap[] : [];
      const cdi = currency === 'BRL' ? item.cdi_percent : null;
      const hasData = item.data_available === true;
      return <View key={currency} style={styles.monthlyCurrency}>
        <View style={styles.rowBetween}><Text style={styles.subsectionTitle}>{currency} · {month}</Text>{item.source_status === 'partial' ? <Text style={styles.badge}>Dados parciais</Text> : null}</View>
        {!item.full_month_to_date && item.coverage_start ? <Text style={styles.muted}>Histórico disponível desde {dateOnlyValue(item.coverage_start)}.</Text> : null}
        <View style={styles.monthlyMetrics}>
          <Metric label="Valor investido" value={hideValues ? '••••••' : money(item.invested_value, currency)} />
          <Metric label="Rendimento" value={!hasData ? '—' : hideValues ? '••••••' : money(item.profit_value, currency)} />
          {/* Percentuais e gráfico mensal seguem visíveis mesmo com os valores monetários ocultos. */}
          <Metric label="Rendimento %" value={hasData ? `${Number(item.return_percent).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%` : '—'} />
          <Metric label={currency === 'BRL' ? 'CDI no mês' : 'CDI'} value={currency === 'BRL' && cdi != null ? `${Number(cdi).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%` : '—'} />
          <Metric label="Acima do CDI" value={currency === 'BRL' && item.excess_percentage_points != null ? `${Number(item.excess_percentage_points) >= 0 ? '+' : ''}${Number(item.excess_percentage_points).toLocaleString('pt-BR', { maximumFractionDigits: 2 })} p.p.` : '—'} />
          <Metric label="Equivale a" value={currency === 'BRL' && item.percent_of_cdi != null ? `${Number(item.percent_of_cdi).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}% do CDI` : '—'} />
        </View>
        {item.source_status === 'insufficient' || !hasData ? <Text style={styles.muted}>Precisamos de pelo menos duas atualizações completas para calcular o rendimento.</Text> : <MonthlyReturnGraph points={points} cdiAvailable={currency === 'BRL' && cdi != null} />}
      </View>;
    })}
    {currencies.some((item) => item.data_available) ? <Text style={styles.muted}>Estimativa baseada nos snapshots e no resultado das posições abertas; aportes, retiradas e vendas realizadas podem alterar o resultado mensal.</Text> : null}
    {data?.cdi_status === 'cached' ? <Text style={styles.muted}>CDI: último dado em cache de {data?.cdi_as_of ? dateOnlyValue(data.cdi_as_of) : 'data indisponível'}.</Text> : data?.cdi_as_of ? <Text style={styles.muted}>CDI oficial atualizado em {dateOnlyValue(data.cdi_as_of)}.</Text> : <Text style={styles.muted}>CDI oficial indisponível no momento.</Text>}
  </View>;
}

// Apresenta posições, rendimento e histórico de operações.
function PortfolioView({ portfolio, transactions, monthlyPerformance, monthlyPerformanceError, hideValues, onEmitReport }: { portfolio: Portfolio | null; transactions: JsonMap[]; monthlyPerformance: JsonMap | null; monthlyPerformanceError?: string; hideValues: boolean; onEmitReport: () => void }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Carteira de investimentos</Text>
      {/* Este botão não recebe o estado busy; emissões paralelas gravam no mesmo destino local (achado 208). */}
      <Pressable onPress={onEmitReport} style={styles.outlineWideButton}><Text style={styles.outlineButtonText}>Emitir relatório detalhado (PDF)</Text></Pressable>
      <View style={styles.cardGrid}>
        <Metric label="Investido" value={hideValues ? '••••••' : money(portfolio?.invested_total)} />
        <Metric label="Atualizado" value={hideValues ? '••••••' : money(portfolio?.current_total)} />
        <Metric label="Resultado" value={hideValues ? '••••••' : money(portfolio?.pnl_total)} />
      </View>
      {portfolio?.positions?.length ? <View style={styles.card}>
        <Text style={styles.cardTitle}>Distribuição da carteira</Text>
        {/* A rosca apresenta alocações percentuais e não recebe a preferência hideValues. */}
        {Array.from(new Set(portfolio.positions.map((position) => position.currency || 'BRL'))).sort().map((currency) => <View key={currency} style={styles.allocationCurrency}><Text style={styles.subsectionTitle}>{currency}</Text><PortfolioDonut positions={portfolio.positions} currency={currency} /></View>)}
        {portfolio.mixed_currency ? <Text style={styles.muted}>As moedas são exibidas separadamente, sem conversão cambial.</Text> : null}
      </View> : null}
      <MonthlyPerformance data={monthlyPerformance} error={monthlyPerformanceError} hideValues={hideValues} />
      {(portfolio?.positions || []).map((position) => (
        <View style={styles.card} key={position.id}>
          <View style={styles.rowBetween}>
            <Text style={styles.cardTitle}>{position.symbol}</Text>
            <Text style={styles.badge}>{marketLabel(position.market)}</Text>
          </View>
          <Text style={styles.muted}>{position.name || 'Ativo sem nome informado'}</Text>
          <Text style={styles.bodyText}>{hideValues ? '•••• cotas · médio ••••••' : `${formatInvestmentQuantity(position.quantity)} cotas · médio ${money(position.average_price, position.currency === 'USD' ? 'USD' : 'BRL')}`}</Text>
          <Text style={styles.bodyText}>Atual: {hideValues ? '••••••' : position.current_value == null ? 'Cotação indisponível' : money(position.current_value, position.currency === 'USD' ? 'USD' : 'BRL')}</Text>
          <Text style={styles.bodyText}>Resultado: {hideValues ? '••••••' : position.pnl == null ? '—' : money(position.pnl, position.currency === 'USD' ? 'USD' : 'BRL')} {hideValues || position.pnl_percent == null ? '' : '(' + Number(position.pnl_percent).toFixed(2) + '%)'}</Text>
        </View>
      ))}
      {/* Quantidade, preço unitário e taxas do histórico não acompanham hideValues. */}
      {transactions.length ? <View style={styles.card}>
        <Text style={styles.cardTitle}>Histórico de operações</Text>
        {transactions.map((operation) => {
          const isBuy = operation.operation_type === 'buy';
          const isVoided = operation.voided_at != null;
          const currency = String(operation.currency || 'BRL');
          return <View style={styles.listRow} key={String(operation.id)}>
            <View style={styles.flexOne}>
              <Text style={styles.cardTitle}>{isBuy ? 'Compra' : 'Venda'}{isVoided ? ' anulada' : ''} · {textValue(operation.symbol)}</Text>
              <Text style={styles.muted}>{isVoided ? `Motivo: ${textValue(operation.void_reason, 'não informado')}` : `${dateOnlyValue(operation.operation_date)} · ${formatInvestmentQuantity(operation.quantity)} cotas × ${money(operation.unit_price, currency)} · taxas ${money(operation.fees, currency)}`}</Text>
              {!isVoided && operation.realized_pnl != null ? <Text style={styles.muted}>Resultado realizado: {hideValues ? '••••••' : money(operation.realized_pnl, currency)}</Text> : null}
            </View>
            <Text style={styles.bodyText}>{isVoided ? 'Anulada' : hideValues ? '••••••' : money(operation.net_value, currency)}</Text>
          </View>;
        })}
      </View> : <Text style={styles.muted}>Ainda não há compras ou vendas registradas. Saldos cadastrados antes do início do histórico aparecem como posição inicial.</Text>}
      {!portfolio?.positions?.length ? <Text style={styles.muted}>Nenhuma posição cadastrada.</Text> : null}
    </View>
  );
}

// Lista itens patrimoniais e ações de edição permitidas.
function PatrimonyView({ items, hideValues, canEdit, onEdit, onCreate }: { items: JsonMap[]; hideValues: boolean; canEdit: boolean; onEdit: (item: JsonMap) => void; onCreate: () => void }) {
  return (
    <View style={styles.section}>
      <View style={styles.rowBetween}><Text style={styles.sectionTitle}>Patrimônio</Text>{canEdit ? <Pressable onPress={onCreate}><Text style={styles.link}>Adicionar</Text></Pressable> : null}</View>
      <Text style={styles.muted}>Visão consolidada dos itens informados pelo Advisor.</Text>
      {items.map((item) => (
        <Pressable style={styles.card} key={String(item.id)} onPress={() => canEdit && onEdit(item)}>
          <View style={styles.rowBetween}>
            <Text style={styles.cardTitle}>{textValue(item.description)}</Text>
            <Text style={styles.badge}>{textValue(item.category)}</Text>
          </View>
          <Text style={styles.bodyText}>Valor: {hideValues ? '••••••' : money(item.value)}</Text>
          <Text style={styles.muted}>Instituição: {textValue(item.institution)}</Text>
          {item.notes ? <Text style={styles.bodyText}>{String(item.notes)}</Text> : null}
        </Pressable>
      ))}
      {!items.length ? <Text style={styles.muted}>Nenhum item patrimonial cadastrado.</Text> : null}
    </View>
  );
}

// Mostra metas, progresso e ações associadas ao planejamento.
function GoalsView({ goals, actionPlan, errors, hideValues, canEdit, onEdit, onCreate }: { goals: JsonMap[]; actionPlan: JsonMap[]; errors: WorkspaceErrors; hideValues: boolean; canEdit: boolean; onEdit: (item: JsonMap) => void; onCreate: () => void }) {
  const [filter, setFilter] = useState('all');
  // O filtro considera somente metas ativas; pausadas ficam fora de "Atrasadas" (achado 54).
  // O parse da data sem horário usa meia-noite UTC, antes do fim do prazo local (achado 120).
  const visibleGoals = goals.filter((goal) => filter === 'all' || goal.status === filter || (filter === 'overdue' && goal.status === 'active' && goal.target_date && new Date(String(goal.target_date)) < new Date()));
  return (
    <View style={styles.section}>
      <View style={styles.rowBetween}><Text style={styles.sectionTitle}>Metas e plano de ação</Text>{canEdit ? <Pressable onPress={onCreate}><Text style={styles.link}>Adicionar meta</Text></Pressable> : null}</View>
      <View style={styles.optionWrap}>{[['all', 'Todas'], ['active', 'Ativas'], ['paused', 'Pausadas'], ['completed', 'Concluídas'], ['overdue', 'Atrasadas']].map(([value, label]) => <OptionButton key={value} label={label} active={filter === value} onPress={() => setFilter(value)} />)}</View>
      <ModuleState error={errors.goals}>
        {visibleGoals.map((goal) => (
          <Pressable style={styles.card} key={String(goal.id)} onPress={() => canEdit && onEdit(goal)}>
            <View style={styles.rowBetween}>
              <Text style={styles.cardTitle}>{textValue(goal.title)}</Text>
              <Text style={styles.badge}>{textValue(goal.status)}</Text>
            </View>
            <Text style={styles.bodyText}>{hideValues ? '•••••• de ••••••' : `${money(goal.current_value)} de ${money(goal.target_value)}`}</Text>
            <ProgressBar value={percentage(goal.current_value, goal.target_value)} />
            <Text style={styles.muted}>Prazo: {dateValue(goal.target_date)}</Text>
          </Pressable>
        ))}
        {!visibleGoals.length ? <Text style={styles.muted}>Nenhuma meta neste filtro.</Text> : null}
      </ModuleState>
      <Text style={styles.subsectionTitle}>Ações combinadas</Text>
      <ModuleState error={errors.actionPlan}>
        {actionPlan.map((action) => (
          <View style={styles.card} key={String(action.id)}>
            <View style={styles.rowBetween}>
              <Text style={styles.cardTitle}>{textValue(action.title)}</Text>
              <Text style={styles.badge}>{textValue(action.priority)}</Text>
            </View>
            <Text style={styles.bodyText}>{textValue(action.description)}</Text>
            <Text style={styles.muted}>Status: {textValue(action.status)} · prazo {dateValue(action.due_date)}</Text>
          </View>
        ))}
        {!actionPlan.length ? <Text style={styles.muted}>Nenhuma ação cadastrada.</Text> : null}
      </ModuleState>
    </View>
  );
}

// Lista documentos e permite abrir um item selecionado.
function DocumentsView({ documents, onOpen }: { documents: DocumentItem[]; onOpen: (document: DocumentItem) => void }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Documentos</Text>
      <Text style={styles.muted}>
        Os documentos são enviados e atualizados pelo Advisor. Os comprovantes devem ser renovados anualmente.
      </Text>
      {documents.map((document) => (
        <Pressable style={styles.card} key={document.id} onPress={() => onOpen(document)}>
          <View style={styles.rowBetween}>
            <Text style={styles.cardTitle}>{document.original_name}</Text>
            <Text style={styles.badge}>{documentKind(document.kind)}</Text>
          </View>
          {document.description ? <Text style={styles.bodyText}>{document.description}</Text> : null}
          <Text style={styles.muted}>Enviado em {dateValue(document.created_at)} · {document.size_bytes} bytes</Text>
          <Text style={styles.link}>Toque para abrir ou compartilhar</Text>
        </Pressable>
      ))}
      {!documents.length ? <Text style={styles.muted}>Nenhum documento disponível.</Text> : null}
    </View>
  );
}

// Lista relatórios disponibilizados ao cliente.
function ReportsView({ reports }: { reports: JsonMap[] }) {
  const [selected, setSelected] = useState<JsonMap | null>(null);
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Relatórios</Text>
      <Text style={styles.muted}>Relatórios publicados pelo Advisor para acompanhamento do cliente.</Text>
      {reports.map((report) => (
        /* Seleciona o relatório da lista para abrir sua visualização ampliada. */
        <Pressable style={styles.card} key={String(report.id)} onPress={() => setSelected(report)}>
          <View style={styles.rowBetween}>
            <Text style={styles.cardTitle}>{textValue(report.title)}</Text>
            <Text style={styles.badge}>{textValue(report.status)}</Text>
          </View>
          <Text style={styles.muted}>{dateValue(report.period_start)} a {dateValue(report.period_end)}</Text>
          <Text style={styles.bodyText}>{textValue(report.summary)}</Text>
        </Pressable>
      ))}
      {!reports.length ? <Text style={styles.muted}>Nenhum relatório publicado.</Text> : null}
      {/* Mantém o resumo aberto até o cliente fechar o modal ou usar o retorno do sistema. */}
      <Modal visible={Boolean(selected)} transparent animationType="fade" onRequestClose={() => setSelected(null)}><View style={styles.dialogBackdrop}><View style={styles.dialogCard}><Text style={styles.sectionTitle}>{textValue(selected?.title)}</Text><Text style={styles.muted}>Período: {dateValue(selected?.period_start)} a {dateValue(selected?.period_end)}</Text><Text style={styles.bodyText}>{textValue(selected?.summary)}</Text><Pressable onPress={() => setSelected(null)} style={styles.outlineWideButton}><Text style={styles.outlineButtonText}>Fechar</Text></Pressable></View></View></Modal>
    </View>
  );
}

// Exibe e edita cadastro, dados financeiros e senha do cliente.
function ProfileView({
  errors,
  profile,
  financialProfile,
  hideValues,
  canEditFinancial,
  clientId,
  onSaved,
  biometricOn,
  preferences,
  onToggleBiometric,
  onTogglePreference,
}: {
  errors: WorkspaceErrors;
  profile: JsonMap | null;
  financialProfile: JsonMap | null;
  hideValues: boolean;
  canEditFinancial: boolean;
  clientId: number;
  onSaved: () => void;
  biometricOn: boolean;
  preferences: JsonMap;
  onToggleBiometric: (value: boolean) => void;
  onTogglePreference: (key: string, value: boolean) => void;
}) {
  const [financialEditor, setFinancialEditor] = useState(false);
  const [income, setIncome] = useState('');
  const [expenses, setExpenses] = useState('');
  const [riskProfile, setRiskProfile] = useState('');
  const [passwordEditor, setPasswordEditor] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [saving, setSaving] = useState(false);
  // Preenche os campos controlados sempre que o perfil financeiro recebido muda.
  useEffect(() => {
    setIncome(formatMoneyInput(String(financialProfile?.monthly_income ?? '0')));
    setExpenses(formatMoneyInput(String(financialProfile?.monthly_expenses ?? '0')));
    setRiskProfile(String(financialProfile?.risk_profile ?? ''));
  }, [financialProfile]);
  // Valida e salva renda e despesas do perfil financeiro.
  async function saveFinancial() {
    const normalizedIncome = parseMoneyInput(income);
    const normalizedExpenses = parseMoneyInput(expenses);
    if (!Number.isFinite(normalizedIncome) || normalizedIncome < 0 || !Number.isFinite(normalizedExpenses) || normalizedExpenses < 0) {
      Alert.alert('Confira os valores', 'Informe renda e despesas válidas, sem valores negativos.');
      return;
    }
    setSaving(true);
    try {
      await api.updateFinancialProfile(clientId, { monthly_income: normalizedIncome, monthly_expenses: normalizedExpenses, risk_profile: riskProfile.trim() || null }); // Texto livre segue sem validação do identificador canônico (achado 139).
      setFinancialEditor(false); onSaved();
    } catch (cause) { Alert.alert('Não foi possível salvar', cause instanceof Error ? cause.message : 'Tente novamente.'); }
    finally { setSaving(false); }
  }
  // Valida os campos e envia a troca de senha.
  async function savePassword() {
    if (newPassword.length < 8 || newPassword !== confirmPassword) { Alert.alert('Confira a nova senha', 'Use ao menos 8 caracteres e confirme a mesma senha.'); return; }
    setSaving(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setPasswordEditor(false); setCurrentPassword(''); setNewPassword(''); setConfirmPassword('');
      Alert.alert('Senha alterada', 'Sua senha foi atualizada.');
    } catch (cause) { Alert.alert('Não foi possível alterar a senha', cause instanceof Error ? cause.message : 'Tente novamente.'); }
    finally { setSaving(false); }
  }
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Meu perfil</Text>
      <ModuleState error={errors.profile}>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Dados cadastrais</Text>
          <ProfileLine label="Nome" value={textValue(profile?.name)} />
          <ProfileLine label="E-mail" value={textValue(profile?.email)} />
          <ProfileLine label="Telefone" value={textValue(profile?.phone)} />
          <ProfileLine label="Pai" value={textValue(profile?.father_name)} />
          <ProfileLine label="Mãe" value={textValue(profile?.mother_name)} />
          <ProfileLine label="Advisor" value={textValue(profile?.advisor_name)} />
        </View>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Endereço</Text>
          <ProfileLine label="Rua" value={textValue(profile?.address_street)} />
          <ProfileLine label="Número" value={textValue(profile?.address_number)} />
          <ProfileLine label="Cidade" value={textValue(profile?.address_city)} />
          <ProfileLine label="CEP" value={textValue(profile?.address_zip_code)} />
          <ProfileLine label="Estado" value={textValue(profile?.address_state)} />
        </View>
      </ModuleState>
      <ModuleState error={errors.financialProfile && 'Perfil financeiro: ' + errors.financialProfile}>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Perfil financeiro</Text>
          <ProfileLine label="Renda mensal" value={hideValues ? '••••••' : money(financialProfile?.monthly_income)} />
          <ProfileLine label="Despesas mensais" value={hideValues ? '••••••' : money(financialProfile?.monthly_expenses)} />
          <ProfileLine label="Perfil de risco" value={textValue(financialProfile?.risk_profile)} />
          {canEditFinancial ? <Pressable onPress={() => setFinancialEditor(true)}><Text style={styles.link}>Editar perfil financeiro</Text></Pressable> : null}
        </View>
      </ModuleState>
      <View style={styles.card}>
        <View style={styles.rowBetween}>
          <View style={styles.flexOne}>
            <Text style={styles.cardTitle}>Acesso com biometria</Text>
            <Text style={styles.muted}>Protege a abertura da sessão neste aparelho.</Text>
          </View>
          {/* O texto ao lado é visual; o Switch ainda não recebe um rótulo acessível (achado 200). */}
          <Switch value={biometricOn} onValueChange={onToggleBiometric} />
        </View>
      </View>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Preferências de avisos</Text>
        <ModuleState error={errors.notificationPreferences}>
          {preferenceLabels.map((item) => (
            <View style={styles.preferenceRow} key={item.key}>
              <Text style={styles.bodyText}>{item.label}</Text>
              {/* A legenda da preferência não está associada ao controle nativo (achado 200). */}
              <Switch
                value={Boolean(preferences[item.key])}
                onValueChange={(value) => onTogglePreference(item.key, value)}
              />
            </View>
          ))}
        </ModuleState>
      </View>
      <Pressable onPress={() => setPasswordEditor(true)} style={styles.outlineWideButton}><Text style={styles.outlineButtonText}>Alterar senha</Text></Pressable>
      <Text style={styles.muted}>Para alterar seus dados cadastrais, solicite a atualização ao Advisor responsável.</Text>
      <Modal visible={financialEditor} animationType="slide" onRequestClose={() => setFinancialEditor(false)}><SafeAreaView style={styles.modalSafe}><ScrollView contentContainerStyle={styles.modalContent}><View style={styles.rowBetween}><Text style={styles.sectionTitle}>Editar perfil financeiro</Text><Pressable onPress={() => setFinancialEditor(false)}><Text style={styles.link}>Fechar</Text></Pressable></View><MoneyInput value={income} onChangeText={setIncome} placeholder="Renda mensal" /><MoneyInput value={expenses} onChangeText={setExpenses} placeholder="Despesas mensais" /><TextInput style={styles.input} value={riskProfile} onChangeText={setRiskProfile} placeholder="Perfil de risco (opcional)" /><Pressable disabled={saving} onPress={() => void saveFinancial()} style={styles.primaryButton}>{saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>Salvar</Text>}</Pressable></ScrollView></SafeAreaView></Modal>
      <Modal visible={passwordEditor} animationType="slide" onRequestClose={() => setPasswordEditor(false)}><SafeAreaView style={styles.modalSafe}><ScrollView contentContainerStyle={styles.modalContent}><View style={styles.rowBetween}><Text style={styles.sectionTitle}>Alterar senha</Text><Pressable onPress={() => setPasswordEditor(false)}><Text style={styles.link}>Fechar</Text></Pressable></View><TextInput style={styles.input} secureTextEntry value={currentPassword} onChangeText={setCurrentPassword} placeholder="Senha atual" /><TextInput style={styles.input} secureTextEntry value={newPassword} onChangeText={setNewPassword} placeholder="Nova senha (mínimo 8 caracteres)" /><TextInput style={styles.input} secureTextEntry value={confirmPassword} onChangeText={setConfirmPassword} placeholder="Confirme a nova senha" /><Pressable disabled={saving} onPress={() => void savePassword()} style={styles.primaryButton}>{saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>Atualizar senha</Text>}</Pressable></ScrollView></SafeAreaView></Modal>
    </View>
  );
}

// Apresenta uma notificação e oferece a ação de leitura.
function NotificationCard({
  notifications,
  unread,
  onMarkRead,
  onMarkAllRead,
  onOpenAll,
}: {
  notifications: NotificationItem[];
  unread: NotificationItem[];
  onMarkRead: (item: NotificationItem) => void;
  onMarkAllRead: () => void;
  onOpenAll: () => void;
}) {
  return (
    <View style={styles.card}>
      <View style={styles.rowBetween}>
        <Text style={styles.cardTitle}>Notificações ({unread.length})</Text>
        <View style={styles.optionWrap}>{unread.length ? <Pressable onPress={onMarkAllRead}><Text style={styles.link}>Marcar todas</Text></Pressable> : null}<Pressable onPress={onOpenAll}><Text style={styles.link}>Ver histórico</Text></Pressable></View>
      </View>
      {notifications.slice(0, 4).map((notification) => (
        <Pressable
          key={notification.id}
          onPress={() => onMarkRead(notification)}
          style={[styles.notificationRow, !notification.read_at && styles.unreadRow]}
        >
          <Text style={styles.bodyText}>{notification.title}</Text>
          <Text style={styles.muted}>{notification.message}</Text>
        </Pressable>
      ))}
      {!notifications.length ? <Text style={styles.muted}>Nenhuma notificação.</Text> : null}
    </View>
  );
}

// Lista notificações e encaminha ações de leitura.
function NotificationsView({ notifications, onMarkRead, onMarkAllRead }: { notifications: NotificationItem[]; onMarkRead: (item: NotificationItem) => void; onMarkAllRead: () => void }) {
  const [filter, setFilter] = useState('all');
  // O filtro atua sobre a lista carregada, limitada a 50 itens pela API.
  const visible = notifications.filter((item) => filter === 'all' || (filter === 'unread' ? !item.read_at : Boolean(item.read_at)));
  return <View style={styles.section}>
    <View style={styles.rowBetween}><Text style={styles.sectionTitle}>Notificações</Text>{notifications.some((item) => !item.read_at) ? <Pressable onPress={onMarkAllRead}><Text style={styles.link}>Marcar todas como lidas</Text></Pressable> : null}</View>
    {/* As opções atualizam o estado do filtro e reaplicam a seleção local. */}
    <View style={styles.optionWrap}>{[['all', 'Todas'], ['unread', 'Não lidas'], ['read', 'Lidas']].map(([value, label]) => <OptionButton key={value} label={label} active={filter === value} onPress={() => setFilter(value)} />)}</View>
    {/* Tocar num aviso encaminha seu registro ao callback que o marca como lido. */}
    {visible.map((item) => <Pressable key={item.id} onPress={() => onMarkRead(item)} style={[styles.card, !item.read_at && styles.unreadRow]}>
      <View style={styles.rowBetween}><Text style={styles.cardTitle}>{item.title}</Text><Text style={styles.badge}>{item.read_at ? 'Lida' : 'Nova'}</Text></View>
      <Text style={styles.bodyText}>{item.message}</Text><Text style={styles.muted}>{dateValue(item.created_at)}</Text>
    </Pressable>)}
    {!visible.length ? <Text style={styles.muted}>Nenhuma notificação neste filtro.</Text> : null}
  </View>;
}

// Resume avaliação, perfil de risco e carteira sugerida.
function SuitabilityCard({
  assessment,
  onQuestionnaire,
  onAccept,
}: {
  assessment: JsonMap | null;
  onQuestionnaire: () => void;
  onAccept: (assessment: JsonMap) => void;
}) {
  const recommendation = assessment?.recommendation;
  const allocations = Array.isArray(recommendation?.allocations) ? recommendation.allocations : [];
  return (
    <View style={styles.card}>
      <View style={styles.rowBetween}>
        <Text style={styles.cardTitle}>Carteira sugerida</Text>
        <Pressable onPress={onQuestionnaire}>
          <Text style={styles.link}>{assessment ? 'Atualizar' : 'Responder'}</Text>
        </Pressable>
      </View>
      {assessment ? (
        <>
          {recommendation?.advisor_proposal_published_at ? <Text style={styles.bodyText}>Sugestão personalizada do Advisor</Text> : null}
          <Text style={styles.subsectionTitle}>Divisão da carteira</Text>
          {allocations.length ? allocations.map((allocation: JsonMap, index: number) => (
            <View key={String(index)} style={styles.question}>
              <View style={styles.listRow}>
                <Text style={styles.bodyText}>{textValue(allocation.label)}</Text>
                <Text style={styles.badge}>{textValue(allocation.percentage)}%</Text>
              </View>
              {(Array.isArray(allocation.suballocations) ? allocation.suballocations : []).map((segment: JsonMap, child: number) => (
                <View key={String(child)} style={styles.question}>
                  <Text style={styles.bodyText}>{textValue(segment.label)} — {textValue(segment.percentage)}%</Text>
                  {Array.isArray(segment.examples) && segment.examples.length ? (
                    <Text style={styles.muted}>Ativos sugeridos: {segment.examples.join(', ')}</Text>
                  ) : null}
                </View>
              ))}
              {(Array.isArray(allocation.advisor_assets) ? allocation.advisor_assets : []).map((asset: JsonMap, assetIndex: number) => (
                <View key={`advisor-${assetIndex}`} style={styles.question}>
                  <Text style={styles.muted}>Selecionado pelo Advisor: {textValue(asset.symbol)} — {textValue(asset.name)}</Text>
                </View>
              ))}
            </View>
          )) : <Text style={styles.muted}>A divisão sugerida ainda não está disponível.</Text>}
          {/* A API exige proposta publicada e aprovação; o botão não bloqueia toques repetidos (achado 155). */}
          {recommendation?.advisor_proposal_published_at && assessment.status === 'approved' && assessment.client_response === 'pending' ? (
            <Pressable onPress={() => onAccept(assessment)} style={styles.primaryButton}><Text style={styles.primaryButtonText}>Aceitar sugestão do Advisor</Text></Pressable>
          ) : assessment.client_response === 'accepted' ? <Text style={styles.bodyText}>Você aceitou esta sugestão do Advisor.</Text> : null}
        </>
      ) : (
        <Text style={styles.muted}>Responda ao questionário para ver a divisão e os ativos sugeridos.</Text>
      )}
    </View>
  );
}

// Apresenta o contexto financeiro considerado na avaliação.
function FinancialSnapshot({ snapshot, hideValues = false }: { snapshot: JsonMap; hideValues?: boolean }) {
  // Formata valores financeiros ou os oculta conforme a preferência.
  // Mantém a máscara aplicada de forma uniforme aos montantes deste retrato.
  const amount = (value: unknown) => hideValues ? '••••••' : money(value as number | string | null | undefined);
  return <View style={styles.question}>
    <Text style={styles.cardTitle}>Situação financeira usada nesta avaliação</Text>
    <Text style={styles.bodyText}>Renda mensal: {amount(snapshot.monthly_income)}</Text>
    <Text style={styles.bodyText}>Despesas mensais: {amount(snapshot.monthly_expenses)}</Text>
    <Text style={styles.bodyText}>Saldo mensal: {amount(snapshot.monthly_surplus)}</Text>
    <Text style={styles.bodyText}>Patrimônio cadastrado, sem dívidas: {amount(snapshot.patrimony_total)}</Text>
    {(Array.isArray(snapshot.patrimony_by_category) ? snapshot.patrimony_by_category : []).map((category: JsonMap, index: number) => <Text style={styles.muted} key={String(index)}>{textValue(category.category)}: {amount(category.value)}</Text>)}
    {(Array.isArray(snapshot.active_goals) && snapshot.active_goals.length) ? <Text style={styles.muted}>Metas ativas: {snapshot.active_goals.map((goal: JsonMap) => goal.title).join(', ')}</Text> : null}
  </View>;
}

// Mostra o alerta de mercado e permite editar seu estado.
function AlertCard({
  alerts,
  onNew,
  onEdit,
}: {
  alerts: MarketAlert[];
  onNew: () => void;
  onEdit: (item: MarketAlert) => void;
}) {
  return (
    <View style={styles.card}>
      <View style={styles.rowBetween}>
        <Text style={styles.cardTitle}>Alertas de preço</Text>
        <Pressable onPress={onNew}><Text style={styles.link}>Novo alerta</Text></Pressable>
      </View>
      {alerts.slice(0, 4).map((alert) => (
        <Pressable key={alert.id} onPress={() => onEdit(alert)} style={styles.listRow}>
          <View style={styles.flexOne}>
            <Text style={styles.bodyText}>{alert.symbol} · {marketLabel(alert.market)}</Text>
            <Text style={styles.muted}>{alertConditionLabel(alert.condition)} {money(alert.target_price, alert.market === 'global' ? 'USD' : 'BRL')}</Text>
          </View>
          <Text style={styles.badge}>{alertStatusLabel(alert.status)}</Text>
        </Pressable>
      ))}
      {!alerts.length ? <Text style={styles.muted}>Nenhum alerta configurado.</Text> : null}
    </View>
  );
}

// Conduz o preenchimento e a confirmação do questionário.
function SuitabilityModal({
  visible,
  questionnaire,
  current,
  onClose,
  onSaved,
}: {
  visible: boolean;
  questionnaire: JsonMap | null;
  current: JsonMap | null;
  onClose: () => void;
  onSaved: (assessment: JsonMap) => void;
}) {
  const [objective, setObjective] = useState('');
  const [answers, setAnswers] = useState<JsonMap>({});
  const [confirmedFinancial, setConfirmedFinancial] = useState(false);
  const [saving, setSaving] = useState(false);
  const objectives = Array.isArray(questionnaire?.objectives) ? questionnaire.objectives : [];
  const questions = Array.isArray(questionnaire?.questions) ? questionnaire.questions : [];
  const financialSituation = questionnaire?.financial_situation || {};

  // Só reinicia ao abrir ou trocar a definição; mudança isolada de current não dispara o efeito (achado 203).
  useEffect(() => {
    if (!visible) return;
    setObjective(textValue(current?.objective, objectives[0]?.value || ''));
    setAnswers(current?.answers && typeof current.answers === 'object' ? { ...current.answers } : {});
    setConfirmedFinancial(false);
  }, [visible, questionnaire]);

  // Valida as respostas e envia a avaliação de suitability para a API.
  async function submit() {
    if (!objective || questions.some((question: JsonMap) => !answers[question.key]) || !confirmedFinancial) {
      Alert.alert('Questionário incompleto', 'Responda todas as perguntas para calcular a sugestão.');
      return;
    }
    if (!financialSituation.has_financial_profile || !financialSituation.data_version) {
      Alert.alert('Perfil financeiro necessário', 'Peça ao Advisor para cadastrar seu perfil financeiro antes de continuar.');
      return;
    }
    setSaving(true);
    try {
      const result = await api.submitSuitability(objective, answers, String(financialSituation.data_version), confirmedFinancial);
      onSaved(result);
    } catch (cause) {
      Alert.alert('Não foi possível salvar', cause instanceof Error ? cause.message : 'Tente novamente.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <SafeAreaView style={styles.modalSafe}>
        <ScrollView contentContainerStyle={styles.modalContent}>
          <View style={styles.rowBetween}>
            <Text style={styles.sectionTitle}>Questionário de suitability</Text>
            <Pressable onPress={onClose}><Text style={styles.link}>Fechar</Text></Pressable>
          </View>
          <Text style={styles.muted}>{textValue(questionnaire?.disclaimer)}</Text>
          {/* O modal não recebe hideValues; os valores deste resumo permanecem visíveis (achado 13). */}
          <FinancialSnapshot snapshot={financialSituation} />
          <View style={styles.preferenceRow}>
            <Text style={[styles.bodyText, styles.flexOne]}>Confirmo que revisei os dados financeiros acima.</Text>
            {/* O texto de confirmação não foi definido como rótulo acessível do Switch (achado 200). */}
            <Switch value={confirmedFinancial} onValueChange={setConfirmedFinancial} />
          </View>
          <Text style={styles.subsectionTitle}>Objetivo principal</Text>
          <View style={styles.optionWrap}>
            {objectives.map((item: JsonMap) => (
              <OptionButton
                key={String(item.value)}
                label={textValue(item.label)}
                active={objective === item.value}
                onPress={() => setObjective(String(item.value))}
              />
            ))}
          </View>
          {questions.map((question: JsonMap, index: number) => (
            <View style={styles.question} key={String(question.key)}>
              <Text style={styles.cardTitle}>{index + 1}. {textValue(question.label)}</Text>
              <Text style={styles.muted}>{textValue(question.description)}</Text>
              <View style={styles.optionWrap}>
                {/* Alterna uma opção no modo múltiplo e substitui a resposta no modo único. */}
                {(Array.isArray(question.options) ? question.options : []).map((option: JsonMap) => (
                  <OptionButton
                    key={String(option.value)}
                    label={textValue(option.label)}
                  active={String(answers[question.key] || '').split(',').includes(String(option.value))}
                    onPress={() => setAnswers((currentAnswers) => {
                      const selected = String(currentAnswers[question.key] || '').split(',').filter(Boolean);
                      if (question.selection_mode === 'multiple') {
                        const next = selected.includes(String(option.value)) ? selected.filter((value) => value !== String(option.value)) : [...selected, String(option.value)];
                        return { ...currentAnswers, [question.key]: next.join(',') };
                      }
                      return { ...currentAnswers, [question.key]: option.value };
                    })}
                  />
                ))}
              </View>
            </View>
          ))}
          <Pressable disabled={saving} onPress={() => void submit()} style={styles.primaryButton}>
            {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>Calcular sugestão</Text>}
          </Pressable>
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

// Edita ou cria um item patrimonial ou uma meta financeira.
function RecordEditorModal({
  visible,
  kind,
  item,
  onClose,
  onSave,
  onDelete,
}: {
  visible: boolean;
  kind: 'patrimony' | 'goal';
  item: JsonMap | null;
  onClose: () => void;
  onSave: (values: JsonMap) => void;
  onDelete: () => void;
}) {
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('');
  const [institution, setInstitution] = useState('');
  const [amount, setAmount] = useState('');
  const [currentAmount, setCurrentAmount] = useState('');
  const [targetDate, setTargetDate] = useState('');
  const [notes, setNotes] = useState('');
  const [status, setStatus] = useState('active');
  const [saving, setSaving] = useState(false);
  // Carrega os valores do item selecionado ou limpa o formulário quando um novo modal abre.
  useEffect(() => {
    if (!visible) return;
    setTitle(String(item?.title ?? item?.description ?? ''));
    setCategory(String(item?.category ?? ''));
    setInstitution(String(item?.institution ?? ''));
    setAmount(formatMoneyInput(String(item?.target_value ?? item?.value ?? '')));
    setCurrentAmount(formatMoneyInput(String(item?.current_value ?? '0')));
    setTargetDate(String(item?.target_date ?? '').slice(0, 10));
    setNotes(String(item?.notes ?? ''));
    setStatus(String(item?.status ?? 'active'));
  }, [visible, item, kind]);
  // Converte o texto do campo monetário em valor numérico.
  function numeric(value: string) { return parseMoneyInput(value); }
  // Valida os campos e encaminha os dados do registro para salvamento.
  async function submit() {
    // A regra de valor e os limites textuais não reproduzem integralmente os schemas (achado 129).
    if (!title.trim() || !Number.isFinite(numeric(amount)) || numeric(amount) <= 0 || (kind === 'goal' && !Number.isFinite(numeric(currentAmount)))) {
      Alert.alert('Confira os dados', 'Informe uma descrição e valores válidos.'); return;
    }
    setSaving(true);
    try {
      const values = kind === 'goal'
        ? { title: title.trim(), target_value: numeric(amount), current_value: numeric(currentAmount), target_date: targetDate || null, ...(item ? { status } : {}) }
        : { description: title.trim(), category: category.trim() || 'Outros', institution: institution.trim() || null, value: numeric(amount), notes: notes.trim() || null };
      onSave(values); // Não aguarda o callback; o finally libera saving antes de a requisição terminar (achado 22).
    } finally { setSaving(false); }
  }
  // Pede confirmação antes de excluir o registro selecionado.
  function confirmDelete() {
    Alert.alert('Excluir registro?', 'Esta ação removerá o item do seu planejamento.', [
      { text: 'Cancelar', style: 'cancel' }, { text: 'Excluir', style: 'destructive', onPress: onDelete },
    ]);
  }
  return <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
    <SafeAreaView style={styles.modalSafe}><ScrollView contentContainerStyle={styles.modalContent}>
      <View style={styles.rowBetween}><Text style={styles.sectionTitle}>{item ? 'Editar' : 'Adicionar'} {kind === 'goal' ? 'meta' : 'patrimônio'}</Text><Pressable onPress={onClose}><Text style={styles.link}>Fechar</Text></Pressable></View>
      <TextInput style={styles.input} value={title} onChangeText={setTitle} placeholder={kind === 'goal' ? 'Nome da meta' : 'Descrição do item'} />
      {kind === 'patrimony' ? <>
        <TextInput style={styles.input} value={category} onChangeText={setCategory} placeholder="Categoria (ex.: imóvel, reserva)" />
        <TextInput style={styles.input} value={institution} onChangeText={setInstitution} placeholder="Instituição (opcional)" />
      </> : null}
      <MoneyInput value={amount} onChangeText={setAmount} placeholder={kind === 'goal' ? 'Valor desejado' : 'Valor'} />
      {kind === 'goal' ? <>
        <MoneyInput value={currentAmount} onChangeText={setCurrentAmount} placeholder="Valor já acumulado" />
        <TextInput style={styles.input} value={targetDate} onChangeText={setTargetDate} placeholder="Prazo (AAAA-MM-DD)" />
        {item ? <View style={styles.optionWrap}>{[['active', 'Ativa'], ['paused', 'Pausada'], ['completed', 'Concluída']].map(([value, label]) => <OptionButton key={value} label={label} active={status === value} onPress={() => setStatus(value)} />)}</View> : null}
      </> : <TextInput style={styles.input} value={notes} onChangeText={setNotes} placeholder="Observações (opcional)" />}
      <Pressable disabled={saving} onPress={() => void submit()} style={styles.primaryButton}>{saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>Salvar</Text>}</Pressable>
      {item ? <Pressable onPress={confirmDelete} style={styles.dangerButton}><Text style={styles.dangerText}>Excluir</Text></Pressable> : null}
    </ScrollView></SafeAreaView>
  </Modal>;
}

// Permite criar ou atualizar um alerta de preço.
function AlertEditorModal({
  visible,
  initial,
  onClose,
  onSaved,
}: {
  visible: boolean;
  initial: MarketAlert | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [symbol, setSymbol] = useState('');
  const [market, setMarket] = useState<'br' | 'global'>('br');
  const [targetPrice, setTargetPrice] = useState('');
  const [condition, setCondition] = useState<'at_or_below' | 'at_or_above'>('at_or_below');
  const [saving, setSaving] = useState(false);

  // Inicializa os campos com o alerta em edição ou com os valores padrão para criação.
  useEffect(() => {
    setSymbol(initial?.symbol || '');
    setMarket(initial?.market || 'br');
    setTargetPrice(initial ? formatMoneyInput(String(initial.target_price)) : '');
    setCondition(initial?.condition || 'at_or_below');
  }, [initial, visible]);

  // Valida e persiste a configuração do alerta.
  async function save() {
    const normalizedPrice = parseMoneyInput(targetPrice);
    if (!symbol.trim() || !Number.isFinite(normalizedPrice) || normalizedPrice <= 0) {
      Alert.alert('Dados incompletos', 'Informe o ativo e um preço-alvo válido.');
      return;
    }
    setSaving(true);
    try {
      if (initial) {
        await api.updateMarketAlert(initial.id, { target_price: normalizedPrice, condition });
      } else {
        await api.createMarketAlert({
          symbol: symbol.trim().toUpperCase(),
          market,
          target_price: normalizedPrice,
          condition,
        });
      }
      onSaved(); // A recarga iniciada pelo callback não é aguardada (achado 28).
    } catch (cause) {
      Alert.alert('Não foi possível salvar', cause instanceof Error ? cause.message : 'Tente novamente.');
    } finally {
      setSaving(false);
    }
  }

  // Confirma e solicita o cancelamento do alerta.
  function cancelAlert() {
    if (!initial) return;
    Alert.alert('Desativar alerta?', 'O alerta deixará de ser monitorado.', [
      { text: 'Voltar', style: 'cancel' },
      {
        text: 'Desativar',
        style: 'destructive',
        onPress: async () => {
          // Cancela no servidor somente depois da confirmação explícita na caixa de diálogo.
          try {
            await api.cancelMarketAlert(initial.id);
            onSaved(); // A recarga iniciada pelo callback não é aguardada (achado 28).
          } catch (cause) {
            Alert.alert('Não foi possível desativar', cause instanceof Error ? cause.message : 'Tente novamente.');
          }
        },
      },
    ]);
  }

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <SafeAreaView style={styles.modalSafe}>
        <ScrollView contentContainerStyle={styles.modalContent}>
          <View style={styles.rowBetween}>
            <Text style={styles.sectionTitle}>{initial ? 'Editar alerta' : 'Novo alerta'}</Text>
            <Pressable onPress={onClose}><Text style={styles.link}>Fechar</Text></Pressable>
          </View>
          <TextInput
            autoCapitalize="characters"
            editable={!initial}
            placeholder="Código do ativo, ex.: PETR4"
            placeholderTextColor={colors.placeholder}
            style={[styles.input, initial && styles.disabledInput]}
            value={symbol}
            onChangeText={setSymbol}
          />
          <Text style={styles.subsectionTitle}>Mercado</Text>
          <View style={styles.optionWrap}>
            <OptionButton label="Brasil — B3" active={market === 'br'} onPress={() => setMarket('br')} disabled={Boolean(initial)} />
            <OptionButton label="Exterior" active={market === 'global'} onPress={() => setMarket('global')} disabled={Boolean(initial)} />
          </View>
          <MoneyInput value={targetPrice} onChangeText={setTargetPrice} placeholder="Preço-alvo" />
          <Text style={styles.subsectionTitle}>Condição</Text>
          <View style={styles.optionWrap}>
            <OptionButton label="Atingir ou ficar abaixo" active={condition === 'at_or_below'} onPress={() => setCondition('at_or_below')} />
            <OptionButton label="Atingir ou superar" active={condition === 'at_or_above'} onPress={() => setCondition('at_or_above')} />
          </View>
          <Pressable disabled={saving} onPress={() => void save()} style={styles.primaryButton}>
            {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>Salvar alerta</Text>}
          </Pressable>
          {initial && initial.status !== 'cancelled' ? (
            <Pressable onPress={cancelAlert} style={styles.dangerButton}>
              <Text style={styles.dangerButtonText}>Desativar alerta</Text>
            </Pressable>
          ) : null}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

// Apresenta uma opção selecionável de formulário.
function OptionButton({
  label,
  active,
  disabled,
  onPress,
}: {
  label: string;
  active: boolean;
  disabled?: boolean;
  onPress: () => void;
}) {
  return (
    {/* A opção ativa também é indicada só pelo estilo; seu estado não é acessível (achado 199). */}
    <Pressable disabled={disabled} onPress={onPress} style={[styles.option, active && styles.activeOption, disabled && styles.disabledOption]}>
      <Text style={[styles.optionText, active && styles.activeOptionText]}>{label}</Text>
    </Pressable>
  );
}

// Exibe um campo de perfil como rótulo e valor.
function ProfileLine({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.profileLine}>
      <Text style={styles.muted}>{label}</Text>
      <Text style={styles.bodyText}>{value}</Text>
    </View>
  );
}

// Mostra visualmente o percentual de progresso informado.
function ProgressBar({ value }: { value: number }) {
  return (
    <View style={styles.progressTrack}>
      <View style={[styles.progressFill, { width: (String(value) + '%') as `${number}%` }]} />
    </View>
  );
}

// Apresenta um indicador resumido com seu título e valor.
function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
    </View>
  );
}

// Cria uma opção de navegação para uma aba do aplicativo.
function TabButton({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    {/* A seleção atual altera somente o estilo; o estado não é anunciado ao leitor de tela (achado 199). */}
    <Pressable onPress={onPress} style={[styles.tab, active && styles.activeTab]}>
      <Text style={[styles.tabText, active && styles.activeTabText]}>{label}</Text>
    </Pressable>
  );
}

// Centraliza o conteúdo usado em estados sem dados ou carregamento.
function Centered({ children }: { children: React.ReactNode }) {
  return <SafeAreaView style={styles.centered}>{children}</SafeAreaView>;
}

// Reúne estilos reutilizados pela navegação, cartões, formulários e gráficos.
const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  centered: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: colors.background },
  container: { padding: 24, gap: 18 },
  loginCard: { padding: 22, borderRadius: 22, backgroundColor: '#fff', gap: 14 },
  modalSafe: { flex: 1, backgroundColor: colors.background },
  modalContent: { padding: 24, gap: 16 },
  dialogBackdrop: { flex: 1, justifyContent: 'center', padding: 22, backgroundColor: 'rgba(23,50,77,0.42)' },
  dialogCard: { gap: 14, padding: 20, borderRadius: 18, backgroundColor: colors.background },
  eyebrow: { color: colors.primary, fontSize: 11, fontWeight: '800', letterSpacing: 1.4 },
  brandLockup: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 48 },
  brandMark: { width: 48, height: 48 },
  brandName: { color: colors.primary, fontSize: 25, fontWeight: '700', letterSpacing: -0.8 },
  title: { color: colors.ink, fontSize: 28, fontWeight: '800', letterSpacing: -0.7 },
  sectionTitle: { color: colors.ink, fontSize: 21, fontWeight: '800' },
  subsectionTitle: { color: colors.ink, fontSize: 15, fontWeight: '800' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 },
  headerCopy: { flex: 1, gap: 4 },
  section: { gap: 12 },
  loginDescription: { marginBottom: 8 },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 20 },
  bodyText: { color: colors.ink, fontSize: 13, lineHeight: 20 },
  input: { height: 48, paddingHorizontal: 14, borderWidth: 1, borderColor: colors.line, borderRadius: 11, color: colors.ink, backgroundColor: '#fff' },
  moneyInputContainer: { minHeight: 48, paddingLeft: 14, paddingRight: 8, marginBottom: 12, flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderColor: colors.line, borderRadius: 11, backgroundColor: '#fff' },
  moneyInputPrefix: { marginRight: 8, color: colors.muted, fontWeight: '600' },
  moneyInput: { flex: 1, height: 48, paddingVertical: 0, color: colors.ink },
  disabledInput: { color: colors.placeholder, backgroundColor: '#F1F4F5' },
  primaryButton: { minHeight: 48, alignItems: 'center', justifyContent: 'center', borderRadius: 11, backgroundColor: colors.primary, paddingHorizontal: 14 },
  primaryButtonText: { color: '#fff', fontWeight: '800', textAlign: 'center' },
  secondaryButton: { minHeight: 48, alignItems: 'center', justifyContent: 'center', borderRadius: 11, backgroundColor: colors.accent, paddingHorizontal: 14 },
  secondaryButtonText: { color: '#fff', fontWeight: '800', textAlign: 'center' },
  outlineButton: { paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: colors.line, borderRadius: 9 },
  outlineWideButton: { minHeight: 44, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.line, borderRadius: 11 },
  outlineButtonText: { color: colors.muted, fontWeight: '700' },
  error: { color: colors.error, fontSize: 13, lineHeight: 19 },
  apiLabel: { color: colors.placeholder, fontSize: 10 },
  tabBar: { gap: 8, padding: 5, borderRadius: 13, backgroundColor: colors.mist },
  tab: { paddingHorizontal: 13, alignItems: 'center', paddingVertical: 10, borderRadius: 9 },
  activeTab: { backgroundColor: '#fff' },
  tabText: { color: colors.muted, fontSize: 12, fontWeight: '700' },
  activeTabText: { color: colors.primary },
  cardGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  allocationCurrency: { marginTop: 14, gap: 8 },
  donutWrap: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  donutGraphic: { width: 132, height: 132, alignItems: 'center', justifyContent: 'center' },
  donutCenter: { position: 'absolute', alignItems: 'center', justifyContent: 'center' },
  donutCenterLabel: { color: colors.ink, fontSize: 14, fontWeight: '800' },
  donutCenterValue: { color: colors.muted, fontSize: 10 },
  donutLegend: { flex: 1, gap: 5 },
  donutLegendRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  donutDot: { width: 8, height: 8, borderRadius: 4 },
  donutLegendName: { flex: 1, color: colors.muted, fontSize: 11 },
  donutLegendPct: { color: colors.ink, fontSize: 11, fontWeight: '700' },
  monthlyCurrency: { gap: 9, paddingTop: 10 },
  monthlyMetrics: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  monthlyGraph: { width: '100%', padding: 8, borderRadius: 12, backgroundColor: '#F3F7F8' },
  monthlyGraphAxis: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 8 },
  graphLegend: { flexDirection: 'row', gap: 16, paddingHorizontal: 8, paddingTop: 8 },
  graphLegendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  graphLineSample: { width: 18, height: 3, borderRadius: 2 },
  metric: { flexGrow: 1, flexBasis: '46%', padding: 13, borderWidth: 1, borderColor: colors.mist, borderRadius: 12, backgroundColor: '#fff' },
  metricLabel: { color: colors.muted, fontSize: 11 },
  metricValue: { marginTop: 5, color: colors.ink, fontSize: 16, fontWeight: '800' },
  card: { gap: 8, padding: 15, borderWidth: 1, borderColor: colors.line, borderRadius: 15, backgroundColor: '#fff' },
  cardTitle: { color: colors.ink, fontSize: 15, fontWeight: '800' },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 10 },
  listRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 10, paddingVertical: 5 },
  flexOne: { flex: 1 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, color: colors.primary, backgroundColor: colors.mist, fontSize: 10, fontWeight: '800' },
  link: { color: colors.primary, fontSize: 12, fontWeight: '800' },
  smallButton: { alignSelf: 'flex-start', paddingHorizontal: 12, paddingVertical: 9, borderRadius: 9, backgroundColor: colors.primary },
  dangerButton: { minHeight: 44, alignItems: 'center', justifyContent: 'center', borderRadius: 11, backgroundColor: '#fff0f1', borderWidth: 1, borderColor: '#f0bdc5' },
  dangerButtonText: { color: '#b84a5c', fontWeight: '800' },
  dangerText: { color: '#b84a5c', fontWeight: '800' },
  notificationRow: { padding: 8, borderRadius: 9 },
  unreadRow: { backgroundColor: colors.mist },
  question: { gap: 8, paddingTop: 4 },
  optionWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  option: { paddingHorizontal: 11, paddingVertical: 9, borderWidth: 1, borderColor: colors.line, borderRadius: 10, backgroundColor: '#fff' },
  activeOption: { borderColor: colors.primary, backgroundColor: colors.mist },
  disabledOption: { opacity: 0.55 },
  optionText: { color: colors.muted, fontSize: 12, fontWeight: '700' },
  activeOptionText: { color: colors.primary },
  profileLine: { flexDirection: 'row', justifyContent: 'space-between', gap: 12, paddingVertical: 4 },
  preferenceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', minHeight: 42 },
  progressTrack: { height: 7, overflow: 'hidden', borderRadius: 5, backgroundColor: colors.mist },
  progressFill: { height: 7, borderRadius: 5, backgroundColor: colors.accent },
});
