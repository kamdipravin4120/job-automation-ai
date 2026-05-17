# SP2: Android Companion App — Foundation Design

**Date:** 2026-05-06  
**Sprint:** SP2  
**Scope:** Read-only + light interactions (star, dismiss, scrape trigger)  
**Stack:** Kotlin · Jetpack Compose · MVVM · Clean Architecture · Hilt · Room · Retrofit

---

## 1. Scope

SP2 ships the Android companion app that connects to the existing job-automation-ai VPS backend.

**In scope:**
- One-time device pairing via QR code
- Dashboard: pipeline KPIs, recent activity feed
- Job list: browsable, searchable, filterable by score/date
- Application tracker: grouped by status with interview progress timeline
- Star and dismiss jobs (write these two endpoints to backend)
- Trigger a scrape run from the app

**Out of scope (SP3+):**
- Apply flow (auto-fill, submit)
- Push notification delivery UI (infra is done in W4c; in-app display is SP3)
- Settings/preferences screen
- Multi-server support

---

## 2. Architecture

### 2.1 Layer Stack

```
UI (Compose screens)
    │
ViewModel (StateFlow, one per screen)
    │
UseCases (single-responsibility, in domain/)
    │
Repository (interface in domain/, impl in data/)
    ├── Remote: Retrofit API calls
    └── Local:  Room DAO (offline cache)
```

### 2.2 Key Libraries

| Layer | Library |
|-------|---------|
| DI | Hilt |
| UI | Jetpack Compose + Material 3 |
| Navigation | Compose Navigation |
| Async | Kotlin Coroutines + Flow |
| Network | Retrofit + OkHttp + Moshi |
| Local DB | Room |
| Secure storage | AndroidX Security (EncryptedSharedPreferences) |
| Crypto | Android Keystore (Ed25519) |
| Image | Coil |

### 2.3 Module Structure

```
app/
  src/main/
    auth/          — pairing flow, keypair, session
    home/          — dashboard screen + viewmodel
    jobs/          — job list screen + viewmodel
    tracker/       — application tracker screen + viewmodel
    runs/          — pipeline runs screen (placeholder in SP2)
    core/
      api/         — Retrofit service interfaces
      db/          — Room database + DAOs
      model/       — shared data classes
      ui/          — design system (colors, typography, components)
      util/        — extensions, formatters
```

---

## 3. Authentication & Pairing

### 3.1 Flow (4 screens)

```
Welcome → QR Scan → Connecting → Paired
```

**Welcome:** app icon, "Connect your pipeline" hero, "Pair with Server" CTA, security badges (Keystore · Ed25519 · TLS 1.3).

**QR Scan:** full-bleed camera view, animated cyan scan beam with RGB chromatic effect, HUD grid overlay, corner brackets. User runs `docker logs jobai | grep QR` on VPS to get code.

**Connecting:** dashed outer orbit ring with revolving dot, gradient progress arc, 5-step chain:
1. Bootstrap secret verified
2. Ed25519 keypair generated (Android Keystore)
3. Pairing with server (active)
4. Session token stored
5. Ready

