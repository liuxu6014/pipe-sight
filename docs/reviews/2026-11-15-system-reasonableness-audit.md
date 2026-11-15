# PipeSight 系统合理性审查（2026-11-15）

审查基线：`main@fd56b3487b7dabe335a5266a9dddf43a0163bd31`。本次审查没有修改产品代码、模型绑定、用户资料或任务，没有提交或推送。

## 结论

业务方向和主体分层合理：公开情报、个人资料、个人模板、生成任务与成果有明确边界；报告的基本信息→资料→模板→大纲流程也合理。但是，目前还不能认定为“权限闭环且可稳定交付”的系统。已确认 **10 项问题：4 项 P1 优先修复，6 项 P2 完善**。最需要先解决的是文件下载旁路、内容处理静默跳过、报告大纲缺少硬校验，以及界面承诺的引用检查没有对应执行。

P1 表示影响权限边界或核心生成契约，建议作为下一次交付前置条件；P2 表示具体业务断点或规模、运行保障缺口。这里没有把缺少线上压测证据等不确定事项冒充已发生故障。

## 范围、方法和证据边界

- 阅读鉴权入口、用户归属查询、模板初始化/删除恢复、采集处理/翻译、模型用途配置、生成/引用/导出、持久任务恢复和部署配置；沿调用链检查，不只看最新提交。
- OCR 使用本地主机审查模式，只做文件与规则解析，没有调用远端审查模型。最新提交列出 24 个文件，其中 14 个可审查文件全部覆盖；两份生成的 schema JSON 做结构化比较，变化仅在 templates 表。其余 10 个为工具默认排除的测试/文档，未伪称逐行审查；相关全量测试结果另行复核。
- 实际查看普通用户模板、新建简报、新建报告、实时全局搜索，以及管理员模型用途、数据源管理。管理员与普通用户会话均有可见页面证据。本次没有重新提交收费生成任务，也没有下载真实私有文件。
- 390px 宽度检查首页与报告第一步，未发现页面横向溢出；这不等于所有页面都完成手机验收。已恢复原浏览器尺寸。
- 使用临时文件、内存替身进行 6 类安全复现，不操作真实用户数据、不调用外部模型：通用下载、处理模型缺失、模板周期、并发翻译、大纲缺失、队列并发。
- 复核当前代码已有验证记录：后端 1,857 项通过，前端 662 项通过，均无跳过，前端生产构建通过。本次产品代码未变，没有为审查重复跑整套。这些测试不能覆盖下述全部业务契约。

审查证据位于 `.runtime/system-audit-20261115/`：`reproduce.py`、`reproductions.json`、`outline-reproduction.json`、`queue-reproduction.json`、`runtime-summary.json`、`ocr-preview.json`、`ocr-rules.json`、`coverage.json` 和页面截图。

## 优先修复

### F01 · P1 · 通用资源下载绕过资料所有者与安全扫描

**触发**：已登录普通用户知道某个上传文件的合法存储路径，调用通用资源下载接口。

专用资料下载经过所有者校验和扫描；但 `/common/download/resource` 没有接收当前用户，服务只验证目录、文件名时间戳/机器码/随机码和文件存在，随后直接返回字节。资料上传使用同一个上传根目录和符合这些规则的文件名。因此“资料库接口隔离正确”并不能阻止从通用接口取同一个文件。这里不是匿名任意文件读取，也不意味着已经发现真实泄露；问题前提是已登录并取得合法路径。

**复现**：在临时目录用真实 FileStorageService 写入一份无敏感内容的测试文件，再由通用下载读取，未提供所有者、资料 ID 或扫描上下文，成功获得相同字节。未读取任何实际私有资料。

**建议**：把头像等公开资源与私有资料分开存储/下载；通用下载拒绝私有命名空间；私有文件只通过资料 ID、当前用户和扫描门访问。补充跨账号、未扫描/隔离文件的跨接口回归测试，不能只测路径穿越。

**代码**：[backend/src/app/infrastructure/api/file_controller.py:73](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/infrastructure/api/file_controller.py:73)；[backend/src/app/infrastructure/services/file_transfer.py:85](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/infrastructure/services/file_transfer.py:85)；[backend/src/app/library/api/controller.py:54](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/library/api/controller.py:54)。

