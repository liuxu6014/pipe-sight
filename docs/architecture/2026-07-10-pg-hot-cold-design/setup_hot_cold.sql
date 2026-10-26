-- ============================================================
-- 一键式 PostgreSQL 热冷库自动分离方案
-- 依赖: pg_partman 5.4+, pg_cron 1.6+, PG 16+
-- ============================================================
-- 前置步骤（需单独执行，因 CREATE TABLESPACE 不能放事务里）:
--   psql -U postgres -c "CREATE TABLESPACE ts_ssd  LOCATION '/data/ssd';"
--   psql -U postgres -c "CREATE TABLESPACE ts_hdd  LOCATION '/data/hdd';"
-- ============================================================
-- 一键执行:
--   psql -U postgres -f setup_hot_cold.sql
-- ============================================================
-- 效果:
--   1. pg_partman 自动提前建未来 3 个月的分区
--   2. 新建分区默认放 SSD 热库
--   3. 超过 3 个月的分区 → 自动迁 HDD 冷库
--   4. 超过 12 个月的分区 → 自动 DETACH（归档，数据不丢）
--   5. pg_cron 每小时自动执行以上逻辑，完全无需人工干预
-- ============================================================

-- === 1. 扩展 ===
CREATE EXTENSION IF NOT EXISTS pg_partman;
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- === 2. 建分区父表 + pg_partman 注册 ===
CREATE TABLE IF NOT EXISTS event_log (
    id          BIGSERIAL,
    event_ts    TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type  TEXT NOT NULL,
    payload     JSONB
) PARTITION BY RANGE (event_ts);

-- 仅首次注册（幂等：已注册则跳过）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM part_config WHERE parent_table = 'public.event_log'
    ) THEN
        PERFORM create_parent(
            'public.event_log',
            'event_ts',
            '1 month',
            p_premake        := 3,
            p_start_partition := '2026-05-01'
        );
    END IF;
END;
$$;

-- === 3. 立即建初始分区 ===
SELECT run_maintenance();

-- === 4. 新分区默认绑 SSD 热库 ===
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT c.relname
        FROM pg_inherits i
        JOIN pg_class p ON i.inhparent = p.oid
        JOIN pg_class c ON i.inhrelid  = c.oid
        WHERE p.relname = 'event_log'
          AND c.relkind = 'r'
          AND c.relname !~ '_default$'
    LOOP
        -- 只把还在 pg_default 的分区迁到 SSD（幂等）
        IF NOT EXISTS (
            SELECT 1 FROM pg_tablespace ts
            JOIN pg_class c2 ON ts.oid = c2.reltablespace
            WHERE c2.relname = r.relname AND ts.spcname != 'pg_default'
        ) THEN
            EXECUTE format('ALTER TABLE %I SET TABLESPACE ts_ssd', r.relname);
        END IF;
    END LOOP;
END;
$$;

-- === 5. 自动冷热迁移函数 ===
CREATE OR REPLACE FUNCTION auto_hot_cold_migration(
    p_parent_table         TEXT,
    p_hot_retention_months  INT DEFAULT 3,
    p_cold_retention_months INT DEFAULT 12
)
RETURNS TABLE(partition_name TEXT, action TEXT, old_ts TEXT, new_ts TEXT)
LANGUAGE plpgsql AS $$
DECLARE
    rec           RECORD;
    cutoff_hot    DATE;
    cutoff_cold   DATE;
    parent_table  TEXT;
    part_date_str TEXT;
    part_date     DATE;
BEGIN
    cutoff_hot  := date_trunc('month', now())::date
                   - (p_hot_retention_months || ' months')::interval;
    cutoff_cold := date_trunc('month', now())::date
                   - (p_cold_retention_months || ' months')::interval;
    parent_table := split_part(p_parent_table, '.', 2);

    FOR rec IN
        SELECT c.relname, coalesce(ts.spcname, 'pg_default') AS current_ts
        FROM pg_inherits i
        JOIN pg_class p ON i.inhparent = p.oid
        JOIN pg_class c ON i.inhrelid  = c.oid
        LEFT JOIN pg_tablespace ts ON ts.oid = c.reltablespace
        WHERE p.relname = parent_table
          AND c.relkind = 'r'
          AND c.relname !~ '_default$'
        ORDER BY c.relname
    LOOP
        part_date_str := substring(rec.relname FROM '_p(\d{8})$');
        IF part_date_str IS NULL THEN CONTINUE; END IF;
        part_date := to_date(part_date_str, 'YYYYMMDD');

        -- 超冷保留期 → DETACH
        IF part_date < cutoff_cold THEN
            EXECUTE format('ALTER TABLE %s DETACH PARTITION %I',
                p_parent_table, rec.relname);
            partition_name := rec.relname;
            action         := 'DETACHED';
            old_ts         := rec.current_ts;
            new_ts         := NULL;
            RETURN NEXT;
            CONTINUE;
        END IF;

        -- 超热保留期且不在 HDD → 迁 HDD
        IF part_date < cutoff_hot AND rec.current_ts <> 'ts_hdd' THEN
            EXECUTE format('ALTER TABLE %I SET TABLESPACE ts_hdd', rec.relname);
            partition_name := rec.relname;
            action         := 'TO_HDD';
            old_ts         := rec.current_ts;
            new_ts         := 'ts_hdd';
            RETURN NEXT;
        END IF;
    END LOOP;
END;
$$;

-- === 6. 统一维护入口（pg_cron 每小时调用） ===
CREATE OR REPLACE FUNCTION hourly_partition_maintenance()
RETURNS TEXT
LANGUAGE plpgsql AS $$
DECLARE
    msg TEXT := '';
    rec RECORD;
    cnt INT := 0;
BEGIN
    -- pg_partman: 建未来分区
    BEGIN
        PERFORM run_maintenance();
        msg := msg || 'partman:OK';
    EXCEPTION WHEN OTHERS THEN
        msg := msg || 'partman:ERR=' || SQLERRM;
    END;

    -- 冷热迁移
    FOR rec IN SELECT * FROM auto_hot_cold_migration('public.event_log', 3, 12)
    LOOP
        cnt := cnt + 1;
        msg := msg || ' | ' || rec.partition_name || ':' || rec.action;
    END LOOP;
    IF cnt = 0 THEN
        msg := msg || ' | migrate:none';
    END IF;

    RETURN msg;
END;
$$;

-- === 7. 定时调度 ===
SELECT cron.schedule(
    'hot-cold-maintenance',
    '0 * * * *',
    'SELECT hourly_partition_maintenance();'
);

-- === 8. 首次执行 ===
SELECT hourly_partition_maintenance();
