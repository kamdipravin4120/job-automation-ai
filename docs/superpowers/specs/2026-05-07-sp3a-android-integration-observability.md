# SP3a Design Spec: Android Integration + Pipeline Observability

**Date:** 2026-05-07
**Branch:** prod/w3-console → new branch `feat/sp3a`
**Depends on:** SP2 (Android foundation), W4b (Gmail OAuth), W4c (FCM push)

---

## Goals

1. Wire the Android companion app to the W4c FCM push backend — devices receive real-time pipeline notifications
2. Replace the Settings stub with a functional screen (server info, Gmail OAuth, unpair)
3. Surface `jobs_found` per pipeline run (currently hardcoded 0 on Android and missing from `RunOut`)
4. Add DLQ management from mobile — operators can retry/dismiss failed runs without opening the web console

---

## Sub-sprint decomposition

| Sub-sprint | Scope |
|---|---|
| **SP3a** (this spec) | FCM receive + Settings screen + jobs_found + DLQ mobile |
| SP3b | AI job-fit depth (cover letter, resume tailoring, interview brief) |
| SP3c | Recruiter intelligence (Gmail thread parsing, follow-up suggestions) |

---

## Architecture Overview

Two parallel work streams:

**Backend** — minimal additions to existing models/schemas; no new routers needed.

**Android** — four self-contained features: `firebase/`, `settings/`, `RunsScreen` enrichment, `dlq/`.

All Android features follow the established MVVM + Clean Architecture pattern from SP2:
`Repository (Room + Retrofit) → ViewModel (StateFlow) → Screen (Compose)`

---

## Backend Changes

### 1. `jobs_found` on Run

**Problem:** `Run` model has no `jobs_found` column. Android `RunEntity.jobsFound` is always 0.

**Solution:**
- Add `jobs_found: Mapped[int] = mapped_column(Integer, default=0)` to `src/data/models/run.py`
- New Alembic migration: `add_jobs_found_to_runs`
- Add `jobs_found: int` to `RunOut` schema in `src/api/schemas/runs.py`
- In the scraper task (wherever jobs are bulk-inserted), call `RunsRepository.set_jobs_found(run_id, count)` after upsert

**`RunsRepository` addition:**
```python
async def set_jobs_found(self, run_id: UUID, count: int) -> None:
    await self._session.execute(
        update(Run).where(Run.id == run_id).values(jobs_found=count)
    )
```

### 2. Expose `steps` and `error_details` in RunOut

`Run` model already stores `steps: list` (JSONB) and `error_details: dict | None` (JSONB). Neither is exposed in `RunOut`. Add both:

```python
class RunOut(BaseModel):
    ...
    jobs_found: int
    steps: list
    error_details: dict | None
```

No migration needed — columns exist.

### 3. Fix FCM token loading in PushService

`PushService` currently stores FCM tokens in-memory (`self._fcm_tokens: list[str]`). On restart, tokens are lost. Fix: `send_fcm_all` must load tokens from the `fcm_tokens` DB table at send time.

**Change in `src/notifications/push.py`:**
- Remove `self._fcm_tokens` in-memory list
- `send_fcm_all(event)` accepts an optional `tokens: list[str]` parameter
- Caller (`base.py` `_push_on_complete`) fetches tokens from `FcmTokensRepository` and passes them in

**`FcmTokensRepository`** already exists at `src/data/repositories/fcm_tokens.py` — just needs to be wired into `_push_on_complete`.

### 4. No backend changes needed for

- DLQ endpoints — `GET /dlq`, `POST /dlq/{run_id}/retry`, `POST /dlq/{run_id}/dismiss` — already implemented
- Gmail status — `GET /gmail/status` — already implemented
- FCM register/unregister — `POST /notifications/fcm/register`, `DELETE /notifications/fcm/{token}` — already implemented

---

## Android Changes

### 1. FCM Integration (`firebase/`)

**Dependencies to add in `app/build.gradle.kts`:**
```
implementation(libs.firebase.messaging.ktx)
```
Add `google-services` plugin. `google-services.json` must be placed at `android/app/` by the operator (documented below).

