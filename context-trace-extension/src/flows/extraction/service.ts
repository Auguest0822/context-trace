// ============================================================================
// 提炼记忆流程 —— 编排服务（唯一业务逻辑，跑在 background service worker）
// ----------------------------------------------------------------------------
// UI 层（浮窗 / 侧边栏 / popup）不直接碰接口，全部通过 CT_FLOW_* 消息调用这里。
// 队长接口调用统一走 shared/api-client.ts（契约 /v1/*，mock 自动降级）。
//
// 状态机：
//   idle ──start()──▶ previewing ──队长返回──▶ reviewing ──confirm()──▶ saving ──▶ done
//                        │                        │  ▲                        │
//                        └──失败──▶ error ◀──失败──┘  └──────reset()──────────┘
//                                （任意步骤可 reset() 回 idle）
// ============================================================================

import type { Conversation } from '../../shared/types'
import type { CaptainApi } from '../../shared/api-client'
import type { ExtractionFlowState } from './types'
import { initialFlowState } from './types'

const STORAGE_KEY = 'ct_extraction_flow'

export class ExtractionFlowService {
  constructor(private captainApi: CaptainApi) {}

  private cache: ExtractionFlowState | null = null

  // ---- 持久化：service worker 会被杀，状态落 chrome.storage.session ---- //

  private async load(): Promise<ExtractionFlowState> {
    if (this.cache) return this.cache
    try {
      const data = await chrome.storage.session.get(STORAGE_KEY)
      const stored = data[STORAGE_KEY] as ExtractionFlowState | undefined
      this.cache = stored || initialFlowState()
    } catch {
      this.cache = initialFlowState()
    }
    return this.cache
  }

  private async save(state: ExtractionFlowState): Promise<ExtractionFlowState> {
    state.updatedAt = new Date().toISOString()
    this.cache = state
    try {
      await chrome.storage.session.set({ [STORAGE_KEY]: state })
    } catch {
      /* 内存兜底：cache 已更新 */
    }
    return state
  }

  // ---- 查询 ---- //

  async getState(): Promise<ExtractionFlowState> {
    return this.load()
  }

  /** 供 UI 选择会话用：会话列表 + 消息（远端会话懒拉消息） */
  async listConversationsWithMessages(): Promise<Conversation[]> {
    const convs = await this.captainApi.listConversations()
    await Promise.all(
      convs.map(async (c) => {
        if (c.messages.length) return
        try {
          c.messages = await this.captainApi.getConversationMessages(c.id)
        } catch {
          /* 拉不到就空列表，UI 显示「消息不可用」 */
        }
      })
    )
    return convs
  }

  // ---- ① 选会话 / 勾选消息（本地，未发接口） ---- //

  /** 选中会话并给出默认勾选（前 4 条，不足则全选） */
  async pickConversation(conversationId: string): Promise<ExtractionFlowState> {
    const convs = await this.listConversationsWithMessages()
    const conv = convs.find((c) => c.id === conversationId)
    const state = await this.load()
    return this.save({
      ...initialFlowState(),
      conversationId,
      conversationTitle: conv?.title || '',
      source: conv?.source || '',
      selectedMessageIds: (conv?.messages || []).slice(0, 4).map((m) => m.id)
    })
  }

  async toggleMessage(messageId: string, checked: boolean): Promise<ExtractionFlowState> {
    const state = await this.load()
    const set = new Set(state.selectedMessageIds)
    if (checked) set.add(messageId)
    else set.delete(messageId)
    return this.save({ ...state, selectedMessageIds: Array.from(set) })
  }

  // ---- ② 发给队长：POST /v1/extractions/preview ---- //

  async start(): Promise<ExtractionFlowState> {
    const cur = await this.load()
    if (!cur.conversationId || !cur.selectedMessageIds.length) {
      return this.save({ ...cur, step: 'error', error: '请先选择会话并勾选至少一条消息' })
    }
    await this.save({ ...cur, step: 'previewing', error: null })
    try {
      const resp = await this.captainApi.extract(
        {
          conversationId: cur.conversationId,
          source: cur.source,
          selectedMessageIds: cur.selectedMessageIds
        },
        undefined
      )
      if (resp.error && !resp.candidates.length) {
        return this.save({ ...cur, step: 'error', error: resp.error })
      }
      if (!resp.candidates.length) {
        return this.save({
          ...cur,
          step: 'error',
          error: '队长没有从选中的消息里提炼出记忆，试着多勾几条或换一段对话。'
        })
      }
      return this.save({
        ...cur,
        step: 'reviewing',
        previewId: resp.previewId ?? null,
        candidates: resp.candidates,
        // 默认全部勾选，用户逐条取消
        selectedCandidateIds: resp.candidates.map((c) => c.id),
        edits: {},
        error: null
      })
    } catch (e) {
      return this.save({ ...cur, step: 'error', error: String((e as Error).message || e) })
    }
  }

  // ---- ③ 候选勾选 / 编辑（本地） ---- //

  async toggleCandidate(candidateId: string, checked: boolean): Promise<ExtractionFlowState> {
    const state = await this.load()
    const set = new Set(state.selectedCandidateIds)
    if (checked) set.add(candidateId)
    else set.delete(candidateId)
    return this.save({ ...state, selectedCandidateIds: Array.from(set) })
  }

  async setContent(candidateId: string, content: string): Promise<ExtractionFlowState> {
    const state = await this.load()
    return this.save({ ...state, edits: { ...state.edits, [candidateId]: content } })
  }

  // ---- ④ 确认保存：POST /v1/extractions/{preview_id}/commit ---- //

  async confirm(): Promise<ExtractionFlowState> {
    const cur = await this.load()
    if (cur.step !== 'reviewing') {
      return this.save({ ...cur, step: 'error', error: '当前没有可提交的提炼预览' })
    }
    if (!cur.selectedCandidateIds.length) {
      return this.save({ ...cur, step: 'error', error: '请先勾选要保存的记忆' })
    }
    await this.save({ ...cur, step: 'saving', error: null })
    try {
      // 用户编辑过的候选，用 edits 里的最新内容
      const chosen = cur.candidates
        .filter((c) => cur.selectedCandidateIds.includes(c.id))
        .map((c) => ({ ...c, content: cur.edits[c.id] ?? c.content }))
      const resp = await this.captainApi.save(
        chosen,
        cur.conversationId || '',
        cur.previewId || undefined
      )
      return this.save({ ...cur, step: 'done', savedCount: resp.saved })
    } catch (e) {
      return this.save({ ...cur, step: 'error', error: String((e as Error).message || e) })
    }
  }

  // ---- 回到 idle ---- //

  async reset(): Promise<ExtractionFlowState> {
    const cur = await this.load()
    return this.save({
      ...initialFlowState(),
      // 保留会话选择，方便连续提炼同一段对话
      conversationId: cur.conversationId,
      conversationTitle: cur.conversationTitle,
      source: cur.source,
      selectedMessageIds: cur.selectedMessageIds
    })
  }
}
