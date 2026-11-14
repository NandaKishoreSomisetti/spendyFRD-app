# Translations (English · తెలుగు · हिन्दी)

All text lives in one JSON file per language, shared by the frontend and the backend:

```
locales/
├── en.json   English (reference: every key must exist here)
├── te.json   Telugu
└── hi.json   Hindi
```

## File format

```json
{
  "meta":       { "code": "te", "name": "తెలుగు" },
  "ui":         { "dropTitle": "మీ స్టేట్‌మెంట్‌ను ఇక్కడ వదలండి", "...": "..." },
  "categories": { "Food & Dining": "ఆహారం & భోజనం", "...": "..." },
  "report":     { "title": "ఖర్చుల నివేదిక", "...": "..." }
}
```

| Section | Used by | What it is |
|---|---|---|
| `meta` | both | Language code and the name shown in the language picker |
| `ui` | frontend (`frontend/i18n.js`) | Every label, button, message and placeholder on the page |
| `categories` | both | Display names for categories. **Keys stay in English.** They are the values stored in the database, so never translate a key, only its value. |
| `report` | backend (`backend/app/i18n.py`) | Text in the downloadable PDF report |

## Placeholders

Words in `{braces}` are filled in at runtime and must be kept exactly as they are,
though they can move within the sentence:

```json
"fileImported": "{name}: {n} జోడించబడ్డాయి"      // "statement.csv: 9 జోడించబడ్డాయి"
"top_category": "అత్యధిక ఖర్చు {c}పై: {a} (ఖర్చులో {p}%)."
```

## How it flows

- **UI:** the page loads `/locales/en.json` (fallback) plus the chosen language and remembers the choice.
  In HTML, `data-i18n="key"` sets text, `data-i18n-placeholder="key"` sets a placeholder, and `data-i18n-aria="key"` sets an aria-label and tooltip.
- **PDF:** `GET /api/report.pdf?lang=te` builds the report with `report` + `categories`.
  Noto Sans Telugu and Noto Sans Devanagari fonts (in `backend/app/fonts/`) plus HarfBuzz text shaping render the conjuncts correctly.

## Adding or changing text

1. Add the key to **all three** files (`en.json` first).
2. Run `cd backend && .venv/bin/python -m pytest`. `test_locales_served_and_complete` fails if any language is missing a key.

## Adding a language (e.g. Tamil)

1. Copy `en.json` to `ta.json` and translate the values.
2. Add `"ta"` to `LANGS` in `frontend/i18n.js` and `backend/app/i18n.py`, and add an `<option>` in `frontend/index.html`.
3. For the PDF, add a Noto Sans Tamil font in `backend/app/report.py`.
