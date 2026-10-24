<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { store } from '../store'
import { CANDIDATES, DEFAULT_SELECTED, MESSAGES } from '../data/mock'
import SourceBadge from '../components/SourceBadge.vue'
import CategoryTag from '../components/CategoryTag.vue'
import { previewManual, commitManual, readMemory } from '../data/extractionApi'

const router = useRouter()
const isApiArchive = import.meta.env.VITE_ARCHIVE_DATA_SOURCE === 'api'
const kindLabels = { decision: '决策', constraint: '约束', fact: '事实', preference: '偏好', skill: '技能' }

const fallbackMessages = MESSAGES.filter(m => DEFAULT_SELECTED.includes(m.id))
const selectedMessages = computed(() => isApiArchive
  ? store.selectedMessages
  : (store.selectedMessages.length ? store.selectedMessages : fallbackMessages))
const candidates = ref(isApiArchive ? [] : CANDIDATES)
const previewId = ref(null)
const previewLoading = ref(false)
const saving = ref(false)
const errorText = ref('')
const readbackWarning = ref('')
const savedMemories = ref([])
const pendingPayload = ref(null)

const selectedIds = ref(new Set(isApiArchive ? [] : ['c1']))

const selectedCount = computed(() => selectedIds.value.size)

function toggleCandidate(id) {
  if (pendingPayload.value || savedMemories.value.length) return
  const s = new Set(selectedIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedIds.value = s
}

function goBack() {
  router.push('/archive')
}

function openSource(memory) {
  router.push({ path: '/archive', query: {
    conversation: memory.conversation_id,
    message: memory.source_message_ids[0]
  } })
}

async function loadPreview() {
  if (!store.selectedConversationId || !selectedMessages.value.length) {
    errorText.value = '请返回对话档案，先选择 1–20 条消息。'
    return
  }
  previewLoading.value = true
  errorText.value = ''
  try {
    const result = await previewManual(
      store.selectedConversationId, selectedMessages.value.map(message => String(message.id))
    )
    previewId.value = result.preview_id
    candidates.value = result.candidates.map(item => ({
      id: item.candidate_id,
      kind: item.kind,
      content: item.content,
      summary: item.summary || '',
      basedOn: item.source_message_ids.map(id =>
        selectedMessages.value.find(message => String(message.id) === id)?.seq ?? id),
      citations: item.source_message_ids.map(id => {
        const message = selectedMessages.value.find(entry => String(entry.id) === id)
        return { id, seq: message?.seq ?? id, role: message?.role || '消息', text: item.source_excerpt }
      })
    }))
  } catch (error) {
    errorText.value = error.message
  } finally {
    previewLoading.value = false
  }
}

onMounted(() => { if (isApiArchive) loadPreview() })

async function confirmSave() {
  if (!selectedCount.value) return
  if (isApiArchive) {
    if (!previewId.value || saving.value || savedMemories.value.length) return
    if (!pendingPayload.value) {
      const chosen = candidates.value.filter(candidate => selectedIds.value.has(candidate.id))
      if (chosen.some(candidate => !candidate.content.trim() || candidate.content.length > 8000 || candidate.summary.length > 512)) {
        errorText.value = '请检查记忆内容（1–8000 字）和摘要（最多 512 字）。'
        return
      }
      pendingPayload.value = {
        client_request_id: crypto.randomUUID(),
        selected: chosen.map(candidate => ({
          candidate_id: candidate.id, kind: candidate.kind,
          content: candidate.content.trim(), summary: candidate.summary.trim() || null
        }))
      }
    }
    saving.value = true
    errorText.value = ''
    try {
      const result = await commitManual(previewId.value, pendingPayload.value)
      savedMemories.value = result.memories
      store.showToast(`已写入 seekdb：${result.memories.length} 条记忆`)
      try {
        const checked = await Promise.all(result.memories.map(memory => readMemory(memory.id)))
        if (checked.some((item, index) => {
          const expected = result.memories[index]
          const actual = item.memory
          return actual?.id !== expected.id || actual?.source_excerpt !== expected.source_excerpt ||
            JSON.stringify(actual?.source_message_ids) !== JSON.stringify(expected.source_message_ids)
        })) {
          readbackWarning.value = '写入已完成，但读取核对的出处与保存结果不同。'
        }
      } catch (error) {
        readbackWarning.value = `写入已完成，读取核对暂时失败：${error.message}`
      }
    } catch (error) {
      errorText.value = `${error.message}。请保留本页重试；相同请求不会重复写入。`
    } finally {
      saving.value = false
    }
    return
  }
  const chosen = candidates.value.filter(c => selectedIds.value.has(c.id))
  chosen.forEach(c => {
    store.savedMemories.push({
      id: c.id + '-' + Date.now(),
      category: c.category,
      title: c.content.slice(0, 14) + '…',
      content: c.content,
      source: 'DeepSeek',
      conversation: '初赛部署讨论',
      conversationId: 2,
      time: '刚刚',
      quote: c.citations[0]?.text || ''
    })
  })
  store.showToast(`已确认保存 ${selectedCount.value} 条记忆到记忆库`)
  selectedIds.value = new Set()
}
</script>

<template>
  <div class="extract-page">
    <div class="page-head">
      <div class="head-left">
        <h1>提炼记忆 · 预览确认</h1>
        <div class="breadcrumb">
          <router-link to="/archive">对话档案</router-link>
          <span class="sep">/</span>
          <span class="current">{{ isApiArchive ? store.selectedConversationTitle : '初赛部署讨论' }}</span>
        </div>
        <p class="sub">{{ isApiArchive ? '从选中消息建立逐字引用的人工草稿；请编辑、选择，再确认写入。这里没有 AI 自动提炼或向量生成。' : '基于选中的对话内容，生成候选记忆。请确认并选择需要保存的记忆。' }}</p>
      </div>
      <div class="head-hint">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
        <div>
          <p>预览不会自动保存记忆，</p>
          <p>请检查内容并选择后确认保存。</p>
        </div>
      </div>
    </div>

    <p v-if="previewLoading" class="status-message">正在读取归档消息并创建预览…</p>
    <p v-if="errorText" class="status-message error">{{ errorText }}</p>
    <p v-if="savedMemories.length" class="status-message success">已确认写入 seekdb：{{ savedMemories.map(memory => '#' + memory.id).join('、') }}。出处见下方；尚无向量 embedding。</p>
    <p v-if="readbackWarning" class="status-message error">{{ readbackWarning }}</p>
    <div v-if="savedMemories.length" class="saved-list">
      <div v-for="memory in savedMemories" :key="memory.id" class="saved-item">
        <strong>记忆 #{{ memory.id }} · {{ kindLabels[memory.kind] }}</strong>
        <p>{{ memory.content }}</p>
        <small>原始消息 {{ memory.source_message_ids.map(id => '#' + id).join('、') }} · 原文：“{{ memory.source_excerpt }}”</small>
        <button class="source-link" @click="openSource(memory)">查看原消息</button>
      </div>
    </div>

    <div class="main-grid">
      <!-- 左：已选对话内容 -->
      <section class="panel">
        <header class="panel-head">
          <h3>已选对话内容（{{ selectedMessages.length }} 条）</h3>
          <p>{{ isApiArchive ? '归档原文，仅用于人工拟定；未选消息不会成为出处' : '作为生成候选记忆的依据' }}</p>
        </header>
        <div class="panel-body">
          <div v-for="m in selectedMessages" :key="m.id" class="picked-msg">
            <div class="picked-head">
              <span class="checkbox checked">
                <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
              </span>
              <SourceBadge v-if="m.role !== '我'" :source="m.source" :size="22" />
              <span v-else class="avatar-me">R</span>
              <span class="role">{{ m.role }}</span>
              <span class="time">今天 {{ m.time }}</span>
              <span class="seq"># {{ m.seq }}</span>
            </div>
            <div class="picked-body">{{ m.text }}</div>
          </div>
        </div>
      </section>

      <!-- 右：候选记忆 -->
      <section class="panel">
        <header class="panel-head">
          <h3>候选记忆（{{ candidates.length }} 条）</h3>
          <p>{{ isApiArchive ? '每条草稿复制一条消息的原文片段；勾选并改写为值得保存的结论' : '基于选中内容生成的候选记忆，可编辑后保存到记忆库' }}</p>
        </header>
        <div class="panel-body">
          <div v-for="c in candidates" :key="c.id" class="candidate" :class="{ checked: selectedIds.has(c.id) }">
            <div class="cand-head">
              <span
                class="checkbox"
                :class="{ checked: selectedIds.has(c.id) }"
                @click="toggleCandidate(c.id)"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
              </span>
              <select v-if="isApiArchive" v-model="c.kind" :disabled="!!pendingPayload || !!savedMemories.length" aria-label="记忆类型" class="kind-select">
                <option v-for="(label, key) in kindLabels" :key="key" :value="key">{{ label }}</option>
              </select>
              <CategoryTag v-else :category="c.category" />
              <span class="based-on">基于 {{ c.basedOn.map(n => '#' + n).join('、') }}</span>
            </div>

            <div class="field-label">记忆内容</div>
            <div class="content-box">
              <textarea v-model="c.content" rows="2" :maxlength="isApiArchive ? 8000 : 200" :disabled="isApiArchive && (!!pendingPayload || !!savedMemories.length)"></textarea>
              <span class="char-count">{{ c.content.length }}/{{ isApiArchive ? 8000 : 200 }}</span>
            </div>
            <template v-if="isApiArchive">
              <div class="field-label">简短摘要（可选）</div>
              <input v-model="c.summary" class="summary-input" maxlength="512" :disabled="!!pendingPayload || !!savedMemories.length" placeholder="一句话概括这条记忆" />
            </template>

            <div class="field-label">证据引用</div>
            <div class="citations">
              <div v-for="ct in c.citations" :key="ct.seq" class="citation-row">
                <span class="cite-seq"># {{ ct.seq }}</span>
                <span class="cite-role">{{ ct.role }}</span>
                <span class="cite-text">"{{ ct.text }}"</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 底部操作条 -->
    <div class="foot-bar">
      <div class="foot-info">
        <p class="foot-count">已选 {{ selectedCount }} 条候选</p>
        <p class="foot-tip">{{ isApiArchive ? '确认后写入 seekdb，并保留原始消息出处；当前不生成向量。' : '将保存到记忆库，可在记忆库中查看和编辑。' }}</p>
      </div>
      <div class="foot-actions">
        <button class="btn-outline" @click="goBack">返回对话</button>
        <button class="btn-primary" :disabled="!selectedCount || previewLoading || saving || !!savedMemories.length || (isApiArchive && !previewId)" @click="confirmSave">{{ saving ? '正在保存…' : savedMemories.length ? '已保存' : `确认保存 ${selectedCount} 条` }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}
.page-head h1 { font-size: 22px; font-weight: 700; }
.breadcrumb {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.breadcrumb a { color: var(--primary); text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }
.breadcrumb .sep { color: var(--text-tertiary); }
.breadcrumb .current { color: var(--text-secondary); }
.page-head .sub { margin-top: 10px; font-size: 13.5px; color: var(--text-secondary); }

.head-hint {
  display: flex;
  gap: 8px;
  font-size: 12.5px;
  color: var(--text-tertiary);
  line-height: 1.7;
  flex-shrink: 0;
  padding-top: 6px;
}
.head-hint svg { width: 15px; height: 15px; flex-shrink: 0; margin-top: 2px; }

.main-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: 1fr 1.15fr;
  gap: 16px;
  align-items: start;
}

.panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.panel-head {
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
}
.panel-head h3 { font-size: 15px; font-weight: 700; }
.panel-head p { margin-top: 5px; font-size: 12.5px; color: var(--text-tertiary); }
.panel-body {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 已选消息卡片 */
.picked-msg {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
}
.picked-head { display: flex; align-items: center; gap: 8px; }
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
.role { font-size: 13px; font-weight: 600; }
.time { font-size: 12px; color: var(--text-tertiary); }
.seq { margin-left: auto; font-size: 12px; color: var(--text-tertiary); }
.picked-body {
  margin-top: 10px;
  background: #f3f4f4;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 13.5px;
  line-height: 1.7;
  white-space: pre-line;
}

/* 候选记忆卡片 */
.candidate {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  transition: border-color 0.15s;
}
.candidate.checked { border-color: rgba(15, 118, 110, 0.45); }
.cand-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.based-on { margin-left: auto; font-size: 12px; color: var(--text-tertiary); }

.field-label {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.content-box { position: relative; margin-top: 6px; }
.content-box textarea {
  width: 100%;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  padding: 10px 12px 22px;
  resize: none;
  font-size: 13px;
  line-height: 1.6;
  background: #fff;
}
.content-box textarea:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.1);
}
.char-count {
  position: absolute;
  right: 10px;
  bottom: 8px;
  font-size: 11px;
  color: var(--text-tertiary);
}

.citations {
  margin-top: 6px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.citation-row {
  display: flex;
  gap: 8px;
  padding: 9px 12px;
  background: #fafbfb;
  font-size: 12.5px;
  line-height: 1.6;
}
.citation-row + .citation-row { border-top: 1px solid var(--border); }
.cite-seq { color: var(--text-tertiary); flex-shrink: 0; }
.cite-role { font-weight: 600; flex-shrink: 0; color: var(--text-secondary); }
.cite-text { color: var(--text-secondary); }

/* 底部操作条 */
.foot-bar {
  margin-top: 20px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.foot-count { font-size: 13.5px; font-weight: 600; }
.foot-tip { margin-top: 3px; font-size: 12px; color: var(--text-tertiary); }
.foot-actions { display: flex; gap: 12px; }
.status-message { margin-top: 14px; padding: 10px 14px; border-radius: 8px; background: #edf4f3; color: #175b57; font-size: 13px; }
.status-message.error { background: #fff0ef; color: #a33a31; }
.status-message.success { background: #eaf7ed; color: #176735; }
.kind-select, .summary-input { border: 1px solid var(--border-strong); border-radius: 8px; padding: 6px 9px; background: #fff; font-size: 13px; }
.summary-input { display: block; width: 100%; margin-top: 6px; padding: 9px 12px; }
.saved-list { display: grid; gap: 8px; margin-top: 12px; }
.saved-item { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; font-size: 13px; }
.saved-item p { margin: 6px 0; white-space: pre-wrap; }
.saved-item small { color: var(--text-secondary); white-space: pre-wrap; }
.source-link { display: block; margin-top: 8px; padding: 0; border: 0; background: none; color: var(--primary); cursor: pointer; font-size: 12px; font-weight: 600; }
</style>
