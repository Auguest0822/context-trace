<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { store } from '../store'
import { CONVERSATIONS, MESSAGES, FILTERS } from '../data/mock'
import { loadConversations, loadConversationDetail, loadMessages } from '../data/archiveApi'
import SourceBadge from '../components/SourceBadge.vue'

const router = useRouter()
const route = useRoute()
const isApiArchive = import.meta.env.VITE_ARCHIVE_DATA_SOURCE === 'api'
const apiConfig = {
  baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  scope: import.meta.env.VITE_ARCHIVE_SCOPE || 'project:context-trace'
}

const activeFilter = ref('all')
const keyword = ref('')
const conversations = ref(isApiArchive ? [] : CONVERSATIONS)
const apiMessages = ref([])
const activeConvId = ref(isApiArchive ? null : 1)
const selectedMsgIds = ref(new Set(isApiArchive ? [] : [2, 3]))
const loadingConversations = ref(false)
const loadingMessages = ref(false)
const listError = ref('')
const detailError = ref('')
let detailController = null

const currentMessages = computed(() => isApiArchive ? apiMessages.value : MESSAGES)
const filters = computed(() => {
  if (!isApiArchive) return FILTERS
  return [
    { key: 'all', label: '全部', count: conversations.value.length },
    ...['DeepSeek', 'Kimi', '豆包', 'Agent', '其他'].map(source => ({
      key: source,
      label: source,
      count: conversations.value.filter(c => c.source === source).length
    }))
  ]
})

const filteredConvs = computed(() =>
  conversations.value.filter(c => {
    if (activeFilter.value !== 'all' && c.source !== activeFilter.value) return false
    if (keyword.value && !c.title.includes(keyword.value)) return false
    return true
  })
)

const activeConv = computed(() => conversations.value.find(c => c.id === activeConvId.value))

async function selectConversation(id) {
  activeConvId.value = id
  if (!isApiArchive) return
  detailController?.abort()
  const controller = new AbortController()
  detailController = controller
  apiMessages.value = []
  selectedMsgIds.value = new Set()
  detailError.value = ''
  loadingMessages.value = true
  store.archiveStatus = 'checking'
  try {
    const conversation = conversations.value.find(c => c.id === id)
    const [detail, messages] = await Promise.all([
      loadConversationDetail(apiConfig, id, controller.signal),
      loadMessages(apiConfig, conversation, controller.signal)
    ])
    if (detailController !== controller) return
    conversations.value = conversations.value.map(c => c.id === id ? detail : c)
    apiMessages.value = messages
    store.archiveStatus = 'ready'
  } catch (error) {
    if (error.name !== 'AbortError' && detailController === controller) {
      detailError.value = error.message
      store.archiveStatus = 'error'
    }
  } finally {
    if (detailController === controller) loadingMessages.value = false
  }
}

async function refreshArchive() {
  if (!isApiArchive) return
  detailController?.abort()
  store.archiveStatus = 'checking'
  loadingConversations.value = true
  listError.value = ''
  try {
    const items = await loadConversations(apiConfig)
    store.archiveStatus = 'ready'
    conversations.value = items
    const linkedConversationId = typeof route.query.conversation === 'string'
      ? route.query.conversation : null
    const nextId = items.some(c => c.id === linkedConversationId)
      ? linkedConversationId
      : items.some(c => c.id === activeConvId.value)
        ? activeConvId.value : items[0]?.id ?? null
    activeConvId.value = nextId
    if (nextId !== null) {
      await selectConversation(nextId)
      if (route.query.message) {
        await nextTick()
        document.getElementById(`archive-message-${route.query.message}`)?.scrollIntoView({ block: 'center' })
      }
    }
    else {
      apiMessages.value = []
      selectedMsgIds.value = new Set()
      detailError.value = ''
      loadingMessages.value = false
    }
  } catch (error) {
    store.archiveStatus = 'error'
    listError.value = error.message
    conversations.value = []
    apiMessages.value = []
    activeConvId.value = null
    selectedMsgIds.value = new Set()
    loadingMessages.value = false
  } finally {
    loadingConversations.value = false
  }
}

onMounted(refreshArchive)
onUnmounted(() => detailController?.abort())

