// Talentum — mobile/lib/main.dart
// Responsabilidade: Implementa a interface Flutter, os fluxos de autenticação e as funcionalidades do cliente.
// Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import 'dart:async';
import 'dart:convert';
// Arquivos locais e detecção de plataforma usam dart:io e exigem alternativa antes de habilitar Flutter Web.
import 'dart:io' show File, Platform;

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:local_auth/local_auth.dart';
import 'package:printing/printing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';

// Compartilhada entre a autenticação e a tela autenticada para invalidar cache ao trocar de conta.
const clientCacheKey = 'talentum_client_cache';

// Aplica máscara pt-BR e limita valores a duas casas decimais.
/// Formata valores monetários durante a digitação, limitando as casas decimais.
class TwoDecimalMoneyInputFormatter extends TextInputFormatter {
  const TwoDecimalMoneyInputFormatter();

  /// Filtra caracteres inválidos e mantém no máximo duas casas decimais.
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final input = newValue.text;
    if (!RegExp(r'^-?[0-9.,]*$').hasMatch(input)) return oldValue;

    final caret = newValue.selection.baseOffset.clamp(0, input.length);
    final digitsBeforeCaret =
        RegExp(r'\d').allMatches(input.substring(0, caret)).length;
    final hasComma = input.contains(',');
    final periodsAreGrouping =
        !hasComma && RegExp(r'^-?\d{1,3}(\.\d{3})+$').hasMatch(input);
    final separatorIndex = hasComma
        ? input.indexOf(',')
        : periodsAreGrouping
            ? -1
            : input.lastIndexOf('.');
    final caretWasAfterDecimal = separatorIndex >= 0 && caret > separatorIndex;
    final integerSource =
        separatorIndex >= 0 ? input.substring(0, separatorIndex) : input;
    final fractionSource = separatorIndex >= 0
        ? input.substring(separatorIndex + 1).replaceAll(RegExp(r'\D'), '')
        : '';
    // Rejeita a edição inteira acima de duas casas; o protótipo RN trunca o excedente (achado 99).
    if (fractionSource.length > 2) return oldValue;

    final negative = integerSource.startsWith('-');
    final digits = integerSource.replaceAll(RegExp(r'\D'), '');
    final integer = digits.isEmpty
        ? (negative ? '-0' : '0')
        : '${negative ? '-' : ''}${digits.replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => '.')}';
    final formatted =
        '$integer${separatorIndex >= 0 ? ',$fractionSource' : ''}';
    var mappedCaret = 0;
    var seenDigits = 0;
    for (var index = 0; index < formatted.length; index++) {
      if (RegExp(r'\d').hasMatch(formatted[index])) seenDigits++;
      if (seenDigits >= digitsBeforeCaret && digitsBeforeCaret > 0) {
        mappedCaret = index + 1;
        break;
      }
      mappedCaret = index + 1;
    }
    final formattedSeparator = formatted.indexOf(',');
    if (caretWasAfterDecimal &&
        formattedSeparator >= 0 &&
        mappedCaret <= formattedSeparator) {
      mappedCaret = formattedSeparator + 1;
    }
    return TextEditingValue(
      text: formatted,
      selection: TextSelection.collapsed(
          offset: mappedCaret.clamp(0, formatted.length)),
    );
  }
}

/// Converte entradas numéricas digitadas no padrão brasileiro para `double`.
double? parseBrazilianNumber(String value) {
  final sanitized = value.trim().replaceAll(RegExp(r'[^0-9,.-]'), '');
  if (sanitized.isEmpty) return null;
  final groupedInteger = RegExp(r'^-?\d{1,3}(\.\d{3})+$').hasMatch(sanitized);
  final normalized = sanitized.contains(',') || groupedInteger
      ? sanitized.replaceAll('.', '').replaceAll(',', '.')
      : sanitized;
  return double.tryParse(normalized);
}

// Formata valores com separador de milhares e casas decimais no padrão pt-BR.
/// Formata um valor numérico com separadores usados no padrão brasileiro.
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

/// Converte uma data da API para a apresentação adotada pelo aplicativo.
String formatApiDate(dynamic value) {
  final raw = value?.toString() ?? '';
  return RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(raw)
      ? '${raw.substring(8, 10)}/${raw.substring(5, 7)}/${raw.substring(0, 4)}'
      : raw;
}

// Quantidades da API aceitam até oito casas; a notação científica é expandida até esse limite.
/// Apresenta cotas inteiras sem casas e remove zeros finais de cotas fracionadas.
String formatInvestmentQuantity(dynamic value) {
  if (value == null) return '0';
  final raw = value.toString().trim().replaceAll(',', '.');
  final normalized = raw.toLowerCase().contains('e')
      ? (double.tryParse(raw)?.toStringAsFixed(8) ?? raw)
      : raw;
  final parts = normalized.split('.');
  if (parts.length < 2) return normalized;
  final fraction = parts.skip(1).join().replaceAll(RegExp(r'0+$'), '');
  return fraction.isEmpty ? parts.first : '${parts.first},$fraction';
}

const biometricEnabledKey =
    'talentum_biometric_enabled'; // Chave local da preferência de autenticação biométrica.

// Consulta os recursos biométricos disponíveis antes de exibir ações de login.
/// Verifica se o dispositivo oferece autenticação biométrica.
Future<bool> deviceSupportsBiometrics() async {
  try {
    final authentication = LocalAuthentication();
    if (!await authentication.isDeviceSupported()) return false;
    return (await authentication.getAvailableBiometrics()).isNotEmpty;
  } catch (_) {
    // Uma falha do plugin é tratada como biometria indisponível e oculta a opção.
    return false;
  }
}

// Mantém a tradução dos tipos internos de documento para os rótulos da interface.
/// Converte o código do tipo de documento em um rótulo para a interface.
String documentKindLabel(dynamic kind) => switch (kind?.toString()) {
      'identification' => 'Identificação',
      'income_proof' => 'Comprovante de renda',
      'address_proof' => 'Comprovante de endereço',
      _ => 'Outro documento',
    };

const configuredApiUrl = String.fromEnvironment('API_URL');
// O fallback usa HTTP: só o manifesto debug Android libera essa exceção; os demais builds precisam de URL HTTPS apropriada.
final apiUrl = configuredApiUrl.isNotEmpty
    ? configuredApiUrl
    : Platform.isAndroid
        ? 'http://10.0.2.2:8000'
        : 'http://127.0.0.1:8000';

/// Reúne as cores principais usadas para manter a identidade visual do aplicativo.
class TalentumColors {
  static const petrol = Color(0xff17324d);
  static const teal = Color(0xff167c76);
  static const silver = Color(0xffb8c3ca);
  static const ink = Color(0xff1f2b35);
  static const muted = Color(0xff63717d);
  static const line = Color(0xffdce4e8);
  static const background = Color(0xfff7f9fa);
  static const mist = Color(0xffe8eff2);
  static const error = Color(0xffb84a5c);
  static const gold = Color(0xffc78a30);
  static const coral = Color(0xffc95f6d);
  static const blue = Color(0xff4a82b8);
}

// Inicializa preferências, restaura a sessão segura e monta a árvore Flutter.
/// Inicializa os serviços necessários e executa o aplicativo Flutter.
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // As preferências também são carregadas antes da interface e podem interromper a inicialização (achado 202).
  final preferences = await SharedPreferences.getInstance();
  final api = ApiClient(
      baseUrl: apiUrl,
      preferences: preferences,
      secureStorage: PlatformSecureValueStore());
  // Restaura os tokens antes da primeira tela; falha do storage ainda não tem recuperação visual (achado 202).
  await api.restoreSession();
  runApp(TalentumApp(api: api));
}

// Tema e ponto de entrada visual compartilhado por todas as telas do aplicativo.
/// Configura tema, rotas iniciais e estrutura global do aplicativo.
class TalentumApp extends StatelessWidget {
  const TalentumApp({super.key, required this.api});

  final ApiClient api;

  /// Monta o tema global e disponibiliza o cliente da API à navegação do app.
  @override
  Widget build(BuildContext context) {
    const brandScheme = ColorScheme.light(
      primary: TalentumColors.petrol,
      onPrimary: Colors.white,
      primaryContainer: TalentumColors.mist,
      onPrimaryContainer: TalentumColors.petrol,
      secondary: TalentumColors.teal,
      onSecondary: Colors.white,
      secondaryContainer: Color(0xffdcefeb),
      onSecondaryContainer: Color(0xff124d49),
      tertiary: TalentumColors.gold,
      onTertiary: Colors.white,
      error: TalentumColors.error,
      onError: Colors.white,
      surface: Color(0xfffdfefe),
      onSurface: TalentumColors.ink,
      outline: TalentumColors.silver,
      outlineVariant: TalentumColors.line,
    );
    const fieldBorder = OutlineInputBorder(
      borderRadius: BorderRadius.all(Radius.circular(12)),
      borderSide: BorderSide(color: TalentumColors.line),
    );
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Talentum',
      builder: (context, child) => AnnotatedRegion<SystemUiOverlayStyle>(
        value: SystemUiOverlayStyle.dark.copyWith(
          statusBarColor: TalentumColors.background,
          systemNavigationBarColor: TalentumColors.background,
          systemNavigationBarIconBrightness: Brightness.dark,
          systemNavigationBarDividerColor: TalentumColors.line,
        ),
        child: child ?? const SizedBox.shrink(),
      ),
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: brandScheme,
        scaffoldBackgroundColor: TalentumColors.background,
        textTheme: ThemeData.light().textTheme.apply(
              bodyColor: TalentumColors.ink,
              displayColor: TalentumColors.ink,
              fontFamily: 'Roboto',
            ),
        appBarTheme: const AppBarTheme(
          backgroundColor: TalentumColors.background,
          foregroundColor: TalentumColors.petrol,
          surfaceTintColor: Colors.transparent,
          elevation: 0,
          scrolledUnderElevation: 0,
          titleSpacing: 16,
          iconTheme: IconThemeData(color: TalentumColors.petrol),
          actionsIconTheme: IconThemeData(color: TalentumColors.petrol),
          systemOverlayStyle: SystemUiOverlayStyle.dark,
        ),
        cardTheme: CardThemeData(
          color: brandScheme.surface,
          surfaceTintColor: Colors.transparent,
          elevation: 0,
          margin: const EdgeInsets.only(bottom: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
            side: const BorderSide(color: TalentumColors.line),
          ),
        ),
        dividerTheme: const DividerThemeData(
          color: TalentumColors.line,
          thickness: 1,
          space: 24,
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: brandScheme.surface,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
          border: fieldBorder,
          enabledBorder: fieldBorder,
          focusedBorder: const OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            borderSide: BorderSide(color: TalentumColors.petrol, width: 1.6),
          ),
          errorBorder: const OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            borderSide: BorderSide(color: TalentumColors.error),
          ),
          focusedErrorBorder: const OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            borderSide: BorderSide(color: TalentumColors.error, width: 1.6),
          ),
          labelStyle: const TextStyle(color: TalentumColors.muted),
          hintStyle: const TextStyle(color: TalentumColors.muted),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            minimumSize: const Size(48, 50),
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            textStyle: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            minimumSize: const Size(44, 46),
            foregroundColor: TalentumColors.petrol,
            side: const BorderSide(color: TalentumColors.silver),
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            textStyle: const TextStyle(fontWeight: FontWeight.w600),
          ),
        ),
        navigationBarTheme: NavigationBarThemeData(
          backgroundColor: brandScheme.surface,
          indicatorColor: TalentumColors.mist,
          surfaceTintColor: Colors.transparent,
          elevation: 4,
          height: 72,
          labelTextStyle: WidgetStateProperty.resolveWith((states) => TextStyle(
                color: states.contains(WidgetState.selected)
                    ? TalentumColors.petrol
                    : TalentumColors.muted,
                fontWeight: states.contains(WidgetState.selected)
                    ? FontWeight.w700
                    : FontWeight.w500,
                fontSize: 12,
              )),
          iconTheme: WidgetStateProperty.resolveWith((states) => IconThemeData(
                color: states.contains(WidgetState.selected)
                    ? TalentumColors.petrol
                    : TalentumColors.muted,
              )),
        ),
        snackBarTheme: SnackBarThemeData(
          backgroundColor: TalentumColors.petrol,
          contentTextStyle: const TextStyle(color: Colors.white),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          behavior: SnackBarBehavior.floating,
        ),
      ),
      home: TalentumSplashScreen(api: api),
    );
  }
}

/// Apresenta a identidade visual durante a abertura do aplicativo.
class TalentumSplashScreen extends StatefulWidget {
  const TalentumSplashScreen({super.key, required this.api});

  final ApiClient api;

  /// Cria o estado que controla a transição da abertura para o login.
  @override
  State<TalentumSplashScreen> createState() => _TalentumSplashScreenState();
}

/// Controla a exibição e o tempo da tela inicial da marca.
class _TalentumSplashScreenState extends State<TalentumSplashScreen> {
  Timer? _transitionTimer;

