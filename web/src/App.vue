<script setup>
import { store } from './store'
import SideBar from './components/SideBar.vue'
import TopBar from './components/TopBar.vue'
import ApiSettingsDrawer from './components/ApiSettingsDrawer.vue'
</script>

<template>
  <div class="app-layout">
    <SideBar />
    <div class="main-area">
      <TopBar />
      <div class="page-area">
        <router-view />
      </div>
    </div>
    <ApiSettingsDrawer v-if="store.apiDrawerOpen" />

    <transition name="toast">
      <div v-if="store.toast.show" class="toast">{{ store.toast.text }}</div>
    </transition>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.page-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
}
</style>