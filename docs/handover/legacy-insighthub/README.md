# InsightHub 新闻处理服务

> **PipeSight 集成说明（2026-10-02）**  
> 本目录已纳入 PipeSight 同一仓库。运行时唯一事实存储为 PostgreSQL + pgvector；新闻事实、领域配置、提示词配置和向量均使用同一 PostgreSQL 实例。根目录 `docker-compose.pg.yml` 是当前统一运行配置。

> **源码归并说明（2026-10-03）**  
> Worker 源码现已归入 `backend/src/app/intelligence/processing`，正式入口为
> `app.intelligence.processing.main`，统一使用 `backend/pyproject.toml`、
> `backend/requirements-pg.txt` 和 `backend/Dockerfile.processing.pg`。本目录中的
> `news_processor` 目前仅作为迁移期回滚副本，不参与当前构建；完成测试迁移后再删除。

## PipeSight 一体化运行

默认启动统一的 PostgreSQL + pgvector，并让 PipeSight 后端与 InsightHub 共用同一个数据库实例：

```bash
docker compose -p pipesight-pg -f docker-compose.pg.yml up -d --build
```

配置真实 LLM 与 Embedding 凭据后，可启动处理 Worker：

```bash
export INSIGHTHUB_LLM_API_KEYS='...'
export INSIGHTHUB_LLM_BASE_URL='...'
# 可选：未配置时仍可完成新闻主记录处理，但不会生成 news.news_embedding
export INSIGHTHUB_EMBEDDING_KEY='...'
export INSIGHTHUB_EMBEDDING_URL='...'
docker compose -p pipesight-pg -f docker-compose.pg.yml up -d --build insighthub-worker
```

在统一 Compose 中，`insighthub-worker` 是 PostgreSQL 全链路的默认服务，不属于
profile；因此不需要额外启用 profile。完整平台仍可使用前面的统一启动命令。

```bash
docker compose -p pipesight-pg -f docker-compose.pg.yml up -d --build insighthub-worker
```

Embeddings 配置完成后，可用以下命令为历史已完成新闻补建缺失向量；命令只写入
`news.news_embedding`，不会修改新闻处理状态，重复执行也是幂等的：

```bash
docker compose -p pipesight-pg -f docker-compose.pg.yml exec insighthub-worker \
  python -m app.intelligence.processing.backfill_embeddings --limit 100
```

执行前可先使用 `--dry-run` 查看候选数量。未配置 `INSIGHTHUB_EMBEDDING_URL` 时，
回填命令会明确拒绝执行，不会把 DeepSeek 文本模型当作 Embeddings 服务。

对象存储是可选 profile；配置可用的 MinIO/S3 镜像仓库后再启动：

```bash
docker compose -p pipesight-pg -f docker-compose.pg.yml --profile insighthub-storage up -d insighthub-minio
```

Worker 不把对象存储作为 PostgreSQL 处理主链路的硬依赖；本地环境若无法访问 MinIO 镜像仓库，仍可启动并验证数据库、队列和向量处理服务。

集成后的数据路径：

```text
PipeSight news_articles
  → backend/module_pipeline/integration/insighthub_adapter.py
  → PostgreSQL ruoyi-fastapi.news.hp_news（processing_status=pending）
  → InsightHub PostgreSQL inbox worker（同一实例）
  → 领域/分类/风险/摘要处理
  → PostgreSQL news.hp_news + news.news_prompt_usage
  → （已配置 EMBEDDING_URL 时）pgvector news.news_embedding
  → PipeSight 回执同步
```

主要运行文件：

- `backend/sql/insighthub-schema.pg.sql`：本地完整 schema 和索引；
- `backend/src/app/intelligence/processing/db/postgres.py`：新闻事实、来源、领域和 inbox；
- `backend/src/app/intelligence/processing/db/pgvector.py`：1024 维向量写入；
- `backend/src/app/intelligence/processing/main.py`：默认 `INPUT_MODE=postgres`，可切回 Kafka；

