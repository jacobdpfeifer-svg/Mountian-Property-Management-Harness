# 08 — Vendor task-import adapter field check (Guesty tasks, Breezeway, Turno)

Audit date: 2026-10-06. Branch `audit/ops-compliance` @ `5f4c496`. The working tree also had an uncommitted change to `src/ops/sources/normalize.py` (adds `as_local`/`as_local_iso` for America/Denver, and `minutes_between` now converts to local). The adapters did not call the new helpers at replay time, so the UTC service-date finding stands until `guesty_tasks.py:96` switches over. Read-only: no live API was called and no credentials were used. Every doc page cited below was loaded on 2026-10-06 (see Sources).

> **Addendum (lead, 2026-10-06, after this file was written):** commit `3c928d7` made
> `minutes_between` convert both sides to local time, and `280330a` made `as_iso_date` return
> the America/Denver date and `as_float` accept `"250.00 USD"`. The Guesty UTC service-date
> misread below is fixed. The Breezeway cost misread is **not** fixed. `_cost` still returns
> the `costs[]` materials line ($10.50) before it reads `rate_paid`, because whether
> `rate_paid` and `costs[]` should be summed needs a real tenant export. Every other finding
> in this file stands.

## Verdict

**Turno is broken against its own published docs.** The code says the Turno docs "could not be read from the public page" (`src/ops/sources/turno.py:4-9`). They can: the Postman collection behind apidocs.turnoverbnb.com is public JSON. Against it, almost every Turno assumption is wrong:
- The partner header is `TBNB-Partner-ID`, not `X-Partner-Id`.
- The date params are `start`/`end` (or `date_range_start`/`date_range_end`), not `start_date`/`end_date`.
- The list envelope is `data.items` with `data.last_page`, not a list under `data`.
- Completion, cost and cleaner are under `assignment.*` (`completed_at`, `charged_amount`, `contractor.id`).
- There is no `status` string. The flag is `completed: 1`.

The documented list response makes `fetch_projects` raise "unexpected Turno payload shape" on page 1. Even a documented project passed straight to `normalize_project` returns `None`, because it has no status and no top-level `completed_at`. So a completed clean is silently dropped.

**Breezeway mostly matches its docs, with one silent misread.** Auth, paths, pagination, ids, times and status all match. The misread is cost. REST tasks have no `total_cost`. `rate_paid` is a string, `"250.00 USD"`, which `as_float` cannot parse. So the adapter reports only the materials line in `costs[]`: **$10.50 for the doc's $250 departure clean.**

**Guesty tasks is half-right, and wrong in the field that matters.**
- **Matches:** auth, paths, the `columns`/`limit`/`skip` grammar and the top-level array.
- **`endTime` misread:** the adapter treats `endTime` as the completion time. Guesty's own webhook examples show `endTime = startTime + plannedDuration` on a **pending** task. So for documented payloads, `actual_minutes` is always the planned duration. `completedAt` appears in no Guesty doc.
- **Timezone:** service dates are taken from the UTC date, so an evening Mountain-time turn lands on the next day.
- **Webhooks:** nothing verifies the Svix signature anywhere in the repo. The webhook import orders events by arrival time. Guesty says to order by `__v`/`updatedAt`. In the replay below, a stale "in progress" redelivery erased a completed task.

**Severity.** Nothing here can push a wrong restriction today. Outcomes feed `turn_cost`/readiness → `ops_aware_stay`, which is `enabled: false` (`config/policies/default.yaml:336-337`), and its min-stay is "never pushed" (`src/ops/pricing_hook.py:11-12`). The readiness gate uses asset events, not these outcomes. Most findings are therefore P2. The cost and date misreads become P1 the day `ops_aware_stay` is turned on.

---

## 1. Guesty tasks — `src/ops/sources/guesty_tasks.py` (+ auth in `src/pms/guesty.py`)

Doc keys used below:
- **[G-AUTH]** https://open-api-docs.guesty.com/docs/authentication
- **[G-LIST]** https://open-api-docs.guesty.com/reference/get_tasks-open-api-tasks. Its embedded OpenAPI 3.0.3 spec has a 200 schema but **no response example**.
- **[G-ONE]** https://open-api-docs.guesty.com/reference/get_tasks-open-api-taskid. This is in the same embedded spec.
- **[G-CREATE]** https://open-api-docs.guesty.com/reference/post_tasks-open-api-create-single-task. Same spec.
- **[G-WH]** https://open-api-docs.guesty.com/docs/webhooks-tasks. Verbatim payload examples.
- **[G-HOOKS]** https://open-api-docs.guesty.com/docs/webhooks

