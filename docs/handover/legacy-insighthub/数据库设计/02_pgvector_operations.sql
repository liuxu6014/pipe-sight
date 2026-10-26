-- pipeline_news.news pgvector 写入、检索和校验契约
-- PostgreSQL 参数使用 $1...$N 表示，由应用驱动绑定。
-- embedding_version=1 的精确输入：
--   标题: {ai_title 非空时取 ai_title，否则取 title} 摘要: {abstract}
-- source_hash：上述 UTF-8 输入文本的 SHA-256 小写十六进制。

-- 1. 生成向量前检查是否需要重建。
SELECT source_hash, embedding_model, embedding_version
FROM news.news_embedding
WHERE news_id = $1
  AND news_create_time = $2;

-- 2. 首次写入或向量重建后的完整 UPSERT。
INSERT INTO news.news_embedding (
    news_id,
    news_create_time,
    uuid,
    embedding,
    embedding_model,
    embedding_version,
    source_hash,
    domain_id,
    category_id,
    published_at,
    key_words,
    title,
    ai_title,
    source,
    domain,
    external_link,
    cover_image_url,
    producer
) VALUES (
    $1, $2, $3, $4::news.vector, $5, $6, $7, $8, $9,
    $10, $11, $12, $13, $14, $15, $16, $17, $18
)
ON CONFLICT (news_id, news_create_time) DO UPDATE SET
    uuid = EXCLUDED.uuid,
    embedding = EXCLUDED.embedding,
    embedding_model = EXCLUDED.embedding_model,
    embedding_version = EXCLUDED.embedding_version,
    source_hash = EXCLUDED.source_hash,
    domain_id = EXCLUDED.domain_id,
    category_id = EXCLUDED.category_id,
    published_at = EXCLUDED.published_at,
    key_words = EXCLUDED.key_words,
    title = EXCLUDED.title,
    ai_title = EXCLUDED.ai_title,
    source = EXCLUDED.source,
    domain = EXCLUDED.domain,
    external_link = EXCLUDED.external_link,
    cover_image_url = EXCLUDED.cover_image_url,
    producer = EXCLUDED.producer;

-- 3. 向量输入未变化时，仅同步过滤投影和检索快照。
UPDATE news.news_embedding
SET
    uuid = $3,
    domain_id = $4,
    category_id = $5,
    published_at = $6,
    key_words = $7,
    title = $8,
    ai_title = $9,
    source = $10,
    domain = $11,
    external_link = $12,
    cover_image_url = $13,
    producer = $14
WHERE news_id = $1
  AND news_create_time = $2;

-- 4. 近邻检索示例：限定领域和起始发布时间。
-- 应用应按实际过滤条件生成 SQL，不使用“参数为空 OR”统一模板。
SELECT
    news_id,
    news_create_time,
    uuid,
    key_words,
    title,
    ai_title,
    source,
    domain,
    external_link,
    cover_image_url,
    producer,
    domain_id,
    category_id,
    published_at,
    embedding <=> $1::news.vector AS distance
FROM news.news_embedding
WHERE domain_id = $2
  AND published_at >= $3
  AND EXISTS (
      SELECT 1
      FROM news.hp_news n
      WHERE n.news_id = news.news_embedding.news_id
        AND n.create_time = news.news_embedding.news_create_time
        AND n.del_flag = '0'
  )
ORDER BY embedding <=> $1::news.vector
LIMIT $4;

-- 5. 删除分区新闻对应的向量行。
-- 正常情况下删除 news.hp_news 后同库外键会自动级联；该语句用于显式修复。
DELETE FROM news.news_embedding
WHERE news_id = $1
  AND news_create_time = $2;

-- 6. PostgreSQL 本地结构/数据质量检查。
SELECT e.extversion, n.nspname AS extension_schema
FROM pg_extension e
JOIN pg_namespace n ON n.oid = e.extnamespace
WHERE e.extname = 'vector';

SELECT
    COUNT(*) AS total_embeddings,
    COUNT(*) FILTER (WHERE domain_id IS NULL) AS missing_domain_id,
    COUNT(*) FILTER (WHERE category_id IS NULL) AS missing_category_id,
    COUNT(*) FILTER (WHERE published_at IS NULL) AS missing_published_at,
    COUNT(*) FILTER (WHERE btrim(uuid) = '') AS blank_uuid,
    COUNT(*) FILTER (WHERE btrim(title) = '') AS blank_title,
    min(news.vector_dims(embedding)) AS min_vector_dims,
    max(news.vector_dims(embedding)) AS max_vector_dims
FROM news.news_embedding;

SELECT embedding_model, embedding_version, COUNT(*) AS row_count
FROM news.news_embedding
GROUP BY embedding_model, embedding_version
ORDER BY embedding_model, embedding_version;

-- 7. 同库外键已经阻止孤儿向量；仍需检查快照和 source_hash 漂移。
SELECT
    e.news_id,
    e.news_create_time,
    e.uuid AS embedding_uuid,
    n.uuid AS news_uuid,
    e.domain_id AS embedding_domain_id,
    n.domain_id AS news_domain_id,
    e.category_id AS embedding_category_id,
    n.classify AS news_category_id,
    e.published_at AS embedding_published_at,
    n.publish_time AS news_published_at
FROM news.news_embedding e
JOIN news.hp_news n
  ON n.news_id = e.news_id
 AND n.create_time = e.news_create_time
WHERE e.uuid IS DISTINCT FROM n.uuid
   OR e.domain_id IS DISTINCT FROM n.domain_id
   OR e.category_id IS DISTINCT FROM n.classify
   OR e.published_at IS DISTINCT FROM n.publish_time;