**验收**：账号 A 的文件，B 即使知道存储路径也得不到内容；所有入口对隔离或未扫描文件执行相同拒绝规则。

### F02 · P1 · 未配置内容处理模型时静默跳过过滤、分类、摘要和实体抽取

freeze 在没有统一处理模型时返回 processing_model=None；prepare 遇到该值，将条目标记成 `(None, False)`，即没有类别、也没有处理失败。持久化层因此允许继续保存，而不是保持待处理或给出阻断。此时用户要求的“处理时同时生成摘要和实体”没有执行，采集却可能成功。

**当前环境**：管理员用途页确实显示内容处理模型尚未选择。现有 6 篇新闻、3 篇论文均未分类；但本地没有 collection_runs 记录，不能把这些历史数据归因于本缺陷。

**复现**：输入一条文章和 processing_model=None，得到无失败标记、无新增摘要的原记录。

**建议**：明确区分“仅保存原始采集数据”和“完成内容处理”。若当前业务必须处理，则入队前阻断未配置模型；若允许原始落库，应有待处理状态、补处理队列和可见提示，不能作为已处理情报使用。

**代码**：[backend/src/app/intelligence/services/content_processing.py:66](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/intelligence/services/content_processing.py:66)；[backend/src/app/intelligence/services/content_processing.py:118](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/intelligence/services/content_processing.py:118)；[backend/src/app/intelligence/services/collection_persistence.py:204](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/intelligence/services/collection_persistence.py:204)。

**验收**：移除处理模型后，不能产生“采集成功且处理完成”的假象；恢复配置后可以补处理，摘要/实体/类别结果可追溯。

### F03 · P1 · 两种科研报告没有核对确认的大纲

科技项目需求表有章节顺序校验；科研需求报告和技术路线报告则直接进入通用规范化。通用完整性检查只检查非空、空章节、引用编号等，不比较已确认的章节列表或篇幅要求。模型少生成章节、改成别的章节，仍可能被标记完成。

**离线复现**：快照要求“研究现状、研究目标、研究内容”三章，返回只有“无关小节”的短文及一处有效引用；normalize_task_report 与 validate_generated_article 都接受。这个复现说明可接受的错误输出，不表示本次真实模型已经生成该内容。

**建议**：所有报告类型统一验证确认大纲的章节集合和顺序；篇幅采用合理容差和明确警告。缺章应明确失败或允许用户修正，不能自动附参考资料后直接视为完整成品。

**代码**：[backend/src/app/research/services/report_content.py:343](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/research/services/report_content.py:343)；[backend/src/app/research/services/report_content.py:80](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/research/services/report_content.py:80)；[backend/src/app/research/services/execution.py:65](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/research/services/execution.py:65)。

**验收**：缺章、错序、超短正文有确定结果；满足确认大纲的正常文本仍能生成、编辑、导出。

### F04 · P1 · “引用完整性检查”勾选项没有对应检查行为

新建报告默认勾选“提交前执行引用完整性检查”。后端保存 requested 值，但在任务完成时直接将 citation.status 写为 not_run、reason=normalization_only；quality 同样是 not_run。已有文稿结构与引用编号检查，但不等于该选项所承诺的独立检查，勾选与取消也没有相应的检查分支。

**建议**：定义引用完整性范围，例如每处引用是否对应来源、未解析引用、孤立来源和位置映射，接入确定的检查结果。若暂不实现，应移除或禁用该承诺，并在成果页明确“仅完成格式与编号校验，未完成引用支持性/事实核验”。不能把事实真实性交给一个布尔开关承诺。

**代码**：[frontend/src/views/portal/pages/ResearchCreateView.vue:119](/Users/liuxu/Documents/ChatGPT/管网/frontend/src/views/portal/pages/ResearchCreateView.vue:119)；[backend/src/app/research/services/execution.py:83](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/research/services/execution.py:83)。

**验收**：选项状态与实际执行、版本化结果一致；修改正文后不能继续显示旧版本已通过。

## 业务与运行完善

### F05 · P2 · 自建简报模板的适用周期依赖名称