**New files:**
- `firebase/JobAiFirebaseService.kt` — extends `FirebaseMessagingService`
  - `onNewToken(token)` → calls `api.registerFcmToken(FcmRegisterRequest(token))` via a background coroutine (ApplicationScope)
  - `onMessageReceived(message)` → posts a local notification via `NotificationManager`; payload `data["screen"]` routes deep link (`jobs`, `runs`, `dlq`)
- `firebase/FcmModule.kt` — Hilt `@Module` providing `ApplicationScope` (a `CoroutineScope` with `SupervisorJob + Dispatchers.IO`)

**`AndroidManifest.xml` additions:**
```xml
<service android:name=".firebase.JobAiFirebaseService"
    android:exported="false">
    <intent-filter>
        <action android:name="com.google.firebase.MESSAGING_EVENT"/>
    </intent-filter>
</service>
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
```

**`AuthRepository` change:** After successful `pair()`, call `FirebaseMessaging.getInstance().token.await()` and register with backend.

**`libs.versions.toml` additions:**
```toml
firebase-bom = "33.1.0"
firebase-messaging-ktx = { group = "com.google.firebase", name = "firebase-messaging-ktx" }
```

### 2. Settings Screen (`settings/`)

Replaces the `Text("Settings coming in SP3")` stub in `AppNavigation`.

**New files:**
- `settings/SettingsRepository.kt` — wraps `api.gmailStatus()`, `api.deleteDevice(deviceId)` (`DELETE /devices/{device_id}`); reads `sessionStore`
- `settings/SettingsViewModel.kt` — `SettingsUiState(serverUrl, deviceId, gmailStatus, isUnpairing)`; `unpair()` calls `AuthRepository.unpair()` then emits navigation event
- `settings/SettingsScreen.kt` — composable with sections:
  - **Device** — server URL (read-only), device ID (first 16 chars, FiraCode)
  - **Gmail** — status chip (Connected / Not connected); "Connect Gmail" button opens `verification_url` in browser via `Intent.ACTION_VIEW`, then polls `GET /gmail/oauth/poll` every 3s for up to 5 min
  - **Account** — red "Unpair Device" button with confirmation dialog

**`AppNavigation` change:** Replace `Text("Settings coming in SP3")` with `SettingsScreen()`. Add `LaunchedEffect` for unpair navigation event → navigate to `Screen.Welcome` with full back-stack pop.

**`GmailOAuthPoller`** — small helper in `settings/` that polls the oauth/poll endpoint on a coroutine and emits `authorized`/`timeout`. Not a ViewModel — injected into `SettingsViewModel`.

### 3. RunsScreen Enrichment

**`RunsRepository` changes:**
- `sync()` maps `dto.jobsFound` (now present in `RunOut`) into `RunEntity.jobsFound`
- Add `getRunDetail(id): RunDto` calling `GET /runs/{run_id}` — returns `steps` + `error_details`

**`RunEntity` change:** `jobsFound` column already exists (added in SP2 as placeholder 0) — no schema change.

**`RunsViewModel` change:** Add `loadDetail(runId)` that fetches and caches detail into a `_selectedRun: MutableStateFlow<RunDto?>`.

**`RunsScreen` change:**
- `RunRow` gains a "N jobs" `SurfaceChip` (using `ScoreHigh` color) when `jobsFound > 0`
- Tapping a `RunRow` expands an inline detail panel showing `steps` list and `error_details` if present (no new screen — accordion pattern within `LazyColumn`)

### 4. DLQ Screen (`dlq/`)

Accessible via long-press on the RunsScreen FAB → navigates to `Screen.Dlq`. A DLQ badge (red dot) appears on the Runs bottom-tab icon when any DLQ items exist.

**Room:**
- `DlqEntity(@Entity tableName="dlq_items")` — `id: String, runId: String, kind: String, status: String, errorCode: String?, createdAt: Long, syncedAt: Long`
- `DlqDao` — `observeAll(): Flow<List<DlqEntity>>`, `upsertAll()`, `delete(id)`

**`DlqRepository`:**
- `dlqFlow: Flow<List<DlqItem>>` from Room
- `sync()` — `GET /dlq` → upsert to Room
- `retry(runId)` — `POST /dlq/{run_id}/retry`, then `sync()`
- `dismiss(runId)` — `POST /dlq/{run_id}/dismiss`, then delete from Room

**`DlqViewModel`:** `DlqUiState(items, isRefreshing)`, `retry()`, `dismiss()`

