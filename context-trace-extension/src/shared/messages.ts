// chrome.runtime 消息协议
// 所有 popup / sidepanel / content / background 通信都走这套类型

import type {
  Conversation,
  ExtractRequest,
  ExtractResponse,
  SearchRequest,
  SearchResponse,
  CandidateMemory,
  ApiSettings,
  SavedMemory
} from './types'

/** content -> background：抓取当前活动 tab 的对话 */
export interface CapturePageMessage {
  type: 'CT_CAPTURE_PAGE'
  tabId: number
  url: string
}

/** background -> content：让 content 抓取并回传 */
export interface PickConversationMessage {
  type: 'CT_PICK_CONVERSATION'
  conversationId: string
}

/** background -> popup/sidepanel：把抓到的对话投递 */
export interface ConversationCapturedMessage {
  type: 'CT_CONVERSATION_CAPTURED'
  conversation: Conversation
}

/** popup/sidepanel -> background：请求提炼 */
export interface ExtractMemoriesMessage {
  type: 'CT_EXTRACT'
  payload: ExtractRequest
}

export interface ExtractMemoriesResponseMessage {
  type: 'CT_EXTRACT_RESULT'
  payload: ExtractResponse
}

/** popup/sidepanel -> background：保存候选（HTTP 模式需带提炼时拿到的 previewId） */
export interface SaveMemoriesMessage {
  type: 'CT_SAVE'
  payload: { candidates: CandidateMemory[]; conversationId: string; previewId?: string }
}

export interface SaveMemoriesResponseMessage {
  type: 'CT_SAVE_RESULT'
  payload: { saved: number }
}

/** popup/sidepanel -> background：搜索记忆 */
export interface SearchMemoriesMessage {
  type: 'CT_SEARCH'
  payload: SearchRequest
}

export interface SearchMemoriesResponseMessage {
  type: 'CT_SEARCH_RESULT'
  payload: SearchResponse
}

/** popup/sidepanel -> background：设置读写 */
export interface GetSettingsMessage { type: 'CT_GET_SETTINGS' }
export interface SaveSettingsMessage { type: 'CT_SAVE_SETTINGS'; payload: Partial<ApiSettings> }
export interface SettingsMessage { type: 'CT_SETTINGS'; payload: ApiSettings }

/** 队长 "翻译人话"：拿到记忆后让队长生成面向用户的回答 */
export interface AskCaptainMessage {
  type: 'CT_ASK_CAPTAIN'
  payload: { question: string; memories: SearchResponse }
}
export interface AskCaptainResponseMessage {
  type: 'CT_ASK_CAPTAIN_RESULT'
  payload: { answer: string }
}

/** 内部：列出已保存的记忆（popup 用） */
export interface ListMemoriesMessage { type: 'CT_LIST_MEMORIES' }
export interface ListMemoriesResponseMessage {
  type: 'CT_LIST_MEMORIES_RESULT'
  payload: SavedMemory[]
}

export interface ListConversationsMessage { type: 'CT_LIST_CONVERSATIONS' }
export interface ListConversationsResponseMessage {
  type: 'CT_LIST_CONVERSATIONS_RESULT'
  payload: Conversation[]
}

export type ExtMessage =
  | CapturePageMessage
  | PickConversationMessage
  | ConversationCapturedMessage
  | ExtractMemoriesMessage
  | ExtractMemoriesResponseMessage
  | SaveMemoriesMessage
  | SaveMemoriesResponseMessage
  | SearchMemoriesMessage
  | SearchMemoriesResponseMessage
  | GetSettingsMessage
  | SaveSettingsMessage
  | SettingsMessage
  | AskCaptainMessage
  | AskCaptainResponseMessage
  | ListMemoriesMessage
  | ListMemoriesResponseMessage
  | ListConversationsMessage
  | ListConversationsResponseMessage
