# 言迹 ContextTrace

把用户主动保存的 AI 对话归档为原始消息，再由用户挑选、确认记忆。网页与 Agent MCP 工具读写同一份 seekdb；每条聊天记忆保留可点击回原消息的证据。

## 最短运行路径

详细的 Windows、Docker、密码、建表、样例、向量基线与评测命令见 [复现步骤](docs/reproduction.md)。日常重启遇到 `/healthz` 正常、`/readyz` 失败时看 [Python API 启动排查](docs/python-api-startup.md)。

1. 启动本机 seekdb 1.4，初始化 `context_trace` 库及表。
2. 在仓库根目录安装 Python 包：`.\.venv\Scripts\python.exe -m pip install -e '.[mcp,dev]'`。
3. 运行 `.\.venv\Scripts\python.exe -m yanji.store.seed_demo` 导入两段虚构对话与 15 条评测记忆。
4. 在设置好 `SEEKDB_*` 环境变量的同一终端运行 `.\.venv\Scripts\python.exe -m uvicorn yanji.server.api:app --host 127.0.0.1 --port 8000`。
5. 在 `web` 目录运行 `npm ci`、`npm run dev`。默认 mock；本机真实模式按 [网页说明](web/README.md) 设置 `web/.env.local`。

检查：`http://127.0.0.1:8000/healthz` 表示 API 进程可用；`/readyz` 表示 seekdb 可连接；`/docs` 是 HTTP 交互文档；`/mcp` 是 Agent Streamable HTTP 入口。`web/.env.local` 只配置本地 API 地址和数据源，不放数据库密码或模型密钥。

## 两周闭环

- **原始对话**：手动导入或 Agent 宿主明确提供的消息，按角色、顺序和来源归档；归档本身不产生记忆。
- **确认记忆**：网页选消息 → 预览逐字候选 → 用户编辑并确认 → 校验出处后入库。文档/Git/手动结论也可带来源直接写入。
- **检索与上下文**：按 scope、状态、类别、平台、对话和时间过滤；关键词检索默认可用。用户取消勾选后，后端只组装仍被选中的记忆，保留出处与预算取舍。
- **Agent MCP**：`conversation_capture`、`memory_write`、`memory_search`、`memory_reconcile`、`memory_handoff`、`memory_forget` 共用 HTTP 业务函数。MCP 不自动读取宿主全部聊天历史。
- **向量基线**：设置 `YANJI_EMBEDDING_BACKEND=hash` 后，生成本地 1024 维字符特征向量、回填旧记忆，并启用向量与混合检索。该基线是词形匹配，不代表神经语义 embedding 效果。

浏览器扩展排在网页 + MCP 必做闭环之后，不是运行演示的前提。数据与 API 规则见 [契约](docs/api-data-contract.md)，逐日目标与验收见 [14 天计划](docs/14-day-team-plan.md)，实测状态见 [结果记录](docs/RESULTS.md)。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s python/tests -v
```

在 `web` 目录运行 `node --test tests/*.test.js` 和 `npm run build`。真实数据库验收与 30 道固定问题的结果只在 seekdb 可用后写入 `docs/RESULTS.md`，不会用模拟测试代替。

## 许可

Apache-2.0
