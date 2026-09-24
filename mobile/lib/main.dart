// Talentum — mobile/lib/main.dart
// Responsabilidade: Implementa a interface Flutter, os fluxos de autenticação e as funcionalidades do cliente.
// Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import 'dart:convert';
import 'dart:io' show File, Platform;
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';

// Converte entradas numéricas digitadas no padrão brasileiro para double.
double? parseBrazilianNumber(String value) {
  final sanitized = value.trim().replaceAll(RegExp(r'[^0-9,.-]'), '');
  if (sanitized.isEmpty) return null;
  final normalized = sanitized.contains(',')
      ? sanitized.replaceAll('.', '').replaceAll(',', '.')
      : sanitized;
  return double.tryParse(normalized);
}

// Formata valores com separador de milhares e casas decimais no padrão pt-BR.
String formatBrazilianNumber(dynamic value, {int fractionDigits = 2}) {
  final parsed = value is num
      ? value.toDouble()
      : parseBrazilianNumber(value?.toString() ?? '');
  if (parsed == null || !parsed.isFinite) {
    return fractionDigits == 0
        ? '0'
        : '0,${List.filled(fractionDigits, '0').join()}';
  }
  final fixed = parsed.abs().toStringAsFixed(fractionDigits);
  final parts = fixed.split('.');
  final groupedInteger = parts[0].replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => '.',
  );
  final sign = parsed < 0 ? '-' : '';
  return '$sign$groupedInteger${fractionDigits > 0 ? ',${parts[1]}' : ''}';
}

const biometricEnabledKey = 'talentum_biometric_enabled';

// Consulta os recursos biométricos disponíveis antes de exibir ações de login.
Future<bool> deviceSupportsBiometrics() async {
  try {
    final authentication = LocalAuthentication();
    if (!await authentication.isDeviceSupported()) return false;
    return (await authentication.getAvailableBiometrics()).isNotEmpty;
  } catch (_) {
    return false;
  }
}

// Mantém a tradução dos tipos internos de documento para os rótulos da interface.
String documentKindLabel(dynamic kind) => switch (kind?.toString()) {
      'identification' => 'Identificação',
      'income_proof' => 'Comprovante de renda',
      'address_proof' => 'Comprovante de endereço',
      _ => 'Outro documento',
    };

const configuredApiUrl = String.fromEnvironment('API_URL');
final apiUrl = configuredApiUrl.isNotEmpty
    ? configuredApiUrl
    : Platform.isAndroid
        ? 'http://10.0.2.2:8000'
        : 'http://127.0.0.1:8000';

// Inicializa preferências, restaura a sessão segura e monta a árvore Flutter.
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final preferences = await SharedPreferences.getInstance();
  final api = ApiClient(
      baseUrl: apiUrl,
      preferences: preferences,
      secureStorage: PlatformSecureValueStore());
  await api.restoreSession();
  runApp(TalentumApp(api: api));
}

// Tema e ponto de entrada visual compartilhado por todas as telas do aplicativo.
class TalentumApp extends StatelessWidget {
  const TalentumApp({super.key, required this.api});

  final ApiClient api;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Talentum',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff5d4bc4)),
        scaffoldBackgroundColor: const Color(0xfffaf9f6),
        useMaterial3: true,
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
        ),
      ),
      home: LoginScreen(api: api),
    );
  }
}

