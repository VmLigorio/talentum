const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

// Executa o TypeScript real; somente os adaptadores nativos e a rede são simulados.
function harness(fetch, store = new Map(), timers = { setTimeout, clearTimeout }) {
  const cache = new Map();
  const secureStore = {
    getItemAsync: async (key) => store.get(key) ?? null,
    setItemAsync: async (key, value) => { store.set(key, value); },
    deleteItemAsync: async (key) => { store.delete(key); },
  };
  function load(file) {
    if (cache.has(file)) return cache.get(file).exports;
    const module = { exports: {} };
    cache.set(file, module);
    const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText;
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
  return { ...apiModule, ...workspaceModule, api: new apiModule.TalentumApi(), store, secureStore };
}

const response = (status, data) => new Response(status === 204 ? null : JSON.stringify(data), { status });
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};
const sessionStore = () => new Map([
  ['talentum_prototype_access_token', 'old-access'],
  ['talentum_prototype_refresh_token', 'old-refresh'],
]);
module.exports = { harness, response, deferred, sessionStore };
