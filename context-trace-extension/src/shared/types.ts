// 跨 popup / sidepanel / content / background 共用的类型
// 与 context-trace/ 前端的 mock.js 字段保持一致

export type Role = 'user' | 'assistant' | 'system'
export type Source = 'DeepSeek' | 'Kimi' | '豆包' | 'Agent' | 'ChatGPT' | 'Gemini'
export type Category = '决策' | '行动' | '约束' | '事实'

export interface ChatMessage {
  id: string
  role: Role
  text: string
  time?: string
}

export interface Conversation {
  id: string
  title: string
  source: Source | string
  url: string
  messages: ChatMessage[]
  capturedAt: string
}

export interface CandidateMemory {
  id: string
  category: Category
  content: string
  citations: Array<{ seq: number; role: Role; text: string }>
  basedOn: number[]
}

export interface SavedMemory {
  id: string
  category: Category
  title: string
  content: string
  source: string
  conversation: string
  conversationId: string
  time: string
  quote: string
  tokens?: number
}

export interface SearchResult extends SavedMemory {
  matchedBy: Array<'关键词匹配' | '向量相似'>
  conversationLabel: string
  score?: number
}

export interface MatchExplainItem {
  seq: number
  ways: Array<'关键词匹配' | '向量相似'>
  text: string
  target: string
}

export interface ApiSettings {
  baseUrl: string
  modelName: string
  apiKey: string
  // mock 模式标记，未来切真实后端用
  mock: boolean
}

export interface ExtractRequest {
  conversationId: string
  source: string
  selectedMessageIds: string[]
}

export interface ExtractResponse {
  candidates: CandidateMemory[]
  explain?: MatchExplainItem[]
  /** 契约两步提炼：preview 返回的预览单号，commit 时回传 */
  previewId?: string
  /** 接口调用失败信息（HTTP 模式下提炼失败时非空） */
  error?: string
}

export interface SearchRequest {
  question: string
  source?: string
  category?: Category | ''
  mode?: '混合' | '关键词' | '向量'
  tokenBudget?: number
  topK?: number
}

export interface SearchResponse {
  results: SearchResult[]
  explain: MatchExplainItem[]
  total: number
  /** 召回回放：本次检索的 trace，可查 GET /v1/traces/{trace_id} */
  traceId?: string
  /** 压缩对比：最终拼装进上下文的记忆形态 */
  selectedForm?: string
  /** 压缩对比：实际消耗 token */
  tokenCount?: number
  /** 压缩对比：token 预算 */
  budget?: number
  /** 接口调用失败信息（HTTP 模式下检索失败时非空） */
  error?: string
}
