# Pipeline MVP Completion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current RuoYi-integrated pipeline scaffold into a usable demo MVP for “管网科技情报与科研辅助平台”.

**Architecture:** Keep the existing RuoYi Vue3 + FastAPI authentication, permission, menu, and layout. Complete the pipeline domain as a lightweight business module with deterministic in-project data, report export, knowledge-base search/QA, source/task operations, and readable Chinese content; defer Kafka/ES/Milvus/MinIO until the production phase.

**Tech Stack:** Vue 3, Vite, Element Plus, FastAPI, Pydantic, pytest.

---

### Task 1: Backend domain behavior

**Files:**
- Modify: `backend/tests/test_pipeline_service.py`
- Modify: `backend/module_pipeline/service/pipeline_service.py`
- Modify: `backend/module_pipeline/entity/vo/pipeline_vo.py`
- Modify: `backend/module_pipeline/controller/pipeline_controller.py`

**Step 1:** Add failing tests for readable Chinese sample data, task run simulation, report markdown export, and knowledge-base QA.

**Step 2:** Run `python -m pytest tests/test_pipeline_service.py -q` and verify the new tests fail because methods/data do not exist or are incorrect.

**Step 3:** Replace mojibake sample data with readable Chinese, then implement `run_collect_task`, `export_report_markdown`, `list_knowledge_documents`, and `ask_knowledge_base`.

**Step 4:** Add FastAPI endpoints for task run, report export, knowledge documents, and knowledge ask.

**Step 5:** Re-run `python -m pytest tests/test_pipeline_service.py -q` and verify all tests pass.

### Task 2: Frontend API and page interactions

**Files:**
- Modify: `frontend/src/api/pipeline/intelligence.js`
- Modify: `frontend/src/views/pipeline/task/index.vue`
- Modify: `frontend/src/views/pipeline/report/index.vue`
- Modify: `frontend/src/views/pipeline/knowledge/index.vue`

**Step 1:** Add API wrappers for running a task, exporting a report, listing knowledge documents, and asking the knowledge base.

**Step 2:** Wire task “运行” buttons to the backend task-run endpoint and refresh the task table.

**Step 3:** Wire report “导出” buttons to the backend export endpoint and download a markdown file.

**Step 4:** Wire knowledge document list and QA box to backend endpoints.

**Step 5:** Run `npm run build:prod` and verify the frontend builds.

### Task 3: Documentation and final verification

**Files:**
- Modify: `README.md`

**Step 1:** Document the current MVP scope and remaining production-grade work.

**Step 2:** Verify login/API smoke path if backend is running.

**Step 3:** Run backend tests and frontend build.