| Field | Code location | Doc status | Doc URL | Note |
|---|---|---|---|---|
| Token URL `https://open-api.guesty.com/oauth2/token` | `src/pms/guesty.py:23` | confirmed-in-docs | [G-AUTH] | cURL example posts to exactly this URL |
| `grant_type=client_credentials`, `scope=open-api`, client_id/secret, form-encoded | `src/pms/guesty.py:150-152` | confirmed-in-docs | [G-AUTH] | `--data-urlencode 'grant_type=client_credentials' ... 'scope=open-api'`, `Content-Type: application/x-www-form-urlencoded` |
| `expires_in` (default 86400) | `src/pms/guesty.py:157` | confirmed-in-docs | [G-AUTH] | "`expires_in`: 86400". Docs advise refreshing **30–60 min** before expiry. Code refreshes 300 s before (`guesty.py:141`). Max 5 tokens / 24 h; the disk cache mitigates this. P3 |
| `Authorization: Bearer <token>` | `src/pms/guesty.py:162-164` | confirmed-in-docs | [G-AUTH], [G-LIST] | `"token_type": "Bearer"`; spec `bearerAuth` |
| Base `https://open-api.guesty.com` + `/v1/...` | `src/pms/guesty.py:24`, `guesty_tasks.py:31` | confirmed-in-docs | [G-LIST] | spec server `https://open-api.guesty.com/v1` + path `/tasks-open-api/tasks` |
| `GET /v1/tasks-open-api/tasks` | `guesty_tasks.py:31,64` | confirmed-in-docs | [G-LIST] | |
| `columns` (required, space-separated) | `guesty_tasks.py:33-37,64` | confirmed-in-docs (param) | [G-LIST] | "Selection of columns, separated by space", `required: true`. The doc's example list is `status taskTitle listing reservation scheduledFor endTime canStartAfter mustFinishBefore assignee id`. Code also requests `_id title listingId reservationId startTime completedAt plannedDuration assigneeId assigneeFullName`, which are not list-schema columns. Whether unknown columns are ignored or rejected is **assumed** |
| `limit`, `skip` | `guesty_tasks.py:55,64,72-74` | confirmed-in-docs | [G-LIST] | "Pagination" / "Indication of number of results to skip" |
| `filters` deliberately not sent | `guesty_tasks.py:58-61` | confirmed-in-docs (optional) | [G-LIST] | Optional param. Without it the adapter pages through **every task in the account's history** at 25 per request and filters client-side. P3 (cost / rate limits) |
| Response = top-level array | `guesty_tasks.py:44-46` | confirmed-in-docs | [G-LIST] | 200 schema `type: array`. The `results`/`data`/`tasks` wrappers (`:48`) are assumed (harmless) |
| `status` ∈ {completed, done, finished}; skip {canceled, cancelled, deleted} | `guesty_tasks.py:38-39,79-81` | **contradicted (shape)** in [G-LIST]; confirmed in [G-ONE]/[G-WH] | [G-LIST], [G-ONE], [G-WH] | The list schema types `status` as an **object** `{children: enum[pending, confirmed, in progress, completed, canceled]}`. By-id and webhooks give a plain string. If the list returns the object shape, `str(dict)` never matches and **every task is silently dropped** (see fixture replay). Enum value `completed` is confirmed. `done`/`finished`/`deleted` are not Guesty values (assumed, harmless) |
| `_id` / `id` | `guesty_tasks.py:82` | confirmed-in-docs | [G-LIST] (`id`), [G-ONE]/[G-WH] (`_id`) | |
| `listingId` (top level) | `guesty_tasks.py:83` | confirmed-in-docs | [G-WH] | `"listingId": "62e17bddae108b003b1f87d7"` in task webhooks |
| `listing.listingId` | `guesty_tasks.py:83` | confirmed-in-docs | [G-LIST] | `listing: {listingId, img, title}` |
| `listing._id`, `listing.id` | `guesty_tasks.py:83` | assumed | — | |
| `apply.listingId` (by-id shape) | not read | **contradicted (not handled)** | [G-ONE] | GET-by-id puts the listing at `apply.listingId`. Not used by the adapter today. Re-fetching by id after a webhook, as [G-HOOKS] recommends, would raise "unknown listing" |
| `listing.title` | `guesty_tasks.py:84` | confirmed-in-docs | [G-LIST] | |
| `listing.nickname` | `guesty_tasks.py:84` | assumed | — | |
| `startTime` (top level) | `guesty_tasks.py:66,87` | confirmed-in-docs | [G-WH], [G-CREATE] | Webhook: `"startTime": "2022-09-04T10:00:00.000Z"` (fixed task) |
| `scheduledFor.startTime` / `.canStartAfter` / `.mustFinishBefore` | `guesty_tasks.py:66-68,87-90` | confirmed-in-docs | [G-LIST] | `scheduledFor: {startTime, canStartAfter, mustFinishBefore}` |
| `timing.startTime` etc. (by-id shape) | not read | **contradicted (not handled)** | [G-ONE] | By-id nests times under `timing` |
| `canStartAfter`, `mustFinishBefore` (top level) | `guesty_tasks.py:66-68,88,90` | confirmed (webhook strings) / **contradicted (shape)** in list | [G-WH], [G-LIST] | The list schema types top-level `canStartAfter`/`mustFinishBefore`/`endTime` as objects `{date: string}`. `as_datetime(dict)` returns None |
| `completedAt` | `guesty_tasks.py:68,89` (also `COLUMNS`) | **assumed — absent from every Guesty page opened** | [G-LIST], [G-ONE], [G-WH] | Not in the list schema, the by-id schema, or any webhook example |
| `endTime` used as completion time | `guesty_tasks.py:68,89,112` | **contradicted** | [G-WH] vs [G-LIST] | [G-LIST] describes it as "The date and time the task was completed". But [G-WH] shows a **pending** task with `startTime 10:00`, `plannedDuration 3`, `endTime 13:00`. After an update it shows `startTime 08:00` → `endTime 11:00`. `endTime` is the *planned* end. Result: `actual_minutes == plannedDuration*60` and `completed_at` is planned, not actual. P2 |
| `plannedDuration` (hours → ×60) | `guesty_tasks.py:99,110` | confirmed-in-docs | [G-ONE], [G-CREATE], [G-WH] | "The amount of time budgeted for the task (hours)". **Not** in the list schema, so it may never come back from the list endpoint |
| Lateness = completed − mustFinishBefore | `guesty_tasks.py:91-95` | derived; inputs assumed | [G-WH] | Fixed tasks carry `mustFinishBefore: null`. Flexible tasks carry no `endTime`, and `completedAt` is undocumented. With doc-shaped payloads `late_ready_minutes` is **never** populated |
| `type` / `taskTitle` / `title` → service type | `guesty_tasks.py:105` | confirmed-in-docs | [G-LIST] (`type`, `taskTitle`), [G-ONE]/[G-WH] (`title`) | Create enum: cleaning, maintenance, inspection, mid-stay, runner, sanitation, check-in, issue, inventory, administration. `check-in` → "maintenance" via the fallback (P3) |
| `assigneeId` / `assignee.assigneeId` | `guesty_tasks.py:115-116` | confirmed-in-docs | [G-WH]/[G-ONE] (`assigneeId`), [G-LIST] (`assignee.assigneeId`) | |
| `assigneeFullName` (column) | `guesty_tasks.py:36` | confirmed-in-docs (webhook only) | [G-WH] | `"assigneeFullName": "Belle Perry"`. Requested but not read. A person's name should not be pulled in at all; drop it from `COLUMNS` |
| `reservationId`, `reservation._id`, `reservation.id` | `guesty_tasks.py:117-118` | `reservationId` confirmed ([G-WH], [G-CREATE]); `reservation.*` assumed | [G-WH] | [G-LIST] types `reservation` as an untyped object |
| Timezone | `guesty_tasks.py:96`, `normalize.py:84` | not handled | [G-WH] | Payloads are UTC (`...000Z`) and carry `"timezone"` (deleted example: `"Europe/Athens"`). `service_date = as_iso_date(UTC)`, so a 18:30 MST Dec 23 turn becomes **2026-12-24** (replayed below). Readiness joins outcomes to turns **by service_date** (`src/ops/economics.py:160`) |
| Cost: "Guesty tasks carry no cost" | `guesty_tasks.py:8,113` | **contradicted** | [G-ONE], [G-CREATE] | By-id returns `pendingExpenses[]`/`postedExpenses[]` (name, amount, shareSplit), and create accepts `expenses[]` with `amount`. Available but unused. P3 |
| `POST /v1/tasks-open-api/create-single-task`, `title` required | `guesty_tasks.py:32,134-138,150-156` | confirmed-in-docs | [G-CREATE] | schema `required: ["title"]` |
| Task webhook events `task.created/updated/deleted`, envelope `{task, by, event}` | `src/ops/sources/webhooks.py:26,32` | confirmed-in-docs | [G-WH] | |

