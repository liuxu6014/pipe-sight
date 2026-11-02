# PipeSight 数据库字段设计梳理

> 本文对生产库（`172.16.4.183/pipesight`）做字段级盘点，标出命名/类型不一致，记录已拍板项与待拍板项。
> 数据来源：`docker exec pipesight-pg-ruoyi-backend-pg-1` 读库（表清单、列定义、行数、大小、分区、表空间）。
> 相关既有约定见 [table-naming.md](table-naming.md)、[database-dictionary.md](database-dictionary.md)、[configuration-ownership.md](configuration-ownership.md) 与 `docs/plans/2026-10-14-database-naming-and-comments.md`。

## 0. 现状总览：单一 schema、两套「世代」

> **2026-11-01 已拍板并执行**：`news.*`（InsightHub 内容契约，8 张空壳表）整体删除——它 0 行数据、后端 ORM 已不映射、唯一引用它的 `InsightHubAdapter` 是无调用方的死代码。内容契约只剩 `public.*` 一套。

| 世代 | schema | 表数 | 来源 | 风格 |
|---|---|---|---|---|
| B. PipeSight 业务契约 | `public.*`（业务表） | 15 | 本项目演进（已做精简 + 北京墙钟迁移） | `id` + 共享 `business_id_seq`、`created_at`/`updated_at` 北京墙钟 `timestamp(0)`、`boolean`、`jsonb` |
| C. 若依（RuoYi）框架 | `public.*`（sys_* 等） | 14 | 第三方 Java 管理后台 | `id` + 独立 sequence、`created_by`/`updated_by` 文本、`char(1)` 状态码 |

合计 **29 张基础表 + 2 个视图**（`public.list_table` / `public.list_column`）。

删除 `news.*` 时一并移除的对象：8 张表 + 6 个 sequence + `news.content_type`（ENUM）与各表复合类型 + `vector` 扩展 0.8.5（`news.vector`/`halfvec`/`sparsevec` 及其数组类型，扩展仅装在 news schema，全库无其它 vector 列）。`news_app` 角色仍在库里（孤立，无对象依赖），待确认后删除。

### 0.1 冷热库：**没分，也不需要分**

生产 `pipesight` 库现状（实测）：

- 分区表 **0**、分区块 **0**；表空间只有 `pg_default` / `pg_global`，无 SSD/HDD 冷热表空间，无 FDW 冷库。
- 最大表 `public.news_articles` 仅 **22 MB / 2599 行**，全库远不到需要冷热分离的量级。

仓库里那份 `docs/architecture/2026-07-10-pg-hot-cold-design/` 是**给 legacy InsightHub 的 `news` 表**设计的按月分区方案（pg_partman + pg_cron，3 月热 / 13 月冷 / 再归档），**从未落地**。该设计随 `news.*` 删除已彻底无对象可套。

> 结论：冷热库不在当前统一范围内；等单表规模上到百万级再启用那份设计。

### 0.2 内容契约已收敛到 `public.*`

实测行数：`public.news_articles` 2599 行、`public.model_calls` 51810 行、`public.papers` 3 行 —— 活数据全在 `public.*`。`news.*` 的 8 张表除 `news.domains` 11 行种子领域外全部 0 行，已于 2026-11-01 删除。**`public.*` 是唯一事实来源**。

---

## 1. 表清单（29 张）

### A. `public.*` — PipeSight 业务表（15 张）

| 表 | 主键 | 序列 |
|---|---|---|
| `ai_models` | `id bigint` | ⚠️ 无默认值 |
| `basket_items` | `id bigint` | ⚠️ 无默认值（沿用原 saved_item_id） |
| `report_versions` | `id bigint` | ⚠️ 无默认值 |
| `categories` / `collection_runs` / `data_sources` / `digest_schedules` / `generation_tasks` / `knowledge_files` / `model_calls` / `news_articles` / `papers` / `report_assets` / `reports` / `templates` | `id bigint` | `business_id_seq` 共享 |

### B. `public.*` — 若依 + 框架（14 张）

