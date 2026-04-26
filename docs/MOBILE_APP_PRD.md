# Mobile Companion App — Product Requirements Document

**Project:** Job Automation AI — Mobile Companion
**Platform:** Native Android (Kotlin + Jetpack Compose)
**Status:** Design approved — pending UI/UX mockups and backend readiness
**Owner:** Pravin Kamdi
**Document version:** 1.0 (2026-04-21)

---

## 1. Purpose

A production-grade Android companion that lets the user run the entire job-application pipeline from a phone: trigger scrapes, review AI-ranked jobs, apply (Easy Apply automated on backend, deep-link for external ATS), track application status, and edit/send follow-up emails and LinkedIn messages. Replaces the need to sit in front of a laptop for day-to-day job-search operations.

The mobile app is a **thin client**. All scraping, LLM calls, Playwright automation, and persistence live on a VPS-hosted backend. The phone is a fast, opinionated UI over that backend.

## 2. Non-goals

- Running Playwright, Claude, or OpenAI locally on the device.
- Offline apply (applications require the backend).
- iOS support in v1 (API is designed so an iOS client can be added later without backend changes).
- Multi-user / multi-tenant operation (single user, multiple devices).
- Job-board discovery beyond LinkedIn + Naukri (matching existing scraper scope).

## 3. Primary user & jobs-to-be-done

**Persona — Experienced engineer job-seeking on the move.**
- Commutes, travels, or otherwise isn't at a laptop for long stretches.
- Wants to triage AI-ranked jobs in 30-second bursts.
- Willing to review AI-generated resume tailoring before submission.
- Cares about follow-up cadence; hates manually typing emails.
- Trusts automation *conditionally* — wants a human-in-the-loop gate before final submission.

**Jobs-to-be-done (JTBD):**
1. "When a notification pings me, I want to see whether this new job is worth applying to in under 15 seconds."
2. "When I have 3 minutes in a cab, I want to kick off an Easy Apply and approve whatever fields the bot couldn't fill."
3. "When a recruiter replies, I want to send a well-written follow-up without opening my laptop."
4. "When I see a rejection, I want to update status and not have that application nag me again."

## 4. Success metrics

| Metric | Target |
|---|---|
| Time from push-notification to applied | < 90 seconds median |
| % of Easy Apply runs fully completed on phone without laptop fallback | ≥ 85% |
| Follow-up emails sent per week (vs. baseline 0 from laptop-only flow) | ≥ 10 |
| Crash-free session rate | ≥ 99.5% |
| Cold start p50 | < 1.5 s |

## 5. Scope & sub-project decomposition

The mobile rollout is split into five sequentially-built sub-projects. Each has its own implementation plan; all share the data model, auth, and deployment sections of this PRD.

| # | Sub-project | Ships |
|---|---|---|
| **SP1** | **Backend API + VPS deployment** | FastAPI exposes pipeline behind auth; Docker-compose on Hetzner-class VPS; Postgres + Redis + Playwright worker; Gmail OAuth. Prereq for all mobile work. |
| **SP2** | **Android foundation** | Auth pairing flow, dashboard, job list, job detail, application history — read-only companion per `docs/APP_GUIDELINES.md`. |
| **SP3** | **Remote apply + live status** | Phone triggers Easy Apply; watches progress over WebSocket; approves manual-review steps; deep-links for external ATS. |
| **SP4** | **Follow-up Gmail composer** | Claude-drafted email, user edits, backend sends via Gmail OAuth. Threaded view per application. |
| **SP5** | **LinkedIn follow-up messages** | Backend Playwright DMs; phone composes/reviews; strict rate limits; account-safety guardrails. |

## 6. System architecture

```
┌──────────────────────────┐    HTTPS + WSS   ┌──────────────────────────────────────────┐
│   Android companion app  │ ◄──────────────► │                VPS (Docker)               │
│   Compose · Hilt · Room  │                  │  ┌──────────────────────────────────┐    │
│   EncryptedSharedPrefs   │                  │  │  FastAPI — REST + WebSocket      │    │
│   FCM receiver           │                  │  │  /api/v1/*  /ws                  │    │
└──────────┬───────────────┘                  │  └──────────────┬───────────────────┘    │
           │ Firebase Cloud Messaging          │                 │                         │
           ▼                                   │  ┌──────────────▼───────────────────┐    │
       Google FCM ─────────► push to device    │  │  Celery workers (Playwright,     │    │
                                               │  │  Claude, OpenAI, Gmail API)      │    │
                                               │  └──────────────┬───────────────────┘    │
                                               │                 │                         │
                                               │  ┌──────────────▼───────────────────┐    │
                                               │  │  Postgres · Redis · artifacts/   │    │
                                               │  └──────────────────────────────────┘    │
                                               └──────────────────────────────────────────┘
```

