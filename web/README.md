# 言迹 ContextTrace

基于 Vue 3 + Vite 实现的「言迹 ContextTrace」记忆管理前端，UI 依照设计稿实现 4 个界面：

| 页面 | 路由 | 说明 |
|---|---|---|
| 对话档案 | `#/archive` | 来源过滤、会话列表、消息勾选、提取记忆入口 |
| 记忆提炼确认 | `#/extract` | 左侧已选内容、右侧候选记忆（可编辑/证据引用）、确认保存 |
| 记忆检索 | `#/search` | 问题检索、来源/类别/检索方式筛选、最终上下文组装与复制、命中解释 |
| API 设置抽屉 | 顶栏按钮 | 右侧滑出：模型/密钥配置、连接测试、保存 |

「召回记录」「版本与冲突」为设计稿外的占位页。

## 运行

```bash
npm install
npm run dev      # http://localhost:5180
npm run build    # 生产构建
```

## 核心交互流程

1. **对话档案** → 勾选消息（默认已选 #2、#3）→ 点击「提取记忆」
2. **提炼确认页** → 编辑候选记忆、勾选 → 「确认保存 N 条」（写入记忆库/搜索数据源）
3. **记忆检索** → 查找记忆 → 勾选结果组装上下文 → 「复制上下文」
4. 顶栏「模型与 API 设置」→ 抽屉中填密钥 → 「测试连接」→「保存设置」

## 目录结构

```
src/
├── main.js              # 入口
├── router.js            # 路由（hash 模式）
├── store.js             # 轻量全局状态（reactive）
├── style.css            # 设计变量 + 通用样式（主色 teal #0f766e）
├── data/mock.js         # 模拟数据
├── components/
│   ├── SideBar.vue      # 左侧导航
│   ├── TopBar.vue       # 顶栏（项目选择/连接状态/API 设置入口）
│   ├── ApiSettingsDrawer.vue
│   ├── SourceBadge.vue  # 来源 logo 徽章
│   └── CategoryTag.vue  # 记忆类别徽章
└── views/
    ├── ArchiveView.vue
    ├── MemoryExtractView.vue
    ├── MemorySearchView.vue
    └── PlaceholderView.vue
```
