// Talentum — mobile/lib/api_client.dart
// Responsabilidade: Implementa o cliente HTTP usado pelo aplicativo Flutter para falar com a API.
// Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

// Abstração permite trocar o armazenamento seguro por um fake nos testes.
abstract interface class SecureValueStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

// Implementação usada no dispositivo, apoiada pelo armazenamento criptografado.
class PlatformSecureValueStore implements SecureValueStore {
  PlatformSecureValueStore([FlutterSecureStorage? storage])
      : storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage storage;

  @override
  Future<String?> read(String key) => storage.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      storage.write(key: key, value: value);

  @override
  Future<void> delete(String key) => storage.delete(key: key);
}

// Armazenamento em memória para testes sem tocar nas credenciais reais do usuário.
class MemorySecureValueStore implements SecureValueStore {
  final Map<String, String> values = {};

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async => values[key] = value;

  @override
  Future<void> delete(String key) async => values.remove(key);
}

// Erro normalizado para que a interface mostre mensagens consistentes.
class ApiException implements Exception {
  ApiException(this.message, this.statusCode);

  final String message;
  final int statusCode;

  @override
  String toString() => message;
}

// Encapsula autenticação, renovação de tokens e todas as chamadas HTTP do app.
class ApiClient {
  ApiClient(
      {required String baseUrl,
      required this.preferences,
      required this.secureStorage})
      : baseUrl = baseUrl.replaceFirst(RegExp(r'/+$'), '');

  final String baseUrl;
  final SharedPreferences preferences;
  final SecureValueStore secureStorage;
  String? accessToken;
  String? refreshToken;
  Completer<void>? _refreshCompleter;

  bool get hasStoredSession => accessToken != null && refreshToken != null;

  static const accessTokenKey = 'talentum_access_token';
  static const refreshTokenKey = 'talentum_refresh_token';

  // Recupera os tokens persistidos antes de a primeira tela ser apresentada.
  Future<void> restoreSession() async {
    accessToken = await secureStorage.read(accessTokenKey);
    refreshToken = await secureStorage.read(refreshTokenKey);
  }

  // Mantém a sessão somente no armazenamento seguro, nunca em texto de interface.
  Future<void> _persistTokens() async {
    await secureStorage.write(accessTokenKey, accessToken!);
    await secureStorage.write(refreshTokenKey, refreshToken!);
  }

  // Remove os tokens locais quando o logout ou a renovação falha.
  Future<void> clearSession() async {
    accessToken = null;
    refreshToken = null;
    await secureStorage.delete(accessTokenKey);
    await secureStorage.delete(refreshTokenKey);
  }

  // Converte respostas JSON e transforma conteúdo inválido em erro de API.
  dynamic _decodeJson(String text) {
    if (text.trim().isEmpty) return null;
    try {
      return jsonDecode(text);
    } on FormatException {
      throw ApiException('A API retornou uma resposta inválida.', 502);
    }
  }

