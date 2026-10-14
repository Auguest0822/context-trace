import { createRouter, createWebHashHistory } from 'vue-router'
import ArchiveView from './views/ArchiveView.vue'
import MemoryExtractView from './views/MemoryExtractView.vue'
import MemorySearchView from './views/MemorySearchView.vue'
import PlaceholderView from './views/PlaceholderView.vue'

const routes = [
  { path: '/', redirect: '/archive' },
  { path: '/archive', name: 'archive', component: ArchiveView, meta: { nav: 'archive' } },
  { path: '/extract', name: 'extract', component: MemoryExtractView, meta: { nav: 'archive' } },
  { path: '/search', name: 'search', component: MemorySearchView, meta: { nav: 'search' } },
  { path: '/recall', name: 'recall', component: PlaceholderView, meta: { nav: 'recall' }, props: { title: '召回记录', desc: '查看记忆被召回使用的完整历史，追踪每条记忆在检索中的命中情况。' } },
  { path: '/versions', name: 'versions', component: PlaceholderView, meta: { nav: 'versions' }, props: { title: '版本与冲突', desc: '管理记忆的版本演进，处理新记忆与已有记忆之间的冲突。' } }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router