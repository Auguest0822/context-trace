# 复现步骤

## seekdb 建库与连接验证（Windows PowerShell）

1. 启动现有 seekdb 容器，并确认 `docker ps` 中显示 `contexttrace-seekdb` 正在运行。确保库 `context_trace` 已创建，容器的 2881 端口已映射到本机。连接信息见根目录 `.env.example`。
2. 在仓库根目录用 Python 3.11 或更高版本安装依赖：

   ```powershell
   python -m pip install -e .
   ```

3. 设置连接参数。下例使用本机 Docker 默认端口；若容器映射不同，按实际修改：

   ```powershell
   $env:SEEKDB_HOST = '127.0.0.1'
   $env:SEEKDB_PORT = '2881'
   $env:SEEKDB_USER = 'root'
   $env:SEEKDB_DATABASE = 'context_trace'
   $env:SEEKDB_EMBEDDING_DIM = '1024'
   ```

4. 检查连接并初始化表结构。命令会提示输入数据库密码，不在终端回显：

   ```powershell
   python -m yanji.store.client --check --init-schema --prompt-password
   ```

   预期输出为 `seekdb connection: OK` 和 `seekdb schema: OK (9 tables)`。重复运行不会删除表或数据。`setup_check` 验证表会保留。若已有旧版 `memories` 草案表，命令会停止并要求先备份、迁移数据。

若不希望每次输入密码，可由运行环境提供 `SEEKDB_PASSWORD`；不要将真实密码提交到仓库。`.env.example` 只是变量模板，程序不会自动读取 `.env`。

## 导入原始对话样例

建表后在仓库根目录运行：

```powershell
python -m yanji.store.import_fixture data/fixtures/conversation-import.sample.json --prompt-password
python -m yanji.store.import_fixture data/fixtures/conversation-import.kimi.sample.json --prompt-password
```

首次导入分别应显示 `message_count=4` 和 `message_count=8`，共 12 条虚构消息。每个文件原样重试均返回首次结果，不重复插入；这一步不会提炼或写入记忆。静态样例与证据校验命令：

```powershell
python -m unittest discover -s python/tests -p test_fixture_contract.py -v
```

数据层的代码阅读顺序和验证 SQL 见 [`data-layer-guide.md`](data-layer-guide.md)；记忆候选与检索问题的用途见 [`samples/README.md`](samples/README.md)。

## 启动对话档案 HTTP API

日常启动命令、`healthz` 正常但 `readyz` 返回 `STORE_UNAVAILABLE` 的排查步骤，见 [Python API 启动与 seekdb 连接故障记录](python-api-startup.md)。

先按上文配置 seekdb 连接环境变量，并在启动服务的终端提供 `SEEKDB_PASSWORD`。然后从仓库根目录运行：

```powershell
python -m uvicorn yanji.server.api:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/docs` 可查看交互式接口文档。另开终端验证进程与数据库：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

导入一段样例对话，再按 scope 读取对话列表：

```powershell
$sample = Get-Content data/fixtures/conversation-import.sample.json -Raw -Encoding UTF8
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/conversations -ContentType 'application/json; charset=utf-8' -Body $sample
Invoke-RestMethod 'http://127.0.0.1:8000/v1/conversations?scope=project%3Acontext-trace'
```

首次创建返回 201；同一 `client_request_id` 原样重试会返回首次响应，不重复写入。详情和消息列表使用返回的十进制字符串 `conversation.id`，并在查询参数中继续传同一 `scope`。本地 Vite 页面默认允许从 `http://localhost:5173` 或 `http://127.0.0.1:5173` 调用 API；其他前端地址可用 `YANJI_CORS_ORIGINS` 配置为逗号分隔的源地址。

HTTP 层的本地测试命令：

```powershell
python -m pip install -e '.[dev]'
python -m unittest discover -s python/tests -v
```

## 从干净环境运行网页 + MCP 闭环

首次安装可运行 `python -m venv .venv`，然后用 `.\.venv\Scripts\python.exe -m pip install -e '.[mcp,dev]'` 安装 HTTP、MCP 与测试依赖。本机已有 `contexttrace-seekdb` 容器时只执行 `docker start contexttrace-seekdb`，不要再用 Compose 创建同名容器。

全新 Docker 环境可使用仓库根目录的 `compose.yaml`。它将官方 seekdb 1.4.0 镜像固定到 `1.4.0-100000172026082615`，数据库端口只绑定本机，并使用 Docker volume 保存数据。先在 PowerShell 中输入密码，再启动：

