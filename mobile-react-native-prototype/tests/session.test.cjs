const test = require('node:test');
const assert = require('node:assert/strict');
const { harness, response, deferred, sessionStore } = require('./helpers.cjs');

test('requisições paralelas com 401 compartilham uma única renovação', async () => {
  const refreshStarted = deferred();
  const releaseRefresh = deferred();
  let refreshes = 0;
  const { api, store } = harness(async (url, init) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes++;
      assert.equal(JSON.parse(init.body).refresh_token, 'old-refresh');
      refreshStarted.resolve();
      await releaseRefresh.promise;
      return response(200, { access_token: 'new-access', refresh_token: 'new-refresh' });
    }
    return init.headers.Authorization === 'Bearer new-access'
      ? response(200, { id: 1 }) : response(401, { detail: 'Expirado' });
  }, sessionStore());
  await api.restoreSession();
  const calls = Promise.all(Array.from({ length: 13 }, () => api.me()));
  await refreshStarted.promise;
  releaseRefresh.resolve();
  assert.equal((await calls).length, 13);
  assert.equal(refreshes, 1);
  assert.equal(store.get('talentum_prototype_refresh_token'), 'new-refresh');
});

test('401 atrasado reutiliza o token já renovado', async () => {
  const delayed = deferred();
  let oldCalls = 0;
  let refreshes = 0;
  const { api } = harness(async (url, init) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes++;
      return response(200, { access_token: 'new-access', refresh_token: 'new-refresh' });
    }
    if (init.headers.Authorization === 'Bearer new-access') return response(200, { id: 1 });
    if (++oldCalls === 2) await delayed.promise;
    return response(401, {});
  }, sessionStore());
  await api.restoreSession();
  const first = api.me();
  const second = api.me();
  await first;
  delayed.resolve();
  assert.deepEqual(await second, { id: 1 });
  assert.equal(refreshes, 1);
});

for (const status of [0, 503]) {
  test(`falha temporária ${status} ao renovar preserva a sessão e permite tentar novamente`, async () => {
    let unavailable = true;
    const { api, store } = harness(async (url, init) => {
      if (url.endsWith('/auth/refresh')) {
        if (unavailable) {
          if (status === 0) throw new TypeError('offline');
          return response(status, {});
        }
        return response(200, { access_token: 'new-access', refresh_token: 'new-refresh' });
      }
      return response(init.headers.Authorization === 'Bearer new-access' ? 200 : 401, { id: 1 });
    }, sessionStore());
    await api.restoreSession();
    await assert.rejects(api.me(), (error) => error.status === status);
    assert.equal(store.get('talentum_prototype_refresh_token'), 'old-refresh');
    unavailable = false;
    assert.deepEqual(await api.me(), { id: 1 });
  });
}

test('refresh rejeitado limpa os tokens e notifica a tela uma única vez', async () => {
  let expired = 0;
  const { api, store } = harness(async () => response(401, {}), sessionStore());
  await api.restoreSession();
  api.onSessionExpired(() => expired++);
  const results = await Promise.allSettled([api.me(), api.me(), api.me()]);
  assert.ok(results.every((result) => result.status === 'rejected' && result.reason.status === 401));
  assert.equal(store.size, 0);
  assert.equal(expired, 1);
});

test('401 após uma renovação não entra em loop e encerra a sessão', async () => {
  let refreshes = 0;
  const { api, store } = harness(async (url) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes++;
      return response(200, { access_token: 'new-access', refresh_token: 'new-refresh' });
    }
    return response(401, {});
  }, sessionStore());
  await api.restoreSession();
  await assert.rejects(api.me(), (error) => error.status === 401);
  assert.equal(refreshes, 1);
  assert.equal(store.size, 0);
});

test('logout durante refresh impede que a resposta restaure a sessão', async () => {
  const started = deferred();
  const finish = deferred();
  const { api, store } = harness(async (url) => {
    if (url.endsWith('/auth/refresh')) {
      started.resolve();
      await finish.promise;
      return response(200, { access_token: 'new-access', refresh_token: 'new-refresh' });
    }
    return response(401, {});
  }, sessionStore());
  await api.restoreSession();
  const pending = assert.rejects(api.me(), (error) => error.status === 401);
  await started.promise;
  await api.logout();
  finish.resolve();
  await pending;
  assert.equal(store.size, 0);
  assert.equal(await api.restoreSession(), false);
});

test('logout aguarda uma gravação já iniciada e remove todos os tokens', async () => {
  const started = deferred();
  const finish = deferred();
  const { api, store, secureStore } = harness(async (url) => url.endsWith('/auth/refresh')
    ? response(200, { access_token: 'new-access', refresh_token: 'new-refresh' })
    : response(401, {}), sessionStore());
  await api.restoreSession();
  const write = secureStore.setItemAsync;
  secureStore.setItemAsync = async (key, value) => {
    started.resolve();
    await finish.promise;
    await write(key, value);
  };
  const pending = assert.rejects(api.me(), (error) => error.status === 401);
  await started.promise;
  const logout = api.logout();
  finish.resolve();
  await Promise.all([pending, logout]);
  assert.equal(store.size, 0);
});

test('resposta da conta anterior não interfere no novo login', async () => {
  const delayed = deferred();
  const { api, store } = harness(async (url) => {
    if (url.endsWith('/auth/login')) return response(200, { access_token: 'other-access', refresh_token: 'other-refresh' });
    await delayed.promise;
    return response(401, {});
  }, sessionStore());
  await api.restoreSession();
  const pending = assert.rejects(api.me(), (error) => error.status === 401);
  await api.login('other@example.test', 'example');
  delayed.resolve();
  await pending;
  assert.equal(store.get('talentum_prototype_refresh_token'), 'other-refresh');
});

test('JSON inválido não vira módulo vazio; null e 204 continuam válidos', async () => {
  const { api } = harness(async (url) => {
    if (url.endsWith('/read-all')) return response(204);
    if (url.endsWith('/suitability')) return response(200, null);
    return new Response('<html>proxy indisponível</html>', { status: 200 });
  });
  await assert.rejects(api.me(), (error) => error.status === 502);
  assert.equal(await api.suitability(), null);
  await api.markAllNotificationsRead();
});

test('requisição sem resposta tem prazo e mantém a sessão para nova tentativa', async () => {
  let expire;
  let cleared = false;
  const { api, store } = harness(async (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
  }), sessionStore(), {
    setTimeout: (callback, delay) => { assert.equal(delay, 30_000); expire = callback; return 1; },
    clearTimeout: () => { cleared = true; },
  });
  await api.restoreSession();
  const pending = assert.rejects(api.me(), (error) => error.status === 0 && /demorou/.test(error.message));
  expire();
  await pending;
  assert.ok(cleared);
  assert.equal(store.get('talentum_prototype_refresh_token'), 'old-refresh');
});
