# Kafka 统一内容采集格式

本仓库的 `pipesight-kafka-consumer` 从 Kafka topic `news_pipeline` 读取
**news / wechat / paper**，处理后写入 `public.*`（`news_articles` / `papers`）。
本文只说明这个消费端接受的消息契约，不表示已经有生产者在发布。

## 拓扑

```
（发布方未在本仓库或 news-pipelines 当前代码中实现）
        │
        ▼
Kafka `news_pipeline` ──→ pipesight-kafka-consumer ──→ 183/pipesight
                              │ 解析/校验/翻译/分类/去重
                              └─ 只写「有效数据」进 public.*
```

- Broker：`172.16.4.182:9092`（`KAFKA_BOOTSTRAP_SERVERS`）
- Topic：`news_pipeline`（`KAFKA_TOPIC`）
- 消费组：`pipesight_news_consumer`（`KAFKA_GROUP_ID`）

## 统一 envelope

消息体优先是一个符合本契约的 JSON 对象。字段是三类内容的**并集**，按 `content_type`
取子集。

> 兼容说明：消费端另外接受扁平 JSON
> `{title,url,author,ctime(unix秒),content,content_md,site_name,domain}`。
> 这是 news-pipelines `NewsArticlesPipeline.map_message` 读取的形状，不是该仓库当前的发布格式。
> `kafka_content_consumer._normalize_crawler_message` 会把它映射进本 envelope
> （`domain == 'mp.weixin.qq.com'` → `wechat`，否则 `news`；`ctime` → `published_at`），
> 之后走同一条处理链路。扁平格式不覆盖论文。

| 字段 | 类型 | 适用 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `schema_version` | int | 全部 | 是 | 固定 `1` |
| `content_type` | string | 全部 | 是 | `news` \| `wechat` \| `paper` |
| `source_name` | string | 全部 | 否 | 来源名（映射到 `data_sources.name`，缺省「未知来源」） |
| `source_url` | string | 全部 | 否 | 来源主页地址 |
| `source_bizid` | string | wechat | 否 | 公众号 bizid（幂等键，映射到 `data_sources.config.bizid`） |
| `item_id` | string | 全部 | 否 | 爬虫侧幂等键（保留，当前写入逻辑不依赖） |
| `title` | string | 全部 | 是 | 标题 |
| `url` | string | news/wechat 必填；paper 与 `doi` 二选一 | 按类 | 规范化后的原文链接 |
| `author` | string | news/wechat | 否 | 作者 |
| `published_at` | string | news/wechat | 否 | ISO-8601 带时区，如 `2026-11-01T09:30:00+08:00` |
| `content` | string | news/wechat | 否 | 正文 |
| `content_zh` | string | news/wechat | 否 | 中文正文（缺省时由消费端翻译） |
| `doi` | string | paper | 否 | `10.xxxx/yyyy` |
| `title_zh` | string | paper | 否 | 中文标题 |
| `authors` | string | paper | 否 | 作者串（`; ` 分隔） |
| `journal` | string | paper | 否 | 期刊 |
| `published_date` | string | paper | 否 | `YYYY` / `YYYY-MM` / `YYYY-MM-DD` |
| `abstract` | string | paper | 否 | 摘要（可退化为 `content`） |
| `abstract_zh` | string | paper | 否 | 中文摘要（缺省时由消费端翻译） |

## 示例

### news

```json
{
  "schema_version": 1,
  "content_type": "news",
  "source_name": "国家管网官网",
  "source_url": "https://www.pipechina.com.cn",
  "title": "西气东输四线全线贯通",
  "url": "https://www.pipechina.com.cn/xwzx/20261101/123.html",
  "author": "编辑部",
  "published_at": "2026-11-01T09:30:00+08:00",
  "content": "……正文……",
  "content_zh": "……中文……"
}
```

### wechat