## 2. Breezeway — `src/ops/sources/breezeway.py`

Doc keys used below:
- **[B-AUTH]** https://developer.breezeway.io/docs/authentication
- **[B-TOK]** https://developer.breezeway.io/reference/obtain-tokens
- **[B-PROP]** https://developer.breezeway.io/reference/list-properties
- **[B-TASKS]** https://developer.breezeway.io/reference/list-tasks
- **[B-TASK]** https://developer.breezeway.io/reference/retrieve-task
- **[B-WH]** https://developer.breezeway.io/docs/task-webhooks
- **[B-SUB]** https://developer.breezeway.io/docs/subscribing-to-webhooks
- **[B-CL]** https://developer.breezeway.io/changelog/task-api-updates

| Field | Code location | Doc status | Doc URL | Note |
|---|---|---|---|---|
| `POST https://api.breezeway.io/public/auth/v1/` | `breezeway.py:40,81` | confirmed-in-docs | [B-AUTH], [B-TOK] | |
| Body `{client_id, client_secret}` JSON | `breezeway.py:81-83` | confirmed-in-docs | [B-AUTH] | "POST call ... using an `application/json` content type" |
| `access_token` in response | `breezeway.py:86-88` | confirmed-in-docs | [B-TOK] | `{"access_token": "xyz", "refresh_token": "xyZ"}` |
| 24 h lifetime (cached 23 h), 1 req/min limit | `breezeway.py:5-6,90` | confirmed-in-docs | [B-AUTH] | "Access tokens have a 24-hour lifetime". Rate limit 1 req/min with HTTP 429. `refresh_token` (30-day, `/refresh`) is ignored. That is acceptable |
| `Authorization: JWT <token>` | `breezeway.py:104` | confirmed-in-docs | [B-AUTH] | "*must include* the scheme `JWT` as a prefix" |
| `Accept: application/json` | `breezeway.py:105` | confirmed-in-docs | [B-AUTH] | |
| Base `https://api.breezeway.io/public/inventory/v1` | `breezeway.py:41` | confirmed-in-docs | [B-PROP], [B-TASKS] | |
| `GET /property` | `breezeway.py:129` | confirmed-in-docs | [B-PROP] | |
| `page`, `limit=100` | `breezeway.py:113` | confirmed-in-docs | [B-PROP], [B-TASKS] | both default 100 / 1 |
| `results`, `total_pages` envelope | `breezeway.py:117-123` | confirmed-in-docs | [B-PROP], [B-TASKS] | `{"limit", "page", "results", "total_pages", "total_results"}` |
| property `id`, `reference_property_id`, `name`, `address1` | `breezeway.py:130-133` | confirmed-in-docs | [B-PROP] | `reference_property_id` is null in the example; name matching via aliases is the realistic path |
| `GET /task/` | `breezeway.py:140` | confirmed-in-docs | [B-TASKS] | |
| `home_id` query | `breezeway.py:140` | confirmed-in-docs | [B-TASKS] | "One of either home_id or reference_property_id is required" |
| `scheduled_date=YYYY-MM-DD,YYYY-MM-DD` | `breezeway.py:138,140` | confirmed-in-docs | [B-TASKS] | "Date range (YYYY-MM-DD) separated by comma". A task finished in-window but scheduled outside it is missed; `finished_at` is also a documented range filter. P3 |
| `type_department` query | docstring `breezeway.py:10` only | confirmed-in-docs, not sent | [B-TASKS] | enum maintenance/housekeeping/inspection/safety |
| task `id`, `home_id`, `reference_property_id`, `name` | `breezeway.py:168-172,179` | confirmed-in-docs | [B-TASKS], [B-TASK] | |
| `scheduled_date`, `scheduled_time` | `breezeway.py:188,192-194` | confirmed-in-docs | [B-TASKS] | `scheduled_time: null` in the example. The adapter then writes a fake `scheduled_start` of `T00:00:00`. P3 |
| `started_at`, `finished_at` | `breezeway.py:164,173,176,195` | confirmed-in-docs | [B-TASKS] | Naive timestamps (`"2024-09-25T20:45:00"`). The timezone is undocumented (assumed company-local) |
| `total_time` | `breezeway.py:174` | confirmed-in-docs | [B-TASKS] | `"1:46:27"` (h:m:s). `as_minutes` returns 106.45, which is correct |
| `type_task_status.stage` / `.code` | `breezeway.py:161` | confirmed-in-docs | [B-TASKS] | `{"code": "finished", "name": "Finished", "stage": "finished"}` |
| DONE_STAGES `completed, closed, approved, done` | `breezeway.py:43` | assumed | [B-TASKS] | Only `finished` appears. "closed"/"approved" exist as actions (Close task, Approve task) but their stage strings are not shown |
| `status` fallback | `breezeway.py:161` | **contradicted (shape)** | [B-WH] | Exists only in the webhook schema, as an **object** `TypeTaskStatus{code,id,name}` |
| `type_department` | `breezeway.py:177` | confirmed-in-docs | [B-TASKS] | `"housekeeping"` |
| `department` fallback | `breezeway.py:177` | **contradicted (shape)** | [B-WH] | Webhook-only, and an object `{code,id,name}`, not a string |
| `total_cost` | `breezeway.py:144` | **contradicted for REST** (absent from [B-TASKS]/[B-TASK]); exists in [B-WH] as number | [B-TASKS], [B-WH] | |
| `costs[].cost` | `breezeway.py:147-155` | confirmed-in-docs | [B-TASKS] | Example: one `material` cost of 10.5 ("Shower curtain"). These are **add-on charges**, not the clean's price. The adapter takes this sum **before** `rate_paid`, so it reports 10.5 for a $250 clean. **Silent misread, P2 (P1 once ops_aware_stay / owner receipts use observed cost)** |
| `rate_paid` | `breezeway.py:156` | **contradicted (type)** | [B-TASKS], [B-TASK] vs [B-CL] | REST returns the string `"250.00 USD"`. `as_float` strips only `,$\s`, so `"250.00USD"` fails and returns None. [B-CL] documents it as a float on create/update; [B-WH] as a number |
| `supplies[].total_price` | not read | confirmed-in-docs, unused | [B-TASKS] | More billable cost the adapter ignores |
| `assignments[0].assignee_id` | `breezeway.py:182-185` | confirmed-in-docs | [B-TASKS] | `7172`. Fallbacks `id`/`name` exist. `name` is a person's name; prefer not to store it |
| `finished_by` | not read | confirmed-in-docs | [B-TASKS] | Who actually finished. Better than `assignments[0]` |
| QA/inspection result | `breezeway.py:178` (dept only) | n/a | [B-TASKS] | No pass/fail field in the task list. "Retrieve task requirements" (llms index) holds responses; not used |

