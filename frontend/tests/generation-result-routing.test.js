import test from 'node:test'
import assert from 'node:assert/strict'
import { getPortalGenerationResultPath, getPortalTaskPath } from '../src/views/portal/utils/routing.js'

test('a queued generic research report opens its real progress page', () => {
  assert.equal(getPortalTaskPath({ id: '501', reportType: 'research' }), '/portal/research/tasks/501')
})

test('completion opens a saved report only when it represents the generated result', () => {
  for (const reportType of ['research', 'weekly', 'monthly']) {
    const task = { id: '501', reportId: '500', reportType, status: 'completed', reportStatus: 'completed' }
    assert.equal(getPortalGenerationResultPath(task), reportType === 'research' ? '/portal/research/reports/500' : '/portal/digests/500')
    assert.equal(getPortalGenerationResultPath({ ...task, applyConflict: true }), '/portal/research/tasks/501')
    assert.equal(getPortalGenerationResultPath({ ...task, reportStatus: 'draft' }), '/portal/research/tasks/501')
    assert.equal(getPortalGenerationResultPath({ ...task, status: 'running' }), '/portal/research/tasks/501')
  }
})
