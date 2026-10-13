const test = require('node:test');
const assert = require('node:assert/strict');
const { harness, response } = require('./helpers.cjs');

// Prepara API, cache e callbacks controlados para testar o carregamento do workspace.
// Prepara respostas padrão dos módulos e uma API simulada para cada cenário.
function setup() {
  const context = harness(async () => { throw new Error('Unexpected fetch'); });
  const mockApi = Object.fromEntries(Object.keys(context.emptyWorkspace).map((key) => [key, async () => {
    if (['notifications', 'documents', 'patrimony', 'goals', 'actionPlan', 'reports', 'marketAlerts'].includes(key)) return [{ id: 1 }];
    return { id: 1 };
  }]));
  // O nome usado pelo workspace difere do método público da API.
  mockApi.investmentMonthlyPerformance = (...args) => mockApi.monthlyPerformance(...args);
  return { ...context, mockApi };
}

// Garante que falha da carteira não impeça o carregamento das demais áreas.
test('carteira indisponível não bloqueia os outros módulos', async () => {
  const { mockApi, ApiError, fetchWorkspace } = setup();
  mockApi.portfolio = async () => { throw new ApiError('Indisponível', 503); };
  const { data, errors, fallbackEligible } = await fetchWorkspace(mockApi, 1);
  assert.equal(data.portfolio, null);
  assert.ok(errors.portfolio);
  assert.deepEqual(data.documents, [{ id: 1 }]);
  assert.deepEqual(data.dashboard, { id: 1 });
  assert.equal(fallbackEligible.portfolio, true);
  assert.equal(Boolean(fallbackEligible.documents), false);
  assert.deepEqual(Object.keys(errors), ['portfolio']);
});

// Confirma que falhas de módulos opcionais apareçam como erros identificáveis.
test('módulos antes silenciados exibem erro em vez de ausência de dados', async () => {
  const { mockApi, ApiError, fetchWorkspace } = setup();
  const failed = ['notifications', 'notificationPreferences', 'suitability', 'marketAlerts'];
  for (const key of failed) mockApi[key] = async () => { throw new ApiError('Offline', 0); };
  const { errors } = await fetchWorkspace(mockApi, 1);
  assert.deepEqual(Object.keys(errors).sort(), failed.sort());
});

// Distingue falta de autorização de indisponibilidade sem interromper o app.
test('permissão negada é distinta de indisponibilidade e não bloqueia o app', async () => {
  const { mockApi, ApiError, fetchWorkspace } = setup();
  mockApi.documents = async () => { throw new ApiError('Proibido', 403); };
  const { data, errors } = await fetchWorkspace(mockApi, 1);
  assert.match(errors.documents, /não está autorizado/);
  assert.deepEqual(data.goals, [{ id: 1 }]);
});

// Garante que expiração da sessão encerre o carregamento em qualquer módulo.
test('401 em qualquer módulo interrompe o acesso, incluindo módulos opcionais', async () => {
  const { mockApi, ApiError, fetchWorkspace, emptyWorkspace } = setup();
  for (const key of Object.keys(emptyWorkspace)) {
    const method = key === 'monthlyPerformance' ? 'investmentMonthlyPerformance' : key;
    const failing = { ...mockApi, [method]: async () => { throw new ApiError('Expirada', 401); } };
    await assert.rejects(fetchWorkspace(failing, 1), (error) => error.status === 401);
  }
});

// Verifica que nova tentativa bem-sucedida limpe o erro anterior do módulo.
test('nova atualização limpa o erro anterior e recupera o módulo', async () => {
  const { mockApi, ApiError, fetchWorkspace } = setup();
  mockApi.documents = async () => { throw new ApiError('Offline', 0); };
  assert.ok((await fetchWorkspace(mockApi, 1)).errors.documents);
  mockApi.documents = async () => [{ id: 7 }];
  const recovered = await fetchWorkspace(mockApi, 1);
  assert.deepEqual(recovered.errors, {});
  assert.deepEqual(recovered.data.documents, [{ id: 7 }]);
});

// Preserva estados vazios legítimos sem classificá-los como falhas de API.
test('um resultado vazio legítimo não recebe aviso de falha', async () => {
  const { api, fetchWorkspace } = harness(async (url) => {
    if (url.endsWith('/suitability') || url.endsWith('/financial-profile')) return response(404, {});
    return response(200, []);
  });
  const { data, errors } = await fetchWorkspace(api, 1);
  assert.equal(data.suitability, null);
  assert.equal(data.financialProfile, null);
  assert.deepEqual(data.documents, []);
  assert.deepEqual(errors, {});
});
