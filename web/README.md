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

在仓库根目录执行：

```powershell
cd web
npm ci
npm run dev
```

浏览器打开终端显示的地址，当前默认是 `http://localhost:5180/#/archive`。验证生产构建可运行 `npm run build`。

### 对话档案的数据来源

默认使用 `src/data/mock.js`，所以队员只需 `npm ci`、`npm run dev`，无需搭建 seekdb。真实接口读取代码单独放在 `src/data/archiveApi.js`；拉取代码不会自动切换数据源。

需要本机联调 seekdb 时，在 **`web/.env.local`** 写入以下内容（该文件已被 Git 忽略）：

```dotenv
VITE_ARCHIVE_DATA_SOURCE=api
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_ARCHIVE_SCOPE=project:context-trace
```

先按仓库根目录的 [`docs/reproduction.md`](../docs/reproduction.md) 导入对话样例。**Docker 中运行 seekdb 不会自动启动 Python API**；需要保留两个终端，一个运行 Vite，另一个从仓库根目录运行 API。API 终端设置 seekdb 密码，并允许当前 Vite 端口：

```powershell
$env:SEEKDB_PASSWORD = [System.Net.NetworkCredential]::new('', (Read-Host 'seekdb 密码' -AsSecureString)).Password
$env:YANJI_CORS_ORIGINS = 'http://localhost:5180,http://127.0.0.1:5180'
.\.venv\Scripts\python.exe -m uvicorn yanji.server.api:app --host 127.0.0.1 --port 8000
```

连接信息若不是默认的 `127.0.0.1:2881`、`root`、`context_trace`，先在同一终端设置相应 `SEEKDB_HOST`、`SEEKDB_PORT`、`SEEKDB_USER`、`SEEKDB_DATABASE`。不要关闭 API 终端。另开一个终端分别检查 `http://127.0.0.1:8000/healthz`（API 已启动）和 `http://127.0.0.1:8000/readyz`（数据库可连），两者均应返回 `{"status":"ok"}`。`/` 返回 404 是正常的，因为 API 没有首页。

切换 `.env.local` 后**重启** `npm run dev`，打开 `http://localhost:5180/#/archive`；如果只是刚启动 API，在网页点“刷新”即可。切回假数据时删除 `web/.env.local` 或把 `VITE_ARCHIVE_DATA_SOURCE` 改为 `mock`，再重启 Vite。`web/.env.local` 只放前端数据源和 API 地址，**不要填写数据库密码或模型密钥**。

真实接口模式下，归档页读取对话列表、详情与消息列表；连接失败会显示错误，不会拿假数据充当数据库结果。选中 1–20 条消息后点击“提取记忆”，页面会请求人工候选预览。每条草稿都是所选消息的逐字片段，需由用户改写、勾选并确认，才会写入 seekdb。此流程不调用模型 API，不生成 embedding；提交后页面会读取记忆详情核对，并显示原始消息 ID 和证据片段。修改 Python API 代码后需停止并重新启动 Uvicorn（当前命令没有 `--reload`）。默认模拟模式继续使用假数据，队员无需数据库即可启动。

`web/src/`、`package.json` 和 `package-lock.json` 都需要提交到 Git。`node_modules/`、`.npm-cache/` 和 `dist/` 是本机生成的内容，已被 `.gitignore` 忽略；队友拉取代码后运行 `npm ci` 即可根据锁文件安装同一套依赖。切换分支或拉取到更新后的 `package-lock.json` 时，先停止旧的开发服务器，再重新运行 `npm ci` 和 `npm run dev`。

## 核心交互流程（默认模拟模式）

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
