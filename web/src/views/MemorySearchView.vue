<script setup>
import { ref, computed } from 'vue'
import { store } from '../store'
import { SEARCH_RESULTS, MATCH_EXPLAIN } from '../data/mock'
import SourceBadge from '../components/SourceBadge.vue'
import CategoryTag from '../components/CategoryTag.vue'

const question = ref('初赛为什么优先保证本地复现？')
const sourcePlatform = ref('DeepSeek')
const conversation = ref('初赛部署讨论')
const category = ref('决策')
const searchMode = ref('混合')
const tokenBudget = ref(1200)
const sortBy = ref('相关性优先')
const searched = ref(true)

const selectedIds = ref(new Set(['m1']))

const results = computed(() => {
  if (!searched.value) return []
  return SEARCH_RESULTS
})

const selectedResults = computed(() => results.value.filter(r => selectedIds.value.has(r.id)))

const totalTokens = computed(() => selectedResults.value.reduce((s, r) => s + r.tokens, 0))

function toggleResult(id) {
  const s = new Set(selectedIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedIds.value = s
}

function doSearch() {
  searched.value = false
  setTimeout(() => { searched.value = true }, 400)
}

function copyContext() {
  const text = selectedResults.value
    .map(r => `[${r.category}] ${r.title}\n${r.content || r.desc}\n来源：${r.conversation} · ${r.time}`)
    .join('\n\n')
  navigator.clipboard?.writeText(text).catch(() => {})
  store.showToast('上下文已复制到剪贴板')
}
</script>

<template>
  <div class="search-page">
    <div class="page-head">
      <h1>记忆检索</h1>
      <p class="sub">按问题和来源范围找回已确认的记忆。</p>
    </div>

    <!-- 搜索区 -->
    <div class="search-row">
      <div class="big-search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input
          v-model="question"
          type="text"
          placeholder="输入要查找的问题…"
          @keydown.enter="doSearch"
        />
      </div>
      <button class="btn-primary search-btn" @click="doSearch">查找记忆</button>
    </div>

    <!-- 筛选行 -->
    <div class="filter-line">
      <div class="filter-item">
        <label>来源平台：</label>
        <div class="select-wrap with-badge">
          <SourceBadge :source="sourcePlatform" :size="17" />
          <select v-model="sourcePlatform">
            <option>DeepSeek</option>
            <option>Kimi</option>
            <option>豆包</option>
            <option>Agent</option>
          </select>
          <span class="select-chev"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg></span>
        </div>
      </div>

      <div class="filter-item">
        <label>对话：</label>
        <div class="select-wrap">
          <select v-model="conversation">
            <option>初赛部署讨论</option>
            <option>需求评审会议</option>
            <option>产品文案优化</option>
          </select>
          <span class="select-chev"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg></span>
        </div>
      </div>

      <div class="filter-item">
        <label>类别：</label>
        <div class="select-wrap with-badge">
          <CategoryTag :category="category" />
          <select v-model="category">
            <option>决策</option>
            <option>行动</option>
            <option>约束</option>
            <option>事实</option>
          </select>
          <span class="select-chev"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg></span>
        </div>
      </div>

      <div class="filter-item">
        <label>检索方式：</label>
        <div class="mode-tabs">
          <button
            v-for="m in ['混合', '关键词', '向量']"
            :key="m"
            class="mode-tab"
            :class="{ active: searchMode === m }"
            @click="searchMode = m"
          >{{ m }}</button>
        </div>
      </div>

      <div class="filter-item token-item">
        <label>Token 预算：</label>
        <input v-model.number="tokenBudget" type="number" class="token-input" />
      </div>
    </div>

    <!-- 主体两栏 -->
    <div class="main-grid">
      <!-- 左：检索结果 -->
      <section class="panel">
        <header class="panel-head">
          <div class="head-left">
            <h3>检索到的记忆</h3>
            <span class="count-chip">{{ results.length }} 条结果</span>
          </div>
          <button class="sort-btn">
            {{ sortBy }}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
          </button>
        </header>

        <div class="panel-body">
          <div v-for="r in results" :key="r.id" class="result-item" :class="{ checked: selectedIds.has(r.id) }">
            <span
              class="checkbox"
              :class="{ checked: selectedIds.has(r.id) }"
              @click="toggleResult(r.id)"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            </span>
            <div class="result-main">
              <div class="result-top">
                <CategoryTag :category="r.category" />
                <h4>{{ r.title }}</h4>
              </div>
              <p class="result-desc">{{ r.desc }}</p>
              <div class="result-meta">
                <span class="meta-chip">
                  <SourceBadge :source="r.source" :size="16" />
                  {{ r.source }}
                </span>
                <span class="meta-chip">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
                  {{ r.conversationLabel }}
                </span>
                <span class="meta-chip">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                  {{ r.time }}
                </span>
              </div>
              <blockquote class="result-quote">{{ r.quote }}</blockquote>
            </div>
          </div>

          <div v-if="!results.length" class="empty">点击"查找记忆"开始检索。</div>
        </div>
      </section>

      <!-- 右：最终上下文 -->
      <section class="panel context-panel">
        <header class="panel-head">
          <div class="head-left">
            <span class="ctx-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="4" width="20" height="16" rx="2"/><path d="M2 9h20M7 4v5M12 4v5M17 4v5"/>
              </svg>
            </span>
            <h3>最终使用的上下文</h3>
            <span class="count-chip plain">已选择 {{ selectedResults.length }} 条记忆</span>
          </div>
        </header>

        <div class="panel-body">
          <div v-for="r in selectedResults" :key="r.id" class="ctx-card">
            <div class="ctx-top">
              <CategoryTag :category="r.category" />
              <span class="ctx-title">{{ r.title }}</span>
              <span class="ctx-source">
                <SourceBadge :source="r.source" :size="16" />
                {{ r.source }} · 对话 #{{ r.conversationId }}
              </span>
            </div>
            <p class="ctx-content">{{ r.quote }}</p>
            <p class="ctx-origin">来源：{{ r.conversation }} · {{ r.time }}</p>
          </div>

          <div v-if="!selectedResults.length" class="empty">从左侧结果中勾选要使用的记忆。</div>

          <div class="token-row">
            <span class="token-label">
              预计 Token 用量
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
            </span>
            <span class="token-value">约 {{ totalTokens }} tokens</span>
          </div>

          <button class="copy-btn" :disabled="!selectedResults.length" @click="copyContext">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            复制上下文
          </button>
        </div>
      </section>
    </div>

    <!-- 命中解释 -->
    <div class="explain-panel">
      <div class="explain-head">
        <span class="bulb">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.4 1 2.3h6c0-.9.4-1.8 1-2.3A7 7 0 0 0 12 2z"/></svg>
        </span>
        <h3>为什么找到这些记忆</h3>
      </div>
      <div class="explain-list">
        <div v-for="e in MATCH_EXPLAIN" :key="e.seq" class="explain-row">
          <span class="e-seq">{{ e.seq }}</span>
          <span class="e-ways">
            <span v-for="w in e.ways" :key="w" class="way-tag" :class="{ kw: w === '关键词匹配', vec: w === '向量相似' }">{{ w }}</span>
          </span>
          <span class="e-text">{{ e.text }}</span>
          <span class="e-target">对应结果 {{ e.target }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-head h1 { font-size: 22px; font-weight: 700; }
.page-head .sub { margin-top: 6px; font-size: 13.5px; color: var(--text-secondary); }

/* 搜索区 */
.search-row {
  margin-top: 18px;
  display: flex;
  gap: 12px;
}
.big-search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  padding: 13px 16px;
}
.big-search svg { width: 17px; height: 17px; color: var(--text-tertiary); flex-shrink: 0; }
.big-search input { flex: 1; border: none; background: transparent; font-size: 14px; }
.big-search:focus-within { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.08); }
.search-btn { padding: 0 26px; border-radius: 10px; font-size: 14px; }

