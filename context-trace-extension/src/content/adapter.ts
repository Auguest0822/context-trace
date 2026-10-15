// AI 网站 DOM 适配器
// 每个网站提供：
//   match(): boolean     —— 是否适用于当前页面
//   source: string       —— 来源名（与 mock.js 的 SOURCES 对齐）
//   pickConversation(): Conversation  —— 抓取当前对话
// 加新网站只需要在这里再加一个 SiteAdapter 即可。

import type { Conversation, ChatMessage } from '../shared/types'

export interface SiteAdapter {
  name: string
  match: (url: string) => boolean
  pickConversation: () => Conversation | null
}

/** 通用兜底：抓取页面上所有看起来像聊天气泡的元素 */
const generic: SiteAdapter = {
  name: 'Generic',
  match: () => false,
  pickConversation() {
    const bubbles = document.querySelectorAll<HTMLElement>(
      '[class*="message"], [class*="Message"], [class*="bubble"], [class*="chat"], [class*="chat-item"]'
    )
    if (!bubbles.length) return null
    const messages: ChatMessage[] = Array.from(bubbles).slice(-30).map((el, i): ChatMessage => {
      const cls = (el.className || '') + ' ' + (el.getAttribute('data-role') || '')
      const role: ChatMessage['role'] = /user|我|human|问/i.test(cls) ? 'user' : 'assistant'
      return {
        id: `m-${i}`,
        role,
        text: (el.innerText || '').trim().slice(0, 2000)
      }
    }).filter((m) => m.text)
    if (!messages.length) return null
    return makeConv('Generic', messages)
  }
}

/** DeepSeek */
const deepseek: SiteAdapter = {
  name: 'DeepSeek',
  match: (u) => /chat\.deepseek\.com/.test(u),
  pickConversation() {
    const items = document.querySelectorAll<HTMLElement>('div[class*="message"], div[class*="Message"]')
    const messages = collectByPair(items)
    if (!messages.length) return generic.pickConversation()
    return makeConv('DeepSeek', messages)
  }
}

/** Kimi */
const kimi: SiteAdapter = {
  name: 'Kimi',
  match: (u) => /kimi\.moonshot\.cn|kimi\.com/.test(u),
  pickConversation() {
    const items = document.querySelectorAll<HTMLElement>('[class*="chat-item"], [class*="message"], .segment')
    const messages = collectByPair(items)
    if (!messages.length) return generic.pickConversation()
    return makeConv('Kimi', messages)
  }
}

/** 豆包 */
const doubao: SiteAdapter = {
  name: '豆包',
  match: (u) => /doubao\.com/.test(u),
  pickConversation() {
    const items = document.querySelectorAll<HTMLElement>('[class*="message"], [class*="Message"], [class*="bubble"]')
    const messages = collectByPair(items)
    if (!messages.length) return generic.pickConversation()
    return makeConv('豆包', messages)
  }
}

/** ChatGPT */
const chatgpt: SiteAdapter = {
  name: 'ChatGPT',
  match: (u) => /chat\.openai\.com|chatgpt\.com/.test(u),
  pickConversation() {
    const items = document.querySelectorAll<HTMLElement>('[data-message-author-role], [class*="message"]')
    const messages: ChatMessage[] = Array.from(items).map((el, i) => {
      const role = (el.getAttribute('data-message-author-role') || /assistant|ai/i.test(el.className) ? 'assistant' : 'user') as any
      return {
        id: `m-${i}`,
        role,
        text: (el.innerText || '').trim()
      }
    }).filter((m) => m.text)
    if (!messages.length) return generic.pickConversation()
    return makeConv('ChatGPT', messages)
  }
}

/** Gemini */
const gemini: SiteAdapter = {
  name: 'Gemini',
  match: (u) => /gemini\.google\.com/.test(u),
  pickConversation() {
    const items = document.querySelectorAll<HTMLElement>('[class*="message"], message-content, user-query')
    const messages = collectByPair(items)
    if (!messages.length) return generic.pickConversation()
    return makeConv('Gemini', messages)
  }
}

export const ADAPTERS: SiteAdapter[] = [deepseek, kimi, doubao, chatgpt, gemini, generic]

export function pickAdapter(url: string): SiteAdapter {
  return ADAPTERS.find((a) => a.match(url)) || generic
}

// —— 工具 —— //
function collectByPair(items: NodeListOf<HTMLElement>): ChatMessage[] {
  // 把同一行配对的 user + assistant 视作一条；只取每条的文字
  const out: ChatMessage[] = []
  items.forEach((el, i) => {
    const text = (el.innerText || '').trim()
    if (!text || text.length < 2) return
    const role: 'user' | 'assistant' = /user|human|me|我|你|question|query/i.test(el.className + ' ' + (el.getAttribute('data-role') || ''))
      ? 'user' : 'assistant'
    out.push({ id: `m-${i}`, role, text: text.slice(0, 2000) })
  })
  // 去重（避免父元素和子元素都被算进）
  const seen = new Set<string>()
  return out.filter((m) => {
    const key = m.text.slice(0, 40)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function makeConv(source: string, messages: ChatMessage[]): Conversation {
  const title =
    document.title.replace(/[-|·].*$/, '').trim() ||
    `对话于 ${new Date().toLocaleString('zh-CN')}`
  return {
    id: `c-${Date.now()}`,
    title,
    source,
    url: location.href,
    messages,
    capturedAt: new Date().toISOString()
  }
}
