// content script 入口：仅在 AI 对话网站注入
// 1. 抓取当前页面的对话
// 2. 挂浮窗
// 3. 响应 background 的 CT_PICK_CONVERSATION

import { mountFloater, handleContentMessage } from './floater'
import { pickAdapter } from './adapter'
import type { Conversation } from '../shared/types'
import type { ExtMessage } from '../shared/messages'

mountFloater()

// 预抓取一次当前对话，浮窗打开时直接可用
try {
  const adapter = pickAdapter(location.href)
  const conv: Conversation | null = adapter.pickConversation()
  if (conv) {
    // 注入到 background 缓存
    chrome.runtime.sendMessage({ type: 'CT_CAPTURE_PAGE', tabId: -1, url: location.href }).catch(() => {})
  }
} catch (e) {
  console.warn('[CT] capture failed', e)
}

chrome.runtime.onMessage.addListener((msg: ExtMessage, _sender, sendResponse) => {
  const r = handleContentMessage(msg)
  if (r !== undefined) sendResponse(r)
})