内置周/月报用 preset_key 固定周期，改名不会失效，这部分合理。但自建模板仍仅支持少数固定全名。新建简报默认“通用简报模板”可用，用户正常改成“腐蚀技术周报”并保存后，digestCadence=None，生成时被排除/拒绝；表单没有周期选择项，也没有提示这个命名限制。

**复现**：通用简报模板可用于 weekly；腐蚀技术周报不可；带内置稳定键的改名周报仍可。

**建议**：增加明确的适用周期字段（周报/月报/通用），在创建、编辑、选择和校验中统一使用；名称只负责展示。已有内置键用于迁移，不应继续作为全部业务类型的替代字段。

**代码**：[backend/src/app/intelligence/services/templates.py:50](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/intelligence/services/templates.py:50)；[frontend/src/views/pipeline/template/index.vue:67](/Users/liuxu/Documents/ChatGPT/管网/frontend/src/views/pipeline/template/index.vue:67)；[frontend/src/views/pipeline/template/index.vue:168](/Users/liuxu/Documents/ChatGPT/管网/frontend/src/views/pipeline/template/index.vue:168)。

### F06 · P2 · 数据源管理只允许新增和配置公众号，网站/论文没有完整管理路径

管理员页面能新增公众号、编辑 RSS 和设置频率。新闻网站/论文仅有启停，频率显示“—”；代码明确拒绝它们的编辑。当前又没有论文数据源，因此管理员无法仅用网页把论文采集链路配置完整。现有网站来源的 adapter 为 manual，真实注册表不支持该值，离线校验返回“适配器未注册”；启用时会被校验拒绝，网页又不能修改网站适配器。外部爬虫来源只做目录与启停本身是合理设计，但内部来源和历史配置需要可修正的路径。后端有适配器和接口，不代表网页管理流程已经闭环。

**建议**：提供按支持适配器受控配置网站和论文来源的入口、频率与手动试采/错误结果；不支持的类型应明确说明配置方式。不同来源的能力可以不同，但不能让“启用”看起来等于“已具备可运行计划”。

**代码**：[frontend/src/views/pipeline/source/index.vue:7](/Users/liuxu/Documents/ChatGPT/管网/frontend/src/views/pipeline/source/index.vue:7)；[frontend/src/views/pipeline/source/index.vue:26](/Users/liuxu/Documents/ChatGPT/管网/frontend/src/views/pipeline/source/index.vue:26)；[frontend/src/views/pipeline/source/index.vue:191](/Users/liuxu/Documents/ChatGPT/管网/frontend/src/views/pipeline/source/index.vue:191)。

### F07 · P2 · 自动任务遇到永久配置错误会每轮扫描重试

模板停用或软删除不检查正在使用它的自动计划。计划派发时取不到启用模板，失败后保留原 next_run_at，仍保持启用；扫描循环约每 5 秒再次派发。failure_count 对同一到期点不重复累加，避免了统计膨胀，但未解决重复验证与异常日志。模型配置错误也会走同一路径。

**影响**：用户以为只是删除模板，自动任务却持续失败；长期配置错误没有退避或挂起状态。当前本地 4 个计划均停用，没有在本地制造该持续失败。

**建议**：停用/删除模板时列出受影响的活动计划；对明确的配置错误挂起并提示修复，瞬时故障采用退避与 next_retry_at。保留原业务周期，修复后由用户决定补跑。

**代码**：[backend/src/app/intelligence/services/templates.py:260](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/intelligence/services/templates.py:260)；[backend/src/app/intelligence/services/templates.py:271](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/intelligence/services/templates.py:271)；[backend/src/app/research/services/digest_schedules.py:632](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/research/services/digest_schedules.py:632)；[backend/src/app/research/services/digest_schedules.py:689](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/research/services/digest_schedules.py:689)；[backend/src/app/research/tasks/research_job_scheduler.py:166](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/research/tasks/research_job_scheduler.py:166)。

### F08 · P2 · 持久任务恢复缺少明确并发上限和用户间公平性

