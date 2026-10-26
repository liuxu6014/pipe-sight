-- PipeSight 最终业务库（核心域，PostgreSQL 14+）

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 将 UTF-8 字节编码为 ASCII，使 pg_trgm 能覆盖中文子串；原文 ILIKE 仍负责最终校验。
CREATE OR REPLACE FUNCTION pipeline_utf8_hex(value TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
PARALLEL SAFE
AS $$
  SELECT encode(convert_to(coalesce(value, ''), 'UTF8'), 'hex')
$$;

CREATE TABLE IF NOT EXISTS knowledge_files (
  file_id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  category VARCHAR(64) NOT NULL DEFAULT '内部文献',
  file_name VARCHAR(255),
  file_path VARCHAR(500),
  file_url VARCHAR(1000),
  mime_type VARCHAR(128),
  file_size BIGINT NOT NULL DEFAULT 0,
  file_hash VARCHAR(128),
  permission_scope VARCHAR(32) NOT NULL DEFAULT 'private',
  allow_download BOOLEAN NOT NULL DEFAULT TRUE,
  allow_ai_use BOOLEAN NOT NULL DEFAULT TRUE,
  parse_status VARCHAR(32) NOT NULL DEFAULT 'queued',
  parse_message VARCHAR(500),
  parse_attempt_count INTEGER NOT NULL DEFAULT 0,
  parse_lease_owner VARCHAR(128),
  parse_lease_until TIMESTAMP,
  parse_next_retry_at TIMESTAMP,
  scan_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  scan_message VARCHAR(500),
  scan_time TIMESTAMP,
  scanner_name VARCHAR(128),
  summary TEXT,
  extracted_text TEXT,
  tags JSON NOT NULL,
  metadata_json JSON NOT NULL,
  version_no INTEGER NOT NULL DEFAULT 1,
  owner_id BIGINT NOT NULL,
  owner_name VARCHAR(64) NOT NULL,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ck_knowledge_files_permission_scope CHECK (permission_scope IN ('private', 'public')),
  CONSTRAINT ck_knowledge_files_parse_status CHECK (parse_status IN ('queued', 'parsing', 'indexed', 'failed')),
  CONSTRAINT ck_knowledge_files_parse_attempt_count CHECK (parse_attempt_count >= 0),
  CONSTRAINT ck_knowledge_files_scan_status CHECK (scan_status IN ('pending', 'clean', 'quarantined', 'failed')),
  CONSTRAINT ck_knowledge_files_file_size CHECK (file_size >= 0),
  CONSTRAINT ck_knowledge_files_version_no CHECK (version_no >= 1),
  CONSTRAINT fk_knowledge_files_user FOREIGN KEY (owner_id) REFERENCES sys_user(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_knowledge_files_owner_time ON knowledge_files(owner_id, update_time);
CREATE INDEX IF NOT EXISTS idx_knowledge_files_scope ON knowledge_files(permission_scope, update_time);
CREATE INDEX IF NOT EXISTS idx_knowledge_files_status_time ON knowledge_files(parse_status, update_time);
CREATE INDEX IF NOT EXISTS idx_knowledge_files_parse_dispatch
  ON knowledge_files(parse_status, scan_status, parse_next_retry_at, parse_lease_until, update_time);
CREATE INDEX IF NOT EXISTS idx_knowledge_files_scan_status_time ON knowledge_files(scan_status, update_time);
CREATE INDEX IF NOT EXISTS idx_knowledge_files_hash ON knowledge_files(file_hash);

CREATE TABLE IF NOT EXISTS user_saved_items (
  saved_item_id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL,
  item_id VARCHAR(64) NOT NULL,
  item_type VARCHAR(32) NOT NULL,
  action VARCHAR(16) NOT NULL,
  title VARCHAR(500) NOT NULL,
  snapshot JSON NOT NULL,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_user_saved_items_target_action UNIQUE (user_id, item_type, item_id, action),
  CONSTRAINT ck_user_saved_items_item_type CHECK (item_type IN ('material', 'article', 'paper', 'report')),
  CONSTRAINT ck_user_saved_items_action CHECK (action IN ('favorite', 'basket')),
  CONSTRAINT fk_user_saved_items_user FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_user_saved_items_user_action_time ON user_saved_items(user_id, action, create_time);
CREATE INDEX IF NOT EXISTS idx_user_saved_items_target ON user_saved_items(item_type, item_id);

CREATE TABLE IF NOT EXISTS generation_tasks (
  task_id VARCHAR(64) PRIMARY KEY,
  user_id BIGINT NOT NULL,
  owner_name VARCHAR(64) NOT NULL,
  title VARCHAR(500) NOT NULL,
  report_type VARCHAR(64) NOT NULL,
  template_id VARCHAR(64),
  template_version VARCHAR(32),
  status VARCHAR(32) NOT NULL DEFAULT 'queued',
  current_stage VARCHAR(64) NOT NULL DEFAULT 'validating',
  progress INTEGER NOT NULL DEFAULT 0,
  config JSON NOT NULL,
  selected_items JSON NOT NULL,
  outline JSON NOT NULL,
  stages JSON NOT NULL,
  logs JSON NOT NULL,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  lease_owner VARCHAR(128),
  lease_until TIMESTAMP,
  next_retry_at TIMESTAMP,
  cancel_requested_at TIMESTAMP,
  error_message TEXT,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ck_generation_tasks_status CHECK (status IN ('queued', 'running', 'completed', 'failed', 'dead_letter', 'cancelled')),
  CONSTRAINT ck_generation_tasks_progress CHECK (progress BETWEEN 0 AND 100),
  CONSTRAINT ck_generation_tasks_attempt_count CHECK (attempt_count >= 0),
  CONSTRAINT fk_generation_tasks_user FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_generation_tasks_user_status_time ON generation_tasks(user_id, status, update_time);
CREATE INDEX IF NOT EXISTS idx_generation_tasks_dispatch ON generation_tasks(status, next_retry_at, lease_until, update_time);
CREATE INDEX IF NOT EXISTS idx_generation_tasks_cancel_dispatch ON generation_tasks(status, cancel_requested_at, lease_until, update_time);

CREATE TABLE IF NOT EXISTS digest_schedules (
  schedule_id VARCHAR(64) PRIMARY KEY,
  user_id BIGINT NOT NULL,
  request_id VARCHAR(128),
  owner_name VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  report_type VARCHAR(32) NOT NULL,
  template_id VARCHAR(64) NOT NULL,
  template_version VARCHAR(32),
  schedule_time VARCHAR(5) NOT NULL DEFAULT '08:00',
  config JSON NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  next_run_time TIMESTAMP NOT NULL,
  last_run_time TIMESTAMP,
  last_task_id VARCHAR(64),
  last_status VARCHAR(32),
  last_error TEXT,
  failure_count INTEGER NOT NULL DEFAULT 0,
  lease_owner VARCHAR(128),
  lease_until TIMESTAMP,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ck_digest_schedules_report_type CHECK (report_type IN ('daily', 'weekly', 'monthly')),
  CONSTRAINT ck_digest_schedules_last_status CHECK (last_status IS NULL OR last_status IN ('queued', 'no_data', 'skipped', 'failed')),
  CONSTRAINT ck_digest_schedules_failure_count CHECK (failure_count >= 0),
  CONSTRAINT fk_digest_schedules_user FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_digest_schedules_task FOREIGN KEY (last_task_id) REFERENCES generation_tasks(task_id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_digest_schedules_user_request ON digest_schedules(user_id, request_id);
CREATE INDEX IF NOT EXISTS idx_digest_schedules_dispatch ON digest_schedules(enabled, next_run_time, lease_until);
CREATE INDEX IF NOT EXISTS idx_digest_schedules_user_time ON digest_schedules(user_id, update_time);

CREATE TABLE IF NOT EXISTS reports (
  report_id VARCHAR(64) PRIMARY KEY,
  source_task_id VARCHAR(64),
  user_id BIGINT NOT NULL,
  owner_name VARCHAR(64) NOT NULL,
  title VARCHAR(500) NOT NULL,
  report_type VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  version_no INTEGER NOT NULL DEFAULT 1,
  content TEXT NOT NULL,
  sections JSON NOT NULL,
  citations JSON NOT NULL,
  quality_issues JSON NOT NULL,
  metadata_json JSON NOT NULL,
  word_count INTEGER NOT NULL DEFAULT 0,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_reports_source_task UNIQUE (source_task_id),
  CONSTRAINT ck_reports_status CHECK (status IN ('draft', 'reviewing', 'completed', 'published', 'archived')),
  CONSTRAINT ck_reports_version_no CHECK (version_no >= 1),
  CONSTRAINT ck_reports_word_count CHECK (word_count >= 0),
  CONSTRAINT fk_reports_generation_tasks FOREIGN KEY (source_task_id) REFERENCES generation_tasks(task_id) ON DELETE SET NULL,
  CONSTRAINT fk_reports_user FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_reports_user_type_time ON reports(user_id, report_type, update_time);
CREATE INDEX IF NOT EXISTS idx_reports_user_status_time ON reports(user_id, status, update_time);

CREATE TABLE IF NOT EXISTS report_versions (
  report_version_id BIGSERIAL PRIMARY KEY,
  report_id VARCHAR(64) NOT NULL,
  version_no INTEGER NOT NULL,
  title VARCHAR(500) NOT NULL,
  content TEXT NOT NULL,
  sections JSON NOT NULL,
  citations JSON NOT NULL,
  quality_issues JSON NOT NULL,
  model_snapshot JSON NOT NULL,
  source VARCHAR(32) NOT NULL DEFAULT 'manual',
  operator_id BIGINT,
  operator_name VARCHAR(64) NOT NULL,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_report_versions_report_version UNIQUE (report_id, version_no),
  CONSTRAINT ck_report_versions_version_no CHECK (version_no >= 1),
  CONSTRAINT ck_report_versions_source CHECK (source IN ('generated', 'retry', 'manual', 'autosave', 'publish', 'restored')),
  CONSTRAINT fk_report_versions_reports FOREIGN KEY (report_id) REFERENCES reports(report_id) ON DELETE CASCADE,
  CONSTRAINT fk_report_versions_user FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_report_versions_report_time ON report_versions(report_id, create_time);

CREATE TABLE IF NOT EXISTS report_publications (
  publication_id VARCHAR(64) PRIMARY KEY,
  report_id VARCHAR(64) NOT NULL,
  report_version_no INTEGER NOT NULL,
  action VARCHAR(16) NOT NULL,
  operator_id BIGINT,
  operator_name VARCHAR(64) NOT NULL,
  note TEXT,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ck_report_publications_action CHECK (action IN ('publish', 'unpublish')),
  CONSTRAINT ck_report_publications_report_version_no CHECK (report_version_no >= 1),
  CONSTRAINT fk_report_publications_report FOREIGN KEY (report_id) REFERENCES reports(report_id) ON DELETE CASCADE,
  CONSTRAINT fk_report_publications_operator FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_report_publications_report_time ON report_publications(report_id, create_time);
CREATE INDEX IF NOT EXISTS idx_report_publications_action_time ON report_publications(action, create_time);

CREATE TABLE IF NOT EXISTS report_exports (
  export_id VARCHAR(64) PRIMARY KEY,
  report_id VARCHAR(64) NOT NULL,
  user_id BIGINT NOT NULL,
  report_version_no INTEGER NOT NULL,
  report_revision TIMESTAMP NOT NULL,
  format VARCHAR(16) NOT NULL,
  template_version VARCHAR(64),
  file_name VARCHAR(500) NOT NULL,
  file_key VARCHAR(500) NOT NULL,
  content_type VARCHAR(128) NOT NULL,
  file_size BIGINT NOT NULL DEFAULT 0,
  file_hash VARCHAR(128),
  snapshot JSON NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'queued',
  attempt_count INTEGER NOT NULL DEFAULT 0,
  lease_owner VARCHAR(128),
  lease_until TIMESTAMP,
  next_retry_at TIMESTAMP,
  error_message TEXT,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_time TIMESTAMP,
  CONSTRAINT ck_report_exports_format CHECK (format IN ('docx', 'pdf')),
  CONSTRAINT ck_report_exports_status CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  CONSTRAINT ck_report_exports_report_version_no CHECK (report_version_no >= 1),
  CONSTRAINT ck_report_exports_file_size CHECK (file_size >= 0),
  CONSTRAINT ck_report_exports_attempt_count CHECK (attempt_count >= 0),
  CONSTRAINT fk_report_exports_report FOREIGN KEY (report_id) REFERENCES reports(report_id) ON DELETE CASCADE,
  CONSTRAINT fk_report_exports_user FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_report_exports_user_report_time ON report_exports(user_id, report_id, create_time);
CREATE INDEX IF NOT EXISTS idx_report_exports_status_time ON report_exports(status, update_time);
CREATE INDEX IF NOT EXISTS idx_report_exports_dispatch ON report_exports(status, next_retry_at, lease_until, update_time);
