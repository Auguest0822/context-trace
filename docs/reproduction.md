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

## 完整 Demo 与评测

MCP 和网页的端到端复现命令将在对应实现完成后补充；当前 HTTP 层仅覆盖对话归档与读取。