  /// Inicializa dados e tarefas que dependem da criação do estado da tela.
  @override
  void initState() {
    super.initState();
    // Mantém a marca visível por um breve intervalo antes de abrir o login.
    _transitionTimer = Timer(const Duration(milliseconds: 900), () {
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute<void>(
        builder: (_) => LoginScreen(api: widget.api),
      ));
    });
  }

  /// Libera controladores e recursos mantidos enquanto a tela esteve aberta.
  @override
  void dispose() {
    _transitionTimer?.cancel();
    super.dispose();
  }

  /// Exibe a abertura animada e aplica as cores da barra de status e navegação.
  @override
  Widget build(BuildContext context) {
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(
        statusBarColor: TalentumColors.petrol,
        systemNavigationBarColor: TalentumColors.petrol,
        systemNavigationBarIconBrightness: Brightness.light,
        systemNavigationBarDividerColor: TalentumColors.petrol,
      ),
      child: Scaffold(
        backgroundColor: TalentumColors.petrol,
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Image.asset(
                'assets/brand/talentum-moeda-prata.png',
                width: 84,
                height: 84,
                fit: BoxFit.contain,
                semanticLabel: 'Logo Talentum',
              ),
              const SizedBox(height: 18),
              const Text(
                'talentum',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 32,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.6,
                ),
              ),
              const SizedBox(height: 28),
              const SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white70),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Exibe a marca Talentum com o tratamento visual compartilhado entre telas.
class _TalentumBrandLockup extends StatelessWidget {
  const _TalentumBrandLockup({this.markSize = 40, this.fontSize = 21});

  final double markSize;
  final double fontSize;

  /// Renderiza o símbolo e o nome Talentum nas dimensões solicitadas.
  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Talentum',
      image: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Image.asset(
            'assets/brand/talentum-moeda-prata.png',
            width: markSize,
            height: markSize,
            fit: BoxFit.contain,
          ),
          const SizedBox(width: 9),
          Text(
            'talentum',
            style: TextStyle(
              color: TalentumColors.petrol,
              fontSize: fontSize,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.5,
            ),
          ),
        ],
      ),
    );
  }
}

// Tela inicial: autenticação por senha e, quando habilitada, biometria.
/// Representa a tela de autenticação do usuário.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.api, this.message});

  final ApiClient api;
  final String? message;

  /// Cria o estado que controla os campos e o envio do login.
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

/// Desenha o gráfico circular de distribuição da carteira.
class InvestmentDonutPainter extends CustomPainter {
  InvestmentDonutPainter({required this.values});

  final List<double> values;
  // A paleta tem oito cores; o operador módulo reutiliza cores em carteiras maiores (achado 97).
  static const colors = <Color>[
    TalentumColors.petrol,
    TalentumColors.teal,
    TalentumColors.gold,
    TalentumColors.coral,
    TalentumColors.blue,
    TalentumColors.silver,
    Color(0xff55a66e),
    Color(0xffd07842),
  ];

  /// Desenha o gráfico customizado dentro dos limites disponíveis.
  @override
  void paint(Canvas canvas, Size size) {
    final total = values.fold<double>(0, (sum, value) => sum + value);
    // Evita calcular arcos proporcionais quando a soma das fatias não é positiva.
    if (total <= 0) return;
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.shortestSide / 2;
    final bounds = Rect.fromCircle(center: center, radius: radius);
    var start = -1.5707963267948966;
    for (var index = 0; index < values.length; index++) {
      final sweep = values[index] / total * 6.283185307179586;
      canvas.drawArc(bounds, start, sweep, true,
          Paint()..color = colors[index % colors.length]);
      start += sweep;
    }
    canvas.drawCircle(center, radius * .59, Paint()..color = Colors.white);
  }

  /// Indica se as novas propriedades exigem redesenhar o gráfico.
  @override
  bool shouldRepaint(covariant InvestmentDonutPainter oldDelegate) =>
      oldDelegate.values != values;
}

/// Apresenta a evolução mensal da carteira em um gráfico de linhas.
class MonthlyInvestmentLineChart extends StatelessWidget {
  const MonthlyInvestmentLineChart({
    super.key,
    required this.points,
    required this.showCdi,
  });

  final List<dynamic> points;
  final bool showCdi;

  /// Exibe a série mensal, as datas cobertas e a legenda das linhas do gráfico.
  @override
  Widget build(BuildContext context) {
    if (points.isEmpty) return const SizedBox.shrink();
    // A API ordena os pontos por data; os extremos mostram o intervalo efetivamente coberto.
    final firstDate = points.first['date']?.toString() ?? '';
    final lastDate = points.last['date']?.toString() ?? '';
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Column(
        children: [
          SizedBox(
            height: 170,
            child: CustomPaint(
              painter: MonthlyInvestmentChartPainter(
                  points: points, showCdi: showCdi),
              child: const SizedBox.expand(),
            ),
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              // O eixo mostra mês-dia extraídos da ISO; avaliar usar formatApiDate para respeitar pt-BR.
              Text(firstDate.length >= 10 ? firstDate.substring(5, 10) : ''),
              Text(lastDate.length >= 10 ? lastDate.substring(5, 10) : ''),
            ],
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 16,
            children: [
              const _ChartLegend(
                  color: TalentumColors.petrol, label: 'Carteira'),
              if (showCdi)
                const _ChartLegend(color: TalentumColors.teal, label: 'CDI'),
            ],
          ),
        ],
      ),
    );
  }
}

/// Mostra a legenda de séries do gráfico mensal.
class _ChartLegend extends StatelessWidget {
  const _ChartLegend({required this.color, required this.label});
  final Color color;
  final String label;

  /// Monta a amostra colorida e o nome da série do gráfico mensal.
  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(width: 14, height: 3, color: color),
          const SizedBox(width: 5),
          Text(label, style: Theme.of(context).textTheme.bodySmall),
        ],
      );
}

/// Desenha as séries e a grade do gráfico de desempenho mensal.
class MonthlyInvestmentChartPainter extends CustomPainter {
  MonthlyInvestmentChartPainter({required this.points, required this.showCdi});

  final List<dynamic> points;
  final bool showCdi;

  /// Obtém um valor numérico de um ponto da série com fallback seguro.
  double _value(dynamic item, String key) =>
      double.tryParse(item[key]?.toString() ?? '') ?? 0;

  /// Desenha o gráfico customizado dentro dos limites disponíveis.
  @override
  void paint(Canvas canvas, Size size) {
    const horizontalPadding = 10.0;
    const verticalPadding = 12.0;
    // Inclui o ponto de equilíbrio no eixo para contextualizar retornos positivos e negativos.
    final values = <double>[0];
    for (final point in points) {
      values.add(_value(point, 'return_percent'));
      if (showCdi && point['cdi_return_percent'] != null) {
        values.add(_value(point, 'cdi_return_percent'));
      }
    }
    var minimum = values.reduce((a, b) => a < b ? a : b);
    var maximum = values.reduce((a, b) => a > b ? a : b);
    // Expande séries quase planas para que pequenas variações ainda apareçam no desenho.
    if (maximum - minimum < .15) {
      maximum += .1;
      minimum -= .1;
    }
    final plotWidth = size.width - horizontalPadding * 2;
    final plotHeight = size.height - verticalPadding * 2;

    /// Converte o índice do ponto em uma coordenada horizontal do gráfico.
    double x(int index) =>
        horizontalPadding +
        (points.length <= 1 ? 0 : index * plotWidth / (points.length - 1));

    /// Converte um valor da série em uma coordenada vertical do gráfico.
    double y(double value) =>
        verticalPadding + (maximum - value) * plotHeight / (maximum - minimum);

    canvas.drawLine(
      Offset(horizontalPadding, y(0)),
      Offset(size.width - horizontalPadding, y(0)),
      Paint()
        ..color = TalentumColors.line
        ..strokeWidth = 1,
    );

    /// Desenha os pontos e segmentos de uma série com a cor informada.
    void drawSeries(String key, Color color) {
      final path = Path();
      var started = false;
      for (var index = 0; index < points.length; index++) {
        final point = points[index];
        // O CDI pode faltar antes da primeira taxa publicada; a linha começa no primeiro ponto disponível.
        if (point[key] == null) continue;
        final offset = Offset(x(index), y(_value(point, key)));
        if (!started) {
          path.moveTo(offset.dx, offset.dy);
          started = true;
        } else {
          path.lineTo(offset.dx, offset.dy);
        }
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = color
          ..strokeWidth = 2.5
          ..strokeCap = StrokeCap.round
          ..strokeJoin = StrokeJoin.round
          ..style = PaintingStyle.stroke,
      );
    }

    drawSeries('return_percent', TalentumColors.petrol);
    if (showCdi) drawSeries('cdi_return_percent', TalentumColors.teal);
  }

  /// Indica se as novas propriedades exigem redesenhar o gráfico.
  @override
  bool shouldRepaint(covariant MonthlyInvestmentChartPainter oldDelegate) =>
      oldDelegate.points != points || oldDelegate.showCdi != showCdi;
}

/// Controla autenticação, biometria e estado da tela de login.
class _LoginScreenState extends State<LoginScreen> {
  final email = TextEditingController();
  final password = TextEditingController();
  bool loading = false;
  bool obscurePassword = true;
  bool biometricAvailable = false;
  bool biometricEnabled = false;
  String? error;
  final localAuthentication = LocalAuthentication();

  /// Inicializa dados e tarefas que dependem da criação do estado da tela.
  @override
  void initState() {
    super.initState();
    error = widget.message;
    _loadBiometricStatus();
  }

  // Carrega a preferência local sem assumir que a sessão ainda está válida.
  /// Carrega a disponibilidade e a preferência biométrica do dispositivo.
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

  /// Libera controladores e recursos mantidos enquanto a tela esteve aberta.
  @override
  void dispose() {
    email.dispose();
    password.dispose();
    super.dispose();
  }

