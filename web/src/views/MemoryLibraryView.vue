<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { listMemories } from '../data/memoryApi'

const router = useRouter()
const isApi = import.meta.env.VITE_ARCHIVE_DATA_SOURCE === 'api'
const items = ref([])
const loading = ref(false)
const error = ref('')
const status = ref('active')
const kind = ref('')
const platform = ref('')

const shown = computed(() => isApi ? items.value : [])

async function refresh() {
  if (!isApi) return
  loading.value = true
  error.value = ''
  try {
    items.value = await listMemories({ status: status.value, kind: kind.value, platform: platform.value })
  } catch (reason) {
    error.value = `记忆 API 读取失败：${reason.message}`
  } finally {
    loading.value = false
  }
}

function openSource(memory) {
  const message = memory.source_message_ids?.[0]
  if (memory.conversation_id && message) {
    router.push({ path: '/archive', query: { conversation: memory.conversation_id, message } })
  }
}

watch([status, kind, platform], refresh)
onMounted(refresh)
</script>

<template>
  <main class="memory-library">
    <header class="page-head">
      <div><h1>记忆库</h1><p>只显示用户确认写入的记忆；每条记忆都保留出处。</p></div>
      <button class="refresh" @click="refresh">刷新</button>
    </header>
    <div v-if="!isApi" class="notice">当前是演示模式。切换为 API 模式后可浏览 seekdb 中已确认的记忆。</div>
    <div class="filters">
      <label>状态 <select v-model="status"><option value="active">有效</option><option value="superseded">已替代</option><option value="expired">已过期</option></select></label>
      <label>类别 <select v-model="kind"><option value="">全部</option><option value="decision">决策</option><option value="constraint">约束</option><option value="fact">事实</option><option value="preference">偏好</option><option value="skill">技能</option></select></label>
      <label>平台 <select v-model="platform"><option value="">全部</option><option value="deepseek">DeepSeek</option><option value="kimi">Kimi</option><option value="doubao">豆包</option><option value="agent">Agent</option><option value="other">其他</option></select></label>
    </div>
    <p v-if="loading">正在读取记忆…</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="isApi && !loading && !error && !shown.length" class="empty">当前筛选下还没有已确认的记忆。</p>
    <div class="cards">
      <article v-for="memory in shown" :key="memory.id" class="card">
        <div class="meta"><span>{{ memory.kind }}</span><span>{{ memory.source_platform || memory.source_type }}</span><span>{{ memory.created_at }}</span></div>
        <h2>{{ memory.summary || memory.content }}</h2>
        <p v-if="memory.summary" class="content">{{ memory.content }}</p>
        <blockquote>{{ memory.source_excerpt }}</blockquote>
        <div class="footer"><small>{{ memory.source_ref }}</small><button v-if="memory.conversation_id && memory.source_message_ids?.length" @click="openSource(memory)">查看原消息</button></div>
      </article>
    </div>
  </main>
</template>

<style scoped>
.memory-library { padding: 28px; max-width: 1100px; }
.page-head { display: flex; justify-content: space-between; align-items: start; }
h1 { font-size: 23px; } .page-head p { color: var(--text-secondary); margin-top: 8px; }
.refresh, .footer button { color: var(--primary); font-weight: 600; }
.filters { display: flex; gap: 16px; margin: 24px 0; flex-wrap: wrap; }
.filters label { color: var(--text-secondary); font-size: 13px; }
.filters select { margin-left: 8px; padding: 7px; border: 1px solid var(--border); border-radius: 7px; background: white; }
.cards { display: grid; gap: 14px; }
.card { padding: 18px; background: white; border: 1px solid var(--border); border-radius: 10px; }
.meta { display: flex; gap: 12px; color: var(--text-tertiary); font-size: 12px; }
h2 { font-size: 16px; margin: 12px 0; } .content { line-height: 1.7; }
blockquote { border-left: 3px solid var(--primary); margin: 14px 0; padding: 8px 14px; color: var(--text-secondary); background: #fafbfb; }
.footer { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
.footer small { overflow-wrap: anywhere; color: var(--text-tertiary); }
.notice, .empty { padding: 28px; background: white; border-radius: 10px; color: var(--text-secondary); }
.error { color: #b91c1c; }
</style>
