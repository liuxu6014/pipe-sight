-- PipeSight 最终业务库（核心域，PostgreSQL 14+）

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
  CONSTRAINT ck_knowledge_files_file_size CHECK (file_size >= 0),
  CONSTRAINT ck_knowledge_files_version_no CHECK (version_no >= 1),
  CONSTRAINT fk_knowledge_files_user FOREIGN KEY (owner_id) REFERENCES sys_user(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_knowledge_files_owner_time ON knowledge_files(owner_id, update_time);
CREATE INDEX IF NOT EXISTS idx_knowledge_files_scope ON knowledge_files(permission_scope, update_time);
CREATE INDEX IF NOT EXISTS idx_knowledge_files_status_time ON knowledge_files(parse_status, update_time);
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
  error_message TEXT,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ck_generation_tasks_status CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
  CONSTRAINT ck_generation_tasks_progress CHECK (progress BETWEEN 0 AND 100),
  CONSTRAINT fk_generation_tasks_user FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_generation_tasks_user_status_time ON generation_tasks(user_id, status, update_time);

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
