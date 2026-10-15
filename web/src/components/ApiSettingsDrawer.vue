<script setup>
import { reactive, ref } from 'vue'
import { store } from '../store'

const tab = ref('extract')
const showKey = ref(false)

const form = reactive({
  provider: '自定义兼容接口',
  baseUrl: '',
  modelName: '',
  apiKey: ''
})

const testState = ref('idle') // idle | loading | success | fail
const testMsg = ref('尚未测试连接')

function runTest() {
  if (!form.baseUrl || !form.apiKey) {
    testState.value = 'fail'
    testMsg.value = '请先填写 Base URL 和 API Key'
    return
  }
  testState.value = 'loading'
  testMsg.value = '正在测试连接…'
  setTimeout(() => {
    testState.value = 'success'
    testMsg.value = '连接成功，接口可用'
  }, 1200)
}

function save() {
  Object.assign(store.apiSettings, { ...form, modelType: tab.value })
  store.showToast('设置已保存')
  store.apiDrawerOpen = false
}
</script>

<template>
  <div class="drawer-root">
    <div class="mask" @click="store.apiDrawerOpen = false"></div>

    <div class="drawer">
      <button class="close-btn" @click="store.apiDrawerOpen = false">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
      </button>

      <div class="drawer-head">
        <div class="title-row">
          <span class="gear-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
          </span>
          <h2>模型与 API 设置</h2>
        </div>
        <p class="subtitle">配置用于记忆提炼与向量检索的接口。</p>
      </div>

      <!-- Tab 卡片 -->
      <div class="tab-card">
        <div class="tabs">
          <button class="tab" :class="{ active: tab === 'extract' }" @click="tab = 'extract'">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
            </svg>
            记忆提炼模型
          </button>
          <button class="tab" :class="{ active: tab === 'vector' }" @click="tab = 'vector'">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>
            </svg>
            向量模型
          </button>
        </div>

        <div class="tab-hint">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
          向量模型也需要单独配置。
        </div>

        <div class="form-card">
          <div class="form-row">
            <label>服务商</label>
            <div class="select-wrap">
              <select v-model="form.provider">
                <option>自定义兼容接口</option>
                <option>OpenAI 兼容</option>
                <option>DeepSeek 官方</option>
                <option>智谱 GLM</option>
              </select>
              <span class="select-chev">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
              </span>
            </div>
          </div>

          <div class="form-row">
            <label>Base URL</label>
            <input v-model="form.baseUrl" type="text" placeholder="https://api.example.com/v1" />
          </div>

          <div class="form-row">
            <label>模型名称</label>
            <input v-model="form.modelName" type="text" placeholder="请输入模型名称" />
          </div>

          <div class="form-row">
            <label>API Key</label>
            <div class="key-input" :class="{ focused: showKey }">
              <input v-model="form.apiKey" :type="showKey ? 'text' : 'password'" placeholder="sk-…" />
              <button class="eye" @click="showKey = !showKey">
                <svg v-if="!showKey" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><path d="M1 1l22 22"/>
                </svg>
              </button>
            </div>
          </div>

          <div class="form-hint">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
            密钥将用于调用所选模型。
          </div>
        </div>
      </div>

      <!-- 连接测试 -->
      <div class="test-card">
        <div class="test-head">
          <span class="wifi-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12.55a11 11 0 0 1 14.08 0"/>
              <path d="M1.42 9a16 16 0 0 1 21.16 0"/>
              <path d="M8.53 16.11a6 6 0 0 1 6.95 0"/>
              <path d="M12 20h.01"/>
            </svg>
          </span>
          <span class="test-title">连接测试</span>
          <span class="test-state" :class="testState">
            <span class="state-dot"></span>{{ testMsg }}
          </span>
        </div>
        <p class="test-desc">请填写以上信息后，点击"测试连接"验证是否可用。</p>
      </div>

      <div class="drawer-foot">
        <button class="btn-ghost-teal" :disabled="testState === 'loading'" @click="runTest">
          <span v-if="testState === 'loading'" class="spinner"></span>
          测试连接
        </button>
        <button class="btn-primary" @click="save">保存设置</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.drawer-root { position: fixed; inset: 0; z-index: 1000; }
