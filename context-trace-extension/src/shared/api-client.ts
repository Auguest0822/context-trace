// ============================================================================
// 言迹 ContextTrace —— 浏览器扩展接口层（唯一网络出口）
// ----------------------------------------------------------------------------
// 依据 docs/api-data-contract.md 第 6 节「网页前端与后续浏览器扩展约定」实现。
// 本文件是扩展工程独立文件：不 import、不修改 context-trace/（Vue3 前端）任何代码。
//
// 契约端点（全部挂在一个「队长」后端 baseURL 下，统一前缀 /v1）：
//
//  对话首页        GET    /v1/conversations                      会话列表
//                 POST   /v1/conversations                      归档一条抓取的对话
//  对话详情与提炼  GET    /v1/conversations/{id}                 会话详情
//                 GET    /v1/conversations/{id}/messages        消息列表
//                 GET    /v1/memories?conversation_id=...        该会话已沉淀的记忆
//                 POST   /v1/extractions/preview                选择性提炼 → 候选预览
//                 POST   /v1/extractions/{preview_id}/commit    勾选后提交落库
//                 DELETE /v1/conversations/{id}                 删除会话归档
//  记忆库与时间线  GET    /v1/memories                           记忆列表
//                 GET    /v1/memories/{id}                      记忆详情
//                 POST   /v1/memories                           手动写入记忆
//                 DELETE /v1/memories/{id}                      删除记忆
//  召回回放        POST   /v1/memories/search                    检索（响应含 trace_id）
//                 GET    /v1/traces                             召回记录列表
//                 GET    /v1/traces/{trace_id}                  单次召回回放
//  最终上下文选择  POST   /v1/memories/context                   勾选记忆 → 拼装最终上下文
//  压缩对比        ——     search 响应的 selected_form / token_count / budget，
//                        与原记忆 content/summary 对照
//
// 说明：契约规定「接口 / Agent 接入仅提供记忆读写，完整对话归档需走用户
// 导出/手动导入」——本扩展按网页前端的约定仅 POST /v1/conversations 归档
// 用户主动捕获的对话，不做静默全量上传。
// ============================================================================

import type {
  ApiSettings,
  CandidateMemory,
  Category,
  Conversation,
  ExtractRequest,
  ExtractResponse,
  MatchExplainItem,
  SavedMemory,
  SearchRequest,
  SearchResponse,
  SearchResult
} from './types'
import { mockApi } from './api'

// ============================================================================
// 1. 契约 wire 类型（与后端 JSON 一一对应，snake_case）
// ============================================================================

export type WireRole = 'user' | 'assistant' | 'system'
export type WireSearchMode = 'hybrid' | 'keyword' | 'vector'

export interface WireConversation {
  id: string
  title: string
  source?: string
  url?: string
  created_at?: string
  message_count?: number
}

export interface WireMessage {
  id: string
  role: WireRole
  content: string
  created_at?: string
}

export interface WireMemory {
  id: string
  conversation_id?: string
  conversation_title?: string
  category?: string
  title?: string
  content?: string
  /** 压缩后的摘要形态（压缩对比用） */
  summary?: string
  source?: string
  created_at?: string
  token_count?: number
}

/** POST /v1/extractions/preview 请求体 */
export interface WirePreviewRequest {
  conversation_id: string
  message_ids: string[]
  instruction?: string
}

export interface WireCandidate {
  id: string
  category?: string
  content: string
  summary?: string
  /** 证据引用 */
  evidence?: Array<{
    seq?: number
    message_id?: string
    role?: WireRole | string
    text?: string
  }>
  based_on?: number[]
}

export interface WirePreview {
  preview_id: string
  conversation_id: string
  candidates: WireCandidate[]
  /** 可选：提炼过程的解释（命中方式等） */
  explain?: WireExplainItem[]
}

export interface WireExplainItem {
  seq?: number
  ways?: string[]
  text?: string
  target?: string
}

/** POST /v1/extractions/{preview_id}/commit 请求体 */
export interface WireCommitRequest {
  candidate_ids: string[]
  /** 用户编辑后的候选内容覆盖（key = candidate id） */
  overrides?: Record<string, string>
}

export interface WireCommitResponse {
  saved: WireMemory[]
  count?: number
}

/** POST /v1/memories/search 请求体 */
export interface WireSearchRequest {
  query: string
  conversation_id?: string
  category?: string
  mode?: WireSearchMode
  /** token 预算（压缩对比中的 budget） */
  budget?: number
  top_k?: number
}