**`DlqScreen`:**
- `LazyColumn` of `DlqCard` — shows `kind`, `errorCode`, relative time
- Each card has "Retry" and "Dismiss" buttons
- Empty state: "No failed runs"

**`AppNavigation` change:** Add `Screen.Dlq` route, composable wired to `DlqScreen()`.

**`AppDatabase` change:** Add `DlqEntity` to `@Database(entities = [...])` and bump `version`.

---

## Data Flow

```
Pipeline stage completes
  → base.py _push_on_complete
  → FcmTokensRepository.get_all_tokens()
  → PushService.send_fcm_all(event, tokens)
  → FCM → Android JobAiFirebaseService.onMessageReceived
  → Local notification + optional screen route
```

```
User pairs device
  → AuthRepository.pair()
  → FirebaseMessaging.getToken()
  → api.registerFcmToken(token)
  → Backend stores in fcm_tokens table
```

```
User opens Settings → Unpair
  → SettingsViewModel.unpair()
  → api.unregisterFcmToken(token)
  → api.deleteDevice(deviceId)
  → AuthRepository.unpair() → SessionStore.clear() + KeystoreHelper.clearKeyPair()
  → Navigate to WelcomeScreen
```

---

## Error Handling

- FCM token registration failure on pair: silent retry on next app launch via `FirebaseMessaging.getInstance().token` check in `MainActivity.onCreate`
- Gmail OAuth poll timeout (5 min): surface "Timed out — try again" in SettingsScreen
- DLQ retry/dismiss failure: show `Snackbar` with error, keep item in list
- `jobs_found` DB migration: backward-compatible (nullable default 0), no data loss

---

## `google-services.json` setup

Operators must:
1. Create a Firebase project at console.firebase.google.com
2. Add Android app with package `com.jobai.companion`
3. Download `google-services.json` → place at `android/app/google-services.json`
4. Set `FCM_PROJECT_ID` and `FCM_SERVICE_ACCOUNT_JSON` env vars on the backend

Document in `android/README.md`.

---

## File Map

**Backend — modified:**
- `src/data/models/run.py` — add `jobs_found`
- `src/api/schemas/runs.py` — add `jobs_found`, `steps`, `error_details` to `RunOut`
- `src/notifications/push.py` — fix FCM token loading
- `src/tasks/base.py` — pass tokens from DB to `send_fcm_all`
- `src/data/migrations/versions/XXXX_add_jobs_found_to_runs.py` — new migration

**Backend — new:**
- `src/data/repositories/runs.py` — add `set_jobs_found()`

**Android — new:**
- `firebase/JobAiFirebaseService.kt`
- `firebase/FcmModule.kt`
- `settings/SettingsRepository.kt`
- `settings/SettingsViewModel.kt`
- `settings/SettingsScreen.kt`
- `settings/GmailOAuthPoller.kt`
- `dlq/DlqRepository.kt`
- `dlq/DlqViewModel.kt`
- `dlq/DlqScreen.kt`

**Android — modified:**
- `core/db/AppDatabase.kt` — add `DlqEntity`, bump version
- `core/api/JobAiService.kt` — add DLQ endpoints, `gmailStatus`, `unregisterFcmToken`
- `auth/AuthRepository.kt` — register FCM token after pair
- `navigation/AppNavigation.kt` — add `Screen.Dlq`, replace Settings stub, unpair nav
- `runs/RunsRepository.kt` — map `jobsFound`, add `getRunDetail()`
- `runs/RunsViewModel.kt` — add `loadDetail()`
- `runs/RunsScreen.kt` — jobs chip, accordion detail, DLQ badge on tab
- `android/app/build.gradle.kts` — firebase-messaging-ktx dependency
- `android/app/src/main/AndroidManifest.xml` — FCM service declaration
- `android/libs.versions.toml` — firebase-bom + messaging versions

---

## Out of Scope for SP3a

- SP3b: Cover letter / resume tailoring / interview brief (AI features)
- SP3c: Recruiter intelligence / Gmail thread parsing
- `email_status` surfaced in TrackerScreen (SP3c)
- `jobTitle` enrichment beyond jobId placeholder (SP3b, when Application→Job join is done)
- Settings screen dark mode / theme toggle
