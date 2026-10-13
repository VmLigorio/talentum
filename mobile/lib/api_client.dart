// Talentum — mobile/lib/api_client.dart
// Responsabilidade: Implementa o cliente HTTP usado pelo aplicativo Flutter para falar com a API.
// Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

// Abstração permite trocar o armazenamento seguro por um fake nos testes.
/// Abstração do armazenamento de valores sensíveis usado pela sessão.
abstract interface class SecureValueStore {
  /// Lê um valor identificado pela chave no armazenamento correspondente.
  Future<String?> read(String key);
  /// Salva um valor associado à chave no armazenamento correspondente.
  Future<void> write(String key, String value);
  /// Remove do armazenamento o valor associado à chave.
  Future<void> delete(String key);
}

// Implementação usada no dispositivo, apoiada pelo armazenamento criptografado.
/// Implementação da abstração com armazenamento seguro do sistema.
class PlatformSecureValueStore implements SecureValueStore {
  /// Usa a implementação fornecida ou cria o armazenamento seguro padrão.
  PlatformSecureValueStore([FlutterSecureStorage? storage])
      : storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage storage;

  /// Lê um valor identificado pela chave no armazenamento correspondente.
  @override
  Future<String?> read(String key) => storage.read(key: key);

  /// Salva um valor associado à chave no armazenamento correspondente.
  @override
  Future<void> write(String key, String value) =>
      storage.write(key: key, value: value);

  /// Remove do armazenamento o valor associado à chave.
  @override
  Future<void> delete(String key) => storage.delete(key: key);
}

// Armazenamento em memória para testes sem tocar nas credenciais reais do usuário.
/// Implementação em memória usada para isolar testes de credenciais reais.
class MemorySecureValueStore implements SecureValueStore {
  final Map<String, String> values = {};

  /// Lê um valor identificado pela chave no armazenamento correspondente.
  @override
  Future<String?> read(String key) async => values[key];

  /// Salva um valor associado à chave no armazenamento correspondente.
  @override
  Future<void> write(String key, String value) async => values[key] = value;

  /// Remove do armazenamento o valor associado à chave.
  @override
  Future<void> delete(String key) async => values.remove(key);
}

// Erro normalizado para que a interface mostre mensagens consistentes.
/// Erro HTTP normalizado com mensagem segura para exibição no aplicativo.
class ApiException implements Exception {
  /// Guarda o texto seguro para a interface e o status HTTP associado.
  ApiException(this.message, this.statusCode);

  final String message;
  final int statusCode;

  /// Expõe a mensagem normalizada para a interface ou registro de erro.
  @override
  String toString() => message;
}

// Encapsula autenticação, renovação de tokens e todas as chamadas HTTP do app.
/// Centraliza autenticação, persistência de sessão e chamadas aos recursos da API.
class ApiClient {
  /// Configura a origem da API e os armazenamentos usados pela sessão.
  /// Remove barras finais da origem para compor caminhos com uma única separação.
  ApiClient(
      {required String baseUrl,
      required this.preferences,
      required this.secureStorage})
      : baseUrl = baseUrl.replaceFirst(RegExp(r'/+$'), '');

  /// Endereço-base da API, sem barras finais.
  final String baseUrl;
  /// Preferências locais não sensíveis consultadas pelas telas do aplicativo.
  final SharedPreferences preferences;
  /// Armazenamento seguro usado para persistir os tokens da sessão.
  final SecureValueStore secureStorage;
  /// Token de acesso ativo mantido em memória durante a sessão.
  String? accessToken;
  /// Token renovável mantido em memória para solicitar outro par de tokens.
  String? refreshToken;
  /// Future compartilhado para que chamadas simultâneas aguardem a mesma renovação.
  Completer<void>? _refreshCompleter;

  /// Indica se os dois tokens necessários para restaurar a sessão estão carregados.
  bool get hasStoredSession => accessToken != null && refreshToken != null;

  // Mantém identificadores estáveis para recuperar os tokens no armazenamento seguro.
  static const accessTokenKey = 'talentum_access_token';
  static const refreshTokenKey = 'talentum_refresh_token';

  // Recupera os tokens persistidos antes de a primeira tela ser apresentada.
  /// Restaura do armazenamento seguro os tokens da sessão anterior.
  Future<void> restoreSession() async {
    accessToken = await secureStorage.read(accessTokenKey);
    refreshToken = await secureStorage.read(refreshTokenKey);
  }