`sys_user` / `sys_role` / `sys_menu` / `sys_config` / `sys_dict_type` / `sys_dict_data` / `sys_job` / `sys_job_log` / `sys_logininfor` / `sys_oper_log` / `sys_role_menu` / `sys_user_role`，加 `apscheduler_jobs`（`id varchar(191)`）、`alembic_version`（`version_num varchar(64)`）。

---

## 2. 字段级不一致清单

### 2.1 审计字段（创建/更新时间）—— B 族已对齐，C 族保持

**统一规则（已拍板）**：创建/更新时间唯一名字 `created_at` / `updated_at`，唯一类型 `timestamp(0) without time zone`（北京墙钟、精度到秒）。B 族已如此（2026-10-25 `beijing_audit_time` 迁移完成）。`news.*` 里 `create_time`/`update_time` 那套不一致随 schema 删除一并消除。

| 现状 | 位置 | 处理 |
|---|---|---|
| `created_at` / `updated_at`（`timestamp(0)` 北京墙钟） | B 族全部业务表 | 已是目标，无需动 |
| `created_by` / `updated_by` + `created_at` / `updated_at` | C 族 sys_* | 若依框架，保持不动（见 §4） |

### 2.2 主键 / 序列 —— 仅剩 B 族内部 3 处

| 族 | 主键 | 外键 |
|---|---|---|
| B（业务表） | 一律 `id` | `<实体单数>_id`（`source_id`、`report_id`、`task_id`、`template_id`、`model_id`、`article_id`、`paper_id`、`file_id`、`operator_id`、`parent_id`） |
| C（sys_*） | `id` | `<entity>_id` |

**问题**：B 族内 `ai_models`/`basket_items`/`report_versions` 的 `id` 无默认序列，与其余 12 张共享 `business_id_seq` 不一致。

### 2.3 布尔 / 开关 / 状态 —— B 族 boolean 与 C 族 char(1) 并存

| 表达 | 字段举例 |
|---|---|
| `boolean` | B 族 `is_enabled`、`is_pushed` |
| `char(1)`（'0'/'1'） | C 族 `status`、`del_flag`、`visible`、`concurrent`、`type`、`is_default` |
| `smallint`（0/1） | `sys_role.menu_check_strictly` |
| `integer`（0/1/2…） | `sys_menu.is_frame`、`sys_menu.is_cache`、`sys_oper_log.status` |
| `varchar(16)` 词表 | B 族 `status`（`queued/running/success/failed/cancelled` 等） |

C 族编码保留；B 族已用 `boolean` + `varchar(16)` 词表，是基准。

### 2.4 时间类型 —— 目标「全库一种 datetime」

**统一规则（已拍板）**：全库时间字段唯一类型 `timestamp(0) without time zone`（北京墙钟、精度到秒）——即 Postgres 的 datetime（SQLAlchemy `DateTime`；Postgres 没有 `DATETIME` 关键字，对应 `timestamp`）。

存量需收敛：

| 现状 | 位置 | 说明 |
|---|---|---|
| `timestamp(0) without time zone` 北京墙钟 | B 族 `created_at`/`updated_at` | 已是目标类型 |
| `timestamp without time zone`（无 (0) 精度、无统一默认） | C 族 | 框架层，保持 |
| `timestamp with time zone` | B 族 6 个调度/租约字段 + `news_articles.published_at` | 见下 |

**已拍板：`timestamptz` 字段一并改** —— B 族「绝对时刻」字段现为 `timestamptz`，做租约/退避/调度比较：

`collection_runs.available_at` / `.started_at` / `.finished_at` / `.lease_expires_at` / `.stop_requested_at`、`data_sources.next_run_at`、`digest_schedules.next_run_at`、`generation_tasks.lease_expires_at` / `.started_at` / `.finished_at`、`news_articles.published_at`。

统一改为北京 naive `timestamp(0)`，并同步把 worker 里 `now()` 与租约/退避比较逻辑统一成北京时间口径。全库最终只剩一种时间类型。

**唯一有意不并入 datetime**（它不是「时刻」）：

- `public.digest_schedules.run_time`：`time without time zone` 存「当地时分秒」，本就是 time-of-day，保持 `time`。

`papers.published_date` 已按用户要求**强并 datetime**（见 §6 G），同时补 `published_precision` 精度位，避免把「仅知年份」伪造补全成具体月日。

