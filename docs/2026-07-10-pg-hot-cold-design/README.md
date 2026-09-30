# PostgreSQL 热冷库自动分区设计方案

> 调研日期：2026-07-10  
> 环境：PostgreSQL 16 (Docker) + pg_partman 5.4 + pg_cron 1.6

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `setup_hot_cold.sql` | 通用冷热分区方案（任意表） |
| `setup_news.sql` | **生产加固版** — 新闻表专用，3 年无人值守 |

---

## 两种方案

### 方案一：同实例声明式分区 + 表空间（`setup_hot_cold.sql`）

- `PARTITION BY RANGE` 按月分片
- 热分区 → `ts_ssd`，冷分区 → `ts_hdd`
- 分区裁剪自动跳过无关分区
- `ALTER TABLE ... SET TABLESPACE` 在线迁数据

### 方案二：跨实例 FDW + 外部分区

- 冷库独立 PG 实例
- `postgres_fdw` 挂载为外部表分区
- WHERE 条件下推到远端
- 冷库可独立备份、降配

---

## 新闻表生产方案-用的第一种（`setup_news.sql`）

### 自动化策略

```
pg_cron 每小时整点
  → hourly_news_maintenance()
    ├── run_maintenance()              → 自动建未来 3 个月分区
    ├── auto_news_migration(3,13)      → 迁冷 / DETACH 归档（永久保留）
    └── INSERT partition_health        → 健康记录
```

### 生命周期

| 周期 | 操作 | 数据状态 |
|------|------|---------|
| 0~3 月 | 保持 `ts_ssd` | 热库，毫秒级查询 |
| 3~13 月 | `ALTER TABLE SET TABLESPACE ts_hdd` | 冷库，低成本存储 |
| >13 月 | `DETACH PARTITION` | 独立归档表，永久保留 |


### 性能实测

| 查询场景 | 耗时 | 策略 |
|---------|------|------|
| 最近 3 天 breaking 新闻（5 万行热分区） | **0.15ms** | Index Scan + 分区裁剪 |
| 跨 6 个月统计 | 正常 | Append 混合扫描 |
| 无时间范围全表查 | ⚠️ 退化 | 扫全部 36+ 分区（3 年后） |

### 应用层约定

**查 news 表必须带 `publish_ts` 范围。** 这是唯一红线。

```sql
-- ✅ 正确
SELECT * FROM news
WHERE publish_ts >= now() - interval '7 days'
  AND news_type = 'breaking'
ORDER BY publish_ts DESC LIMIT 20;

-- ❌ 禁止（3 年后扫 36 分区）
SELECT * FROM news
WHERE news_type = 'breaking'
ORDER BY publish_ts DESC LIMIT 20;
```

### 核心索引

```sql
CREATE INDEX idx_news_type_ts   ON news (news_type, publish_ts DESC);
CREATE INDEX idx_news_cat_ts    ON news (category, publish_ts DESC);
CREATE INDEX idx_news_author_ts ON news (author_id, publish_ts DESC);
CREATE UNIQUE INDEX idx_news_id_ts ON news (id, publish_ts);
```

注意：唯一约束必须含分区键 `publish_ts`。外键不能指向分区表（PG 限制）。

### 数据量评估

**业务量级**：一周 ~10 万条 → 一月 ~43 万 → 一年 ~520 万 → 三年 ~1560 万。

| 时间层 | 数据量 | 存储 | 查询影响 |
|--------|--------|------|---------|
| 当月热分区 | ~43 万行 | SSD | 全部索引命中，毫秒级 |
| 热窗口（3 个月） | ~130 万行 | SSD | 裁剪后只扫 1~2 分区 |
| 冷窗口（4~13 月） | ~390 万行 | HDD | 带时间范围不碰，不带才扫 |

