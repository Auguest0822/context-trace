<script setup>
import { onMounted, ref } from 'vue'
import { loadTrace, loadTraces } from '../data/memoryApi'

const isApi = import.meta.env.VITE_ARCHIVE_DATA_SOURCE === 'api'
const traces = ref([])
const active = ref(null)
const loading = ref(false)
const error = ref('')
const labels = {
  KEYWORD_MATCH: '关键词命中', VECTOR_MATCH: '向量命中', BUDGET_SUMMARY: '预算内采用摘要',
  BUDGET_EXCEEDED: '预算不足', TOP_K_EXCEEDED: '超出候选数量'
}

async function refresh() {
  if (!isApi) return
  loading.value = true
  error.value = ''
  try {
    const page = await loadTraces()
    traces.value = page.items || []
    if (traces.value.length) await selectTrace(traces.value[0].trace_id)
  } catch (reason) { error.value = `读取召回记录失败：${reason.message}` }
  finally { loading.value = false }
}

async function selectTrace(id) {
  try { active.value = await loadTrace(id) }
  catch (reason) { error.value = `读取轨迹详情失败：${reason.message}` }
}

onMounted(refresh)
</script>

<template>
  <main class="recall-page">
    <header><div><h1>召回记录</h1><p>展示数据库保存的检索轨迹和预算取舍。</p></div><button @click="refresh">刷新</button></header>
    <p v-if="!isApi" class="notice">当前是演示模式。切换为 API 模式后可查看真实检索轨迹。</p>
    <p v-if="loading">正在读取…</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-if="isApi" class="grid">
      <aside class="list">
        <button v-for="trace in traces" :key="trace.trace_id" class="trace-card" :class="{ selected: active?.trace_id === trace.trace_id }" @click="selectTrace(trace.trace_id)">
          <strong>{{ trace.query }}</strong>
          <span>{{ trace.mode_used }} · {{ trace.selected_count }}/{{ trace.candidate_count }} 条 · {{ trace.created_at }}</span>
        </button>
        <p v-if="!loading && !traces.length">还没有检索轨迹。先到记忆检索页执行一次查询。</p>
      </aside>
      <section v-if="active" class="detail">
        <h2>{{ active.query }}</h2>
        <p>方式：{{ active.mode_used }} · 耗时：{{ active.elapsed_ms }} ms · 预算：约 {{ active.budget.used_tokens }}/{{ active.budget.limit_tokens }} tokens</p>
        <p>轨迹 ID：{{ active.trace_id }}</p>
        <ol>
          <li v-for="candidate in active.candidates" :key="candidate.memory_id">
            <strong>记忆 #{{ candidate.memory_id }}</strong>
            <span>{{ candidate.decision === 'selected' ? '已纳入' : '未纳入' }}</span>
            <small>关键词排名 {{ candidate.keyword_rank ?? '—' }} · 向量排名 {{ candidate.vector_rank ?? '—' }} · 融合得分 {{ candidate.fusion_score }}</small>
            <small>{{ candidate.reason_codes.map(code => labels[code] || code).join('、') }}</small>
          </li>
        </ol>
      </section>
    </div>
  </main>
</template>

<style scoped>
.recall-page { padding: 28px; } header { display:flex; justify-content:space-between; } h1 { font-size:23px; }
header p, .detail p { color:var(--text-secondary); margin-top:8px; } header button { color:var(--primary); font-weight:600; }
.grid { display:grid; grid-template-columns:300px 1fr; gap:16px; margin-top:24px; }
.list,.detail { background:white; border:1px solid var(--border); border-radius:10px; padding:16px; }
.trace-card { display:flex; flex-direction:column; text-align:left; width:100%; padding:12px; border-radius:8px; margin-bottom:8px; }
.trace-card.selected { background:var(--primary-bg); } .trace-card span, .detail small { display:block; color:var(--text-tertiary); font-size:12px; margin-top:8px; }
.detail h2 { font-size:17px; } .detail ol { margin-top:18px; padding-left:20px; } .detail li { padding:12px; border-top:1px solid var(--border); }
.detail li span { margin-left:12px; color:var(--primary); } .notice { margin-top:24px; padding:24px; background:white; }
.error { color:#b91c1c; }
@media (max-width:800px) { .grid { grid-template-columns:1fr; } }
</style>