### 2.5 发布时间 —— 两种存法

| 字段 | 类型 | 问题 |
|---|---|---|
| `public.papers.published_date` | **`varchar(10)`** 存 `YYYY` / `YYYY-MM` / `YYYY-MM-DD` | 日期当文本、精度可变，无法范围比较 |
| `public.news_articles.published_at` | `timestamptz` | 与目标类型不一致 |

`papers.published_date` 强并 datetime（§6 G）后只剩一种 `published_at timestamp(0)` 口径。

### 2.6 JSON / 结构化字段 —— B 族统一 jsonb

| 表达 | 字段举例 |
|---|---|
| `jsonb` | B 族 `config`、`config_snapshot`、`checkpoint`、`materials`、`sections`、`citations`、`image_config`、`capabilities` |

`news.*` 里大量 `text` 承载 JSON 的历史问题已随 schema 删除消除；B 族以 `jsonb` 为基准。

---

## 3. 重复表：已消除

`news.*` 与 `public.*` 的「同一领域两套 schema」重复（文章/数据源/类目/提示词/向量 5 组），已通过删除 `news.*` 一并解决，不再存在重复表。`news.*` 里独有的向量嵌入（`news.embeddings`）也一并删除——目前平台无向量检索需求，将来需要时在 `public.*` 重建。

---

## 4. 统一规范建议（以 B 族为基准）

| 维度 | 统一后约定 | 存量整改 |
|---|---|---|
| 主键 | `id bigint`，业务表共享 `business_id_seq`，API 返回十进制字符串 | B 族内 3 张无默认序列补齐（`ai_models`/`basket_items`/`report_versions`） |
| 外键 | `<实体单数>_id` | B 族已统一，无待改 |
| 创建/更新时间 | **`created_at` / `updated_at`，`timestamp(0) without time zone` 北京墙钟**（已拍板） | B 族已对齐，无待改 |
| 时间字段 | **全库一种 datetime = `timestamp(0) without time zone` 北京墙钟**（已拍板） | B 族调度/租约/发布 `timestamptz` → `timestamp(0)`（§6 D） |
| 开关/标志 | `boolean`（`is_enabled`/`is_pushed`） | C 族 `char(1)`/`smallint`/`integer` 框架编码保留 |
| 状态 | `varchar(16)` 词表 + CHECK（或代码层唯一枚举） | B 族词表补 CHECK；C 族编码保留 |
| 结构化数据 | `jsonb` | B 族已统一 |
| 发布时间 | `published_at timestamp(0)` 北京墙钟 | `published_date` 归并（§6 G）；`news_articles.published_at` 改类型 |
| 幂等/租约 | `request_id varchar(128)` + `execution_token varchar(64)` | 已存在，保留 |

> C 族（`sys_*`、`apscheduler_jobs`、`alembic_version`）是第三方框架，**不做字段重命名**（破坏若依升级兼容）；只保证 `public.*` 业务表统一。`sys_*` 的 `created_at`/`updated_at` 已是 `timestamp(0)`，与目标类型一致，仅命名带 `_by` 文本字段，保持即可。

---

## 5. 决策清单

**已拍板**：

- [x] 冷热库：当前不分，规模达标再启用 `2026-07-10` 那份设计。
- [x] 创建/更新时间：唯一名字 `created_at` / `updated_at`。
- [x] 时间字段：全库唯一类型 `timestamp(0) without time zone`（北京墙钟 datetime）——含调度/租约 `timestamptz` 字段、`published_at`、**`papers.published_date` 也强并 datetime**；唯一例外是 `digest_schedules.run_time`（时分秒，保持 `time`）。
- [x] **内容契约：`public.*` 是唯一事实来源，`news.*` 整体删除**（2026-11-01 已执行）。
- [x] **数据库只连 183**：项目三个 docker-compose 里的本地 PG（`ruoyi-pg`/`postgres`/`insighthub-postgres`）全部移除，统一连 `172.16.4.183/pipesight`。

**待办（已由内容契约决策连带解决，无需再点头）**：

- 来源表、类目/领域、提示词与调用留痕的合并问题——随 `news.*` 删除，`public.data_sources`/`categories`/`templates`/`model_calls` 即为唯一对应表。

