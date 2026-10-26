-- PipeSight 最终业务库（采集与内容域，PostgreSQL 14+）

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

CREATE TABLE IF NOT EXISTS data_sources (
  source_id VARCHAR(64) PRIMARY KEY,
  source_code VARCHAR(100) NOT NULL,
  name VARCHAR(255) NOT NULL,
  source_type VARCHAR(32) NOT NULL,
  endpoint VARCHAR(1000),
  adapter_key VARCHAR(128) NOT NULL,
  schedule_cron VARCHAR(100),
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  config_json JSON NOT NULL,
  handoff_mode VARCHAR(16) NOT NULL DEFAULT 'external',
  processor_source_code VARCHAR(128),
  last_run_time TIMESTAMP,
  last_run_status VARCHAR(32),
  success_count INTEGER NOT NULL DEFAULT 0,
  failure_count INTEGER NOT NULL DEFAULT 0,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  collection_lease_owner VARCHAR(128),
  collection_lease_until TIMESTAMP,
  owner_id BIGINT,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_data_sources_code UNIQUE (source_code),
  CONSTRAINT ck_data_sources_status CHECK (status IN ('active', 'inactive')),
  CONSTRAINT ck_data_sources_handoff_mode CHECK (handoff_mode IN ('local', 'external')),
  CONSTRAINT ck_data_sources_counters CHECK (success_count >= 0 AND failure_count >= 0 AND consecutive_failures >= 0),
  CONSTRAINT fk_data_sources_user FOREIGN KEY (owner_id) REFERENCES sys_user(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_data_sources_type_status ON data_sources(source_type, status);
CREATE INDEX IF NOT EXISTS idx_data_sources_owner ON data_sources(owner_id);
CREATE INDEX IF NOT EXISTS idx_data_sources_collection_lease
  ON data_sources(enabled, status, collection_lease_until, update_time);

CREATE TABLE IF NOT EXISTS pipeline_template_versions (
  template_id VARCHAR(64) PRIMARY KEY,
  template_key VARCHAR(64) NOT NULL,
  code VARCHAR(32) NOT NULL,
  category VARCHAR(32) NOT NULL,
  report_type VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description VARCHAR(1000) NOT NULL DEFAULT '',
  color VARCHAR(32) NOT NULL DEFAULT '#2764e7',
  version_label VARCHAR(32) NOT NULL,
  version_no INTEGER NOT NULL DEFAULT 1,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  formats JSON NOT NULL,
  sections JSON NOT NULL,
  usage_count INTEGER NOT NULL DEFAULT 0,
  operator_id BIGINT,
  operator_name VARCHAR(64) NOT NULL DEFAULT '',
  published_at TIMESTAMP,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_pipeline_template_key_version UNIQUE (template_key, version_no),
  CONSTRAINT ck_pipeline_template_status CHECK (status IN ('draft', 'published', 'retired')),
  CONSTRAINT ck_pipeline_template_version_no CHECK (version_no >= 1),
  CONSTRAINT fk_pipeline_template_user FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pipeline_template_category_status ON pipeline_template_versions(category, status);
CREATE INDEX IF NOT EXISTS idx_pipeline_template_key_time ON pipeline_template_versions(template_key, update_time);

CREATE TABLE IF NOT EXISTS collection_runs (
  run_id VARCHAR(64) PRIMARY KEY,
  source_id VARCHAR(64) NOT NULL,
  scheduler_job_id BIGINT,
  trigger_type VARCHAR(32) NOT NULL DEFAULT 'schedule',
  status VARCHAR(32) NOT NULL DEFAULT 'queued',
  config_snapshot JSON NOT NULL,
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  fetched_count INTEGER NOT NULL DEFAULT 0,
  inserted_count INTEGER NOT NULL DEFAULT 0,
  updated_count INTEGER NOT NULL DEFAULT 0,
  duplicate_count INTEGER NOT NULL DEFAULT 0,
  failed_count INTEGER NOT NULL DEFAULT 0,
  handoff_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  handoff_batch_id VARCHAR(64),
  handoff_count INTEGER NOT NULL DEFAULT 0,
  handoff_processed_count INTEGER NOT NULL DEFAULT 0,
  handoff_rejected_count INTEGER NOT NULL DEFAULT 0,
  handoff_failed_count INTEGER NOT NULL DEFAULT 0,
  handoff_time TIMESTAMP,
  handoff_error TEXT,
  handoff_lease_owner VARCHAR(128),
  handoff_lease_until TIMESTAMP,
  error_message TEXT,
  checkpoint_json JSON NOT NULL,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ck_collection_runs_trigger_type CHECK (trigger_type IN ('schedule', 'manual', 'retry')),
  CONSTRAINT ck_collection_runs_status CHECK (status IN ('queued', 'running', 'success', 'failed', 'cancelled')),
  CONSTRAINT ck_collection_runs_counters CHECK (fetched_count >= 0 AND inserted_count >= 0 AND updated_count >= 0 AND duplicate_count >= 0 AND failed_count >= 0 AND handoff_count >= 0 AND handoff_processed_count >= 0 AND handoff_rejected_count >= 0 AND handoff_failed_count >= 0),
  CONSTRAINT ck_collection_runs_handoff_status CHECK (handoff_status IN ('pending', 'dispatched', 'processing', 'completed', 'partial', 'failed')),
  CONSTRAINT fk_collection_runs_sources FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE RESTRICT,
  CONSTRAINT fk_collection_runs_jobs FOREIGN KEY (scheduler_job_id) REFERENCES sys_job(job_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_collection_runs_source_time ON collection_runs(source_id, create_time);
CREATE INDEX IF NOT EXISTS idx_collection_runs_status_time ON collection_runs(status, create_time);
CREATE INDEX IF NOT EXISTS idx_collection_runs_handoff_lease
  ON collection_runs(handoff_status, handoff_lease_until, update_time);

CREATE TABLE IF NOT EXISTS news_articles (
  article_id VARCHAR(64) PRIMARY KEY,
  article_type VARCHAR(32) NOT NULL,
  title VARCHAR(500) NOT NULL,
  canonical_url VARCHAR(1500),
  url_hash VARCHAR(128),
  source_id VARCHAR(64),
  source_name VARCHAR(255),
  collection_run_id VARCHAR(64),
  author_text VARCHAR(500),
  published_time TIMESTAMP,
  discovered_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  language VARCHAR(16) NOT NULL DEFAULT 'zh-CN',
  summary TEXT,
  body TEXT,
  article_hash VARCHAR(128),
  relevance_score INTEGER NOT NULL DEFAULT 0,
  review_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  reviewed_by BIGINT,
  reviewed_at TIMESTAMP,
  review_reason TEXT,
  published_at TIMESTAMP,
  permission_scope VARCHAR(32) NOT NULL DEFAULT 'public',
  tags JSON NOT NULL,
  metadata_json JSON NOT NULL,
  analysis_version VARCHAR(64),
  handoff_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  handoff_batch_id VARCHAR(64),
  handoff_record_id VARCHAR(128),
  handoff_trace_id VARCHAR(64),
  handoff_version VARCHAR(64),
  handoff_result_json JSON NOT NULL DEFAULT '{}'::json,
  handoff_time TIMESTAMP,
  handoff_error TEXT,
  version_no INTEGER NOT NULL DEFAULT 1,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_news_articles_hash UNIQUE (article_hash),
  CONSTRAINT uk_news_articles_url_hash UNIQUE (url_hash),
  CONSTRAINT ck_news_articles_type CHECK (article_type IN ('news', 'wechat')),
  CONSTRAINT ck_news_articles_relevance CHECK (relevance_score BETWEEN 0 AND 100),
  CONSTRAINT ck_news_articles_review_status CHECK (review_status IN ('pending', 'approved', 'rejected')),
  CONSTRAINT ck_news_articles_permission_scope CHECK (permission_scope IN ('private', 'public')),
  CONSTRAINT ck_news_articles_handoff_status CHECK (handoff_status IN ('pending', 'dispatched', 'processing', 'completed', 'partial', 'failed', 'rejected')),
  CONSTRAINT fk_news_articles_sources FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE SET NULL,
  CONSTRAINT fk_news_articles_runs FOREIGN KEY (collection_run_id) REFERENCES collection_runs(run_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_news_articles_type_time ON news_articles(article_type, published_time);
CREATE INDEX IF NOT EXISTS idx_news_articles_source_time ON news_articles(source_id, published_time);
CREATE INDEX IF NOT EXISTS idx_news_articles_review_time ON news_articles(review_status, published_time);
CREATE INDEX IF NOT EXISTS idx_news_articles_review_queue ON news_articles(review_status, handoff_status, update_time);

CREATE TABLE IF NOT EXISTS papers (
  paper_id VARCHAR(64) PRIMARY KEY,
  title VARCHAR(500) NOT NULL,
  canonical_url VARCHAR(1500),
  source_id VARCHAR(64),
  source_name VARCHAR(255),
  collection_run_id VARCHAR(64),
  authors VARCHAR(1000),
  authors_json JSON NOT NULL,
  keywords JSON NOT NULL,
  doi VARCHAR(255),
  doi_normalized VARCHAR(255),
  external_id VARCHAR(255),
  journal VARCHAR(255),
  publisher VARCHAR(255),
  publication_year INTEGER,
  volume VARCHAR(64),
  issue VARCHAR(64),
  pages VARCHAR(64),
  abstract_text TEXT,
  full_text_url VARCHAR(1500),
  citation_count INTEGER NOT NULL DEFAULT 0,
  open_access_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
  full_text_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
  review_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  reviewed_by BIGINT,
  reviewed_at TIMESTAMP,
  review_reason TEXT,
  published_at TIMESTAMP,
  permission_scope VARCHAR(32) NOT NULL DEFAULT 'public',
  tags JSON NOT NULL,
  metadata_json JSON NOT NULL,
  handoff_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  handoff_batch_id VARCHAR(64),
  handoff_record_id VARCHAR(128),
  handoff_trace_id VARCHAR(64),
  handoff_version VARCHAR(64),
  handoff_result_json JSON NOT NULL DEFAULT '{}'::json,
  handoff_time TIMESTAMP,
  handoff_error TEXT,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_papers_doi_normalized UNIQUE (doi_normalized),
  CONSTRAINT ck_papers_publication_year CHECK (publication_year IS NULL OR publication_year >= 1600),
  CONSTRAINT ck_papers_citation_count CHECK (citation_count >= 0),
  CONSTRAINT ck_papers_review_status CHECK (review_status IN ('pending', 'approved', 'rejected')),
  CONSTRAINT ck_papers_permission_scope CHECK (permission_scope IN ('private', 'public')),
  CONSTRAINT ck_papers_handoff_status CHECK (handoff_status IN ('pending', 'dispatched', 'processing', 'completed', 'partial', 'failed', 'rejected')),
  CONSTRAINT fk_papers_sources FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE SET NULL,
  CONSTRAINT fk_papers_runs FOREIGN KEY (collection_run_id) REFERENCES collection_runs(run_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(publication_year);
CREATE INDEX IF NOT EXISTS idx_papers_journal ON papers(journal);
CREATE INDEX IF NOT EXISTS idx_papers_source_time ON papers(source_id, create_time);
CREATE INDEX IF NOT EXISTS idx_papers_review_queue ON papers(review_status, handoff_status, update_time);
CREATE INDEX IF NOT EXISTS idx_papers_review_published ON papers(review_status, published_at);

CREATE TABLE IF NOT EXISTS pipeline_prompt_versions (
  prompt_id VARCHAR(64) PRIMARY KEY,
  prompt_key VARCHAR(64) NOT NULL,
  scene VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description VARCHAR(1000) NOT NULL DEFAULT '',
  system_prompt TEXT NOT NULL,
  user_prompt TEXT NOT NULL,
  version_no INTEGER NOT NULL DEFAULT 1,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  test_status VARCHAR(32) NOT NULL DEFAULT 'untested',
  test_result JSON NOT NULL,
  operator_id BIGINT,
  operator_name VARCHAR(64) NOT NULL DEFAULT '',
  published_at TIMESTAMP,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_pipeline_prompt_key_version UNIQUE (prompt_key, version_no),
  CONSTRAINT ck_pipeline_prompt_status CHECK (status IN ('draft', 'published', 'retired')),
  CONSTRAINT ck_pipeline_prompt_test_status CHECK (test_status IN ('untested', 'passed', 'failed')),
  CONSTRAINT ck_pipeline_prompt_version_no CHECK (version_no >= 1),
  CONSTRAINT fk_pipeline_prompt_operator FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pipeline_prompt_scene_status ON pipeline_prompt_versions(scene, status);
CREATE INDEX IF NOT EXISTS idx_pipeline_prompt_key_time ON pipeline_prompt_versions(prompt_key, update_time);

CREATE INDEX IF NOT EXISTS idx_collection_runs_handoff_status_time ON collection_runs(handoff_status, create_time);
CREATE INDEX IF NOT EXISTS idx_news_articles_handoff_status_time ON news_articles(handoff_status, update_time);
CREATE INDEX IF NOT EXISTS idx_papers_handoff_status_time ON papers(handoff_status, update_time);

CREATE TABLE IF NOT EXISTS pipeline_content_review_events (
  event_id VARCHAR(64) PRIMARY KEY,
  content_type VARCHAR(16) NOT NULL,
  content_id VARCHAR(64) NOT NULL,
  from_status VARCHAR(32),
  to_status VARCHAR(32) NOT NULL,
  action VARCHAR(32) NOT NULL,
  reason TEXT,
  operator_id BIGINT,
  operator_name VARCHAR(64) NOT NULL DEFAULT '',
  snapshot_json JSON NOT NULL DEFAULT '{}'::json,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ck_pipeline_review_event_content_type CHECK (content_type IN ('article', 'paper')),
  CONSTRAINT ck_pipeline_review_event_action CHECK (action IN ('approve', 'reject', 'withdraw', 'reprocess')),
  CONSTRAINT fk_pipeline_review_event_operator FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pipeline_review_event_content_time
  ON pipeline_content_review_events(content_type, content_id, create_time);
CREATE INDEX IF NOT EXISTS idx_pipeline_review_event_operator_time
  ON pipeline_content_review_events(operator_id, create_time);

CREATE TABLE IF NOT EXISTS pipeline_quality_issues (
  issue_id VARCHAR(64) PRIMARY KEY,
  content_type VARCHAR(16) NOT NULL,
  content_id VARCHAR(64) NOT NULL,
  issue_code VARCHAR(32) NOT NULL,
  severity VARCHAR(16) NOT NULL DEFAULT 'warning',
  evidence JSON NOT NULL DEFAULT '{}'::json,
  description TEXT NOT NULL,
  suggestion TEXT NOT NULL DEFAULT '',
  status VARCHAR(16) NOT NULL DEFAULT 'open',
  resolution TEXT,
  operator_id BIGINT,
  operator_name VARCHAR(64) NOT NULL DEFAULT '',
  first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at TIMESTAMP,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_pipeline_quality_issue_content_code UNIQUE (content_type, content_id, issue_code),
  CONSTRAINT ck_pipeline_quality_issue_content_type CHECK (content_type IN ('article', 'paper')),
  CONSTRAINT ck_pipeline_quality_issue_code CHECK (issue_code IN ('duplicate', 'missing', 'tag', 'parse', 'review')),
  CONSTRAINT ck_pipeline_quality_issue_severity CHECK (severity IN ('error', 'warning', 'info')),
  CONSTRAINT ck_pipeline_quality_issue_status CHECK (status IN ('open', 'resolved', 'ignored')),
  CONSTRAINT fk_pipeline_quality_issue_operator FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pipeline_quality_issue_status_time
  ON pipeline_quality_issues(status, update_time);
CREATE INDEX IF NOT EXISTS idx_pipeline_quality_issue_content
  ON pipeline_quality_issues(content_type, content_id, status);

CREATE TABLE IF NOT EXISTS pipeline_quality_issue_events (
  event_id VARCHAR(64) PRIMARY KEY,
  issue_id VARCHAR(64) NOT NULL,
  from_status VARCHAR(16),
  to_status VARCHAR(16) NOT NULL,
  action VARCHAR(16) NOT NULL,
  reason TEXT NOT NULL,
  operator_id BIGINT,
  operator_name VARCHAR(64) NOT NULL DEFAULT '',
  snapshot_json JSON NOT NULL DEFAULT '{}'::json,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ck_pipeline_quality_issue_event_action CHECK (action IN ('resolve', 'ignore', 'reopen')),
  CONSTRAINT ck_pipeline_quality_issue_event_to_status CHECK (to_status IN ('open', 'resolved', 'ignored')),
  CONSTRAINT fk_pipeline_quality_issue_event_issue FOREIGN KEY (issue_id) REFERENCES pipeline_quality_issues(issue_id) ON DELETE CASCADE,
  CONSTRAINT fk_pipeline_quality_issue_event_operator FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pipeline_quality_issue_event_issue_time
  ON pipeline_quality_issue_events(issue_id, create_time);
CREATE INDEX IF NOT EXISTS idx_pipeline_quality_issue_event_operator_time
  ON pipeline_quality_issue_events(operator_id, create_time);

CREATE TABLE IF NOT EXISTS pipeline_duplicate_groups (
  group_id VARCHAR(64) PRIMARY KEY,
  content_type VARCHAR(16) NOT NULL,
  group_key VARCHAR(255) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'candidate',
  master_content_id VARCHAR(64),
  similarity DOUBLE PRECISION,
  decision_reason TEXT,
  operator_id BIGINT,
  operator_name VARCHAR(64) NOT NULL DEFAULT '',
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_pipeline_duplicate_group_key UNIQUE (content_type, group_key),
  CONSTRAINT ck_pipeline_duplicate_group_content_type CHECK (content_type IN ('article', 'paper')),
  CONSTRAINT ck_pipeline_duplicate_group_status CHECK (status IN ('candidate', 'merged', 'split', 'dismissed')),
  CONSTRAINT ck_pipeline_duplicate_group_similarity CHECK (similarity IS NULL OR similarity BETWEEN 0 AND 1),
  CONSTRAINT fk_pipeline_duplicate_group_operator FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pipeline_duplicate_group_status_time
  ON pipeline_duplicate_groups(status, update_time);

CREATE TABLE IF NOT EXISTS pipeline_duplicate_members (
  member_id BIGSERIAL PRIMARY KEY,
  group_id VARCHAR(64) NOT NULL,
  content_type VARCHAR(16) NOT NULL,
  content_id VARCHAR(64) NOT NULL,
  relation_type VARCHAR(16) NOT NULL DEFAULT 'candidate',
  similarity DOUBLE PRECISION,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_pipeline_duplicate_member_content UNIQUE (group_id, content_type, content_id),
  CONSTRAINT ck_pipeline_duplicate_member_content_type CHECK (content_type IN ('article', 'paper')),
  CONSTRAINT ck_pipeline_duplicate_member_relation_type CHECK (relation_type IN ('candidate', 'master', 'duplicate')),
  CONSTRAINT ck_pipeline_duplicate_member_similarity CHECK (similarity IS NULL OR similarity BETWEEN 0 AND 1),
  CONSTRAINT fk_pipeline_duplicate_member_group FOREIGN KEY (group_id) REFERENCES pipeline_duplicate_groups(group_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_pipeline_duplicate_member_content
  ON pipeline_duplicate_members(content_type, content_id);

CREATE TABLE IF NOT EXISTS pipeline_duplicate_group_events (
  event_id VARCHAR(64) PRIMARY KEY,
  group_id VARCHAR(64) NOT NULL,
  from_status VARCHAR(16),
  to_status VARCHAR(16) NOT NULL,
  action VARCHAR(16) NOT NULL,
  master_content_id VARCHAR(64),
  reason TEXT NOT NULL,
  operator_id BIGINT,
  operator_name VARCHAR(64) NOT NULL DEFAULT '',
  snapshot_json JSON NOT NULL DEFAULT '{}'::json,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ck_pipeline_duplicate_event_action CHECK (action IN ('merge', 'split', 'dismiss', 'reopen')),
  CONSTRAINT ck_pipeline_duplicate_event_to_status CHECK (to_status IN ('candidate', 'merged', 'split', 'dismissed')),
  CONSTRAINT fk_pipeline_duplicate_event_group FOREIGN KEY (group_id) REFERENCES pipeline_duplicate_groups(group_id) ON DELETE CASCADE,
  CONSTRAINT fk_pipeline_duplicate_event_operator FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pipeline_duplicate_event_group_time
  ON pipeline_duplicate_group_events(group_id, create_time);
CREATE INDEX IF NOT EXISTS idx_pipeline_duplicate_event_operator_time
  ON pipeline_duplicate_group_events(operator_id, create_time);

CREATE TABLE IF NOT EXISTS pipeline_model_routes (
  route_id VARCHAR(64) PRIMARY KEY,
  scene VARCHAR(32) NOT NULL,
  primary_model_id BIGINT,
  fallback_model_id BIGINT,
  timeout_seconds INTEGER NOT NULL DEFAULT 30,
  max_tokens INTEGER NOT NULL DEFAULT 2048,
  temperature DOUBLE PRECISION NOT NULL DEFAULT 0.2,
  daily_limit INTEGER NOT NULL DEFAULT 0,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  version_no INTEGER NOT NULL DEFAULT 1,
  operator_id BIGINT,
  operator_name VARCHAR(64) NOT NULL DEFAULT '',
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_pipeline_model_routes_scene UNIQUE (scene),
  CONSTRAINT ck_pipeline_model_routes_scene CHECK (scene IN ('research', 'digest', 'data-filter')),
  CONSTRAINT ck_pipeline_model_routes_timeout CHECK (timeout_seconds BETWEEN 1 AND 120),
  CONSTRAINT ck_pipeline_model_routes_max_tokens CHECK (max_tokens BETWEEN 1 AND 32768),
  CONSTRAINT ck_pipeline_model_routes_temperature CHECK (temperature BETWEEN 0 AND 2),
  CONSTRAINT ck_pipeline_model_routes_daily_limit CHECK (daily_limit >= 0),
  CONSTRAINT ck_pipeline_model_routes_version CHECK (version_no >= 1),
  CONSTRAINT fk_pipeline_route_primary_model FOREIGN KEY (primary_model_id) REFERENCES ai_models(model_id) ON DELETE RESTRICT,
  CONSTRAINT fk_pipeline_route_fallback_model FOREIGN KEY (fallback_model_id) REFERENCES ai_models(model_id) ON DELETE RESTRICT,
  CONSTRAINT fk_pipeline_route_operator FOREIGN KEY (operator_id) REFERENCES sys_user(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pipeline_model_routes_enabled
  ON pipeline_model_routes(enabled, scene);

CREATE TABLE IF NOT EXISTS pipeline_model_route_usage (
  route_id VARCHAR(64) NOT NULL,
  usage_date TIMESTAMP NOT NULL,
  call_count INTEGER NOT NULL DEFAULT 0,
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (route_id, usage_date),
  CONSTRAINT ck_pipeline_model_route_usage_count CHECK (call_count >= 0),
  CONSTRAINT fk_pipeline_model_route_usage_route FOREIGN KEY (route_id)
    REFERENCES pipeline_model_routes(route_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_pipeline_model_route_usage_date
  ON pipeline_model_route_usage(usage_date);

CREATE TABLE IF NOT EXISTS pipeline_model_call_audits (
  call_id VARCHAR(64) PRIMARY KEY,
  task_id VARCHAR(64),
  user_id BIGINT,
  scene VARCHAR(32) NOT NULL,
  route_id VARCHAR(64),
  route_version_no INTEGER,
  prompt_version_id VARCHAR(64),
  template_version_id VARCHAR(64),
  model_id BIGINT,
  model_code VARCHAR(100),
  provider VARCHAR(50),
  attempt_no INTEGER NOT NULL DEFAULT 0,
  fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
  status VARCHAR(20) NOT NULL,
  latency_ms INTEGER,
  input_char_count INTEGER NOT NULL DEFAULT 0,
  output_char_count INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER,
  output_tokens INTEGER,
  error_code VARCHAR(64),
  error_message VARCHAR(1000),
  create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ck_pipeline_model_call_audit_status CHECK (status IN ('success', 'failed', 'limit_exceeded')),
  CONSTRAINT ck_pipeline_model_call_audit_attempt CHECK (attempt_no >= 0),
  CONSTRAINT ck_pipeline_model_call_audit_latency CHECK (latency_ms IS NULL OR latency_ms >= 0),
  CONSTRAINT fk_pipeline_model_call_audit_user FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE SET NULL,
  CONSTRAINT fk_pipeline_model_call_audit_route FOREIGN KEY (route_id) REFERENCES pipeline_model_routes(route_id) ON DELETE SET NULL,
  CONSTRAINT fk_pipeline_model_call_audit_model FOREIGN KEY (model_id) REFERENCES ai_models(model_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pipeline_model_call_audit_scene_time
  ON pipeline_model_call_audits(scene, create_time);
CREATE INDEX IF NOT EXISTS idx_pipeline_model_call_audit_status_time
  ON pipeline_model_call_audits(status, create_time);
CREATE INDEX IF NOT EXISTS idx_pipeline_model_call_audit_task_time
  ON pipeline_model_call_audits(task_id, create_time);

-- 统一检索使用与 DAO 拼接表达式一致的 trigram 索引，保留 ILIKE 语义；中文分词索引另行建设。
CREATE INDEX IF NOT EXISTS idx_news_articles_search_trgm
  ON news_articles USING gin ((coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(body, '')) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_papers_search_trgm
  ON papers USING gin ((coalesce(title, '') || ' ' || coalesce(abstract_text, '') || ' ' || coalesce(authors, '')) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_knowledge_files_search_trgm
  ON knowledge_files USING gin ((coalesce(name, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(extracted_text, '')) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_reports_search_trgm
  ON reports USING gin ((coalesce(title, '') || ' ' || coalesce(content, '') || ' ' || coalesce(report_type, '')) gin_trgm_ops);

-- 中文/英文统一使用 UTF-8 编码后的辅助索引；查询同时保留原文 ILIKE，避免编码边界产生误匹配。
CREATE INDEX IF NOT EXISTS idx_news_articles_search_utf8_trgm
  ON news_articles USING gin ((pipeline_utf8_hex(lower(coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(body, '')))) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_papers_search_utf8_trgm
  ON papers USING gin ((pipeline_utf8_hex(lower(coalesce(title, '') || ' ' || coalesce(abstract_text, '') || ' ' || coalesce(authors, '')))) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_knowledge_files_search_utf8_trgm
  ON knowledge_files USING gin ((pipeline_utf8_hex(lower(coalesce(name, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(extracted_text, '')))) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_reports_search_utf8_trgm
  ON reports USING gin ((pipeline_utf8_hex(lower(coalesce(title, '') || ' ' || coalesce(content, '') || ' ' || coalesce(report_type, '')))) gin_trgm_ops);
