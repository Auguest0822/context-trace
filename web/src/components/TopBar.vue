<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { store } from '../store'

const route = useRoute()

const projectLabel = ref(route.meta.nav === 'archive' ? '项目：ContextTrace' : '工作空间：产品研发')
const projectOpen = ref(false)
const projects = ['项目：ContextTrace', '工作空间：产品研发']

function pickProject(p) {
  projectLabel.value = p
  projectOpen.value = false
}
</script>

<template>
  <header class="topbar">
    <div class="left">
      <div class="project-select" @click="projectOpen = !projectOpen">
        <span class="doc-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <path d="M14 2v6h6"/>
            <path d="M9 13h6M9 17h6"/>
          </svg>
        </span>
        <span class="project-label">{{ projectLabel }}</span>
        <span class="chev" :class="{ up: projectOpen }">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
        </span>
        <transition name="fade">
          <div v-if="projectOpen" class="project-menu">
            <div
              v-for="p in projects"
              :key="p"
              class="project-option"
              :class="{ current: p === projectLabel }"
              @click.stop="pickProject(p)"
            >{{ p }}</div>
          </div>
        </transition>
      </div>

      <div class="conn-status">
        <span class="dot"></span>
        <span>已连接 · 本地记忆库</span>
      </div>
    </div>

    <div class="right">
      <button class="api-btn" @click="store.apiDrawerOpen = true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
        模型与 API 设置
      </button>
      <div class="avatar">R</div>
      <span class="chev">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
      </span>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: 56px;
  flex-shrink: 0;
  background: #fff;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}
.left { display: flex; align-items: center; gap: 24px; }

.project-select {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  user-select: none;
}
.project-select:hover { background: #f2f6f5; }
.doc-icon { width: 16px; height: 16px; color: var(--text-secondary); display: inline-flex; }
.doc-icon svg { width: 100%; height: 100%; }
.project-label { font-size: 13.5px; font-weight: 500; }
.chev {
  width: 14px; height: 14px; color: var(--text-tertiary);
  display: inline-flex; transition: transform 0.15s;
}
.chev.up { transform: rotate(180deg); }
.chev svg { width: 100%; height: 100%; }

.project-menu {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 190px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-lg);
  padding: 4px;
  z-index: 100;
}
.project-option {
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.project-option:hover { background: #f2f6f5; }
.project-option.current { color: var(--primary); font-weight: 600; background: var(--primary-bg-soft); }

.conn-status {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: var(--text-secondary);
}
.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--green-dot);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.15);
}

.right { display: flex; align-items: center; gap: 14px; }
.api-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid var(--border-strong);
  background: #fff;
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  transition: all 0.15s;
}
.api-btn:hover { border-color: var(--primary); color: var(--primary); }
.api-btn svg { width: 15px; height: 15px; }

.avatar {
  width: 32px; height: 32px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>