**遗留清理（代码侧，2026-11-01 已执行）**：

- ✅ 已删 `backend/src/app/intelligence/integrations/insighthub.py`（`InsightHubAdapter` 死代码）及其测试 `test_insighthub_adapter.py`。
- ✅ 已删 `backend/sql/insighthub-schema.pg.sql`、`backend/sql/processing-comments-pg.sql`（news.* DDL/注释）及 `test_processing_schema_comments.py`。
- ✅ 已从 `config/env.py` 删除 `InsightHubSettings` 与 `InsightHubConfig` 单例；`start-dev.ps1`、`docs/README.md` 里对 `INSIGHTHUB_DB_*` / `processing-comments-pg.sql` 的引用一并移除。
- 历史 alembic 迁移（`20261003_*`、`20261014_*`、`20261025_retire_*`）对 news schema 的引用——已 applied，作为历史保留即可，不必改。
- `schema_migration.py` 里对 `news.*`（含 `news.domains` → `categories` 的一次性迁移来源）是「紧凑 v1 迁移」的**源侧**契约（把含 news 的 47 表旧态迁到 29 表新态），仍被排练测试按旧 dump 重放；与 alembic 迁移同理按历史保留，**不删**。`numeric_id_migration.py` 实际只引用 `public.news_articles`，无任何 `news` schema 引用，本就无需清理。

---

## 6. 时间字段统一——逐字段改动清单

> 目标：全库时间字段唯一类型 `timestamp(0) without time zone`（北京墙钟、精度到秒）。下表是「梳理出的完整改动面」，尚未执行；落地时走项目既有的备份门禁 + 排练库 + Alembic 迁移流程（参考 `beijing_audit_time` 迁移）。

### D. `public.*` 业务调度/租约/发布（`timestamptz` → `timestamp(0)`）

| 字段 | 现状 | 改为 |
|---|---|---|
| `collection_runs.available_at` / `started_at` / `finished_at` / `lease_expires_at` / `stop_requested_at` | `timestamptz` | `timestamp(0)` |
| `data_sources.next_run_at` | `timestamptz` | `timestamp(0)` |
| `digest_schedules.next_run_at` | `timestamptz` | `timestamp(0)` |
| `generation_tasks.lease_expires_at` / `started_at` / `finished_at` | `timestamptz` | `timestamp(0)` |
| `news_articles.published_at` | `timestamptz` | `timestamp(0)` |

> 同步改动：worker 里所有 `now()` 与租约/退避比较逻辑，统一用北京时间口径（`CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai'` 或等价），避免「改了列类型、比较还按 UTC」的错位。代码侧把这些列的类型从 `DateTime(timezone=True)` 换成既有的 `BeijingAuditTime` TypeDecorator（`business_time.py`），Python 侧仍是 UTC-aware，比较逻辑 `aware()`/`utcnow()` 无需改。

### F. 唯一例外（非「时刻」）

| 字段 | 现状 | 处理 |
|---|---|---|
| `digest_schedules.run_time` | `time without time zone` | 保持 `time`（当地时分秒） |

### G. 日期强并 datetime（`papers.published_date`）

| 字段 | 现状 | 改为 |
|---|---|---|
| `papers.published_date` | `varchar(10)`（`YYYY` / `YYYY-MM` / `YYYY-MM-DD`） | `published_at timestamp(0)`（`YYYY`→`YYYY-01-01 00:00:00`，`YYYY-MM`→`YYYY-MM-01 00:00:00`，`YYYY-MM-DD`→当日 00:00:00） |
| `papers.published_precision` | （新增） | `varchar(8)`，取值 `Y` / `YM` / `YMD`，记录原精度 |

> 原字段注释约定「未知月日不补造」：强并 datetime 必然要把 `YYYY` 补成 `YYYY-01-01`。为不丢失「只有年份 / 年月」这一精度信息，必须保留 `published_precision` 精度位，否则会把「仅知 2023」伪装成「2023-01-01 确知」。

> `sys_*`（C 族）已是 `timestamp(0) without time zone`，类型无需改，仅默认值非北京墙钟、且不重命名（若依兼容），保持现状。
