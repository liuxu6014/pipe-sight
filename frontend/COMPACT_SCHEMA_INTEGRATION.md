# 精简方案前端交接（2026-10-25）

## 浏览器验收入口

- 管理员模型配置：`/pipeline/model`，路由名 `PipelineModel`，页面标题“模型与类别提示词”。同页两个标签分别管理模型和类别提示词。
- 模板配置与直接选模型：`/pipeline/template`，路由名 `PipelineTemplate`。
- 旧后台 `/ai/model` 组件复用相同模型管理页；首选 `/pipeline/model`。
- 隔离库联调须将前端进程的 `VITE_BACKEND_TARGET` 指向 `http://127.0.0.1:19099`。Vite 默认目标仍为 9099；本次未改现有进程或重启正式服务。页面路由属于前端 origin，19099 是 API 端口。

仅修改 frontend 内的页面、接口、工具及前端测试。后端、数据库、真实采集及模型调用不在本次执行范围。沿用现有门户布局，保留导航紧凑化、列表与资料篮等已有用户修改。

## 已采用接口

- 类别：`GET/POST /pipeline/categories`，`PUT/DELETE /pipeline/categories/{id}`。写入 `name,prompt,modelId,appliesTo,sortOrder,isEnabled`；默认 `all,0,false`。未配置模型不可启用。按管理员角色展示操作，与后端 ADMIN 约束一致，不依赖新增权限记录。
- 模型：沿用 `GET /ai/model/all`、`POST/PUT /ai/model`。同一管理组件供 `/pipeline/model` 和旧 `/ai/model` 使用；写入能力数组 `capabilities`、`parameters` 与既有 camelCase 模型字段。`image_input` 不代表 `image_generate`。仅保存配置，前端已移除连通测试按钮。
- 模板：`GET/POST /pipeline/templates`、`PUT /pipeline/templates/{id}`。写入严格为 `name,purpose,prompt,description,modelId,imageModelId,sections,imageConfig,isEnabled`，没有发布审批请求。普通用户仍用 `GET /pipeline/templates/published?category=research|digest` 获取启用模板。
- 模板列表读取 `modelConfigured/imageModelConfigured`。NULL 模型不阻止浏览或选择模板；提交生成、创建自动计划前提示缺配置并停止请求。通用 digest 模板可用于日报、周报、月报。
- 来源：沿用 `GET/POST /pipeline/sources`、`PUT/DELETE /pipeline/sources/{id}`。写入 `name,type,url,adapter,cron,timezone,config,modelId,isEnabled`，`type=website|wechat|paper`。DELETE 表示停用；启用本身不触发采集。
- 采集：沿用 `GET /pipeline/tasks`、`POST /pipeline/tasks/{sourceId}/run`、`GET /pipeline/tasks/runs/{runId}`、`POST /pipeline/tasks/runs/{runId}/stop|retry`。入队及重试带 `requestId`。后端按已确认约定委托新 `/pipeline/collection` controller 服务，不读取旧数据库结构。
- 运行列表接受 camelCase，兼容旧字段别名。停止以实际响应 status 为准；stopping 只提示已请求停止，3 秒刷新直到终态。刷新失败保留现有状态、显示错误并继续重试；离开页面清理定时器。重试仅针对 failed，详情可跳转 parentId 查看原记录；cancelled 不原地重开。

## 页面与数据规则

模型页新增类别提示词管理，模板直接选择文本/图片生成模型。后台导航、首页与情报查询移除人工审核、独立治理、旧过滤及交接入口；旧治理/过滤组件及其过滤结果工具已物理删除，不保留退役说明页。旧 route/promptversion/governance/review/handoff API 包装已移除。

论文列表不再提供全文状态筛选，详情无全文标签、iframe、全文预览或获取动作；历史全文字段不进入论文归一化结果或资料篮新快照。仅用摘要核验论文选材，使用真实发表日期，保留年/月精度。新闻正文优先使用中文正文；website/wechat 来源分别筛选。安全和资料访问拒绝仍阻断选材，人工审核字段不再作为可用性门槛。文件 ready 状态可用；editedText 为有意空字符串时不回退提取正文。

## 验证与边界

使用 `npm test` 与 `npm run build:prod`。新增 compact-schema 与生成页实际 Vue setup 测试全部注入本地接口桩，测试未发真实采集、生成或调度请求。覆盖类别启用约束、能力筛选、canonical 模板保存、未配置模型、通用简报模板、采集停止状态及轮询清理、失败重试、来源停用保存和失败回滚。

最终结果：`npm test` 310/310 通过；`npm run build:prod` 通过（16.98 秒）；`git diff --check -- frontend` 通过。新增测试为 `tests/compact-schema.test.js`，既有论文阅读、导航、权限、模板及选材测试已按本轮确认规则调整。

## 浏览器验收反馈与配图契约补充