// Tela inicial: autenticação por senha e, quando habilitada, biometria.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.api, this.message});

  final ApiClient api;
  final String? message;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final email = TextEditingController();
  final password = TextEditingController();
  bool loading = false;
  bool obscurePassword = true;
  bool biometricAvailable = false;
  bool biometricEnabled = false;
  String? error;
  final localAuthentication = LocalAuthentication();

  @override
  void initState() {
    super.initState();
    error = widget.message;
    _loadBiometricStatus();
  }

  // Carrega a preferência local sem assumir que a sessão ainda está válida.
  Future<void> _loadBiometricStatus() async {
    final enabled =
        widget.api.preferences.getBool(biometricEnabledKey) ?? false;
    if (!widget.api.hasStoredSession || !enabled) return;
    final available = await deviceSupportsBiometrics();
    if (!mounted) return;
    setState(() {
      biometricEnabled = enabled;
      biometricAvailable = available;
    });
  }

  @override
  void dispose() {
    email.dispose();
    password.dispose();
    super.dispose();
  }

  // Valida os campos, autentica na API e navega para a área do cliente.
  Future<void> submit() async {
    if (loading) return;
    final normalizedEmail = email.text.trim();
    if (normalizedEmail.isEmpty || !normalizedEmail.contains('@')) {
      setState(() => error = 'Informe um e-mail válido.');
      return;
    }
    if (password.text.isEmpty) {
      setState(() => error = 'Informe sua senha.');
      return;
    }
    setState(() {
      loading = true;
      error = null;
    });
    try {
      await widget.api.login(normalizedEmail, password.text);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => HomeScreen(api: widget.api)),
      );
    } on ApiException catch (exception) {
      setState(() => error = exception.message);
    } catch (_) {
      setState(() => error = 'Não foi possível conectar à API.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  // Desbloqueia uma sessão salva usando a biometria do dispositivo.
  Future<void> submitWithBiometrics() async {
    if (loading || !biometricAvailable || !widget.api.hasStoredSession) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final authenticated = await localAuthentication.authenticate(
        localizedReason: 'Confirme sua identidade para acessar o Talentum.',
        biometricOnly: true,
        persistAcrossBackgrounding: true,
      );
      if (!authenticated) return;
      await widget.api.me();
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => HomeScreen(api: widget.api)),
      );
    } on ApiException {
      await widget.api.clearSession();
      if (mounted)
        setState(
            () => error = 'Sua sessão expirou. Entre com sua senha novamente.');
    } catch (_) {
      if (mounted)
        setState(() => error = 'Não foi possível validar a biometria.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(28),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 430),
              child: Card(
                elevation: 0,
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Text('talentum ✦',
                          style: TextStyle(
                              fontSize: 22, fontWeight: FontWeight.w800)),
                      const SizedBox(height: 28),
                      Text('Sua jornada financeira começa aqui.',
                          style: Theme.of(context).textTheme.headlineSmall),
                      const SizedBox(height: 8),
                      const Text(
                          'Acompanhe seu patrimônio, metas e relatórios.'),
                      const SizedBox(height: 28),
                      TextField(
                          controller: email,
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.next,
                          autocorrect: false,
                          decoration:
                              const InputDecoration(labelText: 'E-mail')),
                      const SizedBox(height: 14),
                      TextField(
                        controller: password,
                        obscureText: obscurePassword,
                        textInputAction: TextInputAction.done,
                        enableSuggestions: false,
                        decoration: InputDecoration(
                          labelText: 'Senha',
                          suffixIcon: IconButton(
                            tooltip: obscurePassword
                                ? 'Exibir senha'
                                : 'Ocultar senha',
                            onPressed: () => setState(
                                () => obscurePassword = !obscurePassword),
                            icon: Icon(obscurePassword
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined),
                          ),
                        ),
                        onSubmitted: (_) => submit(),
                      ),
                      if (error != null) ...[
                        const SizedBox(height: 12),
                        Text(error!, style: const TextStyle(color: Colors.red)),
                      ],
                      const SizedBox(height: 22),
                      FilledButton(
                          onPressed: loading ? null : submit,
                          child: Text(loading ? 'Entrando...' : 'Entrar')),
                      if (biometricAvailable && biometricEnabled) ...[
                        const SizedBox(height: 10),
                        OutlinedButton.icon(
                          onPressed: loading ? null : submitWithBiometrics,
                          icon: const Icon(Icons.fingerprint),
                          label: const Text('Entrar com biometria'),
                        ),
                      ],
                      const SizedBox(height: 10),
                      const Text(
                        'Por segurança, a senha é solicitada sempre que o aplicativo é aberto.',
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// Área autenticada do cliente: carrega dados, controla abas e edita recursos.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.api});

  final ApiClient api;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // Preferências e cache local permitem preservar a experiência em falhas temporárias.
  static const hideValuesKey = 'talentum_hide_values';
  static const clientCacheKey = 'talentum_client_cache';
  static const defaultNotificationPreferences = <String, dynamic>{
    'action_overdue': true,
    'action_due_soon': true,
    'goal_overdue': true,
    'goal_due_soon': true,
    'document_uploaded': true,
    'document_review_due': true,
    'market_price_alert': true,
  };
  int tab = 0;
  String goalFilter = 'all';
  String notificationFilter = 'all';
  bool hideValues = false;
  Map<String, dynamic>? user;
  Map<String, dynamic>? dashboard;
  Map<String, dynamic>? investmentPortfolio;
  List<dynamic> patrimony = [];
  List<dynamic> goals = [];
  List<dynamic> actionPlan = [];
  List<dynamic> reports = [];
  List<dynamic> documents = [];
  List<dynamic> notifications = [];
  List<dynamic> marketAlerts = [];
  Map<String, dynamic> notificationPreferences = {};
  Map<String, dynamic>? financialProfile;
  Map<String, dynamic>? clientProfile;
  Map<String, dynamic>? permissions;
  Map<String, dynamic>? suitability;
  String? error;
  bool loading = false;
  bool documentBusy = false;
  bool biometricAvailable = false;
  bool biometricEnabled = false;
  String? cachedAt;

  // Carrega preferências e dispara a leitura inicial dos dados protegidos.
  @override
  void initState() {
    super.initState();
    hideValues = widget.api.preferences.getBool(hideValuesKey) ?? false;
    _loadBiometricStatus();
    load();
  }

  Future<void> _loadBiometricStatus() async {
    final available = await deviceSupportsBiometrics();
    if (!mounted) return;
    setState(() {
      biometricAvailable = available;
      biometricEnabled =
          widget.api.preferences.getBool(biometricEnabledKey) ?? false;
    });
  }

  Future<void> _toggleBiometric() async {
    if (!biometricAvailable) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content:
                Text('Este dispositivo não possui biometria disponível.')));
      return;
    }
    if (biometricEnabled) {
      await widget.api.preferences.setBool(biometricEnabledKey, false);
      if (mounted) setState(() => biometricEnabled = false);
      return;
    }
    try {
      final authenticated = await LocalAuthentication().authenticate(
        localizedReason:
            'Confirme sua identidade para ativar o acesso biométrico no Talentum.',
        biometricOnly: true,
        persistAcrossBackgrounding: true,
      );
      if (!authenticated) return;
      await widget.api.preferences.setBool(biometricEnabledKey, true);
      if (mounted) {
        setState(() => biometricEnabled = true);
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Acesso biométrico ativado.')));
      }
    } catch (_) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Não foi possível ativar a biometria.')));
    }
  }

  // Busca o usuário e os módulos independentes em paralelo para reduzir a espera.
  Future<void> load() async {
    if (loading) return;
    if (mounted) setState(() => loading = true);
    try {
      if (mounted) setState(() => error = null);
      final currentUser = await widget.api.me();
      final role = currentUser['role']?.toString();
      if (role != 'client') {
        if (!mounted) return;
        setState(() {
          user = currentUser;
          error = role == 'admin'
              ? 'Esta conta é de administrador. Entre no aplicativo com uma conta de cliente ou use o painel Advisor.'
              : 'Esta conta é de consultor. Entre no aplicativo com uma conta de cliente ou use o painel Advisor.';
        });
        return;
      }
      final id = currentUser['id'] as int;
      final results = await Future.wait<dynamic>([
        widget.api.dashboard(id),
        widget.api.investmentPortfolio(id),
        widget.api.patrimony(id),
        widget.api.goals(id),
        widget.api.reports(id),
        widget.api.documents(id),
        widget.api.financialProfile(id),
        widget.api.profile(id),
        widget.api.permissions(id),
        widget.api.actionPlan(id),
        _loadNotifications(),
        _loadNotificationPreferences(),
      ]);
      if (!mounted) return;
      setState(() {
        user = currentUser;
        cachedAt = null;
        dashboard = results[0] as Map<String, dynamic>;
        investmentPortfolio = results[1] as Map<String, dynamic>;
        patrimony = results[2] as List<dynamic>;
        goals = results[3] as List<dynamic>;
        reports = results[4] as List<dynamic>;
        documents = results[5] as List<dynamic>;
        financialProfile = results[6] as Map<String, dynamic>?;
        clientProfile = results[7] as Map<String, dynamic>;
        permissions = results[8] as Map<String, dynamic>;
        actionPlan = results[9] as List<dynamic>;
        notifications = results[10] as List<dynamic>;
        notificationPreferences = results[11] as Map<String, dynamic>;
      });
      final alerts = await _loadMarketAlerts();
      if (mounted) setState(() => marketAlerts = alerts);
      final currentSuitability = await _loadSuitability();
      if (mounted) setState(() => suitability = currentSuitability);
      await _saveClientCache(currentUser, results, currentSuitability);
    } on ApiException catch (exception) {
      if (widget.api.accessToken == null) {
        await widget.api.secureStorage.delete(clientCacheKey);
        if (!mounted) return;
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(
              builder: (_) => LoginScreen(
                  api: widget.api,
                  message:
                      'Sua sessão expirou. Entre novamente para continuar.')),
          (_) => false,
        );
        return;
      }
      if ((exception.statusCode == 0 || exception.statusCode >= 500) &&
          await _restoreClientCache()) {
        if (!mounted) return;
        setState(() => error = null);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                content: Text(
                    'Sem conexão. Exibindo a última atualização disponível.')));
          }
        });
      } else if (mounted) {
        setState(() => error = exception.message);
      }
    } catch (_) {
      if (widget.api.accessToken != null && await _restoreClientCache()) {
        if (!mounted) return;
        setState(() => error = null);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                content: Text(
                    'Sem conexão. Exibindo a última atualização disponível.')));
          }
        });
      } else if (mounted) {
        setState(() => error = 'Não foi possível carregar seus dados.');
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<List<dynamic>> _loadNotifications() async {
    try {
      return await widget.api.notifications();
    } catch (_) {
      return <dynamic>[];
    }
  }

  Future<Map<String, dynamic>> _loadNotificationPreferences() async {
    try {
      return await widget.api.notificationPreferences();
    } catch (_) {
      return Map<String, dynamic>.from(defaultNotificationPreferences);
    }
  }

  Future<List<dynamic>> _loadMarketAlerts() async {
    try {
      return await widget.api.marketAlerts();
    } catch (_) {
      return <dynamic>[];
    }
  }

  Future<Map<String, dynamic>?> _loadSuitability() async {
    try {
      return await widget.api.suitability();
    } catch (_) {
      return null;
    }
  }

  Future<void> _saveClientCache(
      Map<String, dynamic> currentUser,
      List<dynamic> results,
      Map<String, dynamic>? currentSuitability) async {
    try {
      await widget.api.secureStorage.write(
          clientCacheKey,
          jsonEncode({
            'user': currentUser,
            'dashboard': results[0],
            'investment_portfolio': results[1],
            'patrimony': results[2],
            'goals': results[3],
            'reports': results[4],
            'documents': results[5],
            'financial_profile': results[6],
            'client_profile': results[7],
            'permissions': results[8],
            'action_plan': results[9],
            'notifications': results[10],
            'notification_preferences': results[11],
            'market_alerts': marketAlerts,
            'suitability': currentSuitability,
            'cached_at': DateTime.now().toIso8601String(),
          }));
    } catch (_) {
      // A falha no cache não pode impedir o uso dos dados online.
    }
  }

  Future<bool> _restoreClientCache() async {
    try {
      final raw = await widget.api.secureStorage.read(clientCacheKey);
      if (raw == null) return false;
      final payload = jsonDecode(raw) as Map<String, dynamic>;
      final cachedUser = Map<String, dynamic>.from(payload['user'] as Map);
      final cachedDashboard =
          Map<String, dynamic>.from(payload['dashboard'] as Map);
      if (cachedUser['role'] != 'client') return false;
      if (!mounted) return false;
      setState(() {
        user = cachedUser;
        dashboard = cachedDashboard;
        investmentPortfolio = Map<String, dynamic>.from(
            payload['investment_portfolio'] as Map? ?? {});
        patrimony = List<dynamic>.from(payload['patrimony'] as List? ?? []);
        goals = List<dynamic>.from(payload['goals'] as List? ?? []);
        reports = List<dynamic>.from(payload['reports'] as List? ?? []);
        documents = List<dynamic>.from(payload['documents'] as List? ?? []);
        financialProfile = payload['financial_profile'] == null
            ? null
            : Map<String, dynamic>.from(payload['financial_profile'] as Map);
        clientProfile =
            Map<String, dynamic>.from(payload['client_profile'] as Map);
        permissions = Map<String, dynamic>.from(payload['permissions'] as Map);
        actionPlan = List<dynamic>.from(payload['action_plan'] as List? ?? []);
        notifications =
            List<dynamic>.from(payload['notifications'] as List? ?? []);
        marketAlerts =
            List<dynamic>.from(payload['market_alerts'] as List? ?? []);
        notificationPreferences = Map<String, dynamic>.from(
            payload['notification_preferences'] as Map? ??
                defaultNotificationPreferences);
        suitability = payload['suitability'] == null
            ? null
            : Map<String, dynamic>.from(payload['suitability'] as Map);
        cachedAt = payload['cached_at']?.toString();
      });
      return true;
    } catch (_) {
      return false;
    }
  }

  // Formatações e rótulos abaixo isolam regras de apresentação dos widgets.
  String money(dynamic value) => 'R\$ ${formatBrazilianNumber(value)}';

  String alertPrice(Map<String, dynamic> alert) {
    final value = formatBrazilianNumber(alert['target_price']);
    return alert['market'] == 'global' ? 'US\$ $value' : 'R\$ $value';
  }

  String marketAlertConditionLabel(dynamic value) =>
      value == 'at_or_above' ? 'Atingir ou superar' : 'Atingir ou ficar abaixo';

  String marketAlertStatusLabel(dynamic value) => switch (value.toString()) {
        'active' => 'Ativo',
        'paused' => 'Pausado',
        'triggered' => 'Disparado',
        'cancelled' => 'Desativado',
        _ => 'Desconhecido',
      };

  String dateLabel(dynamic value) {
    final date = DateTime.tryParse(value?.toString() ?? '');
    if (date == null) return value?.toString() ?? '';
    final day = date.day.toString().padLeft(2, '0');
    final month = date.month.toString().padLeft(2, '0');
    return '$day/$month/${date.year}';
  }

  String dateTimeLabel(dynamic value) {
    final date = DateTime.tryParse(value?.toString() ?? '');
    if (date == null) return value?.toString() ?? '';
    final day = date.day.toString().padLeft(2, '0');
    final month = date.month.toString().padLeft(2, '0');
    final hour = date.hour.toString().padLeft(2, '0');
    final minute = date.minute.toString().padLeft(2, '0');
    return '$day/$month/${date.year} às $hour:$minute';
  }

  void showFormError(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  String privateMoney(dynamic value) =>
      hideValues ? 'R\$ ••••••' : money(value);

  String fileSizeLabel(dynamic value) {
    final bytes = int.tryParse(value?.toString() ?? '') ?? 0;
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  String goalStatusLabel(dynamic value) => switch (value.toString()) {
        'paused' => 'Pausada',
        'completed' => 'Concluída',
        _ => 'Ativa',
      };

  String actionStatusLabel(dynamic value) => switch (value.toString()) {
        'in_progress' => 'Em andamento',
        'completed' => 'Concluída',
        _ => 'Planejada',
      };

  String actionPriorityLabel(dynamic value) => switch (value.toString()) {
        'high' => 'Prioridade alta',
        'low' => 'Prioridade baixa',
        _ => 'Prioridade média',
      };

  Color actionPriorityColor(dynamic value) => switch (value.toString()) {
        'high' => Colors.deepOrange,
        'low' => Colors.teal,
        _ => Colors.amber.shade800,
      };

  String? goalTitleForAction(dynamic goalId) {
    if (goalId == null) return null;
    for (final goal in goals) {
      if (goal['id'] == goalId) return goal['title']?.toString();
    }
    return null;
  }

  bool isOverdueAction(Map<String, dynamic> action) {
    final dueDate = DateTime.tryParse(action['due_date']?.toString() ?? '');
    if (dueDate == null || action['status'] == 'completed') return false;
    final endOfDueDay =
        DateTime(dueDate.year, dueDate.month, dueDate.day, 23, 59, 59);
    return endOfDueDay.isBefore(DateTime.now());
  }

  // A ordenação mantém pendências e vencimentos mais importantes no topo.
  List<dynamic> orderedActionPlan() {
    final actions = List<dynamic>.from(actionPlan);
    const priorityOrder = {'high': 0, 'medium': 1, 'low': 2};
    actions.sort((leftValue, rightValue) {
      final left = Map<String, dynamic>.from(leftValue as Map);
      final right = Map<String, dynamic>.from(rightValue as Map);
      final leftOverdue = isOverdueAction(left) ? 1 : 0;
      final rightOverdue = isOverdueAction(right) ? 1 : 0;
      if (leftOverdue != rightOverdue)
        return rightOverdue.compareTo(leftOverdue);
      final leftCompleted = left['status'] == 'completed' ? 1 : 0;
      final rightCompleted = right['status'] == 'completed' ? 1 : 0;
      if (leftCompleted != rightCompleted)
        return leftCompleted.compareTo(rightCompleted);
      final leftPriority = priorityOrder[left['priority']?.toString()] ?? 3;
      final rightPriority = priorityOrder[right['priority']?.toString()] ?? 3;
      if (leftPriority != rightPriority)
        return leftPriority.compareTo(rightPriority);
      final leftDue = left['due_date']?.toString();
      final rightDue = right['due_date']?.toString();
      if (leftDue != null && rightDue != null && leftDue != rightDue)
        return leftDue.compareTo(rightDue);
      if (leftDue != null && rightDue == null) return -1;
      if (leftDue == null && rightDue != null) return 1;
      return (left['title']?.toString() ?? '')
          .compareTo(right['title']?.toString() ?? '');
    });
    return actions;
  }

  bool isOverdueGoal(Map<String, dynamic> goal) {
    final targetDate = DateTime.tryParse(goal['target_date']?.toString() ?? '');
    if (targetDate == null || goal['status'] == 'completed') return false;
    final endOfTargetDay =
        DateTime(targetDate.year, targetDate.month, targetDate.day, 23, 59, 59);
    return endOfTargetDay.isBefore(DateTime.now());
  }

  List<dynamic> orderedGoals(Iterable<dynamic> source) {
    final items = source.toList();
    items.sort((leftValue, rightValue) {
      final left = Map<String, dynamic>.from(leftValue as Map);
      final right = Map<String, dynamic>.from(rightValue as Map);
      final leftOverdue = isOverdueGoal(left) ? 1 : 0;
      final rightOverdue = isOverdueGoal(right) ? 1 : 0;
      if (leftOverdue != rightOverdue)
        return rightOverdue.compareTo(leftOverdue);
      final leftCompleted = left['status'] == 'completed' ? 1 : 0;
      final rightCompleted = right['status'] == 'completed' ? 1 : 0;
      if (leftCompleted != rightCompleted)
        return leftCompleted.compareTo(rightCompleted);
      final leftDate = left['target_date']?.toString();
      final rightDate = right['target_date']?.toString();
      if (leftDate != null && rightDate != null && leftDate != rightDate)
        return leftDate.compareTo(rightDate);
      if (leftDate != null && rightDate == null) return -1;
      if (leftDate == null && rightDate != null) return 1;
      return (left['title']?.toString() ?? '')
          .compareTo(right['title']?.toString() ?? '');
    });
    return items;
  }

  IconData actionStatusIcon(dynamic value) => switch (value.toString()) {
        'in_progress' => Icons.timelapse_outlined,
        'completed' => Icons.check_circle_outline,
        _ => Icons.radio_button_unchecked,
      };

  // Alterna a ocultação de valores sensíveis apenas na interface local.
  Future<void> toggleValueVisibility() async {
    setState(() => hideValues = !hideValues);
    await widget.api.preferences.setBool(hideValuesKey, hideValues);
  }

  // Constrói a navegação principal e escolhe a aba atualmente selecionada.
  @override
  Widget build(BuildContext context) {
    final labels = [
      'Início',
      'Patrimônio',
      'Metas',
      'Documentos',
      'Relatórios',
      'Perfil'
    ];
    return Scaffold(
      appBar: AppBar(
        title: const Text('talentum ✦'),
        actions: [
          IconButton(
            tooltip: hideValues ? 'Exibir valores' : 'Ocultar valores',
            onPressed: toggleValueVisibility,
            icon: Icon(hideValues
                ? Icons.visibility_off_outlined
                : Icons.visibility_outlined),
          ),
          IconButton(
            tooltip: 'Alertas',
            onPressed: openNotificationHistory,
            icon: Badge(
              isLabelVisible: notifications
                  .any((notification) => notification['read_at'] == null),
              label: Text(
                  '${notifications.where((notification) => notification['read_at'] == null).length}'),
              child: const Icon(Icons.notifications_outlined),
            ),
          ),
          IconButton(
              onPressed: loading ? null : load,
              icon: const Icon(Icons.refresh)),
        ],
      ),
      body: error != null
          ? Center(
              child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Text(error!, textAlign: TextAlign.center),
                    const SizedBox(height: 14),
                    Wrap(
                        alignment: WrapAlignment.center,
                        spacing: 10,
                        children: [
                          OutlinedButton(
                              onPressed: signOut,
                              child: const Text('Sair da conta')),
                          FilledButton(
                              onPressed: load,
                              child: const Text('Tentar novamente'))
                        ])
                  ])))
          : user == null
              ? const Center(child: CircularProgressIndicator())
              : RefreshIndicator(
                  onRefresh: load,
                  child: ListView(padding: const EdgeInsets.all(20), children: [
                    if (loading) const LinearProgressIndicator(),
                    Text(labels[tab],
                        style: Theme.of(context).textTheme.headlineMedium),
                    const SizedBox(height: 18),
                    _content()
                  ])),
      bottomNavigationBar: NavigationBar(
          selectedIndex: tab,
          onDestinationSelected: (value) => setState(() => tab = value),
          destinations: const [
            NavigationDestination(
                icon: Icon(Icons.home_outlined),
                selectedIcon: Icon(Icons.home),
                label: 'Início'),
            NavigationDestination(
                icon: Icon(Icons.pie_chart_outline),
                selectedIcon: Icon(Icons.pie_chart),
                label: 'Patrimônio'),
            NavigationDestination(
                icon: Icon(Icons.flag_outlined),
                selectedIcon: Icon(Icons.flag),
                label: 'Metas'),
            NavigationDestination(
                icon: Icon(Icons.folder_outlined),
                selectedIcon: Icon(Icons.folder),
                label: 'Documentos'),
            NavigationDestination(
                icon: Icon(Icons.description_outlined),
                selectedIcon: Icon(Icons.description),
                label: 'Relatórios'),
            NavigationDestination(
                icon: Icon(Icons.person_outline),
                selectedIcon: Icon(Icons.person),
                label: 'Perfil')
          ]),
    );
  }

  // Seleciona o conteúdo da aba sem duplicar a estrutura do scaffold principal.
  Widget _content() {
    if (tab == 1) return _patrimonyView();
    if (tab == 2) return _goalsView();
    if (tab == 3) return _documentsView();
    if (tab == 4) return _reportsView();
    if (tab == 5) return _profileView();
    final data = dashboard!;
    final categories =
        List<dynamic>.from(data['patrimony_by_category'] as List? ?? []);
    final monthlyIncome =
        double.tryParse(data['monthly_income']?.toString() ?? '') ?? 0;
    final monthlyExpenses =
        double.tryParse(data['monthly_expenses']?.toString() ?? '') ?? 0;
    final monthlyBalance = monthlyIncome - monthlyExpenses;
    final orderedActions = orderedActionPlan();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (cachedAt != null) ...[
        Card(
          color: Colors.amber.shade50,
          child: ListTile(
            leading: const Icon(Icons.cloud_off_outlined),
            title: const Text('Visualização offline'),
            subtitle: Text('Última atualização: ${dateTimeLabel(cachedAt)}'),
          ),
        ),
        const SizedBox(height: 12),
      ],
      Text('Olá, ${(user!['name'] as String).split(' ').first} ✦',
          style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 16),
      Card(
          child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('PATRIMÔNIO TOTAL'),
                    const SizedBox(height: 6),
                    Text(privateMoney(data['patrimony_total']),
                        style: Theme.of(context)
                            .textTheme
                            .headlineMedium
                            ?.copyWith(fontWeight: FontWeight.w800)),
                    const SizedBox(height: 8),
                    const Text('Acompanhe sua evolução com clareza.')
                  ]))),
      const SizedBox(height: 16),
      Card(
          child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('FLUXO MENSAL'),
                    const SizedBox(height: 12),
                    _summaryRow(
                        'Renda', privateMoney(monthlyIncome), Colors.green),
                    _summaryRow('Despesas', privateMoney(monthlyExpenses),
                        Colors.orange),
                    const Divider(height: 22),
                    _summaryRow('Saldo estimado', privateMoney(monthlyBalance),
                        monthlyBalance >= 0 ? Colors.teal : Colors.red)
                  ]))),
      const SizedBox(height: 16),
      Card(
          child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('ACOMPANHAMENTO'),
                    const SizedBox(height: 12),
                    _summaryRow(
                        'Ações pendentes',
                        '${data['action_pending'] ?? actionPlan.where((action) => action['status'] != 'completed').length}',
                        Colors.indigo),
                    _summaryRow('Ações atrasadas',
                        '${data['action_overdue'] ?? 0}', Colors.red)
                  ]))),
      if (notifications
          .any((notification) => notification['read_at'] == null)) ...[
        const SizedBox(height: 16),
        _notificationsCard(),
      ],
      const SizedBox(height: 16),
      _marketAlertsCard(),
      const SizedBox(height: 16),
      _suitabilityCard(),
      const SizedBox(height: 16),
      const Text('Distribuição'),
      const SizedBox(height: 8),
      ...categories.map((item) => ListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(item['category'].toString()),
          subtitle: LinearProgressIndicator(
              value:
                  (double.tryParse(item['percentage'].toString()) ?? 0) / 100),
          trailing: Text(privateMoney(item['total'])))),
      const SizedBox(height: 12),
      const Text('Suas metas'),
      ...List<dynamic>.from(data['goals'] as List? ?? []).map((goal) =>
          ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(goal['title'].toString()),
              subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    LinearProgressIndicator(
                        value:
                            (double.tryParse(goal['percentage'].toString()) ??
                                    0) /
                                100),
                    if (goal['target_date'] != null)
                      Text(
                          'Prazo: ${dateLabel(goal['target_date'])}${isOverdueGoal(Map<String, dynamic>.from(goal)) ? ' · Prazo vencido' : ''}',
                          style: TextStyle(
                              color:
                                  isOverdueGoal(Map<String, dynamic>.from(goal))
                                      ? Colors.red
                                      : null))
                  ]),
              trailing: Text('${goal['percentage']}%'))),
      const SizedBox(height: 12),
      const Text('Plano de ação'),
      const SizedBox(height: 8),
      if (actionPlan.isEmpty)
        const Text('Nenhuma ação definida pelo seu Advisor.'),
      ...orderedActions.take(3).map((action) => ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(actionStatusIcon(action['status']),
              color: isOverdueAction(Map<String, dynamic>.from(action))
                  ? Colors.red
                  : actionPriorityColor(action['priority'])),
          title: Text(action['title'].toString()),
          subtitle: Text(
              '${actionStatusLabel(action['status'])} · ${actionPriorityLabel(action['priority'])}${action['due_date'] != null ? ' · até ${dateLabel(action['due_date'])}' : ''}${isOverdueAction(Map<String, dynamic>.from(action)) ? ' · Atrasada' : ''}'))),
      if (actionPlan.isNotEmpty)
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: openActionPlan,
            icon: const Icon(Icons.arrow_forward),
            label: const Text('Ver detalhes do plano'),
          ),
        ),
    ]);
  }

  // Cartão de notificações com filtros, leitura individual e leitura em massa.
  Widget _notificationsCard() {
    final unread = notifications
        .where((notification) =>
            notification['read_at'] == null &&
            (notificationFilter == 'all' ||
                notification['kind'] == notificationFilter))
        .take(3)
        .toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text('Alertas', style: Theme.of(context).textTheme.titleMedium),
              Text(
                  '${notifications.where((notification) => notification['read_at'] == null).length} não lidos',
                  style: const TextStyle(
                      color: Colors.deepOrange, fontWeight: FontWeight.w700))
            ]),
            const SizedBox(height: 8),
            DropdownButton<String>(
              value: notificationFilter,
              isExpanded: true,
              items: const [
                DropdownMenuItem(value: 'all', child: Text('Todos os alertas')),
                DropdownMenuItem(
                    value: 'action_overdue', child: Text('Ações atrasadas')),
                DropdownMenuItem(
                    value: 'action_due_soon',
                    child: Text('Ações próximas do prazo')),
                DropdownMenuItem(
                    value: 'goal_overdue', child: Text('Metas vencidas')),
                DropdownMenuItem(
                    value: 'goal_due_soon',
                    child: Text('Metas próximas do prazo')),
                DropdownMenuItem(
                    value: 'document_uploaded',
                    child: Text('Documentos novos')),
                DropdownMenuItem(
                    value: 'document_review_due',
                    child: Text('Atualização anual de documentos')),
                DropdownMenuItem(
                    value: 'market_price_alert',
                    child: Text('Alertas de preço')),
              ],
              onChanged: (value) =>
                  setState(() => notificationFilter = value ?? 'all'),
            ),
            if (unread.isEmpty) const Text('Nenhum alerta neste filtro.'),
            ...unread.map((notification) => ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.notifications_active_outlined,
                    color: Colors.deepOrange),
                title: Text(notification['title'].toString()),
                subtitle: Text(
                    '${notification['message']} · ${dateTimeLabel(notification['created_at'])}'),
                onTap: () => openNotification(notification))),
            Wrap(spacing: 8, children: [
              TextButton(
                  onPressed: openNotificationPreferences,
                  child: const Text('Preferências')),
              TextButton(
                  onPressed: markAllNotificationsRead,
                  child: const Text('Marcar todas como lidas'))
            ]),
          ],
        ),
      ),
    );
  }

  // Lista de alertas de preço e ações para editar, pausar ou cancelar cada alerta.
  Widget _marketAlertsCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text('Alertas de preço',
                  style: Theme.of(context).textTheme.titleMedium),
              TextButton.icon(
                  onPressed: openMarketAlertDialog,
                  icon: const Icon(Icons.add_alert_outlined),
                  label: const Text('Novo'))
            ]),
            const SizedBox(height: 6),
            if (marketAlerts.isEmpty)
              const Text(
                  'Crie um alerta para receber uma notificação quando um ativo atingir o preço escolhido.'),
            ...marketAlerts.take(3).map(
                (alert) => _marketAlertTile(Map<String, dynamic>.from(alert))),
            if (marketAlerts.length > 3)
              TextButton(
                  onPressed: openMarketAlertsHistory,
                  child: Text('Ver todos (${marketAlerts.length})')),
          ],
        ),
      ),
    );
  }

  // Apresenta o estado da avaliação e os percentuais da carteira modelo.
  Widget _suitabilityCard() {
    final assessment = suitability;
    if (assessment == null) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Carteira sugerida',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              const Text(
                  'Responda algumas perguntas para receber uma sugestão de alocação por objetivo e perfil de risco.'),
              const SizedBox(height: 14),
              FilledButton.icon(
                onPressed: openSuitabilityQuestionnaire,
                icon: const Icon(Icons.assignment_outlined),
                label: const Text('Responder questionário'),
              ),
            ],
          ),
        ),
      );
    }

    final recommendation =
        Map<String, dynamic>.from(assessment['recommendation'] as Map? ?? {});
    final allocations = List<dynamic>.from(
        recommendation['allocations'] as List? ?? <dynamic>[]);
    final status = assessment['status']?.toString() ?? 'pending_review';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text('Sua carteira sugerida',
                      style: Theme.of(context).textTheme.titleMedium),
                ),
                IconButton(
                  tooltip: 'Refazer questionário',
                  onPressed: openSuitabilityQuestionnaire,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            Text(
              '${assessment['objective_label']} · perfil ${assessment['risk_profile_label']}',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            Text('Status: ${suitabilityStatusLabel(status)}'),
            const SizedBox(height: 8),
            Text(assessment['risk_profile_description']?.toString() ?? ''),
            if (recommendation['summary'] != null) ...[
              const SizedBox(height: 8),
              Text(recommendation['summary'].toString()),
            ],
            const Divider(height: 24),
            const Text('Alocação de referência',
                style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            ...allocations.map((item) {
              final allocation = Map<String, dynamic>.from(item as Map);
              final percentage =
                  int.tryParse(allocation['percentage']?.toString() ?? '') ?? 0;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(child: Text(allocation['label'].toString())),
                        Text('$percentage%',
                            style:
                                const TextStyle(fontWeight: FontWeight.w700)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    LinearProgressIndicator(value: percentage / 100),
                  ],
                ),
              );
            }),
            const SizedBox(height: 8),
            const Text(
              'Esta é uma carteira modelo por classes de ativos. A validação do Advisor é necessária antes de qualquer decisão.',
              style: TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: openSuitabilityQuestionnaire,
              icon: const Icon(Icons.edit_outlined),
              label: const Text('Atualizar respostas'),
            ),
          ],
        ),
      ),
    );
  }

  String suitabilityStatusLabel(dynamic value) => switch (value.toString()) {
        'approved' => 'Aprovada pelo Advisor',
        'rejected' => 'Aguardando nova validação',
        'superseded' => 'Substituída por uma avaliação mais recente',
        _ => 'Aguardando validação do Advisor',
      };

  // Abre o formulário completo e envia as respostas para a avaliação versionada.
  Future<void> openSuitabilityQuestionnaire() async {
    Map<String, dynamic> definition;
    try {
      definition = await widget.api.suitabilityQuestionnaire();
    } on ApiException catch (exception) {
      if (mounted) showFormError(exception.message);
      return;
    }

    final objectives = List<dynamic>.from(
        definition['objectives'] as List? ?? <dynamic>[]);
    final questions = List<dynamic>.from(
        definition['questions'] as List? ?? <dynamic>[]);
    if (objectives.isEmpty || questions.isEmpty) {
      if (mounted) showFormError('O questionário ainda não está disponível.');
      return;
    }
    var objective = suitability?['objective']?.toString() ??
        Map<String, dynamic>.from(objectives.first as Map)['value'].toString();
    final answers = <String, String>{};
    final savedAnswers = suitability?['answers'];
    if (savedAnswers is Map) {
      savedAnswers.forEach((key, value) {
        answers[key.toString()] = value.toString();
      });
    }

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) {
        var submitting = false;
        return StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: const Text('Perfil e carteira sugerida'),
            content: SizedBox(
              width: 560,
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      'Escolha seu objetivo principal e responda com base na sua situação atual. Não existem respostas certas ou erradas.',
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<String>(
                      initialValue: objective,
                      decoration:
                          const InputDecoration(labelText: 'Objetivo principal'),
                      items: objectives
                          .map((item) {
                            final value =
                                Map<String, dynamic>.from(item as Map);
                            return DropdownMenuItem<String>(
                              value: value['value'].toString(),
                              child: Text(value['label'].toString()),
                            );
                          })
                          .toList(),
                      onChanged: submitting
                          ? null
                          : (value) => setDialogState(
                              () => objective = value ?? objective),
                    ),
                    const SizedBox(height: 16),
                    ...questions.map((item) {
                      final question = Map<String, dynamic>.from(item as Map);
                      final key = question['key'].toString();
                      final options = List<dynamic>.from(
                          question['options'] as List? ?? <dynamic>[]);
                      final optionValues = options
                          .map((option) =>
                              Map<String, dynamic>.from(option as Map)['value'])
                          .map((value) => value.toString())
                          .toSet();
                      final selected = optionValues.contains(answers[key])
                          ? answers[key]
                          : null;
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 14),
                        child: DropdownButtonFormField<String>(
                          initialValue: selected,
                          decoration: InputDecoration(
                            labelText: question['label'].toString(),
                            helperText: question['description']?.toString(),
                          ),
                          items: options
                              .map((option) {
                                final value =
                                    Map<String, dynamic>.from(option as Map);
                                return DropdownMenuItem<String>(
                                  value: value['value'].toString(),
                                  child: Text(value['label'].toString()),
                                );
                              })
                              .toList(),
                          onChanged: submitting
                              ? null
                              : (value) => setDialogState(() {
                                    if (value == null) {
                                      answers.remove(key);
                                    } else {
                                      answers[key] = value;
                                    }
                                  }),
                        ),
                      );
                    }),
                    const Text(
                      'A carteira exibida é uma referência por classe de ativo e ficará pendente de validação do Advisor.',
                      style: TextStyle(fontSize: 12),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: submitting ? null : () => Navigator.pop(dialogContext),
                child: const Text('Cancelar'),
              ),
              FilledButton(
                onPressed: submitting || answers.length != questions.length
                    ? null
                    : () async {
                        setDialogState(() => submitting = true);
                        try {
                          final submitted = await widget.api.submitSuitability(
                            objective: objective,
                            answers: answers,
                          );
                          if (!dialogContext.mounted) return;
                          Navigator.pop(dialogContext, submitted);
                        } on ApiException catch (exception) {
                          if (!dialogContext.mounted) return;
                          setDialogState(() => submitting = false);
                          ScaffoldMessenger.of(dialogContext).showSnackBar(
                              SnackBar(content: Text(exception.message)));
                        }
                      },
                child: Text(submitting ? 'Calculando...' : 'Gerar sugestão'),
              ),
            ],
          ),
        );
      },
    );

    if (result == null || !mounted) return;
    setState(() => suitability = result);
    await widget.api.secureStorage.delete(clientCacheKey);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Questionário salvo e carteira sugerida gerada.')));
    }
  }

  Future<void> cancelMarketAlert(Map<String, dynamic> alert) async {
    try {
      await widget.api.cancelMarketAlert(alert['id'] as int);
      await load();
    } on ApiException catch (exception) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
    }
  }

  Widget _marketAlertTile(Map<String, dynamic> alert) {
    final status = alert['status']?.toString();
    final editable = status != 'cancelled';
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        status == 'triggered'
            ? Icons.notifications_active
            : Icons.trending_up_outlined,
        color: status == 'triggered' ? Colors.deepOrange : Colors.indigo,
      ),
      title: Text('${alert['symbol']} · ${alertPrice(alert)}'),
      subtitle: Text(
          '${marketAlertConditionLabel(alert['condition'])} · ${marketAlertStatusLabel(status)}'),
      onTap: editable ? () => openMarketAlertDialog(alert: alert) : null,
      trailing: Wrap(
        spacing: 0,
        children: [
          if (editable)
            IconButton(
              tooltip: 'Editar alerta',
              onPressed: () => openMarketAlertDialog(alert: alert),
              icon: const Icon(Icons.edit_outlined),
            ),
          if (status == 'active' || status == 'paused')
            IconButton(
              tooltip: 'Desativar alerta',
              onPressed: () => cancelMarketAlert(alert),
              icon: const Icon(Icons.close),
            ),
        ],
      ),
    );
  }

  Future<void> openMarketAlertsHistory() async {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Alertas de preço'),
        content: SizedBox(
          width: 520,
          child: marketAlerts.isEmpty
              ? const Text('Nenhum alerta cadastrado.')
              : ListView(
                  shrinkWrap: true,
                  children: marketAlerts
                      .map((alert) =>
                          _marketAlertTile(Map<String, dynamic>.from(alert)))
                      .toList(),
                ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Fechar'),
          ),
        ],
      ),
    );
  }

  Future<void> openMarketAlertDialog({Map<String, dynamic>? alert}) async {
    final editing = alert != null;
    final symbol = TextEditingController(
        text: editing ? alert['symbol']?.toString() ?? '' : '');
    final target = TextEditingController(
        text: editing ? formatBrazilianNumber(alert['target_price']) : '');
    var market = editing ? alert['market']?.toString() ?? 'br' : 'br';
    var condition = editing
        ? alert['condition']?.toString() ?? 'at_or_below'
        : 'at_or_below';
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title:
              Text(editing ? 'Editar alerta de preço' : 'Novo alerta de preço'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                    controller: symbol,
                    readOnly: editing,
                    textCapitalization: TextCapitalization.characters,
                    decoration: const InputDecoration(
                        labelText: 'Ticker ou símbolo',
                        hintText: 'PETR4 ou AAPL')),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: market,
                  onChanged: editing
                      ? null
                      : (value) => setDialogState(() => market = value ?? 'br'),
                  decoration: const InputDecoration(labelText: 'Mercado'),
                  items: const [
                    DropdownMenuItem(value: 'br', child: Text('Brasil — B3')),
                    DropdownMenuItem(value: 'global', child: Text('Exterior'))
                  ],
                ),
                const SizedBox(height: 12),
                TextField(
                    controller: target,
                    keyboardType:
                        const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(
                        labelText: 'Preço-alvo', hintText: 'Ex.: 32,50')),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                    initialValue: condition,
                    decoration: const InputDecoration(labelText: 'Condição'),
                    items: const [
                      DropdownMenuItem(
                          value: 'at_or_below',
                          child: Text('Atingir ou ficar abaixo')),
                      DropdownMenuItem(
                          value: 'at_or_above',
                          child: Text('Atingir ou superar'))
                    ],
                    onChanged: (value) => setDialogState(
                        () => condition = value ?? 'at_or_below')),
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Cancelar')),
            FilledButton(
              onPressed: () async {
                final parsedTarget = parseBrazilianNumber(target.text);
                if (symbol.text.trim().isEmpty ||
                    parsedTarget == null ||
                    parsedTarget <= 0) {
                  ScaffoldMessenger.of(dialogContext).showSnackBar(
                      const SnackBar(
                          content:
                              Text('Informe o ativo e um preço-alvo válido.')));
                  return;
                }
                try {
                  if (editing) {
                    await widget.api.updateMarketAlert(
                      alert['id'] as int,
                      targetPrice: parsedTarget,
                      condition: condition,
                    );
                  } else {
                    await widget.api.createMarketAlert(
                        symbol: symbol.text.trim().toUpperCase(),
                        market: market,
                        targetPrice: parsedTarget,
                        condition: condition);
                  }
                  if (!mounted || !dialogContext.mounted) return;
                  Navigator.pop(dialogContext);
                  final messenger = ScaffoldMessenger.of(context);
                  await load();
                  if (mounted)
                    messenger.showSnackBar(const SnackBar(
                        content: Text('Alerta salvo com sucesso.')));
                } on ApiException catch (exception) {
                  if (dialogContext.mounted)
                    ScaffoldMessenger.of(dialogContext).showSnackBar(
                        SnackBar(content: Text(exception.message)));
                }
              },
              child: Text(editing ? 'Salvar alterações' : 'Criar alerta'),
            ),
          ],
        ),
      ),
    );
    symbol.dispose();
    target.dispose();
  }

  Future<void> openNotification(Map<String, dynamic> notification) async {
    try {
      await widget.api.markNotificationRead(notification['id'] as int);
      await load();
      if (!mounted) return;
      final kind = notification['kind']?.toString();
      if (kind == 'action_overdue' || kind == 'action_due_soon') {
        setState(() => tab = 0);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) openActionPlan();
        });
      } else if (kind == 'goal_overdue' || kind == 'goal_due_soon') {
        setState(() => tab = 2);
      } else if (kind == 'document_uploaded') {
        setState(() => tab = 3);
      } else if (kind == 'document_review_due') {
        setState(() => tab = 3);
      }
    } on ApiException catch (exception) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
    }
  }

  Future<void> markAllNotificationsRead() async {
    try {
      await widget.api.markAllNotificationsRead();
      await load();
    } on ApiException catch (exception) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
    }
  }

  Future<void> openNotificationPreferences() async {
    final values = <String, bool>{
      'action_overdue': notificationPreferences['action_overdue'] == true,
      'action_due_soon': notificationPreferences['action_due_soon'] == true,
      'goal_overdue': notificationPreferences['goal_overdue'] == true,
      'goal_due_soon': notificationPreferences['goal_due_soon'] == true,
      'document_uploaded': notificationPreferences['document_uploaded'] == true,
      'document_review_due':
          notificationPreferences['document_review_due'] == true,
      'market_price_alert':
          notificationPreferences['market_price_alert'] == true,
    };
    final labels = <String, String>{
      'action_overdue': 'Ações atrasadas',
      'action_due_soon': 'Ações próximas do prazo',
      'goal_overdue': 'Metas vencidas',
      'goal_due_soon': 'Metas próximas do prazo',
      'document_uploaded': 'Documentos novos',
      'document_review_due': 'Atualização anual de documentos',
      'market_price_alert': 'Alertas de preço',
    };
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Preferências de alertas'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: labels.entries
                  .map((entry) => SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(entry.value),
                      value: values[entry.key]!,
                      onChanged: (value) =>
                          setDialogState(() => values[entry.key] = value)))
                  .toList(),
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Cancelar')),
            FilledButton(
              onPressed: () async {
                try {
                  final updated =
                      await widget.api.updateNotificationPreferences(values);
                  if (!mounted || !dialogContext.mounted) return;
                  setState(() => notificationPreferences = updated);
                  ScaffoldMessenger.of(dialogContext).showSnackBar(
                      const SnackBar(content: Text('Preferências salvas.')));
                  Navigator.pop(dialogContext);
                } on ApiException catch (exception) {
                  if (dialogContext.mounted)
                    ScaffoldMessenger.of(dialogContext).showSnackBar(
                        SnackBar(content: Text(exception.message)));
                }
              },
              child: const Text('Salvar'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> openNotificationHistory() async {
    var selectedFilter = notificationFilter;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) {
          final visible = notifications
              .where((notification) =>
                  selectedFilter == 'all' ||
                  notification['kind'] == selectedFilter)
              .toList();
          return AlertDialog(
            title: const Text('Histórico de alertas'),
            content: SizedBox(
              width: 520,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    DropdownButton<String>(
                      value: selectedFilter,
                      isExpanded: true,
                      items: const [
                        DropdownMenuItem(
                            value: 'all', child: Text('Todos os alertas')),
                        DropdownMenuItem(
                            value: 'action_overdue',
                            child: Text('Ações atrasadas')),
                        DropdownMenuItem(
                            value: 'action_due_soon',
                            child: Text('Ações próximas do prazo')),
                        DropdownMenuItem(
                            value: 'goal_overdue',
                            child: Text('Metas vencidas')),
                        DropdownMenuItem(
                            value: 'goal_due_soon',
                            child: Text('Metas próximas do prazo')),
                        DropdownMenuItem(
                            value: 'document_uploaded',
                            child: Text('Documentos novos')),
                        DropdownMenuItem(
                            value: 'document_review_due',
                            child: Text('Atualização anual de documentos')),
                        DropdownMenuItem(
                            value: 'market_price_alert',
                            child: Text('Alertas de preço')),
                      ],
                      onChanged: (value) =>
                          setDialogState(() => selectedFilter = value ?? 'all'),
                    ),
                    if (visible.isEmpty)
                      const Padding(
                          padding: EdgeInsets.only(top: 12),
                          child: Text('Nenhum alerta encontrado.')),
                    ...visible.map((notification) => ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: Icon(
                              notification['read_at'] == null
                                  ? Icons.notifications_active_outlined
                                  : Icons.notifications_none_outlined,
                              color: notification['read_at'] == null
                                  ? Colors.deepOrange
                                  : null),
                          title: Text(notification['title'].toString()),
                          subtitle: Text(
                              '${notification['message']}\n${dateTimeLabel(notification['created_at'])}'),
                          onTap: () {
                            Navigator.pop(dialogContext);
                            openNotification(
                                Map<String, dynamic>.from(notification));
                          },
                        )),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                  onPressed: openNotificationPreferences,
                  child: const Text('Preferências')),
              TextButton(
                  onPressed: markAllNotificationsRead,
                  child: const Text('Marcar todas como lidas')),
              TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child: const Text('Fechar')),
            ],
          );
        },
      ),
    );
    if (mounted) setState(() => notificationFilter = selectedFilter);
  }

  Future<void> openActionPlan() async {
    final orderedActions = orderedActionPlan();
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => SafeArea(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxHeight: 620),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Plano de ação',
                        style: Theme.of(context).textTheme.titleLarge),
                    IconButton(
                        onPressed: () => Navigator.pop(sheetContext),
                        icon: const Icon(Icons.close)),
                  ],
                ),
                const SizedBox(height: 8),
                Expanded(
                  child: ListView.separated(
                    itemCount: orderedActions.length,
                    separatorBuilder: (_, __) => const Divider(),
                    itemBuilder: (_, index) {
                      final action = orderedActions[index];
                      final overdue =
                          isOverdueAction(Map<String, dynamic>.from(action));
                      return ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(actionStatusIcon(action['status']),
                            color: overdue
                                ? Colors.red
                                : actionPriorityColor(action['priority'])),
                        title: Text(action['title'].toString()),
                        subtitle: Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Text(
                              '${actionStatusLabel(action['status'])} · ${actionPriorityLabel(action['priority'])}${action['due_date'] != null ? ' · até ${dateLabel(action['due_date'])}' : ''}${goalTitleForAction(action['goal_id']) != null ? ' · meta: ${goalTitleForAction(action['goal_id'])}' : ''}${overdue ? ' · Atrasada' : ''}${action['description'] != null && action['description'].toString().isNotEmpty ? '\n${action['description']}' : ''}'),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _summaryRow(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label),
          Text(value,
              style: TextStyle(fontWeight: FontWeight.w700, color: color)),
        ],
      ),
    );
  }

  String investmentMoney(dynamic value, dynamic currency) {
    if (hideValues) return '••••••';
    final prefix = currency?.toString() == 'USD' ? 'US\$' : 'R\$';
    return '$prefix ${formatBrazilianNumber(value)}';
  }

  // Exibe a carteira consolidada por posição, moeda e resultado.
  Widget _investmentPortfolioView() {
    final portfolio = investmentPortfolio ?? <String, dynamic>{};
    final positions = List<dynamic>.from(portfolio['positions'] as List? ?? []);
    final allocations =
        List<dynamic>.from(portfolio['allocations'] as List? ?? []);
    final pnl = double.tryParse(portfolio['pnl_total']?.toString() ?? '') ?? 0;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Carteira de investimentos',
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 10),
            _summaryRow(
                'Valor investido',
                portfolio['mixed_currency'] == true
                    ? 'Ver por moeda'
                    : investmentMoney(portfolio['invested_total'],
                        portfolio['total_currency']),
                Colors.blueGrey),
            _summaryRow(
                'Valor atualizado',
                portfolio['mixed_currency'] == true
                    ? 'Ver por moeda'
                    : investmentMoney(portfolio['current_total'],
                        portfolio['total_currency']),
                Colors.teal),
            _summaryRow(
                'Resultado',
                portfolio['mixed_currency'] == true
                    ? 'Ver por moeda'
                    : '${pnl >= 0 ? '+' : ''}${investmentMoney(portfolio['pnl_total'], portfolio['total_currency'])}',
                pnl >= 0 ? Colors.green : Colors.red),
            if ((portfolio['unpriced_position_count'] as num? ?? 0) > 0)
              Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                      '${portfolio['unpriced_position_count']} posição(ões) sem cotação atual.',
                      style: Theme.of(context).textTheme.bodySmall)),
            if (allocations.isNotEmpty) ...[
              const Divider(height: 24),
              const Text('Alocação por mercado',
                  style: TextStyle(fontWeight: FontWeight.w700)),
              ...allocations.map((item) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  title: Text(item['label'].toString()),
                  subtitle: LinearProgressIndicator(
                      value: (double.tryParse(
                                  item['percentage']?.toString() ?? '') ??
                              0) /
                          100),
                  trailing: Text(
                      '${double.tryParse(item['percentage']?.toString() ?? '')?.toStringAsFixed(1) ?? '0,0'}%'))),
            ],
            if ((portfolio['currency_totals'] as List? ?? []).isNotEmpty) ...[
              const Divider(height: 24),
              const Text('Totais por moeda',
                  style: TextStyle(fontWeight: FontWeight.w700)),
              ...List<dynamic>.from(portfolio['currency_totals'] as List).map(
                  (item) => ListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      title: Text(item['currency'].toString()),
                      subtitle: Text(
                          'Investido: ${investmentMoney(item['invested_total'], item['currency'])} · Atualizado: ${investmentMoney(item['current_total'], item['currency'])}'),
                      trailing: Text(
                          '${double.tryParse(item['pnl_percent']?.toString() ?? '')?.toStringAsFixed(1) ?? '—'}%'))),
            ],
            if (positions.isNotEmpty) ...[
              const Divider(height: 24),
              const Text('Posições',
                  style: TextStyle(fontWeight: FontWeight.w700)),
              ...positions.map((item) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('${item['symbol']} · ${item['name'] ?? 'Ativo'}'),
                  subtitle: Text(
                      '${item['quantity']} unidades · médio ${investmentMoney(item['average_price'], item['currency'])}'),
                  trailing: Text(item['current_value'] == null
                      ? 'Sem cotação'
                      : investmentMoney(
                          item['current_value'], item['currency'])))),
            ],
            if (positions.isEmpty)
              const Padding(
                  padding: EdgeInsets.only(top: 10),
                  child: Text('Nenhuma posição de investimento cadastrada.')),
          ],
        ),
      ),
    );
  }

  // Patrimônio, metas e plano de ação são módulos independentes da carteira.
  Widget _patrimonyView() {
    final canEdit = permissions?['can_edit_patrimony'] == true;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (investmentPortfolio != null) ...[
          _investmentPortfolioView(),
          const SizedBox(height: 14)
        ],
        if (canEdit)
          FilledButton.icon(
            onPressed: addPatrimony,
            icon: const Icon(Icons.add),
            label: const Text('Adicionar patrimônio'),
          ),
        if (patrimony.isEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 14),
            child: Text('Nenhum item patrimonial cadastrado.'),
          ),
        ...patrimony.map(
          (item) => Card(
            child: ListTile(
              title: Text(item['description'].toString()),
              subtitle: Text(
                '${item['category']} · ${item['institution'] ?? 'Sem instituição'}${item['notes'] != null && item['notes'].toString().isNotEmpty ? '\n${item['notes']}' : ''}',
              ),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(privateMoney(item['value'])),
                  if (canEdit)
                    PopupMenuButton<String>(
                      onSelected: (action) => action == 'edit'
                          ? editPatrimony(item)
                          : deletePatrimony(item),
                      itemBuilder: (_) => const [
                        PopupMenuItem(value: 'edit', child: Text('Editar')),
                        PopupMenuItem(value: 'delete', child: Text('Remover')),
                      ],
                    ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _goalsView() {
    final canEdit = permissions?['can_edit_goals'] == true;
    final visibleGoals = orderedGoals(goalFilter == 'all'
        ? goals
        : goals.where((goal) => goalFilter == 'overdue'
            ? isOverdueGoal(Map<String, dynamic>.from(goal))
            : goal['status'] == goalFilter));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (canEdit)
          FilledButton.icon(
            onPressed: addGoal,
            icon: const Icon(Icons.add),
            label: const Text('Adicionar meta'),
          ),
        Align(
          alignment: Alignment.centerRight,
          child: DropdownButton<String>(
            value: goalFilter,
            items: const [
              DropdownMenuItem(value: 'all', child: Text('Todas')),
              DropdownMenuItem(value: 'active', child: Text('Ativas')),
              DropdownMenuItem(value: 'paused', child: Text('Pausadas')),
              DropdownMenuItem(value: 'completed', child: Text('Concluídas')),
              DropdownMenuItem(value: 'overdue', child: Text('Prazo vencido')),
            ],
            onChanged: (value) => setState(() => goalFilter = value ?? 'all'),
          ),
        ),
        if (visibleGoals.isEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 14),
            child: Text('Nenhuma meta neste filtro.'),
          ),
        ...visibleGoals.map(
          (goal) {
            final overdue = isOverdueGoal(Map<String, dynamic>.from(goal));
            final target =
                double.tryParse(goal['target_value']?.toString() ?? '') ?? 0;
            final current =
                double.tryParse(goal['current_value']?.toString() ?? '') ?? 0;
            final progress = target <= 0
                ? 0.0
                : (current / target).clamp(0.0, 1.0).toDouble();
            return Card(
              child: ListTile(
                title: Text(goal['title'].toString()),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SizedBox(height: 8),
                    LinearProgressIndicator(
                        value: progress, color: overdue ? Colors.red : null),
                    const SizedBox(height: 6),
                    Text(
                      '${privateMoney(goal['current_value'])} de ${privateMoney(goal['target_value'])}${goal['target_date'] != null ? ' · até ${dateLabel(goal['target_date'])}' : ''}${overdue ? ' · Prazo vencido' : ''}',
                    ),
                  ],
                ),
                trailing: canEdit
                    ? PopupMenuButton<String>(
                        onSelected: (action) => action == 'edit'
                            ? editGoal(goal)
                            : deleteGoal(goal),
                        itemBuilder: (_) => const [
                          PopupMenuItem(value: 'edit', child: Text('Editar')),
                          PopupMenuItem(
                              value: 'delete', child: Text('Remover')),
                        ],
                      )
                    : Text(goalStatusLabel(goal['status'])),
              ),
            );
          },
        ),
      ],
    );
  }

  // Relatórios são somente leitura no mobile; a publicação ocorre no painel Advisor.
  Widget _reportsView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (reports.isEmpty) const Text('Nenhum relatório publicado.'),
        ...reports.map(
          (report) => Card(
            child: ListTile(
              leading: const Icon(Icons.description_outlined),
              title: Text(report['title'].toString()),
              subtitle: Text(
                '${dateLabel(report['period_start'])} a ${dateLabel(report['period_end'])}',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => openReport(report),
            ),
          ),
        ),
      ],
    );
  }

  // Documentos exibem o estado de revisão e permitem visualizar/baixar o arquivo.
  Widget _documentsView() {
    final canUpload = user?['role'] != 'client' &&
        permissions?['can_upload_documents'] == true;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
            'Documentos disponibilizados pelo seu Advisor. O envio e a atualização são feitos pelo Advisor.'),
        const SizedBox(height: 8),
        const Text(
          'Os comprovantes de renda e endereço devem ser atualizados a cada 12 meses.',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 12),
        if (canUpload)
          FilledButton.icon(
            onPressed: documentBusy ? null : uploadDocument,
            icon: const Icon(Icons.upload_file),
            label: Text(documentBusy ? 'Enviando...' : 'Enviar documento'),
          ),
        if (canUpload) const SizedBox(height: 12),
        if (documents.isEmpty) const Text('Nenhum documento disponível.'),
        ...documents.map(
          (document) => Card(
            child: ListTile(
              leading: const Icon(Icons.attach_file),
              title: Text(document['original_name'].toString()),
              subtitle: Text(
                '${documentKindLabel(document['kind'])} · ${fileSizeLabel(document['size_bytes'])} · ${dateLabel(document['created_at'])}${document['description'] != null && document['description'].toString().isNotEmpty ? '\n${document['description']}' : ''}',
              ),
              onTap: () => showDocument(document),
            ),
          ),
        ),
      ],
    );
  }

  Future<void> uploadDocument() async {
    final result = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'png', 'jpg', 'jpeg', 'txt'],
    );
    if (!mounted) return;
    if (result == null || result.files.single.path == null || user == null)
      return;
    final file = result.files.single;
    if (file.size > 10 * 1024 * 1024) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('O arquivo excede o limite de 10 MB.')));
      return;
    }
    final path = file.path!;
    final extension = (file.extension ?? '').toLowerCase();
    final contentType = switch (extension) {
      'pdf' => 'application/pdf',
      'png' => 'image/png',
      'jpg' || 'jpeg' => 'image/jpeg',
      _ => 'text/plain',
    };
    if (mounted) setState(() => documentBusy = true);
    final description = TextEditingController();
    var kind = 'other';
    final shouldSend = await showDialog<bool>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: const Text('Enviar documento'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(file.name),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: kind,
                  decoration:
                      const InputDecoration(labelText: 'Tipo de documento'),
                  items: const [
                    DropdownMenuItem(
                        value: 'identification', child: Text('Identificação')),
                    DropdownMenuItem(
                        value: 'income_proof',
                        child: Text('Comprovante de renda')),
                    DropdownMenuItem(
                        value: 'address_proof',
                        child: Text('Comprovante de endereço')),
                    DropdownMenuItem(
                        value: 'other', child: Text('Outro documento')),
                  ],
                  onChanged: (value) => kind = value ?? 'other',
                ),
                const SizedBox(height: 12),
                TextField(
                    controller: description,
                    maxLength: 500,
                    decoration: const InputDecoration(
                        labelText: 'Descrição (opcional)')),
              ],
            ),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(dialogContext, false),
                  child: const Text('Cancelar')),
              FilledButton(
                  onPressed: () => Navigator.pop(dialogContext, true),
                  child: const Text('Enviar')),
            ],
          ),
        ) ??
        false;
    if (!shouldSend) {
      description.dispose();
      if (mounted) setState(() => documentBusy = false);
      return;
    }
    try {
      await widget.api.uploadDocument(user!['id'] as int,
          path: path,
          fileName: file.name,
          contentType: contentType,
          kind: kind,
          description:
              description.text.trim().isEmpty ? null : description.text.trim());
      await load();
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Documento enviado com sucesso.')));
    } on ApiException catch (exception) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
    } finally {
      description.dispose();
      if (mounted) setState(() => documentBusy = false);
    }
  }

  Future<void> showDocument(Map<String, dynamic> document) async {
    if (user == null) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DocumentViewerScreen(
          api: widget.api,
          clientId: user!['id'] as int,
          document: document,
        ),
      ),
    );
  }

  Future<void> downloadDocument(Map<String, dynamic> document) async {
    if (user == null) return;
    final outputPath = await FilePicker.saveFile(
        fileName: document['original_name']?.toString() ?? 'documento');
    if (outputPath == null) return;
    try {
      final bytes = await widget.api
          .downloadDocument(user!['id'] as int, document['id'] as int);
      await File(outputPath).writeAsBytes(bytes, flush: true);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Documento salvo em $outputPath.')),
        );
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  Future<void> openReport(Map<String, dynamic> report) async {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(report['title'].toString()),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Período: ${dateLabel(report['period_start'])} a ${dateLabel(report['period_end'])}',
                style: Theme.of(context).textTheme.labelLarge,
              ),
              const SizedBox(height: 18),
              Text(report['summary'].toString()),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Fechar'),
          ),
        ],
      ),
    );
  }

  Future<bool> confirmRemoval(String label) async {
    return await showDialog<bool>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: Text('Remover $label?'),
            content: const Text('Essa ação não pode ser desfeita.'),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(dialogContext, false),
                  child: const Text('Cancelar')),
              FilledButton(
                  onPressed: () => Navigator.pop(dialogContext, true),
                  child: const Text('Remover')),
            ],
          ),
        ) ??
        false;
  }

  Future<void> editPatrimony(Map<String, dynamic> item) async {
    final category = TextEditingController(text: item['category'].toString());
    final description =
        TextEditingController(text: item['description'].toString());
    final institution =
        TextEditingController(text: item['institution']?.toString() ?? '');
    final value =
        TextEditingController(text: formatBrazilianNumber(item['value']));
    final notes = TextEditingController(text: item['notes']?.toString() ?? '');
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Editar patrimônio'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                  controller: category,
                  decoration: const InputDecoration(labelText: 'Categoria')),
              const SizedBox(height: 10),
              TextField(
                  controller: description,
                  decoration: const InputDecoration(labelText: 'Descrição')),
              const SizedBox(height: 10),
              TextField(
                  controller: institution,
                  decoration: const InputDecoration(
                      labelText: 'Instituição (opcional)')),
              const SizedBox(height: 10),
              TextField(
                  controller: value,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                      labelText: 'Valor', prefixText: 'R\$ ')),
              const SizedBox(height: 10),
              TextField(
                  controller: notes,
                  maxLines: 2,
                  maxLength: 500,
                  decoration: const InputDecoration(
                      labelText: 'Observações (opcional)')),
            ],
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar')),
          FilledButton(
            onPressed: () {
              final parsedValue = parseBrazilianNumber(value.text);
              if (category.text.trim().isEmpty ||
                  description.text.trim().isEmpty) {
                showFormError('Preencha categoria e descrição.');
                return;
              }
              if (parsedValue == null || parsedValue < 0) {
                showFormError('Informe um valor patrimonial válido.');
                return;
              }
              Navigator.pop(dialogContext, {
                'category': category.text.trim(),
                'description': description.text.trim(),
                'institution': institution.text.trim().isEmpty
                    ? null
                    : institution.text.trim(),
                'value': parsedValue,
                'notes': notes.text.trim().isEmpty ? null : notes.text.trim()
              });
            },
            child: const Text('Salvar'),
          ),
        ],
      ),
    );
    category.dispose();
    description.dispose();
    institution.dispose();
    value.dispose();
    notes.dispose();
    if (result == null || user == null) return;
    try {
      await widget.api
          .updatePatrimony(user!['id'] as int, item['id'] as int, result);
      await load();
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Patrimônio atualizado.')));
    } on ApiException catch (exception) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
    }
  }

  Future<void> deletePatrimony(Map<String, dynamic> item) async {
    if (!await confirmRemoval('este item patrimonial') || user == null) return;
    try {
      await widget.api.deletePatrimony(user!['id'] as int, item['id'] as int);
      await load();
    } on ApiException catch (exception) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
    }
  }

  Future<void> addPatrimony() async {
    final category = TextEditingController();
    final description = TextEditingController();
    final institution = TextEditingController();
    final value = TextEditingController();
    final notes = TextEditingController();
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Adicionar patrimônio'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                  controller: category,
                  decoration: const InputDecoration(labelText: 'Categoria')),
              const SizedBox(height: 10),
              TextField(
                  controller: description,
                  decoration: const InputDecoration(labelText: 'Descrição')),
              const SizedBox(height: 10),
              TextField(
                  controller: institution,
                  decoration: const InputDecoration(
                      labelText: 'Instituição (opcional)')),
              const SizedBox(height: 10),
              TextField(
                  controller: value,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                      labelText: 'Valor', prefixText: 'R\$ ')),
              const SizedBox(height: 10),
              TextField(
                  controller: notes,
                  maxLines: 2,
                  maxLength: 500,
                  decoration: const InputDecoration(
                      labelText: 'Observações (opcional)')),
            ],
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar')),
          FilledButton(
            onPressed: () {
              final parsedValue = parseBrazilianNumber(value.text);
              if (category.text.trim().isEmpty ||
                  description.text.trim().isEmpty) {
                showFormError('Preencha categoria e descrição.');
                return;
              }
              if (parsedValue == null || parsedValue < 0) {
                showFormError('Informe um valor patrimonial válido.');
                return;
              }
              Navigator.pop(dialogContext, {
                'category': category.text.trim(),
                'description': description.text.trim(),
                'institution': institution.text.trim().isEmpty
                    ? null
                    : institution.text.trim(),
                'value': parsedValue,
                'notes': notes.text.trim().isEmpty ? null : notes.text.trim()
              });
            },
            child: const Text('Salvar'),
          ),
        ],
      ),
    );
    category.dispose();
    description.dispose();
    institution.dispose();
    value.dispose();
    notes.dispose();
    if (result == null || user == null) return;
    try {
      await widget.api.createPatrimony(user!['id'] as int, result);
      await load();
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Patrimônio adicionado.')));
    } on ApiException catch (exception) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
    }
  }

  Future<void> addGoal() async {
    final title = TextEditingController();
    final target = TextEditingController();
    final targetDate = TextEditingController();
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Adicionar meta'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
                controller: title,
                decoration: const InputDecoration(labelText: 'Título')),
            const SizedBox(height: 10),
            TextField(
                controller: target,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                    labelText: 'Valor-alvo', prefixText: 'R\$ ')),
            const SizedBox(height: 10),
            TextField(
              controller: targetDate,
              readOnly: true,
              decoration: const InputDecoration(
                  labelText: 'Prazo (opcional)',
                  suffixIcon: Icon(Icons.calendar_today_outlined)),
              onTap: () async {
                final date = await showDatePicker(
                    context: dialogContext,
                    firstDate: DateTime.now(),
                    lastDate: DateTime(2100),
                    initialDate: DateTime.now());
                if (date != null)
                  targetDate.text = date.toIso8601String().split('T').first;
              },
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar')),
          FilledButton(
            onPressed: () {
              final parsedTarget = parseBrazilianNumber(target.text);
              if (title.text.trim().isEmpty) {
                showFormError('Informe o título da meta.');
                return;
              }
              if (parsedTarget == null || parsedTarget <= 0) {
                showFormError('Informe um valor-alvo maior que zero.');
                return;
              }
              Navigator.pop(dialogContext, {
                'title': title.text.trim(),
                'target_value': parsedTarget,
                'target_date': targetDate.text.isEmpty ? null : targetDate.text
              });
            },
            child: const Text('Salvar'),
          ),
        ],
      ),
    );
    title.dispose();
    target.dispose();
    targetDate.dispose();
    if (result == null || user == null) return;
    try {
      await widget.api.createGoal(user!['id'] as int, result);
      await load();
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Meta adicionada.')));
    } on ApiException catch (exception) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
    }
  }

  Future<void> editGoal(Map<String, dynamic> goal) async {
    final title = TextEditingController(text: goal['title'].toString());
    final target = TextEditingController(
        text: formatBrazilianNumber(goal['target_value']));
    final current = TextEditingController(
        text: formatBrazilianNumber(goal['current_value']));
    final targetDate =
        TextEditingController(text: goal['target_date']?.toString() ?? '');
    var status = goal['status']?.toString() ?? 'active';
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Editar meta'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
                controller: title,
                decoration: const InputDecoration(labelText: 'Título')),
            const SizedBox(height: 10),
            TextField(
                controller: target,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                    labelText: 'Valor-alvo', prefixText: 'R\$ ')),
            const SizedBox(height: 10),
            TextField(
                controller: current,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                    labelText: 'Valor atual', prefixText: 'R\$ ')),
            const SizedBox(height: 10),
            TextField(
              controller: targetDate,
              readOnly: true,
              decoration: const InputDecoration(
                  labelText: 'Prazo (opcional)',
                  suffixIcon: Icon(Icons.calendar_today_outlined)),
              onTap: () async {
                final date = await showDatePicker(
                    context: dialogContext,
                    firstDate: DateTime(2000),
                    lastDate: DateTime(2100),
                    initialDate:
                        DateTime.tryParse(targetDate.text) ?? DateTime.now());
                if (date != null)
                  targetDate.text = date.toIso8601String().split('T').first;
              },
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: status,
              decoration: const InputDecoration(labelText: 'Status'),
              items: const [
                DropdownMenuItem(value: 'active', child: Text('Ativa')),
                DropdownMenuItem(value: 'paused', child: Text('Pausada')),
                DropdownMenuItem(value: 'completed', child: Text('Concluída'))
              ],
              onChanged: (value) => status = value ?? status,
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar')),
          FilledButton(
            onPressed: () {
              final parsedTarget = parseBrazilianNumber(target.text);
              final parsedCurrent = parseBrazilianNumber(current.text);
              if (title.text.trim().isEmpty) {
                showFormError('Informe o título da meta.');
                return;
              }
              if (parsedTarget == null ||
                  parsedTarget <= 0 ||
                  parsedCurrent == null ||
                  parsedCurrent < 0) {
                showFormError('Informe valores válidos para a meta.');
                return;
              }
              Navigator.pop(dialogContext, {
                'title': title.text.trim(),
                'target_value': parsedTarget,
                'current_value': parsedCurrent,
                'target_date': targetDate.text.isEmpty ? null : targetDate.text,
                'status': status
              });
            },
            child: const Text('Salvar'),
          ),
        ],
      ),
    );
    title.dispose();
    target.dispose();
    current.dispose();
    targetDate.dispose();
    if (result == null || user == null) return;
    try {
      await widget.api
          .updateGoal(user!['id'] as int, goal['id'] as int, result);
      await load();
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Meta atualizada.')));
    } on ApiException catch (exception) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
    }
  }

  Future<void> deleteGoal(Map<String, dynamic> goal) async {
    if (!await confirmRemoval('esta meta') || user == null) return;
    try {
      await widget.api.deleteGoal(user!['id'] as int, goal['id'] as int);
      await load();
    } on ApiException catch (exception) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
    }
  }

  Future<void> editFinancialProfile() async {
    final income = TextEditingController(
      text: formatBrazilianNumber(financialProfile?['monthly_income'] ?? 0),
    );
    final expenses = TextEditingController(
      text: formatBrazilianNumber(financialProfile?['monthly_expenses'] ?? 0),
    );
    final risk = TextEditingController(
      text: financialProfile?['risk_profile']?.toString() ?? '',
    );
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Perfil financeiro'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: income,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                  labelText: 'Renda mensal',
                  prefixText: 'R\$ ',
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: expenses,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                  labelText: 'Despesas mensais',
                  prefixText: 'R\$ ',
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: risk,
                decoration: const InputDecoration(
                  labelText: 'Perfil de risco (opcional)',
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () {
              final parsedIncome = parseBrazilianNumber(income.text);
              final parsedExpenses = parseBrazilianNumber(expenses.text);
              if (parsedIncome == null ||
                  parsedIncome < 0 ||
                  parsedExpenses == null ||
                  parsedExpenses < 0) {
                showFormError('Informe renda e despesas válidas.');
                return;
              }
              Navigator.pop(dialogContext, {
                'monthly_income': parsedIncome,
                'monthly_expenses': parsedExpenses,
                'risk_profile':
                    risk.text.trim().isEmpty ? null : risk.text.trim(),
              });
            },
            child: const Text('Salvar'),
          ),
        ],
      ),
    );
    income.dispose();
    expenses.dispose();
    risk.dispose();
    if (result == null || user == null) return;
    try {
      await widget.api.updateFinancialProfile(user!['id'] as int, result);
      await load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Perfil financeiro atualizado.')),
        );
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(exception.message)),
        );
      }
    }
  }

  Future<void> editClientProfile() async {
    final name = TextEditingController(text: user?['name']?.toString() ?? '');
    final phone = TextEditingController(
      text: clientProfile?['phone']?.toString() ?? '',
    );
    final fatherName = TextEditingController(
        text: clientProfile?['father_name']?.toString() ?? '');
    final motherName = TextEditingController(
        text: clientProfile?['mother_name']?.toString() ?? '');
    final street = TextEditingController(
        text: clientProfile?['address_street']?.toString() ?? '');
    final number = TextEditingController(
        text: clientProfile?['address_number']?.toString() ?? '');
    final city = TextEditingController(
        text: clientProfile?['address_city']?.toString() ?? '');
    final zipCode = TextEditingController(
        text: clientProfile?['address_zip_code']?.toString() ?? '');
    final state = TextEditingController(
        text: clientProfile?['address_state']?.toString() ?? '');
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Meus dados'),
        content: SizedBox(
          width: 460,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: name,
                  decoration: const InputDecoration(labelText: 'Nome'),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: phone,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(labelText: 'Telefone'),
                ),
                const SizedBox(height: 18),
                const Align(
                    alignment: Alignment.centerLeft,
                    child: Text('Filiação',
                        style: TextStyle(fontWeight: FontWeight.w700))),
                const SizedBox(height: 10),
                TextField(
                    controller: fatherName,
                    decoration: const InputDecoration(
                        labelText: 'Nome do pai (opcional)')),
                const SizedBox(height: 10),
                TextField(
                    controller: motherName,
                    decoration: const InputDecoration(
                        labelText: 'Nome da mãe (opcional)')),
                const SizedBox(height: 18),
                const Align(
                    alignment: Alignment.centerLeft,
                    child: Text('Endereço',
                        style: TextStyle(fontWeight: FontWeight.w700))),
                const SizedBox(height: 10),
                TextField(
                    controller: street,
                    decoration: const InputDecoration(labelText: 'Rua')),
                const SizedBox(height: 10),
                TextField(
                    controller: number,
                    decoration: const InputDecoration(labelText: 'Número')),
                const SizedBox(height: 10),
                TextField(
                    controller: city,
                    decoration: const InputDecoration(labelText: 'Cidade')),
                const SizedBox(height: 10),
                TextField(
                    controller: zipCode,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'CEP')),
                const SizedBox(height: 10),
                TextField(
                    controller: state,
                    decoration: const InputDecoration(labelText: 'Estado')),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () {
              if (name.text.trim().length < 2) {
                showFormError('Informe seu nome completo.');
                return;
              }
              Navigator.pop(dialogContext, {
                'name': name.text.trim(),
                'phone': phone.text.trim().isEmpty ? null : phone.text.trim(),
                'father_name': fatherName.text.trim().isEmpty
                    ? null
                    : fatherName.text.trim(),
                'mother_name': motherName.text.trim().isEmpty
                    ? null
                    : motherName.text.trim(),
                'address_street':
                    street.text.trim().isEmpty ? null : street.text.trim(),
                'address_number':
                    number.text.trim().isEmpty ? null : number.text.trim(),
                'address_city':
                    city.text.trim().isEmpty ? null : city.text.trim(),
                'address_zip_code':
                    zipCode.text.trim().isEmpty ? null : zipCode.text.trim(),
                'address_state':
                    state.text.trim().isEmpty ? null : state.text.trim(),
              });
            },
            child: const Text('Salvar'),
          ),
        ],
      ),
    );
    name.dispose();
    phone.dispose();
    fatherName.dispose();
    motherName.dispose();
    street.dispose();
    number.dispose();
    city.dispose();
    zipCode.dispose();
    state.dispose();
    if (result == null || user == null) return;
    try {
      await widget.api.updateProfile(user!['id'] as int, result);
      await load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Dados atualizados.')),
        );
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(exception.message)),
        );
      }
    }
  }

  Future<void> signOut() async {
    try {
      await widget.api.logout();
    } catch (_) {
      widget.api.accessToken = null;
    }
    await widget.api.secureStorage.delete(clientCacheKey);
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => LoginScreen(api: widget.api)),
      (_) => false,
    );
  }

  Future<void> changePassword() async {
    final current = TextEditingController();
    final next = TextEditingController();
    final confirmation = TextEditingController();
    final result = await showDialog<List<String>>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Alterar senha'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: current,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Senha atual'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: next,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Nova senha'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: confirmation,
              obscureText: true,
              decoration:
                  const InputDecoration(labelText: 'Confirmar nova senha'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () {
              if (current.text.length < 8 || next.text.length < 8) {
                showFormError('As senhas devem ter pelo menos 8 caracteres.');
                return;
              }
              if (next.text != confirmation.text) {
                showFormError('A confirmação da nova senha não confere.');
                return;
              }
              Navigator.pop(dialogContext, [current.text, next.text]);
            },
            child: const Text('Alterar'),
          ),
        ],
      ),
    );
    current.dispose();
    next.dispose();
    confirmation.dispose();
    if (result == null) return;
    try {
      await widget.api.changePassword(result[0], result[1]);
      await widget.api.clearSession();
      await widget.api.secureStorage.delete(clientCacheKey);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Senha alterada'),
          content: const Text('Entre novamente com sua nova senha.'),
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Continuar'),
            ),
          ],
        ),
      );
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => LoginScreen(api: widget.api)),
        (_) => false,
      );
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(exception.message)),
        );
      }
    }
  }

  // Perfil reúne identidade, endereço, dados financeiros e preferências de segurança.
  Widget _profileView() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              user!['name'].toString(),
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 6),
            Text(user!['email'].toString()),
            const SizedBox(height: 6),
            Text('Telefone: ${clientProfile?['phone'] ?? 'Não informado'}'),
            const SizedBox(height: 6),
            Text('Pai: ${clientProfile?['father_name'] ?? 'Não informado'}'),
            const SizedBox(height: 6),
            Text('Mãe: ${clientProfile?['mother_name'] ?? 'Não informado'}'),
            const SizedBox(height: 6),
            Text('Endereço: ${_addressLabel()}'),
            const SizedBox(height: 6),
            Text(
              'Advisor: ${clientProfile?['advisor_name'] ?? 'Ainda não vinculado'}',
            ),
            if (user?['role'] != 'client' &&
                permissions?['can_edit_profile'] == true) ...[
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: editClientProfile,
                icon: const Icon(Icons.edit_outlined),
                label: const Text('Editar meus dados'),
              ),
            ],
            const SizedBox(height: 18),
            Text('Papel: ${user!['role']}'),
            const SizedBox(height: 18),
            const Text(
              'Seus dados cadastrais e documentos são atualizados pelo Advisor. Você pode consultar as informações disponíveis neste aplicativo.',
            ),
            const SizedBox(height: 18),
            const Divider(),
            const SizedBox(height: 12),
            Text(
              'Perfil financeiro',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Renda mensal: ${privateMoney(financialProfile?['monthly_income'] ?? 0)}',
            ),
            Text(
              'Despesas mensais: ${privateMoney(financialProfile?['monthly_expenses'] ?? 0)}',
            ),
            if (financialProfile?['risk_profile'] != null)
              Text('Perfil de risco: ${financialProfile!['risk_profile']}'),
            if (permissions?['can_edit_financial_profile'] == true) ...[
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: editFinancialProfile,
                icon: const Icon(Icons.edit_outlined),
                label: const Text('Editar perfil financeiro'),
              ),
            ],
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: openSuitabilityQuestionnaire,
              icon: const Icon(Icons.assignment_outlined),
              label: Text(suitability == null
                  ? 'Responder perfil de investidor'
                  : 'Ver ou atualizar carteira sugerida'),
            ),
            const SizedBox(height: 24),
            if (biometricAvailable) ...[
              OutlinedButton.icon(
                onPressed: _toggleBiometric,
                icon: Icon(biometricEnabled
                    ? Icons.fingerprint
                    : Icons.fingerprint_outlined),
                label: Text(biometricEnabled
                    ? 'Desativar acesso biométrico'
                    : 'Ativar acesso biométrico'),
              ),
              const SizedBox(height: 10),
            ],
            OutlinedButton.icon(
              onPressed: changePassword,
              icon: const Icon(Icons.lock_outline),
              label: const Text('Alterar senha'),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: signOut,
              icon: const Icon(Icons.logout),
              label: const Text('Sair da conta'),
            ),
          ],
        ),
      ),
    );
  }

  String _addressLabel() {
    final profile = clientProfile;
    if (profile == null) return 'Não informado';
    final street = profile['address_street']?.toString() ?? '';
    final number = profile['address_number']?.toString() ?? '';
    final city = profile['address_city']?.toString() ?? '';
    final state = profile['address_state']?.toString() ?? '';
    final zipCode = profile['address_zip_code']?.toString() ?? '';
    final line = [
      if (street.isNotEmpty) street,
      if (number.isNotEmpty) 'nº $number',
      if (city.isNotEmpty) city,
      if (state.isNotEmpty) state,
      if (zipCode.isNotEmpty) 'CEP $zipCode',
    ].join(', ');
    return line.isEmpty ? 'Não informado' : line;
  }
}

