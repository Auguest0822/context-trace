// Real seekdb-backed memory adapter. Mock pages opt in only through Vite env.
const env = import.meta.env || {}
export const memoryApiConfig = {
  baseUrl: env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  scope: env.VITE_ARCHIVE_SCOPE || 'project:context-trace'
}

async function request(path, options = {}) {
  let response
  try { response = await fetch(new URL(path, memoryApiConfig.baseUrl), options) }
  catch (error) { throw new Error(`无法连接记忆 API（${memoryApiConfig.baseUrl}）：${error.message}`) }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.error?.message || `HTTP ${response.status}`)
  return body
}

export async function listMemories(filters = {}, signal) {
  const url = new URL('/v1/memories', memoryApiConfig.baseUrl)
  const params = { scope: memoryApiConfig.scope, limit: 100, ...filters }
  Object.entries(params).forEach(([key, value]) => {
    if (value != null && value !== '') url.searchParams.set(key, String(value))
  })
  const items = []
  let cursor = null
  do {
    if (cursor) url.searchParams.set('cursor', cursor)
    const page = await request(url.pathname + url.search, { signal })
    if (!Array.isArray(page.items)) throw new Error('记忆列表格式不正确')
    items.push(...page.items)
    cursor = page.next_cursor
  } while (cursor)
  return items
}

export function searchMemories(query, options = {}, signal) {
  return request('/v1/memories/search', {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scope: memoryApiConfig.scope, query, mode: options.mode || 'keyword',
      top_k: options.top_k || 20, budget_tokens: options.budget_tokens || 1200,
      filters: options.filters || {}
    })
  })
}

export function assembleContext(memoryIds, budgetTokens, signal) {
  return request('/v1/memories/context', {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scope: memoryApiConfig.scope, memory_ids: memoryIds,
      budget_tokens: budgetTokens })
  })
}

export function loadTraces(signal) {
  const url = new URL('/v1/traces', memoryApiConfig.baseUrl)
  url.searchParams.set('scope', memoryApiConfig.scope)
  return request(url.pathname + url.search, { signal })
}

export function loadTrace(traceId, signal) {
  const url = new URL(`/v1/traces/${encodeURIComponent(traceId)}`, memoryApiConfig.baseUrl)
  url.searchParams.set('scope', memoryApiConfig.scope)
  return request(url.pathname + url.search, { signal })
}

export function loadMemoryHistory(memoryId, signal) {
  const url = new URL(`/v1/memories/${encodeURIComponent(memoryId)}/history`, memoryApiConfig.baseUrl)
  url.searchParams.set('scope', memoryApiConfig.scope)
  return request(url.pathname + url.search, { signal })
}

export function reconcileMemory(oldMemoryId, newMemory, reason) {
  return request('/v1/memories/reconcile', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scope: memoryApiConfig.scope, old_memory_id: oldMemoryId,
      new_memory: newMemory, reason, client_request_id: crypto.randomUUID() })
  })
}

export function forgetMemory(memoryId) {
  const url = new URL(`/v1/memories/${encodeURIComponent(memoryId)}`, memoryApiConfig.baseUrl)
  url.searchParams.set('scope', memoryApiConfig.scope)
  return request(url.pathname + url.search, { method: 'DELETE' })
}
