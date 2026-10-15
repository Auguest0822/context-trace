<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { SavedMemory } from '../shared/types'
import type { ExtMessage } from '../shared/messages'

const settings = ref<{ mock: boolean; baseUrl: string }>({ mock: true, baseUrl: '' })
const memories = ref<SavedMemory[]>([])
const activeTab = ref<{ id: number; url: string } | null>(null)

async function send<T extends ExtMessage, R = any>(msg: T): Promise<R> {
  return chrome.runtime.sendMessage(msg)
}

async function loadAll() {
  settings.value = (await send({ type: 'CT_GET_SETTINGS' })) as any
  memories.value = (await send({ type: 'CT_LIST_MEMORIES' } as any)) || []
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (tab?.id != null) {
      activeTab.value = { id: tab.id, url: tab.url || '' }
    }
  } catch {}
}

onMounted(loadAll)

async function openSidePanel() {
  if (activeTab.value?.id != null) {
    try { await (chrome as any).sidePanel?.open({ tabId: activeTab.value.id }) } catch {}
  } else {
    window.open(chrome.runtime.getURL('sidepanel.html'), '_blank')
  }
}

async function captureHere() {
  if (activeTab.value == null) return
  await send({ type: 'CT_CAPTURE_PAGE', tabId: activeTab.value.id, url: activeTab.value.url })
  await loadAll()
  openSidePanel()
}

function openWebApp() {
  // 跳到 web 端（http://localhost:5180/）
  chrome.tabs.create({ url: 'http://localhost:5180/' })
}
</script>

<template>
  <div class="app">
    <header class="head">
      <div class="logo">言</div>
      <div>
        <div class="title">言迹 ContextTrace</div>
        <div class="subtitle">记忆提取 · 检索 · 跨 AI 对话</div>
      </div>
    </header>

    <div class="status">
      <span class="dot"></span>
      <span class="label">{{ settings.mock ? 'Mock 队长' : '已连接' }}</span>
      <span class="value">{{ settings.mock ? '本地模式' : (settings.baseUrl || '未配置') }}</span>
    </div>

    <div class="section">
      <h3>快捷操作</h3>
      <div class="actions">
        <button class="action-btn primary" @click="captureHere">
          <span class="icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </span>
          <span class="t">抓取当前对话</span>
          <span class="d">自动选中前 4 条</span>
        </button>
        <button class="action-btn" @click="openSidePanel">
          <span class="icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
          </span>
          <span class="t">打开检索面板</span>
          <span class="d">侧边栏长期显示</span>
        </button>
      </div>
    </div>

    <div class="section">
      <h3>最近的记忆（{{ memories.length }}）</h3>
      <div class="memories">
        <div v-if="!memories.length" class="empty">还没有保存的记忆。先到 AI 对话网站抓取一段对话试试。</div>
        <div v-for="m in memories.slice(0, 4)" :key="m.id" class="memory">
          <div class="top">
            <span class="cat" :class="m.category">{{ m.category }}</span>
            <span class="time">{{ m.time }}</span>
          </div>
          <div class="title">{{ m.title }}</div>
          <div class="content">{{ m.content }}</div>
        </div>
      </div>
    </div>

    <div class="footer">
      <span>v0.1.0 · MV3</span>
      <a href="#" @click.prevent="openWebApp">打开 Web 版 →</a>
    </div>
  </div>
</template>
