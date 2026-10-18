import test from 'node:test'
import assert from 'node:assert/strict'
import { previewManual, commitManual, readMemory } from '../src/data/extractionApi.js'

test('manual preview sends only selected archived IDs and explicit mode', async t => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  let sent
  globalThis.fetch = async (url, options) => {
    sent = { url: String(url), body: JSON.parse(options.body) }
    return Response.json({ preview_id: 'preview-1', candidates: [] })
  }
  const response = await previewManual('201', ['301', '302'])
  assert.equal(response.preview_id, 'preview-1')
  assert.equal(new URL(sent.url).pathname, '/v1/extractions/preview')
  assert.deepEqual(sent.body, {
    scope: 'project:context-trace', conversation_id: '201',
    message_ids: ['301', '302'], mode: 'manual'
  })
})

test('confirm sends one idempotency key and readback uses scope', async t => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url: new URL(url), options })
    return Response.json(calls.length === 1 ? { memories: [{ id: '401' }] } : { memory: { id: '401' } })
  }
  const payload = { client_request_id: 'a5dd4e86-e121-48b8-b265-34204dbe1dd3',
    selected: [{ candidate_id: 'c1', kind: 'decision', content: '确认的结论', summary: null }] }
  assert.equal((await commitManual('preview-1', payload)).memories[0].id, '401')
  assert.equal(calls[0].url.pathname, '/v1/extractions/preview-1/commit')
  assert.deepEqual(JSON.parse(calls[0].options.body), { scope: 'project:context-trace', ...payload })
  assert.equal((await readMemory('401')).memory.id, '401')
  assert.equal(calls[1].url.searchParams.get('scope'), 'project:context-trace')
})

test('API errors are shown rather than treated as saved memories', async t => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  globalThis.fetch = async () => Response.json({ error: { code: 'PREVIEW_EXPIRED', message: 'expired' } }, { status: 410 })
  await assert.rejects(commitManual('preview-1', { selected: [], client_request_id: 'x' }), /PREVIEW_EXPIRED/)
})
