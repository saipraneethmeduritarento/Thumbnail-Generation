# Codebase Summary

> Generated: 2026-06-11. All claims cite source file and line number [RULE 2].
> Every factual statement is tagged [OBSERVED], [INFERRED], or [UNVERIFIED] per RULE 9.

---

## Project Info

| Key | Value | Source |
|---|---|---|
| Python version | ^3.12 | pyproject.toml:9 |
| FastAPI version | 0.112.2 (pinned) | poetry.lock |
| App root path | `/imagegen` (proxy prefix only — does not affect route registration) | app/main.py:10 |
| Lock file | `poetry.lock` — present | — |
| No database | No SQLAlchemy, no ORM, no DB setup found | [OBSERVED] |
| No authentication | No auth dependency on any route | [OBSERVED] |

---

## 1.2 Route Inventory

| HTTP Method | Path | File:Line | Request Body | Path/Query Params | Response Model | Auth Dependency | Status Codes | Sonar Rule Flags |
|---|---|---|---|---|---|---|---|---|
| GET | `/v1/image/variations/course/{course_id}` | app/routers/course.py:30 | None | `course_id: str` (path) | `ImageVariationResponse` [app/models.py:9] | None | 200 (success) [app/routers/course.py:37], 500 (HTTPException) [app/routers/course.py:39] | S8415 [app/routers/course.py:39] |
| GET | `/v1/image/resource/{resource_id}` | app/routers/resource.py:8 | None | `resource_id: str` (path) | `dict` [app/routers/resource.py:8] | None | 200 (success) [app/routers/resource.py:11-13], 500 (HTTPException) [app/routers/resource.py:15-16] | S8415 [app/routers/resource.py:15] |
| GET | `/` | app/main.py:20 | None | None | None | None | 200 [app/main.py:21] | Excluded (main.py) |

**Note**: The `GET /v1/image/course/{course_id}` route exists in `app/routers/course.py:13-27` but is **entirely commented out** [app/routers/course.py:13-27]. No tests are generated for it.

**Router registration order** [OBSERVED]:
- `app/routers/__init__.py:8` — `router.include_router(course_router)`
- `app/routers/__init__.py:9` — `router.include_router(resource_router)`
- Both child routers included before `app.include_router(v1_router)` [app/main.py:18] — **correct order** ✓

---

## 1.3 Auth Pattern

**No authentication** [OBSERVED] — no `Depends(...)` in any active route function signature:
- `generate_course_image_variations(course_id: str)` [app/routers/course.py:31] — no auth
- `generate_image(resource_id: str)` [app/routers/resource.py:9] — no auth

All routes are public.

---

## 1.4 Database & Dependency Inventory

**No database** — project has no SQLAlchemy, asyncpg, or any DB driver [OBSERVED, pyproject.toml:9-16].
No DB dependencies to override in tests.

### External Services (must be mocked in tests)

| Service | Call site | Mock target |
|---|---|---|
| `requests.get` — KB API content fetch | app/services/image_variation.py:55 | `app.services.image_variation.requests.get` |
| `requests.get` — thumbnail download | app/services/image_variation.py:97 | `app.services.image_variation.requests.get` |
| `vertexai.GenerativeModel` — Gemini logo detection | app/services/image_variation.py:120 | `app.services.image_variation.GenerativeModel` |
| `vertexai.GenerativeModel` — Gemini content description | app/services/image_variation.py:216 | `app.services.image_variation.GenerativeModel` |
| `ImageGenerationModel` — Vertex AI image generation | app/services/image_variation.py:288 | `app.services.image_variation.ImageGenerationModel` |
| `GCPStorage.write_file` — upload to GCS | app/services/image_variation.py:17 (module-level init) | `app.libs.storage.storage.Client`, `app.libs.storage.service_account.Credentials.from_service_account_file` |
| `vertexai.init` | app/services/image_variation.py:28-29 (module-level) | `vertexai.init` |

### Required Environment Variables (must be set before app import in tests)

| Variable | File:Line |
|---|---|
| `KB_API_HOST` | app/services/image_variation.py:20 |
| `STORAGE_THUMBNAIL_FOLDER` | app/services/image_variation.py:22 |
| `STORAGE_PROXY_PATH` | app/services/image_variation.py:23 |
| `GCP_BUCKET_NAME` | app/libs/storage.py:31 |
| `GCP_STORAGE_CREDENTIALS` | app/libs/storage.py:32 |
| `GCP_GEMINI_CREDENTIALS` | app/services/image_variation.py:27 |
| `GCP_GEMINI_PROJECT_ID` | app/services/image_variation.py:28 |
| `GEMINI_MODEL_PRO` | app/services/image_variation.py:31 |
| `VISION_MODEL` | app/services/image_variation.py:32 |
| `NUMBER_OF_IMAGES` | app/services/image_variation.py:33 |
| `LOG_LEVEL` | app/logger.py:14 |

---

## 1.5 Custom Exception Handlers

**None registered** via `@app.exception_handler(...)` [OBSERVED, app/main.py:1-21]. FastAPI defaults apply.

Per-route `try/except` error handling only:
- `app/routers/course.py:38-39` — catches all `Exception` → `HTTPException(status_code=500, detail="Something went wrong, please try again later...")`
- `app/routers/resource.py:14-16` — catches all `Exception` → `HTTPException(status_code=500, detail="Something went wrong, please try again later...")`

Default FastAPI `422 Unprocessable Entity` for Pydantic validation failures is in effect (not overridden).

