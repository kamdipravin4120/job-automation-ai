# SP3b: AI Job-fit Depth — Design Spec

**Date:** 2026-05-15
**Branch:** prod/w3-console
**Follows:** SP3a (Android Integration + Pipeline Observability)

---

## Goal

Surface AI-generated cover letters, tailored resume text, and interview prep briefings on the Android companion app. Users can view existing artifacts or trigger on-demand generation per job/application.

## Architecture

**Backend:** Three new API endpoints (no new DB migrations — `JobArtifact` and `Application.briefing_json` already exist). `ApplicationOut` schema extended to expose `briefing_json`. FCM payload enriched with `kind` + `reference_id` so Android knows which job to refresh after tailor completes.

**Android:** Two new detail screens (`JobDetailScreen`, `ApplicationDetailScreen`) reached by tapping cards in the existing `JobsScreen` and `TrackerScreen`. Artifacts fetched on-demand, not cached in Room. Tailor generation is async (FCM notifies completion); brief generation is a synchronous ~8s API call.

**Generation mode:** Hybrid — show existing artifacts if available, show "Generate" button if not yet generated.

---

## Artifacts in Scope

| Artifact | Source | Trigger |
|---|---|---|
| Cover letter | `JobArtifact` (kind=`cover_letter`) | `POST /jobs/{id}/tailor` → Celery |
| Tailored resume text | `JobArtifact` (kind=`resume_text`) | `POST /jobs/{id}/tailor` → Celery (same task) |
| Interview prep brief | `Application.briefing_json` | `POST /applications/{id}/brief` → sync API call |

Recruiter pitch and DOCX download are out of scope.

---

## Backend Changes

### 1. `ApplicationOut` schema (`src/api/schemas/applications.py`)

Add field parsed from the `briefing_json` text column:

```python
import json
from pydantic import field_validator

class BriefingItem(BaseModel):
    question: str
    rationale: str
    star_points: list[str]

class ApplicationOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    channel: str
    current_status: str
    submitted_at: datetime
    external_ref: str | None
    briefing_json: list[BriefingItem] | None = None

    model_config = {"from_attributes": True}

    @field_validator("briefing_json", mode="before")
    @classmethod
    def parse_briefing(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except ValueError:
                return None
        return v
```

### 2. `ArtifactsOut` schema (`src/api/schemas/jobs.py`)

```python
class ArtifactsOut(BaseModel):
    cover_letter: str | None = None
    resume_text: str | None = None
    generated_at: datetime | None = None
```

### 3. New routes on jobs router (`src/api/routes/jobs.py`)

```
GET  /jobs/{job_id}/artifacts   → ArtifactsOut
POST /jobs/{job_id}/tailor      → {"queued": true}
```

`GET /jobs/{job_id}/artifacts`: queries `JobArtifact` for the two latest rows of kinds `cover_letter` and `resume_text` for this `job_id`. Returns nulls if no rows exist.

`POST /jobs/{job_id}/tailor`: calls `run_tailor.delay(job_id=str(job_id))`. Returns `{"queued": true}`. `@pipeline_task` handles idempotency at the task level.

### 4. New route on applications router (`src/api/routes/applications.py`)

```
POST /applications/{app_id}/brief  → ApplicationOut
```

If `application.briefing_json` is already set: parse and return immediately (no LLM call).

If null: load `CandidateProfile` from settings (resume path), load `Job` via `application.job_id`, call `ResumeService().generate_interview_briefing(profile, job)`, serialize result to JSON string, store in `application.briefing_json`, commit, return updated `ApplicationOut`.

If resume path not configured: raise `HTTP 422` with `{"detail": "Resume not configured"}`.

### 5. FCM payload enrichment (`src/tasks/base.py` + `src/notifications/push.py`)

`_push_on_complete` currently sends a generic event. Extend to pass task metadata:

- For `run_tailor` tasks: include `{"kind": "tailor", "reference_id": "<job_id>"}` in FCM data payload.
- For all other tasks: include `{"kind": "<task_kind>", "reference_id": null}`.

`push.py` `send_event()` already accepts arbitrary kwargs — pass `data: dict` through to FCM message.

---

## Android Changes

### New DTOs (`JobAiService.kt`)

```kotlin
@JsonClass(generateAdapter = true)
data class ArtifactsDto(
    @Json(name = "cover_letter") val coverLetter: String?,
    @Json(name = "resume_text") val resumeText: String?,
    @Json(name = "generated_at") val generatedAt: String?,
)

@JsonClass(generateAdapter = true)
data class TailorQueuedDto(val queued: Boolean)

@JsonClass(generateAdapter = true)
data class BriefingItemDto(
    val question: String,
    val rationale: String,
    @Json(name = "star_points") val starPoints: List<String>,
)
```

`ApplicationDto` gets: `@Json(name = "briefing_json") val briefingJson: List<BriefingItemDto>? = null`

New service methods:

```kotlin
@GET("jobs/{id}/artifacts")
suspend fun getArtifacts(@Path("id") id: String): ArtifactsDto

@POST("jobs/{id}/tailor")
suspend fun triggerTailor(@Path("id") id: String): TailorQueuedDto

@GET("applications/{id}")
suspend fun getApplication(@Path("id") id: String): ApplicationDto

@POST("applications/{id}/brief")
suspend fun generateBrief(@Path("id") id: String): ApplicationDto
```

### FCM Event Bus (`firebase/FcmEventBus.kt`)

```kotlin
data class FcmEvent(val kind: String, val referenceId: String?)

object FcmEventBus {
    private val _events = MutableSharedFlow<FcmEvent>(extraBufferCapacity = 8)
    val events: SharedFlow<FcmEvent> = _events.asSharedFlow()
    fun emit(event: FcmEvent) { _events.tryEmit(event) }
}
```

`JobAiFirebaseService.onMessageReceived()` reads `remoteMessage.data["kind"]` + `remoteMessage.data["reference_id"]` and calls `FcmEventBus.emit(FcmEvent(kind, referenceId))` before showing the notification.

### Job Detail (`jobs/JobDetailScreen.kt` + `jobs/JobDetailViewModel.kt`)

**ViewModel state:**

```kotlin
data class JobDetailUiState(
    val jobId: String,
    val coverLetter: String? = null,
    val resumeText: String? = null,
    val isGenerating: Boolean = false,
    val isLoading: Boolean = true,
    val error: String? = null,
)
```

On init: calls `GET /jobs/{id}/artifacts`. If `coverLetter == null && resumeText == null`: shows "Generate" button.

On `triggerGeneration()`: calls `POST /jobs/{id}/tailor`, sets `isGenerating = true`. Collects `FcmEventBus.events` — when `event.kind == "tailor" && event.referenceId == jobId`: re-fetches artifacts, clears `isGenerating`.

**Screen layout:**
- Header: job title + company (passed as nav args)
- "Cover Letter" section: text in scrollable card or "Generate" button
- "Resume" section: text in scrollable card (same generate state as cover letter — both come from one tailor run)
- Circular progress indicator when `isGenerating`

### Application Detail (`tracker/ApplicationDetailScreen.kt` + `tracker/ApplicationDetailViewModel.kt`)

**ViewModel state:**

```kotlin
data class AppDetailUiState(
    val appId: String,
    val briefingItems: List<BriefingItemDto> = emptyList(),
    val isGenerating: Boolean = false,
    val isLoading: Boolean = true,
    val error: String? = null,
)
```

On init: calls `GET /applications/{id}` — if `briefingJson != null`, populate `briefingItems`.

On `generateBrief()`: calls `POST /applications/{id}/brief`, sets `isGenerating = true`. On response: populate `briefingItems`, clear `isGenerating`. (Sync call, ~8s.)

