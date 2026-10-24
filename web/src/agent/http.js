// Shared HTTP helper for the agent interaction layer.
// Follows the error format defined in docs/api-data-contract.md section 2.
const env = import.meta.env || {}
export const AGENT_BASE_URL = env.VITE_AGENT_BASE_URL || env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
export const SCOPE = env.VITE_ARCHIVE_SCOPE || 'project:context-trace'

export async function request(path, options = {}) {
  let response
  try {
    response = await fetch(new URL(path, AGENT_BASE_URL), options)
  } catch {
    throw new Error('无法连接 Python API，请检查 8000 端口和 CORS 设置')
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(body.error?.code ? `${body.error.code}：${body.error.message}` : `HTTP ${response.status}`)
  }
  return body
}

export function postJson(path, payload) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scope: SCOPE, ...payload })
  })
}