  // Valida os campos, autentica na API e navega para a área do cliente.
  /// Valida as credenciais e inicia a sessão pela API.
  Future<void> submit() async {
    if (loading) return;
    final normalizedEmail = email.text.trim();
    if (normalizedEmail.isEmpty || !normalizedEmail.contains('@')) {
      setState(() => error = 'Informe um e-mail válido.');
      return;
    }
    // A API também exige até 128 caracteres; o formulário só barra senha vazia (achado 67).
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
      // Uma nova autenticação pode pertencer a outra conta; não reaproveita dados do usuário anterior.
      await widget.api.secureStorage.delete(clientCacheKey);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => HomeScreen(api: widget.api)),
      );
    } on ApiException catch (exception) {
      setState(() => error = exception.message);
    } catch (_) {
      // Também recebe falhas do armazenamento seguro, mas as mostra como erro de conexão.
      setState(() => error = 'Não foi possível conectar à API.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  // Desbloqueia uma sessão salva usando a biometria do dispositivo.
  /// Autentica o usuário usando a sessão biométrica já configurada.
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
      // Qualquer erro da consulta à API, inclusive indisponibilidade transitória, apaga a sessão biométrica salva.
      await widget.api.clearSession();
      if (mounted) {
        setState(
            () => error = 'Sua sessão expirou. Entre com sua senha novamente.');
      }
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Não foi possível validar a biometria.');
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  /// Monta a tela de acesso com validação, opção biométrica e estados de erro.
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(28),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 430),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Center(
                    child: _TalentumBrandLockup(markSize: 72, fontSize: 28),
                  ),
                  const SizedBox(height: 28),
                  Text(
                    'Seu patrimônio, acompanhado com clareza.',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                          height: 1.15,
                          color: TalentumColors.petrol,
                        ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'Carteira, metas e planejamento financeiro em um só lugar.',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: TalentumColors.muted,
                          height: 1.45,
                        ),
                  ),
                  const SizedBox(height: 26),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(22),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text('Acesse sua conta',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleLarge
                                  ?.copyWith(fontWeight: FontWeight.w700)),
                          const SizedBox(height: 5),
                          Text('Entre para acompanhar sua vida financeira.',
                              style: Theme.of(context)
                                  .textTheme
                                  .bodySmall
                                  ?.copyWith(color: TalentumColors.muted)),
                          const SizedBox(height: 20),
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
                            // Texto não é região viva e pode não ser anunciado ao aparecer (achado 207).
                            const SizedBox(height: 12),
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: const Color(0xffffeff1),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Icon(Icons.error_outline,
                                      color: TalentumColors.error, size: 19),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(error!,
                                        style: const TextStyle(
                                            color: TalentumColors.error)),
                                  ),
                                ],
                              ),
                            ),
                          ],
                          const SizedBox(height: 20),
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
                          const SizedBox(height: 14),
                          Text(
                            'Acesso protegido. Sua senha é solicitada sempre que o app é aberto.', // O login biométrico permite entrar sem redigitá-la (achado 209).
                            style: Theme.of(context)
                                .textTheme
                                .bodySmall
                                ?.copyWith(color: TalentumColors.muted),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// Área autenticada do cliente: carrega dados, controla abas e edita recursos.
/// Define a tela principal e seus parâmetros de navegação.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.api});

  final ApiClient api;

  /// Cria o estado compartilhado da navegação e dos dados do cliente.
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

/// Mantém os dados, filtros e ações das áreas do aplicativo do cliente.
class _HomeScreenState extends State<HomeScreen> {
  // Preferências e cache local permitem preservar a experiência em falhas temporárias.
  static const hideValuesKey = 'talentum_hide_values';
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
  String investmentTransactionPeriod = 'all';
  String investmentTransactionType = 'all';
  final TextEditingController investmentTransactionSymbolController =
      TextEditingController();
  bool hideValues = false;
  Map<String, dynamic>? user;
  Map<String, dynamic>? dashboard;
  Map<String, dynamic>? investmentPortfolio;
  List<dynamic> investmentTransactions = [];
  Map<String, dynamic>? investmentMonthlyPerformance;
  String? investmentMonthlyPerformanceError;
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
  bool investmentReportBusy = false;
  bool investmentTransactionsBusy = false;
  bool investmentTransactionsHasMore = false;
  String? investmentTransactionsError;
  bool biometricAvailable = false;
  bool biometricEnabled = false;
  String? cachedAt;
  Timer? monthlyPerformanceTimer;

  // Carrega preferências e dispara a leitura inicial dos dados protegidos.
  /// Inicializa dados e tarefas que dependem da criação do estado da tela.
  @override
  void initState() {
    super.initState();
    hideValues = widget.api.preferences.getBool(hideValuesKey) ?? false;
    _loadBiometricStatus();
    load();
    // Atualiza rendimento e CDI a cada hora sem recarregar os demais módulos da carteira.
    monthlyPerformanceTimer = Timer.periodic(const Duration(hours: 1), (_) {
      final clientId = user?['id'];
      if (clientId is int) {
        unawaited(_loadInvestmentMonthlyPerformance(clientId));
      }
    });
  }

  /// Libera controladores e recursos mantidos enquanto a tela esteve aberta.
  @override
  void dispose() {
    monthlyPerformanceTimer?.cancel();
    investmentTransactionSymbolController.dispose();
    super.dispose();
  }

  /// Carrega a disponibilidade e a preferência biométrica do dispositivo.
  Future<void> _loadBiometricStatus() async {
    final available = await deviceSupportsBiometrics();
    if (!mounted) return;
    setState(() {
      biometricAvailable = available;
      biometricEnabled =
          widget.api.preferences.getBool(biometricEnabledKey) ?? false;
    });
  }

  /// Alterna o uso de biometria para entrar no aplicativo.
  Future<void> _toggleBiometric() async {
    if (!biometricAvailable) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content:
                Text('Este dispositivo não possui biometria disponível.')));
      }
      return;
    }
    if (biometricEnabled) {
      // Este ramo não verifica o resultado nem captura exceções da gravação (achado 185).
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
      // setBool pode retornar false sem lançar; o estado abaixo ainda será marcado como ativo (achado 185).
      await widget.api.preferences.setBool(biometricEnabledKey, true);
      if (mounted) {
        setState(() => biometricEnabled = true);
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Acesso biométrico ativado.')));
      }
    } catch (_) {
      // Captura exceções da autenticação/gravação, mas não um resultado false de setBool (achado 185).
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Não foi possível ativar a biometria.')));
      }
    }
  }

  /// Formata a data selecionada no padrão esperado pelo filtro da API.
  String _transactionApiDate(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';

  /// Busca uma página de operações respeitando os filtros atuais.
  Future<List<dynamic>> _loadInvestmentTransactions(int clientId,
      {int offset = 0}) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    // Os períodos de 30 e 90 dias incluem o dia atual na contagem.
    final DateTime? dateFrom = switch (investmentTransactionPeriod) {
      '30d' => today.subtract(const Duration(days: 29)),
      '90d' => today.subtract(const Duration(days: 89)),
      'ytd' => DateTime(today.year),
      _ => null,
    };
    final operationType =
        investmentTransactionType == 'all' ? null : investmentTransactionType;
    return widget.api.investmentTransactions(
      clientId,
      symbol: investmentTransactionSymbolController.text,
      operationType: operationType,
      dateFrom: dateFrom == null ? null : _transactionApiDate(dateFrom),
      dateTo: dateFrom == null ? null : _transactionApiDate(today),
      offset: offset,
    );
  }

  /// Reinicia o histórico de operações com os filtros selecionados.
  Future<void> refreshInvestmentTransactions() async {
    final clientId = user?['id'];
    if (clientId is! int || investmentTransactionsBusy) return;
    setState(() {
      investmentTransactionsBusy = true;
      investmentTransactionsError = null;
    });
    try {
      final transactions = await _loadInvestmentTransactions(clientId);
      if (!mounted) return;
      setState(() {
        investmentTransactions = transactions;
        investmentTransactionsHasMore = transactions.length ==
            100; // Página cheia sugere continuação; um total múltiplo de 100 pode exibir uma carga extra.
      });
    } on ApiException catch (exception) {
      if (!mounted) return;
      setState(() {
        investmentTransactionsError =
            exception.statusCode == 0 || exception.statusCode >= 500
                ? 'Sem conexão para atualizar as operações. Tente novamente.'
                : 'Não foi possível carregar as operações.';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => investmentTransactionsError =
          'Não foi possível carregar as operações. Tente novamente.');
    } finally {
      if (mounted) setState(() => investmentTransactionsBusy = false);
    }
  }

  /// Carrega a próxima página do histórico sem descartar os resultados atuais.
  Future<void> loadMoreInvestmentTransactions() async {
    final clientId = user?['id'];
    if (clientId is! int ||
        investmentTransactionsBusy ||
        !investmentTransactionsHasMore) {
      return;
    }
    setState(() {
      investmentTransactionsBusy = true;
      investmentTransactionsError = null;
    });
    try {
      final transactions = await _loadInvestmentTransactions(clientId,
          offset: investmentTransactions.length);
      if (!mounted) return;
      setState(() {
        investmentTransactions = [...investmentTransactions, ...transactions];
        investmentTransactionsHasMore = transactions.length ==
            100; // A API não informa total; a próxima resposta vazia encerra a paginação.
      });
    } on ApiException catch (exception) {
      if (!mounted) return;
      setState(() {
        investmentTransactionsError =
            exception.statusCode == 0 || exception.statusCode >= 500
                ? 'Sem conexão para carregar mais operações. Tente novamente.'
                : 'Não foi possível carregar mais operações.';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => investmentTransactionsError =
          'Não foi possível carregar mais operações. Tente novamente.');
    } finally {
      if (mounted) setState(() => investmentTransactionsBusy = false);
    }
  }

  /// Remove filtros e recarrega o histórico completo de operações.
  Future<void> clearInvestmentTransactionFilters() async {
    setState(() {
      investmentTransactionPeriod = 'all';
      investmentTransactionType = 'all';
      investmentTransactionSymbolController.clear();
      investmentTransactionsHasMore = false;
    });
    await refreshInvestmentTransactions();
  }

  // Busca o usuário e os módulos independentes em paralelo para reduzir a espera.
  /// Carrega os dados necessários para atualizar as áreas da tela principal.
  Future<void> load() async {
    // Descarta uma nova carga em andamento, inclusive as solicitadas após uma gravação (achado 28).
    if (loading) return;
    int? authenticatedClientId;
    if (mounted) setState(() => loading = true);
    try {
      if (mounted) setState(() => error = null);
      final currentUser = await widget.api.me();
      final role = currentUser['role']?.toString();
      // As áreas e os endpoints seguintes pertencem ao fluxo de cliente, não ao Advisor.
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
      authenticatedClientId = id;
      // Future.wait falha como conjunto: uma consulta obrigatória com erro leva ao fallback geral abaixo.
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
        _loadInvestmentTransactions(id),
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
        investmentTransactions = results[12] as List<dynamic>;
        investmentTransactionsHasMore = investmentTransactions.length == 100;
      });
      final alerts = await _loadMarketAlerts();
      if (mounted) setState(() => marketAlerts = alerts);
      final currentSuitability = await _loadSuitability();
      if (mounted) setState(() => suitability = currentSuitability);
      await _saveClientCache(currentUser, results, currentSuitability);
      unawaited(_loadInvestmentMonthlyPerformance(id));
    } on ApiException catch (exception) {
      if (widget.api.accessToken == null) {
        try {
          await widget.api.secureStorage.delete(clientCacheKey);
        } catch (_) {
          // A falha no storage não mantém a tela autenticada após a sessão ser invalidada.
        }
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
      // Usa o cache somente em falhas de conexão/servidor, não em erros funcionais da API.
      if ((exception.statusCode == 0 || exception.statusCode >= 500) &&
          await _restoreClientCache(expectedUserId: authenticatedClientId)) {
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
      // Também trata erros inesperados como indisponibilidade se houver cache (achado 186).
      if (widget.api.accessToken != null &&
          await _restoreClientCache(expectedUserId: authenticatedClientId)) {
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

  /// Consulta notificações e atualiza a lista apresentada ao usuário.
  Future<List<dynamic>> _loadNotifications() async {
    try {
      return await widget.api.notifications();
    } catch (_) {
      // Fallback atual: erro do endpoint aparece como lista sem notificações.
      return <dynamic>[];
    }
  }

  /// Carrega opções de recebimento de notificações.
  Future<Map<String, dynamic>> _loadNotificationPreferences() async {
    try {
      return await widget.api.notificationPreferences();
    } catch (_) {
      // Usa padrões sem distinguir falha de leitura; salvar a tela inteira pode sobrescrever preferências (achado 31).
      return Map<String, dynamic>.from(defaultNotificationPreferences);
    }
  }

  /// Busca alertas de preço vinculados à carteira do usuário.
  Future<List<dynamic>> _loadMarketAlerts() async {
    try {
      return await widget.api.marketAlerts();
    } catch (_) {
      // Fallback atual: falha na consulta é apresentada como ausência de alertas.
      return <dynamic>[];
    }
  }

  /// Consulta a avaliação de perfil mais recente do usuário.
  Future<Map<String, dynamic>?> _loadSuitability() async {
    try {
      return await widget.api.suitability();
    } catch (_) {
      // Fallback atual: falha na consulta é apresentada como avaliação inexistente.
      return null;
    }
  }

  /// Atualiza a série mensal de desempenho da carteira.
  Future<void> _loadInvestmentMonthlyPerformance(int clientId) async {
    try {
      final result = await widget.api.investmentMonthlyPerformance(clientId);
      if (!mounted) return;
      setState(() {
        investmentMonthlyPerformance = result;
        investmentMonthlyPerformanceError = null;
      });
      try {
        final raw = await widget.api.secureStorage.read(clientCacheKey);
        if (raw != null) {
          final cache = jsonDecode(raw) as Map<String, dynamic>;
          cache['investment_monthly_performance'] = result;
          await widget.api.secureStorage
              .write(clientCacheKey, jsonEncode(cache));
        }
      } catch (_) {
        // A falha de cache não impede a atualização online da carteira.
      }
    } on ApiException catch (exception) {
      if (!mounted) return;
      // Conserva o valor anterior, mas a tela prioriza esta mensagem e oculta o gráfico (achado 178).
      setState(() => investmentMonthlyPerformanceError = exception.message);
    }
  }

  /// Armazena os dados do cliente para restaurar a tela quando a API falhar.
  Future<void> _saveClientCache(Map<String, dynamic> currentUser,
      List<dynamic> results, Map<String, dynamic>? currentSuitability) async {
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
            'investment_transactions': results[12],
            'market_alerts': marketAlerts,
            'suitability': currentSuitability,
            'cached_at': DateTime.now().toIso8601String(),
          }));
    } catch (_) {
      // A falha no cache não pode impedir o uso dos dados online.
    }
  }

  /// Restaura dados de interface previamente armazenados no dispositivo.
  Future<bool> _restoreClientCache({int? expectedUserId}) async {
    try {
      final raw = await widget.api.secureStorage.read(clientCacheKey);
      if (raw == null) return false;
      final payload = jsonDecode(raw) as Map<String, dynamic>;
      final cachedUser = Map<String, dynamic>.from(payload['user'] as Map);
      final cachedDashboard =
          Map<String, dynamic>.from(payload['dashboard'] as Map);
      final cachedUserId = cachedUser['id'];
      // Dados de outro papel ou de outra conta nunca substituem a tela autenticada atual.
      if (cachedUser['role'] != 'client' ||
          cachedUserId is! int ||
          (expectedUserId != null && cachedUserId != expectedUserId)) {
        return false;
      }
      if (!mounted) return false;
      setState(() {
        user = cachedUser;
        dashboard = cachedDashboard;
        investmentPortfolio = Map<String, dynamic>.from(
            payload['investment_portfolio'] as Map? ?? {});
        investmentTransactions = List<dynamic>.from(
            payload['investment_transactions'] as List? ?? []);
        investmentMonthlyPerformance =
            payload['investment_monthly_performance'] == null
                ? null
                : Map<String, dynamic>.from(
                    payload['investment_monthly_performance'] as Map);
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
      // Cache inválido ou inacessível não substitui o erro original do carregamento.
      return false;
    }
  }

  // Formatações e rótulos abaixo isolam regras de apresentação dos widgets.
  /// Formata valores monetários para exibição na tela.
  String money(dynamic value) => 'R\$ ${formatBrazilianNumber(value)}';

  /// Formata o preço de referência de um alerta de mercado.
  String alertPrice(Map<String, dynamic> alert) {
    // O preço-alvo não consulta hideValues e permanece visível com a preferência ativa.
    final value = formatBrazilianNumber(alert['target_price']);
    // A API só entrega o mercado; alertas globais são assumidos como USD na tela.
    return alert['market'] == 'global' ? 'US\$ $value' : 'R\$ $value';
  }

  /// Traduz a condição de disparo do alerta para um texto amigável.
  String marketAlertConditionLabel(dynamic value) =>
      value == 'at_or_above' ? 'Atingir ou superar' : 'Atingir ou ficar abaixo';

  /// Traduz o estado do alerta para a interface.
  String marketAlertStatusLabel(dynamic value) => switch (value.toString()) {
        'active' => 'Ativo',
        'paused' => 'Pausado',
        'triggered' => 'Disparado',
        'cancelled' => 'Desativado',
        _ => 'Desconhecido',
      };

  /// Formata uma data sem horário para apresentação ao usuário.
  String dateLabel(dynamic value) {
    final date = DateTime.tryParse(value?.toString() ?? '');
    if (date == null) return value?.toString() ?? '';
    final day = date.day.toString().padLeft(2, '0');
    final month = date.month.toString().padLeft(2, '0');
    return '$day/$month/${date.year}';
  }

  /// Formata data e horário para apresentação ao usuário.
  String dateTimeLabel(dynamic value) {
    final date = DateTime.tryParse(value?.toString() ?? '');
    if (date == null) return value?.toString() ?? '';
    final day = date.day.toString().padLeft(2, '0');
    final month = date.month.toString().padLeft(2, '0');
    final hour = date.hour.toString().padLeft(2, '0');
    final minute = date.minute.toString().padLeft(2, '0');
    return '$day/$month/${date.year} às $hour:$minute';
  }

  /// Exibe uma mensagem de validação ou falha no formulário atual.
  void showFormError(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  /// Oculta ou formata um valor conforme a preferência de privacidade.
  String privateMoney(dynamic value) =>
      hideValues ? 'R\$ ••••••' : money(value);

  /// Converte bytes em uma unidade legível para identificar o tamanho do arquivo.
  String fileSizeLabel(dynamic value) {
    final bytes = int.tryParse(value?.toString() ?? '') ?? 0;
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  /// Traduz o estado da meta para um rótulo em português.
  String goalStatusLabel(dynamic value) => switch (value.toString()) {
        'paused' => 'Pausada',
        'completed' => 'Concluída',
        _ => 'Ativa',
      };

  /// Traduz o estado de uma ação para um rótulo em português.
  String actionStatusLabel(dynamic value) => switch (value.toString()) {
        'in_progress' => 'Em andamento',
        'completed' => 'Concluída',
        _ => 'Planejada',
      };

  /// Traduz a prioridade de uma ação para um rótulo em português.
  String actionPriorityLabel(dynamic value) => switch (value.toString()) {
        'high' => 'Prioridade alta',
        'low' => 'Prioridade baixa',
        _ => 'Prioridade média',
      };

  /// Escolhe uma cor visual conforme a prioridade da ação.
  Color actionPriorityColor(dynamic value) => switch (value.toString()) {
        'high' => TalentumColors.error,
        'low' => TalentumColors.teal,
        _ => TalentumColors.gold,
      };

  /// Encontra o nome da meta vinculada a uma ação do plano.
  String? goalTitleForAction(dynamic goalId) {
    if (goalId == null) return null;
    for (final goal in goals) {
      if (goal['id'] == goalId) return goal['title']?.toString();
    }
    return null;
  }

  /// Verifica se uma ação não concluída já passou da data limite.
  bool isOverdueAction(Map<String, dynamic> action) {
    final dueDate = DateTime.tryParse(action['due_date']?.toString() ?? '');
    if (dueDate == null || action['status'] == 'completed') return false;
    final endOfDueDay =
        DateTime(dueDate.year, dueDate.month, dueDate.day, 23, 59, 59);
    return endOfDueDay.isBefore(DateTime.now());
  }

  // A ordenação mantém pendências e vencimentos mais importantes no topo.
  /// Ordena ações por atraso, conclusão, prioridade, prazo e título.
  List<dynamic> orderedActionPlan() {
    final actions = List<dynamic>.from(actionPlan);
    const priorityOrder = {'high': 0, 'medium': 1, 'low': 2};
    actions.sort((leftValue, rightValue) {
      final left = Map<String, dynamic>.from(leftValue as Map);
      final right = Map<String, dynamic>.from(rightValue as Map);
      final leftOverdue = isOverdueAction(left) ? 1 : 0;
      final rightOverdue = isOverdueAction(right) ? 1 : 0;
      if (leftOverdue != rightOverdue) {
        return rightOverdue.compareTo(leftOverdue);
      }
      final leftCompleted = left['status'] == 'completed' ? 1 : 0;
      final rightCompleted = right['status'] == 'completed' ? 1 : 0;
      if (leftCompleted != rightCompleted) {
        return leftCompleted.compareTo(rightCompleted);
      }
      final leftPriority = priorityOrder[left['priority']?.toString()] ?? 3;
      final rightPriority = priorityOrder[right['priority']?.toString()] ?? 3;
      if (leftPriority != rightPriority) {
        return leftPriority.compareTo(rightPriority);
      }
      final leftDue = left['due_date']?.toString();
      final rightDue = right['due_date']?.toString();
      if (leftDue != null && rightDue != null && leftDue != rightDue) {
        return leftDue.compareTo(rightDue);
      }
      if (leftDue != null && rightDue == null) return -1;
      if (leftDue == null && rightDue != null) return 1;
      return (left['title']?.toString() ?? '')
          .compareTo(right['title']?.toString() ?? '');
    });
    return actions;
  }

  /// Verifica se uma meta não concluída passou da data definida.
  bool isOverdueGoal(Map<String, dynamic> goal) {
    final targetDate = DateTime.tryParse(goal['target_date']?.toString() ?? '');
    if (targetDate == null || goal['status'] == 'completed') return false;
    final endOfTargetDay =
        DateTime(targetDate.year, targetDate.month, targetDate.day, 23, 59, 59);
    return endOfTargetDay.isBefore(DateTime.now());
  }

  /// Ordena metas por atraso, conclusão, prazo e título.
  List<dynamic> orderedGoals(Iterable<dynamic> source) {
    final items = source.toList();
    items.sort((leftValue, rightValue) {
      final left = Map<String, dynamic>.from(leftValue as Map);
      final right = Map<String, dynamic>.from(rightValue as Map);
      final leftOverdue = isOverdueGoal(left) ? 1 : 0;
      final rightOverdue = isOverdueGoal(right) ? 1 : 0;
      if (leftOverdue != rightOverdue) {
        return rightOverdue.compareTo(leftOverdue);
      }
      final leftCompleted = left['status'] == 'completed' ? 1 : 0;
      final rightCompleted = right['status'] == 'completed' ? 1 : 0;
      if (leftCompleted != rightCompleted) {
        return leftCompleted.compareTo(rightCompleted);
      }
      final leftDate = left['target_date']?.toString();
      final rightDate = right['target_date']?.toString();
      if (leftDate != null && rightDate != null && leftDate != rightDate) {
        return leftDate.compareTo(rightDate);
      }
      if (leftDate != null && rightDate == null) return -1;
      if (leftDate == null && rightDate != null) return 1;
      return (left['title']?.toString() ?? '')
          .compareTo(right['title']?.toString() ?? '');
    });
    return items;
  }

  /// Seleciona o ícone que representa o estado atual de uma ação.
  IconData actionStatusIcon(dynamic value) => switch (value.toString()) {
        'in_progress' => Icons.timelapse_outlined,
        'completed' => Icons.check_circle_outline,
        _ => Icons.radio_button_unchecked,
      };

  // Alterna a ocultação de valores sensíveis apenas na interface local.
  /// Alterna a exibição de valores financeiros privados.
  Future<void> toggleValueVisibility() async {
    setState(() => hideValues = !hideValues);
    // A preferência visual muda antes da gravação; uma falha local escapa sem reverter o estado.
    await widget.api.preferences.setBool(hideValuesKey, hideValues);
  }

  // Constrói a navegação principal e escolhe a aba atualmente selecionada.
  /// Monta a navegação do cliente, o menu lateral e o conteúdo da área ativa.
  @override
  Widget build(BuildContext context) {
    final labels = [
      'Início',
      'Carteira',
      'Patrimônio',
      'Metas',
      'Documentos',
      'Relatórios',
      'Perfil'
    ];
    // Relaciona cada destino visível na barra inferior ao índice lógico da tela.
    const bottomSections = [0, 1, 5, 6];
    final bottomIndex = bottomSections.indexOf(tab);
    return Scaffold(
      drawer: _buildNavigationDrawer(),
      appBar: AppBar(
        title: const _TalentumBrandLockup(markSize: 34, fontSize: 20),
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
      bottomNavigationBar: bottomIndex < 0
          ? null
          : NavigationBar(
              selectedIndex: bottomIndex,
              labelBehavior:
                  NavigationDestinationLabelBehavior.onlyShowSelected,
              onDestinationSelected: (value) =>
                  setState(() => tab = bottomSections[value]),
              destinations: const [
                  NavigationDestination(
                      icon: Icon(Icons.home_outlined),
                      selectedIcon: Icon(Icons.home),
                      label: 'Início'),
                  NavigationDestination(
                      icon: Icon(Icons.show_chart),
                      selectedIcon: Icon(Icons.show_chart),
                      label: 'Carteira'),
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

  /// Constrói o menu lateral com navegação e atalhos do cliente.
  Widget _buildNavigationDrawer() {
    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            Container(
              height: 100,
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
              color: TalentumColors.petrol,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Image.asset(
                        'assets/brand/talentum-moeda-prata.png',
                        width: 34,
                        height: 34,
                        fit: BoxFit.contain,
                      ),
                      const SizedBox(width: 8),
                      const Text(
                        'talentum',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      user?['name']?.toString() ?? 'Área do cliente',
                      textAlign: TextAlign.left,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView(
                padding: EdgeInsets.zero,
                children: [
                  _drawerGroupLabel('PRINCIPAL'),
                  _drawerDestination(
                      icon: Icons.home_outlined,
                      label: 'Início',
                      destination: 0),
                  _drawerDestination(
                      icon: Icons.show_chart,
                      label: 'Carteira',
                      destination: 1),
                  _drawerDestination(
                      icon: Icons.description_outlined,
                      label: 'Relatórios',
                      destination: 5),
                  _drawerDestination(
                      icon: Icons.person_outline,
                      label: 'Perfil e segurança',
                      destination: 6),
                  _drawerGroupLabel('PLANEJAMENTO'),
                  _drawerDestination(
                      icon: Icons.pie_chart_outline,
                      label: 'Patrimônio',
                      destination: 2),
                  _drawerDestination(
                      icon: Icons.flag_outlined,
                      label: 'Metas',
                      destination: 3),
                  _drawerDestination(
                      icon: Icons.checklist_outlined,
                      label: 'Plano de ação',
                      onTap: () => unawaited(openActionPlan())),
                  _drawerGroupLabel('DOCUMENTOS E INVESTIMENTOS'),
                  _drawerDestination(
                      icon: Icons.folder_outlined,
                      label: 'Documentos',
                      destination: 4),
                  _drawerDestination(
                      icon: Icons.auto_awesome_outlined,
                      label: 'Carteira sugerida',
                      onTap: () => unawaited(openSuitabilityQuestionnaire())),
                  _drawerGroupLabel('ACOMPANHAMENTO'),
                  _drawerDestination(
                      icon: Icons.notifications_outlined,
                      label: 'Central de alertas',
                      onTap: () => unawaited(openNotificationHistory())),
                  const Divider(height: 18),
                  ListTile(
                    leading: const Icon(Icons.logout),
                    title: const Text('Sair da conta'),
                    onTap: () {
                      // Fecha o drawer imediatamente e inicia a saída sem aguardar a navegação.
                      Navigator.of(context).pop();
                      unawaited(signOut());
                    },
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Constrói o título visual de um grupo no menu lateral.
  Widget _drawerGroupLabel(String label) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 2),
        child: Text(
          label,
          style: const TextStyle(
            color: TalentumColors.muted,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.8,
          ),
        ),
      );

  /// Constrói um item do menu que seleciona uma aba ou executa uma ação contextual.
  Widget _drawerDestination({
    required IconData icon,
    required String label,
    int? destination,
    VoidCallback? onTap,
  }) {
    final selected = destination != null && tab == destination;
    return ListTile(
      dense: true,
      visualDensity: const VisualDensity(vertical: -2),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16),
      minLeadingWidth: 32,
      selected: selected,
      leading: Icon(icon, size: 21),
      title: Text(label),
      onTap: () {
        // Fecha o drawer antes de executar uma ação ou trocar a aba selecionada.
        Navigator.of(context).pop();
        if (onTap != null) {
          onTap();
        } else if (destination != null) {
          setState(() => tab = destination);
        }
      },
    );
  }

  // Seleciona o conteúdo da aba sem duplicar a estrutura do scaffold principal.
  /// Seleciona e constrói o conteúdo correspondente à área ativa.
  Widget _content() {
    if (tab == 1) return _investmentPortfolioView();
    if (tab == 2) return _patrimonyView();
    if (tab == 3) return _goalsView();
    if (tab == 4) return _documentsView();
    if (tab == 5) return _reportsView();
    if (tab == 6) return _profileView();
    // As abas secundárias são renderizadas acima; o restante usa o resumo do dashboard.
    final data = dashboard!;
    final categories =
        List<dynamic>.from(data['patrimony_by_category'] as List? ?? []);
    // A API usa null quando não há perfil; este fallback transforma ausência em zero (achado 142).
    final monthlyIncome =
        double.tryParse(data['monthly_income']?.toString() ?? '') ?? 0;
    final monthlyExpenses =
        double.tryParse(data['monthly_expenses']?.toString() ?? '') ?? 0;
    // O saldo exibido é uma estimativa simples, sem considerar movimentações futuras.
    final monthlyBalance = monthlyIncome - monthlyExpenses;
    // A função ordena atrasos, pendências, prioridade e prazo antes do resumo.
    final orderedActions = orderedActionPlan();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      // A data indica que o conteúdo veio do cache local em vez de uma carga atual.
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
                    _summaryRow('Renda', privateMoney(monthlyIncome),
                        TalentumColors.teal),
                    _summaryRow('Despesas', privateMoney(monthlyExpenses),
                        Colors.orange),
                    const Divider(height: 22),
                    _summaryRow(
                        'Saldo estimado',
                        privateMoney(monthlyBalance),
                        monthlyBalance >= 0
                            ? TalentumColors.teal
                            : TalentumColors.error)
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
                        TalentumColors.petrol),
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
      // Percentuais e barras permanecem visíveis mesmo quando montantes estão ocultos.
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
                                      ? TalentumColors.error
                                      : null))
                  ]),
              trailing: Text('${goal['percentage']}%'))),
      const SizedBox(height: 12),
      const Text('Plano de ação'),
      const SizedBox(height: 8),
      if (actionPlan.isEmpty)
        const Text('Nenhuma ação definida pelo seu Advisor.'),
      // O painel mostra só as três primeiras ações da lista já priorizada.
      ...orderedActions.take(3).map((action) => ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(actionStatusIcon(action['status']),
              color: isOverdueAction(Map<String, dynamic>.from(action))
                  ? TalentumColors.error
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
  /// Constrói o cartão com avisos recentes do usuário.
  Widget _notificationsCard() {
    // O indicador conta somente a lista carregada, limitada a 50 pela API por padrão.
    // O cartão mostra até três avisos não lidos que correspondem ao filtro atual.
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
                      color: TalentumColors.error, fontWeight: FontWeight.w700))
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
              // Aplica o filtro selecionado à lista carregada e atualiza a tela.
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
                // Marca o aviso como lido e leva o cliente à área relacionada.
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
  /// Constrói a seção de alertas de preço ativos.
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
            // Mantém o resumo compacto; o histórico abre a lista completa quando houver mais de três.
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

  // Resume a carteira sugerida à divisão e aos ativos de referência.
  /// Apresenta a avaliação, recomendação e ações de suitability.
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
                  'Responda ao questionário para ver a divisão da carteira e os ativos sugeridos.'),
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
                  child: Text('Carteira sugerida',
                      style: Theme.of(context).textTheme.titleMedium),
                ),
                IconButton(
                  tooltip: 'Refazer questionário',
                  onPressed: openSuitabilityQuestionnaire,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            if (recommendation['advisor_proposal_published_at'] != null)
              const Padding(
                padding: EdgeInsets.only(bottom: 10),
                child: Text(
                  'Sugestão personalizada do Advisor',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
            const Text('Divisão da carteira',
                style: TextStyle(fontWeight: FontWeight.w700)),
            if (allocations.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('A divisão sugerida ainda não está disponível.'),
              ),
            // Cada categoria mostra seu peso e, quando disponíveis, subcategorias e ativos.
            ...allocations.map((item) {
              final allocation = Map<String, dynamic>.from(item as Map);
              final percentage =
                  double.tryParse(allocation['percentage']?.toString() ?? '') ??
                      0;
              final suballocations = List<dynamic>.from(
                  allocation['suballocations'] as List? ?? <dynamic>[]);
              return Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(child: Text(allocation['label'].toString())),
                        Text('${percentage.toStringAsFixed(0)}%',
                            style:
                                const TextStyle(fontWeight: FontWeight.w700)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    LinearProgressIndicator(value: percentage / 100),
                    ...suballocations.map((segment) {
                      final details = Map<String, dynamic>.from(segment as Map);
                      final examples = List<dynamic>.from(
                          details['examples'] as List? ?? <dynamic>[]);
                      return Padding(
                        padding: const EdgeInsets.only(left: 10, top: 8),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                                '${details['label']} — ${details['percentage']}%'),
                            if (examples.isNotEmpty)
                              Text('Ativos sugeridos: ${examples.join(', ')}',
                                  style: const TextStyle(fontSize: 12)),
                          ],
                        ),
                      );
                    }),
                    // Mostra à parte os ativos individuais que o Advisor selecionou para a proposta.
                    ...List<dynamic>.from(
                            allocation['advisor_assets'] as List? ??
                                <dynamic>[])
                        .map((item) {
                      final asset = Map<String, dynamic>.from(item as Map);
                      return Padding(
                        padding: const EdgeInsets.only(left: 10, top: 8),
                        child: Text(
                          'Selecionado pelo Advisor: ${asset['symbol']} — ${asset['name']}',
                          style: const TextStyle(fontSize: 12),
                        ),
                      );
                    }),
                  ],
                ),
              );
            }),
            // Só permite aceite quando a proposta do Advisor foi publicada e aprovada e aguarda resposta.
            if (recommendation['advisor_proposal_published_at'] != null &&
                assessment['status'] == 'approved' &&
                assessment['client_response'] == 'pending') ...[
              const SizedBox(height: 14),
              FilledButton.icon(
                onPressed: () => acceptAdvisorSuitability(assessment),
                icon: const Icon(Icons.check_circle_outline),
                label: const Text('Aceitar sugestão do Advisor'),
              ),
            ] else if (assessment['client_response'] == 'accepted') ...[
              const SizedBox(height: 12),
              const Text('Você aceitou esta sugestão do Advisor.'),
            ],
          ],
        ),
      ),
    );
  }

  /// Registra a confirmação do cliente para a carteira sugerida pelo assessor.
  Future<void> acceptAdvisorSuitability(Map<String, dynamic> assessment) async {
    final assessmentId = assessment['id'];
    if (assessmentId is! int) return;
    try {
      final updated = await widget.api.respondToSuitability(
        assessmentId: assessmentId,
        response: 'accepted',
      );
      if (!mounted) return;
      setState(() => suitability = updated);
      // Invalida o cache local depois de o aceite já ter sido confirmado pela API.
      await widget.api.secureStorage.delete(clientCacheKey);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Sugestão aceita e registrada na Carteira sugerida.'),
        ));
      }
    } on ApiException catch (exception) {
      if (mounted) showFormError(exception.message);
    }
  }

  /// Abre o questionário, coleta respostas e envia a avaliação.
  Future<void> openSuitabilityQuestionnaire() async {
    Map<String, dynamic> definition;
    try {
      definition = await widget.api.suitabilityQuestionnaire();
    } on ApiException catch (exception) {
      if (mounted) showFormError(exception.message);
      return;
    }

    final objectives =
        List<dynamic>.from(definition['objectives'] as List? ?? <dynamic>[]);
    final questions =
        List<dynamic>.from(definition['questions'] as List? ?? <dynamic>[]);
    final financialSituation = Map<String, dynamic>.from(
      definition['financial_situation'] as Map? ?? <String, dynamic>{},
    );
    final financialDataVersion =
        financialSituation['data_version']?.toString() ?? '';
    final hasFinancialProfile =
        financialSituation['has_financial_profile'] == true;
    final patrimonyByCategory = List<dynamic>.from(
        financialSituation['patrimony_by_category'] as List? ?? <dynamic>[]);
    final activeGoals = List<dynamic>.from(
        financialSituation['active_goals'] as List? ?? <dynamic>[]);
    if (objectives.isEmpty || questions.isEmpty) {
      if (mounted) showFormError('O questionário ainda não está disponível.');
      return;
    }
    if (!mounted) return;
    var objective = suitability?['objective']?.toString() ??
        Map<String, dynamic>.from(objectives.first as Map)['value']
            .toString(); // O objetivo salvo não é validado contra as opções atuais (achado 190).
    final answers = <String, String>{};
    // Reaproveita as respostas anteriores sem filtrar chaves que possam ter saído do questionário (achado 188).
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
        // Exige confirmação explícita do retrato financeiro atual antes de enviar as respostas.
        var financialConfirmed = false;
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
                    Card(
                      color:
                          Theme.of(context).colorScheme.surfaceContainerHighest,
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Sua situação financeira',
                                style: Theme.of(context).textTheme.titleMedium),
                            const SizedBox(height: 8),
                            Text(
                                'Renda mensal: ${privateMoney(financialSituation['monthly_income'] ?? 0)}'),
                            Text(
                                'Despesas mensais: ${privateMoney(financialSituation['monthly_expenses'] ?? 0)}'),
                            Text(
                                'Saldo mensal: ${privateMoney(financialSituation['monthly_surplus'] ?? 0)}'),
                            Text(
                                'Patrimônio cadastrado (sem dívidas): ${privateMoney(financialSituation['patrimony_total'] ?? 0)}'),
                            if (patrimonyByCategory.isNotEmpty) ...[
                              const SizedBox(height: 6),
                              ...patrimonyByCategory.map((entry) {
                                final category =
                                    Map<String, dynamic>.from(entry as Map);
                                return Text(
                                    '${category['category']}: ${privateMoney(category['value'] ?? 0)}');
                              }),
                            ] else
                              const Text(
                                  'Nenhum item de patrimônio cadastrado.'),
                            const SizedBox(height: 6),
                            Text(activeGoals.isEmpty
                                ? 'Nenhuma meta ativa cadastrada.'
                                : 'Metas ativas: ${activeGoals.map((entry) => Map<String, dynamic>.from(entry as Map)['title']).join(', ')}'),
                            if (!hasFinancialProfile) ...[
                              const SizedBox(height: 8),
                              const Text(
                                  'Seu perfil financeiro ainda não foi cadastrado. Peça ao Advisor para preenchê-lo antes de continuar.'),
                            ],
                          ],
                        ),
                      ),
                    ),
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      value: financialConfirmed,
                      onChanged: submitting || !hasFinancialProfile
                          ? null
                          : (value) => setDialogState(
                              () => financialConfirmed = value ?? false),
                      title: const Text(
                          'Confirmo que renda, despesas, patrimônio e metas exibidos estão atualizados. Se algo estiver faltando, pedirei ao Advisor para corrigir antes de gerar.'),
                      controlAffinity: ListTileControlAffinity.leading,
                    ),
                    const SizedBox(height: 8),
                    DropdownButtonFormField<String>(
                      isExpanded: true,
                      initialValue: objective,
                      decoration: const InputDecoration(
                        label: Text(
                          'Objetivo principal',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      items: objectives.map((item) {
                        final value = Map<String, dynamic>.from(item as Map);
                        return DropdownMenuItem<String>(
                          value: value['value'].toString(),
                          child: Text(
                            value['label'].toString(),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        );
                      }).toList(),
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
                      // Respostas múltiplas são salvas em ordem das opções; "none" exclui as demais.
                      if (question['selection_mode'] == 'multiple') {
                        return Card(
                          margin: const EdgeInsets.only(bottom: 14),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(vertical: 8),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Padding(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 16),
                                  child: Text(
                                    question['label'].toString(),
                                    style:
                                        Theme.of(context).textTheme.titleSmall,
                                  ),
                                ),
                                Padding(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 16, vertical: 4),
                                  child: Text(
                                    question['description']?.toString() ?? '',
                                    style:
                                        Theme.of(context).textTheme.bodySmall,
                                  ),
                                ),
                                ...options.map((option) {
                                  final choice =
                                      Map<String, dynamic>.from(option as Map);
                                  final value = choice['value'].toString();
                                  final selectedValues = (answers[key] ?? '')
                                      .split(',')
                                      .where((entry) => entry.isNotEmpty)
                                      .toSet();
                                  return CheckboxListTile(
                                    dense: true,
                                    value: selectedValues.contains(value),
                                    title: Text(choice['label'].toString()),
                                    controlAffinity:
                                        ListTileControlAffinity.leading,
                                    onChanged: submitting
                                        ? null
                                        : (checked) => setDialogState(() {
                                              if (value == 'none' &&
                                                  checked == true) {
                                                selectedValues
                                                  ..clear()
                                                  ..add('none');
                                              } else {
                                                selectedValues.remove('none');
                                                if (checked == true) {
                                                  selectedValues.add(value);
                                                } else {
                                                  selectedValues.remove(value);
                                                }
                                              }
                                              if (selectedValues.isEmpty) {
                                                answers.remove(key);
                                              } else {
                                                final ordered = options
                                                    .map((entry) => Map<String,
                                                                dynamic>.from(
                                                            entry
                                                                as Map)['value']
                                                        .toString())
                                                    .where(
                                                        selectedValues.contains)
                                                    .toList();
                                                answers[key] =
                                                    ordered.join(',');
                                              }
                                            }),
                                  );
                                }),
                              ],
                            ),
                          ),
                        );
                      }
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 14),
                        child: DropdownButtonFormField<String>(
                          isExpanded: true,
                          initialValue: selected,
                          decoration: InputDecoration(
                            label: Text(
                              question['label'].toString(),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            helperText: question['description']?.toString(),
                            helperMaxLines: 2,
                          ),
                          items: options.map((option) {
                            final value =
                                Map<String, dynamic>.from(option as Map);
                            return DropdownMenuItem<String>(
                              value: value['value'].toString(),
                              child: Text(
                                value['label'].toString(),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            );
                          }).toList(),
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
                    Text(
                      definition['disclaimer']?.toString() ??
                          'Carteira educativa; aguarde a validação do Advisor antes de tomar decisões.',
                      style: const TextStyle(fontSize: 12),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed:
                    submitting ? null : () => Navigator.pop(dialogContext),
                child: const Text('Cancelar'),
              ),
              // A habilitação compara quantidades; a API também valida se cada chave esperada está presente.
              FilledButton(
                onPressed: submitting ||
                        !hasFinancialProfile ||
                        !financialConfirmed ||
                        answers.length != questions.length
                    ? null
                    : () async {
                        setDialogState(() => submitting = true);
                        try {
                          final submitted = await widget.api.submitSuitability(
                            objective: objective,
                            answers: answers,
                            financialDataVersion: financialDataVersion,
                            confirmFinancialSituation: financialConfirmed,
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
    // Atualiza a avaliação; o risco no perfil financeiro local continua até uma nova carga.
    setState(() => suitability = result);
    // Se a limpeza falhar, a avaliação já foi salva e o aviso de sucesso não será exibido (achado 119).
    await widget.api.secureStorage.delete(clientCacheKey);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Questionário salvo e carteira sugerida gerada.')));
    }
  }

  /// Cancela um alerta de preço após a ação do usuário.
  Future<void> cancelMarketAlert(Map<String, dynamic> alert) async {
    try {
      await widget.api.cancelMarketAlert(alert['id'] as int);
      await load();
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  /// Constrói a linha visual de um alerta e suas ações.
  Widget _marketAlertTile(Map<String, dynamic> alert, {VoidCallback? onEdit}) {
    final status = alert['status']?.toString();
    final editable = status != 'cancelled';
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        status == 'triggered'
            ? Icons.notifications_active
            : Icons.trending_up_outlined,
        color:
            status == 'triggered' ? TalentumColors.gold : TalentumColors.petrol,
      ),
      title: Text('${alert['symbol']} · ${alertPrice(alert)}'),
      subtitle: Text(
          '${marketAlertConditionLabel(alert['condition'])} · ${marketAlertStatusLabel(status)}'),
      onTap: editable
          ? (onEdit ?? () => openMarketAlertDialog(alert: alert))
          : null,
      trailing: Wrap(
        spacing: 0,
        children: [
          if (editable)
            IconButton(
              tooltip: 'Editar alerta',
              onPressed: onEdit ?? () => openMarketAlertDialog(alert: alert),
              icon: const Icon(Icons.edit_outlined),
            ),
          if (status == 'active' || status == 'paused')
            IconButton(
              tooltip: 'Desativar alerta',
              // O cancelamento é imediato e o alerta cancelado não pode ser reativado por esta tela (achado 211).
              onPressed: () => cancelMarketAlert(alert),
              icon: const Icon(Icons.close),
            ),
        ],
      ),
    );
  }

  /// Abre a relação completa de alertas de mercado.
  Future<void> openMarketAlertsHistory() async {
    final selectedAlert = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Alertas de preço'),
        content: SizedBox(
          width: 520,
          child: marketAlerts.isEmpty
              ? const Text('Nenhum alerta cadastrado.')
              : ListView(
                  shrinkWrap: true,
                  children: marketAlerts.map((alert) {
                    final item = Map<String, dynamic>.from(alert);
                    return _marketAlertTile(
                      item,
                      // Fecha o histórico antes de abrir o editor para evitar rotas
                      // de diálogo sobrepostas durante a desmontagem no Navigator.
                      onEdit: () => Navigator.pop(dialogContext, item),
                    );
                  }).toList(),
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
    if (selectedAlert != null && mounted) {
      await openMarketAlertDialog(alert: selectedAlert);
    }
  }

  /// Abre o formulário para criar ou editar um alerta de preço.
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
    var saving = false;
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
                    // O endpoint de edição aceita preço e condição; ticker e mercado ficam fixos.
                    readOnly: editing || saving,
                    textCapitalization: TextCapitalization.characters,
                    decoration: const InputDecoration(
                        labelText: 'Ticker ou símbolo',
                        hintText: 'PETR4 ou AAPL')),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  isExpanded: true,
                  initialValue: market,
                  onChanged: editing || saving
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
                    enabled: !saving,
                    keyboardType:
                        const TextInputType.numberWithOptions(decimal: true),
                    inputFormatters: const [TwoDecimalMoneyInputFormatter()],
                    decoration: const InputDecoration(
                        labelText: 'Preço-alvo', hintText: 'Ex.: 32,50')),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                    isExpanded: true,
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
                    onChanged: saving
                        ? null
                        : (value) => setDialogState(
                            () => condition = value ?? 'at_or_below')),
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: saving ? null : () => Navigator.pop(dialogContext),
                child: const Text('Cancelar')),
            FilledButton(
              onPressed: saving
                  ? null
                  : () async {
                      final parsedTarget = parseBrazilianNumber(target.text);
                      if (symbol.text.trim().isEmpty ||
                          parsedTarget == null ||
                          parsedTarget <= 0) {
                        ScaffoldMessenger.of(dialogContext).showSnackBar(
                          const SnackBar(
                            content:
                                Text('Informe o ativo e um preço-alvo válido.'),
                          ),
                        );
                        return;
                      }
                      if (saving) return;
                      // Define o bloqueio antes do primeiro await para evitar envios repetidos.
                      saving = true;
                      try {
                        setDialogState(() {});
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
                            condition: condition,
                          );
                        }
                        if (!mounted || !dialogContext.mounted) return;
                        Navigator.pop(dialogContext);
                        final messenger = ScaffoldMessenger.of(context);
                        await load();
                        if (mounted) {
                          messenger.showSnackBar(const SnackBar(
                            content: Text('Alerta salvo com sucesso.'),
                          ));
                        }
                      } on ApiException catch (exception) {
                        if (dialogContext.mounted) {
                          setDialogState(() => saving = false);
                          ScaffoldMessenger.of(dialogContext).showSnackBar(
                            SnackBar(content: Text(exception.message)),
                          );
                        }
                      } catch (_) {
                        if (dialogContext.mounted) {
                          setDialogState(() => saving = false);
                          ScaffoldMessenger.of(dialogContext).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'Não foi possível salvar o alerta. Tente novamente.',
                              ),
                            ),
                          );
                        }
                      }
                    },
              child: Text(saving
                  ? 'Salvando...'
                  : editing
                      ? 'Salvar alterações'
                      : 'Criar alerta'),
            ),
          ],
        ),
      ),
    );
    symbol.dispose();
    target.dispose();
  }

  /// Abre o destino associado a uma notificação e marca a leitura.
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
        setState(() => tab = 3);
      } else if (kind == 'document_uploaded') {
        setState(() => tab = 4);
      } else if (kind == 'document_review_due') {
        setState(() => tab = 4);
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  /// Marca todas as notificações carregadas como lidas.
  Future<void> markAllNotificationsRead() async {
    try {
      await widget.api.markAllNotificationsRead();
      await load();
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  /// Abre o formulário de preferências de notificações.
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
                  // Cada alternância edita o rascunho local até o usuário salvar o diálogo.
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
                  // Envia todas as opções; após o fallback, valores não editados também podem ser sobrescritos.
                  // O diálogo e o botão seguem ativos durante o PATCH; envios podem confirmar fora de ordem (achado 159).
                  final updated =
                      await widget.api.updateNotificationPreferences(values);
                  if (!mounted || !dialogContext.mounted) return;
                  setState(() => notificationPreferences = updated);
                  ScaffoldMessenger.of(dialogContext).showSnackBar(
                      const SnackBar(content: Text('Preferências salvas.')));
                  Navigator.pop(dialogContext);
                } on ApiException catch (exception) {
                  if (dialogContext.mounted) {
                    ScaffoldMessenger.of(dialogContext).showSnackBar(
                        SnackBar(content: Text(exception.message)));
                  }
                }
              },
              child: const Text('Salvar'),
            ),
          ],
        ),
      ),
    );
  }

  /// Abre o histórico de notificações com seus filtros.
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
              .toList(); // O histórico filtra apenas os itens já carregados; a API limita essa lista a 50 (achado 140).
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
                                  ? TalentumColors.error
                                  : null),
                          title: Text(notification['title'].toString()),
                          subtitle: Text(
                              '${notification['message']}\n${dateTimeLabel(notification['created_at'])}'),
                          onTap: () {
                            // Fecha o histórico antes de marcar a notificação e abrir seu destino.
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

  /// Exibe o plano de ações e permite consultar tarefas do cliente.
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
                      // Deriva o destaque de atraso e o conteúdo de cada ação ao montar a lista.
                      final action = orderedActions[index];
                      final overdue =
                          isOverdueAction(Map<String, dynamic>.from(action));
                      return ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(actionStatusIcon(action['status']),
                            color: overdue
                                ? TalentumColors.error
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

  /// Constrói uma linha de resumo com rótulo, valor e cor.
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

  /// Formata ou mascara valores monetários; cotas e percentuais são renderizados separadamente.
  String investmentMoney(dynamic value, dynamic currency) {
    if (hideValues) return '••••••';
    // O formatador atual distingue USD e usa BRL como fallback para outras moedas.
    final prefix = currency?.toString() == 'USD' ? 'US\$' : 'R\$';
    return '$prefix ${formatBrazilianNumber(value)}';
  }

  /// Agrupa posições por moeda para não comparar valores sem conversão cambial.
  Map<String, List<dynamic>> _positionsByCurrency(List<dynamic> positions) {
    final grouped = <String, List<dynamic>>{};
    for (final item in positions) {
      final position = Map<String, dynamic>.from(item as Map);
      final currency = position['currency']?.toString() ?? 'BRL';
      grouped.putIfAbsent(currency, () => []).add(position);
    }
    return grouped;
  }

  /// Constrói o gráfico circular com pesos percentuais visíveis mesmo com hideValues ativo.
  Widget _assetAllocationDonut(String currency, List<dynamic> positions) {
    // Exclui posições sem peso positivo para não criar segmentos vazios no gráfico.
    final priced = positions
        .where((item) =>
            (double.tryParse(item['allocation_percent']?.toString() ?? '') ??
                0) >
            0)
        .toList();
    if (priced.isEmpty) return const SizedBox.shrink();
    final values = priced
        .map((item) =>
            double.tryParse(item['allocation_percent']?.toString() ?? '') ?? 0)
        .toList();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          SizedBox(
            width: 148,
            height: 148,
            child: Stack(
              alignment: Alignment.center,
              children: [
                CustomPaint(
                  size: const Size.square(144),
                  painter: InvestmentDonutPainter(values: values),
                ),
                Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(currency,
                        style: const TextStyle(fontWeight: FontWeight.w800)),
                    Text('${priced.length} ativos',
                        style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              children: List.generate(priced.length, (index) {
                final position =
                    Map<String, dynamic>.from(priced[index] as Map);
                final pct = values[index];
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    children: [
                      Container(
                        width: 9,
                        height: 9,
                        decoration: BoxDecoration(
                          color: InvestmentDonutPainter.colors[
                              index % InvestmentDonutPainter.colors.length],
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(position['symbol']?.toString() ?? 'Ativo',
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 12)),
                      ),
                      Text('${formatBrazilianNumber(pct, fractionDigits: 1)}%',
                          style: const TextStyle(
                              fontSize: 12, fontWeight: FontWeight.w700)),
                    ],
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }

  /// Constrói o gráfico e os indicadores de desempenho mensal.
  Widget _monthlyInvestmentPerformance() {
    final performance = investmentMonthlyPerformance;
    // A API retorna séries separadas por moeda; não há conversão cambial para consolidá-las aqui.
    // Os percentuais de retorno/CDI e as linhas do gráfico não consultam hideValues.
    final currencies =
        List<dynamic>.from(performance?['currencies'] as List? ?? []);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Divider(height: 24),
        const Text('Rendimento no mês',
            style: TextStyle(fontWeight: FontWeight.w700)),
        if (investmentMonthlyPerformanceError != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(investmentMonthlyPerformanceError!,
                style: Theme.of(context).textTheme.bodySmall),
          )
        else if (performance == null)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: LinearProgressIndicator(),
          )
        else if (currencies.isEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text(
                'O histórico aparecerá após a primeira atualização da carteira.'),
          )
        else ...[
          ...currencies.map((raw) {
            final item = Map<String, dynamic>.from(raw as Map);
            final currency = item['currency']?.toString() ?? 'BRL';
            // Dados parciais podem mostrar totais e cobertura, mas não um retorno calculado.
            final hasData = item['data_available'] == true;
            final points = List<dynamic>.from(item['points'] as List? ?? []);
            // A comparação com CDI só é válida para a série denominada em reais.
            final cdi = currency == 'BRL' ? item['cdi_percent'] : null;
            final monthParts =
                (performance['month']?.toString() ?? '').split('-');
            final month = monthParts.length == 2
                ? '${monthParts[1]}/${monthParts[0]}'
                : monthParts.first;
            final start = item['coverage_start']?.toString();
            return Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('$currency · $month',
                          style: const TextStyle(fontWeight: FontWeight.w700)),
                      if (item['source_status'] == 'partial')
                        const Text('Dados parciais',
                            style: TextStyle(color: TalentumColors.error)),
                    ],
                  ),
                  if (item['full_month_to_date'] == false && start != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                          'Histórico disponível desde ${formatApiDate(start)}.',
                          style: Theme.of(context).textTheme.bodySmall),
                    ),
                  const SizedBox(height: 6),
                  _summaryRow(
                      'Valor investido',
                      investmentMoney(item['invested_value'], currency),
                      TalentumColors.muted),
                  _summaryRow(
                      'Rendimento em valor',
                      hasData
                          ? '${(double.tryParse(item['profit_value']?.toString() ?? '') ?? 0) >= 0 ? '+' : ''}${investmentMoney(item['profit_value'], currency)}'
                          : '—',
                      (double.tryParse(
                                      item['profit_value']?.toString() ?? '') ??
                                  0) >=
                              0
                          ? TalentumColors.teal
                          : TalentumColors.error),
                  _summaryRow(
                      'Rendimento',
                      hasData
                          ? '${formatBrazilianNumber(item['return_percent'], fractionDigits: 2)}%'
                          : '—',
                      TalentumColors.petrol),
                  if (currency == 'BRL') ...[
                    _summaryRow(
                        'CDI no mês',
                        cdi == null
                            ? 'Indisponível'
                            : '${formatBrazilianNumber(cdi, fractionDigits: 2)}%',
                        TalentumColors.muted),
                    // As duas métricas podem indicar desempenho abaixo do CDI, mas recebem sempre a cor teal (achado 187).
                    _summaryRow(
                        'Acima do CDI',
                        item['excess_percentage_points'] == null
                            ? '—'
                            : '${(double.tryParse(item['excess_percentage_points'].toString()) ?? 0) >= 0 ? '+' : ''}${formatBrazilianNumber(item['excess_percentage_points'], fractionDigits: 2)} p.p.',
                        TalentumColors.teal),
                    _summaryRow(
                        'Equivalente',
                        item['percent_of_cdi'] == null
                            ? '—'
                            : '${formatBrazilianNumber(item['percent_of_cdi'], fractionDigits: 1)}% do CDI',
                        TalentumColors.teal),
                  ],
                  if (!hasData)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(
                          'Precisamos de duas atualizações completas para calcular o rendimento.',
                          style: Theme.of(context).textTheme.bodySmall),
                    )
                  else
                    MonthlyInvestmentLineChart(
                        points: points,
                        showCdi: currency == 'BRL' && cdi != null),
                ],
              ),
            );
          }),
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              performance['cdi_status'] == 'cached'
                  ? 'CDI em cache: ${formatApiDate(performance['cdi_as_of'] ?? 'data indisponível')}.'
                  : performance['cdi_as_of'] != null
                      ? 'CDI oficial atualizado em ${formatApiDate(performance['cdi_as_of'])}.'
                      : 'CDI oficial indisponível no momento.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          if (currencies.any((item) => (item as Map)['data_available'] == true))
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                'Estimativa baseada nos snapshots e no resultado das posições abertas; aportes, retiradas e vendas realizadas podem alterar o resultado mensal.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
        ],
      ],
    );
  }

  /// Constrói a lista filtrável do histórico de operações.
  Widget _investmentTransactionsHistory() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Divider(height: 24),
        const Text('Histórico de operações',
            style: TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 12),
        // Alterar filtros só muda os parâmetros da próxima consulta, não a lista já carregada.
        Row(
          children: [
            Expanded(
              child: DropdownButtonFormField<String>(
                initialValue: investmentTransactionPeriod,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Período',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
                items: const [
                  DropdownMenuItem(
                      value: 'all', child: Text('Todo o histórico')),
                  DropdownMenuItem(
                      value: '30d', child: Text('Últimos 30 dias')),
                  DropdownMenuItem(
                      value: '90d', child: Text('Últimos 90 dias')),
                  DropdownMenuItem(value: 'ytd', child: Text('Este ano')),
                ],
                onChanged: investmentTransactionsBusy
                    ? null
                    : (value) {
                        if (value != null) {
                          setState(() => investmentTransactionPeriod = value);
                        }
                      },
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: DropdownButtonFormField<String>(
                initialValue: investmentTransactionType,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Tipo',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
                items: const [
                  DropdownMenuItem(value: 'all', child: Text('Todas')),
                  DropdownMenuItem(value: 'buy', child: Text('Compras')),
                  DropdownMenuItem(value: 'sell', child: Text('Vendas')),
                ],
                onChanged: investmentTransactionsBusy
                    ? null
                    : (value) {
                        if (value != null) {
                          setState(() => investmentTransactionType = value);
                        }
                      },
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        TextField(
          controller: investmentTransactionSymbolController,
          enabled: !investmentTransactionsBusy,
          textCapitalization: TextCapitalization.characters,
          textInputAction: TextInputAction.search,
          onSubmitted: (_) => refreshInvestmentTransactions(),
          decoration: const InputDecoration(
            labelText: 'Ativo',
            hintText: 'Ex.: PETR4 ou AAPL',
            prefixIcon: Icon(Icons.search),
            border: OutlineInputBorder(),
            isDense: true,
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilledButton.icon(
              onPressed: investmentTransactionsBusy
                  ? null
                  : refreshInvestmentTransactions,
              icon: const Icon(Icons.filter_alt_outlined),
              label: const Text('Aplicar filtros'),
            ),
            TextButton.icon(
              onPressed: investmentTransactionsBusy
                  ? null
                  : clearInvestmentTransactionFilters,
              icon: const Icon(Icons.clear),
              label: const Text('Limpar'),
            ),
          ],
        ),
        if (investmentTransactionsBusy)
          const Padding(
            padding: EdgeInsets.only(top: 12),
            child: LinearProgressIndicator(),
          ),
        if (investmentTransactionsError != null)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Text(investmentTransactionsError!,
                style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ),
        Padding(
          padding: const EdgeInsets.only(top: 12, bottom: 4),
          child: Text('${investmentTransactions.length} operação(ões)'),
        ),
        if (investmentTransactions.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text('Nenhuma operação corresponde aos filtros.'),
          )
        else
          ...investmentTransactions.map((raw) {
            final operation = Map<String, dynamic>.from(raw as Map);
            final isBuy = operation['operation_type'] == 'buy';
            final isVoided = operation['voided_at'] != null;
            final currency = operation['currency'];
            // investmentMoney mascara montantes, mas a quantidade de cotas continua visível (achado 98).
            final realized = isVoided ? null : operation['realized_pnl'];
            return ListTile(
              contentPadding: EdgeInsets.zero,
              onTap: () => showInvestmentTransactionDetails(operation),
              leading: Icon(
                isBuy ? Icons.south_west : Icons.north_east,
                color: isVoided
                    ? TalentumColors.silver
                    : isBuy
                        ? TalentumColors.petrol
                        : TalentumColors.teal,
              ),
              title: Text(
                  '${isBuy ? 'Compra' : 'Venda'}${isVoided ? ' anulada' : ''} · ${operation['symbol']} · ${dateLabel(operation['operation_date'])}'),
              subtitle: Text(
                isVoided
                    ? 'Toque para ver os detalhes da anulação.'
                    : '${formatInvestmentQuantity(operation['quantity'])} cotas × ${investmentMoney(operation['unit_price'], currency)} · taxas ${investmentMoney(operation['fees'], currency)}'
                        '${realized == null ? '' : '\nResultado realizado: ${investmentMoney(realized, currency)}'}',
              ),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    isVoided
                        ? 'Anulada'
                        : investmentMoney(operation['net_value'], currency),
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(width: 2),
                  const Icon(Icons.chevron_right, size: 18),
                ],
              ),
            );
          }),
        if (investmentTransactionsHasMore)
          Align(
            alignment: Alignment.center,
            child: TextButton.icon(
              onPressed: investmentTransactionsBusy
                  ? null
                  : loadMoreInvestmentTransactions,
              icon: const Icon(Icons.expand_more),
              label: const Text('Carregar mais operações'),
            ),
          ),
      ],
    );
  }

  /// Constrói uma linha de campo no detalhe de uma operação.
  Widget _investmentTransactionDetailRow(String label, String value,
      {Color? valueColor}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label)),
          const SizedBox(width: 12),
          Flexible(
            child: Text(value,
                textAlign: TextAlign.end,
                style:
                    TextStyle(fontWeight: FontWeight.w600, color: valueColor)),
          ),
        ],
      ),
    );
  }

  /// Apresenta todos os dados disponíveis de uma operação selecionada.
  Future<void> showInvestmentTransactionDetails(
      Map<String, dynamic> operation) async {
    final isBuy = operation['operation_type'] == 'buy';
    final isVoided = operation['voided_at'] != null;
    final currency = operation['currency'];
    final realized =
        double.tryParse(operation['realized_pnl']?.toString() ?? '');
    final name = operation['name']?.toString().trim();
    // A preferência oculta valores monetários abaixo, mas não mascara as quantidades de cotas (achado 98).
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Theme.of(sheetContext).colorScheme.outlineVariant,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
              const SizedBox(height: 18),
              Text(
                '${isBuy ? 'Compra' : 'Venda'} · ${operation['symbol']}',
                style: Theme.of(sheetContext).textTheme.titleLarge,
              ),
              if (name != null && name.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(name,
                      style: Theme.of(sheetContext).textTheme.bodyMedium),
                ),
              if (isVoided)
                const Padding(
                  padding: EdgeInsets.only(top: 12),
                  child: Chip(
                    avatar: Icon(Icons.cancel_outlined, size: 18),
                    label: Text('Operação anulada'),
                  ),
                ),
              const Divider(height: 24),
              _investmentTransactionDetailRow(
                  'Data', dateLabel(operation['operation_date'])),
              _investmentTransactionDetailRow('Mercado',
                  operation['market'] == 'global' ? 'Global' : 'Brasil'),
              _investmentTransactionDetailRow('Quantidade',
                  '${formatInvestmentQuantity(operation['quantity'])} cotas'),
              _investmentTransactionDetailRow('Preço por cota',
                  investmentMoney(operation['unit_price'], currency)),
              _investmentTransactionDetailRow('Valor bruto',
                  investmentMoney(operation['gross_value'], currency)),
              _investmentTransactionDetailRow(
                  'Taxas', investmentMoney(operation['fees'], currency)),
              _investmentTransactionDetailRow('Valor líquido',
                  investmentMoney(operation['net_value'], currency)),
              const Divider(height: 20),
              Text('Impacto na carteira',
                  style: Theme.of(sheetContext)
                      .textTheme
                      .titleSmall
                      ?.copyWith(fontWeight: FontWeight.w700)),
              _investmentTransactionDetailRow('Cotas antes',
                  formatInvestmentQuantity(operation['quantity_before'])),
              _investmentTransactionDetailRow('Cotas depois',
                  formatInvestmentQuantity(operation['quantity_after'])),
              _investmentTransactionDetailRow(
                  'Preço médio antes',
                  operation['average_price_before'] == null
                      ? '—'
                      : investmentMoney(
                          operation['average_price_before'], currency)),
              _investmentTransactionDetailRow(
                  'Preço médio depois',
                  operation['average_price_after'] == null
                      ? '—'
                      : investmentMoney(
                          operation['average_price_after'], currency)),
              if (!isBuy && !isVoided && operation['realized_pnl'] != null)
                _investmentTransactionDetailRow(
                  'Resultado realizado',
                  '${realized != null && realized >= 0 ? '+' : ''}${investmentMoney(operation['realized_pnl'], currency)}',
                  valueColor: realized == null
                      ? null
                      : realized >= 0
                          ? TalentumColors.teal
                          : TalentumColors.error,
                ),
              if (operation['institution']?.toString().trim().isNotEmpty ==
                  true)
                _investmentTransactionDetailRow(
                    'Instituição', operation['institution'].toString()),
              if (operation['notes']?.toString().trim().isNotEmpty == true)
                _investmentTransactionDetailRow(
                    'Observações', operation['notes'].toString()),
              if (isVoided && operation['void_reason'] != null)
                _investmentTransactionDetailRow(
                    'Motivo da anulação', operation['void_reason'].toString()),
              if (isVoided && operation['voided_at'] != null)
                _investmentTransactionDetailRow(
                    'Anulada em', dateTimeLabel(operation['voided_at'])),
            ],
          ),
        ),
      ),
    );
  }

  // Exibe a carteira consolidada por posição, moeda e resultado.
  /// Constrói a visão de posições e distribuição da carteira.
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
                TalentumColors.muted),
            _summaryRow(
                'Valor atualizado',
                portfolio['mixed_currency'] == true
                    ? 'Ver por moeda'
                    : investmentMoney(portfolio['current_total'],
                        portfolio['total_currency']),
                TalentumColors.teal),
            _summaryRow(
                'Resultado',
                portfolio['mixed_currency'] == true
                    ? 'Ver por moeda'
                    : '${pnl >= 0 ? '+' : ''}${investmentMoney(portfolio['pnl_total'], portfolio['total_currency'])}',
                pnl >= 0 ? TalentumColors.teal : TalentumColors.error),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: investmentReportBusy ? null : emitInvestmentReport,
              icon: investmentReportBusy
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.picture_as_pdf_outlined),
              label: Text(investmentReportBusy
                  ? 'Emitindo relatório...'
                  : 'Emitir relatório detalhado (PDF)'),
            ),
            if ((portfolio['unpriced_position_count'] as num? ?? 0) > 0)
              Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                      '${portfolio['unpriced_position_count']} posição(ões) sem cotação atual.',
                      style: Theme.of(context).textTheme.bodySmall)),
            if (positions.isNotEmpty) ...[
              const Divider(height: 24),
              const Text('Distribuição por ativo',
                  style: TextStyle(fontWeight: FontWeight.w700)),
              ..._positionsByCurrency(positions).entries.map(
                  (entry) => _assetAllocationDonut(entry.key, entry.value)),
              if (_positionsByCurrency(positions).length > 1)
                const Text(
                  'As moedas são apresentadas separadamente, sem conversão cambial.',
                  style: TextStyle(
                      fontSize: 12, color: TalentumColors.muted),
                ),
            ],
            _monthlyInvestmentPerformance(),
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
                      '${double.tryParse(item['percentage']?.toString() ?? '')?.toStringAsFixed(1) ?? '0,0'}%'))), // toStringAsFixed usa ponto, ao contrário do formato pt-BR (achado 157).
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
                          '${double.tryParse(item['pnl_percent']?.toString() ?? '')?.toStringAsFixed(1) ?? '—'}%'))), // Percentual sem localização pt-BR (achado 157).
            ],
            if (positions.isNotEmpty) ...[
              const Divider(height: 24),
              const Text('Posições',
                  style: TextStyle(fontWeight: FontWeight.w700)),
              ...positions.map((item) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('${item['symbol']} · ${item['name'] ?? 'Ativo'}'),
                  subtitle: Text(
                      '${formatInvestmentQuantity(item['quantity'])} cotas · médio ${investmentMoney(item['average_price'], item['currency'])}'),
                  trailing: Text(item['current_value'] == null
                      ? 'Sem cotação'
                      : investmentMoney(
                          item['current_value'], item['currency'])))),
            ],
            _investmentTransactionsHistory(),
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
  /// Constrói a área de consulta e edição de patrimônio.
  Widget _patrimonyView() {
    final canEdit = permissions?['can_edit_patrimony'] == true;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
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

  /// Constrói a área de metas financeiras e seu progresso.
  Widget _goalsView() {
    final canEdit = permissions?['can_edit_goals'] == true;
    // O filtro de atraso inclui toda meta não concluída, inclusive pausadas (achado 54).
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
            // Mantém a barra entre 0% e 100%, mesmo quando o valor atual supera a meta.
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
                        value: progress,
                        color: overdue ? TalentumColors.error : null),
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
  /// Constrói a lista de relatórios disponíveis ao cliente.
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
  /// Constrói a área de consulta e envio de documentos.
  Widget _documentsView() {
    // A permissão controla apenas o botão; clientes continuam sem autorização de upload na rota (achado 49).
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

  /// Seleciona o arquivo, coleta seus metadados e envia o documento ao cliente.
  Future<void> uploadDocument() async {
    // O seletor fica fora do try abaixo, que captura apenas falhas da API (achado 41).
    final result = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'png', 'jpg', 'jpeg', 'txt'],
    );
    if (!mounted) return;
    if (result == null || result.files.single.path == null || user == null) {
      return;
    }
    final file = result.files.single;
    // Evita iniciar um envio acima do limite, que também é aplicado durante a leitura na API.
    if (file.size > 10 * 1024 * 1024) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('O arquivo excede o limite de 10 MB.')));
      }
      return;
    }
    final path = file.path!;
    final extension = (file.extension ?? '').toLowerCase();
    // Define o MIME enviado no multipart a partir da extensão permitida pelo seletor.
    final contentType = switch (extension) {
      'pdf' => 'application/pdf',
      'png' => 'image/png',
      'jpg' || 'jpeg' => 'image/jpeg',
      _ => 'text/plain',
    };
    if (mounted) setState(() => documentBusy = true);
    final description = TextEditingController();
    var kind = 'other';
    // Confirma a classificação e a descrição antes de enviar o arquivo à API.
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
      await load(); // A guarda pode descartar a recarga; a confirmação ainda aparece (achado 28).
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Documento enviado com sucesso.')));
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    } finally {
      description.dispose();
      if (mounted) setState(() => documentBusy = false);
    }
  }

  /// Abre os metadados e as ações disponíveis para um documento.
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

  /// Baixa o documento e abre o visualizador correspondente.
  Future<void> downloadDocument(Map<String, dynamic> document) async {
    if (user == null) return;
    // O seletor abre antes do try e pode lançar erros fora do tipo ApiException.
    final outputPath = await FilePicker.saveFile(
        fileName: document['original_name']?.toString() ?? 'documento');
    if (outputPath == null) return;
    try {
      final bytes = await widget.api
          .downloadDocument(user!['id'] as int, document['id'] as int);
      // Falhas de gravação local também não são convertidas em ApiException.
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

  /// Solicita à API a geração e o download do relatório da carteira.
  Future<void> emitInvestmentReport() async {
    if (user == null) return;
    setState(() => investmentReportBusy = true);
    try {
      final bytes =
          await widget.api.downloadInvestmentReport(user!['id'] as int);
      if (mounted) {
        await Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => InvestmentReportPreviewScreen(bytes: bytes),
          ),
        );
      }
      // A prévia só é aberta depois que a API devolve os bytes do PDF.
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(exception.message)),
        );
      }
    } finally {
      if (mounted) setState(() => investmentReportBusy = false);
    }
  }

  /// Abre os detalhes ou o conteúdo de um relatório selecionado.
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

  /// Solicita confirmação antes de remover o item identificado.
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

  /// Edita o patrimônio e converte campos opcionais vazios em `null` no payload.
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
                  inputFormatters: const [TwoDecimalMoneyInputFormatter()],
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
              // Valida o patrimônio e devolve ao formulário os campos normalizados.
              final parsedValue = parseBrazilianNumber(value.text);
              // Os schemas também impõem comprimentos mínimos e máximos não espelhados por estes campos (achado 129).
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
      await load(); // A API já confirmou; se outra carga estiver ativa, o feedback pode vir sem atualizar a lista (achado 28).
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Patrimônio atualizado.')));
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  /// Confirma e solicita a exclusão de um item patrimonial.
  Future<void> deletePatrimony(Map<String, dynamic> item) async {
    if (!await confirmRemoval('este item patrimonial') || user == null) return;
    try {
      await widget.api.deletePatrimony(user!['id'] as int, item['id'] as int);
      await load(); // A API já confirmou; se outra carga estiver ativa, a lista permanece desatualizada (achado 28).
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  /// Cria um item patrimonial após validar categoria, descrição e valor.
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
                  inputFormatters: const [TwoDecimalMoneyInputFormatter()],
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
              // Valida o patrimônio novo antes de devolver os campos normalizados.
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
      await load(); // A API já confirmou; se outra carga estiver ativa, o feedback pode vir sem atualizar a lista (achado 28).
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Patrimônio adicionado.')));
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  /// Cria uma meta e envia o prazo opcional como data civil em formato ISO.
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
                inputFormatters: const [TwoDecimalMoneyInputFormatter()],
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
                // Escolhe o prazo como data civil e armazena sua representação ISO.
                final date = await showDatePicker(
                    context: dialogContext,
                    firstDate: DateTime.now(),
                    lastDate: DateTime(2100),
                    initialDate: DateTime.now());
                if (date != null) {
                  targetDate.text = date.toIso8601String().split('T').first;
                }
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
              // Confere o título e o valor-alvo antes de devolver a meta ao formulário.
              final parsedTarget = parseBrazilianNumber(target.text);
              // Um título não vazio ainda pode ser menor que o mínimo aceito pelo schema (achado 129).
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
      await load(); // A API já confirmou; se outra carga estiver ativa, o feedback pode vir sem atualizar a lista (achado 28).
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Meta adicionada.')));
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  /// Atualiza valores, prazo opcional e estado da meta em um payload completo.
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
                inputFormatters: const [TwoDecimalMoneyInputFormatter()],
                decoration: const InputDecoration(
                    labelText: 'Valor-alvo', prefixText: 'R\$ ')),
            const SizedBox(height: 10),
            TextField(
                controller: current,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: const [TwoDecimalMoneyInputFormatter()],
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
                // Seleciona o prazo existente e o mantém como data civil ISO no formulário.
                final date = await showDatePicker(
                    context: dialogContext,
                    firstDate: DateTime(2000),
                    lastDate: DateTime(2100),
                    initialDate:
                        DateTime.tryParse(targetDate.text) ?? DateTime.now());
                if (date != null) {
                  targetDate.text = date.toIso8601String().split('T').first;
                }
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
              // Valida os valores editados e devolve o estado completo da meta.
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
      await load(); // A API já confirmou; se outra carga estiver ativa, o feedback pode vir sem atualizar a lista (achado 28).
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Meta atualizada.')));
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  /// Confirma e solicita a exclusão da meta selecionada.
  Future<void> deleteGoal(Map<String, dynamic> goal) async {
    if (!await confirmRemoval('esta meta') || user == null) return;
    try {
      await widget.api.deleteGoal(user!['id'] as int, goal['id'] as int);
      await load(); // A API já confirmou; se outra carga estiver ativa, a lista permanece desatualizada (achado 28).
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  /// Permite atualizar renda, despesas e perfil de risco.
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
                inputFormatters: const [TwoDecimalMoneyInputFormatter()],
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
                inputFormatters: const [TwoDecimalMoneyInputFormatter()],
                decoration: const InputDecoration(
                  labelText: 'Despesas mensais',
                  prefixText: 'R\$ ',
                ),
              ),
              const SizedBox(height: 10),
              // Aceita texto livre, enquanto a API limita só o tamanho e não valida códigos canônicos (achado 139).
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
              // Valida renda e despesas e normaliza o perfil de risco opcional.
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

  /// Abre o formulário para editar os dados cadastrais do cliente.
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
              // Valida o nome e converte campos cadastrais opcionais vazios em nulos.
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

  /// Encerra a sessão e retorna à tela de autenticação.
  Future<void> signOut() async {
    try {
      await widget.api.logout();
    } catch (_) {
      // Mesmo sem resposta da API, invalida a credencial local para concluir a saída.
      widget.api.accessToken = null;
    }
    try {
      await widget.api.secureStorage.delete(clientCacheKey);
    } catch (_) {
      // A navegação para login também protege a sessão se o dispositivo negar a limpeza do cache.
    }
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => LoginScreen(api: widget.api)),
      (_) => false,
    );
  }

  /// Envia a nova senha e, após sucesso, encerra a sessão e remove o cache local.
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
              // Valida as senhas e confirma a repetição antes de devolver os valores.
              // O schema também limita a 128 caracteres; esta checagem local só aplica o mínimo.
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

  // Perfil reúne identidade/endereço/segurança; campos financeiros ausentes viram zero (achado 142).
  /// Constrói a tela de perfil e suas opções de manutenção.
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
            // Esta condição só controla a exibição; a API ainda restringe a edição ao Advisor/admin (achado 49).
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

  /// Monta o endereço cadastrado em uma linha legível.
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

/// Exibe o relatório emitido e oferece salvar, compartilhar ou imprimir.
class InvestmentReportPreviewScreen extends StatelessWidget {
  const InvestmentReportPreviewScreen({super.key, required this.bytes});

  final List<int> bytes;

  /// Abre o seletor de destino somente quando o usuário escolhe salvar o PDF.
  Future<void> _savePdf(BuildContext context) async {
    try {
      final outputPath = await FilePicker.saveFile(
        fileName: 'relatorio-carteira-talentum.pdf',
        bytes: Uint8List.fromList(bytes),
      );
      if (outputPath != null && context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Relatório salvo em $outputPath.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Não foi possível salvar o relatório.')),
        );
      }
    }
  }

  /// Mantém a prévia à vista e deixa as ações disponíveis depois da leitura.
  @override
  Widget build(BuildContext context) {
    final pdfBytes = Uint8List.fromList(bytes);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Relatório da carteira'),
        actions: [
          IconButton(
            tooltip: 'Salvar PDF',
            onPressed: () => _savePdf(context),
            icon: const Icon(Icons.download_outlined),
          ),
        ],
      ),
      body: PdfPreview(
        build: (_) async => pdfBytes,
        pdfFileName: 'relatorio-carteira-talentum.pdf',
        allowSharing: true,
        allowPrinting: true,
        canChangeOrientation: false,
        canChangePageFormat: false,
        canDebug: false,
        onError: (_, __) => const Center(
          child: Text('Não foi possível exibir a prévia do relatório.'),
        ),
      ),
    );
  }
}