任务查询一次取出全部待执行任务，循环为每条创建 asyncio.Task，没有全局模型并发池、每用户在途上限或查询批量上限。已有任务租约解决重复认领，模型 daily_limit 可选控制当天调用数，但两者都不等于瞬时并发控制。

**离线复现**：内存提供 50 条任务，一轮派发并同时启动 50 个替身任务；没有真实模型调用或压力测试。

**建议**：数据库批量领取+受控工作池，限制全局/模型/用户并发，区分长任务和导出，设置排队上限并公开状态。再通过真实负载测试确定数值，不能据本复现声称具体机器可承载多少用户。

**代码**：[backend/src/app/research/repositories/research_repository.py:159](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/research/repositories/research_repository.py:159)；[backend/src/app/research/tasks/research_job_scheduler.py:48](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/research/tasks/research_job_scheduler.py:48)；[backend/src/app/research/services/model_generation.py:48](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/research/services/model_generation.py:48)。

### F09 · P2 · 多处分页只在前端切片，后端仍加载全部资料/报告

个人报告、管理员成果及个人资料的仓储查询没有数据库分页；前端报告列表把全部数据过滤/排序后 slice。大数据时会传输完整集合，资料接口还会整理正文摘要；页面看起来每页 10 条，不代表后台只读取 10 条。搜索和研究资料选择器已有服务端分页，可以沿用其约定。

**建议**：报告、资料、模板列表统一 page/pageSize/filter/sort，后端只查当前页和所需字段；列表 DTO 不返回全文，详情按需加载。以真实数据集验证排序、总数与翻页，不把小样本速度当容量证明。

**代码**：[backend/src/app/research/repositories/research_repository.py:62](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/research/repositories/research_repository.py:62)；[backend/src/app/library/repositories/material_repository.py:59](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/library/repositories/material_repository.py:59)；[frontend/src/views/portal/pages/ResearchWorkbenchView.vue:144](/Users/liuxu/Documents/ChatGPT/管网/frontend/src/views/portal/pages/ResearchWorkbenchView.vue:144)。

### F10 · P2 · 同一论文的首次并发翻译会重复调用模型

翻译先读取缓存，再调用模型，最后才锁行写入。两个账号或标签页同时首次翻译同一标题/摘要，均可能在缓存为空时进入模型调用。相同 Idempotency-Key 被传给供应商，但应用支持多个兼容端点，不能把端点是否执行幂等当成本系统保证。最后的行锁只防止覆盖，不会合并已发生的调用。

**离线复现**：两个协程请求同一未翻译标题，进入两次模型替身，request_id 相同。没有发生真实重复收费；若供应商有效幂等可能合并计费，但本地仍重复发起请求。

**建议**：按论文+字段+原文哈希合并在途任务，使用独立翻译队列或分布式锁；等待者复用结果，失败后可重试，并保留原文变更检查。

**代码**：[backend/src/app/intelligence/services/collection_translation.py:260](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/intelligence/services/collection_translation.py:260)；[backend/src/app/intelligence/services/collection_translation.py:284](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/intelligence/services/collection_translation.py:284)；[backend/src/app/intelligence/services/collection_translation.py:299](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/intelligence/services/collection_translation.py:299)。

### 上线配置风险 · 专业文件扫描需要单独验证（不计入缺陷数）

docker-compose.pg.yml 的 API/Worker 配置默认 FILE_SCAN_MODE=basic，并有注释说明这是本地验收设置，生产必须切换 external。因此这里不认定生产已误配置，但交付时不能直接照用本地默认。扫描服务明确说明 basic 仅用于开发/验收，只检查常见可执行文件头和大小，无法替代病毒库、压缩包/宏等检查。默认落入此模式时仍会返回 clean，用户只见已解析，容易误判安全能力。

**建议**：正式部署默认 external 且缺失扫描器时保持不可用；启动检查区分开发和正式环境；界面明确显示扫描能力。配置真实扫描器后以无害标准测试样本验证隔离和全部下载入口。F01 应同时修复，否则专用扫描门仍可能被旁路。

**代码**：[docker-compose.pg.yml:109](/Users/liuxu/Documents/ChatGPT/管网/docker-compose.pg.yml:109)；[backend/src/app/system/services/file_scan.py:29](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/system/services/file_scan.py:29)；[backend/src/app/system/services/file_scan.py:109](/Users/liuxu/Documents/ChatGPT/管网/backend/src/app/system/services/file_scan.py:109)。

