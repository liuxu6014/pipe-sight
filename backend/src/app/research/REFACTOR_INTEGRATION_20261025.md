# 生成 / 资料模块集成交接

实现于共享工作区，未连接真实数据库、Redis、采集器或付费模型；未修改主 PipelineDao、alembic、认证或采集实现。

## 已实现

- reports 只有 id、user_id、title、type、template_id、content、version、created_at、updated_at。
- generation_tasks 通过 report_id 取得所有者；全局 request_id、输入冻结、最多 50 条、上下文预算、执行令牌/租约、用户编辑冲突保留任务结果。
- 明确重试创建新任务、沿用原输入；错误不会转换成正常的模拟生成。取消隔离令牌，阻止取消后回写；不能声称已终止供应商侧正在执行的请求。
- 选材支持 article / paper / file。论文只读摘要与文献信息；文件 ready 且有效正文非空，edited_text IS NOT NULL 优先（空字符串不会回退）。
- report_assets 由原导出实体改名承载；图片和导出共表，复合外键保证任务/资源属于同一成果。独立资源失败重试、权限校验、稳定存储键。
- 模板可无模型保存/浏览/选择；真正入队时严格要求启用且能力匹配的文本/图片模型。默认模板不自动捏造模型配置。
- ai_models 单表；管理 DTO 接受新字段及旧 modelId/modelName/modelCode/status/apiKey，旧 supportImages 仅映射 image_input；不会推断 image_generate。API 统一由管理员维护。
- 实际调用实现为 OpenAI 兼容 chat/completions 与 images/generations（base64 PNG）；provider 明确仅允许 openai / openai-compatible / compatible / deepseek，Anthropic、Qwen 等原生协议主动报错，厂商的兼容端点须明确选择 compatible。DTO/OpenAPI 提示一致。凭证支持 env: 引用或 encrypted: 本地加密引用。配额使用 Redis 原子计数，配置限额时缓存失败不放行。未配置备用模型时不会自动换模型。
- model_calls 已接入真实文本/图片网关，记录成功/失败、耗时及供应商返回的 Token 用量；不保存输入正文、密钥或响应原文。未返回用量时保持 NULL。
- 普通用户模板列表提供 modelConfigured / imageModelConfigured（同时检查存在、启用、能力和受支持协议）；前端供应商选项须与上述四个 provider 标识保持一致。
- 保留 report_versions 历史列表、详情、恢复，编辑/生成/显式应用结果前后留历史。恢复创建新版本。version 仅为并发控制，不替代历史正文。
- 上传资料扫描、类型/大小/ZIP 限制保留；解析重试不覆盖用户编辑。资料默认私有。普通删除明确返回 historicalSnapshotsRetained=true，不冒充彻底清除历史生成副本。

## 专属仓储及跨域接口

研究服务均使用 app.research.repositories.research_repository.ResearchDao（另有同类 PipelineDao 导出），资料使用 app.library.repositories.material_repository.MaterialDao。**不需要在主 DAO 再实现几十个研究/资料方法。**

ResearchDao 已覆盖成果读写、任务入队/认领/令牌续租、版本、模板、模型、资源、资料篮和计划。MaterialDao 覆盖本人查询、解析 CAS 认领与结果回写。资源执行使用事务行锁、稳定资源 ID 和落盘检查；失败只在用户明确重试后再请求。进程中断的请求无法保证供应商计费恰好一次，仍依赖供应商幂等能力；不做此保证。

唯一跨内容域读取接口在 ResearchDao：

- load_content(db, kind, item_id)：读取 app.intelligence.models.content.PipelineArticle / PipelinePaper，规范 id、content/content_zh、abstract/abstract_zh、source_id、published_at/published_date、url、doi、journal、authors、title/title_zh。
- digest_candidates(db, start, end, config)：PipelineArticle.source_id → PipelineSource.id，PipelineSource.type 使用 website/wechat；category_ids/category_names → PipelineCategory，日期/来源/类别/关键词先过滤，再完整标题去重、分页或显式前 N 条。

需主代理清理 app.intelligence.models.__init__ / pipeline_models 等聚合入口中已退役的 Prompt/Route/Publication/治理实体导出；保留 PipelineModelCallAudit、PipelineTemplateVersion 和新的内容实体。模型管理服务已绕开旧 AiModelDao；个人聊天消费者仍需另行适配规范 AiModels 字段（该域不在本次写范围）。

旧 research/services/facade.py 已在确认无运行消费者后删除。其默认大纲、假章节生成、审核质量拼接和 Markdown 假生成 builder 一并删除；成果详情实际使用的 Markdown 分节移到 services/report_content.py 保留。来源、目录、dashboard 消费者直接调用各自领域服务。共享 controller/bootstrap 的旧 PromptService 由主代理清理。

## 共享 DTO 需要主代理集成