export interface WireSearchResultItem {
  memory: WireMemory
  score?: number
  matched_by?: string[]
}

/** POST /v1/memories/search 响应 —— 含压缩对比与召回回放字段 */
export interface WireSearchResponse {
  results: WireSearchResultItem[]
  /** 压缩对比：最终拼装进上下文的记忆形态（摘要/原文） */
  selected_form?: string
  /** 压缩对比：实际消耗 token */
  token_count?: number
  /** 压缩对比：预算 */
  budget?: number
  /** 召回回放：本次检索的 trace */
  trace_id?: string
  explain?: WireExplainItem[]
}

/** POST /v1/memories/context 请求体（最终上下文选择） */
export interface WireContextRequest {
  memory_ids: string[]
  query?: string
  budget?: number
}

export interface WireContextResponse {
  context: string
  token_count?: number
  budget?: number
  /** 因超预算被裁剪掉的记忆 id */
  dropped?: string[]
}

export interface WireTrace {
  trace_id: string
  query?: string
  created_at?: string
  results?: WireSearchResultItem[]
  selected_form?: string
  token_count?: number
  budget?: number
}

// ============================================================================
// 2. HTTP 客户端（fetch 封装：鉴权、超时、错误归一化）
// ============================================================================

export class CaptainApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public path: string
  ) {
    super(message)
    this.name = 'CaptainApiError'
  }
}

export class CaptainHttpClient {
  constructor(
    private getConfig: () => Promise<{ baseUrl: string; apiKey?: string; timeoutMs?: number }>
  ) {}

  private async request<T>(
    method: 'GET' | 'POST' | 'DELETE',
    path: string,
    body?: unknown
  ): Promise<T> {
    const { baseUrl, apiKey, timeoutMs = 15000 } = await this.getConfig()
    if (!baseUrl) throw new CaptainApiError('未配置队长后端 baseUrl', 0, path)

    const url = baseUrl.replace(/\/+$/, '') + path
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const resp = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {})
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal
      })
      if (!resp.ok) {
        const text = await resp.text().catch(() => '')
        throw new CaptainApiError(
          `队长接口 ${method} ${path} 失败：HTTP ${resp.status}${text ? ' - ' + text.slice(0, 200) : ''}`,
          resp.status,
          path
        )
      }
      // 204 / 空响应
      if (resp.status === 204) return undefined as T
      const text = await resp.text()
      return (text ? JSON.parse(text) : undefined) as T
    } finally {
      clearTimeout(timer)
    }
  }

  private get<T>(path: string) {
    return this.request<T>('GET', path)
  }
  private post<T>(path: string, body?: unknown) {
    return this.request<T>('POST', path, body)
  }
  private del<T>(path: string) {
    return this.request<T>('DELETE', path)
  }

  // ---- 以下方法与契约表格一一对应 ----

  /** 对话首页：会话列表。query 支持 source/q/limit 等 */
  listConversations(query?: { source?: string; q?: string; limit?: number }) {
    return this.get<{ items?: WireConversation[] } | WireConversation[]>(`/v1/conversations${toQuery(query)}`)
  }

  /** 对话首页：归档一条用户主动捕获的对话 */
  createConversation(body: {
    title: string
    source?: string
    url?: string
    messages: Array<{ role: WireRole | string; content: string; id?: string }>
  }) {
    return this.post<WireConversation>('/v1/conversations', body)
  }

  /** 对话详情 */
  getConversation(id: string) {
    return this.get<WireConversation>(`/v1/conversations/${encodeURIComponent(id)}`)
  }

  /** 会话消息列表 */
  listConversationMessages(id: string) {
    return this.get<{ items?: WireMessage[] } | WireMessage[]>(
      `/v1/conversations/${encodeURIComponent(id)}/messages`
    )
  }

  /** 删除会话归档 */
  deleteConversation(id: string) {
    return this.del<void>(`/v1/conversations/${encodeURIComponent(id)}`)
  }

  /** 记忆列表。契约示例：GET /v1/memories?conversation_id=... */
  listMemories(query?: { conversation_id?: string; category?: string; q?: string; limit?: number }) {
    return this.get<{ items?: WireMemory[] } | WireMemory[]>(`/v1/memories${toQuery(query)}`)
  }

  /** 记忆详情 */
  getMemory(id: string) {
    return this.get<WireMemory>(`/v1/memories/${encodeURIComponent(id)}`)
  }

  /** 手动写入一条记忆 */
  createMemory(body: {
    content: string
    title?: string
    category?: string
    conversation_id?: string
    source?: string
  }) {
    return this.post<WireMemory>('/v1/memories', body)
  }

  /** 删除记忆 */
  deleteMemory(id: string) {
    return this.del<void>(`/v1/memories/${encodeURIComponent(id)}`)
  }

  /** 选择性提炼：先预览拿候选，不落库 */
  previewExtraction(body: WirePreviewRequest) {
    return this.post<WirePreview>('/v1/extractions/preview', body)
  }

  /** 提炼提交：把勾选的候选真正写入记忆库 */
  commitExtraction(previewId: string, body: WireCommitRequest) {
    return this.post<WireCommitResponse>(
      `/v1/extractions/${encodeURIComponent(previewId)}/commit`,
      body
    )
  }

  /** 召回检索（响应含 selected_form / token_count / budget / trace_id） */
  searchMemories(body: WireSearchRequest) {
    return this.post<WireSearchResponse>('/v1/memories/search', body)
  }

  /** 召回回放：trace 列表 */
  listTraces(query?: { limit?: number }) {
    return this.get<{ items?: WireTrace[] } | WireTrace[]>(`/v1/traces${toQuery(query)}`)
  }

  /** 召回回放：单条 trace 详情 */
  getTrace(traceId: string) {
    return this.get<WireTrace>(`/v1/traces/${encodeURIComponent(traceId)}`)
  }

  /** 最终上下文选择：勾选的记忆 id → 拼装后的最终上下文 */
  buildContext(body: WireContextRequest) {
    return this.post<WireContextResponse>('/v1/memories/context', body)
  }
}

