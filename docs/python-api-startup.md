# Python API 启动与 seekdb 连接故障记录

适用环境：Windows PowerShell、仓库 `E:\competition\context-trace`、本机 Docker 中的 `contexttrace-seekdb`、前端 Vite 使用 5180 端口。

## 这次遇到的现象

- `GET http://127.0.0.1:8000/healthz` 返回 `{"status":"ok"}`。
- `GET http://127.0.0.1:8000/readyz` 返回 HTTP 503，错误码 `STORE_UNAVAILABLE`，提示 `seekdb is unavailable`。
- 检查时 Docker 容器正在运行，端口映射为 `127.0.0.1:2881->2881/tcp`；容器日志显示 SQL 服务已就绪，从 Windows 主机测试 2881 端口也可连接。
- 在**启动 API 的同一个终端**重新设置 seekdb 连接变量和密码，先执行数据库连接检查，再重启 API 后，`/readyz` 返回 `ok`。

`/healthz` 仅说明 Python Web 服务已启动，不会测试数据库；`/readyz` 才会实际连接 seekdb。此次的排查结果指向 **API 进程使用的连接配置或密码不匹配**。没有保存当时进程的完整配置，因此不能断言具体是哪一个变量出错。PowerShell 的 `$env:` 变量只传给当前终端启动的进程；在另一个终端设置密码，不会自动更新已经运行的 API。仓库的 `.env.example` 是模板，程序也不会自动读取 `.env`。

## 下次正确启动（已有数据库和表）

### 1. 确认 seekdb 容器运行

在 PowerShell 执行：

```powershell
docker ps --filter "name=contexttrace-seekdb"
```

若没有看到运行中的容器，启动已有容器：

```powershell
docker start contexttrace-seekdb
```

等容器启动完成。**日常启动无需重新建库或执行 `--init-schema`。**

### 2. 在准备运行 API 的同一个终端设置变量并检查连接

```powershell
cd E:\competition\context-trace

$env:SEEKDB_HOST = '127.0.0.1'
$env:SEEKDB_PORT = '2881'
$env:SEEKDB_USER = 'root'
$env:SEEKDB_DATABASE = 'context_trace'
$env:SEEKDB_PASSWORD = [System.Net.NetworkCredential]::new('', (Read-Host 'seekdb 密码' -AsSecureString)).Password
$env:YANJI_CORS_ORIGINS = 'http://localhost:5180,http://127.0.0.1:5180'

.\.venv\Scripts\python.exe -m yanji.store.client --check
```

必须先看到 `seekdb connection: OK`。这里不使用 `--prompt-password`：`--check` 直接读取当前终端的 `SEEKDB_PASSWORD`，与随后启动的 API 使用同一组环境变量。不要把密码写进仓库、前端 `.env.local` 或聊天记录。如果前端实际运行在其他端口，先把 `YANJI_CORS_ORIGINS` 改为终端显示的源地址。

### 3. 在同一个终端启动 API

```powershell
.\.venv\Scripts\python.exe -m uvicorn yanji.server.api:app --host 127.0.0.1 --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 后，保持该终端开启。要停止服务按 `Ctrl+C`。若重新打开终端，需要重新设置上述环境变量；若修改了 Python API 代码，也要停止后重新启动（当前命令没有 `--reload`）。

### 4. 在另一个终端验证

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

两项都应返回 `status: ok`。接口文档地址为 `http://127.0.0.1:8000/docs`；访问根路径 `/` 返回 404 是正常的。

## 再次出现 `STORE_UNAVAILABLE` 时

1. 看 `docker ps --filter "name=contexttrace-seekdb"`：容器是否运行，是否映射 `127.0.0.1:2881->2881/tcp`。
2. 在 Windows PowerShell 运行 `Test-NetConnection 127.0.0.1 -Port 2881`：`TcpTestSucceeded` 应为 `True`。若为 `False`，查看 `docker logs --tail 50 contexttrace-seekdb`，等待数据库完成启动。
3. 到运行 API 的终端按 `Ctrl+C` 停掉旧服务，再在**这个终端**重新设置上述变量并执行 `yanji.store.client --check`。若检查失败，以该命令的数据库错误为准，核对密码、库名、用户和端口；不要只根据 `/readyz` 的通用 503 信息猜测。
4. `--check` 成功后，从同一终端重新启动 API。如果 8000 端口仍被占用，先找到并停止旧 API 进程，不要让新旧进程混淆。

如果前端显示“无法连接对话 API”，先检查 Python API 是否仍在运行，再检查 `/healthz`、`/readyz` 和 Vite 实际端口对应的 CORS 配置。前端的模型 API Key 与本地 Python API/seekdb 连接是两件事，不影响这里的数据库就绪检查。