### 6.1 Component responsibilities

**FastAPI service** — HTTP + WebSocket edge. Auth, request validation, enqueues long-running work to Celery, streams run progress via WS topics. Never calls Playwright directly.

**Celery workers** — execute the existing `src/` pipeline: scraping, matching, resume tailoring, Easy Apply, Gmail send, LinkedIn DM. Emit progress events to Redis pub/sub which FastAPI forwards to connected WS clients.

**Postgres** — replaces the current SQLite tracking store. Schema carries jobs, applications, runs, drafts, threads, devices, integrations, audit log. Artifacts (DOCX, PDFs) stay on the filesystem under `artifacts/`, referenced by URL.

**Redis** — Celery broker + pub/sub for live progress streaming + idempotency-key store.

**Firebase Cloud Messaging** — push delivery. Backend keeps per-device FCM tokens; sends notifications on: new ranked-job batch ready, apply-run needs approval, Gmail thread got a reply, application status auto-detected as changed.

**Android client** — offline-tolerant read-cache in Room; state stored as sealed UI states (Loading/Success/Empty/Error) per the guidelines doc. All network I/O through a single Retrofit + OkHttp stack with auth interceptor, retry, and token-rotation handling.

## 7. Feature specification

### 7.1 Authentication & device pairing

- **Initial pairing (one-time):**
  1. User provisions the VPS, sets `BOOTSTRAP_SECRET` via env var, restarts `docker-compose`.
  2. Backend prints a QR code containing `https://<host>/?bs=<secret>` to `docker logs`.
  3. User `ssh`es in, scans the QR with the app camera.
  4. App generates an Ed25519 keypair in **Android Keystore** (non-exportable, requires device unlock), sends public key + bootstrap secret to `POST /auth/pair`, receives a long-lived session token.
  5. Backend invalidates the bootstrap secret after first successful pair; user must mint a new one for additional devices.
- **Multi-device:** Multiple devices can pair using fresh bootstrap secrets. Device list viewable + revocable from any paired device.
- **Session rotation:** Automatic on the first request after token age > 6 days. New token returned in `X-Auth-Next-Token` header.
- **Revocation:** `DELETE /auth/devices/{id}` from another paired device, or direct DB operation.
- **At rest on phone:** Session token stored in EncryptedSharedPreferences. Private key never leaves Keystore.
- **Third-party creds (Gmail, LinkedIn, OpenAI, Anthropic):** server-side only. Gmail uses OAuth2 — phone opens a Chrome Custom Tab; phone never sees the token.

### 7.2 Dashboard (home screen)

Read-only overview. Sections:

- **Today strip** — new jobs since last visit, apps needing follow-up, apps with status changes.
- **Pipeline health** — badge for each integration (Gmail · LinkedIn · OpenAI · Anthropic). Tap to view last error / reconnect.
- **KPI tiles** — applied this week, interviews this month, follow-ups due.
- **Quick actions** — "Run scrape now", "Draft pending follow-ups".

### 7.3 Job list

- Infinite-scroll list, default sorted by match-score descending.
- Card shows: title, company, location, salary (if scraped), match score with color band, source (LinkedIn / Naukri), age, status chip.
- Filter bar: status (new / starred / applied / dismissed), source, score ≥, posted-within.
- Swipe actions: star, dismiss.
- Pull-to-refresh triggers `POST /jobs/refresh`; progress bar in header wired to the resulting WS topic.

### 7.4 Job detail

- Hero: title, company, match score breakdown (description sim / title sim / skill overlap) with visual explanation.
- Tabs: **JD** · **Tailored resume** · **Cover letter** · **Pitch** · **Apply**.
- Each AI artifact has: "Regenerate" button, read-only preview, "Edit" mode persisting changes back via `PATCH /jobs/{id}/resume`.
- Apply tab shows path: Easy Apply (backend-automated) vs. External (deep-link to LinkedIn app / browser).
- Footer actions: Star · Dismiss · Apply · Share.

