# 后端维护脚本

脚本按用途归档，不参与 API 启动时的自动导入。安装后端依赖及应用包后，从 `backend/` 目录执行；例如 `uv run python scripts/checks/export_database_dictionary.py --env dev --check`。

| 目录 | 脚本 | 用途 |
| --- | --- | --- |
| `bootstrap/` | `bootstrap_real_pipeline.py`、`bootstrap_deepseek_route.py`、`seed_dev_data.py` | 初始化来源、模型路由或开发种子数据 |
| `imports/` | `import_curated_content.py`、`import_wechat_feeds.py` | 导入受控内容和公众号数据 |
| `backfills/` | `complete_authorized_articles.py`、`cleanup_low_quality_articles.py` | 补充授权文章、清理低质量文章 |
| `backfills/` | `normalize_manuscript_templates.py`、`update_project_demand_template.py` | 修正已有模板数据 |
| `checks/` | `export_database_dictionary.py`、`verify_schema.py` | 导出/检查实际数据库结构 |
| `papers/` | `prepare_licensed_papers.py`、`prepare_publisher_paper_previews.py`、`render_publisher_pdf_page_images.py` | 授权论文资源与预览辅助工具 |
| `migrations/` | `migrate_wechat_rss_sources.py` | 历史公众号适配器数据迁移 |
| `migrations/` | `rehearse_schema_chain.py` | 仅供隔离演练库使用的历史迁移链工具 |

正式 schema revision 仍在 `backend/alembic/versions/`，不能用本目录代替 Alembic。

这些脚本并非全部只读或默认 dry-run。初始化、导入、回填、清理及演练工具可能修改数据，运行前需确认目标环境、适用数据和备份要求；以各脚本参数和说明为准。`verify_schema.py` 会连接实际配置库，不属于离线目录检查。此次目录整理不执行以上数据工具。

脚本的文件清单、论文资源和输出仍指向原有的 `backend/data/`、`backend/vf_admin/`、根目录 `.runtime/` 等位置。历史论文辅助工具保留用于追溯，不意味着用户端已启用论文全文功能。

## 科研报告分类模板

`bootstrap/seed_research_templates.py` 读取 `data/templates/research-presets-v1.json`，为科研需求、技术路线和科技项目需求表三类各提供 3 份具体模板。模板包含独立正文提示词、章节说明和篇幅规划；模型不自动选择，配图默认关闭。

部署时先备份数据库并执行 `alembic upgrade head`，再从 `backend/` 目录预览和追加：

```sh
PYTHONPATH=src:. .venv/bin/python scripts/bootstrap/seed_research_templates.py
PYTHONPATH=src:. .venv/bin/python scripts/bootstrap/seed_research_templates.py --apply
```

默认仅预览；`--apply` 仅追加缺少的模板，以报告类型和模板名称匹配，不覆盖已有提示词、章节、模型或启停状态。已有通用模板需在模板管理中明确绑定报告类型，不从名称猜测。新建报告的基本信息、选材、模板和大纲按四步完成；项目描述及本次写作要求随任务快照保存。
