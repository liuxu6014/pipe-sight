import test from 'node:test'
import assert from 'node:assert/strict'
import { reportCitationParts, cleanReportCitationNotes, buildReportMarkdown } from '../src/utils/portal/reportDocument.js'

test('body citation notes are removed, but ordinary parentheses and bibliography details survive', () => {
  assert.equal(cleanReportCitationNotes('成果[3]（新闻正文，2025-02-09）。假设（待验证）。'), '成果[3]。假设（待验证）。')
  assert.equal(cleanReportCitationNotes('摘要[1](论文摘要，2024-03)。'), '摘要[1]。')
  assert.equal(cleanReportCitationNotes('[1] 文献（论文摘要，2024）', '参考资料'), '[1] 文献（论文摘要，2024）')
})

test('only actual citation markers become superscripts; reference rows stay baseline and text stays escaped', () => {
  const parts = reportCitationParts('<img onerror=alert(1)>成果[2][3]（新闻正文，2025-02-09），[2026]不是引用。', '正文', 5)
  assert.deepEqual(parts.filter(part => part.citation).map(part => part.text), ['[2]', '[3]'])
  assert.ok(parts.some(part => part.text.includes('<img onerror=alert(1)>')))
  assert.ok(!parts.some(part => part.text.includes('2025-02-09')))
  assert.deepEqual(reportCitationParts('[1] 文献', '参考资料', 5), [{ text: '[1] 文献', citation: false }])
})

test('saved Markdown retains citation markers without source-note parentheses or HTML', () => {
  const content = buildReportMarkdown({ title: '报告', sections: [{ title: '正文', content: '成果[3]（新闻正文，2025-02-09）。' }] })
  assert.ok(content.includes('成果[3]。'))
  assert.doesNotMatch(content, /新闻正文|<sup/)
})

test('an introductory evidence marker is moved to sentence end without duplicating it or losing other citations', () => {
  assert.equal(cleanReportCitationNotes('[2]新闻正文报道，系统已上线[2]。'), '新闻正文报道，系统已上线[2]。')
  assert.equal(cleanReportCitationNotes('[2]新闻正文报道，系统已上线。'), '新闻正文报道，系统已上线[2]。')
  assert.equal(cleanReportCitationNotes('[2]和[3]新闻正文报道，系统已上线[3]。'), '新闻正文报道，系统已上线[2][3]。')
  assert.equal(cleanReportCitationNotes('已有研究[2]。另一项研究[2]。'), '已有研究[2]。另一项研究[2]。')
  assert.equal(cleanReportCitationNotes('新闻报道[2]；[4]摘要提到检测[4]。'), '新闻报道[2]；摘要提到检测[4]。')
  assert.equal(cleanReportCitationNotes('结合[2]新闻正文中的报道[2]和[4]摘要中的方向[4]，提出建议。'), '结合新闻正文中的报道和摘要中的方向，提出建议[2][4]。')
})

test('all body citations move to sentence end while links, code and separate sentences survive', () => {
  assert.equal(cleanReportCitationNotes('研究[1]指出可行[1]，仍需验证。另一项结论[1]。'), '研究指出可行，仍需验证[1]。另一项结论[1]。')
  assert.equal(cleanReportCitationNotes('示例 `[1]` 与 [1](https://example.org) 不移动。'), '示例 `[1]` 与 [1](https://example.org) 不移动。')
  const content = buildReportMarkdown({ sections: [{ title: '正文', content: '[1]研究发现可行[1]。' },
    { title: '参考资料', content: '[1] 论文（论文摘要，2024-03）' }] })
  assert.ok(content.includes('研究发现可行[1]。'))
  assert.ok(content.includes('[1] 论文（论文摘要，2024-03）'))
})
