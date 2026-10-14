<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { store } from '../store'
import { CANDIDATES, DEFAULT_SELECTED, MESSAGES } from '../data/mock'
import SourceBadge from '../components/SourceBadge.vue'
import CategoryTag from '../components/CategoryTag.vue'

const router = useRouter()

// 左侧展示从对话页传来的选中消息（兜底用默认）
const fallbackMessages = MESSAGES.filter(m => DEFAULT_SELECTED.includes(m.id))
const selectedMessages = store.selectedMessages.length ? store.selectedMessages : fallbackMessages

const selectedIds = ref(new Set(['c1']))

const selectedCount = computed(() => selectedIds.value.size)

function toggleCandidate(id) {
  const s = new Set(selectedIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedIds.value = s
}

function goBack() {
  router.push('/archive')
}

function confirmSave() {
  if (!selectedCount.value) return
  const chosen = CANDIDATES.filter(c => selectedIds.value.has(c.id))
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
          <span class="current">初赛部署讨论</span>
        </div>
        <p class="sub">基于选中的对话内容，生成候选记忆。请确认并选择需要保存的记忆。</p>
      </div>
      <div class="head-hint">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
        <div>
          <p>预览不会自动保存记忆，</p>
          <p>请检查内容并选择后确认保存。</p>
        </div>
      </div>
    </div>

    <div class="main-grid">
      <!-- 左：已选对话内容 -->
      <section class="panel">
        <header class="panel-head">
          <h3>已选对话内容（{{ selectedMessages.length }} 条）</h3>
          <p>作为生成候选记忆的依据</p>
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
          <h3>候选记忆（{{ CANDIDATES.length }} 条）</h3>
          <p>基于选中内容生成的候选记忆，可编辑后保存到记忆库</p>
        </header>
        <div class="panel-body">
          <div v-for="c in CANDIDATES" :key="c.id" class="candidate" :class="{ checked: selectedIds.has(c.id) }">
            <div class="cand-head">
              <span
                class="checkbox"
                :class="{ checked: selectedIds.has(c.id) }"
                @click="toggleCandidate(c.id)"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
              </span>
              <CategoryTag :category="c.category" />
              <span class="based-on">基于 {{ c.basedOn.map(n => '#' + n).join('、') }}</span>
            </div>

            <div class="field-label">记忆内容</div>
            <div class="content-box">
              <textarea v-model="c.content" rows="2"></textarea>
              <span class="char-count">{{ c.content.length }}/200</span>
            </div>

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
        <p class="foot-tip">将保存到记忆库，可在记忆库中查看和编辑。</p>
      </div>
      <div class="foot-actions">
        <button class="btn-outline" @click="goBack">返回对话</button>
        <button class="btn-primary" :disabled="!selectedCount" @click="confirmSave">确认保存 {{ selectedCount }} 条</button>
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
</style>