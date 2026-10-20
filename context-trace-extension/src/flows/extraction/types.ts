// ============================================================================
// 提炼记忆流程 —— 类型定义
// ----------------------------------------------------------------------------
// 流程（与 docs/api-data-contract.md 第 6 节一一对应）：
//
//   ① 用户在对话里勾选消息            （本地行为，不走接口）
//   ② 发给队长                        POST /v1/extractions/preview
//        入参  { conversation_id, message_ids }
//        返回  { preview_id, candidates[] }   —— 不落库
//   ③ 候选列举给用户勾选/编辑          （本地行为）
//   ④ 用户确认保存                     POST /v1/extractions/{preview_id}/commit
//        入参  { candidate_ids, overrides }
//        返回  { saved: Memory[] }               —— 这一步才写数据库
//   ⑤ 完成，记忆库可查                 GET /v1/memories
// ============================================================================

import type { CandidateMemory } from '../../shared/types'

/** 流程状态机的步骤 */
export type ExtractionStep =
  | 'idle' // 未开始 / 已重置
  | 'previewing' // ② 正在等队长返回候选
  | 'reviewing' // ③ 候选已列出，等用户勾选/编辑
  | 'saving' // ④ 正在提交落库
  | 'done' // ④ 成功，savedCount 有值
  | 'error' // ②④ 任一步失败，error 有值

/**
 * 提炼流程的完整状态。
 * 全部字段可 JSON 序列化（存 chrome.storage.session，跨 popup/sidepanel/浮窗共享）。
 */
export interface ExtractionFlowState {
  step: ExtractionStep
  /** 当前操作的会话 */
  conversationId: string | null
  conversationTitle: string
  source: string
  /** ① 用户勾选的消息（preview 入参 message_ids） */
  selectedMessageIds: string[]
  /** ② 队长返回的预览单号（commit 路径参数） */
  previewId: string | null
  /** ② 队长返回的候选记忆 */
  candidates: CandidateMemory[]
  /** ③ 用户勾选要保存的候选 id */
  selectedCandidateIds: string[]
  /** ③ 用户编辑后的候选内容（key = 候选 id，commit 时进 overrides） */
  edits: Record<string, string>
  /** ④ 实际保存条数 */
  savedCount: number | null
  /** ②④ 失败原因 */
  error: string | null
  updatedAt: string
}

export function initialFlowState(): ExtractionFlowState {
  return {
    step: 'idle',
    conversationId: null,
    conversationTitle: '',
    source: '',
    selectedMessageIds: [],
    previewId: null,
    candidates: [],
    selectedCandidateIds: [],
    edits: {},
    savedCount: null,
    error: null,
    updatedAt: new Date().toISOString()
  }
}