- 已消除 `/pipeline/reports` 残留：旧命名 wrapper 也请求 `/pipeline/research/reports`，导出使用 `/pipeline/research/reports/{id}/export`。门户 hydrate 只请求一次统一报告列表，供科研报告与简报共享；失败状态仍如实显示，不吞掉错误。
- `/portal/research/reports/{id}/diagram` 改为实际配图查看页。读取 `GET /pipeline/research/reports/{id}/diagram` 返回的 `{reportId,images:[{id,status,position,url,error}]}`，不再使用默认节点图、本地保存或旧 PUT 图形占位接口。
- 图片通过带鉴权的 `GET /pipeline/research/assets/{id}/download` 获取 Blob，不直接把需要 Authorization 的 API 地址交给 img。支持已生成图片展示/下载、排队与生成中自动刷新、逐图错误及 `POST /pipeline/research/assets/{id}/retry` 独立重试；离开页面或切换账号释放图片 URL 并阻止旧响应回显。科研报告与简报编辑页均有“查看配图”入口。
- 管理员 Provider 选项明确限制为 `openai/openai-compatible/compatible/deepseek`；其他服务商必须选 compatible 并填写兼容端点。模板管理支持图片模型、启用开关、数量和提示词；生成页请求配图时校验图片模型，默认跟随模板设置。
- 论文底部重复说明和“论文来源页面”链接已删除。优先顶部 DOI，无 DOI 时顶部显示直接 URL；侧栏统一“关联新闻资讯”，保持原布局。
- 此批最终验证：`npm test` **319/319**；`npm run build:prod` **通过，15.43 秒**；`git diff --check -- frontend` 通过。新增 `tests/report-images.test.js` 使用本地桩验证图片字节读取、刷新、重试、失败、账号隔离和 URL 释放；未执行真实采集或模型调用。

登录与门户列表的既有测试纳入完整测试运行；这不代表迁移中的真实后端已完成登录、采集进程退出或模型生成验收。后端联调应继续核对上述 DTO 与委托路径；目前没有额外待定的新接口。

## 管理菜单退役最终映射

本轮只改前端，没有修改 menus/role_menus。以下历史 ID 来自代码中的菜单种子；迁移端须结合实际 component/perms 精确匹配，不按大范围 ID 或 system/monitor 父目录删除。

| 历史 ID / 匹配条件 | 迁移处理 |
| --- | --- |
| 1301，component=pipeline/governance/index，path=/pipeline/governance | 退役页面菜单及角色关联；前端组件文件已删除 |
| 1302/1303，pipeline:governance:sync/operate；1301 的 pipeline:governance:list | 退役按钮与权限关联 |
| component=pipeline/filter/index 或 path=/pipeline/filter（ID 按实际记录定位） | 退役旧过滤管理菜单；前端组件、filterResult 工具与专属测试已删除 |
| 2015–2018，pipeline:prompt:list/save/test/publish | 退役旧 Prompt 版本流程按钮 |
| 2021，pipeline:template:publish | 退役模板发布审批按钮，保存及启停均使用 pipeline:template:save |
| 2026–2028，pipeline:review:list/operate/reprocess | 退役人工内容审核按钮 |
| 2014，pipeline:report:publish | 退役独立发布/撤销按钮；本轮已删除报告管理页对应 UI、处理函数及 publish/unpublish API 包装 |
| 2009，component=pipeline/model/index，path=model（完整 /pipeline/model） | 保留并改名“模型与类别提示词”；路由名 PipelineModel，复用同一组件，不建类别独立组件 |
| 2008，pipeline/template/index | 保留，直接保存模板和选择正文/图片模型 |
| 2002/2003、2004/2005、2006 | 分别保留情报查询/详情、来源/任务、报告管理 |

必须保留 ai:model:list/query/add/edit（页面读取模型依赖 query），pipeline:template:list/save（2019/2020）、pipeline:source:list/save（2022/2023）、pipeline:task:list/run（2024/2025）、pipeline:report:list/export。类别 CRUD 当前按 admin 角色控制，不需要新增 pipeline:category:* 按钮权限。2025 描述改为“运行、停止与失败重试”，删除外部交接文字。独立模型路由/外部交接菜单若在快照存在，按具体 component/perms 定位退役，勿扩大到通用系统菜单。

前端 permission store 的旧组件拒绝注册和 RETIRED_PIPELINE_PATHS 仅用于阻止尚未清理的后端快照重新注册死入口；它们不是保留的业务路由或实现。未修改无关 system/monitor 菜单代码。

本轮验证：317/317 前端测试通过（删除旧过滤结果的 2 个专属测试，退役断言改为检查文件及 API 确实不存在）；生产构建与差异检查结果见本轮交接。

## 用户确认移除个人聊天

