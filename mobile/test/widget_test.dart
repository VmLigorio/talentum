import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:talentum_mobile/api_client.dart';
import 'package:talentum_mobile/main.dart';

void main() {
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