**Screen layout:**
- Header: job title + status badge (passed as nav args)
- If `briefingItems` empty: "Generate Interview Brief" button + explanation text
- If populated: `LazyColumn` of `BriefingCard`s — question (bold), rationale (muted), collapsible STAR points list
- Circular progress indicator when `isGenerating`

### Navigation (`AppNavigation.kt`)

New sealed `Screen` entries:

```kotlin
object JobDetail : Screen("job_detail/{jobId}/{title}/{company}") {
    fun route(jobId: String, title: String, company: String) =
        "job_detail/$jobId/${Uri.encode(title)}/${Uri.encode(company)}"
}
object AppDetail : Screen("app_detail/{appId}/{title}/{status}") {
    fun route(appId: String, title: String, status: String) =
        "app_detail/$appId/${Uri.encode(title)}/${Uri.encode(status)}"
}
```

`JobsScreen` call updated: `onJobClick = { job -> navController.navigate(Screen.JobDetail.route(job.id, job.title, job.company)) }`

`TrackerScreen` call updated: `onAppClick = { app -> navController.navigate(Screen.AppDetail.route(app.id, app.jobTitle, app.currentStatus)) }`

### Existing screens modified

`JobsScreen.kt` — job card `Modifier.clickable { onJobClick(job) }`. Receives `onJobClick: (JobDto) -> Unit` parameter.

`TrackerScreen.kt` — app card `Modifier.clickable { onAppClick(app) }`. Receives `onAppClick: (ApplicationDto) -> Unit` parameter.

Note: `ApplicationDto` doesn't currently carry job title — either pass it from the ViewModel (which has the associated job) or add a `jobTitle` denormalization to `ApplicationOut`. Simpler: pass `appId + currentStatus` only; `ApplicationDetailViewModel` fetches the full application (which has `job_id`) and loads the job title separately via `GET /jobs/{job_id}`.

---

## File Map

| Action | File |
|---|---|
| Modify | `src/api/schemas/applications.py` |
| Modify | `src/api/schemas/jobs.py` |
| Modify | `src/api/routes/jobs.py` |
| Modify | `src/api/routes/applications.py` |
| Modify | `src/tasks/base.py` |
| Modify | `src/notifications/push.py` |
| Create | `tests/api/test_artifacts_sp3b.py` |
| Modify | `android/.../core/api/JobAiService.kt` |
| Create | `android/.../firebase/FcmEventBus.kt` |
| Modify | `android/.../firebase/JobAiFirebaseService.kt` |
| Create | `android/.../jobs/JobDetailScreen.kt` |
| Create | `android/.../jobs/JobDetailViewModel.kt` |
| Create | `android/.../tracker/ApplicationDetailScreen.kt` |
| Create | `android/.../tracker/ApplicationDetailViewModel.kt` |
| Modify | `android/.../navigation/AppNavigation.kt` |
| Modify | `android/.../jobs/JobsScreen.kt` |
| Modify | `android/.../tracker/TrackerScreen.kt` |

---

## Testing

### Backend (`tests/api/test_artifacts_sp3b.py`)

- `test_get_artifacts_empty` — job with no `JobArtifact` rows → all null
- `test_get_artifacts_returns_latest` — two `cover_letter` rows (v1, v2) → returns v2 text
- `test_trigger_tailor_queues_task` — mock Celery → `{"queued": true}`
- `test_application_out_has_briefing_json` — seed `Application` with `briefing_json` → `GET /applications` returns parsed list
- `test_generate_brief_stores_and_returns` — mock `ResumeService` → `briefing_json` persisted + returned
- `test_generate_brief_idempotent` — `briefing_json` already set → returns existing, no LLM call

### Android

Code review only (no Android SDK on dev machine). Spec + quality subagent review after each task.

---

## Out of Scope

- Recruiter pitch surface
- DOCX download
- Resume upload / profile management
- Caching artifacts in Room DB
- SP3c (Recruiter Intelligence)
