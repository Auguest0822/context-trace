<script setup>
const props = defineProps({
  category: { type: String, required: true }
})
const styleMap = {
  '决策': { color: '#b45309', bg: '#fef3c7', border: '#fde68a' },
  '约束': { color: '#6d28d9', bg: '#ede9fe', border: '#ddd6fe' },
  '行动': { color: '#b45309', bg: '#fef3c7', border: '#fde68a' },
  '事实': { color: '#1d4ed8', bg: '#dbeafe', border: '#bfdbfe' }
}
const s = styleMap[props.category] || styleMap['事实']
</script>

<template>
  <span class="category-tag" :style="{ color: s.color, background: s.bg, borderColor: s.border }">
    <span class="dot"></span>{{ category }}
  </span>
</template>

<style scoped>
.category-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid transparent;
  white-space: nowrap;
}
.dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
</style>