### 7.5 Apply flow (SP3 — most interactive screen)

**Easy Apply path:**
1. User taps Apply → app calls `POST /jobs/{id}/apply` → receives `run_id`.
2. App opens a **Run Viewer** screen and subscribes to WS topic `run:{run_id}`.
3. Viewer shows a vertical timeline: step name, status (pending / running / waiting_approval / success / failed), timestamp, and an optional screenshot thumbnail from the headless browser.
4. When a step emits `waiting_approval`, viewer surfaces a form with the field labels the bot couldn't fill (e.g., "Years of experience in Kubernetes", "Earliest start date"). User fills and submits → `POST /runs/{run_id}/approve`.
5. Final submission step requires explicit confirmation — "Submit application" button with the prepared payload visible.
6. On success, app transitions to Application detail; on failure, shows last error + screenshot + "Retry" / "Open in browser" options.

**External path:**
- Button opens the canonical job URL via `ACTION_VIEW` with LinkedIn app preferred over browser.
- Return to app → prompt "Did you apply? Mark as submitted?" → creates application record manually.

### 7.6 Application tracker

- List of all applications grouped by status: Submitted · Acknowledged · Interview · Offer · Rejected · Ghosted.
- Card shows: company, role, applied date, days-since-last-activity, next-action chip (e.g., "Follow up in 2 days").
- Detail view: timeline of events (applied / recruiter reply / interview scheduled / offer), draft follow-ups, thread history.
- Status editing via bottom sheet; recruiter contact info (email / LinkedIn URL) editable.

### 7.7 Follow-up composer (SP4 + SP5)

Entry points: application detail → "Follow up" button, or Dashboard → "Draft pending follow-ups".

1. User picks channel: Gmail or LinkedIn DM.
2. App calls `POST /applications/{id}/followup?channel=gmail|linkedin` → backend calls Claude with a template + application context → returns `draft_id`.
3. Draft screen: editable subject (Gmail only) + body + signature. Inline hints on tone ("professional / warm / assertive") rewrite the draft on tap.
4. Send: `POST /drafts/{draft_id}/send`. Backend dispatches via Gmail API (SP4) or Playwright LinkedIn (SP5), appends to `threads` table, returns confirmation.
5. Thread view per application shows full outbound + inbound message history.

**Rate limits (LinkedIn safety):**
- Max 5 LinkedIn DMs per day per device.
- Minimum 45-minute gap between DMs.
- Backend refuses to send if LinkedIn session looks flagged (CAPTCHA seen, login page after token).

### 7.8 Notifications (FCM)

Push types:
- `new_jobs` — "{N} new jobs scored above {threshold}. Top match: {title} at {company}."
- `run_needs_approval` — "Apply flow paused — {field_label} needed."
- `reply_detected` — "{recruiter} replied re: {role}."
- `status_change` — "Gmail suggests {role} moved to {status}."

Deep links: tapping a notification opens the specific job / run / thread. Notification channels per type so user can mute categories independently.

### 7.9 Profile & config

- Edit profile JSON (personas, skills, salary expectations).
- Search queries — add / enable / disable.
- Thresholds — min match score, semi-auto review gate, rate limits.
- Integrations — connect Gmail (OAuth), reconnect LinkedIn (streams headless screenshots during login over WS for 2FA input).

## 8. API surface (v1, authoritative)

All endpoints under `/api/v1/`. Auth: `Authorization: Bearer <session-token>` unless noted. Errors: `{error: {code, message, details}}`.

**Auth**
- `POST /auth/pair` (unauth) — `{bootstrap_secret, device_public_key, device_name}` → `{session_token, device_id}`
- `GET /auth/devices` — list paired devices with last-seen timestamps
- `DELETE /auth/devices/{id}` — revoke
- `POST /auth/rotate` — mint a new session token

**Jobs**
- `GET /jobs?status=&source=&min_score=&cursor=` — paginated, 25/page
- `GET /jobs/{id}` — full detail incl. artifacts + score breakdown
- `POST /jobs/refresh` — enqueue scrape → `{run_id}`
- `POST /jobs/{id}/star`, `DELETE /jobs/{id}/star`
- `POST /jobs/{id}/dismiss`
- `PATCH /jobs/{id}` — user fields: notes, custom tags