function toggleMsg(id) {
  const s = new Set(selectedMsgIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedMsgIds.value = s
}

function toggleAll() {
  if (selectedMsgIds.value.size === currentMessages.value.length) {
    selectedMsgIds.value = new Set()
  } else {
    selectedMsgIds.value = new Set(currentMessages.value.map(m => m.id))
  }
}

const selectedCount = computed(() => selectedMsgIds.value.size)

function extractMemory() {
  if (!selectedCount.value || (isApiArchive && (selectedCount.value > 20 || loadingMessages.value))) return
  store.selectedMessages = currentMessages.value.filter(m => selectedMsgIds.value.has(m.id))
  store.selectedConversationId = isApiArchive ? String(activeConv.value.id) : null
  store.selectedConversationTitle = activeConv.value?.title || ''
  router.push('/extract')
}
</script>

<template>
  <div class="archive-page">
    <div class="page-head">
      <h1>对话档案</h1>
      <p class="sub">查看从不同 AI 应用保存的对话。</p>
    </div>

    <!-- 过滤标签行 -->
    <div class="filter-row">
      <div class="filter-tags">
        <button
          v-for="f in filters"
          :key="f.key"
          class="filter-tag"
          :class="{ active: activeFilter === f.key }"
          @click="activeFilter = f.key"
        >
          <SourceBadge v-if="f.key !== 'all'" :source="f.key" :size="18" />
          <span class="tag-label">{{ f.label }}</span>
          <span class="tag-count">{{ f.count }}</span>
        </button>
      </div>
      <div class="search-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input v-model="keyword" type="text" placeholder="搜索对话标题…" />
      </div>
    </div>

    <!-- 主体两栏 -->
    <div class="main-grid">
      <!-- 左：会话列表 -->
      <div class="conv-list">
        <div class="list-toolbar">
          <button class="sort-btn">
            按更新时间
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
          </button>
          <button class="filter-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/></svg>
          </button>
          <button v-if="isApiArchive" class="reload-btn" :disabled="loadingConversations" @click="refreshArchive">刷新</button>
        </div>

        <p v-if="loadingConversations" class="archive-state">正在读取对话…</p>
        <div v-else-if="listError" class="archive-state archive-error">
          <p>{{ listError }}</p>
          <button @click="refreshArchive">重试</button>
        </div>
        <p v-else-if="!filteredConvs.length" class="archive-state">{{ conversations.length ? '没有匹配的对话' : '暂无归档对话' }}</p>

        <div
          v-for="c in filteredConvs"
          :key="c.id"
          class="conv-item"
          :class="{ active: c.id === activeConvId }"
          @click="selectConversation(c.id)"
        >
          <div class="conv-top">
            <SourceBadge :source="c.source" :size="20" />
            <span class="conv-source">{{ c.source }}</span>
            <span class="conv-time">{{ c.time }}</span>
          </div>
          <h3 class="conv-title">{{ c.title }}</h3>
          <p class="conv-summary">{{ c.summary }}</p>
          <div class="conv-meta">
            <span class="meta-msgs">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              {{ c.messageCount }} 条消息
            </span>
            <span v-if="c.badge" class="badge-selected">{{ c.badge }}</span>
            <span v-else-if="c.visible" class="badge-visible">当前页可见</span>
          </div>
        </div>
      </div>

      <!-- 右：会话详情 -->
      <div class="conv-detail" v-if="activeConv">
        <div class="detail-head">
          <div class="head-info">
            <div class="head-title-row">
              <h2>{{ activeConv.title }}</h2>
              <span class="head-source">
                <SourceBadge :source="activeConv.source" :size="18" />
                {{ activeConv.source }}
              </span>
            </div>
            <p class="head-meta">{{ activeConv.createdAt }} · {{ activeConv.messageCount }} 条消息</p>
          </div>
          <div class="head-actions">
            <span v-if="isApiArchive" class="archived-label">已归档</span>
            <button v-else class="btn-ghost-teal save-btn" @click="store.showToast('已保存当前对话到档案')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/></svg>
              保存当前对话
            </button>
            <button class="more-btn">
              <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg>
            </button>
          </div>
        </div>

        <div class="msg-list">
          <p v-if="loadingMessages" class="archive-state">正在读取消息…</p>
          <div v-else-if="detailError" class="archive-state archive-error">
            <p>{{ detailError }}</p>
            <button @click="selectConversation(activeConvId)">重试</button>
          </div>
          <p v-else-if="!currentMessages.length" class="archive-state">这段对话没有消息</p>
          <div v-for="m in currentMessages" :id="isApiArchive ? `archive-message-${m.id}` : undefined" :key="m.id" class="msg-row" :class="{ 'source-highlight': isApiArchive && String(m.id) === String(route.query.message) }">
            <div class="msg-side">
              <span
                class="checkbox"
                :class="{ checked: selectedMsgIds.has(m.id) }"
                @click="toggleMsg(m.id)"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
              </span>
            </div>
            <div class="msg-main">
              <div class="msg-head">
                <span v-if="m.role === '我'" class="avatar-me">R</span>
                <SourceBadge v-else :source="m.source" :size="22" />
                <span class="msg-role">{{ m.role }}</span>
                <span class="msg-time">{{ m.time }}</span>
                <span class="msg-seq"># {{ m.seq }}</span>
              </div>
              <div class="msg-bubble" :class="{ mine: m.role === '我' }">
                <p v-for="(line, i) in m.text.split('\n')" :key="i">{{ line }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="detail-foot">
          <div class="foot-info">
            <p class="foot-count">已选 {{ selectedCount }} 条消息</p>
            <p class="foot-tip">{{ isApiArchive ? '最多选择 20 条；进入人工候选预览' : '可从选中内容提取记忆' }}</p>
          </div>
          <button class="btn-primary" :disabled="!selectedCount || (isApiArchive && (selectedCount > 20 || loadingMessages))" @click="extractMemory">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
            提取记忆
          </button>
        </div>
      </div>
      <div v-else-if="isApiArchive && !loadingConversations && !listError" class="conv-detail empty-detail">暂无可查看的对话</div>
    </div>
  </div>
</template>

<style scoped>
.source-highlight { outline: 2px solid var(--primary); outline-offset: -2px; border-radius: 10px; }
.page-head h1 { font-size: 22px; font-weight: 700; }
.page-head .sub { margin-top: 6px; font-size: 13.5px; color: var(--text-secondary); }

.filter-row {
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.filter-tags { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.filter-tag {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 13px;
  border-radius: 8px;
  border: 1px solid var(--border-strong);
  background: #fff;
  color: var(--text);
  font-size: 13px;
  transition: all 0.15s;
}
.filter-tag:hover { border-color: var(--primary); }
.filter-tag.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}
.tag-count {
  font-size: 12px;
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-secondary);
}
.filter-tag.active .tag-count { background: rgba(255, 255, 255, 0.2); color: #fff; }

.search-box {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  padding: 8px 12px;
  width: 260px;
}
.search-box svg { width: 15px; height: 15px; color: var(--text-tertiary); flex-shrink: 0; }
.search-box input { border: none; flex: 1; min-width: 0; background: transparent; }
.search-box:focus-within { border-color: var(--primary); }

.main-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 290px 1fr;
  gap: 16px;
  align-items: start;
}

/* 左列表 */
.conv-list {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.archive-state { padding: 12px; color: var(--text-secondary); font-size: 13px; }
.archive-error { color: #b42318; overflow-wrap: anywhere; }
.archive-error button, .reload-btn { color: var(--primary); font-size: 12px; font-weight: 600; }
.archive-error button { margin-top: 6px; }
.reload-btn:disabled { opacity: 0.5; }
.archived-label { color: var(--primary); font-size: 12px; }
.empty-detail { align-items: center; justify-content: center; color: var(--text-tertiary); font-size: 13px; }
.list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
}
.sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12.5px;
  color: var(--text-secondary);
}
.sort-btn svg { width: 13px; height: 13px; }
.filter-icon {
  width: 28px; height: 28px;
  border-radius: 6px;
  color: var(--text-secondary);
  display: flex; align-items: center; justify-content: center;
}
.filter-icon:hover { background: #f2f6f5; }
.filter-icon svg { width: 15px; height: 15px; }

.conv-item {
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.12s;
}
.conv-item:hover { background: #f7fafa; }
.conv-item.active {
  background: var(--primary-bg-soft);
  border-color: rgba(15, 118, 110, 0.25);
}
.conv-top { display: flex; align-items: center; gap: 8px; }
.conv-source { font-size: 12.5px; color: var(--text-secondary); }
.conv-time { margin-left: auto; font-size: 12px; color: var(--text-tertiary); }
.conv-title { margin-top: 9px; font-size: 14.5px; font-weight: 600; }
.conv-summary {
  margin-top: 5px;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.conv-meta {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.meta-msgs {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.meta-msgs svg { width: 13px; height: 13px; }
.badge-selected, .badge-visible {
  margin-left: auto;
  font-size: 11.5px;
  padding: 2px 8px;
  border-radius: 999px;
}
.badge-selected { background: var(--primary-bg); color: var(--primary); font-weight: 500; }
.badge-visible { border: 1px solid var(--border-strong); color: var(--text-tertiary); }

/* 右详情 */
.conv-detail {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  min-height: 620px;
}
.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
}
.head-title-row { display: flex; align-items: center; gap: 10px; }
.head-title-row h2 { font-size: 17px; font-weight: 700; }
.head-source {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: var(--text-secondary);
}
.head-meta { margin-top: 6px; font-size: 12.5px; color: var(--text-tertiary); }
.head-actions { display: flex; align-items: center; gap: 8px; }
.more-btn {
  width: 32px; height: 32px;
  border-radius: 8px;
  color: var(--text-secondary);
  display: flex; align-items: center; justify-content: center;
}
.more-btn:hover { background: #f2f6f5; }
.more-btn svg { width: 17px; height: 17px; }

.msg-list {
  flex: 1;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.msg-row { display: flex; gap: 12px; }
.msg-side { padding-top: 2px; }
.msg-main { flex: 1; min-width: 0; }
.msg-head { display: flex; align-items: center; gap: 8px; }
.avatar-me {
  width: 22px; height: 22px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
.msg-role { font-size: 13px; font-weight: 600; }
.msg-time { font-size: 12px; color: var(--text-tertiary); }
.msg-seq { margin-left: auto; font-size: 12px; color: var(--text-tertiary); }

.msg-bubble {
  margin-top: 8px;
  background: #eef3f6;
  border-radius: 4px 12px 12px 12px;
  padding: 12px 14px;
  line-height: 1.7;
  font-size: 13.5px;
}
.msg-bubble.mine { background: #f3f4f4; }

.detail-foot {
  border-top: 1px solid var(--border);
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.foot-count { font-size: 13px; font-weight: 600; }
.foot-tip { margin-top: 3px; font-size: 12px; color: var(--text-tertiary); }
</style>