  // Centraliza timeout, autenticação, tratamento de status e retry após 401.
  Future<dynamic> _request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
    bool retryOnUnauthorized = true,
  }) async {
    final client = HttpClient();
    try {
      client.connectionTimeout = const Duration(seconds: 12);
      final request = await client.openUrl(method, Uri.parse('$baseUrl$path'));
      request.headers.contentType = ContentType.json;
      if (accessToken != null) {
        request.headers
            .set(HttpHeaders.authorizationHeader, 'Bearer $accessToken');
      }
      if (body != null) {
        request.write(jsonEncode(body));
      }
      final response =
          await request.close().timeout(const Duration(seconds: 30));
      final text = await response.transform(utf8.decoder).join();
      final data = _decodeJson(text);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final detail = data is Map && data['detail'] is String
            ? data['detail'] as String
            : 'Não foi possível concluir a operação.';
        final exception = ApiException(detail, response.statusCode);
        if (response.statusCode == 401 &&
            retryOnUnauthorized &&
            refreshToken != null &&
            path != '/auth/login' &&
            path != '/auth/refresh') {
          try {
            await _refresh();
            return await _request(
              path,
              method: method,
              body: body,
              retryOnUnauthorized: false,
            );
          } catch (_) {
            await clearSession();
          }
        }
        throw exception;
      }
      return data;
    } on SocketException {
      throw ApiException('Não foi possível conectar à API.', 0);
    } on HttpException {
      throw ApiException('A API não respondeu corretamente.', 0);
    } on TimeoutException {
      throw ApiException('A conexão demorou demais para responder.', 0);
    } finally {
      client.close(force: true);
    }
  }

  // Faz login e salva os tokens emitidos pela API.
  Future<void> login(String email, String password) async {
    final data = await _request(
      '/auth/login',
      method: 'POST',
      body: {'email': email, 'password': password},
    ) as Map<String, dynamic>;
    accessToken = data['access_token'] as String;
    refreshToken = data['refresh_token'] as String;
    await _persistTokens();
  }

  // Evita várias renovações simultâneas quando requisições expiram juntas.
  Future<void> _refresh() async {
    final activeRefresh = _refreshCompleter;
    if (activeRefresh != null) return activeRefresh.future;

    final completer = Completer<void>();
    _refreshCompleter = completer;
    try {
      await _performRefresh();
      completer.complete();
    } catch (error, stackTrace) {
      completer.completeError(error, stackTrace);
      rethrow;
    } finally {
      _refreshCompleter = null;
    }
  }

  // A renovação usa o refresh token atual e substitui os dois tokens locais.
  Future<void> _performRefresh() async {
    final currentRefreshToken = refreshToken;
    if (currentRefreshToken == null) {
      throw ApiException('Sessão expirada.', 401);
    }
    final data = await _request(
      '/auth/refresh',
      method: 'POST',
      body: {'refresh_token': currentRefreshToken},
      retryOnUnauthorized: false,
    ) as Map<String, dynamic>;
    accessToken = data['access_token'] as String;
    refreshToken = data['refresh_token'] as String;
    await _persistTokens();
  }

  // Métodos seguintes representam os recursos públicos consumidos pelo mobile.
  Future<Map<String, dynamic>> me() async =>
      Map<String, dynamic>.from(await _request('/auth/me') as Map);

  Future<Map<String, dynamic>> dashboard(int clientId) async =>
      Map<String, dynamic>.from(
          await _request('/clients/$clientId/dashboard') as Map);

  Future<Map<String, dynamic>> investmentPortfolio(int clientId) async =>
      Map<String, dynamic>.from(
          await _request('/clients/$clientId/investment-portfolio') as Map);

  Future<Map<String, dynamic>> investmentMonthlyPerformance(int clientId) async =>
      Map<String, dynamic>.from(await _request(
          '/clients/$clientId/investment-monthly-performance') as Map);

  Future<List<dynamic>> investmentTransactions(int clientId) async =>
      List<dynamic>.from(await _request(
          '/clients/$clientId/investment-transactions?limit=100') as List);

  Future<List<dynamic>> patrimony(int clientId) async => List<dynamic>.from(
      await _request('/clients/$clientId/patrimony') as List);

  Future<List<dynamic>> goals(int clientId) async =>
      List<dynamic>.from(await _request('/clients/$clientId/goals') as List);

  Future<List<dynamic>> actionPlan(int clientId) async => List<dynamic>.from(
      await _request('/clients/$clientId/action-plan') as List);

  Future<List<dynamic>> reports(int clientId) async =>
      List<dynamic>.from(await _request('/clients/$clientId/reports') as List);

  Future<List<dynamic>> documents(int clientId) async => List<dynamic>.from(
      await _request('/clients/$clientId/documents') as List);

  Future<List<dynamic>> notifications({bool unreadOnly = false}) async =>
      List<dynamic>.from(
          await _request('/notifications?unread_only=$unreadOnly') as List);

  // Alertas de preço usam o mesmo mecanismo de autenticação e renovação.
  Future<List<dynamic>> marketAlerts() async =>
      List<dynamic>.from(await _request('/market/alerts') as List);

  Future<Map<String, dynamic>> createMarketAlert({
    required String symbol,
    required String market,
    required double targetPrice,
    required String condition,
  }) async =>
      Map<String, dynamic>.from(
          await _request('/market/alerts', method: 'POST', body: {
        'symbol': symbol,
        'market': market,
        'target_price': targetPrice,
        'condition': condition,
      }) as Map);

  Future<Map<String, dynamic>> updateMarketAlert(
    int alertId, {
    double? targetPrice,
    String? condition,
    String? status,
  }) async {
    final body = <String, dynamic>{};
    if (targetPrice != null) body['target_price'] = targetPrice;
    if (condition != null) body['condition'] = condition;
    if (status != null) body['status'] = status;
    return Map<String, dynamic>.from(await _request(
      '/market/alerts/$alertId',
      method: 'PATCH',
      body: body,
    ) as Map);
  }

  Future<Map<String, dynamic>> cancelMarketAlert(int alertId) async =>
      Map<String, dynamic>.from(
          await _request('/market/alerts/$alertId', method: 'DELETE') as Map);

  Future<void> markNotificationRead(int notificationId) async {
    await _request('/notifications/$notificationId/read', method: 'PATCH');
  }

  Future<void> markAllNotificationsRead() async {
    await _request('/notifications/read-all', method: 'PATCH');
  }

  Future<Map<String, dynamic>> notificationPreferences() async =>
      Map<String, dynamic>.from(
          await _request('/notifications/preferences') as Map);

  Future<Map<String, dynamic>> updateNotificationPreferences(
          Map<String, dynamic> body) async =>
      Map<String, dynamic>.from(await _request('/notifications/preferences',
          method: 'PATCH', body: body) as Map);

  // Upload multipart é tratado separadamente porque não envia JSON.
  Future<void> uploadDocument(
    int clientId, {
    required String path,
    required String fileName,
    required String contentType,
    required String kind,
    String? description,
    bool retryOnUnauthorized = true,
  }) async {
    final file = File(path);
    final length = await file.length();
    if (length > 10 * 1024 * 1024) {
      throw ApiException('O arquivo excede o limite de 10 MB.', 413);
    }
    final boundary = 'TalentumBoundary${DateTime.now().microsecondsSinceEpoch}';
    final client = HttpClient();
    try {
      client.connectionTimeout = const Duration(seconds: 12);
      final request = await client
          .postUrl(Uri.parse('$baseUrl/clients/$clientId/documents'));
      request.headers.contentType = ContentType('multipart', 'form-data',
          parameters: {'boundary': boundary});
      if (accessToken != null) {
        request.headers
            .set(HttpHeaders.authorizationHeader, 'Bearer $accessToken');
      }
      final safeFileName = fileName.replaceAll('"', '');
      final prefix = '--$boundary\r\n'
          'Content-Disposition: form-data; name="description"\r\n\r\n'
          '${description ?? ''}\r\n'
          '--$boundary\r\n'
          'Content-Disposition: form-data; name="kind"\r\n\r\n'
          '$kind\r\n'
          '--$boundary\r\n'
          'Content-Disposition: form-data; name="file"; filename="$safeFileName"\r\n'
          'Content-Type: $contentType\r\n\r\n';
      request.add(utf8.encode(prefix));
      await request.addStream(file.openRead());
      request.add(utf8.encode('\r\n--$boundary--\r\n'));
      final response =
          await request.close().timeout(const Duration(seconds: 30));
      final text = await response.transform(utf8.decoder).join();
      final data = _decodeJson(text);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        if (response.statusCode == 401 &&
            retryOnUnauthorized &&
            refreshToken != null) {
          try {
            await _refresh();
            return await uploadDocument(clientId,
                path: path,
                fileName: fileName,
                contentType: contentType,
                kind: kind,
                description: description,
                retryOnUnauthorized: false);
          } catch (_) {
            await clearSession();
          }
        }
        final detail = data is Map && data['detail'] is String
            ? data['detail'] as String
            : 'Não foi possível enviar o documento.';
        throw ApiException(detail, response.statusCode);
      }
    } on SocketException {
      throw ApiException('Não foi possível conectar à API.', 0);
    } on HttpException {
      throw ApiException('A API não respondeu corretamente.', 0);
    } on TimeoutException {
      throw ApiException('O envio demorou demais para responder.', 0);
    } finally {
      client.close(force: true);
    }
  }

  // Download retorna bytes para o visualizador ou para o armazenamento local.
  Future<List<int>> downloadDocument(
    int clientId,
    int documentId, {
    bool retryOnUnauthorized = true,
  }) async {
    final client = HttpClient();
    try {
      client.connectionTimeout = const Duration(seconds: 12);
      final request = await client.getUrl(Uri.parse(
          '$baseUrl/clients/$clientId/documents/$documentId/download'));
      if (accessToken != null) {
        request.headers
            .set(HttpHeaders.authorizationHeader, 'Bearer $accessToken');
      }
      final response =
          await request.close().timeout(const Duration(seconds: 30));
      final bytes = await response.fold<List<int>>(<int>[], (all, chunk) {
        all.addAll(chunk);
        return all;
      });
      if (response.statusCode < 200 || response.statusCode >= 300) {
        if (response.statusCode == 401 &&
            retryOnUnauthorized &&
            refreshToken != null) {
          try {
            await _refresh();
            return await downloadDocument(clientId, documentId,
                retryOnUnauthorized: false);
          } catch (_) {
            await clearSession();
          }
        }
        final text = utf8.decode(bytes);
        final data = _decodeJson(text);
        final detail = data is Map && data['detail'] is String
            ? data['detail'] as String
            : 'Não foi possível baixar o documento.';
        throw ApiException(detail, response.statusCode);
      }
      return bytes;
    } on SocketException {
      throw ApiException('Não foi possível conectar à API.', 0);
    } on HttpException {
      throw ApiException('A API não respondeu corretamente.', 0);
    } on TimeoutException {
      throw ApiException('O download demorou demais para responder.', 0);
    } finally {
      client.close(force: true);
    }
  }

  Future<List<int>> downloadInvestmentReport(int clientId,
      {bool retryOnUnauthorized = true}) async {
    final client = HttpClient();
    try {
      client.connectionTimeout = const Duration(seconds: 12);
      final request = await client.getUrl(
          Uri.parse('$baseUrl/clients/$clientId/investment-report.pdf'));
      if (accessToken != null) {
        request.headers
            .set(HttpHeaders.authorizationHeader, 'Bearer $accessToken');
      }
      final response = await request.close().timeout(const Duration(seconds: 60));
      final bytes = await response.fold<List<int>>(<int>[], (all, chunk) {
        all.addAll(chunk);
        return all;
      });
      if (response.statusCode < 200 || response.statusCode >= 300) {
        if (response.statusCode == 401 &&
            retryOnUnauthorized &&
            refreshToken != null) {
          try {
            await _refresh();
            return await downloadInvestmentReport(clientId,
                retryOnUnauthorized: false);
          } catch (_) {
            await clearSession();
          }
        }
        final data = _decodeJson(utf8.decode(bytes));
        final detail = data is Map && data['detail'] is String
            ? data['detail'] as String
            : 'Não foi possível emitir o relatório da carteira.';
        throw ApiException(detail, response.statusCode);
      }
      return bytes;
    } on SocketException {
      throw ApiException('Não foi possível conectar à API.', 0);
    } on HttpException {
      throw ApiException('A API não respondeu corretamente.', 0);
    } on TimeoutException {
      throw ApiException('A emissão demorou demais para responder.', 0);
    } finally {
      client.close(force: true);
    }
  }

  // Perfil, permissões e dados financeiros são separados para respeitar seus acessos.
  Future<Map<String, dynamic>?> financialProfile(int clientId) async {
    try {
      return Map<String, dynamic>.from(
        await _request('/clients/$clientId/financial-profile') as Map,
      );
    } on ApiException catch (exception) {
      if (exception.statusCode == 404) return null;
      rethrow;
    }
  }

  // Questionário e avaliação de suitability alimentam a carteira modelo do cliente.
  Future<Map<String, dynamic>> suitabilityQuestionnaire() async =>
      Map<String, dynamic>.from(
          await _request('/clients/me/suitability/questionnaire') as Map);

  Future<Map<String, dynamic>?> suitability() async {
    try {
      final data = await _request('/clients/me/suitability');
      return data == null ? null : Map<String, dynamic>.from(data as Map);
    } on ApiException catch (exception) {
      if (exception.statusCode == 404) return null;
      rethrow;
    }
  }

  Future<Map<String, dynamic>> submitSuitability({
    required String objective,
    required Map<String, String> answers,
    required String financialDataVersion,
    required bool confirmFinancialSituation,
  }) async =>
      Map<String, dynamic>.from(await _request(
        '/clients/me/suitability',
        method: 'POST',
        body: {
          'objective': objective,
          'answers': answers,
          'financial_data_version': financialDataVersion,
          'confirm_financial_situation': confirmFinancialSituation,
        },
      ) as Map);

  Future<Map<String, dynamic>> respondToSuitability({
    required int assessmentId,
    required String response,
    String? note,
  }) async =>
      Map<String, dynamic>.from(await _request(
        '/clients/me/suitability/$assessmentId/response',
        method: 'POST',
        body: {'response': response, 'note': note},
      ) as Map);

  Future<Map<String, dynamic>> profile(int clientId) async =>
      Map<String, dynamic>.from(
          await _request('/clients/$clientId/profile') as Map);

  Future<void> updateProfile(int clientId, Map<String, dynamic> body) async {
    await _request('/clients/$clientId/profile', method: 'PUT', body: body);
  }

  Future<void> updateFinancialProfile(
    int clientId,
    Map<String, dynamic> body,
  ) async {
    await _request(
      '/clients/$clientId/financial-profile',
      method: 'PUT',
      body: body,
    );
  }

  Future<Map<String, dynamic>> permissions(int clientId) async =>
      Map<String, dynamic>.from(
          await _request('/clients/$clientId/permissions') as Map);

  Future<void> createPatrimony(int clientId, Map<String, dynamic> body) async {
    await _request('/clients/$clientId/patrimony', method: 'POST', body: body);
  }

  Future<void> createGoal(int clientId, Map<String, dynamic> body) async {
    await _request('/clients/$clientId/goals', method: 'POST', body: body);
  }

  Future<void> updatePatrimony(
    int clientId,
    int itemId,
    Map<String, dynamic> body,
  ) async {
    await _request('/clients/$clientId/patrimony/$itemId',
        method: 'PATCH', body: body);
  }

  Future<void> deletePatrimony(int clientId, int itemId) async {
    await _request('/clients/$clientId/patrimony/$itemId', method: 'DELETE');
  }

  Future<void> updateGoal(
    int clientId,
    int goalId,
    Map<String, dynamic> body,
  ) async {
    await _request('/clients/$clientId/goals/$goalId',
        method: 'PATCH', body: body);
  }

  Future<void> deleteGoal(int clientId, int goalId) async {
    await _request('/clients/$clientId/goals/$goalId', method: 'DELETE');
  }

  // Logout tenta invalidar a sessão no servidor e sempre limpa a sessão local.
  Future<void> logout() async {
    if (accessToken == null) {
      await clearSession();
      return;
    }
    try {
      await _request('/auth/logout', method: 'POST');
    } finally {
      await clearSession();
    }
  }

  Future<void> changePassword(
    String currentPassword,
    String newPassword,
  ) async {
    await _request(
      '/auth/change-password',
      method: 'POST',
      body: {
        'current_password': currentPassword,
        'new_password': newPassword,
      },
    );
  }
}
