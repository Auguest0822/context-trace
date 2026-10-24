import { createRouter, createWebHashHistory } from 'vue-router'
import ArchiveView from './views/ArchiveView.vue'
import MemoryExtractView from './views/MemoryExtractView.vue'
import MemorySearchView from './views/MemorySearchView.vue'
import MemoryLibraryView from './views/MemoryLibraryView.vue'
import RecallView from './views/RecallView.vue'
import VersionsView from './views/VersionsView.vue'

const routes = [
  { path: '/', redirect: '/archive' },
  { path: '/archive', name: 'archive', component: ArchiveView, meta: { nav: 'archive' } },
  { path: '/extract', name: 'extract', component: MemoryExtractView, meta: { nav: 'archive' } },
  { path: '/memories', name: 'memories', component: MemoryLibraryView, meta: { nav: 'memory' } },
  { path: '/search', name: 'search', component: MemorySearchView, meta: { nav: 'search' } },
  { path: '/recall', name: 'recall', component: RecallView, meta: { nav: 'recall' } },
  { path: '/versions', name: 'versions', component: VersionsView, meta: { nav: 'versions' } }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
