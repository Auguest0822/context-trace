// background service worker：MV3 入口
// 职责：
//  1. 消息路由（popup / sidepanel / content 全部走这里）
//  2. chrome.storage 持久化设置
//  3. 队长接口代理 —— 统一走 shared/api-client.ts（契约 /v1/*，mock 自动降级）
//  4. 维护跨 tab 的对话档案缓存

import { createCaptainApi } from '../shared/api-client'
import type { Conversation } from '../shared/types'
import type { ExtMessage } from '../shared/messages'
import type { ApiSettings } from '../shared/types'

const SETTINGS_KEY = 'ct_settings'

const defaults: ApiSettings = {
  baseUrl: '',
  modelName: '',
  apiKey: '',
  mock: true
}

async function getSettings(): Promise<ApiSettings> {
  const { [SETTINGS_KEY]: stored } = await chrome.storage.local.get(SETTINGS_KEY)
  return { ...defaults, ...(stored || {}) }
}

async function saveSettings(patch: Partial<ApiSettings>) {
  const cur = await getSettings()
  const next = { ...cur, ...patch }
  await chrome.storage.local.set({ [SETTINGS_KEY]: next })
  return next
}

// 队长接口门面：mock 模式 / 契约 HTTP 模式自动切换
const captainApi = createCaptainApi({ getSettings })

// —— 消息分发 —— //
chrome.runtime.onMessage.addListener((msg: ExtMessage, sender, sendResponse) => {
  handle(msg, sender).then(sendResponse).catch((err) => {
    console.error('[CT background] error', err)
    sendResponse({ error: String(err?.message || err) })
  })
  return true // 异步响应
})

async function handle(msg: ExtMessage, sender: chrome.runtime.MessageSender): Promise<any> {
  switch (msg.type) {
    case 'CT_CAPTURE_PAGE': {
      // 让对应 tab 的 content script 抓取对话
      const tabId = sender.tab?.id ?? msg.tabId
      if (!tabId) return { error: 'no tabId' }
      try {
        const resp = await chrome.tabs.sendMessage(tabId, { type: 'CT_PICK_CONVERSATION' })
        const conv: Conversation | undefined = resp?.conversation
        if (conv) {
          await captainApi.putConversation(conv)
        }
        return { conversation: conv }
      } catch (e) {
        return { error: 'content script 未就绪：' + String((e as Error).message) }
      }
    }

    case 'CT_EXTRACT': {
      // 契约两步提炼第一步：POST /v1/extractions/preview
      return captainApi.extract(msg.payload)
    }

    case 'CT_SAVE': {
      // 契约两步提炼第二步：POST /v1/extractions/{preview_id}/commit
      return captainApi.save(
        msg.payload.candidates,
        msg.payload.conversationId,
        msg.payload.previewId
      )
    }

    case 'CT_SEARCH': {
      // POST /v1/memories/search（响应含 trace_id / selected_form / token_count / budget）
      return captainApi.search(msg.payload)
    }

    case 'CT_ASK_CAPTAIN': {
      // 翻译人话：HTTP 模式走 POST /v1/memories/context 拼最终上下文
      return { answer: await captainApi.askCaptain(msg.payload.question, msg.payload.memories) }
    }

    case 'CT_LIST_MEMORIES': {
      return captainApi.listSavedMemories()
    }

    case 'CT_LIST_CONVERSATIONS': {
      return captainApi.listConversations()
    }

    case 'CT_GET_SETTINGS': {
      return await getSettings()
    }

    case 'CT_SAVE_SETTINGS': {
      return await saveSettings(msg.payload)
    }

    default:
      return { error: 'unknown message: ' + (msg as any).type }
  }
}

// 工具栏图标点击 → 打开 side panel（如果用户点的是工具栏而不是 popup）
chrome.action?.onClicked?.addListener(async (tab) => {
  if (tab.id != null) {
    try { await (chrome as any).sidePanel?.open({ tabId: tab.id }) } catch {}
  }
})

// 安装时输出 banner
chrome.runtime.onInstalled.addListener(() => {
  console.log('[CT] installed')
})