## 3. Turno — `src/ops/sources/turno.py`

Doc key **[T]**: https://apidocs.turnoverbnb.com/ ("Turno External API v2", Postman documenter, publishDate 2025-11-20). The HTML page renders client-side, so WebFetch saw only the title. The content was read from the collection JSON the page loads: https://apidocs.turnoverbnb.com/api/collections/18953218/UVXomuDo?environment=18953218-1a07a54a-8576-4d96-9401-ef06a0cfcecc&segregateAuth=true&versionTag=latest, plus https://apidocs.turnoverbnb.com/view/metadata/UVXomuDo for the environment.

| Field | Code location | Doc status | Doc URL | Note |
|---|---|---|---|---|
| `Authorization: Bearer <TURNO_API_TOKEN>` | `turno.py:48,66` | confirmed-in-docs | [T] | collection `auth.type = bearer`. Tokens come from an OAuth **authorization_code** flow (`POST /v2/oauth/token`, "Both access and refresh tokens have a 1 year lifespan"). There is no refresh path in code |
| Base `https://api.turnoverbnb.com/v2` | `turno.py:37,51` | **assumed** | [T] | Docs show only `https://sandbox.turnoverbnb.com/v2` (environment var `domain`). No production host is documented |
| Partner header name `X-Partner-Id` | `turno.py:53,67-68` | **contradicted** | [T] | Every request in the collection sends **`TBNB-Partner-ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`**. The header is only sent if `TURNO_PARTNER_ID` is set (`:67`). The docs show it on every call |
| `Accept: application/json` | `turno.py:66` | confirmed-in-docs | [T] | |
| `GET /projects` | `turno.py:78` | confirmed-in-docs | [T] | "List projects" |
| `start_date`, `end_date` | `turno.py:78` | **contradicted** | [T] | Documented: `start=2022-01-31&end=2022-12-31` and `date_range_start`/`date_range_end` (also `time_type`, `time_value`, `properties`, `cleaners`, `limit`, `page`, ...). Unknown params are probably ignored → **no date filter**, and `fetch_projects` has no client-side window filter |
| `page` | `turno.py:78` | confirmed-in-docs | [T] | `limit` is documented but not sent |
| Envelope: list, or list under `data`/`results`/`projects` | `turno.py:79-85` | **contradicted** | [T] | Documented: `{"data": {"items": [...], "current_page", "last_page", "per_page", "total"}}`. `data` is a dict, so the code raises `ValueError("unexpected Turno payload shape")` |
| `meta.last_page` / `last_page` / `total_pages` | `turno.py:86` | **contradicted** | [T] | Documented at `data.last_page` |
| `status` / `state` | `turno.py:93` | **contradicted (absent)** | [T] | No status string. Documented flags: `completed: 1`, `paid: 1`, `published: 1`, `assignment.payment_status: "succeeded"` |
| `completed_at` (and `finished_at`, `end_time`, `checkout_time`) | `turno.py:96` | **contradicted** | [T] | Documented at **`assignment.completed_at`** (`"2022-04-04T20:16:24.000000Z"`). Top-level `end` is the scheduled window end |
| Property: `property.external_id`, `property.external_reference`, `property_external_id` | `turno.py:100` | assumed (absent) | [T] | Documented: `property_id` (Turno integer), `integration_id`, `booking.property_id` |
| `property.name`, `property_name`, `property.nickname` | `turno.py:101` | **contradicted** | [T] | Documented as top-level **`property_alias`** (`"Leonard's apartment"`) |
| `property_address` | `turno.py:102` | confirmed-in-docs | [T] | `"property_address": "2311 N Los Robles Ave, ..."` (the one property field that matches) |
| `id` | `turno.py:104` | confirmed-in-docs | [T] | `"id": 1` |
| `started_at` | `turno.py:107` | **contradicted (location)** | [T] | at `assignment.started_at` |
| `duration`, `duration_minutes`, `time_spent` | `turno.py:108` | assumed (absent) | [T] | Derivable from `assignment.started_at` → `completed_at` |
| `cleaner.id`, `cleaner_id`, `cleaner.name`, `cleaner_name` | `turno.py:111` | **contradicted** | [T] | Documented at `assignment.contractor.id` (plus first/last name) |
| `date`, `project_date`, `scheduled_date` | `turno.py:114` | **contradicted (absent)** | [T] | The service date is `start` (`"2022-06-04T10:00:00-04:00"`), with `time_zone` alongside |
| `service.name`, `service_name`, `type` | `turno.py:118` | assumed (absent) | [T] | Types come from `GET /v2/projects/available-types`. Not in the project example |
| `scheduled_start`, `start_date` | `turno.py:119` | **contradicted** | [T] | Documented as `start` |
| `price`, `total`, `amount`, `total_price`, `payment.amount` | `turno.py:122` | **contradicted** | [T] | Documented at **`assignment.charged_amount`** (`63`) |
| `qa_pass=None` hard-coded | `turno.py:123` | n/a | [T] | Docs expose `quality_controlled: true`, unused |

