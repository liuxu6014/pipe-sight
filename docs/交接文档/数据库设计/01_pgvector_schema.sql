-- 已废弃的早期 pgvector 设计草案。
-- 不得执行：真实 pipeline_news.news 结构以 04_pipeline_news_pg_migration.sql 为准。
-- 保留本文件仅用于设计演进对照。

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS news_embedding (
    news_id            bigint PRIMARY KEY,
    uuid               varchar(255) NOT NULL,
    embedding          vector(1024) NOT NULL,
    embedding_model    text NOT NULL,
    embedding_version  integer NOT NULL DEFAULT 1,
    source_hash        char(64) NOT NULL,
    domain_id          bigint,
    category_id        bigint,
    published_at       timestamp without time zone,
    key_words          text NOT NULL DEFAULT '',
    title              varchar(512) NOT NULL,
    ai_title           text NOT NULL DEFAULT '',
    source             varchar(255),
    domain             varchar(255),
    external_link      varchar(4096),
    cover_image_url    varchar(4096),
    producer           varchar(100) NOT NULL DEFAULT 'insight_hub',
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT ck_news_embedding_uuid_not_blank
        CHECK (btrim(uuid) <> ''),
    CONSTRAINT ck_news_embedding_title_not_blank
        CHECK (btrim(title) <> ''),
    CONSTRAINT ck_news_embedding_model_not_blank
        CHECK (btrim(embedding_model) <> ''),
    CONSTRAINT ck_news_embedding_version_positive
        CHECK (embedding_version > 0),
    CONSTRAINT ck_news_embedding_source_hash_sha256
        CHECK (source_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_news_embedding_producer_not_blank
        CHECK (btrim(producer) <> '')
);

CREATE OR REPLACE FUNCTION set_news_embedding_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_news_embedding_updated_at ON news_embedding;
CREATE TRIGGER trg_news_embedding_updated_at
BEFORE UPDATE ON news_embedding
FOR EACH ROW
EXECUTE FUNCTION set_news_embedding_updated_at();

CREATE INDEX IF NOT EXISTS idx_news_embedding_uuid
    ON news_embedding (uuid);

CREATE INDEX IF NOT EXISTS idx_news_embedding_hnsw_cosine
    ON news_embedding
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_news_embedding_domain_published
    ON news_embedding (domain_id, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_embedding_domain_category_published
    ON news_embedding (domain_id, category_id, published_at DESC);

COMMIT;
