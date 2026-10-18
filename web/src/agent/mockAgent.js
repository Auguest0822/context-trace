// Mock agent responses. The Python side does not yet implement the agent
// endpoints (docs/api-data-contract.md: api.py / mcp_server.py "尚未实现"),
// so the UI can run end-to-end against these fakes before the backend lands.

function delay(ms) { return new Promise(resolve => setTimeout(resolve, ms)) }

// Flow 1 mock: user-selected messages -> candidate memories.
export async function mockExtract(messages) {
  await delay(600)
  return messages.slice(0, 5).map((message, index) => ({
    candidate_id: `mock-candidate-${Date.now()}-${index}`,
    kind: message.rawRole === 'assistant' ? 'decision' : 'fact',
    content: message.text.length > 200 ? `${message.text.slice(0, 200)}…` : message.text,
    summary: null,
    source_message_ids: [message.id],
    source_excerpt: message.text.slice(0, 1000),
    confidence: 0.6 + (index % 4) * 0.1
  }))
}

// Flow 2 mock: question -> answer + which memories were cited and why.
export async function mockAsk(question, memories = []) {
  await delay(800)
  const cited = memories.slice(0, 2).map((memory, index) => ({
    memory_id: memory.id || String(100 + index),
    content: memory.content,
    source_ref: memory.source_ref || `conversation:201#message:30${index + 1}`,
    keywords: ['初赛', '复现'].slice(0, index + 1),
    reason_codes: index === 0 ? ['KEYWORD_MATCH', 'VECTOR_MATCH'] : ['TOP_K_EXCEEDED']
  }))
  return {
    reply: `关于“${question}”：根据已保存的记忆，初赛优先保证仓库本地可复现，云服务器只用于团队联调。`,
    cited_memories: cited
  }
}

// Flow 2 mock fallback for recomposing after the user deselects memory pieces.
export async function mockRecompose(question, keptMemories = []) {
  await delay(500)
  const keptIds = keptMemories.map(memory => memory.memory_id || memory.id).filter(Boolean)
  return {
    included_memory_ids: keptIds,
    context_text: keptMemories
      .map(memory => `[memory:${memory.memory_id || memory.id}] ${memory.content}`)
      .join('\n'),
    reply: keptIds.length
      ? `已按你保留的 ${keptIds.length} 条记忆重新回答“${question}”。`
      : `你没有保留任何记忆片段，以下回答不引用记忆库：关于“${question}”，我仅基于当前问题作答。`
  }
}
