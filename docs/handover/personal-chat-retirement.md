# Confucius：个人聊天退役交接（2026-10-25）

用户已选择“移除未使用的个人聊天功能，只保留业务生成”。本代理仅修改 frontend；最终 29 表由数据库迁移代理核对，本代理未改库、未触发真实采集或模型调用。

## 菜单与权限精确匹配

- 历史菜单 **119**：名称“AI 对话”，parent_id=4，path=chat，component=`ai/chat/index`，完整路由 `/ai/chat`，权限 **`ai:chat:list`**。从 menus 及对应 role_menus 退役。
- 额外快照中若存在同 component、完整路由或 `ai:chat:*` 权限的按钮，逐项核对后随个人聊天退役；不按父目录 4 批量删。
- 不删除 `ai:model:*`。**2009** 继续使用 `pipeline/model/index`，名称“模型与类别提示词”，完整路由 `/pipeline/model`；旧 `ai/model/index` 复用该组件，不是聊天实现。
- `system/*`、`monitor/*`、角色/用户管理及共用 UI 不在聊天退役范围。AI 父目录若仍有模型管理子项，必须保留；前端只裁掉清理后无子项的目录。

## API 退役清单

以下从原前端 wrapper 与流式请求核对，不向这些接口发请求：

| 方法 | 路径 |
| --- | --- |
| GET | `/ai/chat/session/list` |
| GET / DELETE | `/ai/chat/session/{sessionId}` |
| GET / PUT | `/ai/chat/config` |
| POST | `/ai/chat/send`（流式个人聊天） |
| POST | `/ai/chat/cancel`（body.runId） |

仅确认旧前端对应 `ai:chat:list` 菜单权限；其他按钮权限以实际 menus 快照为准，不虚构新权限。

## 已删除前端文件与依赖

- `src/views/ai/chat/index.vue`
- `src/views/ai/chat/components/AiMessage.vue`
- `src/api/ai/chat.js`
- `src/shims/stream-monaco.js` 及对应 Vite alias
- `src/assets/icons/svg/ai-chat.svg`（公众号仍使用的 wechat 图标保留）

直接依赖移除：`markstream-vue`、`stream-markdown`、`stream-monaco`、`mermaid`、`katex`、`shiki`、`uuid`、`@antv/infographic`；开发依赖移除 `vite-plugin-monaco-editor-esm`。它们的源码引用均属于聊天渲染链，infographic 是 markstream 的图形渲染 peer；依赖树由 npm 正常更新 lockfile，不手删共享包。

保留 `@vueuse/core`、Element Plus、Ant Design 等被角色/系统 UI 使用的组件及依赖。统一模型配置、Provider 四选项、模板选模型、报告/简报及 report_assets 图片查看与独立重试均保留。

## 路由行为

不保留个人聊天 UI、API 包装或可注册的聊天路由。permission store 在读取旧后端快照时拒绝 `ai/chat/index` 和 `/ai/chat`，避免数据库菜单迁移前重新注册死入口；这只是退役保护，不是隐藏仍可用的聊天实现。

## 验证结果

- `npm install --ignore-scripts --no-audit --no-fund --offline` 完成，移除 220 个不再需要的包，package-lock 已同步。
- `npm test`：317/317 通过；权限测试包含旧聊天菜单不注册、system/monitor 与模型入口仍保留。
- `npm run build:prod`：通过，7.18 秒。
- `git diff --check -- frontend`：通过。
- 源码残留仅为拒绝旧菜单快照的路径匹配；无个人聊天组件、流式请求或 API 包装。没有写入模型配置、采集或调用模型。
- 当前会话工具未暴露可识别的 Confucius 子会话，交接通过本共享文件提供；不声称已直接发送消息或已完成数据库 29 表验收。
