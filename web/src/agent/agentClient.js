// Agent communication layer.
// Talks to the Python service agent endpoints when available; falls back to
// mockAgent.js so the frontend can be developed before api.py is implemented.
import { postJson, request } from './http.js'
import { mockExtract, mockAsk, mockRecompose } from './mockAgent.js'

// Set VITE_AGENT_ENABLED=false to force mock mode during development.
const agentEnabled = import.meta.env.VITE_AGENT_ENABLED !== 'false'

async function tryAgent(path, payload, mockFn) {
  if (!agentEnabled) return mockFn()
  try {
    return await postJson(path, payload)
  } catch (error) {
    if (String(error.message).includes('无法连接')) return mockFn()
    throw error
  }
}

// Flow 1: send the user-selected conversation messages to the agent for
// memory extraction. Backend contract (planned): POST /v1/agent/extract
export function extractMemories(messages) {
  return tryAgent('/v1/agent/extract', { messages }, () => mockExtract(messages))
}

// Flow 2: send the user's question (with optional memory context) to the agent.
// Backend contract (planned): POST /v1/agent/ask
export function askAgent(question, memories = []) {
  return tryAgent('/v1/agent/ask', { question, memories }, () => mockAsk(question, memories))
}

// Flow 2 follow-up: re-compose an answer after the user deselects memory
// pieces. Uses the already-specified contract POST /v1/memories/context.
export async function recomposeContext(memoryIds, budgetTokens = 1200) {
  if (!agentEnabled) return mockRecompose('', memoryIds.map(id => ({ id })))
  try {
    return await request('/v1/memories/context', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope: (import.meta.env.VITE_ARCHIVE_SCOPE || 'project:context-trace'), memory_ids: memoryIds, budget_tokens: budgetTokens })
    })
  } catch (error) {
    if (String(error.message).includes('无法连接')) return mockRecompose('', memoryIds.map(id => ({ id })))
    throw error
  }
}

// Flow 2: search the memory store before asking the agent.
// Contract: POST /v1/memories/search
export async function searchMemories(query, options = {}) {
  const payload = {
    query,
    mode: options.mode || 'hybrid',
    top_k: options.topK || 5,
    budget_tokens: options.budgetTokens || 1200
  }
  if (options.filters) payload.filters = options.filters
  return postJson('/v1/memories/search', payload)
}
