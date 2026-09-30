# 管网科技情报平台 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将当前静态演示目录整理为基于若依 Vue3 + FastAPI 的管网科技情报全栈项目。

**Architecture:** 保留若依登录、权限、动态菜单和基础后台能力。新增管网业务前端页面与 FastAPI 业务模块，先用内置样例数据形成可运行闭环。

**Tech Stack:** Vue3, Vite, Element Plus, Pinia, Vue Router, FastAPI, SQLAlchemy, Pydantic, pytest.

---

## Constraints

- 当前根目录不是 Git 仓库，无法创建 git worktree，也无法提交阶段性 commit。
- 现有 `frontend/dayReport-web` 是构建产物，不可逆向恢复成完整 Vue 源码；应保留为 `frontend/legacy-static/`。
- 代码落地必须避免删除旧产物。

## Task 1: Scaffold RuoYi Full Stack

**Files:**

- Preserve: `frontend/dayReport-web` under `frontend/legacy-static/dayReport-web`
- Move: `frontend/scripts` to `frontend/legacy-static/scripts`
- Move: `frontend/README.md` to `frontend/legacy-static/README.md`
- Copy: `.upstream-ruoyi-vue3-fastapi/ruoyi-fastapi-frontend/*` to `frontend/`
- Copy: `.upstream-ruoyi-vue3-fastapi/ruoyi-fastapi-backend/*` to `backend/`
- Copy: `.upstream-ruoyi-vue3-fastapi/docker-compose.pg.yml` to `docker-compose.pg.yml`
- Copy: `.upstream-ruoyi-vue3-fastapi/docker-compose.my.yml` to `docker-compose.my.yml`

**Step 1:** Verify source and target paths are inside `D:\A_CODEBASE\pipeSight`.

**Step 2:** Move or copy old static assets into `frontend/legacy-static`. If Windows refuses to move a locked directory, copy it and leave the original in place.

**Step 3:** Copy upstream RuoYi frontend and backend.

**Step 4:** Confirm `frontend/package.json`, `frontend/src/main.js`, `backend/app.py`, and `backend/server.py` exist.

## Task 2: Add Frontend Pipeline Domain

**Files:**

- Create: `frontend/src/api/pipeline/intelligence.js`
- Create: `frontend/src/views/pipeline/dashboard/index.vue`
- Create: `frontend/src/views/pipeline/intelligence/index.vue`
- Create: `frontend/src/views/pipeline/intelligence/detail.vue`
- Create: `frontend/src/views/pipeline/source/index.vue`
- Create: `frontend/src/views/pipeline/task/index.vue`
- Create: `frontend/src/views/pipeline/report/index.vue`
- Create: `frontend/src/views/pipeline/knowledge/index.vue`
- Modify: `frontend/src/settings.js`
- Modify: `frontend/package.json`

**Step 1:** Add API wrapper functions for dashboard, intelligence list/detail, sources, tasks, and reports.

**Step 2:** Build data-dense Vue pages using Element Plus tables, filters, tags, descriptions, timeline, and empty states.

**Step 3:** Rename product metadata from generic RuoYi/VFAdmin to “管网科技情报平台”.

**Step 4:** Add a frontend check script that builds the production bundle.

## Task 3: Add Backend Pipeline Module

**Files:**

- Create: `backend/module_pipeline/__init__.py`
- Create: `backend/module_pipeline/controller/__init__.py`
- Create: `backend/module_pipeline/controller/pipeline_controller.py`
- Create: `backend/module_pipeline/service/__init__.py`
- Create: `backend/module_pipeline/service/pipeline_service.py`
- Create: `backend/module_pipeline/entity/__init__.py`
- Create: `backend/module_pipeline/entity/vo/__init__.py`
- Create: `backend/module_pipeline/entity/vo/pipeline_vo.py`
- Create: `backend/tests/test_pipeline_service.py`

**Step 1: Write failing tests**

Run: `python -m pytest tests/test_pipeline_service.py -q`

Expected: import failure because the module does not exist yet.

**Step 2:** Implement VO models and service methods returning deterministic sample data.

**Step 3:** Add controller with `/pipeline/dashboard`, `/pipeline/intelligence/list`, `/pipeline/intelligence/{item_id}`, `/pipeline/sources`, `/pipeline/tasks`, `/pipeline/reports`.

**Step 4:** Re-run tests and confirm they pass.

## Task 4: Document Menu Integration

**Files:**

- Create: `docs/plans/2026-07-13-pipeline-menu-seed.sql`
- Modify: `README.md`

**Step 1:** Add SQL examples for 若依 menu and permission codes.

**Step 2:** Add root README with run commands for frontend and backend.

## Task 5: Verification

**Commands:**

- `python -m pytest tests/test_pipeline_service.py -q` in `backend/`
- `npm install` in `frontend/`
- `npm run build:prod` in `frontend/`

**Expected:**

- Backend tests pass.
- Frontend production build exits with code 0.
- No legacy files are deleted.
