# 报告正文与引用格式

适用于后续新生成的科研报告，以及页面阅读、保存后的报告和 Word、PDF 导出。

## 统一规则

- 正文自然段首行缩进两个字符；标题和文末参考资料不使用正文缩进。
- Word 和 PDF 每页底部居中显示阿拉伯数字页码，从第 1 页连续编号；Word 使用自动页码域，不把页码写入正文。
- 正文引用采用连续序号，如 `[1]`、`[2]`，显示为右上角角标。
- 引用放在对应句末、句号之前；分号分隔的独立分句在分号前标注。句中或句首的引用统一移到对应句末。
- 同一句或独立分句内，同一资料只标注一次；不同句子仍可分别引用同一资料，不跨句删除引用。
- 正文引用后不附加“新闻正文、论文摘要、来源日期”等括号说明。普通解释性括号保持原样。
- 文末参考资料保留完整来源、日期和链接，序号为普通文字，不上标、不移动。
- 正文保存为普通 Markdown，不把 HTML 上标或手工缩进空格写入模型输出。

## 执行位置

1. `backend/src/app/research/services/model_generation.py`：在所有模板提示之后追加统一正文与引用要求，要求使用选材的类型和 ID 标识证据，不编造引用。
2. `backend/src/app/research/services/report_content.py`：生成成功或应用任务结果时，先映射真实选材到连续序号，再调用规范化函数；清理后的正文与章节一同保存。生成任务的原始模型输出保留，方便追溯。
3. `backend/src/app/research/services/citation_format.py`：后端公共规范化函数；保护参考资料、Markdown 链接和代码，清理引用说明、调整位置并去重。
4. `frontend/src/utils/portal/reportDocument.js`：页面阅读和编辑保存使用对应规则；正文使用上标展示，首行缩进由页面样式设置。
5. `backend/src/app/research/services/exporters.py`：Word 使用原生上标与两个字符的首行缩进，PDF 使用上标排版与两个正文字号宽度的首行缩进；两者复用后端引用规范化函数。

更换模板或文本模型不取消这些平台规则。只调整排版与引用位置，不补造事实、来源或证据编号；不批量覆盖已有报告或历史版本。

## 回归检查

- `backend/tests/test_report_content_normalization.py`：Markdown、JSON 模型输出规范化及幂等性。
- `backend/tests/test_research_model_generation.py`：网关提示要求、后台生成入库、章节快照、原始输出保留及导出快照。
- `backend/tests/test_report_exporters.py`：Word 原生上标、首行缩进、PDF 版式和参考资料保留。
- `frontend/tests/report-citation-style.test.js`、`frontend/tests/report-document.test.js`：页面角标、句末引用、去重、保存与重载。