## 4. Fixture replay

Fixtures are in `tests/ops/fixtures/vendor_docs/`. Each file has `_provenance` (doc URL, retrieved 2026-10-06, `shape`, how the values were obtained) plus `payload`.

| Fixture | Shape | Fed through | Result |
|---|---|---|---|
| `guesty_webhook_task_created_fixed.json` | from-docs (verbatim) | `normalize_task(payload["task"])` | `None` (status pending). Correct |
| `guesty_webhook_task_created_flexible.json` | from-docs (verbatim) | same | `None`. Correct |
| `guesty_webhook_task_updated.json` | from-docs (verbatim) | same | `None`. Correct |
| `guesty_webhook_task_deleted.json` | from-docs (verbatim) | same | `None`. Also excluded by the SQL in `webhooks.py:26` |
| `guesty_webhook_task_completed_fixed_derived.json` | from-docs, `status`→completed | same | **Misread.** `actual_minutes=180.0`, `completed_at=2022-09-04T13:00Z` come straight from the planned `endTime` (start 10:00 + 3 h). `late_ready_minutes` is empty because `mustFinishBefore` is null |
| (inline) same task, `startTime 2026-12-24T01:30Z`, `timezone America/Denver` | derived | same | **Misread.** `service_date=2026-12-24`; the local turn is **Dec 23 18:30 MST** |
| `guesty_tasks_list_schema_literal.json` | from-docs-schema (no example on page) | `fetch_tasks` → `normalize_task` | `fetch_tasks` keeps 1/1 via `scheduledFor.startTime`. **`normalize_task` returns `None`**: `status` is `{children: "completed"}`, so the task is silently dropped |
| `guesty_tasks_list_schema_plain.json` | assumed (scalar strings) | same | Fixed task: accepted; `actual_minutes=180` from `endTime` (the same misread); `required_minutes` missing because `plannedDuration` is not in the list schema. Flexible task: accepted with no `completed_at`, no actual, no lateness |
| `guesty_task_get_by_id_schema.json` | from-docs-schema | `normalize_task` | **Raises** `ValueError: unknown listing None`. The listing is at `apply.listingId`. This fails closed. Matters only if someone adds the re-fetch the docs recommend |
| `breezeway_property_list.json` | from-docs (verbatim, JSON repaired) | `homes()` | `{328858: overlook_ridge}` via alias on `name`. Correct |
| `breezeway_task_list.json` | from-docs (verbatim, JSON repaired) | `fetch_tasks` → `normalize_task` | Accepted: `actual_minutes=106.45` (from "1:46:27", correct), `assignee_ref="7172"`, `service_type=turnover`. **`cost=10.5`, which is wrong**: the doc's clean is `rate_paid "250.00 USD"` plus supplies. `as_float("250.00 USD")` returns `None`. `scheduled_start=2024-09-25T00:00:00` is fabricated from a null `scheduled_time` |
| `breezeway_webhook_task.json` | from-docs-schema | `normalize_task(payload["task"])` | **Raises** `ValueError: unknown home None` (`home.id`, not `home_id`). Fails closed. Breezeway webhooks are not wired in today |
| `turno_projects_list.json` | from-docs (verbatim) | `fetch_projects` | **Raises** `ValueError: unexpected Turno payload shape` (`data` is a dict). Params sent: `{start_date, end_date, page}`. Two of the three are wrong names |
| same, `data.items[0]` | from-docs (verbatim) | `normalize_project` | **`None` — silently dropped.** No `status`, no top-level `completed_at` (it is `assignment.completed_at`) |
| `turno_project_get.json` | from-docs (verbatim) | `normalize_project(payload["data"])` | **`None` — silently dropped** for the same reason |
| (inline) list item + `status: "completed"` | derived | `normalize_project` | Resolves via `property_address` only. `service_date=""` (rejected later by `record_outcomes`, `src/ops/db.py:80`); cost, minutes and cleaner all `None` |
| Guesty ordering: completed (`__v`=1) then stale "in progress" (`__v`=0) delivered 5 s later | from-docs payload, derived values | `record_delivery` ×2 → `import_task_webhooks` | **accepted=0, rejected=0, outcomes=0.** The completed task is lost silently. Redelivering the same `event_id` is a no-op (`duplicate=True`). The same body under a new id is stored again (`duplicate=False`). `record_delivery` extracts `listing_id=None` for task payloads (the id is under `task.listingId`) |