/* 筛选行 */
.filter-line {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
}
.filter-item { display: flex; align-items: center; gap: 8px; }
.filter-item > label { font-size: 13px; color: var(--text-secondary); flex-shrink: 0; }

.select-wrap { position: relative; display: flex; align-items: center; }
.select-wrap select {
  appearance: none;
  border: 1px solid var(--border-strong);
  background: #fff;
  border-radius: 8px;
  padding: 8px 30px 8px 12px;
  font-size: 13px;
  cursor: pointer;
  min-width: 120px;
}
.select-wrap.with-badge select { padding-left: 38px; }
.select-wrap.with-badge > .source-badge,
.select-wrap.with-badge > .category-tag {
  position: absolute;
  left: 12px;
  pointer-events: none;
  z-index: 1;
}
.select-chev {
  position: absolute;
  right: 10px;
  width: 13px; height: 13px;
  color: var(--text-tertiary);
  pointer-events: none;
}
.select-chev svg { width: 100%; height: 100%; }

.mode-tabs {
  display: inline-flex;
  background: #edf1f0;
  border-radius: 8px;
  padding: 3px;
}
.mode-tab {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}
.mode-tab.active {
  background: var(--primary);
  color: #fff;
  font-weight: 500;
}

.token-input {
  width: 76px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  text-align: right;
}
.token-input:focus { border-color: var(--primary); }

