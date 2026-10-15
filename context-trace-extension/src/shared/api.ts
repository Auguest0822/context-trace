// mock 队长后端：在 background 进程里驻留一份「记忆库」+ 「对话档案」，
// 对外模拟 Extract / Search / Save / AskCaptain 四个接口的真实延时与结果。
// 后续接真实后端时，把这里的实现替换成 fetch 即可，调用方零改动。

import type {
  CandidateMemory,
  Conversation,
  ExtractRequest,
  ExtractResponse,
  MatchExplainItem,
  SearchRequest,
  SearchResponse,
  SearchResult,
  SavedMemory
} from './types'

interface Store {
  conversations: Map<string, Conversation>
  savedMemories: SavedMemory[]
}

const store: Store = {
  conversations: new Map(),
  savedMemories: [
    {
      id: 'm1',
      category: '决策',
      title: '初赛优先保证仓库可复现',
      content: '决定优先使用现有的服务器部署初赛环境，保证本地可复现。这样可以减少申请流程的时间，同时便于后续维护。如果现有资源不足，再考虑申请新的服务器。',
      source: 'DeepSeek',
      conversation: '初赛部署讨论',
      conversationId: 'c1',
      time: '今天 10:15',
      quote: '建议优先使用现有的服务器，保证环境可复现。这样可以减少申请流程的时间，同时便于后续维护。如果现有资源不足，再考虑申请新的服务器。',
      tokens: 98
    },
    {
      id: 'm2',
      category: '行动',
      title: '后续考虑申请新的服务器',
      content: '如果本地资源不足，再考虑申请新的服务器，由服务器团队协助测试和部署。',
      source: 'DeepSeek',
      conversation: '初赛部署讨论',
      conversationId: 'c1',
      time: '今天 10:18',
      quote: '如果现有资源不足，再考虑申请新的服务器。到时候可以请服务器团队协助测试，确认环境稳定后再上线。',
      tokens: 58
    }
  ]
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

// —— 1. 队长接收对话 → 提炼候选 —— //
export async function mockExtract(req: ExtractRequest, conversation: Conversation): Promise<ExtractResponse> {
  await sleep(900)
  const conv = store.conversations.get(req.conversationId) || conversation
  const selected = conv.messages.filter((m) => req.selectedMessageIds.includes(m.id))
  if (!selected.length) return { candidates: [] }

  // 简单规则：前两条作为决策类、约束类
  const candidates: CandidateMemory[] = selected.slice(0, 4).map((m, idx) => {
    const category = idx % 2 === 0 ? '决策' : '约束'
    return {
      id: `cand-${Date.now()}-${idx}`,
      category: category as any,
      content: summarize(m.text),
      basedOn: selected.map((s, i) => i + 1),
      citations: selected.map((s, i) => ({ seq: i + 1, role: s.role, text: s.text }))
    }
  })

  const explain: MatchExplainItem[] = [
    { seq: 1, ways: ['关键词匹配', '向量相似'], text: `匹配到对话中关于「${selected[0].text.slice(0, 8)}…」的语义片段`, target: '#1' },
    { seq: 2, ways: ['向量相似'], text: `关联到关于计划/约束的表述`, target: '#2' }
  ]
  return { candidates, explain }
}

// —— 2. 队长保存候选到记忆库 —— //
export async function mockSave(candidates: CandidateMemory[], conversationId: string): Promise<{ saved: number }> {
  await sleep(500)
  const conv = store.conversations.get(conversationId)
  candidates.forEach((c) => {
    store.savedMemories.push({
      id: c.id,
      category: c.category,
      title: c.content.slice(0, 14) + '…',
      content: c.content,
      source: conv?.source || '未知',
      conversation: conv?.title || '当前对话',
      conversationId,
      time: '刚刚',
      quote: c.citations[0]?.text || ''
    })
  })
  return { saved: candidates.length }
}

// —— 3. 队长接收问题 → 检索记忆 + 给出人话 —— //
export async function mockSearch(req: SearchRequest): Promise<SearchResponse> {
  await sleep(700)
  const q = req.question.trim()
  if (!q) return { results: [], explain: [], total: 0 }

  const tokens = q.split(/[\s,，。？?、]+/).filter(Boolean)
  const scored = store.savedMemories
    .map((m) => {
      const text = `${m.title}\n${m.content}\n${m.quote}`
      const hitKw = tokens.some((t) => text.includes(t))
      // 简单语义近似：包含一些共性关键词
      const hitVec = /(优先|复现|服务器|部署|测试|申请|讨论|初赛|方案)/.test(text) && q.length > 4
      const score = (hitKw ? 1 : 0) + (hitVec ? 0.6 : 0)
      return { m, score, hitKw, hitVec }
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, req.topK || 5)

  const results: SearchResult[] = scored.map((x) => {
    const matchedBy: SearchResult['matchedBy'] = [
      x.hitKw ? '关键词匹配' : null,
      x.hitVec ? '向量相似' : null
    ].filter(Boolean) as SearchResult['matchedBy']
    return {
      ...x.m,
      matchedBy,
      conversationLabel: `对话 #${x.m.conversationId} ${x.m.conversation}`
    }
  })

  const explain: MatchExplainItem[] = results.map((r, i) => ({
    seq: i + 1,
    ways: r.matchedBy,
    text: r.matchedBy.includes('关键词匹配')
      ? `匹配到关键词：${tokens.filter((t) => `${r.title}${r.content}${r.quote}`.includes(t)).join('、')}`
      : `语义相似：与查询描述相关`,
    target: `#${i + 1}`
  }))

  return { results, explain, total: scored.length }
}

// —— 4. 队长 "翻译人话"：用检索到的记忆 + LLM 生成回答 —— //
export async function mockAskCaptain(question: string, search: SearchResponse): Promise<string> {
  await sleep(800)
  if (!search.results.length) {
    return `记忆库里还没有找到和「${question}」相关的内容。你可以先去「对话档案」选一些消息提炼记忆，沉淀下来之后再来问。`
  }
  const top = search.results[0]
  return `根据记忆库里 "${top.title}"（${top.conversation} · ${top.time}）的记录：\n${top.content}\n\n如果你想看更完整的上下文，可以打开侧边栏的检索结果。`
}

// —— 工具 —— //
function summarize(text: string): string {
  const first = text.split(/[。.!?？\n]/)[0]?.trim() || text.slice(0, 40)
  return first.length > 60 ? first.slice(0, 60) + '…' : first
}

// 暴露给 background 使用
export const mockApi = {
  extract: mockExtract,
  save: mockSave,
  search: mockSearch,
  askCaptain: mockAskCaptain,
  /** 注册一条已抓取的对话（content script 抓取后调用） */
  putConversation(conv: Conversation) {
    store.conversations.set(conv.id, conv)
  },
  /** 列出已抓取的对话（popup 等调用） */
  listConversations(): Conversation[] {
    return Array.from(store.conversations.values()).sort((a, b) =>
      b.capturedAt.localeCompare(a.capturedAt)
    )
  },
  listSavedMemories(): SavedMemory[] {
    return store.savedMemories.slice()
  }
}
