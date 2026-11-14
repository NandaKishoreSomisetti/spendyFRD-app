/* Where the Python backend runs.
 *   "server":  the FastAPI server (./run.sh) serves this page and answers /api.
 *   "browser": the same Python code runs in the page via Pyodide (GitHub Pages build).
 * scripts/build_web.py overwrites this file with mode "browser" in dist/.
 */
window.SPENDY_CONFIG = { mode: "server" };
