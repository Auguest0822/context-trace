// Manual preview/commit calls; this module never stores a model or database key.
const env = import.meta.env || {}
const baseUrl = env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const scope = env.VITE_ARCHIVE_SCOPE || 'project:context-trace'

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(new URL(path, baseUrl), options)
  } catch {
    throw new Error('无法连接 Python API，请检查 8000 端口和 CORS 设置')
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(body.error?.code ? `${body.error.code}：${body.error.message}` : `HTTP ${response.status}`)
  }
  return body
}

export function previewManual(conversationId, messageIds) {
  return request('/v1/extractions/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scope, conversation_id: conversationId, message_ids: messageIds, mode: 'manual' })
  })
}

export function commitManual(previewId, payload) {
  return request(`/v1/extractions/${encodeURIComponent(previewId)}/commit`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scope, ...payload })
  })
}

export function readMemory(memoryId) {
  const url = new URL(`/v1/memories/${encodeURIComponent(memoryId)}`, baseUrl)
  url.searchParams.set('scope', scope)
  return request(url.toString())
}