// Visualizador protegido: recebe bytes baixados pela API e escolhe o renderer adequado.
/// Recebe os dados necessários para visualizar um documento baixado.
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

  /// Cria o estado responsável pelo carregamento e pela exibição do arquivo.
  @override
  State<DocumentViewerScreen> createState() => _DocumentViewerScreenState();
}

/// Controla carregamento e apresentação do documento no visualizador.
class _DocumentViewerScreenState extends State<DocumentViewerScreen> {
  late final Future<List<int>> documentBytes;

  /// Inicializa dados e tarefas que dependem da criação do estado da tela.
  @override
  void initState() {
    super.initState();
    documentBytes = widget.api.downloadDocument(
      widget.clientId,
      widget.document['id'] as int,
    );
  }

  /// Salva ou compartilha o arquivo aberto no visualizador.
  Future<void> saveDocument() async {
    // A escolha do destino precede o try que trata somente falhas da API.
    final outputPath = await FilePicker.saveFile(
      fileName: widget.document['original_name']?.toString() ?? 'documento',
    );
    if (outputPath == null) return;
    try {
      final bytes = await documentBytes;
      // Erros de gravação local não são convertidos em ApiException neste fluxo.
      await File(outputPath).writeAsBytes(bytes, flush: true);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Documento salvo em $outputPath.')));
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  /// Escolhe o componente de visualização conforme o conteúdo do arquivo.
  Widget contentFor(List<int> bytes) {
    final contentType = widget.document['content_type']?.toString() ?? '';
    final data = Uint8List.fromList(bytes);
    // Sem renderizador embutido de PDF, orienta o cliente a salvar o arquivo e abri-lo no dispositivo.
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
    // Habilita zoom e movimentação na prévia de imagens.
    if (contentType.startsWith('image/')) {
      return InteractiveViewer(
        minScale: 0.5,
        maxScale: 4,
        child: Center(child: Image.memory(data, fit: BoxFit.contain)),
      );
    }
    if (contentType == 'text/plain') {
      // Bytes inválidos são substituídos para manter a prévia aberta, podendo ocultar corrupção no upload.
      return SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: SelectableText(utf8.decode(data, allowMalformed: true)),
      );
    }
    return const Center(
      child: Text('Visualização não disponível para este tipo de arquivo.'),
    );
  }

  /// Exibe o documento carregado e as ações de navegação e salvamento.
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
          // Mostra carregamento, erro de leitura ou conteúdo conforme o estado da Future.
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