.mask {
  position: absolute; inset: 0;
  background: rgba(17, 24, 39, 0.4);
}
.drawer {
  position: absolute;
  top: 0; right: 0; bottom: 0;
  width: 420px;
  background: #fff;
  box-shadow: var(--shadow-lg);
  padding: 28px 24px 24px;
  overflow-y: auto;
  animation: slide-in 0.25s ease;
}
@keyframes slide-in {
  from { transform: translateX(40px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.close-btn {
  position: absolute;
  top: 20px; right: 20px;
  width: 30px; height: 30px;
  border-radius: 6px;
  color: var(--text-secondary);
  display: flex; align-items: center; justify-content: center;
}
.close-btn:hover { background: #f2f6f5; color: var(--text); }
.close-btn svg { width: 17px; height: 17px; }

.drawer-head .title-row { display: flex; align-items: center; gap: 9px; }
.gear-icon { width: 20px; height: 20px; color: var(--primary); display: inline-flex; }
.gear-icon svg { width: 100%; height: 100%; }
.drawer-head h2 { font-size: 17px; font-weight: 600; }
.subtitle { margin-top: 6px; font-size: 13px; color: var(--text-secondary); }

.tab-card {
  margin-top: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.tabs { display: flex; border-bottom: 1px solid var(--border); }
.tab {
  flex: 1;
  padding: 12px 10px;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  background: #fafbfb;
}
.tab svg { width: 15px; height: 15px; }
.tab.active {
  color: var(--primary);
  background: #fff;
  border-bottom-color: var(--primary);
}

.tab-hint {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 12px 16px;
  font-size: 12.5px;
  color: var(--text-secondary);
}
.tab-hint svg { width: 14px; height: 14px; flex-shrink: 0; }

.form-card {
  margin: 0 16px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.form-row { display: flex; align-items: center; gap: 12px; }
.form-row label {
  width: 64px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--text-secondary);
}
.form-row input[type="text"], .form-row input[type="password"] {
  flex: 1;
  min-width: 0;
  padding: 9px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.form-row input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.1);
}
input::placeholder { color: var(--text-tertiary); }

.select-wrap { position: relative; flex: 1; }
.select-wrap select {
  width: 100%;
  appearance: none;
  padding: 9px 32px 9px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}
.select-chev {
  position: absolute;
  right: 10px; top: 50%;
  transform: translateY(-50%);
  width: 14px; height: 14px;
  color: var(--text-tertiary);
  pointer-events: none;
}
.select-chev svg { width: 100%; height: 100%; }

.key-input {
  flex: 1;
  display: flex;
  align-items: center;
  border: 1.5px solid var(--primary);
  border-radius: 8px;
  padding-right: 4px;
}
.key-input input {
  flex: 1; min-width: 0;
  border: none !important;
  box-shadow: none !important;
  padding: 9px 12px;
}
.key-input .eye {
  width: 30px; height: 30px;
  border-radius: 6px;
  color: var(--text-secondary);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.key-input .eye:hover { background: #f2f6f5; }
.key-input .eye svg { width: 16px; height: 16px; }

.form-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.form-hint svg { width: 13px; height: 13px; flex-shrink: 0; }

.test-card {
  margin-top: 16px;
  background: #fafbfb;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
}
.test-head { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.wifi-icon { width: 17px; height: 17px; color: var(--primary); display: inline-flex; }
.wifi-icon svg { width: 100%; height: 100%; }
.test-title { font-size: 13.5px; font-weight: 600; }
.test-state {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.state-dot { width: 7px; height: 7px; border-radius: 50%; background: #cbd5d4; }
.test-state.success { color: #16a34a; }
.test-state.success .state-dot { background: #22c55e; }
.test-state.fail { color: var(--danger); }
.test-state.fail .state-dot { background: var(--danger); }
.test-desc { margin-top: 10px; font-size: 12.5px; color: var(--text-tertiary); line-height: 1.6; }

.drawer-foot {
  margin-top: 24px;
  display: flex;
  gap: 12px;
}
.drawer-foot .btn-ghost-teal { flex: 1; justify-content: center; padding: 10px; }
.drawer-foot .btn-primary { flex: 1; justify-content: center; padding: 10px; }

.spinner {
  width: 13px; height: 13px;
  border: 2px solid rgba(15, 118, 110, 0.25);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>