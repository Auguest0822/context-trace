# 言迹 ContextTrace Agent 使用说明

## 连接

先在本机启动 seekdb 和 Python API；安装后端的 MCP 可选依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[mcp]'
```

同一个 API 进程在 `http://127.0.0.1:8000/mcp` 提供 Streamable HTTP。`127.0.0.1` 指运行 Agent 宿主的本机；远程 Agent 不能直接访问用户电脑上的这个地址。调用前先用 `/readyz` 确认数据库可用。

## 何时调用

- 开始项目任务前，调用 `memory_search`，明确传 `scope`、问题和范围。当前先用 `mode=keyword`；向量与混合尚未配置时会返回 `EMBEDDING_UNAVAILABLE`。
- 用户明确确认一条结论，并提供可核验原文时，调用 `memory_write`。文档/Git/手动来源必须提供 `source_ref` 和 `source_excerpt`；聊天来源需提供同一 scope 中已归档的 `conversation_id`、`source_message_ids` 和逐字证据，不能自称已经读到未提供的历史。
- 只有 Agent 宿主实际提供了消息，且用户确认归档时，才调用 `conversation_capture`。它只归档传入的消息，不会自动读取整个聊天历史。
- 接手项目时，调用 `memory_handoff`，说明目标并保留返回的出处；它只整理已存记忆。
- 新决定明确取代旧决定时，调用 `memory_reconcile`，指定旧记忆 ID、新结论及替代理由。
- 用户明确要求忘记某条记忆时，调用 `memory_forget`。删除不可恢复，调用前核对 ID 和范围。

这些工具与网页 HTTP API 调用同一业务函数和同一个 seekdb。`memory_search` 返回出处、轨迹 ID 和预算信息；在结果为空或数据库不可用时，向用户如实说明，不能编造旧记忆。