// Visualizador protegido: recebe bytes baixados pela API e escolhe o renderer adequado.
class DocumentViewerScreen extends StatefulWidget {
  const DocumentViewerScreen({
    super.key,
    required this.api,
    required this.clientId,
    required this.document,
  });

  final ApiClient api;
  final int clientId;
  final Map<String, dynamic> document;

  @override
  State<DocumentViewerScreen> createState() => _DocumentViewerScreenState();
}

class _DocumentViewerScreenState extends State<DocumentViewerScreen> {
  late final Future<List<int>> documentBytes;

  @override
  void initState() {
    super.initState();
    documentBytes = widget.api.downloadDocument(
      widget.clientId,
      widget.document['id'] as int,
    );
  }

  Future<void> saveDocument() async {
    final outputPath = await FilePicker.saveFile(
      fileName: widget.document['original_name']?.toString() ?? 'documento',
    );
    if (outputPath == null) return;
    try {
      final bytes = await documentBytes;
      await File(outputPath).writeAsBytes(bytes, flush: true);
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Documento salvo em $outputPath.')));
    } on ApiException catch (exception) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
    }
  }

  Widget contentFor(List<int> bytes) {
    final contentType = widget.document['content_type']?.toString() ?? '';
    final data = Uint8List.fromList(bytes);
    if (contentType == 'application/pdf') {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.picture_as_pdf_outlined, size: 64),
              const SizedBox(height: 16),
              const Text(
                'A visualização interna de PDFs está indisponível nesta versão.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              const Text(
                'Baixe o documento para abri-lo no visualizador de PDF do seu dispositivo.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: saveDocument,
                icon: const Icon(Icons.download_outlined),
                label: const Text('Baixar PDF'),
              ),
            ],
          ),
        ),
      );
    }
    if (contentType.startsWith('image/')) {
      return InteractiveViewer(
        minScale: 0.5,
        maxScale: 4,
        child: Center(child: Image.memory(data, fit: BoxFit.contain)),
      );
    }
    if (contentType == 'text/plain') {
      return SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: SelectableText(utf8.decode(data, allowMalformed: true)),
      );
    }
    return const Center(
      child: Text('Visualização não disponível para este tipo de arquivo.'),
    );
  }

  @override
  Widget build(BuildContext context) {
    final document = widget.document;
    return Scaffold(
      appBar: AppBar(
        title: Text(document['original_name']?.toString() ?? 'Documento'),
        actions: [
          IconButton(
              onPressed: saveDocument,
              icon: const Icon(Icons.download_outlined),
              tooltip: 'Baixar')
        ],
      ),
      body: FutureBuilder<List<int>>(
        future: documentBytes,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError || snapshot.data == null) {
            return const Center(
                child: Text('Não foi possível visualizar este documento.'));
          }
          return contentFor(snapshot.data!);
        },
      ),
    );
  }
}
