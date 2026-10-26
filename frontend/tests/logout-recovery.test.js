import test from 'node:test'
import assert from 'node:assert/strict'
import { endSession } from '../src/utils/endSession.js'

test('failed remote logout still clears local state and allows navigation to continue', async () => {
  const events = []
  const revoked = await endSession(async () => { throw new Error('Signature verification failed') }, async () => { events.push('cleared') })
  events.push('navigate')
  assert.equal(revoked, false)
  assert.deepEqual(events, ['cleared', 'navigate'])
})

test('successful logout awaits local workspace cleanup before completing', async () => {
  const events = []
  assert.equal(await endSession(async () => { events.push('revoked') }, async () => { await Promise.resolve(); events.push('cleared') }), true)
  assert.deepEqual(events, ['revoked', 'cleared'])
})
