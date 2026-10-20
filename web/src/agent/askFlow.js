// Flow 2: question answering with memory citations.
// User asks -> search memory store -> agent answers -> present the reply in
// plain language, list which memories were cited (viewable) and why
// (translated reason codes). If the user drops some cited memories, re-compose
// the answer from the remaining ones.
import { searchMemories, askAgent, recomposeContext } from './agentClient.js'
import { describeReason } from './reasonCodes.js'

// Step 1: user asks a question. Returns a display-ready answer object.
export async function askWithMemories(question, options = {}) {
  let searchResult = null
  try {
    searchResult = await searchMemories(question, options)
  } catch {
    searchResult = null // memory store may be empty or offline; agent still answers
  }

  const memoryItems = (searchResult?.items || []).map(item => ({
    id: item.memory.id,
    content: item.memory.content,
    summary: item.memory.summary,
    sourceRef: item.memory.source_ref,
    sourceExcerpt: item.memory.source_excerpt,
    conversationId: item.memory.conversation_id,
    sourceMessageIds: item.memory.source_message_ids,
    selectedForm: item.selected_form,
    reasonText: describeReason(item.reason_codes)
  }))

  const agentResult = await askAgent(question, memoryItems)
  return {
    question,
    traceId: searchResult?.trace_id || null,
    modeUsed: searchResult?.mode_used || null,
    reply: agentResult.reply || agentResult.answer || '',
    // Cited memories the UI renders as expandable cards with "why used" text.
    citations: (agentResult.cited_memories || agentResult.citations || []).map(citation => {
      const matched = memoryItems.find(item => item.id === citation.memory_id) || {}
      return {
        memoryId: citation.memory_id,
        content: citation.content || matched.content || '',
        sourceRef: citation.source_ref || matched.sourceRef || '',
        keywords: citation.keywords || [],
        reasonText: describeReason(citation.reason_codes)
      }
    }),
    rawMemories: memoryItems
  }
}

// Step 2: the user dropped some memory pieces -> re-compose the answer.
// `keptCitations` = citations the user still wants. This re-assembles the
// context via POST /v1/memories/context (no new search, no auto re-add) and
// asks the agent for a fresh answer over the remaining context.
export async function recomposeAnswer(question, keptCitations) {
  const keptIds = keptCitations.map(citation => citation.memoryId).filter(Boolean)
  let contextResult = null
  try {
    contextResult = await recomposeContext(keptIds)
  } catch {
    contextResult = null
  }
  const kept = keptCitations.map(citation => ({
    memory_id: citation.memoryId,
    content: citation.content
  }))
  const agentResult = await askAgent(question, kept)
  return {
    reply: agentResult.reply || agentResult.answer || '',
    citations: keptCitations,
    contextText: contextResult?.context_text || '',
    excluded: contextResult?.excluded || []
  }
}
