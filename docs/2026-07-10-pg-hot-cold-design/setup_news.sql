-- ============================================================
-- 一键式新闻表热冷库自动分离（生产加固版）
-- 设计目标：3 年无人值守，近期新闻毫秒级响应
-- ============================================================
-- 前置：
--   psql -c "CREATE TABLESPACE ts_ssd LOCATION '/data/ssd';"
--   psql -c "CREATE TABLESPACE ts_hdd LOCATION '/data/hdd';"
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_partman;
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- ============================================================
-- 1. 新闻表（高频字段提列，不用 JSONB 藏）
-- ============================================================
CREATE TABLE IF NOT EXISTS news (
    id          BIGSERIAL,
    publish_ts  TIMESTAMPTZ NOT NULL DEFAULT now(),  -- 分区键
    title       TEXT NOT NULL,
    summary     TEXT,
    content     TEXT,
    author_id   BIGINT,
    category    TEXT NOT NULL DEFAULT 'general',      -- 提列！不用 JSONB
    news_type   TEXT NOT NULL DEFAULT 'article',      -- breaking/feature/opinion/daily
    source_url  TEXT,
    tags        TEXT[],
    extra       JSONB,                                -- 只放低频字段
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (publish_ts);

-- ============================================================
-- 1b. 向量表（不分区，与 news 通过 news_id 关联）
-- 依赖: CREATE EXTENSION IF NOT EXISTS vector;
-- ============================================================
CREATE TABLE IF NOT EXISTS news_vectors (
    news_id     BIGINT NOT NULL,
    embedding   vector(1536),       -- 维度按实际模型调整
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 向量索引（IVFFlat，适合百万~千万级；更大数据量用 HNSW）
-- CREATE INDEX idx_news_vectors_ivf ON news_vectors
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 1000);
-- ============================================================
-- 2. 核心索引（建在父表，分区自动继承）
-- ============================================================
-- 主打索引：按时间 + 新闻类型查
CREATE INDEX idx_news_type_ts    ON news (news_type, publish_ts DESC);
-- 按分类 + 时间
CREATE INDEX idx_news_cat_ts     ON news (category, publish_ts DESC);
-- 按作者 + 时间
CREATE INDEX idx_news_author_ts  ON news (author_id, publish_ts DESC);
-- 全局唯一（含分区键）
CREATE UNIQUE INDEX idx_news_id_ts ON news (id, publish_ts);
-- 全文搜索（按标题）
CREATE INDEX idx_news_title_gin  ON news USING gin (to_tsvector('english', title));
-- 标签数组
CREATE INDEX idx_news_tags_gin   ON news USING gin (tags);
-- JSONB 低频字段
CREATE INDEX idx_news_extra_gin  ON news USING gin (extra);

-- ============================================================
-- 3. pg_partman 注册
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM part_config WHERE parent_table = 'public.news') THEN
        PERFORM create_parent(
            'public.news',
            'publish_ts',
            '1 month',
            p_premake        := 3,
            p_start_partition := '2026-05-01'
        );
    END IF;
END;
$$;

-- 立即建初始分区
SELECT run_maintenance();

-- ============================================================
-- 4. 初始分区绑 SSD
-- ============================================================
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT c.relname FROM pg_inherits i
        JOIN pg_class p ON i.inhparent = p.oid
        JOIN pg_class c ON i.inhrelid  = c.oid
        WHERE p.relname = 'news' AND c.relkind = 'r'
          AND c.relname !~ '_default$'
    LOOP
        EXECUTE format('ALTER TABLE %I SET TABLESPACE ts_ssd', r.relname);
    END LOOP;
END;
$$;

-- ============================================================
-- 5. 核心：冷热迁移（DETACH = 永久归档，不删除）
-- ============================================================
CREATE OR REPLACE FUNCTION auto_news_migration(
    p_hot_months  INT DEFAULT 3,    -- 3 个月 → 迁 HDD
    p_cold_months INT DEFAULT 13    -- 13 个月 → DETACH 归档（独立表永久保留）
)
RETURNS TABLE(op TEXT, target TEXT, detail TEXT)
LANGUAGE plpgsql AS $$
DECLARE
    rec           RECORD;
    cutoff_hot    DATE;
    cutoff_cold   DATE;
    part_date_str TEXT;
    part_date     DATE;