Script used (run from the worktree root as `PYTHONPATH=. .venv/bin/python replay.py`; no network):

```python
"""Feed doc-derived fixtures through the adapters' parse/normalize functions. No network."""
import json, copy, dataclasses, pathlib, os, tempfile
from datetime import date
from src.ops.sources import PropertyResolver
from src.ops.sources import guesty_tasks as gt, breezeway as bw, turno as tn

FX = pathlib.Path("tests/ops/fixtures/vendor_docs")
load = lambda n: json.loads((FX / n).read_text())["payload"]
# Map the docs' example ids/names onto Mont Luxe ids so property resolution is not the failure cause.
R = PropertyResolver(None, {"properties": {"summit_haus": {}, "overlook_ridge": {}, "cloud_9": {}},
    "aliases": {"summit_haus": ["62e17bddae108b003b1f87d7"],
                "overlook_ridge": ["279892", "Example property"],
                "cloud_9": ["Leonard's apartment", "2311 N Los Robles Ave, Pasadena, CA 91104, EUA", "1"]}})

def show(label, fn):
    try:
        o = fn()
        out = None if o is None else {k: v for k, v in dataclasses.asdict(o).items() if v is not None}
        print(f"{label}: {json.dumps(out, default=str)}")
    except Exception as e:
        print(f"{label}: RAISES {type(e).__name__}: {e}")

for n in ["guesty_webhook_task_created_fixed.json", "guesty_webhook_task_created_flexible.json",
          "guesty_webhook_task_updated.json", "guesty_webhook_task_deleted.json",
          "guesty_webhook_task_completed_fixed_derived.json"]:
    show(n, lambda: gt.normalize_task(load(n)["task"], R))
t = copy.deepcopy(load("guesty_webhook_task_completed_fixed_derived.json")["task"])
t.update(startTime="2026-12-24T01:30:00.000Z", endTime="2026-12-24T04:30:00.000Z", timezone="America/Denver")
show("derived: completed fixed task, 18:30 MST Dec 23 local", lambda: gt.normalize_task(t, R))

for n in ["guesty_tasks_list_schema_literal.json", "guesty_tasks_list_schema_plain.json"]:
    body = load(n); calls = []
    def get(path, **p):
        calls.append((path, p)); return body if p["skip"] == 0 else []
    kept = list(gt.fetch_tasks(get, date(2022, 9, 1), date(2022, 9, 30)))
    print(f"{n}: fetch_tasks kept {len(kept)}/{len(body)}; params={calls[0][1]}")
    for task in body:
        show(f"  normalize {task['id']}", lambda: gt.normalize_task(task, R))
show("guesty_task_get_by_id_schema.json", lambda: gt.normalize_task(load("guesty_task_get_by_id_schema.json"), R))

props, tasks = load("breezeway_property_list.json"), load("breezeway_task_list.json")
bget = lambda path, **p: props if path == "/property" else tasks
print("homes():", bw.homes(bget, R))
hm_all = {279892: "overlook_ridge"}  # doc's property example id 328858 != task example home_id 279892
for task in bw.fetch_tasks(bget, sorted(hm_all), date(2024, 9, 1), date(2024, 9, 30)):
    show(f"task {task['id']}", lambda: bw.normalize_task(task, hm_all, R))
print("as_float('250.00 USD') ->", bw.as_float("250.00 USD"))
show("breezeway_webhook_task.json", lambda: bw.normalize_task(load("breezeway_webhook_task.json")["task"], hm_all, R))

lst, seen = load("turno_projects_list.json"), []
def tget(path, **p):
    seen.append((path, p)); return lst
try:
    print("fetch_projects:", list(tn.fetch_projects(tget, date(2022, 6, 1), date(2022, 6, 30))))
except Exception as e:
    print(f"fetch_projects RAISES {type(e).__name__}: {e}; params sent={seen[0][1]}")
for it in lst["data"]["items"]:
    show("normalize_project(list item)", lambda: tn.normalize_project(it, R))
show("normalize_project(get data)", lambda: tn.normalize_project(load("turno_project_get.json")["data"], R))
item = copy.deepcopy(lst["data"]["items"][0]); item["status"] = "completed"
show("derived: list item + status='completed'", lambda: tn.normalize_project(item, R))

# Guesty webhook ordering through the real import path on a temp DB
os.environ["MONTLUXE_MEMORY_ROOT"] = tempfile.mkdtemp()
from src.db import connect, init_db
from src.pms.webhooks import record_delivery
import src.ops.sources.webhooks as wmod
wmod.PropertyResolver = lambda conn: R
db = pathlib.Path(tempfile.mkdtemp()) / "o.db"; init_db(db)
done = load("guesty_webhook_task_completed_fixed_derived.json")
stale = copy.deepcopy(done); stale["task"]["status"] = "in progress"; stale["task"]["__v"] = 0; done["task"]["__v"] = 1
with connect(db) as conn:
    record_delivery(conn, event_id="msg_done", event_type="task.updated", payload=done, received_at="2026-10-06 10:00:00")
    record_delivery(conn, event_id="msg_stale", event_type="task.updated", payload=stale, received_at="2026-10-06 10:00:05")
    r = wmod.import_task_webhooks(conn)
    n = conn.execute("SELECT COUNT(*) FROM turnover_outcomes").fetchone()[0]
    print(f"accepted={r.accepted} rejected={r.rejected} outcomes={n}")
    print("same id again -> duplicate:", record_delivery(conn, event_id="msg_done", event_type="task.updated", payload=done).duplicate)
    t2 = record_delivery(conn, event_id="msg_other", event_type="task.updated", payload=done)
    print("same body new id -> duplicate:", t2.duplicate, "listing_id:", t2.listing_id)
```

