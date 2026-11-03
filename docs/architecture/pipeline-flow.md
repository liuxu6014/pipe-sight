# PipeSight 全流程

本文梳理 PipeSight 从「数据采集」到「成果生成」的完整链路，按代码核实，标注了各环节对应的源码位置。

## 一句话总览

> 三路采集 → 翻译/分类 → 入库 → 平台浏览 → 用模板 + 大模型生成成果（需求填报 / 日报周报月报）。

```
┌─ 采集 ─────────────────────────────────────────────┐
│ ① 新闻网站(website) ② 公众号(wechat) ③ 论文(paper) │
└───────────────────┬────────────────────────────────┘
                    ▼
        ┌──── 两条入库通道 ────┐
        │ A. 外部爬虫(news-pipelines) ─→ Kafka(news_pipeline) ─→ 统一消费端 ─→ 处理写库
        │ B. 站内定时采集(adapter) ─→ 翻译/分类 ─→ 写库
        └──────────┬──────────┘
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
| 公众号 | `wechat` | 管理员在来源管理添加公众号 RSS 链接，`wechat_rss` 适配器拉取内部 wechat2rss feed | `intelligence/integrations/wechat_rss.py` |
| 论文 | `paper` | Crossref 抓取，**默认只有摘要**；全文靠授权 JATS / 出版方 PDF 预览 | `public_source_bridge.py`（`crossref_works`）、`intelligence/services/full_text.py`、`scripts/papers/prepare_licensed_papers.py`、`scripts/papers/prepare_publisher_paper_previews.py` |

论文默认只入库摘要，全文（`full_text.py`）分两类可选项：

- `read_licensed_full_text`：CC BY 开放论文，从 Europe PMC 拿 JATS 全文与行内资源（`prepare_licensed_papers.py` 落盘）。
- `read_publisher_pdf_preview`：出版方 PDF 预览，由 `prepare_publisher_paper_previews.py` 重排为文本 + 裁图。

## 2. 入库的两条通道

**A. 外部爬虫（news-pipelines）经 Kafka 统一接入**

外部爬虫（`news-pipelines`，独立仓库）把采集内容发布到 Kafka 主题 `news_pipeline`（`172.16.4.182:9092`）。`pipesight-kafka-consumer`（`intelligence/tasks/kafka_content_consumer.py`）常驻订阅：先解析统一 envelope `KafkaContentMessage`，兼容爬虫历史格式 `{title,url,author,ctime,content,content_md,site_name,domain}`（映射进 envelope），再走与站内采集相同的翻译/分类/有效性裁决后写入 183 的 `public.news_articles`（与站内采集共用同一份紧凑内容契约）。

**B. 站内定时采集（adapter 直接抓取）**

`intelligence/tasks/collection_scheduler.py` 每 15 秒扫 `data_sources` 里到期的来源，执行对应 adapter；adapter 注册在 `public_source_bridge.py`：

- `pipechina_group_news` → `website`（国家管网新闻）
- `wechat_rss` → `wechat`（公众号 RSS，feed 地址放在 `config.feed_url`，`url` 列仍受全局 HTTPS 白名单约束）
- `crossref_works` → `paper`（Crossref 论文）

采集正文经 `CollectionTranslationService`（按来源配置翻译 `content_zh`）与 `CategoryService.classify`（按类别提示词+模型给出唯一 `category_id`）后，由 `CollectionPersistenceService.save_batch` 写入 `news_articles` / `papers`。

## 3. 翻译与分类

- **翻译**：`intelligence/services/collection_translation.py` 按来源配置的翻译模型把正文/摘要翻译成 `content_zh` / `abstract_zh`（原文已中文则跳过）。
- **分类**：`intelligence/services/categories.py` 的 `CategoryService.classify` 依据 `categories` 表里每个类别的过滤/分类提示词（`prompt`）与分类模型（`model_id`）给每条内容一个唯一 `category_id`；未命中则分类为空。
- 管理员在后台维护 `categories`（`applies_to` 限定 `news/paper/all`），启用后即参与新内容的分类判定。

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