**Resume / tailoring**
- `POST /jobs/{id}/tailor` → `{run_id}`
- `GET /jobs/{id}/artifacts` — signed URLs, 15 min HMAC expiry
- `PATCH /jobs/{id}/resume` — persist user edits to tailored text

**Apply**
- `POST /jobs/{id}/apply` — headers `Idempotency-Key` → `{run_id, ws_topic}`
- `POST /runs/{run_id}/approve` — `{field_values: {...}}`
- `POST /runs/{run_id}/cancel`
- `GET /runs/{run_id}` — state snapshot

**Applications**
- `GET /applications?status=&cursor=`
- `GET /applications/{id}`
- `PATCH /applications/{id}` — user-set status, notes
- `POST /applications/{id}/followup?channel=gmail|linkedin` → `{draft_id}`

**Drafts & threads**
- `GET /drafts/{id}` · `PATCH /drafts/{id}` · `POST /drafts/{id}/send`
- `GET /threads/{application_id}`

**Integrations**
- `GET /integrations` — connection status per provider
- `POST /integrations/gmail/oauth` → returns OAuth URL for Chrome Custom Tab
- `POST /integrations/linkedin/login` → `{login_run_id}` — subscribe WS for screenshot stream

**Profile**
- `GET /profile` · `PATCH /profile`
- `GET /config` · `PATCH /config`

**WebSocket — `/ws`**
- Client → server: `{op: "subscribe", topic: "run:{id}"}`, `{op: "unsubscribe", ...}`, `{op: "ping"}`
- Server → client: `{topic, event_type, payload}` where `event_type ∈ {step_started, step_completed, step_failed, waiting_approval, screenshot, log_line, done}`.

**Conventions**
- Pagination: opaque cursor, `?cursor=...&limit=25`.
- Idempotency: `Idempotency-Key` on all `POST` that enqueue runs; replays return the original `run_id`.
- Versioning: `/api/v1/`; breaking changes ship as `/api/v2/`.

## 9. Data model (Postgres)

Core tables (abbreviated):

```
devices              (id, name, public_key, paired_at, last_seen_at, revoked_at)
sessions             (token_hash, device_id, issued_at, rotates_at)
jobs                 (id, source, source_id, title, company, location, salary_band,
                      jd_text, scraped_at, match_score, score_breakdown jsonb,
                      status, starred, dismissed, user_notes)
job_artifacts        (id, job_id, kind {resume|cover|pitch|jd_snapshot},
                      file_path, text, version, generated_at)
applications         (id, job_id, submitted_at, channel, external_ref,
                      current_status, status_history jsonb, recruiter jsonb, notes)
runs                 (id, kind {scrape|tailor|apply|login|send_mail|send_dm},
                      job_id nullable, application_id nullable, status, started_at,
                      finished_at, error_code, error_details jsonb, steps jsonb)
drafts               (id, application_id, channel, subject, body, tone,
                      created_by {ai|user}, edited_at)
threads              (id, application_id, channel, direction {out|in},
                      body, sent_at, external_id)
integrations         (provider, status, credentials_encrypted bytea,
                      last_error, last_check_at)
audit_log            (id, at, actor {device_id|system}, action, target, details jsonb)
fcm_tokens           (id, device_id, token, last_seen_at, platform)
```

- All `credentials_encrypted` encrypted with a VPS-resident KEK (env-var, rotated manually) using authenticated encryption (AES-GCM via `cryptography` lib).
- `audit_log` is append-only; every mutation hitting a third party (send_mail, send_dm, submit_application) must write a row.

## 10. Android module structure

Follows `docs/APP_GUIDELINES.md` (Section 3 — Architecture).

```
app/                 Application class, DI graph (Hilt), nav host
feature/
  auth/              pair device, keystore, session storage
  dashboard/
  jobs/              list + detail + tailoring
  apply/             run viewer, approval forms, screenshot preview
  applications/      tracker + detail
  followup/          drafts + threads
  profile/           settings, integrations
core/
  network/           Retrofit, OkHttp, auth interceptor, rotating tokens
  ws/                OkHttp WebSocket client, topic multiplexer
  data/              Room cache, repositories
  domain/            UseCases, models, error types
  ui/                design tokens, composables (per guidelines §4)
  analytics/         AnalyticsTracker (per guidelines §5)
  notifications/     FCM receiver, channel setup, deep-link router
test/
  unit/              per feature, fakes for repositories
  ui/                Compose critical flows
```

## 11. Non-functional requirements