**Paired:** triple-pulse green rings, "You're in", glassmorphism device card (name, pair time, device #, fingerprint hash), security note, "Enter Dashboard" CTA.

### 3.2 Crypto Protocol

```
QR payload  →  { url, bootstrap_secret }
App          →  generate Ed25519 keypair in Android Keystore (non-exportable)
App          →  POST /auth/pair { public_key, bootstrap_secret, device_name }
Server       →  returns { session_token, device_id }
App          →  store session_token in EncryptedSharedPreferences
App          →  store device_id in EncryptedSharedPreferences
Bootstrap secret invalidated on server after one use.
```

All subsequent API calls: `Authorization: Bearer <session_token>` header via OkHttp interceptor.

### 3.3 Backend Gaps (must add before SP2 ships)

| Endpoint | Status | Needed for |
|----------|--------|-----------|
| `GET /auth/devices` | Missing | device list in Settings |
| `POST /jobs/{id}/star` | Missing | star interaction |
| `POST /jobs/{id}/dismiss` | Missing | dismiss interaction |

---

## 4. Navigation

5-tab bottom navigation:

| Tab | Icon | Screen |
|-----|------|--------|
| Home | house | Dashboard |
| Jobs | briefcase | Job list |
| Applied | checkbox | Application tracker |
| Runs | star/sparkle | Pipeline runs |
| More | settings/gear | Settings (SP3) |

Active tab: `#1E40AF` fill + 4px indicator dot below icon.

---

## 5. Design System

### 5.1 Light Theme (all main screens)

| Token | Value |
|-------|-------|
| Background | `#F8FAFC` |
| Surface | `#FFFFFF` |
| Border | `#E2E8F0` |
| Primary | `#1E40AF` |
| Primary surface | `#EFF6FF` |
| CTA / amber accent | `#F59E0B` |
| Text primary | `#0F172A` |
| Text muted | `#64748B` |
| Text disabled | `#94A3B8` |
| Score high (≥75) | `#1E40AF` |
| Score mid (50–74) | `#D97706` |
| Score low (<50) | `#BE123C` |

### 5.2 Pairing Flow (dark glassmorphism)

| Token | Value |
|-------|-------|
| Background | `#030308` |
| Surface | `rgba(255,255,255,0.04)` |
| Border | `rgba(255,255,255,0.08)` |
| Border highlight | `rgba(255,255,255,0.15)` |
| Blur | `blur(24px)` |
| Accent | `#60A5FA` |
| Neon | `#22D3EE` |
| Success | `#34D399` |
| Aurora orbs | purple `rgba(109,40,217,0.26)` · cyan `rgba(14,165,233,0.17)` · violet `rgba(167,139,250,0.15)` |

### 5.3 Typography

- Headings: Inter 800–900, tracking −1.5px to −0.5px
- Body: Inter 400–500, 16sp minimum on mobile
- Monospace (IPs, hashes, commands): Fira Code 400–500

### 5.4 Score Ring

SVG circle with `stroke-dasharray` proportional to score (50 segments total).  
Color coded by threshold. Used on job cards (22px) and job detail header (64px).

---

## 6. Screens

### 6.1 Dashboard (Home tab)

- Top bar: greeting + notification bell
- KPI row: 3 chips — Total Jobs · Applied · Match Avg
- Pipeline status card: last run time, next scheduled, run count
- Recent activity feed: timestamped events (job scraped, application sent, interview scheduled)
- Quick action: "Trigger Scrape" button

### 6.2 Job List (Jobs tab)

- Search bar + filter chip row (Score · Date · Remote · Status)
- Scrollable list of job cards
- Each card: company initial avatar, job title, company + location, score ring + score value, date scraped, star/dismiss swipe actions
- Score ring color-coded (blue/amber/red by threshold)
- Pull-to-refresh triggers sync from server

### 6.3 Application Tracker (Applied tab)

- Summary chips row: Applied count · Interview count · Offer count
- 4-tab bar: Applied | Screens | Interview | Closed
- **Applied tab:** cards grouped "This week" / "Earlier", each with score ring, status badge, date, next-action label
- **Interview tab:** cards with interview round progress timeline (dot + connector line per stage, color fills done rounds), next event highlighted in amber
- **Closed tab:** rejected and offer cards; offer card shows salary + decision deadline, elevated with green left border
- Left-border accent on interview-active cards (orange `#F97316`) and offer cards (green `#22C55E`)

### 6.4 Pipeline Runs (Runs tab)

- Placeholder list of recent scrape runs in SP2
- Each row: run ID, timestamp, jobs found count, status badge (success/failed/running)
- "Trigger Run" FAB

---

## 7. Interactions (SP2)

| Interaction | Gesture | API call |
|-------------|---------|---------|
| Star job | Tap star icon on card | `POST /jobs/{id}/star` |
| Dismiss job | Swipe left on card | `POST /jobs/{id}/dismiss` |
| Trigger scrape | Tap button on Dashboard or Runs | `POST /pipeline/runs` |
| Refresh | Pull-to-refresh | `GET /jobs` + `GET /applications` |

All other interactions (apply, edit, delete) are read-only — tapping navigates to detail view only.

---

## 8. Offline Behavior

Room is the single source of truth. On app open:
1. Render from Room immediately (no loading flash)
2. Fetch updates from API in background
3. Diff-merge into Room
4. UI updates reactively via Flow

If server unreachable: show "Last synced X minutes ago" banner. All read views still work. Write interactions (star/dismiss/trigger) queue and retry on reconnect.

---

## 9. Error States

| Scenario | UI |
|----------|-----|
| Pairing fails (bad QR / network) | Inline error on Connecting screen, retry button |
| Session expired | Intercept 401, show re-pair bottom sheet |
| No internet on launch | Offline banner, stale data visible |
| Empty job list | Illustrated empty state + "Trigger Scrape" CTA |
| Star/dismiss fails | Toast: "Couldn't save — will retry" |

---

## 10. Out-of-Scope Decisions

- **No Google account / OAuth login** — VPS pairing is the only auth mechanism
- **No background sync service** — sync on foreground only to conserve battery
- **No biometric gate** — session token is in EncryptedSharedPreferences which requires device unlock
- **No tablet layout** — phone-only in SP2
