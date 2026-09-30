# PipeSight Development Flow And Resume State Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate the full `codex resume 019f5a0e-ffe2-71c2-bd46-7846c5a1414b` project context into one development-flow ledger that future work can continue from without losing decisions, progress, constraints, or verification evidence.

**Architecture:** Treat PipeSight as a RuoYi Vue3 + FastAPI full-stack application with two product surfaces: the admin/management side and the separate user portal. Keep the verified current file state separate from historical session notes when they diverge.

**Tech Stack:** Vue 3, Vite, Element Plus, Pinia, Vue Router, FastAPI, SQLAlchemy, Pydantic, MySQL/PostgreSQL, Redis, Node test runner, pytest, uv/pip.

---

## 1. Resume Source Of Truth

Resume id:

```text
019f5a0e-ffe2-71c2-bd46-7846c5a1414b
```

Raw local session log:

```text
C:\Users\admin\.codex\sessions\2026\07\12\rollout-2026-07-12T22-59-20-019f5a0e-ffe2-71c2-bd46-7846c5a1414b.jsonl
```

Related browser-console attachment from the session:

```text
C:\Users\admin\.codex\attachments\9e056de4-8ca3-4c26-938d-f164076c2d77\pasted-text.txt
```

Workspace root:

```text
D:\A_CODEBASE\pipeSight
```

Important current workspace facts:

- The root currently has `.codegraph/`, so CodeGraph must be used before normal code search/read when understanding or editing code.
- The root is currently not a Git repository, so `git status`, commits, and worktrees are unavailable unless Git is initialized later by explicit decision.
- The current frontend directory is a real Vue/Vite source project.
- The current backend directory is a FastAPI/RuoYi backend source project.
- Historical notes said `frontend/legacy-static` preserved old static assets, but the current disk state does not contain `frontend/dayReport-web` or `frontend/legacy-static`. Treat that as an unresolved history/current-state discrepancy.

## 2. Original Request And Scope

The user asked to:

- Organize `D:\A_CODEBASE\pipeSight\frontend` into a suitable frontend project.
- Find a RuoYi full-stack Python version online.
- Build out a full-stack framework.
- Integrate existing visual pages and functions into Vue 3.
- Connect them to RuoYi login, permission, and menu systems.
- Rename/adapt the product into a "管网项目".

The selected base framework was:

```text
insistence/RuoYi-Vue3-FastAPI
```

Clarification recorded in the session:

- This is a community RuoYi Python/FastAPI version, not an official RuoYi Python backend.
- Frontend derives from RuoYi-Vue3.
- Backend replaces Java Spring Boot with FastAPI.
- It keeps users, roles, menus, departments, dictionaries, logs, dynamic routing, permissions, and code generation.
- License: MIT.

## 3. Business Interpretation From Project Docs

The project should not be treated as a generic GIS, pipeline patrol, or asset ledger system.

The documents under `docs/` point to:

```text
国家管网科技情报与科研辅助平台
```

Core business modules extracted from the earlier document review:

- Data collection: papers, news, WeChat public-account articles, scheduling, cleaning, deduplication.
- Data processing: structured parsing, entity extraction.
- Data analysis: pipeline-business relevance judgment and automatic tagging.
- Retrieval and presentation: news, public-account articles, papers, details, unified search, filtering.
- Intelligent generation: daily reports, weekly reports, long-form hot-event reports.
- Knowledge base and QA: document upload/indexing, RAG-style QA, research assistance.
- Technology route and research-demand reports: route reports, demand reports, mind maps, route diagrams, Word/PDF export.
- Requirement parsing: keyword systems, source matching, data-gap analysis.
- Human-in-the-loop editing: paragraph rewrite/polish/delete/reorder, consistency check, version management.
- RuoYi platform capability: users, roles, menus, data permissions, audit logs.

Historical acceptance indicators from the docs:

- At least 20 valid items per technology direction per cycle.
- Deduplication false-positive rate below 5%.
- L1 classification accuracy at least 85%.
- Manual audit amount for auto-generated reports no more than 30% of total text.
- First phase should form the minimal loop: collection -> processing -> search/display -> RBAC.

Infrastructure mentioned in docs but not required for the current MVP:

- PostgreSQL
- Elasticsearch
- MinIO
- Milvus
- Redis
- Kafka
- Kubernetes high availability