BEGIN
    cutoff_hot  := date_trunc('month', now())::date
                   - (p_hot_months || ' months')::interval;
    cutoff_cold := date_trunc('month', now())::date
                   - (p_cold_months || ' months')::interval;
    -- A. 处理挂载的分区：迁冷 / DETACH
    FOR rec IN
        SELECT c.relname, coalesce(ts.spcname, 'pg_default') AS current_ts
        FROM pg_inherits i
        JOIN pg_class p ON i.inhparent = p.oid
        JOIN pg_class c ON i.inhrelid  = c.oid
        LEFT JOIN pg_tablespace ts ON ts.oid = c.reltablespace
        WHERE p.relname = 'news' AND c.relkind = 'r'
          AND c.relname !~ '_default$'
        ORDER BY c.relname
    LOOP
        part_date_str := substring(rec.relname FROM '_p(\d{8})$');
        IF part_date_str IS NULL THEN CONTINUE; END IF;
        part_date := to_date(part_date_str, 'YYYYMMDD');

        IF part_date < cutoff_cold THEN
            EXECUTE format('ALTER TABLE public.news DETACH PARTITION %I', rec.relname);
            op := 'DETACH'; target := rec.relname; detail := 'archived permanently';
            RETURN NEXT;
            CONTINUE;
        END IF;

        IF part_date < cutoff_hot AND rec.current_ts <> 'ts_hdd' THEN
            EXECUTE format('ALTER TABLE %I SET TABLESPACE ts_hdd', rec.relname);
            op := 'TO_HDD'; target := rec.relname; detail := rec.current_ts || ' -> ts_hdd';
            RETURN NEXT;
        END IF;
    END LOOP;

    END;
$$;

-- ============================================================
-- 6. 健康检查表（监控 pg_cron 是否还活着）
-- ============================================================
CREATE TABLE IF NOT EXISTS partition_health (
    check_ts    TIMESTAMPTZ NOT NULL DEFAULT now(),
    status      TEXT,
    detail      TEXT
);

-- ============================================================
-- 7. 统一维护入口
-- ============================================================
CREATE OR REPLACE FUNCTION hourly_news_maintenance()
RETURNS TEXT
LANGUAGE plpgsql AS $$
DECLARE
    msg TEXT := '';
    rec RECORD;
    cnt INT := 0;
    latest_partition TEXT;
BEGIN
    -- A. pg_partman 建新分区
    BEGIN
        PERFORM run_maintenance();
        msg := msg || 'partman:OK';
    EXCEPTION WHEN OTHERS THEN
        msg := msg || 'partman:ERR=' || SQLERRM;
        INSERT INTO partition_health (status, detail)
        VALUES ('ERROR', 'partman: ' || SQLERRM);
        RETURN msg;
    END;

    -- B. 冷热迁移 + DETACH 归档
    FOR rec IN SELECT * FROM auto_news_migration(3, 13) LOOP
        cnt := cnt + 1;
        msg := msg || ' | ' || rec.target || ':' || rec.op;
    END LOOP;

    -- C. 查最新分区
    SELECT c.relname INTO latest_partition
    FROM pg_inherits i
    JOIN pg_class p ON i.inhparent = p.oid
    JOIN pg_class c ON i.inhrelid  = c.oid
    WHERE p.relname = 'news' AND c.relkind = 'r' AND c.relname !~ '_default$'
    ORDER BY c.relname DESC LIMIT 1;

    -- D. 写健康记录
    INSERT INTO partition_health (status, detail)
    VALUES ('OK', format('latest_part=%s, ops=%s, migrated=%s',
        latest_partition, cnt, msg));

    RETURN msg;
END;
$$;

-- ============================================================
-- 8. pg_cron 定时调度
-- ============================================================
SELECT cron.schedule(
    'news-maintenance',
    '0 * * * *',
    'SELECT hourly_news_maintenance();'
);

-- 立即跑一次
SELECT hourly_news_maintenance();