// ============================================================================
// 3. wire ↔ 内部类型映射
// ============================================================================

const CATEGORY_SET: Category[] = ['决策', '行动', '约束', '事实']

function toQuery(params?: Record<string, string | number | undefined>): string {
  if (!params) return ''
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
  return parts.length ? '?' + parts.join('&') : ''
}

/** 契约响应可能是 {items:[...]} 或裸数组，这里统一成数组 */
function itemsOf<T>(data: { items?: T[] } | T[] | undefined | null): T[] {
  if (!data) return []
  if (Array.isArray(data)) return data
  return data.items || []
}

function wireMemoryToSaved(m: WireMemory, idx = 0): SavedMemory {
  return {
    id: m.id,
    category: (m.category as Category) || '事实',
    title: m.title || (m.content || m.summary || '').slice(0, 14) || `记忆 #${idx + 1}`,
    content: m.content || m.summary || '',
    source: m.source || '未知',
    conversation: m.conversation_title || m.conversation_id || '—',
    conversationId: m.conversation_id || '',
    time: m.created_at || '',
    quote: m.summary || '',
    tokens: m.token_count
  }
}

function wireCandidateToInternal(c: WireCandidate): CandidateMemory {
  return {
    id: c.id,
    category: (CATEGORY_SET as string[]).includes(c.category || '')
      ? (c.category as Category)
      : '事实',
    content: c.content,
    citations: (c.evidence || []).map((e, i) => ({
      seq: e.seq ?? i + 1,
      role: (e.role as CandidateMemory['citations'][number]['role']) || 'assistant',
      text: e.text || ''
    })),
    basedOn: c.based_on || []
  }
}

function wireExplainToInternal(items: WireExplainItem[] | undefined): MatchExplainItem[] {
  return (items || []).map((e, i) => ({
    seq: e.seq ?? i + 1,
    ways: (e.ways as MatchExplainItem['ways']) || [],
    text: e.text || '',
    target: e.target || `#${i + 1}`
  }))
}

function modeToWire(mode: SearchRequest['mode']): WireSearchMode {
  if (mode === '关键词') return 'keyword'
  if (mode === '向量') return 'vector'
  return 'hybrid'
}

function wireSearchToInternal(r: WireSearchResponse): SearchResponse {
  const results: SearchResult[] = (r.results || []).map((item, i) => {
    const saved = wireMemoryToSaved(item.memory, i)
    const matchedBy = (item.matched_by || []) as SearchResult['matchedBy']
    return {
      ...saved,
      matchedBy: matchedBy.length ? matchedBy : (['关键词匹配'] as SearchResult['matchedBy']),
      conversationLabel: `对话 ${saved.conversation}`,
      score: item.score
    }
  })
  return {
    results,
    explain: wireExplainToInternal(r.explain),
    total: results.length,
    traceId: r.trace_id,
    selectedForm: r.selected_form,
    tokenCount: r.token_count,
    budget: r.budget
  }
}