```json
{
  "schema_version": 1,
  "content_type": "wechat",
  "source_name": "国家管网",
  "source_bizid": "MzA5NjQ0MjQ5Mg==",
  "title": "一周要闻速览",
  "url": "https://mp.weixin.qq.com/s/xxxx",
  "published_at": "2026-11-01T10:00:00+08:00",
  "content": "……正文……"
}
```

### paper

```json
{
  "schema_version": 1,
  "content_type": "paper",
  "source_name": "arXiv",
  "title": "Attention Is All You Need",
  "url": "https://arxiv.org/abs/1706.03762",
  "doi": "10.48550/arXiv.1706.03762",
  "title_zh": "注意力就是你所需要的一切",
  "authors": "A. Vaswani; N. Shazeer",
  "journal": "NeurIPS",
  "published_date": "2017-06-12",
  "abstract": "……abstract……",
  "abstract_zh": "……中文摘要……"
}
```

## 消费端处理流程

每条消息独立处理，按顺序：

1. **解析 + 契约校验**：JSON 非法、缺 `content_type`/`title`、`schema_version` 非 1 →
   跳过并提交 offset（不阻塞分区）。
2. **来源幂等**：按 `content_type` 映射 `data_sources.type`（news→`website`，wechat→`wechat`，
   paper→`paper`），wechat 按 `config.bizid` 幂等；首次出现自动建档（`adapter=kafka_content_import`）。
3. **翻译（可选）**：仅当该来源在后台配置了 `model_id` 且缺 `content_zh`/`abstract_zh` 时翻译；
   翻译失败保留爬虫原文/译文，不丢内容。
4. **分类（尽力而为）**：启用类别时分类，失败按未分类（`category_id=NULL`）入库。
5. **有效性裁决 + 去重入库**：由 `CollectionPersistenceService.save_record` 统一裁决。
   以下情况**拒绝入库**（跳过并提交 offset）：标题为空/超长、URL/DOI 非法、
   新闻缺 URL、论文同时缺 DOI 和 URL、`published_at` 非带时区时间点、重复条目。

offset 手动按消息提交：**写入失败不提交**（稍后重试）；校验拒绝/重复跳过则提交。

## 与 news-pipelines 的关系

消费端希望 `news_pipeline` 上已经有消息：news/wechat 提供 `title`+`url`，paper 提供 `title`+（`doi` 或 `url`）；`published_at` 带时区；`content_type` 为三类之一。翻译、分类、去重和入库由本消费端完成。

对照 news-pipelines 当前 `main`：有 Kafka 消费实现（`app/runtime/kafka_consumer.py`、`tools/kafka_consume.py`，消费组缺省 `news-pipelines-rss-consumer`），没有把抓取结果发到该主题的生产者。Scrapy `ITEM_PIPELINES` 只注册字段清洗和可选 MySQL。`NewsArticlesPipeline` 仅在 `PG_ENABLED=1` 时由上述消费脚本写入 `news_articles`（`.env.example` 里该开关缺省为 `0`），并可能用 `adapter=kafka` 新建来源。它使用消息里的原始 URL，冲突键是 `md5(url)`。本仓库入库前会规范化 URL，唯一索引同样是 `md5(url)`。两边同时写时，完全相同的 URL 会撞上同一索引，写法不同的同一原文可能变成两行。

news-pipelines 的来源门控读取 `adapter=news_pipelines_spider` 和 `config.spider_name`，但 `PIPESIGHT_SOURCE_GATE` 缺省为 `0`。门控关闭时，爬虫按自己的运行清单执行，不看 `data_sources`。

## 运行消费端

```bash
# 常驻消费（缺省从最新开始，需指定目标环境）
APP_ENV=prod pipesight-kafka-consumer

# 回溯历史并只处理前 50 条
pipesight-kafka-consumer --env prod --from-earliest --limit 50

# 只打印映射、不写库（预览）
pipesight-kafka-consumer --env prod --from-earliest --limit 10 --dry-run
```

消费端内置目标数据库守卫：仅允许 `172.16.4.183/pipesight`，连到其它库直接拒绝。
