// Talentum — mobile/test/widget_test.dart
// Responsabilidade: Valida comportamentos importantes do aplicativo Flutter.
// Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:talentum_mobile/api_client.dart';
import 'package:talentum_mobile/main.dart';

/// Agrupa verificações de interface e restauração de sessão do app Flutter.
void main() {
  // Este teste precisa avançar o timer do splash antes de procurar os controles de login (achado 210).
  testWidgets('exibe a tela de login do Talentum', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    await tester.pumpWidget(
      TalentumApp(
        api: ApiClient(
          baseUrl: 'http://127.0.0.1:8000',
          preferences: preferences,
          secureStorage: MemorySecureValueStore(),
        ),
      ),
    );

    expect(find.text('Sua jornada financeira começa aqui.'), findsOneWidget);
    expect(find.text('Entrar'), findsOneWidget);
  });

  // Garante que o formulário rejeite dados inválidos antes de chamar a API.
  testWidgets('valida o login antes de chamar a API',
      (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    await tester.pumpWidget(
      TalentumApp(
        api: ApiClient(
          baseUrl: 'http://127.0.0.1:8000',
          preferences: preferences,
          secureStorage: MemorySecureValueStore(),
        ),
      ),
    );

    await tester.tap(find.text('Entrar'));
    await tester.pump();

    expect(find.text('Informe um e-mail válido.'), findsOneWidget);
  });

  // Verifica que os tokens salvos na área segura restauram a sessão local.
  test('restaura tokens da área segura', () async {
    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    final secureStorage = MemorySecureValueStore();
    await secureStorage.write(ApiClient.accessTokenKey, 'access-test');
    await secureStorage.write(ApiClient.refreshTokenKey, 'refresh-test');
    final api = ApiClient(
      baseUrl: 'http://127.0.0.1:8000',
      preferences: preferences,
      secureStorage: secureStorage,
    );
    await api.restoreSession();

    expect(api.accessToken, 'access-test');
    expect(api.refreshToken, 'refresh-test');
    expect(await secureStorage.read(ApiClient.accessTokenKey), 'access-test');
    expect(await secureStorage.read(ApiClient.refreshTokenKey), 'refresh-test');
  });

  // Confirma que barras finais repetidas não permanecem na origem da API.
  test('normaliza a barra final da URL da API', () async {
    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    final api = ApiClient(
      baseUrl: 'https://api.talentum.local///',
      preferences: preferences,
      secureStorage: MemorySecureValueStore(),
    );

    expect(api.baseUrl, 'https://api.talentum.local');
  });
}
