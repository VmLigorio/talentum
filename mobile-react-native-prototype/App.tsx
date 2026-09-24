// Talentum — mobile-react-native-prototype/App.tsx
// Responsabilidade: apresenta a experiência mobile experimental em React Native.
// Este arquivo é um protótipo isolado e não substitui o aplicativo Flutter.

import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import {
  API_URL,
  ApiError,
  Dashboard,
  DocumentItem,
  Portfolio,
  TalentumApi,
  User,
} from './src/api';

const api = new TalentumApi();

type Tab = 'summary' | 'portfolio' | 'documents';

const money = (value?: number | null) =>
  value == null
    ? '—'
    : new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
      }).format(Number(value));

const documentKind = (kind: string) =>
  ({
    identification: 'Identificação',
    income_proof: 'Comprovante de renda',
    address_proof: 'Comprovante de endereço',
    other: 'Outro documento',
  })[kind] || 'Outro documento';

const marketLabel = (market: string) =>
  market === 'br' ? 'Brasil — B3' : 'Exterior';

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [tab, setTab] = useState<Tab>('summary');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    void bootstrap();
  }, []);

  async function bootstrap() {
    try {
      if (await api.restoreSession()) {
        const currentUser = await api.me();
        await loadWorkspace(currentUser);
      }
    } catch {
      await api.logout();
    } finally {
      setLoading(false);
    }
  }

  async function loadWorkspace(currentUser: User) {
    if (currentUser.role !== 'client') {
      throw new ApiError('Este protótipo está focado na experiência do cliente.');
    }
    const [nextDashboard, nextPortfolio, nextDocuments] = await Promise.all([
      api.dashboard(currentUser.id),
      api.portfolio(currentUser.id),
      api.documents(currentUser.id),
    ]);
    setUser(currentUser);
    setDashboard(nextDashboard);
    setPortfolio(nextPortfolio);
    setDocuments(nextDocuments);
    setError('');
  }

  async function handleLogin(email: string, password: string) {
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

  async function handleLogout() {
    await api.logout();
    setUser(null);
    setDashboard(null);
    setPortfolio(null);
    setDocuments([]);
    setTab('summary');
  }

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

  if (loading) {
    return (
      <Centered>
        <ActivityIndicator color="#5d4bc4" size="large" />
      </Centered>
    );
  }

  if (!user) {
    return <LoginScreen busy={busy} error={error} onLogin={handleLogin} />;
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.eyebrow}>TALENTUM · PROTÓTIPO</Text>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>Olá, {user.name.split(' ')[0]}</Text>
            <Text style={styles.muted}>Experiência React Native em avaliação</Text>
          </View>
          <Pressable onPress={() => void handleLogout()} style={styles.outlineButton}>
            <Text style={styles.outlineButtonText}>Sair</Text>
          </Pressable>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}
        <View style={styles.tabBar}>
          <TabButton label="Resumo" active={tab === 'summary'} onPress={() => setTab('summary')} />
          <TabButton label="Carteira" active={tab === 'portfolio'} onPress={() => setTab('portfolio')} />
          <TabButton label="Documentos" active={tab === 'documents'} onPress={() => setTab('documents')} />
        </View>

        {tab === 'summary' ? <SummaryView dashboard={dashboard} portfolio={portfolio} /> : null}
        {tab === 'portfolio' ? <PortfolioView portfolio={portfolio} /> : null}
        {tab === 'documents' ? <DocumentsView documents={documents} /> : null}

        <Pressable onPress={() => void handleRefresh()} style={styles.secondaryButton} disabled={busy}>
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.secondaryButtonText}>Atualizar dados</Text>}
        </Pressable>
        <Text style={styles.apiLabel}>API: {API_URL}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function LoginScreen({
  busy,
  error,
  onLogin,
}: {
  busy: boolean;
  error: string;
  onLogin: (email: string, password: string) => Promise<void>;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  return (
    <Centered>
      <View style={styles.loginCard}>
        <Text style={styles.eyebrow}>TALENTUM · PROTÓTIPO</Text>
        <Text style={styles.title}>Acesso do cliente</Text>
        <Text style={[styles.muted, styles.loginDescription]}>
          Primeira experiência mobile construída com React Native.
        </Text>
        <TextInput
          autoCapitalize="none"
          keyboardType="email-address"
          placeholder="E-mail"
          placeholderTextColor="#9895a8"
          style={styles.input}
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          placeholder="Senha"
          placeholderTextColor="#9895a8"
          secureTextEntry
          style={styles.input}
          value={password}
          onChangeText={setPassword}
        />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Pressable
          disabled={busy}
          onPress={() => void onLogin(email, password)}
          style={styles.primaryButton}
        >
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>Entrar</Text>}
        </Pressable>
        <Text style={styles.apiLabel}>API: {API_URL}</Text>
      </View>
    </Centered>
  );
}

function SummaryView({
  dashboard,
  portfolio,
}: {
  dashboard: Dashboard | null;
  portfolio: Portfolio | null;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Visão geral</Text>
      <View style={styles.cardGrid}>
        <Metric label="Patrimônio" value={money(dashboard?.patrimony_total)} />
        <Metric label="Renda mensal" value={money(dashboard?.monthly_income)} />
        <Metric label="Despesas" value={money(dashboard?.monthly_expenses)} />
        <Metric label="Posições" value={String(portfolio?.position_count ?? 0)} />
      </View>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Próximo passo</Text>
        <Text style={styles.muted}>
          Consulte sua carteira e os documentos disponibilizados pelo Advisor.
        </Text>
      </View>
    </View>
  );
}