  // Mantém a sessão somente no armazenamento seguro, nunca em texto de interface.
  /// Persiste os tokens atuais no armazenamento seguro do dispositivo.
  Future<void> _persistTokens() async {
    // As duas gravações são sequenciais; uma falha pode deixar apenas parte do par persistida.
    await secureStorage.write(accessTokenKey, accessToken!);
    await secureStorage.write(refreshTokenKey, refreshToken!);
  }

  // Remove os tokens locais quando o logout ou a renovação falha.
  /// Limpa os tokens em memória e no armazenamento seguro.
  Future<void> clearSession() async {
    accessToken = null;
    refreshToken = null;
    // As exclusões são sequenciais; erro na primeira pode deixar a segunda chave no storage (achado 116).
    await secureStorage.delete(accessTokenKey);
    await secureStorage.delete(refreshTokenKey);
  }

  // Converte respostas JSON e transforma conteúdo inválido em erro de API.
  /// Converte JSON da API e traduz respostas malformadas em erro controlado.
  dynamic _decodeJson(String text) {
    // Respostas sem corpo, como HTTP 204, são representadas por null.
    if (text.trim().isEmpty) return null;
    try {
      return jsonDecode(text);
    } on FormatException {
      throw ApiException('A API retornou uma resposta inválida.', 502);
    }
  }