| 已归档（>13 月） | 自动摘除为独立表 | 永久存储 | 主表不可见，可直查独立表 |
- 比季分区好：每分区 ~43 万行，`VACUUM`/`ANALYZE`/迁表空间都轻量
- 比周分区好：3 年仅 36 个分区，元数据开销小，周分区会产生 156 个
- 3 月热窗口够用：130 万行在 SSD，B-tree 索引 `(news_type, publish_ts)` 仅数次 I/O

**磁盘估算**：

```
每行 ~500 字节（title + summary + content + JSONB + 索引）
1560 万 × 500 字节 ≈ 7.8 GB（数据）
索引 × 2               ≈ 15 GB
30% 余量               ≈ 20 GB（3 年总量）

实际常驻 ≈ 560 万行（13 个月）≈ 5 GB
```

### 向量搜索：双表分离

向量搜索与时间分区裁剪天然冲突——不带时间范围的全表 ANN 会扫所有分区。
因此**向量另存一张不分区的表**：

```
news               ← 正文/分类/时间（分区 + 冷热分离）
news_vectors       ← 向量（不分区，单表）
    └── news_id → news.id
```

| 查询类型 | 走哪张表 | 策略 |
|---------|---------|------|
| 时间线/列表/详情 | `news` | 分区裁剪，毫秒级 |
| 语义搜索 | `news_vectors` | HNSW/IVFFlat 索引，全量 ANN |

```sql
-- 语义搜索（全量，不碰 news 的分区逻辑）
SELECT n.id, n.title,
       v.embedding <=> $query_vec AS distance
FROM news_vectors v
JOIN news n ON n.id = v.news_id
ORDER BY v.embedding <=> $query_vec
LIMIT 20;

-- 时间线（走分区裁剪，不碰向量索引）
SELECT * FROM news
WHERE publish_ts >= now() - interval '7 days'
ORDER BY publish_ts DESC LIMIT 20;
```

向量表 3 年 ~1500 万行，pgvector + IVFFlat/HNSW 索引单机轻松扛。

### 健康监控

```sql
-- 查最近一次维护记录
SELECT * FROM partition_health ORDER BY check_ts DESC LIMIT 1;

-- 查 pg_cron 状态
SELECT jobname, schedule, active FROM cron.job WHERE jobname = 'news-maintenance';

-- 查分区分布
SELECT c.relname, n_live_tup, pg_size_pretty(pg_relation_size(c.oid)),
       coalesce(ts.spcname,'pg_default') AS tablespace
FROM pg_inherits i JOIN pg_class p ON i.inhparent=p.oid
JOIN pg_class c ON i.inhrelid=c.oid
JOIN pg_stat_user_tables s ON s.relid = c.oid
LEFT JOIN pg_tablespace ts ON ts.oid = c.reltablespace
WHERE p.relname = 'news' ORDER BY c.relname;
```

---

## 部署步骤

```bash
# 1. 装扩展（Debian PG 镜像）
apt-get install postgresql-16-partman postgresql-16-cron

# 2. 配 pg_cron（postgresql.conf）
shared_preload_libraries = 'pg_cron'
cron.database_name = 'postgres'

# 3. 建表空间
psql -U postgres -c "CREATE TABLESPACE ts_ssd LOCATION '/data/ssd';"
psql -U postgres -c "CREATE TABLESPACE ts_hdd LOCATION '/data/hdd';"

# 4. 一键部署
psql -U postgres -f setup_news.sql
```

---

## 3 年无人值守保障清单

| 隐患 | 措施 |
|------|------|
| 查询不带时间范围 | 应用层硬约束 |
| pg_cron 静默停止 | `partition_health` 表监控 |
| 旧分区堆积 | 自动 DETACH 归档，独立表永久保留 |
| 磁盘满 | 监控 `pg_size_pretty` 趋势 |
| 索引膨胀 | PG 自带 autovacuum，高负载需调参 |

---

## Docker 测试环境

```bash
# 容器名: pg16, 端口: 5432, 用户/密码: postgres/postgres
docker exec pg16 psql -U postgres -c "SELECT * FROM partition_health ORDER BY check_ts DESC LIMIT 1;"
```
