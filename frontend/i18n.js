/* spendyFRD UI translations.
 * Strings live in the shared locale files: /locales/{en,te,hi}.json (sections "ui" and "categories").
 * Usage: data-i18n="key" (text), data-i18n-placeholder="key", data-i18n-aria="key".
 * In JS: t("key", { name: "x" }) and categoryLabel("Food & Dining").
 */
const LANGS = ["en", "te", "hi"];
const LANG_KEY = "spendyfrd_lang";
// Relative, so it works at "/" (FastAPI) and under a sub-path (GitHub Pages).
// VS Code Live Server (:5500) → the API server on :8000 serves them.
const LOCALES_BASE = location.port === "5500" ? "http://localhost:8000/locales" : "locales";

const locales = {};
let currentLang = "en";
try {
  const saved = localStorage.getItem(LANG_KEY);
  if (LANGS.includes(saved)) currentLang = saved;
} catch (_) { /* storage unavailable */ }

async function loadLocale(lang) {
  if (!locales[lang]) {
    const res = await fetch(`${LOCALES_BASE}/${lang}.json`);
    if (!res.ok) throw new Error(`Locale ${lang} not found`);
    locales[lang] = await res.json();
  }
  return locales[lang];
}

/** Load English (fallback) and the saved language before first render. */
async function initI18n() {
  try {
    await loadLocale("en");
    if (currentLang !== "en") await loadLocale(currentLang);
  } catch (err) {
    console.warn("Translations unavailable:", err);
    currentLang = "en";
  }
}

function t(key, vars = {}) {
  const text = locales[currentLang]?.ui?.[key] ?? locales.en?.ui?.[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? vars[k] : `{${k}}`));
}

function categoryLabel(category) {
  return locales[currentLang]?.categories?.[category] ?? category;
}

function applyTranslations(root = document) {
  document.documentElement.lang = currentLang;
  root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  root.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAria));
    el.title = t(el.dataset.i18nAria);
  });
}

async function setLanguage(lang) {
  if (!LANGS.includes(lang)) return;
  try {
    await loadLocale(lang);
  } catch (err) {
    console.warn(err);
    return;
  }
  currentLang = lang;
  try { localStorage.setItem(LANG_KEY, lang); } catch (_) { /* ignore */ }
  applyTranslations();
}
