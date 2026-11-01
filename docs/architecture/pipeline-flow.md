# PipeSight 全流程

本文梳理 PipeSight 从「数据采集」到「成果生成」的完整链路，按代码核实，标注了各环节对应的源码位置。

## 一句话总览

> 三路采集 → 入库 →（规则预过滤 + 大模型分类）→ 平台浏览 → 用模板 + 大模型生成成果（需求填报 / 日报周报月报）。

```
┌─ 采集 ─────────────────────────────────────────────┐
│ ① 新闻网站(website) ② 公众号(wechat) ③ 论文(paper) │
└───────────────────┬────────────────────────────────┘
                    ▼
        ┌──── 两条入库通道 ────┐
        │ A. 外部爬虫(181) ─→ Kafka ─→ 消费端直写 raw 库
        │ B. 站内定时采集(adapter) ─→ 规则预过滤 ─→ 写库
        └──────────┬──────────┘
                   ▼
          大模型分类/过滤（InsightHub Worker + 后台提示词）
                   ▼
              数据库（news_articles / papers / …）
                   ▼
           平台浏览（标题/时间/正文/类别/作者/原文链接）
                   ▼
        成果生成（模板 prompt + 大模型）─→ 报告/日报
```

## 1. 数据采集（三种来源）

来源类型由 `data_sources.type` 约束限定为 `website / wechat / paper`（见 `backend/src/app/intelligence/models/collection.py`）。

| 来源 | 类型 | 采集方式 | 关键代码 |
|---|---|---|---|
| 新闻网站 | `website` | 站内定时抓取国家管网 `pipechina.com.cn` | `intelligence/integrations/public_source_bridge.py`（`pipechina_group_news` adapter） |
| 公众号 | `wechat` | 外部爬虫（181 InsightHub）推 Kafka，或 `import_wechat_feeds.py` | `intelligence/tasks/kafka_news_consumer.py`、`scripts/import_wechat_feeds.py` |
| 论文 | `paper` | Crossref 抓取，**默认只有摘要**；全文靠授权 JATS / 出版方 PDF 预览 | `public_source_bridge.py`（`crossref_works`）、`intelligence/services/full_text.py`、`scripts/prepare_licensed_papers.py`、`scripts/prepare_publisher_paper_previews.py` |

论文默认只入库摘要，全文（`full_text.py`）分两类可选项：

- `read_licensed_full_text`：CC BY 开放论文，从 Europe PMC 拿 JATS 全文与行内资源（`prepare_licensed_papers.py` 落盘）。
- `read_publisher_pdf_preview`：出版方 PDF 预览，由 `prepare_publisher_paper_previews.py` 重排为文本 + 裁图。

## 2. 入库的两条通道

**A. 外部爬虫 → Kafka → 消费端（直写 raw 库）**

181 的 InsightHub 爬虫把公众号/网站原文推送到 Kafka topic `news`，`intelligence/tasks/kafka_news_consumer.py` 消费后直接写入 `public.news_articles`：

- `review_status='approved'`（不需审核，直接入库）。
- 幂等：按 `url_hash` / `canonical_url` / `article_id` 去重。
- 不调大模型、不评分、不构造交接结果。
- `handoff_status='pending'`，留给后续大模型处理。
- 目标库守卫：仅允许生产 `172.16.4.183/pipesight`。

**B. 站内定时采集（adapter 直接抓取）**

`intelligence/tasks/collection_scheduler.py` 每 15 秒扫 `data_sources` 里到期的来源，执行对应 adapter；adapter 注册在 `public_source_bridge.py`：

- `pipechina_group_news` → `website`（国家管网新闻）
- `crossref_works` → `paper`（Crossref 论文）

> 所以不是所有数据都走 Kafka：Kafka 只是外部爬虫这条通道；站内定时采集（管网新闻、Crossref 论文）是直接抓取的。

## 3. 过滤与分类（规则 + 大模型两段）

核心契约在 `intelligence/services/data_processing.py`，分两段：

1. **规则预过滤（站内，低成本）**：`_classification` 用固定规则做初筛，同时把**后台发布的 Prompt 快照**写进 `processing.filter`。
2. **大模型过滤（外部 InsightHub Worker）**：`intelligence/integrations/insighthub.py` 把记录交接给外部 Worker，Worker 按快照里的提示词执行真正的模型过滤/分类，回写 `filter_result`、`ai_title`、`summary`、`focus_risk`、`suggestion`、`event_keywords` 等。

**提示词由管理员在后台配置**，落在 `templates` 表（`purpose` 区分用途），发布后即成为可审计的快照参与最终判定。

## 4. 数据库

入库后的内容表：

- `news_articles`：新闻 / 公众号文章
- `papers`：论文（摘要，可选全文）
- `data_sources`：采集来源配置
- `categories`：类别（`applies_to` 限定 `news/paper/all`）

## 5. 平台展示

平台读取内容库，展示详情字段：标题、发布时间、正文/摘要、类别、作者、原文链接等（对应 portal 浏览页）。

## 6. 成果生成（模板驱动）

用模板 prompt + 大模型把库里数据生成为成果。报告类型映射见 `research/services/exporters.py`：

| 报告类型 | 展示名 |
|---|---|
| `project-demand` | 科技项目需求填报表 |
| `research-demand` | 科研需求报告 |
| `technology-route` | 技术路线报告 |
| `daily` | 科技情报日报 |
| `weekly` | 科技情报周报 |
| `monthly` | 科技情报月报 |

生成流程：

1. 选模板（`templates` 表，含 prompt）+ 选材（新闻/论文/公众号）。
2. 创建 research job（`research/services/jobs.py`）。
3. worker（`pipesight-task-worker`）消费队列，调大模型。
4. `research/services/report_content.py` 归一化出「分节 + 引用」。
5. 落 `reports` 表。

日报/周报/月报由 `research/services/digest_schedules.py` 的自动计划定时派发：按 `data_sources` 的选材策略自动选材 → 排队生成。

## 7. 模板与报告类型对应

| 文件 | 对应报告类型 | 内容 |
|---|---|---|
| `docs/reference/技术需求模板及撰写指南.doc` | `project-demand` 的撰写指南 | 技术需求调研表 + 七章节逐条编写说明 |
| `docs/reference/文本生成示例.docx` / `文本生成示例2.docx` | `project-demand` 的填写样例 | 两份「科技项目需求填报表」成品，含经费预算表 |
| `docs/reference/生物安全日报示例.docx` | `daily` 的样例 | 按类别分节，每节 = 标题 + 摘要 + 洞察 + 数据源引用 |

模板提示词的结构化底稿见 `docs/reference/模板提示词底稿.md`。