个人 AI 聊天页面、消息组件、API 包装、专用图标、Monaco shim/alias 及 9 项专属直接依赖已删除，npm 离线同步裁掉 220 个包；统一模型配置、类别与 Provider 表单、报告/简报/配图生成保留。系统/角色共用组件和依赖未扩大删除。最终 29 表由数据库迁移代理验收，本代理未改库。

Confucius 精确菜单/API 清单与前端删除项见 [个人聊天退役交接](./PERSONAL_CHAT_RETIREMENT_CONFUCIUS.md)：历史菜单 119、component=ai/chat/index、完整路径 /ai/chat、权限 ai:chat:list；不连带删除 ai:model:* 或 system/monitor 菜单。最新前端验证 317/317，通过生产构建（7.18 秒）与差异检查。

## 业务编号 bigint 适配（2026-10-25）

本轮只修改 frontend 和两份指定 output Markdown；未改后端、未连接真实数据库、未执行采集或模型调用。数据库迁移状态仍为“迁移中”，最终 29 表 / 340 字段 / 35 外键由主迁移验收。

- 新增 src/utils/portal/businessId.js 和 src/api/pipeline/request.js，集中按十进制字符串校验/归一业务编号，拒绝旧 UUID、非法编号及已丢精度的数字；不转换 requestId、execution_token 或用户文字。API 路径不变，输入/输出业务 ID 为十进制字符串，支持 9007199254740993 等值。
- intelligence/categories/assets/manuscript/model API、门户 store、资料篮与选材 helper、详情路由、科研报告/简报创建同步适配。模型下拉选项与类别/模板绑定 ID 统一字符串；sys_* 账号权限接口未更改。
- 模板依据实际返回列表选择，删除 template-01/02 等硬编码映射与模拟模板列表。旧模板 ID 不静默改选；旧资料 UUID 不发详情/生成请求，明确提示“业务编号已升级，请重新选择资料或模板；已填写的表单和正文已保留。”重载模板保留已写需求、标题和大纲正文。
- Set 按字符串区分相邻大整数，跨页勾选保留，仅取消当前页不影响其它页；旧 UUID 资料篮删除/清空操作校验失败时保留条目并提示。
- 新增 tests/business-id.test.js，并更新相关列表、模板 hydration、选材、会话隔离、路由和 wrapper 数字 fixtures。最后一轮 npm test **326/326**，npm run build:prod **通过（7.39 秒）**，git diff --check -- frontend 通过。测试全部本地桩，无真实 API/数据库或供应商调用。

后端联调门槛：12 表共用全局序列、单列/复合外键及 JSON 快照中的旧 ID 全量映射；收发十进制字符串。前端验证不代表本轮数据库已切换或真实生成已验收。

### numeric 后端启动后的独立前端补验

未重复主代理负责的登录、HTTP 详情/资料篮/cursor 验收，未改 Vite 指向或使用临时账号。新增深层业务引用校验：编辑器 citations.sourceId、复制配置 templateId/selectedItemIds 同样禁止旧 UUID；章节/引用本地序号、请求令牌及正文不转换。报告与简报自动保存回显编号升级提示，保存失败保持标题、章节和引用文字，并继续阻止未保存离页。

补充真实大整数模板列表驱动选择、JSON 缓存还原后相邻大整数不合并、旧缓存需显式重选、嵌套引用拦截和两种编辑器正文保留测试。最新 npm test **331/331 通过**，npm run build:prod **通过（7.33 秒）**，git diff --check -- frontend 通过。代码变更为 src/utils/portal/businessId.js、ReportEditorView.vue、DigestEditorView.vue；测试为 business-id、editor-autosave、portal-evidence-input。未发生真实 HTTP、数据库、采集或模型调用；本轮数据库状态仍待主迁移验收。

### 旧详情书签及旧模板 query 迁移体验

路由在详情组件解析前拦截非 decimalstring 编号，覆盖新闻、论文（含 curated-paper-UUID）、资料、任务、报告/配图及简报，replace 到对应列表并提示“编号已更新，请从列表重新打开。”不向 numeric API 提交旧编号；创建页不重定向，表单继续保留。有效大整数详情地址按原字符串通过。

科研报告与简报创建均保留 URL template 原值；旧模板或同页 query 变化不默认选择另一模板，提示重选并拦截生成。简报切换日报/周报/月报时也不覆盖无效旧模板；用户关键词、需求和章节正文保留。相关文件为 src/utils/portal/legacyRoute.js、src/router/index.js、两种 CreateView，新增 tests/legacy-detail-route.test.js 并补充选材页回归；路由抽取测试同步适配 guard 注册。

最终 npm test **334/334**；生产构建 **通过（7.60 秒）**；git diff --check -- frontend 通过。回归使用 Vue memory router 与本地桩，证明旧详情不能进入详情解析/请求阶段、创建表单无重定向、JSON wire 大 ID 不经 Number；未重复主代理真实 HTTP 验收，未改后端或数据库。
