<script setup>
import { SOURCES } from '../data/mock'

const props = defineProps({
  source: { type: String, required: true },
  size: { type: Number, default: 22 }
})

const info = SOURCES[props.source] || SOURCES.Agent
</script>

<template>
  <span
    class="source-badge"
    :style="{ width: size + 'px', height: size + 'px', background: info.color, fontSize: size * 0.5 + 'px' }"
  >{{ info.text }}</span>
</template>

<style scoped>
.source-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #fff;
  font-weight: 700;
  flex-shrink: 0;
  letter-spacing: 0;
}
</style>