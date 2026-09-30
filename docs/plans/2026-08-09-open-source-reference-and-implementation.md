# PipeSight 同类开源项目调研与复用实施方案

> 调研日期：2026-08-09。活跃度、Star、推送时间来自 GitHub API；数值会随时间变化。

> 数据库命名说明：本文中的 `pipeline_*` 是调研阶段的历史命名。当前实现已收敛为 `knowledge_files`、`generation_tasks`、`reports`、`data_sources`、`collection_runs`、`news_articles`、`papers` 等明确业务表名；不再创建 `contents`、`chunks`、`model_calls`、`audit_logs`。

## 1. 结论

本项目不适合整体引入 Dify、RAGFlow 或 Paperless-ngx。它们都是独立平台，直接嵌入会造成账号、权限、菜单、任务、文件和部署体系重复。

推荐采用“领域模式复用 + 能力适配器”的方式：

1. 保留当前 Vue 3 + 若依 FastAPI 的登录、菜单、权限和审计体系。
2. 复用 Paperless-ngx 的文档生命周期设计：上传、解析状态、权限、版本和可检索状态分离。
3. 复用 RAGFlow/PaperQA2 的证据优先设计：回答和报告段落必须携带来源、位置和引用片段。
4. 复用 STORM/GPT Researcher 的两阶段生成设计：先检索和大纲，再按章节写作与校验。
5. 复用 Dify 的模型网关、Prompt 版本和工作流可观察性理念，但不复制其受附加条款约束的代码。
6. 复用 Zotero/CSL 的引用数据标准，不在项目中自创一套论文引用格式。

## 2. 候选项目比较