The agreed practical MVP approach was to keep the RuoYi/FastAPI monolith modular and defer ES/MinIO/Milvus/Kafka until later.

## 4. Key Timeline From The Resume Session

### 2026-07-13: Framework And MVP Scaffold

User confirmed:

```text
将现有页面视觉和功能拆成 Vue 3 页面，直接集成到若依的登录、权限和菜单体系中，并同步改造成“管网项目”
```

Major completed items recorded:

- Created/adapted `frontend/` as Vue 3 + Vite + Element Plus + Pinia + Vue Router.
- Created/adapted `backend/` as FastAPI + SQLAlchemy + RuoYi-style backend.
- Added `backend/module_pipeline`.
- Added `frontend/src/views/pipeline/...`.
- Added `frontend/src/api/pipeline/intelligence.js`.
- Added docs/plans for design, implementation, menu SQL, MVP completion, portal UI, and user portal consolidation.
- Added root `README.md`.

Historical verification from that stage:

- Backend pipeline service tests: `4 passed`.
- Backend module compile: passed.
- Backend app loaded around 161 routes and `/pipeline/dashboard` registered.
- Frontend dependencies installed.
- Frontend production build passed.

### 2026-07-13: Login/API Runtime Fix

User provided browser console logs showing 500 errors:

```text
/dev-api/transport/crypto/frontend-config 500
/dev-api/captchaImage 500
/dev-api/login 500
```

Diagnosis:

- Vite proxy mapped `/dev-api` to backend `http://127.0.0.1:9099`.
- Backend was not listening correctly on 9099.
- A stale `python.exe app.py` process was bound but not listening.
- Earlier backend failure was caused by MySQL authentication/config mismatch.
- Docker CLI commands hung because Docker service was stopped.

Resolution recorded:

- Switched development runtime to local services:

```text
MySQL: 127.0.0.1:3306 / root / 123456 / ruoyi-fastapi
Redis: 127.0.0.1:6379
```

- Verified:

```text
/dev-api/transport/crypto/frontend-config -> 200
/dev-api/captchaImage -> 200
/dev-api/login -> 200 and token returned
/dev-api/getRouters -> 200 and contains pipeline menu
```

Credentials communicated:

```text
Admin login: admin / admin123
New user initial password: 123456
```

Historical user-portal demo credential:

```text
niangao / admin123
```

Important: this demo credential was later removed from the visible user login UI. Do not re-add it to UI unless explicitly requested.

### 2026-07-13: Startup Commands

PowerShell startup commands communicated:

Backend, pip mode:

```powershell
cd D:\A_CODEBASE\pipeSight\backend
$env:PYTHONIOENCODING='utf-8'
python app.py
```

Frontend:

```powershell
cd D:\A_CODEBASE\pipeSight\frontend
npm run dev -- --host 127.0.0.1
```

Access:

```text
Frontend: http://127.0.0.1/
Backend:  http://127.0.0.1:9099
Swagger:  http://127.0.0.1:9099/docs
```

uv startup issue recorded:

```powershell
uv run --no-sync python app.py --env=dev
```

failed with:

```text
ModuleNotFoundError: No module named 'uvicorn'
```

Reason:

- `--no-sync` skips dependency installation/sync.
- The project venv did not yet have backend requirements installed.

Correct uv flow:

```powershell
cd D:\A_CODEBASE\pipeSight\backend
uv venv --python 3.11
uv pip install -r requirements.txt
$env:PYTHONIOENCODING='utf-8'
uv run --no-sync python app.py --env=dev
```

or, if dependency sync is configured later:

```powershell
uv run python app.py --env=dev
```

### 2026-07-13/14: MVP And Admin-Side Pipeline Pages

Backend business module:

```text
backend/module_pipeline/__init__.py
backend/module_pipeline/controller/pipeline_controller.py
backend/module_pipeline/entity/vo/pipeline_vo.py
backend/module_pipeline/service/pipeline_service.py
backend/tests/test_pipeline_service.py
backend/tests/test_pipeline_controller.py
```

Frontend business files:

```text
frontend/src/api/pipeline/intelligence.js
frontend/src/views/pipeline/dashboard/index.vue
frontend/src/views/pipeline/intelligence/index.vue
frontend/src/views/pipeline/intelligence/detail.vue
frontend/src/views/pipeline/source/index.vue
frontend/src/views/pipeline/task/index.vue
frontend/src/views/pipeline/report/index.vue
frontend/src/views/pipeline/knowledge/index.vue
frontend/src/assets/styles/pipeline.scss
frontend/src/utils/pipeline/reportPresentation.js
```

Business endpoints documented:

```text
GET  /pipeline/dashboard
GET  /pipeline/intelligence/list
GET  /pipeline/intelligence/{id}
GET  /pipeline/sources
GET  /pipeline/tasks
POST /pipeline/tasks/{id}/run
GET  /pipeline/reports
GET  /pipeline/reports/{id}/export
GET  /pipeline/knowledge/documents
POST /pipeline/knowledge/ask
```

MVP capability:

- Intelligence dashboard.
- News/public-account/paper intelligence list/detail.
- Data source list.
- Collection task list and manual task-run simulation.
- Report list and Markdown export.
- Knowledge document list and simple QA.
- Deterministic sample data for demo and tests.

### 2026-07-14: User Portal Separation

User repeatedly clarified:

- This is user-side UI, not backend management UI.
- User side must not expose:

```text
系统管理
系统监控
系统工具
AI 管理
个人中心
后台登录
```

Agreed user-side product structure:

```text
/portal-login
  -> login succeeds
/portal
  ├─ 新闻资讯
  │   └─ 新闻详情
  ├─ 论文资料
  │   └─ 论文详情
  └─ 日报周报
```

Auth rule:

- Public user-side route: `/portal-login`
- Protected content routes: `/portal`, `/portal/news/**`, `/portal/papers/**`, `/portal/reports/**`
- Backend/admin login remains `/login`

Current file state:

```text
frontend/src/views/portal/index.vue
frontend/src/views/portal/login.vue
frontend/src/utils/portal/auth.js
frontend/tests/pipeline-portal-auth.test.js
frontend/tests/pipeline-intellinews-layout.test.js
```

Historical consolidation plan proposed splitting `frontend/src/views/portal/index.vue` into components under `frontend/src/views/portal/components/`, but current disk state shows no such component directory. Treat the split as a planned/refactor step, not confirmed completed.

### 2026-07-14: IntelliNews Reference And Calm Login Page

User asked to reference:

```text
C:\Users\admin\Desktop\intellinews-demo
```

and later:

```text
https://www.calm.com/
```

Decisions:

- User portal content should reuse IntelliNews-style layout patterns where relevant.
- Login page should reference Calm-style interaction and structure.
- Avoid copying proprietary Calm image/text directly.
- Use the user-supplied PipeChina logo:

```text
https://www.pipechina.com.cn/Uploads/Picture/2023/09/05/s64f6d50827d73.png
```

Current user login direction:

- Calm-like hero/background.
- Click login/free-trial/owned-account opens a floating modal.
- Login must not appear inline at the bottom.
- User-side login is separate from admin login.

### 2026-07-15: Login Modal Iterations

User rejected multiple versions as unreasonable or too weak. Final accepted direction before latest cleanup:

- Compact single-column modal.
- Width around `520px`.
- Brand row on top.
- Lightweight selected target pill.
- Account/password/captcha/submit in a clear single column.
- No heavy two-column marketing panel.
- PipeChina logo displayed with `object-fit: contain`.
- Clean modal overlay with backdrop and close button.

Latest explicit cleanup request:

Remove all of these from the user login modal:

```text
演示账号：niangao / admin123
填入
登录成功后将自动进入目标栏目，用户端不会展示后台管理菜单。
使用用户端账号进入新闻资讯、论文资料和日报周报工作台
USER SIGN IN
管网项目用户端
```

Implemented cleanup:

- Removed demo account UI.
- Removed "填入" button.
- Removed `fillDemoAccount()` logic.
- Removed bottom explanatory text.
- Removed English kicker `USER SIGN IN`.
- Removed visible "管网项目用户端" login-modal text.
- Removed stale styles:

```text
calm-demo-account
calm-auth-note
```

Current user login modal still keeps:

- PipeSight brand name.
- PipeChina logo.
- Title:

```vue
登录进入 {{ selectedDestinationLabel }}
```

- Target pill:

```vue
本次进入 {{ selectedDestinationLabel }}
```

