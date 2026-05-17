---
name: W3 Operator Console — In Progress
description: Current branch, completed work, open bug, and next steps for W3 console implementation
type: project
---

Branch: `prod/w3-console`

**Why:** W3 adds the Orbital Command SPA operator console — integrations, DLQ, config versions, audit log, selector overrides routers + full OLED/HUD UI. Plan at `docs/superpowers/plans/2026-04-26-w3-operator-console.md`.

**How to apply:** Resume at Task 3 (integrations router). Tests at `tests/api/test_integrations.py` already exist.

---

## W2 — Complete (2026-04-26, branch merged)

All 20 tasks shipped. 44/44 API tests pass.

---

## W3 — Completed So Far (2026-04-28)

| Commit | What shipped |
|--------|--------------|
| `d49123e` | StaticFiles mount + SPA catch-all route |
| `4b48705` | AuditLog, Integration, SelectorOverride, ConfigVersion repositories |
| `935c854` | ACID-safe `IntegrationsRepository.upsert()` (INSERT ON CONFLICT) |
| `6aefe5d` | Pydantic schemas — integrations, DLQ, config, audit, selectors |
| `0ee19d0` | Auth bug fix: Ed25519 pairing switched PEM → DER hex (all 44 tests green) |
| `cfa7780` | Auth bug fix: `_normalize_pem()` + JWT keypair added to `.env` |

**UI complete:** Orbital Command OLED dark / HUD sci-fi SPA — CSS custom properties, radar ring animations, HUD corner brackets, toast notifications, skeleton loading, SVG Heroicons nav, live clock in topbar.

**Autostart:** 3-service systemd chain on login:
- `job-automation-ai-infra.service` — docker compose up (Postgres + Redis)
- `job-automation-ai.service` — FastAPI server
- `job-automation-ai-browser.service` — polls /health then xdg-open localhost:8000

---

## Auth Bugs Fixed (Root Causes)

1. **PEM → DER hex migration** (`0ee19d0`): Browser `crypto.subtle.exportKey('spki')` exports DER bytes. Original code used a fragile `_rawToPem` spread-operator btoa. Fixed by: browser sends `_bytesToHex(new Uint8Array(spkiDer))`, server uses `load_der_public_key(bytes.fromhex(...))`.

2. **JWT key missing from .env** (`cfa7780`): Server fell back to `SecretStr("placeholder")` for `jwt_private_key`. `create_jwt()` called `load_pem_private_key("placeholder")` → ValueError with "Unable to load PEM file. MalformedFraming". Fixed by: generating Ed25519 keypair and appending to `.env`; adding `_normalize_pem()` to expand literal `\n` from systemd EnvironmentFile.

---

## Next Steps (after reboot verification)

1. **Verify browser pairing works** — generate bootstrap secret with `python main.py bootstrap`, paste into localhost:8000, confirm token stored in localStorage
2. **Task 3: integrations router** — `src/api/routers/integrations.py`, test at `tests/api/test_integrations.py`
3. **Tasks 4–8:** DLQ, config versions, audit log, selectors routers
4. **Mount all W3 routers** in `create_app()`

---

## Key File Locations

- Settings: `src/settings.py` (get_settings LRU-cached)
- Auth service: `src/api/services/auth.py` (pair_device, store_challenge)
- JWT helpers: `src/api/core/security.py` (create_jwt, decode_jwt, _normalize_pem)
- Auth router: `src/api/routers/auth.py`
- SPA static: `static/` (index.html, style.css, app.js, auth.js)
- Repositories: `src/data/repositories/` (devices, audit_logs, integrations, selector_overrides, config_versions)
- W3 schemas: `src/api/schemas/` (integrations.py, dlq.py, config.py, audit.py, selectors.py)
- Test conftest: `tests/conftest.py` (testcontainers Postgres+Redis, JWT key fixtures)
- W3 Plan: `docs/superpowers/plans/2026-04-26-w3-operator-console.md`

## Known Pre-existing Failures

- `tests/test_notion_sync.py` — `FakeNotionAPIClient` missing `query_database` — unrelated to W3
