<script setup>
defineProps({
  title: { type: String, required: true },
  desc: { type: String, required: true }
})
</script>

<template>
  <div class="placeholder">
    <h1>{{ title }}</h1>
    <p class="desc">{{ desc }}</p>
    <div class="empty-card">
      <div class="empty-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
        </svg>
      </div>
      <p class="empty-title">该页面即将上线</p>
      <p class="empty-desc">当前设计稿未包含此页面的详细布局，可先在「对话档案」「记忆检索」中体验完整流程。</p>
    </div>
  </div>
</template>

<style scoped>
.placeholder h1 { font-size: 22px; font-weight: 700; }
.desc { margin-top: 8px; font-size: 13.5px; color: var(--text-secondary); }
.empty-card {
  margin-top: 40px;
  background: #fff;
  border: 1px dashed var(--border-strong);
  border-radius: 12px;
  padding: 56px 32px;
  text-align: center;
}
.empty-icon {
  width: 44px; height: 44px;
  margin: 0 auto;
  color: var(--text-tertiary);
}
.empty-icon svg { width: 100%; height: 100%; }
.empty-title { margin-top: 16px; font-size: 15px; font-weight: 600; }
.empty-desc { margin-top: 8px; font-size: 13px; color: var(--text-tertiary); }
</style>