```powershell
$env:SEEKDB_ROOT_PASSWORD = [System.Net.NetworkCredential]::new('', (Read-Host 'seekdb 新密码' -AsSecureString)).Password
$env:SEEKDB_PASSWORD = $env:SEEKDB_ROOT_PASSWORD
docker compose up -d
```

该镜像及 Windows volume 路径依据 [OceanBase 官方 Docker 镜像说明](https://github.com/oceanbase/docker-images/blob/main/seekdb/README.md)，版本标签见 [Docker Hub](https://hub.docker.com/r/oceanbase/seekdb/tags)。待容器就绪后，在同一终端设置 `SEEKDB_HOST=127.0.0.1`、`SEEKDB_PORT=2881`、`SEEKDB_USER=root`、`SEEKDB_DATABASE=context_trace`，执行：

```powershell
.\.venv\Scripts\python.exe -m yanji.store.client --check --init-schema
.\.venv\Scripts\python.exe -m yanji.store.seed_demo
```

`seed_demo` 写入两段**虚构**对话和 15 条已确认的评测记忆，固定幂等键使重复执行不重复写入；它用于 D7/D12 演示与评测，不能代替 D4 的人工预览与确认验收。若要验收 D4，先只导入原始对话样例，确认预览不改变记忆数，再在网页选中候选确认写入。

在启动 API 的同一 PowerShell 终端设置 `$env:YANJI_CORS_ORIGINS='http://localhost:5180,http://127.0.0.1:5180'` 后运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn yanji.server.api:app --host 127.0.0.1 --port 8000
```

另开终端测试 `/readyz`；MCP Streamable HTTP 地址是 `http://127.0.0.1:8000/mcp`。官方 Python MCP SDK 的客户端可以列出 `conversation_capture`、`memory_write`、`memory_search`、`memory_reconcile`、`memory_handoff`、`memory_forget`。MCP 工具只接收宿主提供的消息和参数，不能自动读取宿主全部聊天历史。

网页在 `web/.env.local` 中设置 `VITE_ARCHIVE_DATA_SOURCE=api`、`VITE_API_BASE_URL=http://127.0.0.1:8000`、`VITE_ARCHIVE_SCOPE=project:context-trace`，然后在 `web` 目录依次运行 `npm ci` 和 `npm run dev`。默认不设置 `.env.local` 时，队员仍可使用 mock 页面，无需数据库。

## 向量基线与固定评测

默认只启用关键词检索。为验证 seekdb 的 1024 维向量与混合链路，在启动 API 和回填命令所用的终端设置 `$env:YANJI_EMBEDDING_BACKEND='hash'`，并运行：

```powershell
.\.venv\Scripts\python.exe -m yanji.store.backfill_embeddings --scope project:context-trace
.\.venv\Scripts\python.exe -m yanji.store.seed_demo --scope benchmark:context-trace-v1
.\.venv\Scripts\python.exe -m yanji.eval.run_benchmark --scope benchmark:context-trace-v1
```

网页如需显示“向量/混合”按钮，在 `web/.env.local` 增加 `VITE_ENABLE_VECTOR_SEARCH=true` 并重启 Vite。`char-ngram-hash-v1` 是无需模型 API 的**词形向量基线**，不能当作神经语义 embedding 的效果；评测报告必须写明该限制。30 道固定问题在 `data/fixtures/search-eval.json`，程序只在真实 seekdb 中运行后写出 `docs/benchmark-results.json`。没有真实运行结果时，不得填造命中率或耗时。

## 按天复跑后端验收

确认 `/readyz` 为 `ok` 后，可在另一个终端从仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m yanji.eval.live_acceptance
```

脚本使用每次新生成的 `acceptance:<UUID>` scope，依次验证 D2、D3、D4、D5、D9、D10、D11 的真实 HTTP/seekdb 行为；输出每项 `PASS` 和证据。它只对自己新建的一条记忆执行 D10 遗忘，测试 scope 留在数据库中供复核。启用 `YANJI_EMBEDDING_BACKEND=hash` 并重启 API 后可加 `--vector`，把 D8 的 seekdb 向量和混合 SQL 也纳入验收。脚本不替代 D6 的真实 Agent 宿主联调、D7 的网页全链路、D12 的 30 题评测或 D13 的干净环境复走。

安装 `.[mcp,dev]` 后还可运行 `python -m yanji.eval.mcp_acceptance`。它经 `/mcp` 写入一条新 scope 记忆、经 HTTP 读回、再由 MCP 搜索同一条记忆，作为 D6 的协议和同库验证；真实 Agent 宿主仍需另行连接演示。