// ============================================================================
// 4. 统一门面：mock 模式 ↔ 契约 HTTP 模式自动切换
//    方法签名与旧 mockApi 对齐，background 调用方几乎零改动。
// ============================================================================

export interface CaptainApiDeps {
  getSettings: () => Promise<ApiSettings>
}

export function createCaptainApi(deps: CaptainApiDeps) {
  const client = new CaptainHttpClient(async () => {
    const s = await deps.getSettings()
    return { baseUrl: s.baseUrl, apiKey: s.apiKey }
  })

  /** 当前是否走真实队长后端（否则走内置 mock） */
  async function isLive(): Promise<boolean> {
    const s = await deps.getSettings()
    return !s.mock && !!s.baseUrl
  }

  // previewId → preview 响应 的暂存（提炼 → 提交 两步之间）
  const pendingPreviews = new Map<string, WirePreview>()

  // 本地缓存的会话（抓取后先落本地，HTTP 模式同时归档到队长）
  const localConversations = new Map<string, Conversation>()

  return {
    /** 直接暴露契约客户端，供未来 UI 使用召回回放 / 上下文选择等能力 */
    client,

    /** content script 抓取到对话后调用：本地缓存 + HTTP 模式下归档 */
    async putConversation(conv: Conversation) {
      localConversations.set(conv.id, conv)
      if (await isLive()) {
        try {
          await client.createConversation({
            title: conv.title,
            source: conv.source,
            url: conv.url,
            messages: conv.messages.map((m) => ({ id: m.id, role: m.role, content: m.text }))
          })
        } catch (e) {
          // 归档失败不阻塞提炼流程，候选仍可基于本地缓存生成
          console.warn('[CT] 归档对话失败，稍后可重试：', (e as Error).message)
        }
      }
    },

    /** 对话首页：会话列表（HTTP 模式合并本地未归档会话） */
    async listConversations(): Promise<Conversation[]> {
      if (await isLive()) {
        try {
          const wires = itemsOf(await client.listConversations())
          const remote: Conversation[] = wires.map((w) => ({
            id: w.id,
            title: w.title,
            source: w.source || '未知',
            url: w.url || '',
            messages: [],
            capturedAt: w.created_at || ''
          }))
          const seen = new Set(remote.map((c) => c.id))
          return [...remote, ...Array.from(localConversations.values()).filter((c) => !seen.has(c.id))]
        } catch (e) {
          console.warn('[CT] 拉取会话列表失败，降级本地：', (e as Error).message)
        }
      }
      return Array.from(localConversations.values()).sort((a, b) =>
        b.capturedAt.localeCompare(a.capturedAt)
      )
    },

    /** 选择性提炼：两步契约 —— preview（拿候选） */
    async extract(req: ExtractRequest, conv?: Conversation): Promise<ExtractResponse> {
      if (await isLive()) {
        try {
          const preview = await client.previewExtraction({
            conversation_id: req.conversationId,
            message_ids: req.selectedMessageIds
          })
          pendingPreviews.set(preview.preview_id, preview)
          return {
            candidates: preview.candidates.map(wireCandidateToInternal),
            explain: wireExplainToInternal(preview.explain),
            previewId: preview.preview_id
          }
        } catch (e) {
          console.warn('[CT] 队长提炼失败：', (e as Error).message)
          return { candidates: [], explain: [], error: (e as Error).message }
        }
      }
      // mock 降级
      const c = conv || localConversations.get(req.conversationId)
      if (!c) return { candidates: [], explain: [] }
      return mockApi.extract(req, c)
    },

    /** 提炼提交：契约两步 —— commit（落库）；mock 模式走本地保存 */
    async save(
      candidates: CandidateMemory[],
      conversationId: string,
      previewId?: string
    ): Promise<{ saved: number }> {
      if (await isLive()) {
        const preview = previewId ? pendingPreviews.get(previewId) : undefined
        if (!preview) {
          return { saved: 0 }
        }
        const overrides: Record<string, string> = {}
        candidates.forEach((c) => {
          const orig = preview.candidates.find((p) => p.id === c.id)
          if (orig && orig.content !== c.content) overrides[c.id] = c.content
        })
        const resp = await client.commitExtraction(previewId!, {
          candidate_ids: candidates.map((c) => c.id),
          overrides: Object.keys(overrides).length ? overrides : undefined
        })
        pendingPreviews.delete(previewId!)
        return { saved: resp.saved?.length ?? resp.count ?? candidates.length }
      }
      return mockApi.save(candidates, conversationId)
    },

    /** 召回检索：POST /v1/memories/search，带回 trace_id 与压缩对比字段 */
    async search(req: SearchRequest): Promise<SearchResponse> {
      if (await isLive()) {
        try {
          const resp = await client.searchMemories({
            query: req.question,
            category: req.category || undefined,
            mode: modeToWire(req.mode),
            budget: req.tokenBudget,
            top_k: req.topK
          })
          return wireSearchToInternal(resp)
        } catch (e) {
          console.warn('[CT] 队长检索失败：', (e as Error).message)
          return { results: [], explain: [], total: 0, error: (e as Error).message }
        }
      }
      return mockApi.search(req)
    },

    /**
     * 「翻译人话」：契约没有单独的 LLM 回答端点，
     * HTTP 模式 = search 结果 → POST /v1/memories/context 拼最终上下文
     *           → 本地按上下文组织一段用户能读懂的回答。
     * mock 模式走旧 mockAskCaptain。
     */
    async askCaptain(question: string, resp: SearchResponse): Promise<string> {
      if (await isLive()) {
        if (!resp.results.length) {
          return `记忆库里还没有找到和「${question}」相关的内容。可以先在 AI 对话页点「提取记忆」，沉淀几条后再来问。`
        }
        try {
          const ctx = await client.buildContext({
            memory_ids: resp.results.map((r) => r.id),
            query: question
          })
          return [
            `关于「${question}」，从记忆库中找到 ${resp.results.length} 条相关记录（共 ${ctx.token_count ?? '?'} tokens）：`,
            '',
            ctx.context,
            '',
            `以上内容来自 ${resp.results.map((r) => `「${r.title}」`).join('、')}。如需完整上下文，可打开侧边栏查看检索详情。`
          ].join('\n')
        } catch (e) {
          // 上下文接口不可用时，退化为直接组织检索结果
          const top = resp.results[0]
          return `根据记忆库「${top.title}」的记录：\n${top.content}\n\n（组装最终上下文失败：${(e as Error).message}）`
        }
      }
      return mockApi.askCaptain(question, resp)
    },

    /** popup/sidepanel：已保存记忆列表（GET /v1/memories） */
    async listSavedMemories(): Promise<SavedMemory[]> {
      if (await isLive()) {
        try {
          const wires = itemsOf(await client.listMemories())
          return wires.map((m, i) => wireMemoryToSaved(m, i))
        } catch (e) {
          console.warn('[CT] 拉取记忆列表失败：', (e as Error).message)
          return []
        }
      }
      return mockApi.listSavedMemories()
    },

    /** 单条记忆详情（GET /v1/memories/{id}），含 summary 供压缩对比 */
    async getMemoryDetail(id: string): Promise<SavedMemory | null> {
      if (await isLive()) {
        try {
          return wireMemoryToSaved(await client.getMemory(id))
        } catch {
          return null
        }
      }
      return mockApi.listSavedMemories().find((m) => m.id === id) || null
    },

    /** 删除记忆（DELETE /v1/memories/{id}） */
    async deleteMemory(id: string): Promise<boolean> {
      if (await isLive()) {
        try {
          await client.deleteMemory(id)
          return true
        } catch {
          return false
        }
      }
      const list = mockApi.listSavedMemories()
      const i = list.findIndex((m) => m.id === id)
      if (i >= 0) list.splice(i, 1)
      return i >= 0
    },

    /** 召回回放：trace 列表（GET /v1/traces） */
    async listTraces(limit = 20) {
      if (await isLive()) {
        try {
          return itemsOf(await client.listTraces({ limit }))
        } catch {
          return []
        }
      }
      return []
    },

    /** 召回回放：单条 trace（GET /v1/traces/{trace_id}） */
    async getTrace(traceId: string) {
      if (await isLive()) {
        try {
          return await client.getTrace(traceId)
        } catch {
          return null
        }
      }
      return null
    }
  }
}

export type CaptainApi = ReturnType<typeof createCaptainApi>