- Username/password/captcha fields.
- Submit button.
- Existing auth call:

```js
userStore.login(loginForm.value).then(() => {
  router.push({ path: redirect.value || '/portal' })
})
```

## 5. Existing Planning Documents

Current planning docs under `docs/plans/`:

```text
docs/plans/2026-07-13-pipeline-intelligence-platform-design.md
docs/plans/2026-07-13-pipeline-intelligence-platform-implementation.md
docs/plans/2026-07-13-pipeline-menu-seed.sql
docs/plans/2026-07-13-pipeline-mvp-completion-plan.md
docs/plans/2026-07-13-pipeline-portal-ui.md
docs/plans/2026-07-14-pipeline-user-portal-consolidation.md
```

This document is the resume-state and development-flow index for all of them.

Use the earlier docs this way:

- `pipeline-intelligence-platform-design.md`: product and architecture intent.
- `pipeline-intelligence-platform-implementation.md`: original scaffold and module plan.
- `pipeline-menu-seed.sql`: RuoYi menu/permission seed.
- `pipeline-mvp-completion-plan.md`: MVP backend/frontend interaction completion.
- `pipeline-portal-ui.md`: portal visual direction.
- `pipeline-user-portal-consolidation.md`: user portal auth/split/refactor plan.

## 6. Current Verification Evidence

Latest verification rerun after connecting the resume state:

```powershell
cd D:\A_CODEBASE\pipeSight\frontend
rg -n "USER SIGN IN|管网项目用户端|使用用户端账号进入新闻资讯|演示账号|niangao|admin123|登录成功后将自动进入目标栏目|fillDemoAccount|calm-demo-account|calm-auth-note" src/views/portal/login.vue
```

Result:

```text
No unwanted login-helper text found in src/views/portal/login.vue.
```

Frontend tests:

```powershell
cd D:\A_CODEBASE\pipeSight\frontend
node --test tests/*.test.js
```

Result:

```text
18 tests
18 pass
0 fail
```

Frontend build check:

```powershell
cd D:\A_CODEBASE\pipeSight\frontend
npm run check -- --logLevel silent
```

Result:

```text
exit code 0
```

Historical backend verification:

```powershell
cd D:\A_CODEBASE\pipeSight\backend
python -m pytest tests/test_pipeline_service.py -q
```

Recorded result:

```text
4 passed
```

## 7. Current Known Constraints And Risks

### No Git Repository

The current root is not a Git repository. Consequences:

- Cannot use `git status` to list all changed files.
- Cannot commit plan or code changes.
- Cannot create Git worktrees.
- Any "changed file" list is based on session logs and current disk inspection, not VCS diff.

### Docker Was Unavailable In The Resume Session

Recorded state:

- `com.docker.service` was stopped.
- `docker compose` and `docker ps` commands hung.
- The runtime was moved to local MySQL/Redis.

Do not assume Docker works without checking:

```powershell
docker info
```

### Python Environment

Historical warning:

- Global Python environment was used at one point.
- pip reported a conflict involving `zhipuai` and `PyJWT 2.11.0`.

Preferred future backend setup:

```powershell
cd D:\A_CODEBASE\pipeSight\backend
uv venv --python 3.11
uv pip install -r requirements.txt
$env:PYTHONIOENCODING='utf-8'
uv run --no-sync python app.py --env=dev
```

### Current State Mismatch: Legacy Static Assets

Historical notes say old static assets were preserved under `frontend/legacy-static`, but current disk state shows:

```text
frontend/dayReport-web      missing
frontend/legacy-static      missing
```

Do not rely on those directories without re-checking or restoring them from source/backups.

### User UI Quality Bar

The user has repeatedly rejected weak UI, especially:

- UI that looks like a backend/admin page.
- Inline login forms at the bottom of the page.
- Heavy two-column login marketing panels.
- Demo/helper/development text in formal user-facing UI.
- User portal menus exposing backend management entries.

Future UI changes must be verified against this standard.

## 8. Development Flow Going Forward

### Step 1: Rehydrate Context

Before making changes:

1. Read this document.
2. Check current disk state.
3. Use CodeGraph first for code areas.
4. Treat historical notes as context, but current disk state as the implementation source of truth.

### Step 2: Classify The Work

For a UI/feature change:

- Use TDD where feasible.
- Update or add a focused test first.
- Confirm the test fails for the current behavior.
- Implement the minimum scoped change.
- Re-run target test.
- Re-run all frontend tests/build if UI or route/auth is touched.

For backend behavior:

- Add/adjust pytest coverage first.
- Run target pytest and confirm failure.
- Implement service/controller/VO changes.
- Re-run target and relevant route/app checks.

### Step 3: Verification Commands

Frontend standard verification:

```powershell
cd D:\A_CODEBASE\pipeSight\frontend
node --test tests/*.test.js
npm run check -- --logLevel silent
```

Targeted user-login cleanup check:

```powershell
cd D:\A_CODEBASE\pipeSight\frontend
rg -n "USER SIGN IN|管网项目用户端|使用用户端账号进入新闻资讯|演示账号|niangao|admin123|登录成功后将自动进入目标栏目|fillDemoAccount|calm-demo-account|calm-auth-note" src/views/portal/login.vue
```

Backend standard verification:

```powershell
cd D:\A_CODEBASE\pipeSight\backend
python -m pytest tests/test_pipeline_service.py -q
```

Backend route smoke check, if backend can import:

```powershell
cd D:\A_CODEBASE\pipeSight\backend
python -c "from server import create_app; app = create_app(); print(any(getattr(r, 'path', '') == '/pipeline/dashboard' for r in app.routes))"
```

Runtime smoke checks, if services are running:

```powershell
Invoke-WebRequest http://127.0.0.1:9099/captchaImage
Invoke-WebRequest http://127.0.0.1/dev-api/captchaImage
```

### Step 4: Manual Route Acceptance

User portal:

```text
/portal-login             public user login page
/portal                   protected user home
/portal/news              protected news list
/portal/news/<id>         protected news detail
/portal/papers            protected paper list
/portal/papers/<id>       protected paper detail
/portal/reports           protected daily/weekly report center
```

Expected behavior:

- Anonymous `/portal/**` redirects to `/portal-login?redirect=...`.
- Successful user login redirects to requested portal route.
- User portal does not show backend management menus.
- Login opens as modal overlay.
- Login modal does not show demo account/helper text.

Admin side:

```text
/login
```

Expected behavior:

- RuoYi admin login remains separate.
- Admin side can still show management menus according to role/menu permissions.

## 9. Open Work Backlog

### High Priority

1. Re-check whether `frontend/legacy-static` or `frontend/dayReport-web` should be restored or documented as removed.
2. Keep user portal login UI polished and minimal; do not re-add demo/helper text.
3. Confirm backend runtime works in a clean venv/uv setup.
4. Confirm local MySQL/Redis database has required RuoYi seed data and `pipeline` menu entries.
5. Re-run backend tests after any backend dependency/environment change.

### Medium Priority

1. Execute or revise `docs/plans/2026-07-14-pipeline-user-portal-consolidation.md`:
   - Split `frontend/src/views/portal/index.vue` into smaller components.
   - Keep `/portal-login` public and `/portal/**` protected.
2. Add visual/manual smoke notes for user portal routes.
3. Improve README to reflect actual current legacy-static state.
4. Decide whether Docker should be repaired or local services are the official dev flow.

### Deferred Production Work

1. Real collection workers for RSS/API/crawlers.
2. Data cleaning and deduplication pipeline.
3. Elasticsearch full-text search.
4. MinIO document storage.
5. Vector index/RAG knowledge QA.
6. Report template orchestration and export.
7. Human audit workflow.
8. Kafka/ES/Milvus infrastructure integration.
9. Persistent task logs and alerting.

## 10. Do-Not-Regress Checklist

Do not reintroduce these into user login UI:

```text
演示账号：niangao / admin123
填入
登录成功后将自动进入目标栏目，用户端不会展示后台管理菜单。
使用用户端账号进入新闻资讯、论文资料和日报周报工作台
USER SIGN IN
管网项目用户端
```

Do not expose these in user portal:

```text
系统管理
系统监控
系统工具
AI 管理
个人中心
后台登录
```

Do not merge user-side login with admin login:

```text
User side: /portal-login
Admin side: /login
```

Do not assume Docker is available.

Do not assume Git exists.

Do not treat the platform as a pipeline patrol/GIS system unless the user explicitly changes the product direction.