## 5. Webhooks: what the code does vs what vendors say

**Guesty (the only vendor whose webhooks are wired in).**

| Concern | Vendor docs | Code | Verdict |
|---|---|---|---|
| Signature | [G-HOOKS] "Each subscribed endpoint receives its own unique signing key". Get it via `GET /webhooks-v2/secret?url=...` ([G-SECRET]) and verify per Svix: headers `svix-id`, `svix-timestamp`, `svix-signature`; HMAC-SHA256 over `"{svix_id}.{svix_timestamp}.{raw_body}"` with the base64 key after `whsec_`; constant-time compare ([SVIX]). Guesty lists validation as "(optional)" in its handling steps | **No verification anywhere.** There is no HTTP receiver in the repo. `record_delivery` (`src/pms/webhooks.py:46-79`) accepts any dict, and a repo-wide grep for `svix`/`hmac`/`signature` finds nothing relevant | **Gap.** Whatever receiver is added must verify before `record_delivery`. P2 now (no public endpoint exists); P1 the moment an endpoint is exposed, because unsigned task bodies flow straight into outcomes |
| Replay protection | Svix: compare `svix-timestamp` against your clock within a tolerance | None. `event_id` dedup only (`webhooks.py:69-77`, `INSERT OR IGNORE`) | Gap (P2, same gating) |
| Duplicates | "Deduplicate on the `svix-id` and the Guesty `meta.eventId`" | Dedups on whatever `event_id` the caller passes (docstring: "Guesty's event id or Svix id", `webhooks.py:56`). Task payloads carry no `meta.eventId` (see [G-WH] examples: `{task, by, event}` only), so `svix-id` is the only usable key | OK if the future receiver passes `svix-id`. Re-sent bodies under a new id are stored again but collapse per task id in `import_task_webhooks` |
| Ordering | "you may receive events out of order ... **Order according to the `__v` or `lastUpdatedAt`** ... Rely on the fresh data you ingest" | `ORDER BY received_at` and "later deliveries win" (`src/ops/sources/webhooks.py:27,35`) | **Contradicted.** Replay above: a stale in-progress redelivery after the completed event leaves **no outcome**. Guesty also states that "recovery processes may also emit historical events". Sort by `task.__v` (present in every example), then `updatedAt`. P2 |
| Re-fetch | "Fetch: Invoke Guesty's Open API to retrieve the complete details" | `__init__.py:10` claims "bounded task re-read", but `webhooks.py:30-39` normalizes the webhook body directly and never re-reads | **Docstring is false**; payload is trusted as-is. P3 |
| Deletes | `task.deleted` carries the full task | Filtered out (`webhooks.py:26`). An outcome already recorded for a later-deleted task is never removed | P3 |
| Listing target | Task payload has `task.listingId` | `record_delivery` looks only at top-level `listingId`/`listing` (`src/pms/webhooks.py:66`), so it extracts `listing_id=None` for task events | P3 (only affects the calendar refresh target) |
| Retries | Immediately, 5 s, 5 min, 30 min, 2 h, 5 h, 10 h, 10 h. Ack 2xx within 15 s. Endpoint auto-disabled after 5 days of failures | n/a (no receiver) | Design input for the receiver |

