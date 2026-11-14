/* Web Worker that runs the spendyFRD Python backend in the browser (Pyodide).
 *
 * Boot: load Pyodide, then the Python packages and the app code built by
 * scripts/build_web.py (py/manifest.json, py/wheels/*.whl, py/spendy_app.zip).
 * The SQLite database lives at /data/spendy.db on IndexedDB (IDBFS), so it
 * survives reloads and never leaves the browser.
 *
 * Protocol: {id, method, path, query, headers, body: ArrayBuffer}
 *        → {id, status, headers, body: ArrayBuffer} | {id, error}
 */
const PYODIDE_VERSION = "314.0.7";
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

let handle = null;
let pyodide = null;
let queue = Promise.resolve(); // requests run one at a time (SQLite + IndexedDB sync)

const post = (msg, transfer) => self.postMessage(msg, transfer || []);
const status = (stage) => post({ type: "status", stage });

function syncFS(populate) {
  return new Promise((resolve, reject) =>
    pyodide.FS.syncfs(populate, (err) => (err ? reject(err) : resolve())));
}

async function boot() {
  status("runtime");
  const { loadPyodide } = await import(`${PYODIDE_URL}pyodide.mjs`);
  pyodide = await loadPyodide({ indexURL: PYODIDE_URL });

  const manifest = await (await fetch("py/manifest.json", { cache: "no-cache" })).json();
  status("packages");
  await pyodide.loadPackage(manifest.pyodide_packages);

  const wheelDir = "/tmp/wheels";
  pyodide.FS.mkdirTree(wheelDir);
  await Promise.all(manifest.wheels.map(async (name) => {
    const buf = await (await fetch(`py/wheels/${name}`)).arrayBuffer();
    pyodide.FS.writeFile(`${wheelDir}/${name}`, new Uint8Array(buf));
  }));
  const micropip = pyodide.pyimport("micropip");
  await micropip.install(manifest.wheels.map((n) => `emfs:${wheelDir}/${n}`), { deps: false });

  status("app");
  const appZip = await (await fetch(`py/spendy_app.zip?v=${manifest.build}`)).arrayBuffer();
  pyodide.unpackArchive(new Uint8Array(appZip), "zip", { extractDir: "/home/pyodide/spendy" });
  pyodide.FS.mkdirTree("/home/pyodide/locales");
  await Promise.all(["en", "te", "hi"].map(async (lang) => {
    const text = await (await fetch(`locales/${lang}.json?v=${manifest.build}`)).text();
    pyodide.FS.writeFile(`/home/pyodide/locales/${lang}.json`, text);
  }));

  pyodide.FS.mkdirTree("/data");
  pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, {}, "/data");
  await syncFS(true); // restore the saved database

  await pyodide.runPythonAsync(`
import os, sys
os.environ["SPENDY_DB"] = "/data/spendy.db"
os.environ["SPENDY_LOCALES"] = "/home/pyodide/locales"
sys.path.insert(0, "/home/pyodide/spendy")
from app.wasm import handle
`);
  handle = pyodide.globals.get("handle");
  status("ready");
}

const ready = boot().catch((err) => {
  post({ type: "status", stage: "failed", message: String(err?.message || err) });
  throw err;
});

async function dispatch({ id, method, path, query, headers, body }) {
  await ready;
  const result = await handle(method, path, query, headers, new Uint8Array(body));
  const [code, respHeaders, respBody] = result.toJs();
  result.destroy();
  if (method !== "GET") await syncFS(false); // persist changes to IndexedDB
  const out = respBody.slice().buffer; // copy out of wasm memory
  post({ id, status: code, headers: respHeaders, body: out }, [out]);
}

self.onmessage = (e) => {
  const msg = e.data;
  queue = queue
    .then(() => dispatch(msg))
    .catch((err) => post({ id: msg.id, error: String(err?.message || err) }));
};