当前统一数据库为 `ruoyi-fastapi`，PipeSight 使用 `public` schema，InsightHub 使用 `news` schema。历史迁移说明保存在 `docs/`，不作为当前运行配置使用。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org)
[![uv](https://img.shields.io/badge/uv-0.7+-blueviolet)](https://github.com/astral-sh/uv)
[![Docker](https://img.shields.io/badge/Docker-20.10+-blue)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](../frontend/LICENSE)
[![Kafka](https://img.shields.io/badge/Kafka-Latest-orange)](https://kafka.apache.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-blue)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-0.8+-green)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7.0+-red)](https://redis.io/)

> 🚀 基于 AI 的高性能新闻数据处理与分析微服务

## 📋 项目概述

InsightHub 新闻处理服务是一个企业级的智能新闻数据处理平台，采用领域驱动设计(DDD)架构，支持多领域新闻的实时处理、分析和智能检索。该服务利用
OpenAI 等 AI 技术进行新闻分类、特征提取和向量化，实现高效的语义搜索和内容分析。

### ✨ 核心特性

- 🔄 **实时数据流处理**: 基于 Kafka 的高吞吐量消息处理
- 🧠 **AI 智能分析**: 集成 OpenAI API 进行新闻分类和特征提取
- 🎯 **领域专业化**: 支持政治、科技、生物、航天、种业、水利等多个专业领域
- 🔍 **向量化搜索**: 基于 pgvector 的语义相似度检索
- 📊 **风险评估**: 智能新闻风险评分与多维度分析
- 🌐 **多语言支持**: 中英文内容处理与繁简转换
- 🚀 **高并发架构**: 异步处理架构，支持高并发场景
- 💾 **智能去重**: 基于 Redis Bloom Filter 的高效去重机制
- 🔧 **健康监控**: 内置健康检查和服务监控
- 🐳 **容器化部署**: 完整的 Docker Compose 部署方案

## 🏗️ 系统架构

```
                                     ┌─────────────┐
                                     │             │
                         ┌───────────► AI Service  │
                         │           │  (OpenAI)   │
                         │           └─────────────┘
                         │
┌─────────┐      ┌───────────────┐      ┌─────────────┐
│         │      │               │      │             │
│ Kafka   ├──────► News Processor├──────► PostgreSQL  │
│ 消息队列 │      │   核心处理服务   │      │ 关系库+向量库 │
└─────────┘      └───────┬───────┘      └─────────────┘
                         │
                         │           ┌─────────────┐
                         │           │             │
                         └───────────► pgvector    │
                                     │  向量检索扩展 │
                                     └─────────────┘
                                              │
                                     ┌─────────────┐
                                     │             │
                                     │ Redis       │
                                     │ 缓存&去重    │
                                     └─────────────┘
```

### 📦 服务组件

| 组件                 | 描述      | 技术栈                        |
|--------------------|---------|----------------------------|
| **News Processor** | 核心处理服务  | Python 3.10+, AsyncIO      |
| **Kafka**          | 分布式消息队列 | Apache Kafka               |
| **PostgreSQL**     | 关系型数据存储 | PostgreSQL 16+             |
| **pgvector**       | 向量检索扩展 | pgvector 0.8+              |
| **Redis**          | 缓存与去重   | Redis 7.0+ with RedisBloom |
| **AI Service**     | AI分析服务  | OpenAI API                 |

## 🛠️ 技术栈

### 核心框架

- **Python**: 3.10+
- **异步处理**: AsyncIO, AioHTTP
- **依赖管理**: uv 0.7+

### 数据处理

- **消息队列**: Apache Kafka (aiokafka)
- **数据库**: PostgreSQL 16+ (asyncpg)
- **向量检索**: pgvector 0.8+
- **缓存**: Redis 7.0+ (aioredis) with RedisBloom

### AI & 机器学习

- **AI平台**: OpenAI API
- **文本处理**: OpenCC (繁简转换)
- **数据修复**: json-repair

### 开发工具

- **配置管理**: Pydantic Settings
- **日志**: Loguru
- **重试机制**: Tenacity
- **代码质量**: Black, isort, mypy, pylint
- **测试框架**: pytest, pytest-asyncio, pytest-cov

### 部署运维

- **容器化**: Docker & Docker Compose
- **CI/CD**: GitLab CI
- **健康检查**: 内置HTTP健康检查端点

## 🚀 快速开始

### 📋 环境要求

- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Python**: 3.10+ (本地开发)
- **uv**: 0.7+ (本地开发)

### ⚙️ 环境配置

1. **创建环境变量文件**:

```bash
# 复制环境配置模板
cp .env.example .env
```

2. **配置必要的环境变量**:
```env
# OpenAI 配置（必须）
OPENAI_API_KEY=your_openai_api_key_here

# 性能配置
MAX_WORKERS=5

# PostgreSQL 配置（PipeSight 一体化运行时使用根 Compose 的同一实例）
POSTGRES_HOST=ruoyi-pg
POSTGRES_PORT=5432
POSTGRES_DB=ruoyi-fastapi
POSTGRES_SCHEMA=news
POSTGRES_USER=postgres
POSTGRES_PASSWORD=root

# 领域处理器配置
ENABLE_POLITICS=true
ENABLE_TECH=true
ENABLE_BIOLOGY=true
ENABLE_SPACE=true
ENABLE_SEED=true
ENABLE_WATER=true
```

### 🐳 Docker 部署

#### 统一开发环境部署

```bash
# 在仓库根目录执行；PipeSight 后端、PostgreSQL、Redis 和 Worker 共用该编排
docker compose -p pipesight-pg -f ../docker-compose.pg.yml up -d --build

# 需要启动 Worker 时启用 profile
docker compose -p pipesight-pg -f ../docker-compose.pg.yml --profile insighthub up -d --build

# 查看 Worker 日志
docker compose -p pipesight-pg -f ../docker-compose.pg.yml logs -f insighthub-worker
```

### 💻 本地开发环境

```bash
# 1. 安装依赖
uv venv
uv sync

# 2. 激活虚拟环境
source .venv/bin/activate  # Windows PowerShell: .\\.venv\\Scripts\\Activate.ps1

# 3. 启动根项目的统一 PostgreSQL + pgvector + Redis
cd ..
docker compose -p pipesight-pg -f docker-compose.pg.yml --profile insighthub up -d --build

# 4. 运行应用
python -m app.intelligence.processing.main
```

依赖管理规范：新增 Python 依赖请使用 `uv add <package>`，让依赖同时写入 `pyproject.toml` 和 `uv.lock`；不要只用 `uv pip install` 做本地临时安装。

### ✅ 服务验证

启动完成后，访问以下端点验证服务状态：

- **健康检查**: http://localhost:8000/health
- **领域状态**: http://localhost:8000/domains

## 📂 项目结构

```
insighthub/
├── news_processor/                 # 核心应用包
│   ├── main.py                     # 入口：启动/消费/处理
│   ├── config/                     # 配置管理（Pydantic Settings）
│   ├── models/                     # 数据模型（Pydantic）
│   ├── processors/                 # 应用编排：处理流水线/去重/向量队列
│   ├── domain/                     # 领域处理器（文件系统/数据库/混合）
│   ├── services/                   # 外部服务适配（Kafka、领域配置DB）
│   ├── db/                         # 基础设施适配（PostgreSQL/pgvector/Redis/MinIO）
│   ├── prompts/                    # 提示词模板（按领域分组）
│   ├── supported_text/             # 领域支持文本/词表
│   └── utils/                      # 通用工具（健康检查等）
├── docs/                           # 文档
├── tests/                          # 测试
├── docker-compose.yml              # 外部 PG/Redis 已存在时的独立 Worker 编排
├── Dockerfile                      # 应用容器构建文件
├── pyproject.toml                  # Python项目配置
├── Makefile                        # 常用命令快捷方式
└── README.md                       # 项目说明文档
```

## 🔄 处理流程

### 程序架构（代码视角）

- **入口与生命周期**: `news_processor/main.py` 中 `NewsProcessorApp` 负责启动依赖、从 PostgreSQL inbox 或可选 Kafka 消费、并发处理和优雅关闭。
- **消息入口**: 默认由 `news_processor/db/postgres.py` 领取 `news.hp_news` 中的 pending/failed 记录；仅在 `INPUT_MODE=kafka` 时使用 `news_processor/services/kafka_service.py`。
- **应用编排**: `news_processor/processors/manager.py` 中 `NewsProcessorManager` 负责基础校验、去重、领域筛选/分发、AI 分类/评分、特征提取、入库与向量化。
- **领域层（DDD）**: `news_processor/domain/` 定义 `DomainProcessor` 接口；`DomainProcessorFactory` 组合三类处理器：文件系统处理器、数据库动态处理器、混合处理器（数据库配置 + 文件系统业务逻辑）。
- **基础设施层**: `news_processor/db/` 提供 PostgreSQL、pgvector、Redis 和可选 MinIO 的连接与操作；`news_processor/services/domain_config_service.py` 读取领域与分类配置（用于动态/混合处理器）。
- **运维与可观测性**: `news_processor/utils/health.py` 提供 `/health`（整体状态）与 `/domains`（领域状态），Loguru 负责结构化日志与滚动归档。

### 新闻处理管道

1. **消息消费**: 默认从 PostgreSQL inbox 领取 PipeSight 写入的原始新闻；可选从 Kafka 主题消费
2. **去重检查**: 使用 Redis Bloom Filter 检查消息是否已处理
3. **领域分发**: 根据新闻内容分发到相应的领域处理器
4. **AI 分析**: 调用 OpenAI API 进行新闻分类和风险评分
5. **特征提取**: 提取新闻关键特征（时间、地点、人物、组织等）
6. **向量生成**: 生成新闻向量嵌入用于语义搜索
7. **结构化入库**: 将处理结果更新到 PostgreSQL `news.hp_news`
8. **向量入库**: 通过异步队列构建 embedding 并写入 PostgreSQL `news.news_embedding`

### 管理端数据过滤提示词闭环

管理端 `data-filter` 提示词的执行链路如下：

1. 后端采集开始时读取当前已发布版本，并将 `promptKey`、`versionNo`、系统提示词和用户提示词快照写入采集结果；
2. 采集阶段先执行固定规则预过滤，拒绝项直接进入 `rejected`，避免无效内容调用模型；
3. 预过滤通过的记录进入 InsightHub Worker，使用快照中的 `{{title}}`、`{{body}}`、`{{summary}}`、`{{source}}`、`{{publishedAt}}` 变量调用模型；
4. Worker 要求模型返回 JSON `keep`、`score`、`reason`、`category`、`keywords`，`keep=false` 会阻断领域处理；
5. Worker 将实际使用的提示词版本和模型判定写入 `filter_result`，因此通过和拒绝都可追溯；
6. 带有 PipeSight 快照的记录必须同时携带已启用的 `data-filter` 场景模型路由；未配置路由会明确标记为 `failed`，不会悄悄退回 Worker 的旧全局模型；
7. 没有 PipeSight 快照的历史 Kafka/本地消息继续使用原有领域提示词，不改变兼容路径。

模型返回非法 JSON 时不会降级为另一份提示词，而是将记录标记为可重试的 `failed`，避免管理端配置失效却被静默掩盖。

模型路由启用后，Worker 默认通过 PipeSight 后端模型代理执行调用，模型密钥只保存在后端模型配置中；只有未携带 PipeSight 管理端快照的兼容消息，才会使用本地 `LLM_*` 配置。

### 领域处理器架构

项目采用领域驱动设计，支持多个专业化的新闻处理器：

- **政治新闻处理器**: 处理政治、政策相关新闻
- **科技新闻处理器**: 处理科技、创新相关新闻
- **生物新闻处理器**: 处理生物、医疗相关新闻
- **航天新闻处理器**: 处理航天、太空相关新闻
- **种业新闻处理器**: 处理农业、种子相关新闻
- **水利新闻处理器**: 处理水资源、水利工程相关新闻
- **通用新闻处理器**: 处理其他类型新闻

每个处理器都有专门的 AI 提示模板，确保领域专业性和处理准确性。

## 🔧 配置说明

### 核心配置

```python
# news_processor/config/settings.py
class Settings:
    # 并发/任务超时
    max_workers: int = 4
    news_process_timeout: int = 1800
    vector_save_timeout: int = 600

    # Kafka
    kafka_bootstrap_servers: str
    kafka_topic_name: str

    # PostgreSQL/pgvector/Redis/MinIO
    postgres_host: str
    postgres_db: str
    postgres_schema: str
    postgres_password: str
    embedding_dimensions: int
    redis_host: str
    minio_endpoint: str

    # 领域处理器（文件系统/数据库动态）
    enabled_domains: str
    disabled_domains: str
    enable_database_domains: bool = True
    # 动态领域配置与新闻事实使用同一 PostgreSQL schema
```

### 领域处理器配置

可以通过环境变量控制领域处理器的加载策略（推荐参考 `.env.example`）：

```env
# 文件系统领域处理器（逗号分隔）
ENABLED_DOMAINS=politics,biology,tech,seed,space,water
DISABLED_DOMAINS=

# 是否启用数据库动态领域处理器（开启后会从领域配置库生成处理器/混合处理器）
ENABLE_DATABASE_DOMAINS=true

# 动态领域配置库使用 PostgreSQL 的 news.sys_domain / news.hp_domain
```

## 🧪 测试

项目包含全面的测试套件，支持单元测试、集成测试和端到端测试。

### 运行测试

```bash
# 运行所有测试
make test

# 运行单元测试
make test-unit

# 运行集成测试
make test-integration

# 运行端到端测试
make test-e2e

# 生成覆盖率报告
make test-coverage
```

### 测试结构

```
tests/
├── unit/                    # 单元测试
│   ├── test_config/        # 配置测试
│   ├── test_db/            # 数据库测试
│   ├── test_domain/        # 领域处理器测试
│   ├── test_processors/    # 处理器测试
│   ├── test_services/      # 服务测试
│   └── test_utils/         # 工具函数测试
├── integration/            # 集成测试
└── e2e/                   # 端到端测试
```

### 预警邮件测试

使用 `scripts/test_email_alert.py` 验证邮件中转服务是否可用。前置条件：`.env` 中已配置 `EMAIL_SERVICE_URL`、`ALERT_RECIPIENT_EMAILS` 等变量。

```bash
# 直接发送测试邮件（读取 .env 配置）
uv run python scripts/test_email_alert.py

# 指定收件人
uv run python scripts/test_email_alert.py --to "user@example.com"

# 指定抄送
uv run python scripts/test_email_alert.py --cc "cc@example.com"

# 干跑模式（只渲染不发送）
uv run python scripts/test_email_alert.py --dry-run

# 干跑 + 导出 HTML 预览
uv run python scripts/test_email_alert.py --dry-run --preview-html preview.html
```

## 📊 监控和运维

### 健康检查

服务提供内置的健康检查端点：

- **基础健康检查**: `GET /health`
- **领域处理器状态**: `GET /domains`

### 服务监控

每个核心组件都有独立的健康状态监控：

- Kafka 连接状态
- PostgreSQL 数据库状态
- Redis 缓存状态
- pgvector 向量存储状态
- 各领域处理器状态

### 日志管理

使用 Loguru 进行结构化日志记录：

```bash
# 查看统一编排中的 Worker 日志
docker compose -p pipesight-pg -f ../docker-compose.pg.yml logs -f insighthub-worker
```

## 🔒 安全考虑

- **API 密钥管理**: 使用环境变量管理敏感信息
- **网络隔离**: Docker 网络隔离各服务
- **访问控制**: 数据库和缓存访问控制
- **数据加密**: 传输和存储数据加密

## 🚀 性能优化

- **异步处理**: 全异步架构提高并发性能
- **连接池**: 数据库连接池管理
- **批量处理**: 支持批量数据处理
- **缓存策略**: Redis 缓存热点数据
- **去重优化**: Bloom Filter 高效去重

## 📈 扩展性

- **水平扩展**: 支持多实例部署
- **领域扩展**: 易于添加新的领域处理器
- **存储扩展**: 支持分布式存储
- **服务解耦**: 微服务架构便于独立扩展

## 🐛 故障排除

### 常见问题

1. **服务启动失败**
   ```bash
   # 检查统一编排服务状态
   docker compose -p pipesight-pg -f ../docker-compose.pg.yml ps
   
   # 查看 Worker 错误日志
   docker compose -p pipesight-pg -f ../docker-compose.pg.yml logs insighthub-worker
   ```

2. **数据库连接问题**
   ```bash
   # 检查 PostgreSQL 状态
   docker compose -p pipesight-pg -f ../docker-compose.pg.yml exec ruoyi-pg \
     pg_isready -U postgres -d ruoyi-fastapi
   ```

3. **Kafka消费问题**
   ```bash
   # 检查Kafka主题
   docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list
   ```

4. **AI服务调用失败**
    - 检查 OpenAI API 密钥配置
    - 验证网络连接和API限额

### 性能调优

- 调整 `MAX_WORKERS` 参数控制并发数
- 优化数据库连接池大小
- 配置 Kafka Consumer 参数
- 调整 Redis 内存配置

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 开发规范

- 遵循 PEP 8 代码规范
- 使用 Black 格式化代码
- 编写单元测试
- 更新相关文档

## 📄 许可证

本项目沿用仓库的 MIT 许可证 - 查看 [许可证文件](../frontend/LICENSE) 了解详情。

## 👥 贡献者

- **Jay Liu** - *项目维护者* - [jayliu@tju.edu.cn](mailto:jayliu@tju.edu.cn)

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- **邮箱**: jayliu@tju.edu.cn
- **项目 Issues**：请在 PipeSight 主仓库提交问题。

## 🙏 致谢

感谢以下开源项目和服务：

- [Apache Kafka](https://kafka.apache.org/) - 分布式流处理平台
- [pgvector](https://github.com/pgvector/pgvector) - PostgreSQL 向量扩展
- [OpenAI](https://openai.com/) - AI服务提供商
- [FastAPI](https://fastapi.tiangolo.com/) - 现代Web框架
- [uv](https://github.com/astral-sh/uv) - Python依赖管理

---

<div align="center">
Made with ❤️ by the InsightHub Team
</div>
