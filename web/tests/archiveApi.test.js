import test from 'node:test'
import assert from 'node:assert/strict'
import { loadConversations, loadConversationDetail, loadMessages } from '../src/data/archiveApi.js'

const config = { baseUrl: 'http://127.0.0.1:8000', scope: 'project:context-trace' }
const conversation = {
  id: '201', title: '样例对话', platform: 'deepseek',
  capture_completeness: 'selected', created_at: '2026-10-15T01:00:00Z',
  updated_at: '2026-10-15T02:00:00Z', message_count: 2
}

test('list pagination keeps scope and maps real conversation fields', async t => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  const urls = []
  globalThis.fetch = async url => {
    urls.push(new URL(url))
    return Response.json(urls.length === 1
      ? { items: [conversation], next_cursor: 'next-page' }
      : { items: [], next_cursor: null })
  }

  const items = await loadConversations(config)
  assert.equal(items.length, 1)
  assert.equal(items[0].id, '201')
  assert.equal(items[0].source, 'DeepSeek')
  assert.equal(items[0].messageCount, 2)
  assert.equal(urls[0].searchParams.get('scope'), config.scope)
  assert.equal(urls[1].searchParams.get('cursor'), 'next-page')
})

test('detail and messages use stored IDs, roles and sequence', async t => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  globalThis.fetch = async url => Response.json(String(url).endsWith('/messages?scope=project%3Acontext-trace&limit=100')
    ? { items: [
      { id: '302', sequence: 2, role: 'assistant', content: '回答', captured_at: '2026-10-15T01:00:00Z' },
      { id: '301', sequence: 1, role: 'user', content: '问题', captured_at: '2026-10-15T01:00:00Z' }
    ], next_cursor: null }
    : { conversation })

  const detail = await loadConversationDetail(config, '201')
  const messages = await loadMessages(config, detail)
  assert.equal(detail.title, '样例对话')
  assert.deepEqual(messages.map(m => [m.id, m.seq, m.role, m.text]), [
    ['301', 1, '我', '问题'], ['302', 2, 'DeepSeek', '回答']
  ])
})

test('API failure is surfaced instead of replacing it with mock data', async t => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  globalThis.fetch = async () => Response.json({ error: { code: 'STORE_UNAVAILABLE' } }, { status: 503 })
  await assert.rejects(loadConversations(config), /STORE_UNAVAILABLE/)
})

test('unreachable API reports how to diagnose the local service', async t => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch') }
  await assert.rejects(loadConversations(config), /先启动 Python API/)
})