| Area | Requirement |
|---|---|
| **Performance** | Cold start p50 < 1.5 s · UI 60 fps on Pixel 6 · Job list initial render ≤ 300 ms from cache |
| **Reliability** | Crash-free session ≥ 99.5% · Retries with exponential backoff on network errors · Room cache survives offline |
| **Security** | Only HTTPS/WSS · Certificate pinning for VPS hostname · Keystore-bound keys · No third-party creds on device · Audit log server-side for every send/submit |
| **Accessibility** | TalkBack labels · Dynamic text size support · Minimum 48dp touch targets · Color-independent status indicators |
| **Data** | All network responses cached · Room as read-through cache · ETag support for `/jobs` list |
| **Observability** | Firebase Crashlytics · Analytics events per guidelines §5 · Backend run metrics in Postgres + Prometheus if deployed |
| **Privacy** | No PII in analytics events · No JD text in logs · Opt-out of all analytics available in Profile |

## 12. Rollout plan

| Phase | Contents |
|---|---|
| **0. PRD + mockups** | This document. UI/UX agent produces mockups per §7 screen descriptions. |
| **1. Backend readiness (SP1)** | FastAPI endpoints, Postgres migration, Celery, VPS deploy, Gmail OAuth. Curl-level testable. |
| **2. Android foundation (SP2)** | Pair flow, dashboard, job list/detail, application tracker. Read-only — no apply yet. Internal testing track. |
| **3. Remote apply (SP3)** | Run viewer, WS, approval forms, deep-link fallback. Closed beta (self). |
| **4. Gmail follow-ups (SP4)** | Composer, Claude draft, send, thread view. |
| **5. LinkedIn follow-ups (SP5)** | DM via Playwright with rate limits. Feature-flagged so it can be disabled instantly if LinkedIn flags the account. |

Each phase gates on: crash-free ≥ 99%, all critical acceptance tests pass, user smoke-tests 3 real jobs end-to-end.

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| LinkedIn account restriction from DM automation (SP5) | Hard rate limits, CAPTCHA detection, feature flag kill-switch, prefer Gmail path |
| Playwright selectors break (existing risk) | Ordered fallback selectors already in `config.yaml`; Run Viewer surfaces exact failure + screenshot for diagnosis |
| VPS outage blocks all mobile use | Status page screen in app; last-cached job list remains browsable; FCM for restored-service ping |
| Claude/OpenAI quota exhaustion mid-apply | Pre-flight quota check; degrade gracefully by using last tailored resume instead of regenerating |
| Gmail OAuth token revoked by Google | Integration status surfaced on Dashboard; re-auth via Chrome Custom Tab in one tap |
| User loses phone | Revoke device from another paired device → session invalidated server-side |

## 14. Open items for UI/UX mockup pass

Screens requiring visual design before SP2/SP3 can start (explicit checklist for the UI/UX agent):

1. Pairing flow — QR scan camera screen, connection success, device-already-paired error.
2. Dashboard — KPI tiles layout, today-strip empty/filled states, integration health badges.
3. Job list — card density, match-score visual language (ring / bar / badge), filter sheet.
4. Job detail — tab layout, score-breakdown visualization, resume edit mode.
5. Apply run viewer — timeline component, approval form sheet, screenshot preview, terminal states.
6. Application tracker — group-by-status layout, timeline per application.
7. Follow-up composer — editor with tone toggles, thread view.
8. Profile & integrations — connection states, reconnect flow with LinkedIn screenshot stream.
9. Notifications — in-app notification center (mirror of FCM payloads).
10. Empty, loading, error states for all of the above (per guidelines §4).

## 15. Acceptance criteria (summary)

A release ships when, for a set of 10 fresh LinkedIn job URLs:
- ≥ 9 are scraped, scored, and shown on phone within 3 minutes of "Refresh" tap.
- ≥ 8 can be fully tailored (resume + cover + pitch) on phone without opening a laptop.
- ≥ 7 of the Easy Apply-eligible ones are submitted successfully from phone with ≤ 2 approval prompts each.
- ≥ 9 show up in the tracker within 1 minute of submission.
- User can draft and send a follow-up Gmail in ≤ 60 s from tapping "Follow up".
- Crash-free session rate across the test ≥ 99.5%.

---

_Source of architectural decisions: brainstorming session 2026-04-21. See `docs/APP_GUIDELINES.md` for the Android engineering standards this app must follow._