/* 主体 */
.main-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 16px;
  align-items: start;
}

.panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.panel-head {
  padding: 15px 18px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.head-left { display: flex; align-items: center; gap: 10px; }
.panel-head h3 { font-size: 15px; font-weight: 700; }
.count-chip {
  font-size: 12px;
  color: var(--primary);
  background: var(--primary-bg);
  padding: 2px 9px;
  border-radius: 999px;
}
.count-chip.plain { color: var(--text-secondary); background: #f0f2f2; }
.sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12.5px;
  color: var(--text-secondary);
}
.sort-btn svg { width: 13px; height: 13px; }

.panel-body { padding: 14px 18px 18px; display: flex; flex-direction: column; gap: 12px; }

/* 检索结果项 */
.result-item {
  display: flex;
  gap: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  transition: border-color 0.15s;
}
.result-item.checked { border-color: rgba(15, 118, 110, 0.45); }
.result-main { flex: 1; min-width: 0; }
.result-top { display: flex; align-items: center; gap: 10px; }
.result-top h4 { font-size: 14px; font-weight: 600; }
.result-desc {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.65;
}
.result-meta {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.meta-chip svg { width: 13px; height: 13px; }
.result-quote {
  margin-top: 12px;
  border-left: 3px solid var(--primary-light);
  background: #fafbfb;
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.65;
}

/* 右侧上下文面板 */
.ctx-icon { width: 18px; height: 18px; color: var(--primary); display: inline-flex; }
.ctx-icon svg { width: 100%; height: 100%; }
.ctx-card {
  background: var(--primary-bg-soft);
  border: 1px solid rgba(15, 118, 110, 0.2);
  border-radius: 10px;
  padding: 13px 14px;
}
.ctx-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ctx-title { font-size: 13.5px; font-weight: 600; }
.ctx-source {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--text-tertiary);
}
.ctx-content {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.7;
}
.ctx-origin { margin-top: 10px; font-size: 11.5px; color: var(--text-tertiary); }

.token-row {
  margin-top: 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 2px;
}
.token-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}
.token-label svg { width: 13px; height: 13px; color: var(--text-tertiary); }
.token-value { font-size: 13px; font-weight: 600; }

.copy-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px;
  border-radius: 10px;
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.15s;
}
.copy-btn:hover:not(:disabled) { background: var(--primary-hover); }
.copy-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.copy-btn svg { width: 16px; height: 16px; }

/* 命中解释 */
.explain-panel {
  margin-top: 16px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.explain-head {
  padding: 15px 18px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 9px;
}
.bulb { width: 17px; height: 17px; color: var(--orange); display: inline-flex; }
.bulb svg { width: 100%; height: 100%; }
.explain-head h3 { font-size: 15px; font-weight: 700; }

.explain-list { padding: 8px 18px 12px; }
.explain-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 11px 0;
}
.explain-row + .explain-row { border-top: 1px dashed var(--border); }
.e-seq {
  width: 22px; height: 22px;
  border-radius: 50%;
  background: #f0f2f2;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.e-ways { display: flex; gap: 6px; flex-shrink: 0; }
.way-tag {
  font-size: 11.5px;
  padding: 3px 9px;
  border-radius: 6px;
  font-weight: 500;
  white-space: nowrap;
}
.way-tag.kw { background: var(--primary-bg); color: var(--primary); }
.way-tag.vec { background: var(--blue-bg); color: #1d4ed8; }
.e-text { font-size: 13px; color: var(--text-secondary); }
.e-target { margin-left: auto; font-size: 12.5px; color: var(--primary); font-weight: 500; flex-shrink: 0; }

.empty {
  padding: 32px 0;
  text-align: center;
  font-size: 13px;
  color: var(--text-tertiary);
}
</style>