function PortfolioView({ portfolio }: { portfolio: Portfolio | null }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Carteira de investimentos</Text>
      <View style={styles.cardGrid}>
        <Metric label="Investido" value={money(portfolio?.invested_total)} />
        <Metric label="Atualizado" value={money(portfolio?.current_total)} />
        <Metric label="Resultado" value={money(portfolio?.pnl_total)} />
      </View>
      {(portfolio?.positions || []).map((position) => (
        <View style={styles.card} key={position.id}>
          <View style={styles.rowBetween}>
            <Text style={styles.cardTitle}>{position.symbol}</Text>
            <Text style={styles.badge}>{marketLabel(position.market)}</Text>
          </View>
          <Text style={styles.muted}>{position.name || 'Ativo sem nome informado'}</Text>
          <Text style={styles.bodyText}>
            {position.quantity} cotas/ações · médio {money(position.average_price)}
          </Text>
          <Text style={styles.bodyText}>
            Atual: {position.current_value == null ? 'Cotação indisponível' : money(position.current_value)}
          </Text>
        </View>
      ))}
      {!portfolio?.positions?.length ? <Text style={styles.muted}>Nenhuma posição cadastrada.</Text> : null}
    </View>
  );
}

function DocumentsView({ documents }: { documents: DocumentItem[] }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Documentos</Text>
      <Text style={styles.muted}>
        Os documentos são enviados e atualizados pelo Advisor. Nesta versão, o cliente apenas visualiza os arquivos.
      </Text>
      {documents.map((document) => (
        <View style={styles.card} key={document.id}>
          <Text style={styles.cardTitle}>{document.original_name}</Text>
          <Text style={styles.muted}>{documentKind(document.kind)}</Text>
          {document.description ? <Text style={styles.bodyText}>{document.description}</Text> : null}
        </View>
      ))}
      {!documents.length ? <Text style={styles.muted}>Nenhum documento disponível.</Text> : null}
    </View>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
    </View>
  );
}

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
    <Pressable onPress={onPress} style={[styles.tab, active && styles.activeTab]}>
      <Text style={[styles.tabText, active && styles.activeTabText]}>{label}</Text>
    </Pressable>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <SafeAreaView style={styles.centered}>{children}</SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#faf9f6' },
  centered: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#faf9f6' },
  container: { padding: 24, gap: 18 },
  loginCard: { padding: 22, borderRadius: 22, backgroundColor: '#fff', gap: 14 },
  eyebrow: { color: '#5d4bc4', fontSize: 11, fontWeight: '800', letterSpacing: 1.4 },
  title: { color: '#211f35', fontSize: 28, fontWeight: '800', letterSpacing: -0.7 },
  sectionTitle: { color: '#211f35', fontSize: 21, fontWeight: '800' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 },
  section: { gap: 12 },
  loginDescription: { marginBottom: 8 },
  muted: { color: '#77758a', fontSize: 13, lineHeight: 20 },
  bodyText: { color: '#211f35', fontSize: 13, lineHeight: 20 },
  input: { height: 48, paddingHorizontal: 14, borderWidth: 1, borderColor: '#e8e6ef', borderRadius: 11, color: '#211f35', backgroundColor: '#fff' },
  primaryButton: { minHeight: 48, alignItems: 'center', justifyContent: 'center', borderRadius: 11, backgroundColor: '#5d4bc4' },
  primaryButtonText: { color: '#fff', fontWeight: '800' },
  secondaryButton: { minHeight: 48, alignItems: 'center', justifyContent: 'center', borderRadius: 11, backgroundColor: '#1a9d91' },
  secondaryButtonText: { color: '#fff', fontWeight: '800' },
  outlineButton: { paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: '#e8e6ef', borderRadius: 9 },
  outlineButtonText: { color: '#77758a', fontWeight: '700' },
  error: { color: '#b84a5c', fontSize: 13, lineHeight: 19 },
  apiLabel: { color: '#9895a8', fontSize: 10 },
  tabBar: { flexDirection: 'row', gap: 8, padding: 5, borderRadius: 13, backgroundColor: '#eeeafd' },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: 9 },
  activeTab: { backgroundColor: '#fff' },
  tabText: { color: '#77758a', fontSize: 12, fontWeight: '700' },
  activeTabText: { color: '#5d4bc4' },
  cardGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  metric: { flexGrow: 1, flexBasis: '46%', padding: 13, borderWidth: 1, borderColor: '#eeeaf9', borderRadius: 12, backgroundColor: '#fff' },
  metricLabel: { color: '#77758a', fontSize: 11 },
  metricValue: { marginTop: 5, color: '#211f35', fontSize: 16, fontWeight: '800' },
  card: { gap: 5, padding: 15, borderWidth: 1, borderColor: '#e8e6ef', borderRadius: 15, backgroundColor: '#fff' },
  cardTitle: { color: '#211f35', fontSize: 15, fontWeight: '800' },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, color: '#5d4bc4', backgroundColor: '#eeeafd', fontSize: 10, fontWeight: '800' },
});
