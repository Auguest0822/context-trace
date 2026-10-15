// Read-only conversation archive adapter. The default UI still uses mock.js.
const PLATFORM_LABELS = {
  deepseek: 'DeepSeek',
  kimi: 'Kimi',
  doubao: '豆包',
  agent: 'Agent',
  other: '其他'
}

function displayTime(value) {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间未知'
  return date.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false
  })
}

export function mapConversation(item) {
  return {
    id: String(item.id),
    title: item.title,
    source: PLATFORM_LABELS[item.platform] || '其他',
    platform: item.platform,
    summary: item.capture_completeness === 'selected'
      ? '仅归档用户选中的消息'
      : '归档当前页面可见消息',
    time: displayTime(item.updated_at),
    createdAt: `归档于 ${displayTime(item.created_at)}`,
    messageCount: item.message_count,
    visible: item.capture_completeness === 'visible_page',
    captureCompleteness: item.capture_completeness
  }
}

export function mapMessage(item, conversation) {
  const role = {
    user: '我', assistant: conversation.source, system: '系统', tool: '工具'
  }[item.role] || item.role
  return {
    id: String(item.id),
    seq: item.sequence,
    role,
    rawRole: item.role,
    source: conversation.source,
    time: item.sent_at
      ? displayTime(item.sent_at)
      : `采集于 ${displayTime(item.captured_at)}`,
    text: item.content
  }
}

async function getJson(config, path, params, signal) {
  const url = new URL(path, config.baseUrl)
  for (const [key, value] of Object.entries({ scope: config.scope, ...params })) {
    if (value != null) url.searchParams.set(key, value)
  }
  let response
  try {
    response = await fetch(url, { signal })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error(`无法连接对话 API（${url.origin}）。请先启动 Python API；如果 /healthz 可访问，再检查 CORS 是否允许 5180 端口`)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const code = body.error?.code || `HTTP ${response.status}`
    throw new Error(`读取对话失败：${code}`)
  }
  return response.json()
}

async function allPages(config, path, signal) {
  const items = []
  let cursor = null
  do {
    const page = await getJson(config, path, { limit: 100, cursor }, signal)
    if (!Array.isArray(page.items)) throw new Error('对话 API 返回格式不正确')
    items.push(...page.items)
    cursor = page.next_cursor
  } while (cursor)
  return items
}

export async function loadConversations(config, signal) {
  const items = await allPages(config, '/v1/conversations', signal)
  return items.map(mapConversation)
}

export async function loadConversationDetail(config, conversationId, signal) {
  const result = await getJson(
    config, `/v1/conversations/${encodeURIComponent(conversationId)}`, {}, signal
  )
  if (!result.conversation) throw new Error('对话详情返回格式不正确')
  return mapConversation(result.conversation)
}

export async function loadMessages(config, conversation, signal) {
  const path = `/v1/conversations/${encodeURIComponent(conversation.id)}/messages`
  const items = await allPages(config, path, signal)
  return items.sort((a, b) => a.sequence - b.sequence).map(item => mapMessage(item, conversation))
}
