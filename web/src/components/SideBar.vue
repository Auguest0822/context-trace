<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { key: 'archive', label: '对话档案', to: '/archive', icon: 'chat' },
  { key: 'memory', label: '记忆库', to: '/memories', icon: 'db' },
  { key: 'search', label: '记忆检索', to: '/search', icon: 'search' },
  { key: 'recall', label: '召回记录', to: '/recall', icon: 'shield' },
  { key: 'versions', label: '版本与冲突', to: '/versions', icon: 'loop' }
]

function isActive(item) {
  if (item.key === 'archive') return route.meta.nav === 'archive'
  return route.meta.nav === item.key
}
</script>

<template>
  <aside class="sidebar">
    <div class="logo">
      <span class="logo-cn">言迹</span>
      <span class="logo-en">ContextTrace</span>
    </div>
    <nav class="nav">
      <router-link
        v-for="item in navItems"
        :key="item.key"
        :to="item.to"
        class="nav-item"
        :class="{ active: isActive(item) }"
      >
        <span class="nav-icon">
          <!-- 对话气泡 -->
          <svg v-if="item.icon === 'chat'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
          </svg>
          <!-- 数据库 -->
          <svg v-else-if="item.icon === 'db'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"/>
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
          </svg>
          <!-- 搜索 -->
          <svg v-else-if="item.icon === 'search'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/>
            <path d="m21 21-4.35-4.35"/>
          </svg>
          <!-- 召回盾牌 -->
          <svg v-else-if="item.icon === 'shield'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          <!-- 版本循环 -->
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M23 4v6h-6"/>
            <path d="M1 20v-6h6"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
        </span>
        <span class="nav-label">{{ item.label }}</span>
      </router-link>
    </nav>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 200px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid var(--border);
  padding: 20px 12px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}
.logo {
  padding: 0 10px;
  display: flex;
  align-items: baseline;
  gap: 7px;
  white-space: nowrap;
}
.logo-cn {
  font-size: 19px;
  font-weight: 700;
  color: #111827;
  letter-spacing: 1px;
}
.logo-en {
  font-size: 15px;
  font-weight: 700;
  color: var(--primary);
}
.nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  transition: all 0.15s;
}
.nav-item:hover {
  background: #f2f6f5;
  color: var(--text);
}
.nav-item.active {
  background: var(--primary-bg);
  color: var(--primary);
  font-weight: 600;
}
.nav-icon {
  width: 18px;
  height: 18px;
  display: inline-flex;
}
.nav-icon svg { width: 100%; height: 100%; }
</style>