## 已有合理设计及验证支持

- **个人模板默认复制与隔离**：用户作用域、数据库唯一键、初始化锁和软删除记录配合，改名/删除后不会重复补回；此前双账号/新账号实际验收记录仍在 docs/reports，本次普通账号页面继续显示 10 份，已删除月报没有重现。
- **公开情报和个人资料分开**：选材加载内部文件时按所有者查询，报告/任务写操作也有归属限制。F01 是需要补齐的另一条下载路径，不能因此说所有归属查询都无效。
- **任务快照和编辑保护**：冻结模板/模型/资料；模型身份或端点变化要求重新提交；任务结果不静默覆盖用户已经编辑的成果；报告有版本记录。
- **翻译保留原文**：title_zh/abstract_zh 独立保存，已保存翻译可复用，写入前检查原文是否变化。F10 关注首次并发合并。
- **生成有基础完整性门**：非空、格式、空章节及引用编号检查存在；不应把它们扩大解释为已完成大纲、引用支持性和事实质量审查。
- **界面已有改善**：报告表头排序、个人模板入口、实时全局搜索可见并可用；本次输入“管道”无需点击搜索即返回 9 条结果。390px 首页及报告第一步没有横向溢出。
- **迁移与结构契约**：实际数据库 revision 为 20261115_template_defaults；新旧 schema 结构比较仅涉及 templates 字段与唯一约束，未发现本次迁移静默丢弃历史数据。

## 当前本地运行状态与不能据此推断的事情

只读统计：1 个模型、6 个来源均停用（网站 3、公众号 3、论文 0），collection_runs=0；4 个自动任务均停用；18 个生成任务中 16 个完成、2 个失败。翻译/简报/科研报告绑定了现有 DeepSeek，内容处理未选择，图片模型未接入。这个快照可用于页面和已有成果验收，**不能证明自动采集→处理→定时简报正在持续生产运行**。停用可能是验收保护措施，本次未擅自启用。

`/health/ready` 当前返回数据库和 Redis 均正常；检查不包含独立 Worker 心跳、队列最长等待时间或外部模型可用性。应另设运行监控，避免 API 正常而生成队列停滞时无人知晓。本次未停 Worker 做破坏性故障注入，也未执行线上压测或生产备份恢复。

本次没有调用真实图片模型、重新生成一套周/月报或比对用户 Word 样例的全部页面，因此**不签署最终成品版式与事实质量验收**；那些证据需要在对应真实输出上单独取得。

## 页面一致性观察（不计入上面 10 项）

1. 新闻列表已清理的“官网核验/转载”和“日期未提供”，首页最新内容与全局搜索仍能看到；来源名、日期和空值展示应统一走同一展示函数，原始溯源字段保留。
2. 新建简报尚未填写周期就显示“请选择有效且完整的报告周期”和“重试”，属于未开始操作被当成失败。建议初始状态显示选周期引导，提交/检索后才显示错误。
3. 模型用途页还写“生成日报、周报和月报”，但当前用户流程已经去掉日报。历史读取兼容可以保留，当前可用功能文案应统一。

## 建议收口顺序与完成标准

1. 先修 F01 的所有文件入口权限，再补跨接口安全回归。
2. 修 F02/F03/F04，统一“采集完成、处理完成、生成完成、检查通过”的含义，并绑定实际成果版本。
3. 修 F05/F06/F07，跑一个新用户自建周报模板和一套受控来源/自动任务，验证改名、停用、恢复、补跑。
4. 修 F08—F10，补公平并发、服务端分页和翻译合并；上线前另行核验正式文件扫描与 Worker 监控。
5. 最后做真实成品人工验收：三类科研报告各一份，周/月报各一份，检查章节与提示词、引用定位、导出 Word/PDF、两账号隔离。通过后再用真实多用户负载确定容量。

建议保留现有 Vue/Element Plus 和后端领域分层，围绕以上缺口收口；没有证据支持为本次问题重写整套系统。