| 项目 | 解决的问题 | 主要架构/技术 | 活跃度（2026-08-09） | 可复用设计 | 应避开内容 |
| --- | --- | --- | --- | --- | --- |
| [RAGFlow](https://github.com/infiniflow/ragflow) | 复杂文档解析、切块、检索、Agent、可追溯引用 | Go + Python + TypeScript；DeepDoc；Docker；检索/存储基础设施 | 87k+ Star；2026-08-08 有提交；Apache-2.0 | 解析器适配层、Chunk 保留页码与标题路径、引用回链、解析任务状态 | 部署很重，不应直接作为本项目主后端；避免一次性引入全部检索基础设施 |
| [Dify](https://github.com/langgenius/dify) | 模型管理、Prompt、工作流、RAG 应用编排、可观察性 | Python API + TypeScript Web；PostgreSQL/Redis/Worker/Docker Compose | 151k+ Star；2026-08-09 有提交；Dify Open Source License | 模型能力注册、Prompt 发布版本、工作流步骤日志、密钥不回显 | 许可证有附加条件；不要复制控制台代码；避免与若依权限和菜单体系重复 |
| [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) | 文件接收、OCR、归档、标签、全文搜索、权限 | Python/Django + TypeScript；任务队列；OCR/Tesseract；Docker | 44k+ Star；2026-08-09 有提交；GPL-3.0 | 文件状态机、消费目录、原文件与解析结果分离、标签/权限/归档时间 | GPL 代码不直接复制进当前项目；敏感文件明文存储风险必须规避 |
| [PaperQA2](https://github.com/Future-House/paper-qa) | 科研文档高准确率 RAG、论文元数据、带引用回答 | Python；Agentic RAG；Numpy/外部向量库；Crossref 等元数据源 | 9k+ Star；2026-07-30 有提交；Apache-2.0 | 论文元数据感知、证据汇集、引用质量、可替换向量存储 | 不把 Agent 自由搜索结果直接当结论；必须经过权限过滤和来源校验 |
| [STORM](https://github.com/stanford-oval/storm) | 从研究问题生成长文、提纲和引用 | Python；检索模块 + 多视角问题生成 + 大纲 + 章节写作；LiteLLM | 30k+ Star；最后主要提交为 2025-09；MIT | “预写作/写作”两阶段、先问题再检索、多视角覆盖、大纲可编辑 | 活跃度低于其他候选；不要把维基文章结构直接套到客户正式报告 |
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | Web/本地资料深度研究和引用报告 | Python + TypeScript；Planner/Execution/Publisher；并行研究 Agent | 28k+ Star；2026-07-18 有提交；Apache-2.0 | 规划器—执行器—发布器分层、任务日志、并行检索、最终汇总 | Agent 成本和不确定性高；生产环境必须限制来源、预算、并发和超时 |
| [Zotero](https://github.com/zotero/zotero) | 文献采集、组织、标注、引用和共享 | JavaScript 桌面应用；Translators；CSL 样式 | 14k+ Star；2026-08-08 有提交；多许可证/AGPL 体系 | DOI/作者/期刊字段、CSL JSON、引用样式、翻译器思想 | 不嵌入桌面端；不要复制受许可证约束的界面与内部代码 |
| [Folo](https://github.com/RSSNext/Folo) | RSS/信息流阅读与 AI 摘要 | TypeScript；订阅源、阅读状态、AI 阅读体验 | 38k+ Star；2026-08-03 有提交；AGPL-3.0 | 信息流交互、来源分组、已读状态、摘要与原文并列 | AGPL；不直接复用代码，且不能替代真正的数据采集和原始快照 |

## 3. 本轮已经落地的复用设计

### 3.1 文档生命周期

新增 `pipeline_material`：

- 原文件名、映射路径、访问地址和 MIME 类型分开存储。
- 权限使用 `private/department/organization/public`，不把中文显示值作为权限逻辑。
- 解析状态使用 `queued/indexed/failed`。
- TXT/MD 支持 UTF-8、UTF-16、GB18030 基础文本提取；DOCX 使用标准库 ZIP/XML 提取正文；PDF 与旧版 DOC 进入外部解析器队列。
- 预留 `metadata_json`，后续可记录解析器名称、页数、哈希、OCR 置信度和对象存储键。

### 3.2 用户工作区

新增 `pipeline_workspace_item`：

- 收藏与资料篮使用同一表，通过 `action` 区分。
- `(user_id, item_id, action)` 唯一，避免重复加入。
- 保存最小标题快照，主数据仍以业务实体为准。
- 前端保留即时响应，本地状态更新后异步持久化。

### 3.3 研究任务与报告

新增：

- `pipeline_research_job`
- `pipeline_report`
- `pipeline_report_version`

生成流程采用 STORM/GPT Researcher 的阶段思想，但当前执行器为无需外部密钥的“模板 + 证据”实现：

```text
资料校验 → 资料解析 → 证据检索 → 大纲规划 → 章节生成
        → 引用校验 → 质量检查 → 图形准备 → 报告完成
```

当前实现能够：

- 按用户隔离任务和报告。
- 根据选定资讯、论文和内部资料形成证据清单。
- 根据可编辑大纲生成结构化章节。
- 在正文中生成引用编号，并保存引用标题、来源、位置和片段。
- 标记证据覆盖不足的章节。
- 自动保存报告，显式保存历史版本。
- 导出真实 Markdown 文件。
- 日报周报复用同一任务和报告模型，不另建一套重复工作流。
- 未完成任务可以取消；失败、取消或已完成任务均可按原配置重新生成，并自动形成新版本。
- 日报周报编辑器直接读取持久化章节、引用和质量问题，不再使用静态栏目正文。
- 日报周报支持栏目增补、正文自动保存、候选资讯挂接、来源移除、证据重组和手工版本保存。

### 3.4 基础知识检索

当前实现不伪装成向量 RAG：

- 对已提取 TXT/MD 使用中文词组和二元词基础检索。
- 严格先执行当前用户的资料权限过滤。
- 支持指定资料和指定分类范围。
- 返回引用资料和命中片段。
- 没有证据时明确说明不足。

后续接入 PaperQA2/RAGFlow 风格检索时，只替换检索器，不改变 API、权限和引用结构。

## 4. 下一阶段依赖适配器

建议定义以下接口，不直接依赖单一供应商：

```python
class DocumentParser:
    async def parse(file_path: str) -> ParsedDocument: ...

class EmbeddingProvider:
    async def embed(texts: list[str]) -> list[list[float]]: ...

class Retriever:
    async def search(query: str, scope: AccessScope) -> list[Evidence]: ...

class TextGenerator:
    async def generate(step: str, prompt_version: str, context: list[Evidence]) -> GenerationResult: ...

class ReportExporter:
    async def export(report: Report, template: Template, format: str) -> ExportArtifact: ...
```

推荐适配顺序：

1. Docling 或 MinerU：PDF/OCR、表格、页码以及复杂 DOCX 版面解析。
2. PostgreSQL + pgvector 或 Qdrant：向量检索；数据量较小时不要提前部署 Milvus。
3. LiteLLM：统一国产/私有/云端模型协议。
4. python-docx + LibreOffice headless：客户 Word 模板和 PDF 转换。
5. Celery/RQ：当解析和生成超过 HTTP 请求可接受时间后再引入异步 Worker。

## 5. 许可证原则

- Apache-2.0/MIT：可以在保留声明的前提下参考或复用局部实现，但仍优先自己实现适配层。
- GPL/AGPL：只参考交互和领域设计，不复制代码到当前仓库，避免传染性许可证义务。
- Dify Open Source License：存在 Apache 2.0 之外的附加条件，仅参考设计，不复制代码。
- Zotero/CSL：引用格式优先采用公开标准和独立 CSL 数据，不复制 Zotero 应用代码。

## 6. 运行前数据库初始化

MySQL：

```powershell
cd D:\A_CODEBASE\pipeSight
mysql -uroot -p ruoyi-fastapi < backend\sql\pipeline-domain.sql
```

PostgreSQL：

```powershell
cd D:\A_CODEBASE\pipeSight
psql -d ruoyi-fastapi -f backend\sql\pipeline-domain-pg.sql
```

执行后再启动后端和前端。未执行表结构时，新增持久化接口会明确失败，前端仍保留原有示例数据回退，不会出现空白页面。

Docker Compose 已将基础若依表和管网业务表按 `10-*`、`20-*` 顺序挂载到数据库初始化目录，新建容器时会自动完成两组表结构初始化。

## 7. 2026-08-09 验证记录

- 前端全部 Node 测试：43/43 通过。
- 管网业务与稿件模块相关后端测试：20/20 通过。
- 前端生产构建：通过，Vite 共转换 5531 个模块。
- MySQL 真实闭环：Markdown 入库、权限范围检索、带引用回答、日报生成、人工版本保存、按原配置重新生成均通过。
- 真实闭环生成 5 个栏目、1 条限定资料引用和 3 个报告版本；验收数据已清理。
- 当前代码在临时 9100 端口完成 OpenAPI 冒烟验证：资料详情/删除/重新解析、任务创建/取消/重试、报告保存/版本/导出接口均已注册。
- 后端全部 281 个测试中有 265 个通过；其余为若依 CLI 既有的 Windows/Unix 路径断言差异和受限临时目录权限问题，不涉及本轮管网业务代码。

## 8. 2026-08-10 增量实现与验证

- 技术路线图不再仅保存到浏览器：结构化图形写入所属报告的 `metadata_json`，沿用报告所有者权限，并保留本机备份用于网络异常兜底。
- 新增报告图形读取与保存接口：`GET/PUT /pipeline/research/reports/{report_id}/diagram`。
- 知识问答界面明确标注当前采用“授权资料检索与证据编排”，避免把模板检索实现描述成外部大模型调用。
- 一键启动脚本兼容 Windows 同时存在 `Path`/`PATH` 导致 `Start-Process` 失败的环境，并新增 `-FrontendPort` 参数，允许在旧端口无法清理时安全启用新实例。
- 后端管网与稿件相关测试：28/28 通过；前端 Node 测试：53/53 通过；Vite 生产构建通过。
- 最新后端在 9327 端口完成 OpenAPI 验证，共注册 163 条路径，图形保存和历史版本恢复接口均存在；对应前端在 5187 端口启动并通过代理访问后端。
- 本机 5173、9099、9100 等端口存在无权限清理的旧监听，未强制终止；当前验收地址使用 `http://127.0.0.1:5187/`。
