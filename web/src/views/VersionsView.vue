<script setup>
import { onMounted, ref } from 'vue'
import { forgetMemory, listMemories, loadMemoryHistory, reconcileMemory } from '../data/memoryApi'

const isApi = import.meta.env.VITE_ARCHIVE_DATA_SOURCE === 'api'
const items = ref([])
const selected = ref(null)
const history = ref([])
const error = ref('')
const busy = ref(false)
const form = ref({ kind: 'decision', content: '', summary: '', source_type: 'doc',
  source_ref: '', source_excerpt: '', conversation_id: '', source_message_ids: '', reason: '' })

async function refresh() {
  if (!isApi) return
  error.value = ''
  try {
    const [active, superseded, expired] = await Promise.all([
      listMemories({ status: 'active' }), listMemories({ status: 'superseded' }),
      listMemories({ status: 'expired' })
    ])
    items.value = [...active, ...superseded, ...expired].sort((a, b) => b.created_at.localeCompare(a.created_at))
  } catch (reason) { error.value = `加载记忆失败：${reason.message}` }
}

async function choose(memory) {
  selected.value = memory
  try { history.value = (await loadMemoryHistory(memory.id)).items }
  catch (reason) { error.value = `读取版本历史失败：${reason.message}` }
}

async function replace() {
  if (!selected.value || selected.value.status !== 'active') return
  busy.value = true
  error.value = ''
  try {
    const replacement = { kind: form.value.kind, content: form.value.content,
      summary: form.value.summary || null, source_type: form.value.source_type,
      source_excerpt: form.value.source_excerpt }
    if (replacement.source_type === 'chat') {
      replacement.conversation_id = form.value.conversation_id
      replacement.source_message_ids = form.value.source_message_ids.split(',').map(s => s.trim()).filter(Boolean)
    } else replacement.source_ref = form.value.source_ref
    const result = await reconcileMemory(selected.value.id, replacement, form.value.reason)
    await refresh()
    await choose(result.new_memory)
    form.value = { kind: 'decision', content: '', summary: '', source_type: 'doc',
      source_ref: '', source_excerpt: '', conversation_id: '', source_message_ids: '', reason: '' }
  } catch (reason) { error.value = `替代失败：${reason.message}` }
  finally { busy.value = false }
}

async function remove() {
  if (!selected.value || !window.confirm(`永久删除记忆 #${selected.value.id}？正文、向量和轨迹引用会清除。`)) return
  busy.value = true
  error.value = ''
  try {
    await forgetMemory(selected.value.id)
    selected.value = null
    history.value = []
    await refresh()
  } catch (reason) { error.value = `删除失败：${reason.message}` }
  finally { busy.value = false }
}

onMounted(refresh)
</script>

<template>
  <main class="versions">
    <header><div><h1>版本与冲突</h1><p>由用户明确指定旧记忆，再记录替代依据；历史内容仍可追溯。</p></div><button @click="refresh">刷新</button></header>
    <p v-if="!isApi" class="notice">当前是演示模式。切换为 API 模式后可管理真实记忆版本。</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-if="isApi" class="grid">
      <section class="list">
        <button v-for="memory in items" :key="memory.id" class="memory" :class="{ chosen: selected?.id === memory.id }" @click="choose(memory)">
          <strong>#{{ memory.id }} · {{ memory.summary || memory.content }}</strong>
          <small>{{ memory.status }} · {{ memory.source_ref }}</small>
        </button>
        <p v-if="!items.length">还没有记忆。</p>
      </section>
      <section v-if="selected" class="detail">
        <h2>记忆 #{{ selected.id }}</h2>
        <p>{{ selected.content }}</p>
        <blockquote>{{ selected.source_excerpt }}</blockquote>
        <p>来源：{{ selected.source_ref }}</p>
        <h3>版本历史</h3>
        <ol><li v-for="entry in history" :key="entry.memory.id">#{{ entry.memory.id }} · {{ entry.memory.status }} · {{ entry.memory.content }}<small v-if="entry.reason">替代理由：{{ entry.reason }}</small></li></ol>
        <form v-if="selected.status === 'active'" @submit.prevent="replace">
          <h3>用新记忆替代</h3>
          <label>类别<select v-model="form.kind"><option value="decision">决策</option><option value="constraint">约束</option><option value="fact">事实</option><option value="preference">偏好</option><option value="skill">技能</option></select></label>
          <label>新结论<textarea v-model="form.content" required maxlength="8000" /></label>
          <label>摘要<input v-model="form.summary" maxlength="512" /></label>
          <label>来源类型<select v-model="form.source_type"><option value="doc">文档</option><option value="git">Git</option><option value="issue">Issue</option><option value="manual">人工确认</option><option value="chat">已归档聊天</option></select></label>
          <label v-if="form.source_type !== 'chat'">出处标识<input v-model="form.source_ref" required maxlength="512" placeholder="docs/file.md#标题" /></label>
          <template v-else><label>对话 ID<input v-model="form.conversation_id" required /></label><label>消息 ID（逗号分隔）<input v-model="form.source_message_ids" required /></label></template>
          <label>证据原文<textarea v-model="form.source_excerpt" required maxlength="1000" /></label>
          <label>替代理由<textarea v-model="form.reason" required maxlength="500" /></label>
          <button class="primary" :disabled="busy">确认替代</button>
        </form>
        <button class="danger" :disabled="busy" @click="remove">永久删除这条记忆</button>
      </section>
    </div>
  </main>
</template>

<style scoped>
.versions { padding:28px; } header { display:flex; justify-content:space-between; } h1 { font-size:23px; } header p,.detail p { color:var(--text-secondary); margin-top:8px; }
header button { color:var(--primary); } .grid { display:grid; grid-template-columns:320px 1fr; gap:16px; margin-top:24px; }
.list,.detail { background:white; border:1px solid var(--border); border-radius:10px; padding:16px; }
.memory { display:block; text-align:left; width:100%; padding:12px; border-radius:8px; margin-bottom:8px; }.memory.chosen { background:var(--primary-bg); }
.memory small,.detail small { display:block; margin-top:7px; color:var(--text-tertiary); overflow-wrap:anywhere; }
h2 { font-size:17px; } h3 { font-size:15px; margin-top:22px; } blockquote { margin:12px 0; padding:8px 14px; border-left:3px solid var(--primary); background:#fafbfb; }
ol { padding-left:20px; } li { padding:8px 0; } form { display:grid; gap:12px; } label { display:grid; gap:5px; color:var(--text-secondary); font-size:13px; }
input,textarea,select { width:100%; border:1px solid var(--border-strong); border-radius:7px; padding:9px; background:white; }
textarea { min-height:70px; } .primary { padding:10px; border-radius:8px; background:var(--primary); color:white; }
.danger { color:#b91c1c; margin-top:22px; } .notice { margin-top:24px; padding:24px; background:white; } .error { color:#b91c1c; }
@media (max-width:850px) { .grid { grid-template-columns:1fr; } }
</style>