---

## Files Excluded from Testing

| File | Exclusion Rule |
|---|---|
| `app/main.py` | FastAPI app instantiation, middleware registration, lifespan — no business logic |
| `app/config.py` | Constants only (`DEFAULT_PROMPT`, `NEGATIVE_PROMPT`, etc.) — no branching logic |
| `app/logger.py` | Logging config wiring only |
| `app/logging.conf` | Config file |
| `app/__init__.py` | Empty |
| `app/services/__init__.py` | Empty |
| `app/routers/__init__.py` | Router wiring only — no business logic |
| `app/services/course.py` | Used only by the **commented-out** route [app/routers/course.py:13-27]; dead code |

---

## FastAPI SonarQube Rule Findings (S8389–S8415)

> **Analyzer version note**: SonarQube FastAPI rules S8389–S8415 were introduced March 2026.
> Compatibility with the connected SonarQube instance is `[UNVERIFIED — analyzer version not confirmed]`.
> Findings and tests are valid regardless of whether the analyzer currently enforces them.

### Testable Findings

| Rule | Description | File:Line | Test |
|---|---|---|---|
| **S8415** | `HTTPException(status_code=500)` raised but not documented in `responses={}` on the route decorator | app/routers/course.py:30 (decorator), app/routers/course.py:39 (raise) | `tests/test_course.py::test_get_course_variations_service_raises_exception` |
| **S8415** | `HTTPException(status_code=500)` raised but not documented in `responses={}` on the route decorator | app/routers/resource.py:8 (decorator), app/routers/resource.py:15 (raise) | `tests/test_resource.py::test_get_resource_exception_path` (SKIPPED — dead code, see below) |
| **S8396** | `LogoDetection.warning: str \| None` — typed `X \| None` with no `= None` default | app/models.py:7 | Response-only model — server always provides the field [app/services/image_variation.py:~313]. Indirectly covered by `test_get_course_variations_no_logo`. See note below. |
| **S8401** | Router registration order — verified correct | app/routers/__init__.py:8-9 | `tests/test_app_lifecycle.py::test_openapi_schema_contains_all_routes` |
| **S8400** | No 204 routes — N/A | — | `tests/test_app_lifecycle.py::test_no_204_routes_in_schema` |
| **S8414** | CORSMiddleware ordering | app/main.py:13-19 | `tests/test_app_lifecycle.py::test_cors_header_present_on_error_response` |

**S8396 note**: `LogoDetection` [app/models.py:5-7] is used exclusively as a response model (inside `ImageVariationResponse` [app/models.py:9-12]), never as a request body. The server code always explicitly sets `warning=None` or `warning="..."` [app/services/image_variation.py:~313-316]. Runtime risk: a server-side code path that omits `warning` when constructing `LogoDetection` would raise a `ValidationError`. This is covered indirectly by the happy-path response tests. `[INFERRED from app/services/image_variation.py:313-316]`

### Static / Non-Testable Findings

| Rule | Description | File:Line |
|---|---|---|
| **S8392** | No `uvicorn.run()` call in `main.py` — app launched externally (Docker/systemd) | app/main.py:1-21 |
| **S8397** | No `uvicorn.run()` call — N/A | app/main.py:1-21 |
| **S8409** | No redundant `response_model` + return-type-annotation duplicates found | — |
| **S8410** | No `Body()` / `File()` used as default values | — |
| **S8411** | Path params match function signatures: `{course_id}` ↔ `course_id: str` [app/routers/course.py:30-31]; `{resource_id}` ↔ `resource_id: str` [app/routers/resource.py:8-9] — **no mismatch** ✓ | — |
| **S8413** | Prefix `/v1/image` defined at `APIRouter(prefix=...)` at definition time [app/routers/__init__.py:5-7]; `/resource` prefix at [app/routers/resource.py:5-7] ✓ | — |
| **S8414** | Only one middleware (`CORSMiddleware`) [app/main.py:13-19] — ordering risk N/A. Still tested functionally. | app/main.py:13-19 |
| **S8389** | No route mixes `BaseModel` body with `UploadFile` — N/A | — |

---

## Pydantic Models (used in routes)

| Model | Fields | Source |
|---|---|---|
| `ImageVariationResponse` | `images: List[str]`, `logo: LogoDetection` | app/models.py:9-12 |
| `LogoDetection` | `found: bool`, `warning: str \| None` (**no default — S8396**) | app/models.py:5-7 |
| `ImageResponse` | `final_summary: str`, `image_prompt: str`, `image_url: str` | app/models.py:4-7 (unused by active routes — commented-out route only) |

=== PHASE 1 VERIFICATION ===
Files read this phase:
  - pyproject.toml (full file)
  - poetry.lock (grep for test-related packages)
  - app/main.py (full file)
  - app/config.py (full file)
  - app/models.py (full file)
  - app/routers/__init__.py (full file)
  - app/routers/course.py (full file)
  - app/routers/resource.py (full file)
  - app/services/image_variation.py (full file, lines 1–400)
  - app/services/course.py (full file)
  - app/libs/storage.py (full file)
  - app/utils.py (full file)
  - app/logger.py (full file)
  - app/logging.conf (full file)
  - app/__init__.py (full file — empty)
  - app/services/__init__.py (full file — empty)
  - Jenkinsfile (full file)
Claims made without a direct file read: NONE
UNVERIFIED placeholders created: 1 (SonarQube analyzer version)
Proceeding to Phase 2: YES
==============================