  // Centraliza timeout, autenticação, tratamento de status e retry após 401.
  /// Executa requisições HTTP com timeout, token, renovação e tratamento de falhas.
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
      // O timeout de close cobre a espera pelos cabeçalhos, não o consumo do corpo abaixo.
      final text = await response.transform(utf8.decoder).join();
      final data = _decodeJson(text);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final detail = data is Map && data['detail'] is String
            ? data['detail'] as String
            : 'Não foi possível concluir a operação.';
        final exception = ApiException(detail, response.statusCode);
        // Renova apenas chamadas protegidas e repete a requisição no máximo uma vez.
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
            // Falha transitória na renovação ou na repetição também apaga os tokens locais.
            await clearSession();
          }
        }
        // Se a limpeza terminar, a falha de renovação não substitui o 401 original (achado 56).
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
  /// Autentica o usuário e persiste os tokens retornados pela API.
  Future<void> login(String email, String password) async {
    final data = await _request(
      '/auth/login',
      method: 'POST',
      body: {'email': email, 'password': password},
    ) as Map<String, dynamic>;
    // A sessão em memória é atualizada antes de confirmar as duas gravações seguras.
    accessToken = data['access_token'] as String;
    refreshToken = data['refresh_token'] as String;
    await _persistTokens();
  }

  // Evita várias renovações simultâneas quando requisições expiram juntas.
  /// Coordena a renovação para evitar chamadas simultâneas com o mesmo token.
  Future<void> _refresh() async {
    final activeRefresh = _refreshCompleter;
    if (activeRefresh != null) return activeRefresh.future;

    final completer = Completer<void>();
    _refreshCompleter = completer;
    try {
      await _performRefresh();
      completer.complete();
    } catch (error, stackTrace) {
      // Sem concorrente, este Future não tem handler e pode gerar erro não tratado.
      completer.completeError(error, stackTrace);
      rethrow;
    } finally {
      _refreshCompleter = null;
    }
  }

  // A renovação usa o refresh token atual e substitui os dois tokens locais.
  /// Troca o token renovável atual por um novo par de tokens.
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
  /// Consulta os dados públicos do usuário autenticado.
  Future<Map<String, dynamic>> me() async =>
      Map<String, dynamic>.from(await _request('/auth/me') as Map);

  /// Carrega o resumo financeiro do cliente para o painel inicial.
  Future<Map<String, dynamic>> dashboard(int clientId) async =>
      Map<String, dynamic>.from(
          await _request('/clients/$clientId/dashboard') as Map);

  /// Carrega posições e alocações da carteira de investimentos.
  Future<Map<String, dynamic>> investmentPortfolio(int clientId) async =>
      Map<String, dynamic>.from(
          await _request('/clients/$clientId/investment-portfolio') as Map);

  /// Consulta o desempenho mensal da carteira e seus indicadores.
  Future<Map<String, dynamic>> investmentMonthlyPerformance(int clientId) async =>
      Map<String, dynamic>.from(await _request(
          '/clients/$clientId/investment-monthly-performance') as Map);

  /// Busca uma página do histórico de operações com filtros aplicados.
  Future<List<dynamic>> investmentTransactions(
    int clientId, {
    String? symbol,
    String? operationType,
    String? dateFrom,
    String? dateTo,
    int limit = 100,
    int offset = 0,
  }) async {
    final query = <String, String>{'limit': '$limit', 'offset': '$offset'};
    if (symbol != null && symbol.trim().isNotEmpty) {
      query['symbol'] = symbol.trim().toUpperCase();
    }
    if (operationType != null && operationType.isNotEmpty) {
      query['operation_type'] = operationType;
    }
    if (dateFrom != null) query['date_from'] = dateFrom;
    if (dateTo != null) query['date_to'] = dateTo;
    final queryString = Uri(queryParameters: query).query;
    return List<dynamic>.from(await _request(
        '/clients/$clientId/investment-transactions?$queryString') as List);
  }

  /// Lista os itens patrimoniais cadastrados para o cliente.
  Future<List<dynamic>> patrimony(int clientId) async => List<dynamic>.from(
      await _request('/clients/$clientId/patrimony') as List);

  /// Lista as metas financeiras registradas para o cliente.
  Future<List<dynamic>> goals(int clientId) async =>
      List<dynamic>.from(await _request('/clients/$clientId/goals') as List);

  /// Carrega ações e tarefas do plano financeiro do cliente.
  Future<List<dynamic>> actionPlan(int clientId) async => List<dynamic>.from(
      await _request('/clients/$clientId/action-plan') as List);

  /// Lista relatórios disponibilizados para o cliente.
  Future<List<dynamic>> reports(int clientId) async =>
      List<dynamic>.from(await _request('/clients/$clientId/reports') as List);

  /// Lista documentos cadastrados para o cliente.
  Future<List<dynamic>> documents(int clientId) async => List<dynamic>.from(
      await _request('/clients/$clientId/documents') as List);

  /// Consulta notificações; a API retorna até 50 por padrão, antes da contagem local.
  Future<List<dynamic>> notifications({bool unreadOnly = false}) async =>
      List<dynamic>.from(
          await _request('/notifications?unread_only=$unreadOnly') as List);

  // Alertas de preço usam o mesmo mecanismo de autenticação e renovação.
  /// Lista alertas de preço associados ao usuário autenticado.
  Future<List<dynamic>> marketAlerts() async =>
      List<dynamic>.from(await _request('/market/alerts') as List);

  /// Registra um novo alerta de preço para um ativo.
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

  /// Atualiza a condição ou os parâmetros de um alerta existente.
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

  /// Solicita o cancelamento do alerta informado.
  Future<Map<String, dynamic>> cancelMarketAlert(int alertId) async =>
      Map<String, dynamic>.from(
          await _request('/market/alerts/$alertId', method: 'DELETE') as Map);

  /// Marca uma notificação específica como lida.
  Future<void> markNotificationRead(int notificationId) async {
    await _request('/notifications/$notificationId/read', method: 'PATCH');
  }

  /// Marca todas as notificações atuais como lidas.
  Future<void> markAllNotificationsRead() async {
    await _request('/notifications/read-all', method: 'PATCH');
  }

  /// Carrega as preferências de recebimento de notificações.
  Future<Map<String, dynamic>> notificationPreferences() async =>
      Map<String, dynamic>.from(
          await _request('/notifications/preferences') as Map);

  /// Salva as preferências de notificação alteradas pelo usuário.
  Future<Map<String, dynamic>> updateNotificationPreferences(
          Map<String, dynamic> body) async =>
      Map<String, dynamic>.from(await _request('/notifications/preferences',
          method: 'PATCH', body: body) as Map);

  // Upload multipart é tratado separadamente porque não envia JSON.
  /// Envia um documento multipart para o cliente selecionado.
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
    // A consulta do arquivo fica antes do try HTTP e não converte falhas locais em ApiException.
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
      final safeFileName = fileName.replaceAll('"', ''); // Aspas são removidas, mas CR/LF ainda podem alterar o cabeçalho multipart (achado 215).
      // Separa os campos e o arquivo com CRLF conforme o formato multipart/form-data.
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
      // O stream pode falhar sem tradução local e não recebe timeout junto com close().
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
            // Também apaga a sessão se a renovação ou a repetição falhar temporariamente.
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
  /// Baixa os bytes do documento autorizado pela API.
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
      // A leitura de todos os bytes não tem timeout próprio após a chegada dos cabeçalhos.
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
            // Também apaga a sessão se a renovação ou a repetição falhar temporariamente.
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

  /// Solicita e baixa o relatório detalhado da carteira em PDF.
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
      // O limite de 60 segundos encerra na resposta inicial, não na conclusão deste download.
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
            // Também apaga a sessão se a renovação ou a repetição falhar temporariamente.
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
  /// Consulta renda, despesas e perfil de risco do cliente.
  Future<Map<String, dynamic>?> financialProfile(int clientId) async {
    try {
      return Map<String, dynamic>.from(
        await _request('/clients/$clientId/financial-profile') as Map,
      );
    } on ApiException catch (exception) {
      // Um perfil financeiro ainda não cadastrado é exposto à tela como ausência de dados.
      if (exception.statusCode == 404) return null;
      rethrow;
    }
  }

  // Questionário e avaliação de suitability alimentam a carteira modelo do cliente.
  /// Carrega perguntas, objetivos e contexto financeiro do suitability.
  Future<Map<String, dynamic>> suitabilityQuestionnaire() async =>
      Map<String, dynamic>.from(
          await _request('/clients/me/suitability/questionnaire') as Map);

  /// Consulta a avaliação de suitability mais recente do usuário.
  Future<Map<String, dynamic>?> suitability() async {
    try {
      final data = await _request('/clients/me/suitability');
      return data == null ? null : Map<String, dynamic>.from(data as Map);
    } on ApiException catch (exception) {
      // A ausência de uma avaliação anterior é um estado válido para quem ainda não respondeu.
      if (exception.statusCode == 404) return null;
      rethrow;
    }
  }

  /// Envia respostas e confirmação financeira para gerar uma avaliação.
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

  /// Registra aceite, recusa ou solicitação de ajuste da carteira sugerida.
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

  /// Carrega o perfil cadastral detalhado do cliente.
  Future<Map<String, dynamic>> profile(int clientId) async =>
      Map<String, dynamic>.from(
          await _request('/clients/$clientId/profile') as Map);

  /// Atualiza os dados cadastrais informados para o cliente.
  Future<void> updateProfile(int clientId, Map<String, dynamic> body) async {
    await _request('/clients/$clientId/profile', method: 'PUT', body: body);
  }

  /// Salva renda, despesas e perfil de risco do cliente.
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

  /// Consulta permissões que controlam edições disponíveis ao cliente.
  Future<Map<String, dynamic>> permissions(int clientId) async =>
      Map<String, dynamic>.from(
          await _request('/clients/$clientId/permissions') as Map);

  /// Inclui um item no patrimônio do cliente.
  Future<void> createPatrimony(int clientId, Map<String, dynamic> body) async {
    await _request('/clients/$clientId/patrimony', method: 'POST', body: body);
  }

  /// Cria uma nova meta financeira para o cliente.
  Future<void> createGoal(int clientId, Map<String, dynamic> body) async {
    await _request('/clients/$clientId/goals', method: 'POST', body: body);
  }

  /// Atualiza os campos informados de um item patrimonial.
  Future<void> updatePatrimony(
    int clientId,
    int itemId,
    Map<String, dynamic> body,
  ) async {
    await _request('/clients/$clientId/patrimony/$itemId',
        method: 'PATCH', body: body);
  }

  /// Remove um item patrimonial do cliente.
  Future<void> deletePatrimony(int clientId, int itemId) async {
    await _request('/clients/$clientId/patrimony/$itemId', method: 'DELETE');
  }

  /// Atualiza os campos informados de uma meta financeira.
  Future<void> updateGoal(
    int clientId,
    int goalId,
    Map<String, dynamic> body,
  ) async {
    await _request('/clients/$clientId/goals/$goalId',
        method: 'PATCH', body: body);
  }

  /// Remove uma meta financeira do cliente.
  Future<void> deleteGoal(int clientId, int goalId) async {
    await _request('/clients/$clientId/goals/$goalId', method: 'DELETE');
  }

  // Logout tenta invalidar a sessão no servidor e sempre limpa a sessão local.
  /// Encerra a sessão na API e remove os tokens locais.
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

  /// Altera a senha da conta autenticada e envia a nova credencial.
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
