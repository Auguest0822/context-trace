import test from 'node:test'
import assert from 'node:assert/strict'
import { assembleContext, listMemories, searchMemories } from '../src/data/memoryApi.js'

test('memory list stays scoped across pages', async t => {
  const original = globalThis.fetch
  t.after(() => { globalThis.fetch = original })
  const urls = []
  globalThis.fetch = async url => {
    urls.push(new URL(url))
    return Response.json(urls.length === 1
      ? { items: [{ id: '101', source_message_ids: ['301'] }], next_cursor: 'page2' }
      : { items: [], next_cursor: null })
  }
  const items = await listMemories({ status: 'active', platform: 'deepseek' })
  assert.equal(items.length, 1)
  assert.equal(urls[0].searchParams.get('scope'), 'project:context-trace')
  assert.equal(urls[0].searchParams.get('platform'), 'deepseek')
  assert.equal(urls[1].searchParams.get('cursor'), 'page2')
})

test('search and user-selected context send different requests', async t => {
  const original = globalThis.fetch
  t.after(() => { globalThis.fetch = original })
  const bodies = []
  globalThis.fetch = async (_url, options) => {
    bodies.push(JSON.parse(options.body))
    return Response.json(bodies.length === 1
      ? { trace_id: 'trace', items: [{ memory: { id: '101' } }] }
      : { requested_memory_ids: ['101'], included_memory_ids: ['101'], context_text: 'source' })
  }
  await searchMemories('初赛部署', { mode: 'keyword', filters: { kinds: ['decision'] } })
  await assembleContext(['101'], 100)
  assert.equal(bodies[0].mode, 'keyword')
  assert.deepEqual(bodies[0].filters.kinds, ['decision'])
  assert.deepEqual(bodies[1].memory_ids, ['101'])
  assert.equal(bodies[1].budget_tokens, 100)
  assert.equal(bodies[1].query, undefined)
})
