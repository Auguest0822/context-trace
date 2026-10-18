// Flow 1: selective memory extraction.
// User picks messages -> agent returns candidates -> user confirms which to save.
// Saving always goes through the contract HTTP endpoints (preview -> commit);
// the frontend never writes to the database directly, because the backend must
// validate evidence excerpts, generate source_ref and write in one transaction.
import { previewManual, commitManual } from '../data/extractionApi.js'
import { extractMemories } from './agentClient.js'

// Step 1: user selected messages -> agent candidates for display.
// `messages` items: { id, rawRole, text } (see archiveApi.js mapMessage output).
export async function previewCandidates(messages) {
  const agentResult = await extractMemories(messages)
  return normalizeCandidates(agentResult, messages)
}

function normalizeCandidates(agentResult, messages) {
  const known = new Set(messages.map(message => message.id))
  const candidates = agentResult?.candidates || agentResult || []
  return candidates.map(candidate => ({
    candidateId: candidate.candidate_id,
    kind: candidate.kind || 'fact',
    content: candidate.content || '',
    summary: candidate.summary ?? null,
    confidence: candidate.confidence ?? null,
    sourceMessageIds: (candidate.source_message_ids || []).filter(id => known.has(String(id))),
    sourceExcerpt: candidate.source_excerpt || ''
  }))
}

// Step 2: user confirmed a subset -> persist via the contract commit endpoint.
// `selection` items: { candidateId, kind, content, summary }.
export async function saveConfirmedCandidates(previewId, selection) {
  return commitManual(previewId, {
    selected: selection.map(item => ({
      candidate_id: item.candidateId,
      kind: item.kind,
      content: item.content,
      summary: item.summary
    })),
    client_request_id: crypto.randomUUID()
  })
}

// Full flow helper for simple pages: extract, let the caller filter, then save.
// Returns { previewId, candidates } from step 1; step 2 is a separate user action.
export async function runExtractionFlow(conversationId, messages) {
  const candidates = await previewCandidates(messages)
  const preview = await previewManual(conversationId, messages.map(message => message.id))
  return { previewId: preview.preview_id, candidates }
}