**Breezeway.** Task webhooks exist: events `task-created`, `task-updated`, `task-started`, `task-cost-updated`, and others. The envelope is `{event_type, task, last_updated}`, and "Each event will include a last updated timestamp allowing the receiver to ignore events that have the same updated timestamp". Events coalesce ("we send a fully updated task object ... not 6 different events"). Responses must arrive within 10 s. The subscription is deactivated after 3 days and ≥10 consecutive failures ([B-WH], [B-SUB]). **No signing or secret is documented** on any Breezeway page opened, so a receiver can only protect itself with a secret URL or an IP allowlist plus a re-fetch. The code does not consume Breezeway webhooks. The webhook task schema (`home.id`, `status{}`, `department{}`) would not normalize through `breezeway.normalize_task` (replay: raises).

**Turno.** `GET /v2/webhooks/available-types` lists a single type, `{"id": 1, "name": "Project Completed"}`. Subscribing is `POST /v2/webhooks {callback_url, type_id}`. The collection documents **no delivery payload and no signing**. The code does not consume Turno webhooks.

## Sources

All retrieved 2026-10-06. "curl" means the raw page or markdown (`.md`) or embedded spec was downloaded and parsed locally. "WebFetch" means it was opened with the WebFetch tool.

| URL | Method | Result |
|---|---|---|
| https://open-api-docs.guesty.com/reference/get_tasks-open-api-tasks | WebFetch + curl (HTML, full embedded OpenAPI 3.0.3 spec incl. `/tasks-open-api/{taskId}` and `create-single-task`) | loaded |
| https://open-api-docs.guesty.com/reference/get_tasks-open-api-tasks.md | curl | loaded |
| https://open-api-docs.guesty.com/llms.txt | curl | loaded (index) |
| https://open-api-docs.guesty.com/docs/webhooks-tasks (+ `.md`) | WebFetch + curl | loaded (updatedAt 2026-09-30) |
| https://open-api-docs.guesty.com/docs/webhooks.md | curl | loaded (updatedAt 2026-09-30) |
| https://open-api-docs.guesty.com/reference/svixsecretapicontroller_getsecret.md ([G-SECRET]) | curl | loaded |
| https://open-api-docs.guesty.com/docs/authentication.md | curl | loaded (updatedAt 2026-08-30) |
| https://docs.svix.com/receiving/verifying-payloads/how-manual ([SVIX]) | WebFetch | loaded |
| https://developer.breezeway.io/reference/get_task | WebFetch | **failed (404)**, wrong slug |
| https://developer.breezeway.io/llms.txt | curl | loaded (index) |
| https://developer.breezeway.io/reference/obtain-tokens.md | curl | loaded |
| https://developer.breezeway.io/docs/authentication.md | curl | loaded |
| https://developer.breezeway.io/reference/list-properties.md | curl | loaded (example JSON is malformed as published) |
| https://developer.breezeway.io/reference/list-tasks (+ `.md`) | WebFetch + curl | loaded (example JSON is malformed as published) |
| https://developer.breezeway.io/reference/retrieve-task.md | curl | loaded |
| https://developer.breezeway.io/docs/subscribing-to-webhooks.md | curl | loaded |
| https://developer.breezeway.io/docs/task-webhooks.md | curl | loaded (updatedAt 2026-08-25) |
| https://developer.breezeway.io/changelog/task-api-updates.md | curl | loaded |
| https://developer.breezeway.io/changelog/task-webhook-update.md | curl | loaded |
| https://apidocs.turnoverbnb.com/ | WebFetch + curl | loaded, but the HTML has only a title (client-rendered) |
| https://apidocs.turnoverbnb.com/api/collections/18953218/UVXomuDo?environment=18953218-1a07a54a-8576-4d96-9401-ef06a0cfcecc&segregateAuth=true&versionTag=latest | curl | loaded (146 KB Postman collection; publishDate 2025-11-20) |
| https://apidocs.turnoverbnb.com/view/metadata/UVXomuDo | curl | loaded (Sandbox environment: `domain=https://sandbox.turnoverbnb.com`, `partner-id`) |
| https://apidocs.turnoverbnb.com/llms.txt | curl | failed (404) |
| https://apidocs.turno.com/ | curl | failed (404) |
| https://turno.com/api, https://help.turno.com/ | curl | failed (403) |
| https://developer.turno.com/ | curl | failed (no response) |
