// Translate retrieval trace reason_codes (docs/api-data-contract.md 4.8) into user-readable text.
// The page may only translate these real codes; it must not invent recall reasons.
export const REASON_LABELS = {
  KEYWORD_MATCH: '关键词命中',
  VECTOR_MATCH: '语义命中',
  BUDGET_SUMMARY: '超出预算，改用摘要',
  BUDGET_EXCEEDED: '超出 Token 预算，未纳入',
  TOP_K_EXCEEDED: '排在候选名额之外'
}

export function describeReason(codes) {
  if (!Array.isArray(codes) || codes.length === 0) return '系统未给出召回原因'
  return codes.map(code => REASON_LABELS[code] || code).join('；')
}

// Codes that mean "this memory was selected"; others mean excluded.
export const SELECTED_CODES = ['KEYWORD_MATCH', 'VECTOR_MATCH', 'BUDGET_SUMMARY']
