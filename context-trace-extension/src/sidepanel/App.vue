<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import type { SavedMemory, SearchResponse } from '../shared/types'
import type { ExtMessage } from '../shared/messages'

const tab = ref<'ask' | 'memories'>('ask')
const question = ref('初赛为什么优先保证本地复现？')
const mode = ref<'混合' | '关键词' | '向量'>('混合')
const memories = ref<SavedMemory[]>([])

const loading = ref(false)
const lastResp = ref<SearchResponse | null>(null)
const lastAnswer = ref<string>('')

const totalTokens = computed(() => (lastResp.value?.results || []).reduce((s, r) => s + (r.tokens || 0), 0))

async function send<T extends ExtMessage, R = any>(msg: T): Promise<R> {
  return chrome.runtime.sendMessage(msg)
}

onMounted(loadMemories)

async function loadMemories() {
  memories.value = (await send({ type: 'CT_LIST_MEMORIES' } as any)) || []
}

async function ask() {
  if (!question.value.trim()) return
  loading.value = true
  lastAnswer.value = ''
  lastResp.value = null
  try {
    const resp = (await send({
      type: 'CT_SEARCH',
      payload: { question: question.value, mode: mode.value }
    })) as SearchResponse
    lastResp.value = resp
    const a = (await send({
      type: 'CT_ASK_CAPTAIN',
      payload: { question: question.value, memories: resp }
    })) as { answer: string }
    lastAnswer.value = a.answer
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="layout">
    <header class="head">
      <div class="logo">言</div>
      <div>
        <div class="title">言迹 ContextTrace</div>
        <div class="subtitle">侧边栏 · 检索 / 记忆库</div>
      </div>
      <div class="right">
        <span class="dot"></span>
        <span>Mock 队长</span>
      </div>
    </header>

    <div class="tabs">
      <button class="tab" :class="{ active: tab === 'ask' }" @click="tab = 'ask'">提问</button>
      <button class="tab" :class="{ active: tab === 'memories' }" @click="tab = 'memories'; loadMemories()">记忆库（{{ memories.length }}）</button>
    </div>

    <div class="body">
      <!-- 提问 -->
      <template v-if="tab === 'ask'">
        <div class="search-box">
          <input v-model="question" type="text" placeholder="把问题发给队长，TA 会用记忆库回答" @keydown.enter="ask" />
        </div>
        <div class="filter-line">
          <div class="mode-tabs">
            <button class="mode-tab" v-for="m in ['混合','关键词','向量']" :key="m" :class="{ active: mode === m }" @click="mode = m as any">{{ m }}</button>
          </div>
        </div>

        <div v-if="loading" class="loading">队长正在查阅记忆库</div>

        <div v-if="lastAnswer" class="answer">{{ lastAnswer }}</div>

        <div v-if="lastResp && lastResp.results.length">
          <div class="result" v-for="r in lastResp.results" :key="r.id">
            <div class="top">
              <span class="cat" :class="r.category">{{ r.category }}</span>
              <span class="time">{{ r.time }} · 约 {{ r.tokens }} tokens</span>
            </div>
            <div class="title">{{ r.title }}</div>
            <div class="content">{{ r.content }}</div>
            <div class="meta">{{ r.source }} · {{ r.conversationLabel }} · {{ r.matchedBy.join(' / ') }}</div>
          </div>
        </div>

        <div v-if="!loading && !lastResp" class="empty">输入问题开始检索。队长会先用记忆库找线索，再用 LLM 翻译成回答。</div>
      </template>

      <!-- 记忆库 -->
      <template v-else>
        <div v-if="!memories.length" class="empty">还没有保存的记忆。先回到 AI 对话页面，用右下角浮窗抓取并提取记忆。</div>
        <div v-for="m in memories" :key="m.id" class="result">
          <div class="top">
            <span class="cat" :class="m.category">{{ m.category }}</span>
            <span class="time">{{ m.time }}</span>
          </div>
          <div class="title">{{ m.title }}</div>
          <div class="content">{{ m.content }}</div>
          <div class="meta">{{ m.source }} · {{ m.conversation }}</div>
        </div>
      </template>
    </div>
  </div>
</template>