1. PipelineTemplateSaveModel / PipelineTemplateModel：规范 id、name、purpose、description、prompt、model_id 可空、image_model_id 可空、sections、image_config、is_enabled。模板服务接收 model_dump(by_alias=False)；不再要求 code/color/version_label/report_type/版本审批。旧模板接口可显式适配启停。
2. PipelineResearchJobCreateModel：增加 report_id 可空供重生成；支持规范 type 或 report_type，旧 research-demand/project-demand/technology-route 映射 research；所有类型选材最多 50。可增加 materials: list[{type,id}] 解决跨表 ID 歧义；旧 selected_item_ids 继续严格解析。前端正文不作为权威选材。
3. PipelineDigestScheduleCreateModel：增加 timezone（默认 Asia/Shanghai）、selection_config、generation_config；保留旧 scheduleTime/scheduleWeekday/scheduleMonthDay/options 等显式映射。计划 request_id 不再有实体列；生成轮次仍用 schedule:ID:UTC时刻 全局幂等。
4. PipelineWorkspaceItemMutationModel：允许 file（material 仍为 DTO 别名）；title/snapshot 不必填，不存入实体，由服务重读授权来源。
5. PipelineReportExportRecordModel：从资源 DTO 读取 id/exportId/reportId/taskId/type/mime/status/downloadUrl 等；不能强制依赖已删除的实体 file_size/file_hash/report_revision/attempt_count 列。仅展示格式可由 MIME 推导。
6. PipelineReportExportModel：Markdown 导出使用 fileName/content（filename 也保留显式别名）；不再强制审核或发布后导出。

本次自行新增 DTO：library.schemas.materials.MaterialEditModel（expectedVersion、editedText、name），research.schemas.generation.ApplyGenerationResultModel（expectedVersion）。模型管理 schemas/ai_model.py、services/ai_model_service.py、api/ai_model_controller.py 已在新增授权范围实现，无需主代理再改同一文件。

## 新增/保留 API

- PUT /pipeline/knowledge/documents/{id}：乐观锁编辑 name / editedText，null 表示撤销编辑并回退提取文本，空文本保持空。
- GET /pipeline/research/assets/{id}/download：本人资源受控下载；POST 同路径 /retry 独立重试。
- POST /pipeline/research/jobs/{id}/apply-result：expectedVersion 显式应用冲突生成结果并保留历史。
- 既有 versions 列表/详情/restore 保留。审批、定稿、发布、撤销发布、发布历史的旧方法/路由/DTO 引用均直接删除。
- POST /ai/model/{id}/test?capability=text_generate 或 image_generate：用户明确点击后才会产生真实调用；本次没有执行。

## 可选表迁移依赖

report_versions 保留：id bigint PK（旧 report_version_id）、report_id → reports.id CASCADE、version integer ≥1（旧 version_no）、title varchar(1000)、content text、sections/citations/quality_issues JSONB 数组、model_snapshot JSONB 对象、source varchar(32)、operator_id → users.id SET NULL、operator_name varchar(64)、created_at timestamptz（旧 create_time）。UNIQUE(report_id,version)。原历史内容不能丢弃，需映射原时间语义。

model_calls 保留：configuration.PipelineModelCallAudit 定义为最终源：id varchar(64) PK；task_id → generation_tasks.id SET NULL 可空；model_id → ai_models.id RESTRICT 必填；capability text_generate/image_generate；status success/failed；duration_ms ≥0；input_tokens/output_tokens 可空非负；error text 可空；created_at timestamptz。索引 (model_id,created_at)、(task_id,created_at)。已发送给迁移代理 01a1710f-71ac-7691-b3c3-dbbddc883345。

个人聊天已按用户决定移除，不保留 chat_settings；统一模型配置仅服务业务生成。

## 验证

专属离线命令（backend 目录）：

    PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_research_simplified_20261025.py -q

已同步旧测试 test_digest_schedule_service.py、test_digest_selection_policy.py、test_research_workspace.py、test_material_security_gate.py、test_pipeline_template_service.py、test_research_model_generation.py。以上六个加专属新测试合计 81 项通过。另将 test_pipeline_domain_service.py 完整迁到直接领域服务，37 项通过，保留编码提取、DOCX/PDF 限制、扫描、所有权、下载、删除级联、版本/修订冲突、历史恢复、任务快照/取消/幂等、来源读取/手动采集入队等实际契约；不再导入共享旧 PipelineDao 或旧 facade。旧审批/发布/fallback 假成功断言移除。八个文件合跑最终为 118 项通过；外部 socket connect 被阻断时，全量 tests collect-only 退出码 0，无收集错误（只有既有 Starlette 弃用告警）。已通知 Galileo 删除旧 facade 架构路径要求。

测试只建立内存 SQLite，PostgreSQL CHECK/复合 FK 使用离线 DDL 编译及结构断言；替身 HTTP Transport 验证协议与图片解码，禁止 socket connect。跨域模型聚合入口在测试内隔离，因此测试通过不代表整应用、PostgreSQL 并发锁、真实扫描器或真实模型验收。

完整 Ruff 规则仍有未补齐的类型注解等风格项；本次单独运行 F/I 检查与格式化，并运行 compileall。不要将这项描述成全量 Ruff 通过。

后续诊断补齐：test_ai_model_service.py 改为规范模型及 MockTransport 真实网关契约；test_material_parse_scheduler.py 改为 MaterialDao、内存库认领/恢复及安全门；test_report_exports.py 改为 report_assets 快照与真实 PDF 文件字节/本人权限/受控存储，未恢复已删除 file_hash 列；test_published_template_api.py 识别角色权限，普通用户管理返回403、已删除发布接口返回404。上述四个文件27项通过，与先前118项及模型控制器权限7项合跑最终152项通过。
