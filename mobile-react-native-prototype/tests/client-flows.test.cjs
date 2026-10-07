const test = require('node:test');
const assert = require('node:assert/strict');
const { harness, response, sessionStore } = require('./helpers.cjs');

test('suitability envia versão financeira confirmada e respostas do cliente', async () => {
  const requests = [];
  const { api } = harness(async (url, init) => {
    requests.push({ url, init });
    return response(200, { id: 31, status: 'pending_review' });
  }, sessionStore());
  await api.restoreSession();
  await api.submitSuitability('long_term_growth', { product_familiarity: 'stocks_etfs,fiis' }, 'snapshot-hash', true);
  await api.respondToSuitability(31, 'adjustment_requested', 'Prefiro reduzir a parcela de renda variável.');
  assert.equal(requests[0].url.endsWith('/clients/me/suitability'), true);
  assert.deepEqual(JSON.parse(requests[0].init.body), {
    objective: 'long_term_growth',
    answers: { product_familiarity: 'stocks_etfs,fiis' },
    financial_data_version: 'snapshot-hash',
    confirm_financial_situation: true,
  });
  assert.equal(requests[1].url.endsWith('/clients/me/suitability/31/response'), true);
  assert.deepEqual(JSON.parse(requests[1].init.body), {
    response: 'adjustment_requested', note: 'Prefiro reduzir a parcela de renda variável.',
  });
});

test('permissões do cliente e mudanças de patrimônio/metas usam os endpoints protegidos', async () => {
  const requests = [];
  const { api } = harness(async (url, init) => {
    requests.push({ url, init });
    return response(200, { can_edit_goals: true, can_edit_patrimony: false });
  }, sessionStore());
  await api.restoreSession();
  const permissions = await api.permissions(8);
  await api.createGoal(8, { title: 'Reserva', target_value: 1000 });
  await api.updatePatrimony(8, 4, { value: 2500 });
  assert.equal(permissions.can_edit_goals, true);
  assert.equal(requests[0].url.endsWith('/clients/8/permissions'), true);
  assert.deepEqual(requests.map(({ init }) => init.method), [undefined, 'POST', 'PATCH']);
  assert.equal(requests[1].url.endsWith('/clients/8/goals'), true);
  assert.equal(requests[2].url.endsWith('/clients/8/patrimony/4'), true);
});

test('download de documento usa sessão autenticada e grava bytes no cache em base64', async () => {
  let sentAuthorization;
  const store = sessionStore();
  const { api } = harness(async (_url, init) => {
    sentAuthorization = init.headers.Authorization;
    return new Response(new TextEncoder().encode('Talentum PDF'), { status: 200 });
  }, store);
  await api.restoreSession();
  const uri = await api.downloadDocument(8, 91, 'extrato março.pdf');
  assert.equal(sentAuthorization, 'Bearer old-access');
  assert.equal(uri, 'file:///cache/extrato_mar_o.pdf');
  assert.equal(store.get(`$file:${uri}`), 'base64:VGFsZW50dW0gUERG');
});
