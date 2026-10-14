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

## 完整 Demo 与评测

HTTP、MCP 和网页的端到端复现命令将在对应实现完成后补充；目前建库成功不代表业务接口已可用。
