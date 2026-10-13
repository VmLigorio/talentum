const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

// Executa o TypeScript real; somente os adaptadores nativos e a rede são simulados.
// Carrega o cliente real com serviços de rede, armazenamento e tempo simulados.
// Devolve as funções exportadas junto com o armazenamento usado no cenário.
function harness(fetch, store = new Map(), timers = { setTimeout, clearTimeout }) {
  const cache = new Map();
  const secureStore = {
    getItemAsync: async (key) => store.get(key) ?? null,
    setItemAsync: async (key, value) => { store.set(key, value); },
    deleteItemAsync: async (key) => { store.delete(key); },
  };
  // Avalia o módulo isolado no contexto de teste e devolve sua exportação.
  function load(file) {
    if (cache.has(file)) return cache.get(file).exports;
    const module = { exports: {} };
    cache.set(file, module);
    const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText;
    // Substitui somente os módulos externos usados pelo código carregado.
    const localRequire = (id) => {
      if (id === 'expo-secure-store') return secureStore;
      if (id === 'expo-local-authentication') return {};
      if (id === 'expo-file-system') return {
        cacheDirectory: 'file:///cache/',
        documentDirectory: 'file:///documents/',
        EncodingType: { Base64: 'base64' },
        writeAsStringAsync: async (path, contents, options) => { store.set(`$file:${path}`, `${options.encoding}:${contents}`); },
      };
      if (id.startsWith('.')) return load(path.resolve(path.dirname(file), id + '.ts'));
      return require(id);
    };
    new Function('require', 'module', 'exports', 'fetch', 'setTimeout', 'clearTimeout', source)(
      localRequire, module, module.exports, fetch, timers.setTimeout, timers.clearTimeout,
    );
    return module.exports;
  }
  const apiModule = load(path.resolve(__dirname, '../src/api.ts'));
  const workspaceModule = load(path.resolve(__dirname, '../src/workspace.ts'));
  const moneyModule = load(path.resolve(__dirname, '../src/money.ts'));
  return { ...apiModule, ...workspaceModule, ...moneyModule, api: new apiModule.TalentumApi(), store, secureStore };
}

// Monta uma resposta Fetch com corpo JSON, exceto em respostas sem conteúdo.
const response = (status, data) => new Response(status === 204 ? null : JSON.stringify(data), { status });
// Cria um par de promessas cuja conclusão fica sob controle do cenário.
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};
// Fornece tokens já persistidos para os casos que começam autenticados.
const sessionStore = () => new Map([
  ['talentum_prototype_access_token', 'old-access'],
  ['talentum_prototype_refresh_token', 'old-refresh'],
]);
module.exports = { harness, response, deferred, sessionStore };
